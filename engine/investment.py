"""Investment committee analytics; assumptions are explicit and data is synthetic."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp


def validate_financials(history: pd.DataFrame) -> None:
    keys = ["property_id", "month"]
    if history.duplicated(keys).any():
        raise ValueError("Duplicate property-month records")
    numeric = history[["revenue", "operating_expenses", "noi", "occupancy"]]
    if not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("Non-finite financial data")
    if not history.occupancy.between(0, 1).all():
        raise ValueError("Occupancy outside 0-100%")
    if not np.allclose(history.noi, history.revenue - history.operating_expenses, atol=0.01):
        raise ValueError("NOI reconciliation failed")


def optimize_projects(projects: pd.DataFrame, budget: float) -> pd.DataFrame:
    """Binary knapsack maximizing declared priority, at most one project per asset."""
    if budget < 0 or not np.isfinite(budget):
        raise ValueError("Budget must be finite and nonnegative")
    if projects.empty:
        return projects.copy()
    costs = projects.capital_required.to_numpy(float)
    scores = projects.priority_score.to_numpy(float)
    if not np.isfinite(costs).all() or (costs <= 0).any() or not np.isfinite(scores).all():
        raise ValueError("Invalid project cost or priority")
    groups = pd.get_dummies(projects.property_id, dtype=float).to_numpy().T
    matrix = np.vstack([costs / 1e6, groups])
    upper = np.r_[budget / 1e6, np.ones(len(groups))]
    result = milp(-scores, integrality=np.ones(len(costs)), bounds=Bounds(0, 1),
                  constraints=LinearConstraint(matrix, 0, upper),
                  options={"time_limit": 10, "mip_rel_gap": 0})
    if not result.success:
        raise RuntimeError(f"Capital optimization did not converge: {result.message}")
    selected = projects.loc[result.x > 0.5].copy().sort_values("priority_score", ascending=False)
    if selected.capital_required.sum() > budget + 0.01:
        raise RuntimeError("Solver budget reconciliation failed")
    selected["selected_order"] = np.arange(1, len(selected) + 1)
    return selected


def credit_and_valuation(frame: pd.DataFrame, payment_function, *, discount_rate=0.08,
                         growth=0.02, max_ltv=0.65, min_dscr=1.25) -> pd.DataFrame:
    out = frame.copy()
    annual_noi = out.noi * 12
    annual_payment = out.debt_service * 12
    out["debt_yield"] = annual_noi / out.loan_balance
    out["cash_after_debt"] = annual_noi - annual_payment
    out["dscr_headroom"] = annual_noi - min_dscr * annual_payment
    rent_at_full_occupancy = out.revenue / out.occupancy
    out["break_even_occupancy"] = (out.operating_expenses + out.debt_service) / rent_at_full_occupancy
    # Illustrative underwriting policy, not a CMHC eligibility rule or loan quote.
    mortgage_constant = out.apply(lambda row: 12 * payment_function(
        1, row.interest_rate, int(row.amortization_years)), axis=1)
    ltv_capacity = max_ltv * out.property_value.clip(lower=0)
    dscr_capacity = (annual_noi / min_dscr / mortgage_constant).clip(lower=0)
    out["refinance_capacity"] = np.minimum(ltv_capacity, dscr_capacity)
    out["refinance_gap"] = (out.loan_balance - out.refinance_capacity).clip(lower=0)
    out["binding_constraint"] = np.where(ltv_capacity < dscr_capacity, "LTV", "DSCR")
    out["dcf_value"] = sum(annual_noi * (1 + growth) ** year / (1 + discount_rate) ** year
                           for year in range(1, 6))
    out["dcf_value"] += annual_noi * (1 + growth) ** 6 / out.cap_rate * 0.98 / (1 + discount_rate) ** 5
    out["dcf_vs_cap_value"] = out.dcf_value / out.property_value - 1
    return out


def historical_risk(history: pd.DataFrame, frame: pd.DataFrame) -> dict:
    validate_financials(history)
    levels = history.pivot(index="month", columns="property_id", values="noi").sort_index()
    changes = levels.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna()
    if len(changes) < 12:
        raise ValueError("At least 12 aligned monthly NOI changes are required")
    weights = frame.set_index("property_id").property_value.reindex(changes.columns)
    weights = weights / weights.sum()
    covariance = changes.cov().to_numpy()
    w = weights.to_numpy()
    variance = float(w @ covariance @ w)
    contributions = w * (covariance @ w)
    portfolio_changes = changes.to_numpy() @ w
    losses = -portfolio_changes
    var = float(np.quantile(losses, 0.95))
    es = float(losses[losses >= var].mean())
    names = frame.set_index("property_id").property_name
    attribution = [{"property": names[pid], "weight": float(weights[pid]),
                    "variance_share": float(contributions[i] / variance) if variance > 0 else 0}
                   for i, pid in enumerate(changes.columns)]
    return {"observations": len(changes), "monthly_noi_volatility": float(np.sqrt(variance)),
            "historical_noi_var_95": var, "historical_noi_es_95": es,
            "value_hhi": float(w @ w), "effective_assets": float(1 / (w @ w)),
            "attribution": sorted(attribution, key=lambda row: row["variance_share"], reverse=True),
            "history": [{"month": str(month), "noi": float(value)}
                        for month, value in levels.sum(axis=1).items()],
            "method": "Fixed current value weights applied to historical monthly NOI changes; not investment returns. Synthetic data, descriptive in-sample estimates."}

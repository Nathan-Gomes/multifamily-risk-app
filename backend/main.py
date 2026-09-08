from __future__ import annotations

import json
import math
import sys
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.risk_engine import (  # noqa: E402
    CONFIG,
    apply_scenario,
    prioritize_capital,
    run_pipeline,
    score_properties,
)

FRONTEND = ROOT / "frontend"
GENERATED = ROOT / "data" / "generated"
PIPELINE_LOCK = Lock()

app = FastAPI(title="Multifamily Portfolio Risk API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def clean_value(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.replace([float("inf"), float("-inf")], pd.NA).to_json(orient="records"))


def money(value: float) -> str:
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value / 1_000:.0f}k"


@lru_cache(maxsize=1)
def cached_pipeline() -> dict[str, Any]:
    return run_pipeline(GENERATED)


def base_pipeline() -> dict[str, Any]:
    with PIPELINE_LOCK:
        return cached_pipeline()


def custom_scenario_summary(frame: pd.DataFrame, scenario: dict[str, float]) -> dict[str, Any]:
    stressed = score_properties(apply_scenario(frame, scenario))
    base_value = frame["property_value"].sum()
    base_noi = frame["noi"].sum() * 12
    stressed_value = stressed["property_value"].sum()
    stressed_noi = stressed["noi"].sum() * 12
    return {
        "portfolio_value": clean_value(float(stressed_value)),
        "annual_noi": clean_value(float(stressed_noi)),
        "value_change_pct": clean_value(float(stressed_value / base_value - 1)),
        "noi_change_pct": clean_value(float(stressed_noi / base_noi - 1)),
        "properties_below_1_10_dscr": int((stressed["dscr"] < 1.10).sum()),
        "highest_risk": records(stressed.head(8)),
    }


def get_dashboard_payload(
    capital_budget: float,
    occupancy_shock: float,
    expense_shock: float,
    rate_shock_bps: float,
    cap_rate_shock_bps: float,
) -> dict[str, Any]:
    result = base_pipeline()
    base_scored = result["scored"].copy()
    custom_scenario = {
        "occupancy_shock": occupancy_shock,
        "expense_shock": expense_shock,
        "rate_shock_bps": rate_shock_bps,
        "cap_rate_shock_bps": cap_rate_shock_bps,
    }
    if all(float(value) == 0 for value in custom_scenario.values()):
        scored = base_scored.copy()
    else:
        scored = score_properties(apply_scenario(base_scored, custom_scenario))
    concentration = {
        "market": scored.groupby("market", as_index=False)["property_value"].sum(),
        "maturity": scored.groupby("maturity_year", as_index=False)["loan_balance"].sum(),
        "rate_type": scored.groupby("rate_type", as_index=False)["loan_balance"].sum(),
        "loan_type": scored.groupby("loan_type", as_index=False)["loan_balance"].sum(),
    }
    concentration["market"]["exposure_pct"] = (
        concentration["market"]["property_value"] / concentration["market"]["property_value"].sum()
    )
    concentration["rate_type"]["exposure_pct"] = (
        concentration["rate_type"]["loan_balance"] / concentration["rate_type"]["loan_balance"].sum()
    )
    concentration["loan_type"]["exposure_pct"] = (
        concentration["loan_type"]["loan_balance"] / concentration["loan_type"]["loan_balance"].sum()
    )
    concentration["market"] = concentration["market"].sort_values("property_value", ascending=False)
    concentration["maturity"] = concentration["maturity"].sort_values("maturity_year")
    concentration["rate_type"] = concentration["rate_type"].sort_values("loan_balance", ascending=False)
    concentration["loan_type"] = concentration["loan_type"].sort_values("loan_balance", ascending=False)
    capital = prioritize_capital(scored, result["data"]["capital_projects"], capital_budget)
    market = concentration["market"].copy()
    maturity = concentration["maturity"].copy()
    market["property_value_display"] = market["property_value"].map(money)
    maturity["loan_balance_display"] = maturity["loan_balance"].map(money)
    summary = dict(result["summary"])
    summary["base_portfolio_value"] = result["summary"]["portfolio_value"]
    summary["base_annual_noi"] = result["summary"]["annual_noi"]
    summary["portfolio_value"] = float(scored["property_value"].sum())
    summary["annual_noi"] = float(scored["noi"].sum() * 12)
    summary["weighted_ltv"] = float((scored["ltv"] * scored["property_value"]).sum() / scored["property_value"].sum())
    summary["weighted_dscr"] = float((scored["dscr"] * scored["property_value"]).sum() / scored["property_value"].sum())
    summary["elevated_or_high"] = int(scored["risk_band"].isin(["Elevated", "High"]).sum())
    summary["cmhc_debt"] = float(scored.loc[scored["loan_type"].eq("CMHC-insured"), "loan_balance"].sum())
    summary["cmhc_debt_share"] = float(summary["cmhc_debt"] / scored["loan_balance"].sum())
    summary["scenario_value_change_pct"] = summary["portfolio_value"] / result["summary"]["portfolio_value"] - 1
    summary["scenario_noi_change_pct"] = summary["annual_noi"] / result["summary"]["annual_noi"] - 1
    summary["capital_budget"] = capital_budget
    summary["selected_capital"] = float(capital["capital_required"].sum()) if not capital.empty else 0.0
    summary["selected_projects"] = int(len(capital))
    return {
        "summary": {key: clean_value(value) for key, value in summary.items()},
        "properties": records(scored),
        "top_risk": records(scored.head(8)),
        "scenarios": records(result["scenarios"]),
        "custom_scenario": custom_scenario_summary(base_scored, custom_scenario),
        "capital_plan": records(capital.head(12)) if not capital.empty else [],
        "concentration": {
            "market": records(market),
            "maturity": records(maturity),
            "rate_type": records(concentration["rate_type"]),
            "loan_type": records(concentration["loan_type"]),
        },
        "config": {
            "as_of_month": CONFIG["as_of_month"],
            "default_capital_budget": CONFIG["capital_budget"],
            "risk_score_weights": CONFIG["risk_score_weights"],
        },
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "mode": "demo"}


@app.get("/api/dashboard")
def dashboard(
    capital_budget: float = Query(2_000_000, ge=0, le=10_000_000),
    occupancy_shock: float = Query(0, ge=-0.25, le=0.10),
    expense_shock: float = Query(0, ge=-0.10, le=0.50),
    rate_shock_bps: float = Query(0, ge=-200, le=600),
    cap_rate_shock_bps: float = Query(0, ge=-100, le=400),
) -> dict[str, Any]:
    return get_dashboard_payload(
        capital_budget=capital_budget,
        occupancy_shock=occupancy_shock,
        expense_shock=expense_shock,
        rate_shock_bps=rate_shock_bps,
        cap_rate_shock_bps=cap_rate_shock_bps,
    )


@app.get("/api/properties/{property_id}")
def property_detail(property_id: str) -> dict[str, Any]:
    result = base_pipeline()
    properties = result["data"]["properties"]
    financials = result["data"]["monthly_financials"]
    debt = result["data"]["debt"]
    valuations = result["data"]["valuations"]
    scored = result["scored"]
    if property_id not in set(properties["property_id"]):
        raise HTTPException(status_code=404, detail="Property not found")
    return {
        "property": records(properties.loc[properties["property_id"] == property_id])[0],
        "latest_metrics": records(scored.loc[scored["property_id"] == property_id])[0],
        "debt": records(debt.loc[debt["property_id"] == property_id])[0],
        "history": records(financials.loc[financials["property_id"] == property_id].sort_values("month")),
        "valuations": records(valuations.loc[valuations["property_id"] == property_id].sort_values("month")),
    }


@app.get("/api/export")
def export_payload() -> dict[str, Any]:
    return get_dashboard_payload(
        capital_budget=CONFIG["capital_budget"],
        occupancy_shock=CONFIG["scenarios"]["combined_downside"]["occupancy_shock"],
        expense_shock=CONFIG["scenarios"]["combined_downside"]["expense_shock"],
        rate_shock_bps=CONFIG["scenarios"]["combined_downside"]["rate_shock_bps"],
        cap_rate_shock_bps=CONFIG["scenarios"]["combined_downside"]["cap_rate_shock_bps"],
    )


app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")

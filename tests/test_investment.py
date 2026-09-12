import itertools
import numpy as np
import pandas as pd
import pytest
from engine.investment import optimize_projects, credit_and_valuation, historical_risk, validate_financials
from engine.risk_engine import monthly_debt_service, apply_scenario, generate_sample_data
from backend.main import base_pipeline


def test_optimizer_matches_exhaustive_and_beats_greedy():
    projects = pd.DataFrame({'property_id': ['a','b','c'], 'capital_required': [6,5,5], 'priority_score': [10,9,9]})
    result = optimize_projects(projects, 10)
    best = max(sum(projects.priority_score * bits) for bits in itertools.product([0,1], repeat=3)
               if sum(projects.capital_required * bits) <= 10)
    assert result.priority_score.sum() == best == 18
    assert optimize_projects(projects, 0).empty


def test_one_project_per_asset():
    frame = pd.DataFrame({'property_id': ['a','a'], 'capital_required': [1,1], 'priority_score': [4,5]})
    assert optimize_projects(frame, 10).priority_score.sum() == 5


def test_credit_and_dcf_closed_form():
    frame = pd.DataFrame([dict(noi=100, debt_service=50, loan_balance=10000,
        revenue=200, operating_expenses=100, occupancy=.9, property_value=20000,
        interest_rate=0, amortization_years=20, cap_rate=.06)])
    result = credit_and_valuation(frame, monthly_debt_service, growth=0).iloc[0]
    assert result.debt_yield == .12
    assert result.break_even_occupancy == pytest.approx(.675)
    assert result.refinance_capacity == pytest.approx(min(13000, 1200/1.25/.05))
    assert result.dcf_value == pytest.approx(sum(1200/1.08**t for t in range(1,6)) + 20000*.98/1.08**5)


def test_stress_refreshes_derived_metrics():
    frame = base_pipeline()['scored']
    result = apply_scenario(frame, dict(occupancy_shock=-.05, expense_shock=.1, rate_shock_bps=100, cap_rate_shock_bps=50))
    assert np.allclose(result.noi_yoy, result.noi/result.noi_12m_ago-1)
    assert np.allclose(result.cash_flow, result.noi-result.debt_service)
    assert (result.noi < frame.noi).all()


def test_risk_attribution_reconciles():
    result = base_pipeline()
    risk = historical_risk(result['data']['monthly_financials'], result['scored'])
    assert sum(row['variance_share'] for row in risk['attribution']) == pytest.approx(1)
    assert risk['historical_noi_es_95'] >= risk['historical_noi_var_95']
    assert 1 <= risk['effective_assets'] <= 24


def test_duplicate_and_invalid_financials_rejected():
    data = generate_sample_data()['monthly_financials']
    with pytest.raises(ValueError, match='Duplicate'):
        validate_financials(pd.concat([data, data.iloc[:1]]))
    data.loc[0, 'noi'] += 100
    with pytest.raises(ValueError, match='reconciliation'):
        validate_financials(data)

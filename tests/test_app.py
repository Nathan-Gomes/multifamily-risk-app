import csv
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.main import get_dashboard_payload


client = TestClient(app)


def test_health_endpoint_reports_demo_mode():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "demo"}


def test_dashboard_payload_contains_core_sections():
    payload = get_dashboard_payload(
        capital_budget=2_000_000,
        occupancy_shock=-0.05,
        expense_shock=0.10,
        rate_shock_bps=200,
        cap_rate_shock_bps=100,
    )
    assert payload["summary"]["property_count"] == 24
    assert len(payload["properties"]) == 24
    assert len(payload["top_risk"]) > 0
    assert len(payload["capital_plan"]) > 0
    assert "loan_type" in payload["properties"][0]
    assert len(payload["concentration"]["loan_type"]) > 0


def test_custom_stress_scenario_reduces_value():
    payload = get_dashboard_payload(
        capital_budget=2_000_000,
        occupancy_shock=-0.08,
        expense_shock=0.12,
        rate_shock_bps=250,
        cap_rate_shock_bps=125,
    )
    assert payload["custom_scenario"]["value_change_pct"] < 0
    assert payload["custom_scenario"]["properties_below_1_10_dscr"] >= 0


def test_capital_budget_is_respected():
    budget = 1_250_000
    payload = get_dashboard_payload(
        capital_budget=budget,
        occupancy_shock=-0.05,
        expense_shock=0.10,
        rate_shock_bps=200,
        cap_rate_shock_bps=100,
    )
    assert payload["summary"]["selected_capital"] <= budget


def test_cmhc_debt_is_reported():
    payload = get_dashboard_payload(
        capital_budget=2_000_000,
        occupancy_shock=0,
        expense_shock=0,
        rate_shock_bps=0,
        cap_rate_shock_bps=0,
    )
    assert payload["summary"]["cmhc_debt"] > 0
    assert 0 < payload["summary"]["cmhc_debt_share"] < 1
    loan_types = {row["loan_type"] for row in payload["concentration"]["loan_type"]}
    assert "CMHC-insured" in loan_types


def test_property_detail_endpoint_returns_expected_sections():
    response = client.get("/api/properties/P001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["property"]["property_id"] == "P001"
    assert payload["latest_metrics"]["property_id"] == "P001"
    assert payload["debt"]["property_id"] == "P001"
    assert len(payload["history"]) > 0
    assert len(payload["valuations"]) > 0


def test_property_detail_endpoint_rejects_unknown_property():
    response = client.get("/api/properties/UNKNOWN")
    assert response.status_code == 404
    assert response.json()["detail"] == "Property not found"


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("capital_budget", -1),
        ("occupancy_shock", -0.26),
        ("expense_shock", 0.51),
        ("rate_shock_bps", 601),
        ("cap_rate_shock_bps", 401),
    ],
)
def test_dashboard_endpoint_rejects_out_of_range_inputs(parameter, value):
    response = client.get("/api/dashboard", params={parameter: value})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == parameter


def test_research_metrics_endpoint_returns_downloadable_csv():
    response = client.get("/api/research/metrics")
    rows = list(csv.DictReader(StringIO(response.text)))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="metrics.csv"'
    assert len(rows) == 24
    assert {"property_id", "dscr", "ltv", "refinance_gap"} <= rows[0].keys()


def test_research_endpoint_rejects_unknown_dataset():
    response = client.get("/api/research/not-a-dataset")
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown research dataset"

# Multifamily Portfolio Risk Workspace

![Python](https://img.shields.io/badge/Python-analytics%20engine-0d1117?style=for-the-badge&logo=python&logoColor=58a6ff)
![FastAPI](https://img.shields.io/badge/FastAPI-API%20backend-0d1117?style=for-the-badge&logo=fastapi&logoColor=2ea043)
![SQLite](https://img.shields.io/badge/SQLite-sample%20portfolio%20data-0d1117?style=for-the-badge&logo=sqlite&logoColor=7ee787)
![Tests](https://img.shields.io/badge/tests-pytest-0d1117?style=for-the-badge&logo=pytest&logoColor=ffffff)

A working software version of the Multifamily Portfolio Risk and Capital Allocation Engine.

[Live app](https://nathan-fergo-risk-analyst.onrender.com) | [Portfolio page](https://www.nathan-gomes.com/Project-Multifamily-Risk-Engine.dc.html) | [Live report](https://www.nathan-gomes.com/multifamily-risk-report.html)

The app turns sample multifamily portfolio data into an interactive analyst dashboard for:

- property-level risk scoring
- DSCR and LTV review
- downside scenario testing
- CMHC-aware financing analysis
- market and debt concentration review
- capital allocation recommendations

The current dataset is intentionally synthetic. It is scaled to a 3,000-unit portfolio with roughly $1B in valuation so the demo feels closer to a real multifamily operating portfolio without exposing private information.

## Business question

If a real estate operator owns thousands of units across multiple properties, which assets need attention first when occupancy, expenses, interest rates, cap rates, and capital budgets change?

The app answers that by combining property performance, debt structure, valuation assumptions, CMHC exposure, and scenario controls into one analyst workspace.

## What the app shows

- Base portfolio value, unit count, annual NOI, weighted DSCR, CMHC-insured debt share, and selected capital
- A DSCR versus LTV risk matrix
- A scenario-adjusted property watchlist
- Preset and custom downside scenarios
- Capital project recommendations that respect a chosen capital budget
- Market concentration and financing-type concentration
- Property-level detail for financing type, interest rate, maturity, amortization, revenue, NOI, DSCR, and LTV

## Scenario model

The dashboard updates when the analyst changes:

- Occupancy pressure
- Expense inflation
- Interest-rate shock
- Cap-rate expansion
- Available capital budget

Those controls flow through the risk matrix, selected capital plan, property watchlist, valuation metrics, debt service coverage, and financing concentration views.

## CMHC-aware debt analysis

CMHC financing is treated differently from conventional, bridge/private, and construction debt. The engine gives CMHC-insured loans lower financing risk, longer amortization assumptions, and less sensitivity to rate shocks than shorter-term or floating-rate debt.

That matters because a portfolio with a high CMHC-insured debt share can behave very differently from a portfolio relying heavily on bridge or construction financing.

## Technical shape

- FastAPI backend
- Python, pandas, NumPy, and SQLite-style data modeling
- Deterministic sample data generation
- CMHC, conventional, bridge/private, and construction loan assumptions
- Docker and Render deployment files
- pytest coverage for dashboard structure, stress scenarios, capital budget logic, and CMHC reporting

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8010
```

Open:

```text
http://127.0.0.1:8010
```

## Test

```bash
python3 -m pytest -q
```

## Deploy

The included Dockerfile and `render.yaml` make the app ready for Render as a free web service named `nathan-fergo-risk-analyst`.

Live Render URL:

```text
https://nathan-fergo-risk-analyst.onrender.com
```

This demo uses generated sample data only. It does not connect to real bank accounts, accounting systems, or client data.

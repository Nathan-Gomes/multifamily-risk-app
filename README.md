# Multifamily Portfolio Risk Workspace

A working software version of the Multifamily Portfolio Risk & Capital Allocation Engine.

The app turns sample multifamily portfolio data into an interactive analyst dashboard for:

- property-level risk scoring
- DSCR and LTV review
- downside scenario testing
- CMHC-aware financing analysis
- market and debt concentration review
- capital allocation recommendations

The current dataset is intentionally synthetic. It is scaled to a 3,000-unit portfolio with roughly $1B in valuation so the demo feels closer to a real multifamily operating portfolio without exposing private information.

## What The App Shows

- Base portfolio value, unit count, annual NOI, weighted DSCR, CMHC-insured debt share, and selected capital
- A DSCR versus LTV risk matrix
- A scenario-adjusted property watchlist
- Preset and custom downside scenarios
- Capital project recommendations that respect a chosen capital budget
- Market concentration and financing-type concentration
- Property-level detail for financing type, interest rate, maturity, amortization, revenue, NOI, DSCR, and LTV

## Technical Shape

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

The included Dockerfile and `render.yaml` make the app ready for Render as a web service.

This demo uses generated sample data only. It does not connect to real bank accounts, accounting systems, or client data.

"""Reproducible base-case CSV package for MATLAB, SQL review and Tableau."""
from pathlib import Path
import sys
import sqlite3
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from engine.risk_engine import run_pipeline, monthly_debt_service, CONFIG, prioritize_capital
from engine.investment import credit_and_valuation


def export():
    folder = ROOT / 'research_output'
    result = run_pipeline(folder / 'pipeline')
    metrics = credit_and_valuation(result['scored'], monthly_debt_service)
    metrics.to_csv(folder / 'metrics.csv', index=False)
    with sqlite3.connect(folder / 'pipeline' / 'multifamily_portfolio.db') as connection:
        mart = pd.read_sql_query((ROOT / 'sql' / 'operating_review.sql').read_text(), connection)
    mart.to_csv(folder / 'operating_review.csv', index=False)
    for name, frame in result['data'].items():
        frame.to_csv(folder / f'{name}.csv', index=False)
    projects = result['data']['capital_projects'].merge(metrics[['property_id', 'risk_score']], on='property_id', validate='many_to_one')
    projects['priority_score'] = projects.expected_noi_lift / projects.capital_required * 100 + projects.risk_reduction_points * 2 + projects.risk_score * .25
    projects.to_csv(folder / 'optimization_inputs.csv', index=False)
    selected = prioritize_capital(metrics, result['data']['capital_projects'], CONFIG['capital_budget'])
    pd.DataFrame([{'budget': CONFIG['capital_budget'], 'objective': selected.priority_score.sum()}]).to_csv(folder / 'optimization_reference.csv', index=False)
    print(f'Research data exported to {folder}')


if __name__ == '__main__':
    export()

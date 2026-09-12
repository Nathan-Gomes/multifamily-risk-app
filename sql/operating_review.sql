-- SQLite: reconciled monthly operating mart with explicit time windows.
WITH rolling AS (
  SELECT property_id, month, revenue, operating_expenses, noi,
         SUM(noi) OVER (PARTITION BY property_id ORDER BY month
           ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS trailing_noi,
         COUNT(*) OVER (PARTITION BY property_id ORDER BY month
           ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS window_months,
         LAG(noi, 12) OVER (PARTITION BY property_id ORDER BY month) AS prior_noi
  FROM monthly_financials
), ranked AS (
  SELECT r.*, p.market, p.units,
         (noi - prior_noi) / NULLIF(prior_noi, 0) AS noi_yoy,
         noi / NULLIF(units, 0) AS noi_per_unit,
         DENSE_RANK() OVER (PARTITION BY month, market ORDER BY noi / units DESC) AS market_rank
  FROM rolling r JOIN properties p USING (property_id)
)
SELECT * FROM ranked WHERE window_months = 12 ORDER BY month, market, market_rank;

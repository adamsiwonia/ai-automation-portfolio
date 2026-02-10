-- Executive KPI – Order Revenue

SELECT
  COUNT(*) AS total_orders,
  SUM(revenue) AS total_revenue,
  ROUND(AVG(revenue), 2) AS avg_order_value
FROM public.v_order_revenue;

-- KPI: revenue trend range
SELECT
  MIN(day) AS min_day,
  MAX(day) AS max_day,
  COUNT(*) AS days,
  SUM(revenue) AS total_revenue,
  AVG(revenue) AS avg_daily_revenue
FROM v_daily_revenue;

-- KPI: top 10 revenue days
SELECT
  day,
  revenue,
  orders,
  aov
FROM v_daily_revenue
ORDER BY revenue DESC
LIMIT 10;

-- KPI: AOV distribution (P50/P90)
SELECT
  percentile_cont(0.50) WITHIN GROUP (ORDER BY aov) AS p50_aov,
  percentile_cont(0.90) WITHIN GROUP (ORDER BY aov) AS p90_aov
FROM v_daily_revenue
WHERE orders > 0;
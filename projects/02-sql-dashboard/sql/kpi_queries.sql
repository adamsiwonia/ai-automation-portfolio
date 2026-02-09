-- Executive KPI – Order Revenue

SELECT
  COUNT(*) AS total_orders,
  SUM(revenue) AS total_revenue,
  ROUND(AVG(revenue), 2) AS avg_order_value
FROM public.v_order_revenue;
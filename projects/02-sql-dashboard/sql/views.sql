-- ============================================================
-- Analytical Views
-- ============================================================

CREATE OR REPLACE VIEW public.v_order_revenue AS
SELECT
    o.order_id,
    o.order_purchase_timestamp::date AS order_date,
    SUM(oi.price + oi.freight_value) AS revenue,
    COUNT(*) AS items_count
FROM public.olist_orders o
JOIN public.olist_order_items oi
    ON oi.order_id = o.order_id
GROUP BY
    o.order_id,
    o.order_purchase_timestamp::date;

CREATE OR REPLACE VIEW v_daily_revenue AS
SELECT
  o.order_purchase_timestamp::date AS day,
  SUM(p.payment_value)            AS revenue,
  COUNT(DISTINCT o.order_id)      AS orders,
  CASE
    WHEN COUNT(DISTINCT o.order_id) = 0 THEN 0
    ELSE SUM(p.payment_value) / COUNT(DISTINCT o.order_id)
  END                             AS aov
FROM olist_orders o
JOIN olist_order_payments p
  ON p.order_id = o.order_id
GROUP BY 1
ORDER BY 1;
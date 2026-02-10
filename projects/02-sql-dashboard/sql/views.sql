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
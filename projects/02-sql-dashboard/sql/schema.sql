-- ============================================================
-- Olist (core) - schema.sql
-- Tables covered (based on your CSV headers):
--   - olist_customers
--   - olist_orders
--   - olist_order_items
-- ============================================================

-- Optional: drop in safe order (uncomment if you want reset)
-- DROP TABLE IF EXISTS olist_order_items;
-- DROP TABLE IF EXISTS olist_orders;
-- DROP TABLE IF EXISTS olist_customers;

-- =========================
-- Customers
-- =========================
CREATE TABLE IF NOT EXISTS olist_customers (
  customer_id              TEXT PRIMARY KEY,
  customer_unique_id       TEXT NOT NULL,
  customer_zip_code_prefix INTEGER,
  customer_city            TEXT,
  customer_state           TEXT
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_customers_unique_id
  ON olist_customers (customer_unique_id);

CREATE INDEX IF NOT EXISTS idx_customers_zip_prefix
  ON olist_customers (customer_zip_code_prefix);

CREATE INDEX IF NOT EXISTS idx_customers_state
  ON olist_customers (customer_state);

-- =========================
-- Orders
-- =========================
CREATE TABLE IF NOT EXISTS olist_orders (
  order_id                       TEXT PRIMARY KEY,
  customer_id                    TEXT NOT NULL,

  order_status                   TEXT,
  order_purchase_timestamp       TIMESTAMP,
  order_approved_at              TIMESTAMP,
  order_delivered_carrier_date   TIMESTAMP,
  order_delivered_customer_date  TIMESTAMP,
  order_estimated_delivery_date  TIMESTAMP,

  CONSTRAINT fk_orders_customer
    FOREIGN KEY (customer_id) REFERENCES olist_customers(customer_id)
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_orders_customer_id
  ON olist_orders (customer_id);

CREATE INDEX IF NOT EXISTS idx_orders_purchase_ts
  ON olist_orders (order_purchase_timestamp);

CREATE INDEX IF NOT EXISTS idx_orders_status
  ON olist_orders (order_status);

-- =========================
-- Order items
-- =========================
CREATE TABLE IF NOT EXISTS olist_order_items (
  order_id            TEXT NOT NULL,
  order_item_id       INTEGER NOT NULL,

  product_id          TEXT NOT NULL,
  seller_id           TEXT NOT NULL,

  shipping_limit_date TIMESTAMP,

  price               NUMERIC(10,2),
  freight_value       NUMERIC(10,2),

  PRIMARY KEY (order_id, order_item_id),

  CONSTRAINT fk_items_order
    FOREIGN KEY (order_id) REFERENCES olist_orders(order_id)
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_order_items_product_id
  ON olist_order_items (product_id);

CREATE INDEX IF NOT EXISTS idx_order_items_seller_id
  ON olist_order_items (seller_id);

CREATE INDEX IF NOT EXISTS idx_order_items_shipping_limit_date
  ON olist_order_items (shipping_limit_date);
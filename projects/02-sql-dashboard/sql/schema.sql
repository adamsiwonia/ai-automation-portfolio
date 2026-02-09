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
-- =========================
-- Product category name translation
-- =========================
CREATE TABLE IF NOT EXISTS product_category_name_translation (
  product_category_name          TEXT PRIMARY KEY,
  product_category_name_english  TEXT
);

CREATE INDEX IF NOT EXISTS idx_category_translation_english
  ON product_category_name_translation (product_category_name_english);

-- =========================
-- Products
-- =========================
CREATE TABLE IF NOT EXISTS olist_products (
  product_id                  TEXT PRIMARY KEY,
  product_category_name       TEXT,

  -- Note: column name in CSV is "product_name_lenght" (typo kept)
  product_name_lenght         INTEGER,
  product_description_lenght  INTEGER,
  product_photos_qty          INTEGER,

  product_weight_g            INTEGER,
  product_length_cm           INTEGER,
  product_height_cm           INTEGER,
  product_width_cm            INTEGER,

  CONSTRAINT fk_products_category
    FOREIGN KEY (product_category_name)
    REFERENCES product_category_name_translation(product_category_name)
);

CREATE INDEX IF NOT EXISTS idx_products_category
  ON olist_products (product_category_name);

-- =========================
-- Sellers
-- =========================
CREATE TABLE IF NOT EXISTS olist_sellers (
  seller_id              TEXT PRIMARY KEY,
  seller_zip_code_prefix INTEGER,
  seller_city            TEXT,
  seller_state           TEXT
);

CREATE INDEX IF NOT EXISTS idx_sellers_zip_prefix
  ON olist_sellers (seller_zip_code_prefix);

CREATE INDEX IF NOT EXISTS idx_sellers_state
  ON olist_sellers (seller_state);

-- =========================
-- Payments
-- =========================
CREATE TABLE IF NOT EXISTS olist_order_payments (
  order_id              TEXT NOT NULL,
  payment_sequential    INTEGER NOT NULL,

  payment_type          TEXT,
  payment_installments  INTEGER,
  payment_value         NUMERIC(10,2),

  PRIMARY KEY (order_id, payment_sequential),

  CONSTRAINT fk_payments_order
    FOREIGN KEY (order_id) REFERENCES olist_orders(order_id)
);

CREATE INDEX IF NOT EXISTS idx_payments_order_id
  ON olist_order_payments (order_id);

CREATE INDEX IF NOT EXISTS idx_payments_type
  ON olist_order_payments (payment_type);

-- =========================
-- Reviews
-- =========================
CREATE TABLE IF NOT EXISTS olist_order_reviews (
  review_id               TEXT PRIMARY KEY,
  order_id                TEXT NOT NULL,

  review_score            INTEGER,
  review_comment_title    TEXT,
  review_comment_message  TEXT,

  review_creation_date    TIMESTAMP,
  review_answer_timestamp TIMESTAMP,

  CONSTRAINT fk_reviews_order
    FOREIGN KEY (order_id) REFERENCES olist_orders(order_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_order_id
  ON olist_order_reviews (order_id);

CREATE INDEX IF NOT EXISTS idx_reviews_score
  ON olist_order_reviews (review_score);

-- =========================
-- =========================
-- Add missing FKs for order_items (products + sellers) - Postgres-safe reruns
-- =========================
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_items_product'
  ) THEN
    ALTER TABLE olist_order_items
      ADD CONSTRAINT fk_items_product
      FOREIGN KEY (product_id) REFERENCES olist_products(product_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_items_seller'
  ) THEN
    ALTER TABLE olist_order_items
      ADD CONSTRAINT fk_items_seller
      FOREIGN KEY (seller_id) REFERENCES olist_sellers(seller_id);
  END IF;
END $$;
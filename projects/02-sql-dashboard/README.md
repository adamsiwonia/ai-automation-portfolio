## Overview

This project is a **SQL-based analytical backend** built on the Brazilian E-Commerce Public Dataset by Olist.

The goal is to transform raw transactional data into an **analytics-ready PostgreSQL database** and to build a **semantic layer (SQL views)** that supports executive-level business KPIs such as revenue trends, order volume, and average order value (AOV).

The project reflects **real-world data work**, including:
- importing large CSV datasets into PostgreSQL
- handling foreign keys and data integrity
- resolving encoding issues on Windows
- dealing with duplicate primary keys in production data
- building reusable SQL views for analytics and BI dashboards

---

## Business Questions Answered

- How does revenue evolve over time (daily and monthly)?
- What are the highest revenue days?
- What is the average order value (AOV) and how is it distributed?
- What time range does the dataset cover?

---

## Dataset

This project uses the **Brazilian E-Commerce Public Dataset by Olist**.

Source:  
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Raw CSV files are excluded from version control (`.gitignore`).

---

## Data Model

The database schema is defined in: `sql/schema.sql`

It includes the following core tables:
- customers
- orders
- order_items
- payments
- products
- sellers
- reviews
- product category name translation

Primary keys, foreign keys, and indexes are used to ensure data integrity and query performance.

---

## Key SQL Views

All analytical views are defined in: `sql/views.sql`

### `v_order_revenue`
Aggregates data at the **order level**:
- order date
- total revenue per order (item price + freight value)
- number of items per order

Serves as a foundation for KPI calculations.

### `v_daily_revenue`
Daily aggregation providing:
- total revenue
- number of orders
- average order value (AOV)

### `v_monthly_revenue`
Monthly revenue trend:
- revenue
- order count
- AOV

---

## KPI Queries

Executive KPI queries are defined in: `sql/kpi_queries.sql`, including:
- revenue trend range (min/max date, total days)
- top 10 revenue days
- AOV distribution (P50 / P90)

---

## Dashboard Usage

This project is designed as a **backend for BI dashboards**.

The SQL views can be directly connected to tools such as:
- Power BI
- Tableau
- Metabase

No dashboard is included at this stage.

---

## How to Run

1. Create a PostgreSQL database (e.g. `olist_db`)
2. Execute `sql/schema.sql` to create tables and indexes
3. Import CSV files into the database
4. Execute `sql/views.sql` to create analytical views
5. Run queries from `sql/kpi_queries.sql` to calculate KPIs

The database is then ready for analysis or dashboard integration.
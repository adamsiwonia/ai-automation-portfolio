## Overview

This project is a **SQL-based analytical backend** built on the Brazilian E-Commerce Public Dataset by Olist.

The goal of the project is to transform raw CSV files into a **clean, analytics-ready PostgreSQL database**, and to build a **semantic layer (SQL views)** that supports business KPIs such as revenue, number of orders, and average order value (AOV).

The project focuses on **real-world data work**, including:
- importing large CSV datasets into PostgreSQL
- handling foreign keys and data integrity
- resolving encoding issues on Windows
- dealing with duplicate primary keys in production data
- building reusable SQL views for analytics and dashboards

---

## Dataset

This project uses the **Brazilian E-Commerce Public Dataset by Olist**.

### Download instructions
1. Go to Kaggle:  
   https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
2. Download the dataset (ZIP).
3. Extract all CSV files into the directory: projects/02-sql-dashboard/data_olist/

> Raw CSV files are excluded from version control (`.gitignore`).

---

## Data Model

The database schema is defined in: sql/schema.sql

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

## Key SQL Queries

### Analytical View: `v_order_revenue`

The core analytical view created in this project is: v_order_revenue

This view aggregates data at the **order level** and provides:
- order date
- total revenue per order (item price + freight value)
- number of items per order

The view serves as the foundation for all KPI calculations.

The SQL definition is stored in: sql/views.sql

---

## Dashboard

This project is designed as a **backend for BI dashboards**.

The analytical views can be directly connected to tools such as:
- Power BI
- Tableau
- Metabase

No dashboard is included at this stage.

---

## Insights

Example business KPIs calculated using SQL:
- total number of orders
- total revenue
- average order value (AOV)

KPI queries are defined in: sql/kpi_queries.sql

---

## How to run

1. Create a PostgreSQL database (e.g. `olist_db`).
2. Execute `sql/schema.sql` to create tables and indexes.
3. Import CSV files into the database using `psql \copy`.
4. Execute `sql/views.sql` to create analytical views.
5. Run queries from `sql/kpi_queries.sql` to calculate KPIs.

The database is then ready for analysis or dashboard integration.
# Database

Models cover users, hosting plans, domains, orders and order items, payments, subscriptions, support tickets and messages, contact messages, invoices, activity logs, and password reset tokens. UUID strings identify records; ownership columns are indexed and foreign keys define deletion behavior. No payment card data is stored.

Set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL such as `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require`. Run `alembic upgrade head` from `backend`. Application startup seeds sample plans when the catalog is empty.

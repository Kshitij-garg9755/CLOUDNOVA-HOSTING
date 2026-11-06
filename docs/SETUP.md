# Local setup

Requirements: Python 3.11+, Node 20+, and PostgreSQL 14+ (SQLite works for quick local development).

Backend: `cd backend`; create/activate a virtual environment; `pip install -r requirements.txt`; copy `.env.example` to `.env`; set `SECRET_KEY`, `DATABASE_URL`, and optional bootstrap admin variables; run `alembic upgrade head`; then `uvicorn app.main:app --reload`. API docs: `http://localhost:8000/docs`.

Frontend: `cd frontend`; `npm install`; copy `.env.example` to `.env`; set `VITE_API_URL=http://localhost:8000/api`; run `npm run dev` and open `http://localhost:5173`.

Admin bootstrap: set `BOOTSTRAP_ADMIN_EMAIL` and a long unique `BOOTSTRAP_ADMIN_PASSWORD` in the backend environment before startup. The account is created only server side. Remove bootstrap credentials after account creation and rotate the password.

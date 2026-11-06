# Local setup

Requirements: Python 3.11+, Node 20+, and PostgreSQL 14+ (SQLite works for quick local development).

Backend: `cd backend`; create/activate a virtual environment; `pip install -r requirements.txt`; copy `.env.example` to `.env`; set `SECRET_KEY`, `DATABASE_URL`, and optional bootstrap admin variables; run `alembic upgrade head`; then `uvicorn app.main:app --reload`. API docs: `http://localhost:8000/docs`.

Frontend: `cd frontend`; `npm install`; copy `.env.example` to `.env`; leave `VITE_API_BASE_URL=https://cloudnova-api-qnzr.onrender.com/api` to use the deployed API, or set it to `http://localhost:8000/api` to use a local backend; run `npm run dev` and open `http://localhost:5173`.

For local backend development, set `FRONTEND_ORIGINS=http://localhost:5173` in `backend/.env`. For production, set `FRONTEND_ORIGINS` in the Render service to a comma-separated list of exact frontend origins (for example, `http://localhost:5173,https://your-site.netlify.app`). Do not include paths or use `*` because credentialed CORS requires explicit origins.

Admin bootstrap: set `BOOTSTRAP_ADMIN_EMAIL` and a long unique `BOOTSTRAP_ADMIN_PASSWORD` in the backend environment before startup. The account is created only server side. Remove bootstrap credentials after account creation and rotate the password.

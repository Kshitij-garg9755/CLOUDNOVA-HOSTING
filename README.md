# CloudNova Hosting

Responsive hosting storefront and management portal built with React, TypeScript, FastAPI, SQLAlchemy, and PostgreSQL.

## Quick start

1. Configure backend variables from `backend/.env.example`; set `DATABASE_URL` to PostgreSQL (SQLite is supported for local development).
2. In `backend`, create a virtual environment, install `requirements.txt`, then run `uvicorn app.main:app --reload`.
3. In `frontend`, run `npm install`, copy `.env.example` to `.env`, and run `npm run dev`.
4. Visit `/docs` on the API for interactive documentation. The app initializes tables and sample plans at startup.

Admin bootstrap: set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` before first backend startup. The account is created as admin only if it does not already exist. Keep credentials secret and rotate after setup.

DEMO boundaries: domain availability uses deterministic mock results, hosting provisioning is simulated, and payment can create a demo payment intent when Razorpay is not configured. None represents a completed real-world service or charge. Configure Razorpay test keys and a registrar/hosting adapter before accepting real orders.

See `docs/` for setup, API, database, and deployment details.

## GitHub deployment control plane

The customer dashboard includes GitHub App installation and project import. Configure the App using `docs/GITHUB_APP.md`. The platform records authorized projects, detected build suggestions, signed push events, environment secrets (encrypted), and deployment history. Customer build execution, artifact publication, project routing, rollback, and SSL are intentionally blocked until the isolated gVisor worker and VPS routing infrastructure described in `docs/VPS_PLATFORM.md` are deployed. There is no fake live deployment mode.

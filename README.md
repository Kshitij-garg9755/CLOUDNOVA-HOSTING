# CloudNova Hosting

Responsive hosting storefront and management portal built with React, TypeScript, FastAPI, SQLAlchemy, and PostgreSQL.

## Quick start

1. Configure backend variables from `backend/.env.example`; set `DATABASE_URL` to PostgreSQL (SQLite is supported for local development).
2. In `backend`, create a virtual environment, install `requirements.txt`, then run `uvicorn app.main:app --reload`.
3. In `frontend`, run `npm install`, copy `.env.example` to `.env`, and run `npm run dev`.
4. Visit `/docs` on the API for interactive documentation. The app initializes tables and sample plans at startup.

Admin bootstrap: set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` before first backend startup. The account is created as admin only if it does not already exist. Keep credentials secret and rotate after setup.

DEMO boundaries: domain availability uses deterministic mock results and hosting provisioning is simulated. The plan checkout can use the separately configured UPI Gateway; generic UPI payments require merchant UTR approval. A confirmed payment is real money, but does not provision hosting until a hosting provider is connected. Do not accept customer payments until the amount, merchant account, return URL, and manual verification workflow are configured and reviewed.

## UPI gateway checkout

Plan buttons create an authenticated CloudNova order, then ask the configured UPI Gateway to create its hosted payment link. Gateway API credentials stay in the FastAPI environment. Configure the local values in `backend/.env`, using the API key and API secret from the gateway merchant's Settings page; set its webhook endpoint to `http://127.0.0.1:8000/api/payments/upi/webhook`. The local gateway URL is `http://127.0.0.1:8081`, and the local return URL is `http://localhost:5173/payment/return`. Restart the API after editing `.env`.

The gateway in `upi-gateway/` currently runs locally. Netlify/Render cannot connect to a developer computer: production checkout requires deploying that Laravel app to a public HTTPS host, configuring its production `APP_URL`, and adding its HTTPS base URL plus merchant API credentials to the CloudNova Render service. Then point the gateway merchant webhook to `https://cloudnova-api-qnzr.onrender.com/api/payments/upi/webhook` and the return URL to `https://cloudnova-hosting.netlify.app/payment/return`. Keep all API secrets on the FastAPI server, never in `VITE_*` variables. See `docs/DEPLOYMENT.md` for the full variable list.

See `docs/` for setup, API, database, and deployment details.

## GitHub deployment control plane

The customer dashboard includes GitHub App installation and project import. Configure the App using `docs/GITHUB_APP.md`. The platform records authorized projects, detected build suggestions, signed push events, environment secrets (encrypted), and deployment history. Customer build execution, artifact publication, project routing, rollback, and SSL are intentionally blocked until the isolated gVisor worker and VPS routing infrastructure described in `docs/VPS_PLATFORM.md` are deployed. There is no fake live deployment mode.

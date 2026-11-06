# Deployment

## Render FastAPI service

The FastAPI entrypoint is `app.main:app` (`backend/app/main.py`). The repository-root `render.yaml` uses `rootDir: backend`, matching the existing backend layout.

Blueprint settings:

- Runtime: Python 3.11.11
- Build command: `pip install -r requirements.txt && alembic upgrade head`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`; it runs `SELECT 1` and returns HTTP 503 if PostgreSQL is unavailable.
- Database: Render PostgreSQL or external PostgreSQL. Prefer the internal URL when both services are in the same Render region. `postgres://` and `postgresql://` are normalized to psycopg v3.

Create a Blueprint from the repository root, or manually use those exact settings. Configure these service environment variables in Render:

| Name | Value |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL; keep secret. |
| `SECRET_KEY` | Long random JWT signing key. The Blueprint generates one; retain it across deploys. |
| `FRONTEND_ORIGINS` | Exact frontend origin(s), comma-separated, e.g. `http://localhost:5173,https://your-site.netlify.app`; no path or trailing slash. Wildcards are rejected because credentials are enabled. |
| `ALLOWED_HOSTS` | API hostname, e.g. `cloudnova-api.onrender.com`; add custom API hostname if used. |
| `ENVIRONMENT` | `production`. |
| `BOOTSTRAP_ADMIN_EMAIL` | Optional initial admin email. |
| `BOOTSTRAP_ADMIN_PASSWORD` | Optional strong initial password; remove after initial admin creation. |
| `GITHUB_APP_ID` | GitHub App numeric ID. |
| `GITHUB_APP_SLUG` | GitHub App slug. |
| `GITHUB_CLIENT_ID` | Existing OAuth client ID (optional for current install flow). |
| `GITHUB_CLIENT_SECRET` | Existing OAuth client secret (optional for current install flow). |
| `GITHUB_PRIVATE_KEY` | GitHub App PEM private key. Multiline PEM and literal `\\n` are both supported. |
| `GITHUB_WEBHOOK_SECRET` | Exact GitHub App webhook signing secret. |
| `GITHUB_CALLBACK_URL` | `https://YOUR-API-HOST/api/github/callback`. |
| `PAYMENT_DEMO_MODE` | Keep `true` until Razorpay test configuration is verified. |
| `RAZORPAY_KEY_ID` | Optional Razorpay key ID. |
| `RAZORPAY_KEY_SECRET` | Optional secret. |
| `RAZORPAY_WEBHOOK_SECRET` | Optional webhook signing secret. |

Do not put secrets in `render.yaml`, source control, or frontend variables. GitHub uses the exact existing variable `GITHUB_PRIVATE_KEY`; backend normalization accepts CRLF, escaped `\\n`, and already multiline values without logging the key.

### Database migrations and startup

Render's build command runs Alembic before starting the API. Startup no longer uses `create_all`; migrations are the schema source of truth. Review and commit migrations before deploy. Local commands from `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
# Set DATABASE_URL, SECRET_KEY, and FRONTEND_ORIGINS in .env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The deployed service binds `0.0.0.0` and uses Render's injected `$PORT`. OpenAPI is at `/docs`; Render checks `/health`.

## Netlify frontend

Connect the repository with base directory `frontend`, build command `npm run build`, and publish directory `dist`. Set `VITE_API_BASE_URL=https://cloudnova-api-qnzr.onrender.com/api`. The frontend temporarily supports the former `VITE_API_URL` as a fallback for existing Netlify sites; migrate the Netlify variable to `VITE_API_BASE_URL`. Add the exact Netlify origin to Render's `FRONTEND_ORIGINS`, then redeploy the API. Rebuild Netlify after changing frontend variables. The live API was verified to allow `http://localhost:5173`; add the real production site origin when known.

## Production setup reminders

- Set GitHub App callback and webhook URLs to the deployed API host.
- Keep customer build execution disabled until isolated gVisor infrastructure is installed; Render API does not run customer builds.
- Verify Razorpay test signatures and webhooks before live keys.
- Domain lookup and simulated hosting adapters remain DEMO services.
- Configure managed database backups, service logs, and alerts.

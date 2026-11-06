# CloudNova deployment audit

Audit date: 2026-11-06

## Repository and workspace

- **COMPLETED** — Inspected the local frontend, backend, Render config, Alembic, GitHub API routes, models, tests, and Netlify files.
- **COMPLETED** — At audit start, the linked public repository `Kshitij-garg9755/CLOUDNOVA-HOSTING` was empty and this workspace was not a Git checkout. After the user authorized a push, initialized branch `main` and pushed commit `3dc5e1d` to `origin/main`.
- **COMPLETED** — Verified local `HEAD` and remote `refs/heads/main` both resolve to `3dc5e1d581a4b2346bd79961d7a18c7f1675d0af`; worktree was clean after push.
- **COMPLETED** — No Render, Netlify, or other production service was deployed or modified.

## Architecture inspected

- Frontend: React + Vite + TypeScript, centralized Axios client at `frontend/src/services/api.ts`, React Router dashboard, Netlify SPA fallback in `frontend/netlify.toml`.
- Backend: FastAPI entrypoint `backend/app/main.py`; routers `backend/app/api/routes.py` and `backend/app/api/deployments.py`; SQLAlchemy models in `backend/app/models/__init__.py`; PostgreSQL/SQLite engine in `backend/app/core/database.py`.
- Render: repository-root `render.yaml`, with `rootDir: backend`.
- Database: Alembic revisions `0001_initial` and `0002_github_installation_status`.
- Queue: Celery/Redis configuration exists, but the task deliberately fails closed because no isolated customer build executor exists.

## Status

- **COMPLETED** — Render command, Python version, `$PORT`, `0.0.0.0`, CORS, allowed hosts, psycopg URL normalization, DB health check, and Alembic-before-start configuration are prepared.
- **COMPLETED** — GitHub App install setup flow, signed expiring installation state, RS256 App JWT, short-lived installation tokens, repository/branch/details endpoints, webhook HMAC SHA-256, delivery deduplication, push event handling, installation and installation-repository event handling, and revocation without deleting project history are implemented.
- **COMPLETED** — Framework suggestions and project import use GitHub repository contents; App permissions needed by the current code are read-only Metadata and read-only Contents.
- **COMPLETED** — Frontend prefers `VITE_API_BASE_URL`; it temporarily falls back to the existing `VITE_API_URL` variable for a controlled Netlify migration.
- **REQUIRES MY ACTION** — Supply actual Render PostgreSQL/API settings, frontend URL, GitHub App identifiers/key/secret, and Netlify URL through the service dashboards. No credentials are present in source.
- **REQUIRES MY ACTION** — GitHub connection cannot complete until a GitHub App is created/configured and installed, and its Render secrets are set.
- **NOT IMPLEMENTED** — Production customer build execution, artifact storage, runtime hosting, live URL routing, health-gated atomic activation, and rollback. Deployment endpoints do not claim success; builds are rejected or marked failed without the isolated worker.
- **NOT IMPLEMENTED** — Automatic SSL issuance/renewal and Cloudflare changes for customer-owned domains. Domain ownership TXT verification alone does not activate a route or certificate.
- **NOT IMPLEMENTED** — Pull request preview deployments and OAuth user authorization. Current GitHub flow is App installation setup, not OAuth.
- **BLOCKED** — First real Render + GitHub App + Netlify deployment cannot be completed without user-owned service configuration and credentials. No live services were modified.

## GitHub App settings (actual registered routes)

- Homepage URL: the Netlify CloudNova frontend origin (not yet known; enter the real URL).
- Setup URL: `https://YOUR_RENDER_HOST/api/github/callback`; enable redirect after installation. This endpoint validates the signed `state`, verifies the installation with an App JWT, and records it.
- OAuth user authorization callback: not used; leave unset and do not enable a separate OAuth user flow.
- Webhook URL: `https://YOUR_RENDER_HOST/api/webhooks/github`.
- Repository permissions: Metadata **Read-only**, Contents **Read-only**.
- Subscribe to: `Push`, `Installation`, and `Installation repositories`.
- Webhook secret: generate in GitHub and set the same value as `GITHUB_WEBHOOK_SECRET` in Render.
- App ID/slug/private key: set as `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, and `GITHUB_PRIVATE_KEY` in Render. Keys are never sent to the browser or returned by API routes.

No real hostnames or credentials are inferred in this report.

## Environment variables found in code

Backend settings are read by `backend/app/core/config.py`; put production values in Render, not source control:

- Core: `DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_MINUTES`, `FRONTEND_ORIGINS`, `ALLOWED_HOSTS`, `ENVIRONMENT`.
- Initial admin bootstrap: `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` (remove bootstrap values after account creation).
- GitHub: `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_CALLBACK_URL`. Client ID/secret are currently optional and unused by the App-installation flow.
- Queue/deployment: `REDIS_URL`, `DEPLOYMENT_WORKER_ENABLED`, `DEPLOYMENT_ISOLATION_RUNTIME`, `PUBLIC_BASE_DOMAIN`. Worker flags must remain disabled until a real isolated executor is deployed.
- Payments: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `PAYMENT_DEMO_MODE`.
- Frontend: preferred `VITE_API_BASE_URL`; legacy fallback `VITE_API_URL`; development default is `http://localhost:8000/api`.

GitHub PEM loading accepts literal newlines, CRLF, or escaped `\\n` and normalizes them before signing. No keys should be copied into this file.

## Verification results

- Backend suite: **16 passed**, 2 third-party deprecation warnings.
- Frontend `npm run build`: **passed**, TypeScript and Vite production build.
- Alembic: **passed**, head is `0002_github_installation_status`.
- API health: **passed** locally; reports database `ok` after `SELECT 1`.
- API plans and OpenAPI: **HTTP 200** locally.
- CORS: local configured origin reflected as expected.
- GitHub App JWT: tested with a generated test key; repository listing/branches exercised with a mocked GitHub API; webhook signature/dedup and uninstall handling tested. No real GitHub credentials were available for a live integration test.
- Render/Netlify deployment: not run. Docker/VPS worker, Cloudflare DNS, S3 storage, GitHub App, Render service, and Netlify site credentials are not available here.

# API notes

FastAPI OpenAPI docs: `/docs`. Auth uses bearer JWTs with expiry configured by `ACCESS_TOKEN_MINUTES`. Login accepts OAuth2 form fields `username` (email) and `password`.

Public routes: `/api/auth/register`, `/api/auth/login`, `/api/auth/forgot-password`, `/api/auth/reset-password`, `/api/plans`, `/api/domains/search`, `/api/contact`.

Customer routes require authentication and scope queries to the signed-in user: `/api/orders`, `/api/domains`, `/api/dashboard/*`, `/api/support/tickets`, `/api/payments/*`.

Admin routes require backend role `admin`: `/api/admin/*`. Collections accept `limit` and `offset`; applicable lists support search/status filters. Unauthorized and missing owned resources return 401/403/404.

Domain availability returns `mode: DEMO`; provisioning is simulated. Razorpay verification checks HMAC signatures; webhook requires `X-Razorpay-Signature`. Demo verification accepts only `demo_signature` and is not a real transaction.

## GitHub deployment control plane

`GET /api/github/connect` returns the GitHub App installation URL. After installation, authorized repositories and branches are listed from GitHub using short-lived backend installation tokens. `POST /api/projects` imports a repository and detects a framework from repository files. Project settings are editable via `PUT /api/projects/{id}`. GitHub push webhook events require `X-Hub-Signature-256` and unique `X-GitHub-Delivery` IDs. Environment variable values are encrypted at rest and never returned by list APIs.

Deployment history, log, and cancellation endpoints are present. A deployment request returns 503 until the dedicated gVisor worker/queue is configured. Runtime controls, rollback, live routing, artifact serving, and SSL activation return unavailable until their real provider is installed. Domain verification requires a published TXT record and does not activate DNS or SSL.

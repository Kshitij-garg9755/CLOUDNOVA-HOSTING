# API notes

FastAPI OpenAPI docs: `/docs`. Auth uses bearer JWTs with expiry configured by `ACCESS_TOKEN_MINUTES`. Login accepts OAuth2 form fields `username` (email) and `password`.

Public routes: `/api/auth/register`, `/api/auth/login`, `/api/auth/forgot-password`, `/api/auth/reset-password`, `/api/plans`, `/api/domains/search`, `/api/contact`.

Customer routes require authentication and scope queries to the signed-in user: `/api/orders`, `/api/domains`, `/api/dashboard/*`, `/api/support/tickets`, `/api/payments/*`.

The plan checkout flow uses `POST /api/payments/upi/create` with `{ "plan_id": "...", "checkout_id": "<UUID>" }` and bearer authentication. It returns a server-created UPI gateway checkout URL; the browser is redirected there and returns to `/payment/return`. `GET /api/payments/upi/{order_id}/status` checks the signed-in user's gateway order with the gateway before recording a payment. `POST /api/payments/upi/webhook` accepts only HMAC-SHA256 signed UPI Gateway events (`X-Signature`) and validates order owner reference, amount, and currency before recording payment. Keep all UPI gateway credentials on the FastAPI server.

Admin routes require backend role `admin`: `/api/admin/*`. Collections accept `limit` and `offset`; applicable lists support search/status filters. Unauthorized and missing owned resources return 401/403/404.

Domain availability returns `mode: DEMO`; hosting provisioning is simulated. The UPI Gateway's generic UPI provider requires a merchant to manually approve the customer UTR before CloudNova records payment. A confirmed payment does not provision hosting yet; a real hosting provider is not connected. Razorpay verification checks HMAC signatures; webhook requires `X-Razorpay-Signature`. Demo verification accepts only `demo_signature` and is not a real transaction.

## GitHub import and deployment control plane

`GET /api/github/connect` returns the GitHub App installation URL. After installation, `GET /api/github/repositories` fetches all authorized repositories from GitHub with short-lived backend installation tokens and returns owner, name, description, visibility, default branch, GitHub ID, and CloudNova's internal ID. `GET /api/github/repositories/{id}/branches` lists branches; `GET /api/github/repositories/{id}/detect` suggests project settings from the selected branch/root. `POST /api/projects` stores the selected repository and editable build settings. Project settings are editable via `PUT /api/projects/{id}`.

Per-project environment variable values are encrypted at rest, omitted from API responses, and managed at `/api/projects/{id}/environment`; only names and set status are returned. GitHub push webhook events require `X-Hub-Signature-256` and unique `X-GitHub-Delivery` IDs.

Deployment history, log, and cancellation endpoints are present. A deployment request remains unavailable until a dedicated isolated build executor is implemented and installed. The current Celery task deliberately fails closed and does not run repository code. Build execution, artifact storage, live routing, rollback, and SSL activation are not operational. Domain verification requires a published TXT record and does not activate DNS or SSL.

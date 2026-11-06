# VPS platform deployment

## Current deployment boundary

The app implements GitHub App authorization, paginated repository/branch listing, repository search and refresh in the dashboard, framework suggestions and editable project settings, signed/deduplicated push webhook handling, deployment history, encrypted project environment variables, and DNS TXT ownership verification. It is still a control plane, not a production customer build platform. It does not execute source, publish artifacts, activate project URLs, or issue SSL certificates. The Celery task fails closed until a separate isolated executor is implemented and installed; the API never claims a site is live.

## Control-plane MVP

1. Provision a clean Linux VPS with a supported Docker Engine and Compose plugin; use a separate host or VM pool for customer build workers.
2. Copy `.env.example` to `.env`; generate independent high-entropy database, Redis, and JWT secrets. Configure GitHub App values and exact frontend origins.
3. Set `CF_DNS_API_TOKEN` to a Cloudflare API token scoped to the intended zone with DNS edit permission, and set `ACME_EMAIL`. This token is used by Traefik for ACME DNS challenges; the current API does not modify customer DNS records.
4. Deploy the frontend to Netlify and point `VITE_API_BASE_URL` at the HTTPS control plane. Keep API ports private behind your edge proxy/firewall.
5. `docker compose up -d --build`; check `/health`, API logs, PostgreSQL/Redis health, and Traefik logs. Back up PostgreSQL and the Traefik ACME volume.

Traefik is configured to read dynamic route definitions from `infra/traefik/dynamic`, but the repository has no route writer or artifact origin yet, so no customer site is routed. Do not enable `DEPLOYMENT_WORKER_ENABLED`: the queued task currently records a fail-closed result, not a build. The flag is not sufficient to install or secure a worker.

## Required before customer builds

- A separate worker pool using gVisor `runsc` or stronger VM isolation, non-root identities, seccomp/AppArmor, CPU/memory/PID/disk/time limits, egress controls, and blocked metadata/private-network access.
- BuildKit daemon isolated from the API and customer network. Do not mount a host Docker socket into the API or ordinary Celery worker. Verify the BuildKit worker runtime is actually gVisor-backed; setting an environment flag alone is not sufficient.
- Private S3-compatible artifact storage with short-lived serving URLs or a controlled origin, checksum verification, immutable releases, and atomic route activation.
- A routing controller that writes validated Traefik file-provider routes only after successful artifact and health checks; rollback switches to a known successful release.
- ACME staging tests followed by production Let's Encrypt, persisted protected ACME data, renewal alarms, and verified domain ownership before requesting certificates.
- Independent worker registration/heartbeat, resource accounting, structured build logs, cancellation, and audit events.

The current Render Blueprint deploys only the FastAPI web service. It does not provision the isolated Linux build worker, BuildKit/gVisor runtime, artifact bucket, wildcard DNS, or static-site routing service. There are no S3/artifact configuration variables in the application yet; do not add storage credentials or enable builds until that integration is implemented.

Existing deployment-related settings are `REDIS_URL` (Celery broker), `DEPLOYMENT_WORKER_ENABLED`, `DEPLOYMENT_ISOLATION_RUNTIME`, and `PUBLIC_BASE_DOMAIN`. Keep the worker flag disabled and do not set the runtime to `runsc` as a substitute for installing an executor. VPS edge setup also uses `CF_DNS_API_TOKEN` and `ACME_EMAIL` in Compose. The API currently has no object-storage endpoint, bucket, access-key, or route-controller settings; these must be designed and implemented with the selected storage and hosting services before those credentials can be configured.

Cloudflare serves DNS or ACME only when explicitly scoped; users must publish the provided challenge/CNAME records themselves until a verified DNS authorization flow exists. The TXT ownership-check module does not activate routing or SSL.

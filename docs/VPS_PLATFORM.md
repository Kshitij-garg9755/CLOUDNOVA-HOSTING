# VPS platform deployment

## Current deployment boundary

The app now implements GitHub App authorization, repository/branch listing, framework suggestions, project configuration records, signed/deduplicated push webhook handling, deployment history, encrypted project environment variables, and DNS TXT ownership verification. It is a control plane, not yet a production customer build platform. It intentionally does not execute source, publish artifacts, activate project URLs, or issue SSL certificates. The Celery queue worker marks jobs failed unless a separate executor is built and installed; the API never claims a site is live.

## Control-plane MVP

1. Provision a clean Linux VPS with a supported Docker Engine and Compose plugin; use a separate host or VM pool for customer build workers.
2. Copy `.env.example` to `.env`; generate independent high-entropy database, Redis, and JWT secrets. Configure GitHub App values and exact frontend origins.
3. Set `CF_DNS_API_TOKEN` to a Cloudflare API token scoped to the intended zone with DNS edit permission, and set `ACME_EMAIL`. This token is used by Traefik for ACME DNS challenges; the current API does not modify customer DNS records.
4. Deploy the frontend to Netlify and point `VITE_API_URL` at the HTTPS control plane. Keep API ports private behind your edge proxy/firewall.
5. `docker compose up -d --build`; check `/health`, API logs, PostgreSQL/Redis health, and Traefik logs. Back up PostgreSQL and the Traefik ACME volume.

Traefik reads dynamic route definitions from `infra/traefik/dynamic`. No project route writer or artifact origin exists yet, so empty configuration means no customer site is routed. Do not enable `DEPLOYMENT_WORKER_ENABLED` until the isolated executor and artifact storage have been installed and audited.

## Required before customer builds

- A separate worker pool using gVisor `runsc` or stronger VM isolation, non-root identities, seccomp/AppArmor, CPU/memory/PID/disk/time limits, egress controls, and blocked metadata/private-network access.
- BuildKit daemon isolated from the API and customer network. Do not mount a host Docker socket into the API or ordinary Celery worker. Verify the BuildKit worker runtime is actually gVisor-backed; setting an environment flag alone is not sufficient.
- Private S3-compatible artifact storage with short-lived serving URLs or a controlled origin, checksum verification, immutable releases, and atomic route activation.
- A routing controller that writes validated Traefik file-provider routes only after successful artifact and health checks; rollback switches to a known successful release.
- ACME staging tests followed by production Let's Encrypt, persisted protected ACME data, renewal alarms, and verified domain ownership before requesting certificates.
- Independent worker registration/heartbeat, resource accounting, structured build logs, cancellation, and audit events.

Cloudflare serves DNS or ACME only when explicitly scoped; users must publish the provided challenge/CNAME records themselves until a verified DNS authorization flow exists. The TXT ownership-check module does not activate routing or SSL.

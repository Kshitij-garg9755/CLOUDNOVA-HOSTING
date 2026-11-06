# GitHub App setup

Create a GitHub App in GitHub settings:

- Homepage URL: your deployed CloudNova frontend URL.
- Setup URL: `https://YOUR_API_HOST/api/github/callback`; enable redirect after installation so GitHub supplies `installation_id`, `setup_action`, and the signed `state`.
- OAuth user authorization callback URL: not used by this implementation; leave blank and do not enable a separate OAuth user authorization flow.
- Webhook URL: `https://YOUR_API_HOST/api/webhooks/github`.
- Subscribe to `Push`, `Installation`, and `Installation repositories` events. Pull request preview deployments are not implemented.
- Repository permissions: **Contents: Read-only**, **Metadata: Read-only**. Do not grant write access for the current import workflow.
- Generate a webhook secret and private key. Keep both server side.

Set `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_PRIVATE_KEY` (PEM, newline escaped if needed), `GITHUB_WEBHOOK_SECRET`, and `GITHUB_CALLBACK_URL` in the API environment. The client ID and secret are retained as optional configuration but are not used in this installation-based flow. A user must install the app on selected repositories before listing/importing them.

`GET /api/github/connect` creates a signed, expiring installation state and returns GitHub's App installation URL. GitHub redirects to the Setup URL, which is handled by the registered `GET /api/github/callback` route. This is not an OAuth callback. Repository tokens are short-lived and are never stored in the database or returned to the browser. Webhooks verify `X-Hub-Signature-256` and deduplicate `X-GitHub-Delivery`; push, installation, and installation-repository events are handled.

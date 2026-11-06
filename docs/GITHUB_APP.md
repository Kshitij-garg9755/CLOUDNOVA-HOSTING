# GitHub App setup

Create a GitHub App in GitHub settings:

- Homepage URL: your deployed CloudNova frontend URL.
- Setup URL: `https://cloudnova-api-qnzr.onrender.com/api/github/callback`; enable redirect after installation so GitHub supplies `installation_id`, `setup_action`, and the signed `state`. This is handled by the backend `GET /api/github/callback` route.
- OAuth user authorization callback URL: not used by this implementation; leave blank and do not enable a separate OAuth user authorization flow.
- Webhook URL: `https://cloudnova-api-qnzr.onrender.com/api/webhooks/github`.
- Subscribe to `Push`, `Installation`, and `Installation repositories` events. Pull request preview deployments are not implemented.
- Repository permissions: **Contents: Read-only**, **Metadata: Read-only**. Do not grant write access for the current import workflow.
- Generate a webhook secret and private key. Keep both server side.

Set `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_PRIVATE_KEY` (PEM, newline escaped if needed), `GITHUB_WEBHOOK_SECRET`, and `GITHUB_CALLBACK_URL=https://cloudnova-api-qnzr.onrender.com/api/github/callback` in the Render API environment. The GitHub App's Setup URL must exactly match `GITHUB_CALLBACK_URL`. The client ID and secret are retained as optional configuration but are not used in this installation-based flow. Grant **Metadata: Read-only** and **Contents: Read-only**, then install the App on the selected repositories before listing/importing them.

`GET /api/github/connect` creates a signed, expiring installation state, including the allow-listed frontend origin that started the flow, and returns GitHub's App installation URL. GitHub redirects to the Setup URL; the callback verifies that state and the installation with the App's private key, then persists GitHub's installation ID and account in `github_installations`. It returns the browser to the same frontend origin. This is not an OAuth callback. Repository listing uses short-lived installation tokens and returns actual GitHub repositories; tokens are never stored in the database or returned to the browser. Webhooks verify `X-Hub-Signature-256` and deduplicate `X-GitHub-Delivery`; push, installation, and installation-repository events are handled.

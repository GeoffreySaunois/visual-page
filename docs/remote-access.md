# Hosted reports

The commentable archive lives at **https://artefacts.saunois.xyz**. Cloudflare
Access verifies a reader's email with a one-time code. Cloud Run verifies the
signed identity and enforces each report's reader/commenter grants. The owner is
`geo.saunois@gmail.com`. No SMTP service, local daemon or reverse tunnel is needed.

## Authoring

Authenticate once (the browser handles the email code):

```sh
cloudflared access login https://artefacts.saunois.xyz
```

`cloudflared` is only a client for obtaining the cached Access token; no tunnel
process runs. The CLI reads the token without printing it. An expired session
requires another login. `ARTEFACTS_ACCESS_JWT` can supply an existing token.

```sh
visual-report render SOURCE.md --kind report --serve
visual-report comments report-my-topic
visual-report reply report-my-topic t1 --body 'Updated the explanation.'
```

`render --serve` stores the HTML/source locally for editing and publishes the page
to the hosted archive. The returned HTTPS URL is the link to share. Hosted comments
are authoritative; replies, edits and lifecycle commands use the authenticated API.
Agent comments retain their agent attribution. Never resolve a thread without the
user explicitly requesting it.

Sharing is per report through `visualreport.hosted.share`, using an existing Access
session. Readers can view; commenters can also discuss. A verified email without a
grant cannot read the report. Publishing and sharing require owner access.

## Optional local preview

`render --serve --local` and `visual-report serve` start only a loopback preview.
Use `--local` on a discussion command to inspect or edit its local comment copy.
These previews do not expose the archive publicly. `visual-report stop` stops the
local preview; it does not stop the hosted service.

Cloud Run scales to zero. Infrastructure, including storage, access and the Worker
proxy, is managed in `deploy/gcp`; see its README for deployment commands.

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

## Sharing

A verified email without a grant sees nothing: no gallery card, a 404 on every
report. The archive owner grants access per document or per folder, to one email
or to every verified email (`--everyone`: anyone who passes Cloudflare Access's
one-time code):

```sh
visual-report share alice@example.com --document report-my-topic --role reader
visual-report share alice@example.com --folder personal/medical-copilot --role commenter
visual-report share alice@example.com --folder personal/medical-copilot --role revoke
visual-report share --everyone --document report-my-topic --role reader
visual-report share --everyone --document report-my-topic --role revoke
visual-report shares    # every grant, by folder then by document
```

Readers can view; commenters can also discuss. A folder grant covers the folder,
every folder nested under it and the reports published there later. A report or
folder open to everyone shows in every verified user's gallery. A reader's role on
a report is the strongest of every grant that applies — its document and folder
grants, to their email and to everyone — so revoking one leaves the others in
place. The everyone grant is its own grantee, stored apart from the emails: it
never matches an unauthenticated request, which is refused before any grant is
read. Publishing, sharing and thread moderation stay with the owner.

## Optional local preview

`render --serve --local` and `visual-report serve` start only a loopback preview.
Use `--local` on a discussion command to inspect or edit its local comment copy.
These previews do not expose the archive publicly. `visual-report stop` stops the
local preview; it does not stop the hosted service.

Cloud Run scales to zero. Infrastructure, including storage, access and the Worker
proxy, is managed in `deploy/gcp`; see its README for deployment commands.

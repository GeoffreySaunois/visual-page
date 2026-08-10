# Reading the archive from a phone

The archive server binds loopback only, so a page it serves is reachable from the
machine that renders it and nowhere else. This document is how that same archive
becomes readable — and commentable — from a phone, and how it comes back on its own
after a reboot.

The chain, end to end:

```
iPhone ──▶ Cloudflare edge ──▶ Access (one-time PIN, allowlisted email)
                                 │  denies before anything reaches the Mac
                                 ▼
                        cloudflared tunnel (outbound, no open port)
                                 ▼
                    127.0.0.1:8787  the archive server
```

Two properties fall out of that shape and are worth stating, because they are the
reason it was built this way. **Nothing listens on a routable interface**: the
tunnel dials out, so the Mac exposes no port to any network. And **the gate sits in
front of the whole origin**, pages and comment API alike — an unauthenticated
request never reaches the server at all.

## What the engine knows about it

`server/tunnel.py` reads `~/.cloudflared/config.yml` and takes two things from it:
the tunnel to run, and the hostname the archive answers on. That file is therefore
the single source of truth — the engine and cloudflared cannot disagree about
either, because there is only one statement of each.

**The remote side is optional, and its opt-in is the presence of that config.** No
file, no usable ingress rule, or no `cloudflared` on the PATH, and there is no
tunnel at all: no error, no warning, and the local behavior unchanged. The engine
stays usable by someone who has never heard of Cloudflare.

`visual-report serve` starts the server and then the tunnel; `stop` ends both;
`status` reports both and the public address. A tunnel that fails to start is a
warning and never a failure of `serve` — losing local rendering because Cloudflare
is unreachable would be a regression.

## The one-time Cloudflare setup

Replayable on another machine or another domain. **The ordering is the point**: the
Access policy must exist before DNS resolves, or the archive is briefly public.

**1. Zero Trust.** Enable it on the Cloudflare account owning the domain, on the
**Free** plan — self-hosted Access applications, one-time PIN and API access are all
included, and 50 seats against the one user this needs. Cloudflare asks for a card
even at $0/seat; nothing is charged unless a paid add-on is switched on.

Choose the **team name** deliberately: it is account-wide, not per-application, and
it names the login page (`<team>.cloudflareaccess.com`) of every application ever
added. Naming it after one app ages badly. Changing it later invalidates live
sessions, so it is cheapest to get right before enrolling any device.

**2. The tunnel.**

```bash
cloudflared tunnel login            # browser; pick the zone
cloudflared tunnel create visual-reports
```

Write `~/.cloudflared/config.yml` — the ingress rule names the hostname and the
loopback origin, and the catch-all denies every other hostname pointed at this
tunnel:

```yaml
tunnel: <uuid printed by create>
credentials-file: /Users/<you>/.cloudflared/<uuid>.json

ingress:
  - hostname: reports.example.fr
    service: http://127.0.0.1:8787
  - service: http_status:404
```

`cloudflared tunnel ingress validate` checks it before anything is live.

**3. The Access application — before the DNS record.** *Zero Trust → Access →
Applications → Add an application → Self-hosted*, destination type **Public DNS**
(the hostname resolves publicly; the origin is still only reachable through the
tunnel, and Access default-denies in front of it).

| Field | Value |
|---|---|
| Destination | `reports` + `example.fr` |
| Session Duration | `1 month` — a phone should not re-authenticate often |
| Policy | Action **Allow**, Include **Emails** = the address that receives the code |
| Identity providers | pick One-time PIN explicitly rather than accepting all |
| Instant authentication | on — with a single method it skips the picker, one tap fewer |

**Never `Everyone` or `All authenticated users` as the policy include.** With
one-time PIN as the only method, "authenticated" means anyone in the world who can
receive an email. The email allowlist is the entire gate.

Prefer an address that does not belong to an employer: losing that mailbox would
lock you out of your own archive. Several addresses can share one include.

**4. Only now, the DNS record.**

```bash
cloudflared tunnel route dns visual-reports reports.example.fr
```

## Verifying it

```bash
curl -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/     # 200
curl -o /dev/null -w '%{http_code}\n' https://reports.example.fr/ # 302
```

**The 302 is the test that matters.** Unauthenticated, the public address must
redirect to the Access login. A `200` there means the gate is beside the archive
rather than in front of it — a serious hole, to be reported and not worked around.
Check `/api/health` the same way: the comment API must be gated too.

## Keeping it up: the launchd agent

Started by hand, the pair dies with the session — after a reboot the phone gets
through Access and lands on a **502**, because Cloudflare dials a port nobody
listens on any more.

`deploy/fr.askazul.visual-report.plist` is the service that prevents it. Install it
per user:

```bash
cp deploy/fr.askazul.visual-report.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/fr.askazul.visual-report.plist
launchctl kickstart -k gui/$(id -u)/fr.askazul.visual-report   # restart it
launchctl bootout gui/$(id -u)/fr.askazul.visual-report        # remove it, reversibly
```

**Why `StartInterval` and not `KeepAlive`.** `serve` spawns detached daemons and
then exits, so launchd would read every normal run as a crash and respawn it until
it throttled the job. `RunAtLoad` brings the pair up at login and `StartInterval`
re-runs the same command every five minutes instead — and because `serve` reuses a
running server and a running tunnel, a live pair costs a no-op while a dead one
comes back within one interval. The supervision falls out of the idempotency the
commands already have; nothing was added for it.

The plist states `PATH` explicitly because launchd inherits no shell environment,
and both `uv` and `cloudflared` live in Homebrew's prefix. Its output goes to
`~/.claude/html-reports/logs/launchd.log`.

Two limits this does not remove: a LaunchAgent starts **at login**, not at boot, so
a machine sitting at the login window serves nothing; and the Mac must be awake.
This is a personal server, not hosting.

## When it misbehaves

| Symptom | Cause |
|---|---|
| 502 after the Access login | The origin is down — `visual-report status`, then `serve` |
| `serve` warns and publishes nothing | A cloudflared started outside the engine holds the metrics port. `pkill -f "cloudflared tunnel run"`, then `serve` |
| `status` names a public address that answers 502 | Should not happen: a tunnel that never reaches the edge is halted before the error surfaces, precisely so `status` cannot lie |
| The login page shows an unexpected team name | It is account-wide; renaming it invalidates live sessions |

A page opened from the phone carries the templates it was built with. After a fix
to the comment panel, `visual-report refresh` replays the archive through the
current ones — see the README.

---
name: visual-page
description: Internal — the rendering engine behind the visual-* skills: the markdown dialect, the CLI, the archive, the iteration diff and the comment loop. Loaded by /visual and /ui-feature. Do not invoke directly.
user-invocable: false
---

# Visual page

How to author and compile **one self-contained `.html` page** and hand it over so
Geoffrey can comment on it. This is the shared engine of the `visual-*` family:

- **`/visual`** — reports/analyses, implementation plans, diff/PR recaps. It picks
  the genre and owns each genre's layout.
- **`/ui-feature`** — UI before/after from real screenshots, plus its capture process.

Those skills decide *what goes on the page*. This one owns *how a page is written,
compiled, served and iterated on* — the dialect, the CLI, the archive, the iteration
diff, the comment loop. Read it before authoring a source; nothing here is
genre-specific.

A page is not a dead end: Geoffrey can **comment on any passage** and you answer in
the thread, from the terminal. See *The comment loop* below — that is where most of
the iteration happens.

**The format structures the content — it never compresses it.** The page carries the
source's full argument: the reasoning, the definitions, the caveats, the developed
discussion — in a layout easier to read than raw markdown, not a TLDR of it. Turning
2000 words into a page means organizing those 2000 words, not cutting them to
punchlines. A short "60-second" summary page is opt-in only, when the user explicitly
asks for one.

**Self-containment rule.** Every section must read without the source document:
define each metric before charting it, spell out every mechanism/term/ID where it
appears (never force the reader to cross-reference), and wrap every visual in the
prose that interprets it — a chart or KPI row *supports* a written argument, it never
replaces one. Collapsibles hold annexes (raw data, source lists, methodology), never
the body of the reasoning.

## Hard rules

1. **Single file, fully self-contained.** All CSS, data, and JS inline — including
   the comment threads. The file must open by double-click on any machine, no
   server, no build, no local assets; the panel is then read-only (writing a
   comment is the one thing that needs the local server).
2. **CDN libs only when needed, pinned exactly.** Chart.js / Mermaid / MathJax from
   jsdelivr, at the versions pinned in `document/libraries.py`, and injected **only**
   for the features a page actually uses — a prose-only page ships zero CDN tags.
   Code highlighting happens at build time (Pygments), so it costs no library. You
   never write a `<script src=…>` yourself.
3. **Use the charte.** It lives in `templates/styles/*.css` and is inlined at build
   time: design tokens, dark mode, the light/dark toggle, the sortable tables, the
   comment rail. Write content, never visual identity — no `<style>` block and no
   inline `style=` in a source, except in the rare raw-HTML escape hatch.
4. **Adaptive interactivity** (the user's default):
   - Time series, trajectories, "X over runs/iterations" → **interactive line/bar chart** (Chart.js).
   - Comparisons across few categories → bar chart or a sortable table.
   - Flows / pipelines / state machines → **Mermaid** diagram.
   - Formulas → **MathJax** (see rule 6).
   - Real code snippets → a fenced block with its language (` ```python `, ` ```rust `):
     colored at build time by Pygments, tokens styled from the charte.
   - Structured before/after (old shape vs new, option A vs B) → **`cols`** two-column block.
   - A set of changed files → **`filetree`** with `ft-added`/`ft-removed`/`ft-modified`/`ft-renamed` flags.
   - Code changes → **`diff`** table: **unified** by default (`class="diff unified"`, compact, for new files and most hunks), **split** only for genuine before/after; annotate hunks with `annot` rows and group several behind a **`tabs`** block. Put code straight in `td.code` — no `<code>` wrapper.
   - A sequence of several screenshots meant to be stepped through in order (states
     of a flow, a repro walked step by step) rather than compared side by side →
     **`filmstrip`**: one slide visible at a time, prev/next buttons plus left/right
     arrow-key navigation. A before/after pair meant for direct comparison stays a
     plain vertical stack (see `ui-feature`'s layout rule) — `filmstrip` is for
     sequences too long to usefully stack, not a substitute for that comparison.
   - Otherwise → stay **sober**: KPI cards + clean tables + callouts, no JS libs.
   Don't add a chart just because you can; add it when it beats prose. The `cols` /
   `filetree` / `diff` / `tabs` / `filmstrip` blocks are inline HTML + vanilla JS (no
   CDN) — they carry no library cost, so the "zero `<script>`" rule still holds when
   only these are used.
5. **Color the visuals from the charte.** Charts and Mermaid diagrams must use the
   charte palette, never the libs' grey defaults. Mermaid: init with `theme: "base"` +
   `themeVariables` pulled from the `--accent*` / `--surface*` / `--text*` vars (the
   template does this). Multi-series charts: assign `PALETTE[i]` per dataset so >1
   series stays distinguishable. A monochrome-grey diagram is a tell the defaults leaked.
6. **Equations, when math is actually present.** Render real formulas as actual math
   (MathJax, loaded only if the page has any): inline in prose with `\(...\)`, display
   with `$$...$$` for the load-bearing equation. **A bare `$` is never a delimiter** —
   it collides with the literal dollar amounts a cost or benchmark report is full of
   (`$3–6`, `$/idée`), and MathJax would swallow the prose between two of them as
   italic math garbage. The renderer configures only `\(…\)` and `\[…\]` for exactly
   that reason; inside a formula write a literal dollar as `\$` (e.g.
   `\frac{\$}{\text{turn}}`). Define symbols once near first use, keep one equation per
   line, prefer `\dfrac`, `\,` spacing, and `\text{}` for words inside math. No math on
   a page without math — don't manufacture an equation to look rigorous.

## How to build one — markdown source → the CLI

**Author markdown, not HTML.** The page is written as a `.md` source file (front matter
+ the dialect below) and compiled by `visual-report render` into a self-contained HTML
page — sidebar table of contents with scroll-spy, reading-progress bar, light/dark
theme toggle, charte boxes, build-time Pygments highlighting, and pinned CDN tags
injected **only** for the features the page actually uses (MathJax / Chart.js /
Mermaid). Writing markdown keeps the register in "document" mode (dense, developed
prose) instead of "landing page" mode, and removes the lossy spec-to-sub-agent hop:
**author the source directly in the main agent.** Delegate to a sub-agent only bulk
*verbatim* transformations (e.g. porting an existing long document into the dialect),
with the explicit instruction that every paragraph is carried word-for-word.

1. **Plan the structure** from the source content and the genre's layout (`/visual`
   or `/ui-feature` carries it): the one-line headline, which block each section
   gets — carrying the source's full prose into every section (organize it, don't
   summarize it); only raw data, source lists, and methodology belong in collapsible
   appendices. Add a KPI row **only if** a few numbers genuinely carry the takeaway —
   never manufacture process/meta counts (sub-agents run, sources cited, items
   catalogued) just to fill the band. When no number is the story, ship no KPI cards;
   some genres ban the band outright.
2. **Write the `.md` source** using the dialect:
   - **Front matter** (required): `title`, `eyebrow`, `subtitle`; optional `date`
     (default today), `slug` (default from title), `lang` (default `fr`). These feed
     the `report-*` meta tags, the header, and the sidebar. The `slug` must **not**
     repeat the kind (`slug: gym-steering`, never `plan-gym-steering`) — the filename
     and the document identity already prepend it. Keep it stable across iterations:
     it is what ties a page to its comments and to its previous version.
   - **Headings**: `##` / `###` only (the h1 comes from front matter); they build the
     sidebar TOC.
   - **Callouts**: `!!! type "Title"` with the body indented 4 spaces. Types:
     `note`, `warning`, `danger`, `insight`/`intuition`, `definition`/`def`,
     `finding`/`key`, `example`.
   - **Collapsibles**: `??? note "Title"` (4-space body) — annexes only, never the
     body of the reasoning.
   - **Charts**: fenced ` ```chart title="…" caption="…" height="320" ` block whose
     body is a strict-JSON Chart.js config. Datasets without explicit colors get the
     charte palette automatically; charts re-render on theme toggle.
   - **Diagrams**: fenced ` ```mermaid caption="…" ` block (theme-aware, re-renders
     on toggle).
   - **KPI band**: fenced ` ```kpi ` block with a YAML list of `{value, label, note?}`.
   - **Math**: `\(inline\)` and `$$display$$` — never bare `$` (dollar amounts stay
     literal; MathJax only processes the wrapped spans).
   - **Tables**: markdown tables — rendered charte-styled and click-to-sort.
   - **File maps**: fenced ` ```filetree ` block — YAML list of `{path, flag:
     added|modified|removed|renamed, note?}`, rendered as flagged A/M/D/R rows.
   - **Diffs**: fenced ` ```diff title="…" mode="unified|split" ` block. Unified
     (default): body lines prefixed `+ ` / `- ` / `@ ` (dim annot row) / anything
     else = context — no line numbers, the gutter + tint carry the semantics.
     Split: two halves separated by a line containing exactly `~~~`, labels via
     `left="…" right="…"` (default "Avant"/"Après"). Code lands escaped verbatim,
     no syntax coloring. NB: this fence shadows plain ```diff highlighting.
   - **Two columns**: fenced ` ```cols left="…" right="…" ` block — two *markdown*
     halves separated by a `~~~` line; labels optional. Use 4+ backticks on the
     outer fence when a half contains a code fence.
   - **Transcripts** (agent sessions): fenced ` ```transcript ` block — YAML list
     of `{role: system|user|assistant|tool|tool-error, label?, content}` messages
     rendered verbatim, plus `{annot: "…"}` dim asides between messages.
   - **Tabs**: `=== "Tab title"` + 4-space-indented body (pymdownx.tabbed, max 10
     tabs per set; the body can contain the other fences) — group several diffs
     or snippets so each gets full document width.
   - **Images**: `![](path)` pointing at a local file is embedded as a data URI at
     build time, so a page carrying screenshots stays a single file.
   - **Image sequences**: fenced ` ```filmstrip title="…" ` block — YAML list of
     `{path, caption?}`, at least 2 items (a single image is a plain `![]()`).
     Renders as one slide at a time with prev/next buttons; left/right arrow keys
     move between slides once the block has focus (click it, or hover it — the
     mouseenter handler grabs focus for you). Each `path` resolves and embeds as a
     data URI exactly like a plain `![]()`, so the page stays one file.
   - **Nested blocks inside list items**: a fenced block or continuation
     paragraph belonging to a list item must be indented **4 spaces**, and the
     next `- ` item after indented content needs a **blank line** before it.
     An unindented fence terminates the list, and the following `- ` lines get
     lazily absorbed into the paragraph as literal "- " text. The same 4 spaces
     carry a tab body under its `=== "…"` header. The renderer detects both
     symptoms and warns — `literal list marker inside a paragraph` for a list cut
     by an unindented fence, `indented … block with nothing above it to nest
     under` for indented content that hangs from no item and no tab — treat
     either warning as a broken page, fix the source.
   - **Fence options go on the fence line**, never the line below: ` ```mermaid caption="…" `,
     not a bare ` ```mermaid ` followed by `caption="…"`. One line lower they are body
     content — mermaid reads `caption="…"` as its first statement and dies in the browser
     with *Syntax error in text*, a `cols` label becomes prose atop the left column.
     The renderer **hard-fails** on this (naming the fix) for every fence except the
     ```diff one, whose verbatim body may legitimately contain such a line.
   - **Escape hatch**: raw HTML passes through (`md_in_html`) for one-off layouts.
3. **Render** with the CLI:

    ```bash
    ~/.claude/skills/visual-page/bin/visual-report render SOURCE.md --kind KIND --serve
    ```

    Output is `~/.claude/html-reports/<kind>-<slug>-<date>.html`; the source is
    archived so the page can be re-rendered later; the gallery is rebuilt
    (`--no-index` to skip). Flags:
    - `--serve` starts the local server *and the tunnel* if needed, opens the page
      over http and prints its two addresses — **the only mode where Geoffrey can
      comment**, so prefer it always. The public one (`https://…`, gated by
      Cloudflare Access) is what he opens on his phone; the loopback one is the
      Mac's, and the only one printed when the machine has no tunnel configured.
    - `--open` just opens the file; the comment panel is then read-only.
    - `--kind {report|plan|recap|uidiff}` picks the page family: it decides the
      filename **and the document identity**, so it is what carries a page's
      comments and its iteration history. Any dash-free token works; default
      `report`.
    - `-o` writes elsewhere — a one-off export, outside the archive: **no archive,
      no iteration diff, no comment writes.** Never reach for it to control the
      filename; that is `--kind`'s job.
    - `--diff` / `--no-diff` force or disable the iteration diff.
4. **Review** the rendered page (structure, that every chart/diagram block compiled,
   every render warning fixed — a broken list or fence is a broken page), then tell
   the user the page's URL — the public one, see **Output** — plus the gallery path
   (`~/.claude/html-reports/index.html`) in one line.

Every `visual-*` page — report, plan, recap, uidiff — is authored as markdown and
compiled by this CLI; no page is hand-written in HTML.

## Archive & gallery

All pages live in `~/.claude/html-reports/` — a single persistent location outside
any repo, so they're never tracked and accumulate across sessions for demos:

```
<kind>-<slug>-<date>.html      the pages
index.html                     the gallery (rebuilt on every render)
src/<kind>-<slug>-<date>.md    the sources, kept for re-renders
src/.last-rendered/<doc>.md    the version the next iteration diff compares to
comments/<doc>.json            the comment threads
logs/server.log  .server.json  the local server
logs/tunnel.log  .tunnel.json  the tunnel publishing the archive
```

A **document** is `<kind>-<slug>` (e.g. `report-gym-costs`) — the identity that is
stable across renders, and what comments and iterations are keyed on. The gallery
reads each page's `<meta name="report-*">` tags and shows how many comments are
open on it, flagging those waiting on Claude. To browse, `open ~/.claude/html-reports/`.

**Reaching it.** `visual-report serve` brings up two processes: the loopback server,
and a cloudflared tunnel that publishes the same archive at the hostname read from
`~/.cloudflared/config.yml`, behind Cloudflare Access (e-mail OTP). `status` reports
both plus the public address, `stop` ends both. The tunnel is opt-in by the presence
of that config: without it — or without `cloudflared` — the engine serves locally
and says nothing about a tunnel. A tunnel that fails to start is a warning and never
stops `serve`. Diagnostics: `logs/tunnel.log` in the archive; a `cloudflared` started
outside the engine is invisible to `status` and holds the metrics port, so
`pkill -f "cloudflared tunnel run"` then `visual-report stop && visual-report serve`.
An unauthenticated request to the public hostname answers **302** to the Access login
— that is the guard working, not a breakage. The pair comes back at login through a
launchd agent, so a reboot does not leave the phone on a 502. Setting any of this up
on another machine, and what breaks it: `docs/remote-access.md`.

## Iteration diff

A page is rarely one-shot — you refine it and re-render. When a page is re-rendered,
it can show **what changed since last time**, so the reader reviews the delta instead
of re-reading the whole document. Every genre gets this: a plan is revised after
review, a recap is re-rendered after new commits.

- **What it diffs against.** The version **last rendered** for this document, kept
  at `src/.last-rendered/<kind>-<slug>.md`. A *one-step* reference — the previous
  version only, no history. Two documents are the same iff `<kind>-<slug>` matches:
  **keep the front-matter `slug` and the `--kind` stable across iterations**, or the
  diff loses the thread and the comment store with it. Refining a page twice in the
  same day shows a delta like any other iteration.
- **Flags.** Default is **auto**: diff iff a previous version exists. `--diff`
  forces it and errors if there is no previous; `--no-diff` disables it.
- **Per-content-type treatment.**
  - *Prose paragraphs* → inline **word diff**: removed runs as `del.vr-del`,
    inserted runs as `ins.vr-ins`. **Safety fallback:** if the paragraph carries
    inline markdown/HTML that splicing would corrupt (bold, code spans, links,
    emphasis, raw tags), the block degrades to a bordered box + badge instead —
    the markdown stays intact, no word diff.
  - *Fenced code, callouts, tables, mermaid, and every other block* that changed →
    a bordered box + a **corner badge** (`modifié` / `nouveau`), the content
    rendered normally inside.
  - *Headings* are never boxed (that would break the single-pass TOC); a heading
    change is recorded in the changelog only.
  - *Removed* blocks are **never re-inserted** — they appear in the changelog only.
- **Changelog band.** A `.vr-changelog` block sits at the top of the page: a
  `▲ N changements` header and one line per change, each with an inline badge
  (`modifié` / `nouveau` / `retiré`) and a link to the nearest heading of the
  changed block.
- **In-page controls** (top of the sidebar):
  - **Diff on/off** toggle — *on* reviews the highlighted changes + changelog,
    *off* shows the clean final document. Persisted in `localStorage` (`vr-diff`),
    default *on*. The button only appears when a diff was computed.
  - **3-state theme** toggle — système (◐) → clair (☀) → sombre (☾), cycling and
    persisted (`vr-theme`).
  - **← Index** — back to the gallery. Always present, even with no diff.
  - **Commentaires N** — opens the comment rail (see below); always present.

Matching is `difflib` over the source blocks (a pragmatic top-level splitter that
keeps fences and callouts whole); a changed block pairs as *modified* when it stays
recognizably similar, otherwise it counts as a removal plus an addition.

## The comment loop

A page is a place to work, not a deliverable to admire. Geoffrey highlights a
passage and comments on it; you answer in the thread, fix the source, re-render.
Comments live in `~/.claude/html-reports/comments/<document>.json` — outside any
repo, and independent of the pages, so they survive every re-render. Every genre
gets this: a plan is approved through its threads, a recap is challenged in them.

**In the page.** Select any text → *Commenter* → the thread opens in the right rail
with the passage quoted and highlighted in the document. A thread holds an ordered
exchange, is replied to and resolved (hidden from the default view, reopenable);
each message carries a **⋮** menu to *rewrite* it (it is then marked `modifié`) or
*delete* it — deleting the last message of a thread deletes the thread. Filters:
*Ouverts* / *Résolus* / *Tous*. **Writing requires the served page** — always hand
over a page with `--serve` if you expect feedback, over either of its addresses:
the public one goes through the tunnel to the same server, so commenting works
identically from the phone. A page opened as a plain file still shows every thread,
read-only.

**From the terminal** (`bin/visual-report`, `<document>` is `<kind>-<slug>`):

```bash
visual-report comments report-gym-costs            # open threads, with the passage each targets
visual-report comments report-gym-costs --all      # resolved ones too
visual-report reply report-gym-costs t3 --body "Corrigé : la série est bien celle du 2/08."
visual-report resolve report-gym-costs t3 --body "…"   # uniquement sur demande explicite de Geoffrey
visual-report comment report-gym-costs --quote "le coût marginal par idée" \
    --body "Je ne suis pas sûr de ce chiffre — d'où vient-il ?"
visual-report reopen report-gym-costs t3
visual-report edit report-gym-costs t3.2 --body "…"   # réécrire un message
visual-report delete report-gym-costs t3.2            # un message ; `t3` supprime le fil
```

`comment` is how **you** raise something: a claim you could not verify, a number
you want confirmed, two readings of an ambiguous request. `--quote` anchors it on
the passage (matched verbatim in the source, markdown emphasis ignored); without it
the thread is about the document. Every write defaults to `--as claude`; pass
`--as geoffrey` only when transcribing something he said.

**Who owes the next move.** Each open thread derives it from the last message:
`attend Claude` when Geoffrey wrote last, `attend Geoffrey` when you did. That is
your work queue — `visual-report comments <document>` puts the count in its header,
and the gallery flags the pages waiting on you.

**How to answer well.** Read the threads, fix the *source*, re-render, then reply
in each thread saying what changed. **Never resolve a thread yourself** — resolving
is Geoffrey's acknowledgment that the answer satisfies him, not a step of your
workflow: leave every thread open after replying and let him close it. The one
exception is when he explicitly asks you to resolve a thread. The reader then opens
the new version, sees the iteration diff of what moved, and the thread history
explaining why.

**When the passage moves.** An anchor is re-homed on every render: it follows its
block if the block moved, and states honestly when it could not. A thread whose
quoted words were rewritten is `dérivé` (its block is flagged in the margin, and
the digest shows the *current* wording); a thread whose block disappeared is
`orphelin`. Nothing is ever dropped for having lost its anchor.

**Checking the phone rendering, headlessly.** The panel is a bottom sheet under
720px, and that layout is verified locally through the **Playwright MCP** — no
dependency is added to the package, the tooling lives in the session. Drive a
*served* page (`visual-report status` prints the loopback address):

1. `browser_resize` **390×844**, then `browser_navigate` to
   `http://127.0.0.1:<port>/<page>.html`. After a re-render, append a
   cache-buster (`?v=2`) — Chrome otherwise replays the previous file and you
   review the old script. Re-`browser_resize` after any navigation hiccup: a
   reset viewport silently puts you back on the desktop layout.
2. The sidebar is off-screen on a phone, so the panel opens in two taps: click
   `.menu-btn`, then `#comments-toggle`.
3. What to look at — a thread is opened by a **selection only**: select a passage
   and dispatch a `mouseup`, the `Commenter` bubble shows, and the draft card
   carries the quoted passage. Send it, reload, and the thread is still there with
   its anchor and its `mark.vr-anchor` in the text. The panel foot holds the
   offline notice alone and is `hidden` while the server answers, so the sheet
   ends flush on its last card. Nothing overflows sideways:
   `document.documentElement.scrollWidth === clientWidth`.
4. `browser_resize` **1600×900** confirms the desktop is untouched — the panel is
   a full-height rail on the right edge, the sidebar is visible.
5. Delete whatever thread the check created (`visual-report delete <document> tN`).

**What this cannot see.** A driven Chrome/WebKit has no dynamic browser toolbar,
no virtual keyboard and no iOS AutoFill bar, so `--vr-view-h` / `--vr-view-lift`
and the input attributes that keep the keychain bar away are only verifiable as
*rendered markup*, never as behavior. Anything about those three is confirmed on
the real iPhone or not at all.

## Output

After writing, give the user **one line**: what the page covers + the URL of the
page + the gallery path. No re-narration of the content — the page *is* the content
now. When the page was rendered as an iteration diff, add that it shows the changes
since the previous version (toggle in the sidebar).

**Which URL.** A served page has two, both printed by `render --serve`, and the
rule is to hand over the one he can open anywhere:

1. the **public** one (`https://…/<page>.html`) — the tunnel's, readable and
   commentable from his phone as well as the Mac. Give this one, alone;
2. the **loopback** one (`http://127.0.0.1:…/<page>.html`) — cite it only when
   `render --serve` printed no public URL, which means no tunnel is up.

Never hand over the file path for a served page: it is the one address that cannot
be commented on.

When you answered comments, say which threads you replied to — they all stay open
for Geoffrey to resolve — and nothing more.

## Under the hood

The implementation is a Python package under `src/visualreport/`, run through
`bin/visual-report`. `README.md` there is the architecture map — read it before
changing the code, not before using the skill. Two ideas carry everything: every
feature aligns on the same **block split** of the source, and per-block layers
(iteration diff, comment anchors) are **decorators** applied in one pass.

The CLI keeps the name `visual-report`, and the archive keeps `~/.claude/html-reports/`,
while the skill is `visual-page`: renaming the command would orphan the archive, the
comment stores and the running server's state for a cosmetic gain.

## Possible evolutions

- **Sharing a page with someone else.** The public URL is the Mac's own archive
  behind Cloudflare Access, so it opens for Geoffrey and for nobody else. Handing a
  page to a third party would need a publish step (a static copy pushed somewhere,
  or an Access policy per page); neither is built.
- **Comment mentions of a chart or a table cell** — anchoring is block-level plus a
  text quote today, so a figure can only be commented as a whole.

## Quality bar

- Reads top-to-bottom as a story, along the spine its genre defines, with a KPI band
  up top only when numbers are the story.
- Dense by default: a reader who never opens the source document misses nothing of the
  argument. If a section only makes sense with the source open, it failed.
- Looks intentional on first open: consistent spacing, the charte's accent color,
  dark mode working via `prefers-color-scheme`.
- Every number on the page is traceable to the source; never invent data to fill a chart.
- Prints cleanly (the template already handles `@media print`).

# visualreport — architecture

The package behind the `visual-*` skills. It compiles a markdown source into one
self-contained HTML page, keeps every page in a local archive, and carries a
comment loop between Geoffrey and Claude on top of those pages.

`SKILL.md` next to this file is the `visual-page` skill — the engine's manual
(dialect, CLI, archive, iteration diff, comment loop), loaded by the two invocable
skills: `visual/` (report, plan, recap) and `ui-feature/` (UI before/after). This
file is for changing the code.

The package and the CLI keep the name `visualreport` / `visual-report` while the
skill is `visual-page`: the archive at `~/.claude/html-reports/`, the comment stores
and the running server's state are all keyed on it, so renaming buys nothing.

The hosted archive at https://artefacts.saunois.xyz uses Cloudflare Access for
identity, Cloud Run for the API, Firestore for discussions and GCS for publications.
The CLI publishes and discusses through the same authenticated API as the browser.
`docs/remote-access.md` describes authoring and optional local previews.

## Run it

```bash
bin/visual-report render SOURCE.md --serve      # compile and publish commentable
bin/visual-report pdf report-<slug>             # the published page, on paper
bin/visual-report comments report-<slug>        # what is pending, as markdown
bin/visual-report refresh --dry-run             # what a rebuild of the archive would touch
uv run --frozen pytest                                   # the suite
```

**A page keeps the templates it was built with.** Styles and scripts are inlined at
render time, so a fix to the comment panel or to the charte reaches the pages
rendered afterwards and no others. `refresh` closes that gap: it replays every
archived source through the current templates and rewrites each page in place,
under its own name and its own date — `refresh <kind>-<slug>` for one document,
`--dry-run` to see the list first and `--serve` to republish refreshed pages. It is the gesture that follows a change under
`templates/`.

What it cannot promise is that an old page comes back *the same*: it is rebuilt by
today's renderer, so a page published before a dialect or a splitter change comes
back rendered the way that source reads now — what you want when the change is a
fix, a surprise otherwise. **Take a copy of the archive before a wide pass** (it is
outside any repo and there is no undo), and diff the visible text of the pages that
changed.

`bin/visual-report` is a wrapper over `uv run --frozen --project <here> visual-report`, so
it works from any directory and syncs the environment on the way in.

**Hosted code runs in the deployed Cloud Run image.** A backend change requires a
new deployment. A template change requires republishing its affected reports.
`visual-report serve` is an explicit loopback preview; restart that preview after
changing its Python code. It starts no tunnel or background login service.
`VISUAL_REPORT_ARCHIVE` selects a different local authoring archive for tests.

## The tree

```
src/visualreport/
  paths.py          the archive layout — the only module that knows the disk
  folders.py        the closed taxonomy of folders the gallery files pages under
  rendering.py      the pipeline: where document, iteration and comments meet
  refresh.py        replaying archived pages through today's templates, in place
  pdf.py            a page on paper: a headless browser over the print stylesheet
  document/         markdown source ──► HTML page
    frontmatter.py    the YAML head, and the three documented fallbacks
    blocks.py         the top-level block splitter: THE unit everything aligns on
    composition.py    rebuilding a body through a chain of per-block decorators
    anchors.py        decorator: give every block a DOM address
    converter.py      the markdown converter and its extensions
    fences/           the dialect's fences (figures, data, code, layout)
    page.py           template + style/script partials ──► the final HTML
    controls.py       which controls the sidebar carries
    libraries.py      the pinned CDN libs, included only when used
    images.py lints.py
  iteration/        what changed since the previous version of this document
    matching.py       block alignment (also used to re-home comments)
    annotate.py       decorator: box or word-diff a changed block
    changelog.py review.py
  comments/         threads on a passage
    model.py          Thread / Comment / Anchor / who the loop awaits
    store.py          one locked JSON file per document, atomic writes
    anchors.py        re-homing a thread across a rewrite
    digest.py         the threads as markdown, for the agent
    view.py           the shape the page reads
  server/           reaching the archive: the loopback server and its public address
    app.py api.py __main__.py   the archive as static files + the comment API
    detached.py       the lifecycle both background processes share
    daemon.py         the server process: its command, its state, its health check
    tunnel.py         the cloudflared tunnel: the config it reads, a page's public URL
  gallery/          the archive index, filed by folder, with what is pending on each page
  templates/        page.html, gallery.html, styles/*.css, scripts/*.js
```

## The two ideas worth knowing

**Everything aligns on blocks.** `document/blocks.py` splits a source into
top-level blocks (a paragraph, a fence, a callout, a heading). A comment anchor
stores a block index; an iteration diff computes per block. Because both read the
*same* split of the *same* source, an index always means the same passage.

Which makes the split itself load-bearing across versions: **change how a source
is cut and every stored index below the first change means another passage.** The
next real render repairs it — `comments/anchors.py` re-homes each thread by
matching its recorded block *text*, not its index — but a `refresh` embeds the
stored indices untouched, by design. So a splitter change is measured on the real
stores in `~/.claude/html-reports/comments/` before the archive is rebuilt: the
threads whose index moves are those of a document rebuilt without a re-render in
between, and they need one.

**Per-block features are decorators.** `document/composition.py` rebuilds the
markdown body by passing each block through a chain of `BlockDecorator`s before
the single conversion pass. Today the chain is `[iteration diff, block address]`;
the last one wraps outermost. Adding a per-block feature means writing a
decorator, not rewriting the body again.

## Where a change goes

| To add… | Touch |
|---|---|
| a fence in the dialect | a formatter in `document/fences/`, one line in `registry.py` |
| a per-block visual layer | a decorator + one entry in `rendering.render` |
| a style or a behavior | a file in `templates/styles` or `scripts`, one entry in `page.py`'s order tuple |
| an API endpoint | `server/api.py` (domain logic belongs in `comments/`) |
| a CLI command | a module in `cli/`, registered in `cli/main.py` |
| what a page looks like on paper | `templates/styles/print.css`, and the print hooks in `scripts/page.js` for what a gesture hides |
| a third background process | a `DetachedProcess` in `server/detached.py` + a module owning its command, state and probe |
| a field on a thread | `comments/model.py` + bump `SCHEMA_VERSION` when it breaks reads, and migrate the files in `comments/` in the same change |

## Invariants

- **A page is one file.** Styles and scripts are inlined, images become data URIs,
  CDN libs are pinned exactly and included only when the content uses them.
- **Reading never needs the server.** Every page embeds its threads as JSON, so an
  archived file opened by double-click shows the whole exchange. Only *writing*
  needs the server.
- **A comment is never dropped.** If the quoted words were rewritten it *drifts*;
  if the block disappeared it is *orphaned*. Both stay visible and say so.
- **Two writers, one hosted store.** Browser and CLI mutations use authenticated
  API transactions. Local preview comments use `comments/store.py` with atomic
  replacements; those files are not the authoritative hosted discussion.
- **The iteration reference is one step.** `src/.last-rendered/<document>.md` holds
  the version last rendered; a diff compares against it and never builds a history.
- **A refresh advances nothing.** Rebuilding a published page replays the source
  that produced it: no diff (there is nothing to compare), the iteration reference
  left where it points, and the threads left on the homes they have — re-homing
  them on an old version would drag the anchors backwards. The rebuilt page is
  promoted only once it is whole, and an image whose file left the disk is carried
  over from the page being replaced, so a refresh never costs a screenshot.
- **Publication is explicit.** `render --serve` writes to the hosted service and
  returns its HTTPS URL. A failed or expired login fails publication clearly;
  there is no silent fallback to a private loopback URL.
- **Local preview is explicit.** `--local` and `serve` never open a public tunnel.

## Testing

The suite covers logic that can actually break: the splitter's invariants,
re-homing across edits (moved / rewritten / deleted), thread lifecycle and store
round-trip, and the render pipeline end to end. The HTTP layer is thin wiring over
that logic and is exercised by hand (`curl`, and a playwright script driving the
real panel) rather than by change-detector tests.

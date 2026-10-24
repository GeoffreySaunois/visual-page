/* The comment layer: a Comments panel on the right of the reading column, a
   floating « Commenter » toolbar over a selected passage that turns into the
   composer of a new thread right there (selection-actions.js draws it), and
   the highlights of every commented passage in the document.

   Reading works everywhere: every page is rendered with its threads embedded, so
   a file opened by double-click still shows the whole exchange. Writing needs the
   comment server — when the API does not answer, the panel says how to start
   it instead of pretending to save, and no passage is offered for commenting.

   Threads are anchored on a block index plus the quoted words (with the text
   just before and after them). A figure — table, diagram, chart, image — has
   no words to select, so it is commented as its whole block: the same anchor
   with an empty quote, prefix and suffix. Highlights are recomputed from the text at load
   time rather than baked into the HTML, which is what lets a thread survive an
   edit: if the words moved inside the block they are found again, and if they
   are gone the block itself carries a rule in its margin.

   The page frame (template, top bar, layout) owns the empty `#vr-panel` slot and
   the `#comments-toggle` button with its `#comments-count` badge; everything
   inside the panel is built here. Opening the panel sets `vr-comments-open` on
   <html>, which the frame's stylesheet turns into a pushed reading column, and
   its width rides the `--panel-w` custom property on <html>. */
(function () {
  "use strict";

  var POLL_MS = 4000;
  var AUTHOR_KINDS = { human: "Geoffrey", agent: "Claude" };
  var root = document.documentElement;

  var state = {
    documentId: "",
    threads: [],
    revision: 0,
    filter: "open",       /* "open" | "resolved" */
    active: null,         /* the thread emphasised in the panel and the document */
    api: null,            /* base URL once the server answered, null when offline */
    draft: null,          /* {anchor, label} the inline composer writes a new thread on;
                             `label` names a whole figure, null for a selection */
    replyTo: null,        /* the thread id the composer replies to */
    editing: null,        /* the comment being rewritten in place */
    pending: false        /* a composer write is in flight */
  };

  var ui = {};            /* the panel's parts, filled by buildPanel() */

  /* ================================================================ Boot === */
  function boot() {
    var seed = document.getElementById("vr-bootstrap");
    var data = seed ? JSON.parse(seed.textContent) : { threads: [] };
    state.documentId = data.document_id || "";
    state.threads = data.threads || [];
    state.revision = data.revision || 0;
    ui.panel = document.getElementById("vr-panel");
    ui.toggle = document.getElementById("comments-toggle");
    ui.count = document.getElementById("comments-count");
    if (!ui.panel) return;
    buildPanel();
    PanelWidth.bind();
    bindPanelToggle();
    bindKeyboard();
    bindDocumentClicks();
    Selection.bind();
    bindFigureComments();
    publishViewport();
    paint();
    probeApi();
    setInterval(poll, POLL_MS);
  }

  /* On a phone the panel spans the screen, sized on the part of the page the
     browser really shows. `--vr-view-h` is that height, `--vr-view-top` how far
     the visual viewport is scrolled into the layout one, and `--vr-view-lift`
     the band below it — the overlaying browser toolbar, then the virtual
     keyboard. Fixed positioning ignores all three, so the panel's stylesheet
     subtracts them to keep the composer above the keyboard. */
  function publishViewport() {
    var view = window.visualViewport;
    if (!view) return;
    function apply() {
      var layout = root.clientHeight;
      root.style.setProperty("--vr-view-h", view.height + "px");
      root.style.setProperty("--vr-view-top", Math.max(0, Math.round(view.offsetTop)) + "px");
      root.style.setProperty("--vr-view-lift",
        Math.max(0, Math.round(layout - view.height - view.offsetTop)) + "px");
    }
    view.addEventListener("resize", apply);
    view.addEventListener("scroll", apply);
    apply();
  }

  /* ================================================================= API === */
  function probeApi() {
    if (location.protocol !== "http:" && location.protocol !== "https:") return paint();
    fetch("/api/health", { cache: "no-store" })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (health) {
        if (!health || !health.ok) return paint();
        state.api = "/api/documents/" + encodeURIComponent(state.documentId);
        paint();
        /* The embedded copy is as old as the last render: with a server there,
           catch up immediately instead of showing stale threads until the first
           poll. */
        poll();
      })
      .catch(function () { paint(); });
  }

  function poll() {
    if (!state.api || document.hidden) return;
    fetch(state.api + "/threads", { cache: "no-store" })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        if (!data || data.revision === state.revision) return;
        state.revision = data.revision;
        state.threads = data.threads;
        paint();
      })
      .catch(function () { /* the server went away; the panel keeps what it has */ });
  }

  function send(path, method, payload) {
    if (!state.api) return Promise.reject(new Error("offline"));
    return fetch(state.api + path, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: payload ? JSON.stringify(payload) : null
    }).then(function (response) {
      if (!response.ok) return response.text().then(function (text) { throw new Error(text); });
      return response.json();
    }).then(function (data) {
      state.revision = data.revision;
      state.threads = data.threads;
      paint();
    });
  }

  var Api = {
    openThread: function (anchor, body) { return send("/threads", "POST", { anchor: anchor, body: body }); },
    reply: function (threadId, body) {
      return send("/threads/" + threadId + "/comments", "POST", { body: body });
    },
    editComment: function (threadId, commentId, body) {
      return send("/threads/" + threadId + "/comments/" + commentId, "PATCH", { body: body });
    },
    removeComment: function (threadId, commentId) {
      return send("/threads/" + threadId + "/comments/" + commentId, "DELETE", null);
    },
    resolve: function (threadId) { return send("/threads/" + threadId + "/resolve", "POST", null); },
    reopen: function (threadId) { return send("/threads/" + threadId + "/reopen", "POST", null); },
    removeThread: function (threadId) { return send("/threads/" + threadId, "DELETE", null); }
  };

  /* ======================================================= Panel scaffold === */
  /* One title row (name, Ouverts/Résolus, close), the thread stream, and the
     composer docked at the foot. */
  function buildPanel() {
    var panel = ui.panel;
    panel.classList.add("vr-panel");
    panel.tabIndex = -1;
    panel.textContent = "";

    ui.grip = el("div", "vr-panel-resize");
    ui.grip.setAttribute("aria-label", "Redimensionner le panneau");
    ui.grip.setAttribute("aria-controls", "vr-panel");

    var toolbar = el("div", "vr-panel-toolbar");
    toolbar.appendChild(el("h2", "vr-panel-title", "Commentaires"));
    var filters = el("div", "vr-filter");
    filters.setAttribute("role", "group");
    filters.setAttribute("aria-label", "État des fils");
    ui.filterOpen = filterButton("open", "Ouverts");
    ui.openCount = el("span", "vr-filter-count");
    ui.filterOpen.appendChild(ui.openCount);
    ui.filterResolved = filterButton("resolved", "Résolus");
    filters.appendChild(ui.filterOpen);
    filters.appendChild(ui.filterResolved);
    toolbar.appendChild(filters);
    var close = iconButton("close", "Fermer les commentaires", function () { Panel.show(false); });
    close.classList.add("vr-panel-close");
    close.title = "Fermer (C)";
    toolbar.appendChild(close);

    ui.stream = el("div", "vr-stream");
    ui.threads = el("div", "vr-threads");
    ui.stream.appendChild(ui.threads);

    ui.composer = Composer.build();

    panel.appendChild(ui.grip);
    panel.appendChild(toolbar);
    panel.appendChild(ui.stream);
    panel.appendChild(ui.composer);
  }

  function filterButton(value, label) {
    var node = el("button", "", label);
    node.type = "button";
    node.setAttribute("data-filter", value);
    node.addEventListener("click", function () { state.filter = value; paint(); });
    return node;
  }

  /* ===================================================== Panel visibility === */
  var Panel = {
    isOpen: function () { return root.classList.contains("vr-comments-open"); },
    show: function (open) {
      if (open === Panel.isOpen()) return;
      var hadFocus = ui.panel.contains(document.activeElement);
      root.classList.toggle("vr-comments-open", open);
      ui.panel.hidden = !open;
      if (ui.toggle) {
        ui.toggle.setAttribute("aria-pressed", String(open));
        ui.toggle.setAttribute("aria-expanded", String(open));
      }
      if (open) { Selection.hide(); PanelWidth.sync(); }
      else if (hadFocus && ui.toggle) ui.toggle.focus();
    },
    toggle: function () { Panel.show(!Panel.isOpen()); }
  };

  function bindPanelToggle() {
    ui.panel.hidden = true;
    if (!ui.toggle) return;
    ui.toggle.setAttribute("aria-expanded", "false");
    if (!ui.toggle.title) ui.toggle.title = "Commentaires (C)";
    ui.toggle.addEventListener("click", Panel.toggle);
  }

  /* ========================================================== Panel width === */
  /* The panel's left edge is a separator: dragged with the pointer, stepped
     with the arrow keys, sent to its bounds with Home/End, reset with a double
     click. The width is kept per viewer; the stylesheet's default applies until
     the edge is first moved. */
  var PanelWidth = (function () {
    var KEY = "vr-panel-w";
    var MIN = 320;
    var DOCKED_ROOM = 560;   /* the reading column a docked panel leaves… */
    var OVERLAY_ROOM = 160;  /* …and the strip an overlaying one leaves */
    var KEY_STEP = 16;
    var drag = null;

    function enabled() { return window.innerWidth > 700 && Panel.isOpen(); }
    function bounds() {
      var width = window.innerWidth;
      var room = width >= 1024 ? DOCKED_ROOM : OVERLAY_ROOM;
      return { min: MIN, max: Math.max(MIN, width - room) };
    }
    function clamp(width) {
      var limits = bounds();
      return Math.round(Math.max(limits.min, Math.min(width, limits.max)));
    }
    function current() { return ui.panel.getBoundingClientRect().width; }
    function apply(width) {
      if (width === null) root.style.removeProperty("--panel-w");
      else root.style.setProperty("--panel-w", width + "px");
    }
    function keep(width) {
      try {
        if (width === null) localStorage.removeItem(KEY);
        else localStorage.setItem(KEY, String(width));
      } catch (error) { /* storage refused: the width lasts for this visit */ }
    }
    function stored() {
      try {
        var value = parseFloat(localStorage.getItem(KEY));
        return value > 0 ? value : null;
      } catch (error) { return null; }
    }
    function sync() {
      var limits = bounds();
      ui.grip.setAttribute("aria-valuemin", String(limits.min));
      ui.grip.setAttribute("aria-valuemax", String(limits.max));
      ui.grip.setAttribute("aria-valuenow", String(Math.round(current())));
    }

    function start(event) {
      if (event.button !== 0 || !enabled()) return;
      event.preventDefault();
      ui.grip.setPointerCapture(event.pointerId);
      drag = { pointer: event.pointerId, x: event.clientX, width: current(), last: null };
      root.classList.add("vr-panel-resizing");
      ui.grip.classList.add("dragging");
    }
    function move(event) {
      if (!drag || event.pointerId !== drag.pointer) return;
      var width = clamp(drag.width - (event.clientX - drag.x));
      if (width === drag.last) return;
      drag.last = width;
      apply(width);
      ui.grip.setAttribute("aria-valuenow", String(width));
    }
    function end(event) {
      if (!drag || event.pointerId !== drag.pointer) return;
      var last = drag.last;
      drag = null;
      root.classList.remove("vr-panel-resizing");
      ui.grip.classList.remove("dragging");
      if (last !== null) keep(last);
      sync();
    }
    function key(event) {
      if (!enabled()) return;
      var step = KEY_STEP * (event.shiftKey ? 4 : 1);
      var moves = { ArrowLeft: step, ArrowRight: -step };
      var width = null;
      if (event.key in moves) width = clamp(current() + moves[event.key]);
      else if (event.key === "Home") width = bounds().min;
      else if (event.key === "End") width = clamp(bounds().max);
      if (width === null) return;
      event.preventDefault();
      apply(width);
      keep(width);
      sync();
    }

    return {
      sync: sync,
      bind: function () {
        var grip = ui.grip;
        grip.setAttribute("role", "separator");
        grip.setAttribute("aria-orientation", "vertical");
        grip.tabIndex = 0;
        grip.addEventListener("pointerdown", start);
        grip.addEventListener("pointermove", move);
        grip.addEventListener("pointerup", end);
        grip.addEventListener("pointercancel", end);
        grip.addEventListener("lostpointercapture", end);
        grip.addEventListener("dblclick", function () { apply(null); keep(null); sync(); });
        grip.addEventListener("keydown", key);
        var width = stored();
        if (width !== null) apply(clamp(width));
      }
    };
  })();

  /* ============================================================ Keyboard === */
  /* `C` toggles the panel unless a key is being typed or a modifier is held.
     Escape unwinds one layer at a time: an open menu, a rewrite in progress,
     the inline composer (its own field cancels it), the reply target (when the
     field is empty), a field with a draft (put down, the draft kept), the
     floating toolbar, and finally the panel. */
  function bindKeyboard() {
    window.addEventListener("keydown", function (event) {
      if (event.defaultPrevented || event.isComposing || typeof event.key !== "string") return;
      if (event.key === "Escape") return escape(event);
      if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey || event.repeat) return;
      if (typing(event.target)) return;
      if (event.key.toLowerCase() === "c") { event.preventDefault(); Panel.toggle(); }
    });
  }

  function escape(event) {
    if (Menu.isOpen()) { event.preventDefault(); Menu.close(true); return; }
    var target = event.target;
    if (state.editing && target && target.id === "vr-edit-body") {
      event.preventDefault();
      state.editing = null;
      paint();
      ui.panel.focus();
      return;
    }
    if (target === ui.field) {
      event.preventDefault();
      if (!ui.field.value.trim() && state.replyTo) Composer.disarm();
      ui.panel.focus();
      return;
    }
    if (typing(target)) { event.preventDefault(); target.blur(); return; }
    if (Selection.visible()) { Selection.hide(); return; }
    if (Panel.isOpen()) { event.preventDefault(); Panel.show(false); }
  }

  function typing(target) {
    return Boolean(target && target.closest &&
      target.closest("input, textarea, select, [contenteditable]:not([contenteditable=false])"));
  }

  /* ============================================================ Painting === */
  function paint() {
    paintCounts();
    paintThreads();
    Composer.refresh();
    Highlights.paint();
  }

  /* The open count rides the Ouverts filter and the top bar's badge; Résolus
     shows only once a thread is resolved. */
  function paintCounts() {
    var open = state.threads.filter(function (thread) { return thread.is_open; }).length;
    var resolved = state.threads.length - open;
    if (!resolved && state.filter === "resolved") state.filter = "open";
    ui.filterOpen.setAttribute("aria-pressed", String(state.filter === "open"));
    ui.filterResolved.setAttribute("aria-pressed", String(state.filter === "resolved"));
    ui.filterResolved.hidden = !resolved;
    ui.openCount.textContent = open ? String(open) : "";
    if (ui.count) {
      ui.count.textContent = open > 99 ? "99+" : String(open);
      ui.count.hidden = !open;
    }
    if (ui.toggle) {
      ui.toggle.setAttribute("aria-label", open
        ? "Commentaires, " + open + (open > 1 ? " ouverts" : " ouvert")
        : "Commentaires");
    }
  }

  function matchesFilter(thread) {
    return state.filter === "open" ? thread.is_open : !thread.is_open;
  }

  function paintThreads() {
    var keepScroll = ui.stream.scrollTop;
    ui.threads.textContent = "";
    var shown = state.threads.filter(matchesFilter);
    shown.forEach(function (thread) { ui.threads.appendChild(threadCard(thread)); });
    if (!shown.length) ui.threads.appendChild(emptyNotice());
    ui.stream.scrollTop = keepScroll;
  }

  function emptyNotice() {
    return el("p", "vr-hint vr-empty", state.filter === "resolved"
      ? "Aucun fil résolu."
      : "Aucun commentaire ouvert.");
  }

  /* ============================================================= Threads === */
  function threadCard(thread) {
    var classes = ["vr-thread"];
    if (!thread.is_open) classes.push("resolved");
    if (state.active === thread.id) classes.push("active");
    if (state.replyTo === thread.id) classes.push("replying");
    var card = el("article", classes.join(" "));
    card.setAttribute("data-thread", thread.id);
    card.appendChild(threadHeading(thread));
    card.appendChild(threadMeta(thread));
    thread.comments.forEach(function (comment, index) {
      card.appendChild(message(thread, comment, index === 0));
    });
    if (state.api && thread.is_open) card.appendChild(replyRow(thread));
    /* The card as a whole reaches its passage; its own controls keep their jobs. */
    card.addEventListener("click", function (event) {
      if (event.target.closest("button, a, input, textarea, select, summary")) return;
      activate(thread.id, { scrollDocument: true });
    });
    return card;
  }

  /* The quoted passage, and the resolve/reopen action beside it. */
  function threadHeading(thread) {
    var heading = el("div", "vr-thread-heading");
    if (!thread.anchor) heading.appendChild(el("blockquote", "vr-quote whole", "Sur tout le document"));
    else if (wholeBlock(thread.anchor)) {
      heading.appendChild(el("blockquote", "vr-quote whole", Figures.label(blockAt(thread.anchor.block_index))));
    } else heading.appendChild(el("blockquote", "vr-quote", thread.anchor.quote));
    if (state.api) heading.appendChild(resolveButton(thread));
    return heading;
  }

  function resolveButton(thread) {
    var label = thread.is_open ? "Résoudre" : "Réouvrir";
    var node = iconButton(thread.is_open ? "check" : "reopen", label, function () {
      busy(node, thread.is_open ? Api.resolve(thread.id) : Api.reopen(thread.id));
    });
    node.classList.add("vr-thread-resolve");
    return node;
  }

  /* What the thread's state says beyond its words: its id, who it waits on,
     whether its passage moved, and the section it sits in. */
  function threadMeta(thread) {
    var meta = el("div", "vr-thread-meta");
    meta.appendChild(el("span", "vr-tid", thread.id));
    if (thread.is_open && thread.awaiting) {
      meta.appendChild(el("span", "vr-tag " + thread.awaiting, "attend " + AUTHOR_KINDS[thread.awaiting]));
    }
    /* A whole block has no quoted words to lose, so the server's « drifted »
       (its quote no longer found) says nothing about it. */
    if (thread.state === "drifted" && !wholeBlock(thread.anchor)) {
      meta.appendChild(el("span", "vr-tag moved", "texte réécrit"));
    }
    if (thread.state === "orphaned") meta.appendChild(el("span", "vr-tag moved", "bloc disparu"));
    if (thread.anchor && thread.anchor.section) {
      meta.appendChild(el("span", "vr-section", "§ " + thread.anchor.section));
    }
    return meta;
  }

  function message(thread, comment, isFirst) {
    var agent = comment.author.kind === "agent";
    var node = el("div", "vr-message" + (agent ? " agent" : ""));
    var by = el("div", "vr-author");
    by.appendChild(avatar(comment.author));
    by.appendChild(el("span", "vr-name", comment.author.name));
    if (comment.edited_at) by.appendChild(el("span", "vr-edited", "modifié"));
    by.appendChild(timeOf(comment.created_at));
    if (state.api) by.appendChild(Menu.button(thread, comment, isFirst));
    node.appendChild(by);
    if (state.editing === comment.id) node.appendChild(editForm(thread, comment));
    else node.appendChild(CommentBody.render(comment));
    return node;
  }

  /* A person wears their initials; an agent a robot, solid, so a machine's
     message reads as one at a glance. */
  function avatar(author) {
    var chip = el("span", "vr-avatar " + author.kind);
    if (author.kind === "agent") chip.innerHTML = icon("bot");
    else chip.textContent = (author.name || "?").slice(0, 2).toUpperCase();
    return chip;
  }

  function timeOf(iso) {
    var node = el("time", "", relativeTime(iso));
    node.dateTime = iso;
    node.title = new Date(iso).toLocaleString("fr-FR", {
      day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit"
    });
    return node;
  }

  /* Replies are written in the composer at the foot of the panel; the thread
     only says which one the composer should aim at. */
  function replyRow(thread) {
    var row = el("div", "vr-thread-actions");
    var node = el("button", "vr-thread-reply", "Répondre");
    node.type = "button";
    node.addEventListener("click", function () { Composer.replyTo(thread.id); });
    row.appendChild(node);
    return row;
  }

  /* A rewrite happens in place, under the author line. */
  function editForm(thread, comment) {
    var form = el("form", "vr-edit");
    var field = el("textarea");
    describeAsProse(field, "vr-edit-body");
    field.value = comment.body;
    field.setAttribute("aria-label", "Modifier le message");
    field.rows = 3;
    var row = el("div", "vr-edit-row");
    var cancel = el("button", "vr-quiet", "Annuler");
    cancel.type = "button";
    cancel.addEventListener("click", function () { state.editing = null; paint(); });
    var save = el("button", "vr-primary", "Enregistrer");
    save.type = "submit";
    save.title = "Enregistrer (" + SUBMIT_LABEL + ")";
    row.appendChild(cancel);
    row.appendChild(save);
    form.appendChild(field);
    form.appendChild(row);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var body = field.value.trim();
      if (!body) return;
      save.disabled = true;
      Api.editComment(thread.id, comment.id, body)
        .then(function () { state.editing = null; paint(); })
        .catch(function (error) { save.disabled = false; failed(error); });
    });
    bindSubmitShortcut(field, form);
    return form;
  }

  /* ================================================= Active thread ======= */
  /* The active thread is emphasised in the panel and in the document at once.
     Reached from the panel, the document scrolls to its passage; reached from
     a highlight, the panel scrolls to its card. */
  function activate(id, options) {
    state.active = id;
    ui.threads.querySelectorAll(".vr-thread").forEach(function (card) {
      card.classList.toggle("active", card.getAttribute("data-thread") === id);
    });
    Highlights.emphasise(id, Boolean(options && options.scrollDocument));
  }

  /* A highlight pressed in the document brings its thread into view, whatever
     filter the panel was left on. */
  function openThread(id) {
    var thread = findThread(id);
    if (!thread) return;
    state.filter = thread.is_open ? "open" : "resolved";
    state.active = id;
    Panel.show(true);
    paint();
    var card = ui.threads.querySelector('[data-thread="' + cssEscape(id) + '"]');
    if (card) card.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function bindDocumentClicks() {
    /* Any press that is not on a card, in the composer, on a highlight or on a
       floating surface puts the active thread down. */
    document.addEventListener("pointerdown", function (event) {
      if (!state.active) return;
      if (event.target.closest && event.target.closest(
        ".vr-thread, .vr-composer, .vr-selection-actions, .vr-menu, mark.vr-anchor, .vr-commented, .vr-figure-marker, #comments-toggle"
      )) return;
      activate(null, null);
    });
  }

  function findThread(id) {
    for (var index = 0; index < state.threads.length; index++) {
      if (state.threads[index].id === id) return state.threads[index];
    }
    return null;
  }

  /* ======================================================= Comment body === */
  /* An agent's reply is Markdown and drawn as such (paragraphs, lists, code
     blocks, quotes, headings, emphasis, links); a person's comment is the
     literal text they typed, line breaks kept, its web addresses made links. */
  var CommentBody = {
    render: function (comment) {
      var agent = comment.author.kind === "agent";
      var body = el("div", "vr-body " + (agent ? "markdown" : "literal"));
      body.innerHTML = agent ? markdown(comment.body) : linkify(escapeHtml(comment.body));
      return body;
    }
  };

  function markdown(source) {
    var lines = source.replace(/\r\n?/g, "\n").split("\n");
    var out = [], index = 0;
    while (index < lines.length) {
      var line = lines[index];
      var fence = /^\s*(```|~~~)\s*([\w+-]*)\s*$/.exec(line);
      if (fence) {
        var code = [];
        index++;
        while (index < lines.length && lines[index].trim().indexOf(fence[1]) !== 0) code.push(lines[index++]);
        index++;
        out.push("<pre><code>" + escapeHtml(code.join("\n")) + "</code></pre>");
        continue;
      }
      if (!line.trim()) { index++; continue; }
      var heading = /^(#{1,6})\s+(.*)$/.exec(line);
      if (heading) {
        var level = Math.min(heading[1].length + 2, 6);
        out.push("<h" + level + ">" + inline(heading[2]) + "</h" + level + ">");
        index++;
        continue;
      }
      if (/^\s*>/.test(line)) {
        var quoted = [];
        while (index < lines.length && /^\s*>/.test(lines[index])) quoted.push(lines[index++].replace(/^\s*>\s?/, ""));
        out.push("<blockquote>" + markdown(quoted.join("\n")) + "</blockquote>");
        continue;
      }
      var listItem = /^\s*([-*+]|\d+[.)])\s+/;
      if (listItem.test(line)) {
        var ordered = /^\s*\d/.test(line);
        var items = [];
        while (index < lines.length && (listItem.test(lines[index]) || (/^\s{2,}\S/.test(lines[index]) && items.length))) {
          if (listItem.test(lines[index])) items.push(lines[index].replace(listItem, ""));
          else items[items.length - 1] += " " + lines[index].trim();
          index++;
        }
        var tag = ordered ? "ol" : "ul";
        out.push("<" + tag + ">" + items.map(function (item) { return "<li>" + inline(item) + "</li>"; }).join("") + "</" + tag + ">");
        continue;
      }
      var paragraph = [];
      while (index < lines.length && lines[index].trim() && !/^(\s*(```|~~~)|#{1,6}\s|\s*>|\s*([-*+]|\d+[.)])\s+)/.test(lines[index])) {
        paragraph.push(lines[index++]);
      }
      if (!paragraph.length) paragraph.push(lines[index++]);
      out.push("<p>" + paragraph.map(inline).join("<br>") + "</p>");
    }
    return out.join("");
  }

  /* Inline Markdown on escaped text: code spans first, so nothing inside them
     is read as emphasis or a link. */
  function inline(text) {
    var spans = [];
    var held = escapeHtml(text).replace(/`([^`]+)`/g, function (match, code) {
      spans.push("<code>" + code + "</code>");
      return "\u0000" + (spans.length - 1) + "\u0000";
    });
    held = held
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
      .replace(/(^|[^_\w])_([^_\s][^_]*)_(?!\w)/g, "$1<em>$2</em>");
    held = linkify(held);
    return held.replace(/\u0000(\d+)\u0000/g, function (match, at) { return spans[Number(at)]; });
  }

  /* Bare web addresses become links, leaving those already inside an anchor. */
  function linkify(html) {
    return html.replace(/(<a\b[^>]*>.*?<\/a>)|(https?:\/\/[^\s<]+[^\s<.,;:!?)\]'"])/g, function (match, anchor, url) {
      if (anchor) return anchor;
      return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + "</a>";
    });
  }

  /* ========================================================= Comment menu === */
  /* The ⋯ overflow of a message: rewrite it, drop it, or drop the whole thread
     (offered on the first message, the one the thread hangs from). */
  var Menu = (function () {
    var open = null; /* { node, origin } */

    function button(thread, comment, isFirst) {
      var node = iconButton("more", "Actions du message", function () {
        if (open && open.origin === node) close(true);
        else show(thread, comment, isFirst, node);
      });
      node.classList.add("vr-message-actions");
      node.setAttribute("aria-haspopup", "menu");
      node.setAttribute("aria-expanded", "false");
      return node;
    }

    function show(thread, comment, isFirst, origin) {
      close(false);
      var menu = el("div", "vr-menu");
      menu.setAttribute("role", "menu");
      menu.setAttribute("aria-label", "Actions du message");
      menu.appendChild(item("rename", "Modifier", false, function () {
        state.editing = comment.id;
        paint();
        var field = document.getElementById("vr-edit-body");
        if (field) { field.focus(); field.setSelectionRange(field.value.length, field.value.length); }
      }));
      menu.appendChild(item("delete", "Supprimer le message", true, function () {
        if (thread.comments.length === 1 &&
            !confirm("C'est le seul message : le fil " + thread.id + " sera supprimé. Continuer ?")) return;
        Api.removeComment(thread.id, comment.id).catch(failed);
      }));
      if (isFirst && thread.comments.length > 1) {
        menu.appendChild(item("delete", "Supprimer le fil", true, function () {
          if (!confirm("Supprimer le fil " + thread.id + " et ses " + thread.comments.length + " messages ?")) return;
          Api.removeThread(thread.id).catch(failed);
        }));
      }
      document.body.appendChild(menu);
      open = { node: menu, origin: origin };
      origin.setAttribute("aria-expanded", "true");
      position(menu, origin);
      menu.addEventListener("keydown", traverse);
      menu.querySelector("button").focus();
    }

    function item(glyph, label, danger, run) {
      var node = el("button", danger ? "danger" : "");
      node.type = "button";
      node.setAttribute("role", "menuitem");
      node.tabIndex = -1;
      node.innerHTML = icon(glyph);
      node.appendChild(el("span", "", label));
      node.addEventListener("click", function () { close(false); run(); });
      return node;
    }

    function position(menu, origin) {
      var anchor = origin.getBoundingClientRect(), box = menu.getBoundingClientRect();
      menu.style.left = Math.max(8, Math.min(anchor.right - box.width, window.innerWidth - box.width - 8)) + "px";
      menu.style.top = Math.max(8, Math.min(anchor.bottom + 4, window.innerHeight - box.height - 8)) + "px";
    }

    function traverse(event) {
      var buttons = Array.prototype.slice.call(open.node.querySelectorAll("button"));
      var at = buttons.indexOf(document.activeElement);
      var next = { ArrowDown: (at + 1) % buttons.length, ArrowUp: (at + buttons.length - 1) % buttons.length,
                   Home: 0, End: buttons.length - 1 }[event.key];
      if (next !== undefined) { event.preventDefault(); buttons[next].focus(); }
      if (event.key === "Tab") { event.preventDefault(); close(true); }
    }

    function close(restoreFocus) {
      if (!open) return;
      var origin = open.origin;
      open.node.remove();
      open = null;
      origin.setAttribute("aria-expanded", "false");
      if (restoreFocus && origin.isConnected) origin.focus();
    }

    document.addEventListener("pointerdown", function (event) {
      if (open && !open.node.contains(event.target) && !open.origin.contains(event.target)) close(false);
    });
    window.addEventListener("resize", function () { close(false); });
    document.addEventListener("scroll", function (event) {
      if (open && !open.node.contains(event.target)) close(false);
    }, true);

    return { button: button, close: close, isOpen: function () { return Boolean(open); } };
  })();

  /* ============================================================ Composer === */
  /* The composer at the foot of the panel answers threads: Répondre on a card
     aims it at that thread. A new thread is written inline, at its passage
     (see Selection), so aimed at nothing the composer folds away behind a hint
     saying so. Each thread keeps its own reply draft while the page lives.
     Offline, it is the notice saying how to write instead. */
  var SUBMIT_LABEL = /Mac|iP(hone|ad|od)/.test(navigator.platform || "") ? "⌘↩" : "Ctrl+↩";

  var Composer = (function () {
    var drafts = {};
    var draftKey = null;

    function build() {
      var form = el("form", "vr-composer idle");
      form.setAttribute("aria-label", "Répondre à un fil");

      ui.replyChip = chip("Réponse à", "Annuler la réponse", function () { disarm(); focusField(); });
      ui.replyChip.classList.add("reply");

      var fieldWrap = el("div", "vr-composer-field");
      ui.field = el("textarea");
      describeAsProse(ui.field, "vr-composer-body");
      ui.field.rows = 3;
      ui.field.maxLength = 10000;
      ui.field.addEventListener("input", function () { saveDraft(); controls(); fit(); });
      fieldWrap.appendChild(ui.field);

      var bar = el("div", "vr-composer-controls");
      ui.composerHint = el("p", "vr-hint", "Sélectionne un passage du document pour le commenter.");
      ui.submit = el("button", "vr-primary");
      ui.submit.type = "submit";
      bar.appendChild(ui.composerHint);
      bar.appendChild(ui.submit);

      ui.offline = el("div", "vr-offline");
      ui.offline.innerHTML = "Lecture seule — le serveur de commentaires ne répond pas.<br>"
        + "Pour écrire : <code>visual-report serve</code> puis ouvre la page via "
        + "<code>http://127.0.0.1</code>.";

      form.appendChild(ui.replyChip);
      form.appendChild(fieldWrap);
      form.appendChild(bar);
      form.appendChild(ui.offline);
      form.addEventListener("submit", function (event) { event.preventDefault(); submit(); });
      bindSubmitShortcut(ui.field, form);
      return form;
    }

    function chip(caption, clearLabel, onClear) {
      var node = el("div", "vr-chip");
      var text = el("span", "vr-chip-text");
      text.appendChild(el("small", "", caption));
      text.appendChild(el("span", "vr-chip-quote"));
      var clear = iconButton("close", clearLabel, onClear);
      node.appendChild(text);
      node.appendChild(clear);
      node.hidden = true;
      return node;
    }

    function controls() {
      var form = ui.composer;
      var online = Boolean(state.api);
      var replying = Boolean(state.replyTo);
      form.classList.toggle("offline", !online);
      form.classList.toggle("idle", online && !replying);
      ui.offline.hidden = online;
      ui.composerHint.hidden = !online || replying;
      ui.replyChip.hidden = !online || !replying;
      if (replying) ui.replyChip.querySelector(".vr-chip-quote").textContent = replyLabel(findThread(state.replyTo));
      ui.field.placeholder = "Répondre…";
      ui.field.setAttribute("aria-label", ui.field.placeholder);
      ui.field.disabled = state.pending;
      ui.submit.textContent = "Répondre";
      ui.submit.title = "Répondre (" + SUBMIT_LABEL + ")";
      ui.submit.hidden = !replying;
      ui.submit.disabled = state.pending || !ui.field.value.trim();
    }

    function replyLabel(thread) {
      if (!thread) return "ce fil";
      var text = thread.anchor ? thread.anchor.quote : (thread.comments[0] || {}).body || "ce fil";
      return text.length > 80 ? text.slice(0, 80) + "…" : text;
    }

    /* The thread being replied to may have been resolved or deleted elsewhere. */
    function refresh() {
      if (state.replyTo) {
        var thread = findThread(state.replyTo);
        if (!thread || !thread.is_open) disarm();
      }
      controls();
    }

    /* The textarea grows with its lines, up to a cap past which it scrolls. */
    function fit() {
      ui.field.style.height = "auto";
      ui.field.style.height = Math.min(ui.field.scrollHeight, 200) + "px";
    }

    function retarget() {
      var key = state.replyTo || null;
      if (key === draftKey) return;
      if (draftKey) drafts[draftKey] = ui.field.value;
      draftKey = key;
      ui.field.value = key ? drafts[key] || "" : "";
      fit();
    }
    function saveDraft() { if (draftKey) drafts[draftKey] = ui.field.value; }
    function forgetDraft() { if (draftKey) delete drafts[draftKey]; }

    function replyTo(threadId) {
      state.replyTo = threadId;
      retarget();
      Panel.show(true);
      activate(threadId, { scrollDocument: true });
      paint();
      focusField();
    }

    function disarm() {
      state.replyTo = null;
      retarget();
      paint();
    }

    function focusField() {
      if (ui.field.offsetParent === null) return;
      ui.field.focus();
      ui.field.setSelectionRange(ui.field.value.length, ui.field.value.length);
    }

    function submit() {
      var body = ui.field.value.trim();
      if (state.pending || !body || !state.replyTo) return;
      state.pending = true;
      controls();
      Api.reply(state.replyTo, body).then(function () {
        forgetDraft();
        ui.field.value = "";
        state.pending = false;
        disarm();
      }).catch(function (error) {
        state.pending = false;
        controls();
        failed(error);
        focusField();
      });
    }

    return { build: build, refresh: refresh, replyTo: replyTo, disarm: disarm };
  })();

  /* Command+Enter (Control+Enter off Apple keyboards) sends the field's form. */
  function bindSubmitShortcut(field, form) {
    field.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" || !(event.metaKey || event.ctrlKey) || event.altKey || event.isComposing) return;
      event.preventDefault();
      form.requestSubmit();
    });
  }

  /* A comment field is free French prose, and every attribute says so.

     The stakes are iOS: when Safari cannot classify a field it guesses, and a
     wrong guess puts the AutoFill bar — password, credit card, address — over
     the keyboard. An anonymous control (no `name`, no `id`, no `autocomplete`)
     is exactly the input that guess is made about, so each field is named after
     the message it holds, declines autofill outright, and asks for the writing
     aids prose wants: sentence capitals, autocorrection and spellcheck. */
  function describeAsProse(field, id) {
    field.id = id;
    field.name = id;
    field.setAttribute("autocomplete", "off");
    field.setAttribute("autocorrect", "on");
    field.setAttribute("autocapitalize", "sentences");
    field.setAttribute("spellcheck", "true");
    field.setAttribute("inputmode", "text");
  }

  /* ===================================================== Inline composer === */
  /* A new thread is written where its passage is, not in the panel. A passage
     selected in the document raises the floating toolbar of selection-actions.js
     over it; its « Commenter » turns the toolbar, in place, into a composer for
     the passage. A figure's own Commenter button opens the same composer beside
     the button. While the composer is open its passage stays painted (a draft
     mark, `state.draft`) and the composer follows it through scrolling. Saved,
     the new thread becomes the active one, its passage emphasised right there;
     the panel stays as it was, and its badge counts the thread.

     Two input stories reach the toolbar. A mouse drag ends on `mouseup`, and
     the selection is final there. A finger has no such moment: iOS Safari builds
     and adjusts a selection through its own handles, which emit
     `selectionchange` and nothing else, so touch watches the selection itself
     and waits for it to stop moving.

     The tap that follows is the delicate part. Pressing the toolbar collapses a
     touch selection before the click is delivered, which is why the anchor is
     captured when the toolbar appears rather than read back in the click
     handler, and why a collapse right after a press on it is ignored. */
  var Selection = (function () {
    var SETTLE_MS = 250;
    var TAP_GRACE_MS = 1200;
    var surface = null;
    var offered = null;       /* the passage the toolbar would comment on */
    var origin = null;        /* the figure button an open figure composer sits beside */
    var touchInput = false;   /* the last pointer on the page was a finger */
    var settleTimer = null;
    var heldUntil = 0;        /* a press on the surface freezes selection handling */

    function actions() {
      if (!surface) {
        surface = window.vrSelectionActions({
          choose: choose,
          comment: save,
          closed: closed,
          dismissed: dismissed,
          bounds: bounds
        });
      }
      return surface;
    }

    function bind() {
      document.addEventListener("pointerdown", pointerdown, true);
      document.addEventListener("mouseup", function (event) {
        if (outsideDocument(event.target)) return;
        setTimeout(consider, 0);
      });
      document.addEventListener("keyup", function (event) {
        if (event.shiftKey && !typing(event.target)) consider();
      });
      document.addEventListener("keydown", function (event) {
        /* Tab after a keyboard selection moves focus onto the toolbar. */
        if (event.key !== "Tab" || event.shiftKey || typing(event.target) || !visible()) return;
        if (surface.contains(document.activeElement)) return;
        if (surface.focusToolbar()) event.preventDefault();
      });
      document.addEventListener("selectionchange", function () {
        if (touchInput) settle();
        else if (visible() && collapsed()) hide();
      });
      document.addEventListener("touchend", function (event) {
        if (!outsideDocument(event.target)) settle();
      }, { passive: true });
      window.addEventListener("scroll", moved, { passive: true, capture: true });
      window.addEventListener("resize", moved);
    }

    /* A press elsewhere puts the toolbar away, and an empty composer with it; a
       composer holding words stays until it is saved or cancelled. */
    function pointerdown(event) {
      touchInput = event.pointerType === "touch" || event.pointerType === "pen";
      if (surface && surface.contains(event.target)) { heldUntil = Date.now() + TAP_GRACE_MS; return; }
      if (composing() && !surface.text()) surface.cancel();
    }

    /* Handle drags fire `selectionchange` continuously; act on the last one only. */
    function settle() {
      if (settleTimer) clearTimeout(settleTimer);
      settleTimer = setTimeout(consider, SETTLE_MS);
    }

    function outsideDocument(target) {
      return ui.panel.contains(target) || Boolean(surface && surface.contains(target));
    }

    function collapsed() {
      var selection = window.getSelection();
      return !selection || selection.isCollapsed || !selection.rangeCount;
    }

    function consider() {
      if (Date.now() < heldUntil || composing()) return;
      /* Writing needs the server; offline, a passage has nowhere to go. */
      if (!state.api || collapsed()) return hide();
      var selection = window.getSelection();
      var range = selection.getRangeAt(0);
      var block = blockOf(range.commonAncestorContainer);
      var quote = selection.toString().trim();
      if (!block || quote.length < 3 || !block.closest("main")) return hide();
      offered = {
        block_index: parseInt(block.getAttribute("data-vr-block"), 10),
        quote: quote,
        prefix: contextBefore(block, range),
        suffix: contextAfter(block, range)
      };
      actions().offer(range.getBoundingClientRect(), touchInput);
    }

    function choose() {
      var passage = offered;
      if (!passage || !state.api) return hide();
      offered = null;
      heldUntil = 0;   /* the tap reached its action: selections count again */
      /* The finger's native callout stays over the page as long as the
         selection lives; the draft mark paints the passage from here on. */
      var selection = window.getSelection();
      if (selection) selection.removeAllRanges();
      start({ anchor: passage, label: null });
      surface.open(draftRect(), "passage");
    }

    /* A figure's button opens the composer beside it, in place of an empty
       composer, never of one holding words. */
    function figure(passage, button) {
      if (composing()) {
        if (surface.text()) return;
        surface.cancel();
      }
      hide();
      origin = button && button.isConnected ? button : null;
      start(passage);
      actions().open(draftRect(), "figure");
    }

    function start(draft) {
      state.draft = draft;
      Highlights.paint();
    }

    function save(body) {
      var known = state.threads.map(function (thread) { return thread.id; });
      return Api.openThread(state.draft.anchor, body)
        .then(function () { showCreated(known); return true; })
        .catch(function (error) { failed(error); return false; });
    }

    /* The server answers with every thread, not the one it created: the new
       thread is the one that was not there before. It becomes the active one,
       its passage or figure emphasised where the comment was written; an open
       panel brings its card into view. */
    function showCreated(known) {
      var created = state.threads.filter(function (thread) { return known.indexOf(thread.id) < 0; });
      if (created.length !== 1) return;
      state.filter = "open";
      state.active = created[0].id;
      paint();
      if (!Panel.isOpen()) return;
      var card = ui.threads.querySelector('[data-thread="' + cssEscape(created[0].id) + '"]');
      if (card) card.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

    /* Cancelling a figure's composer hands the focus back to its button. */
    function closed(reason) {
      var button = origin;
      state.draft = null;
      origin = null;
      Highlights.paint();
      if (reason === "cancel" && button && button.isConnected) button.focus({ preventScroll: true });
    }

    /* Escape on the toolbar drops the selection with it. */
    function dismissed() {
      offered = null;
      var selection = window.getSelection();
      if (selection) selection.removeAllRanges();
    }

    /* Where the composer's passage is on screen: the box around its painted
       lines, or the figure's button; null when it is scrolled out of view. */
    function draftRect() {
      var rects = [];
      if (origin && origin.isConnected) rects.push(origin.getBoundingClientRect());
      else if (state.draft) {
        document.querySelectorAll("mark.vr-draft").forEach(function (mark) {
          Array.prototype.forEach.call(mark.getClientRects(), function (rect) { rects.push(rect); });
        });
        var block = blockAt(state.draft.anchor.block_index);
        if (!rects.length && block) rects.push(block.getBoundingClientRect());
      }
      rects = rects.filter(function (rect) {
        return rect.width && rect.height && rect.bottom > 0 && rect.top < window.innerHeight;
      });
      if (!rects.length) return null;
      var box = {
        left: Math.min.apply(null, rects.map(function (rect) { return rect.left; })),
        top: Math.min.apply(null, rects.map(function (rect) { return rect.top; })),
        right: Math.max.apply(null, rects.map(function (rect) { return rect.right; })),
        bottom: Math.max.apply(null, rects.map(function (rect) { return rect.bottom; }))
      };
      box.width = box.right - box.left;
      box.height = box.bottom - box.top;
      return box;
    }

    /* The surface stays over the reading column, under the top bar. */
    function bounds() {
      var column = (document.querySelector(".reading") || document.body).getBoundingClientRect();
      var bar = document.querySelector(".reader-header");
      return {
        left: Math.max(0, column.left),
        right: Math.min(root.clientWidth, column.right),
        top: bar ? Math.max(0, bar.getBoundingClientRect().bottom) : 0
      };
    }

    /* An open composer follows its passage; the toolbar follows the selection. */
    function moved() {
      if (composing()) return surface.follow(draftRect());
      if (!visible()) return;
      if (collapsed()) return hide();
      var rect = window.getSelection().getRangeAt(0).getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > window.innerHeight) hide();
      else surface.offer(rect, touchInput);
    }

    function hide() { if (surface) surface.hide(); }
    function visible() { return Boolean(surface && surface.offered); }
    function composing() { return Boolean(surface && surface.composing); }

    return { bind: bind, hide: hide, visible: visible, figure: figure };
  })();

  function blockOf(node) {
    var element = node.nodeType === 1 ? node : node.parentElement;
    return element ? element.closest("[data-vr-block]") : null;
  }

  function contextBefore(block, range) {
    var before = document.createRange();
    before.selectNodeContents(block);
    try { before.setEnd(range.startContainer, range.startOffset); } catch (error) { return ""; }
    return before.toString().slice(-60);
  }

  function contextAfter(block, range) {
    var after = document.createRange();
    after.selectNodeContents(block);
    try { after.setStart(range.endContainer, range.endOffset); } catch (error) { return ""; }
    return after.toString().slice(0, 60);
  }

  /* ============================================================= Figures === */
  /* A figure's comment button (drawn by the document's own scripts) asks for a
     thread on its whole block through `vr-figure-comment`, with the block, a
     short label (« Tableau : … », « Diagramme »…) and the button itself, which
     the inline composer opens beside. */
  function bindFigureComments() {
    document.addEventListener("vr-figure-comment", function (event) {
      var detail = event.detail || {};
      var block = detail.block && detail.block.closest ? detail.block.closest("[data-vr-block]") : null;
      if (!block) return;
      if (!state.api) { Panel.show(true); return; }   /* the panel says why it cannot write */
      Selection.figure({
        anchor: { block_index: parseInt(block.getAttribute("data-vr-block"), 10), quote: "", prefix: "", suffix: "" },
        label: (detail.label || "").trim() || Figures.label(block)
      }, detail.origin);
    });
  }

  /* A thread on a whole block: an anchor whose quote is empty. */
  function wholeBlock(anchor) { return Boolean(anchor) && !String(anchor.quote || "").trim(); }

  function blockAt(index) { return document.querySelector('main [data-vr-block="' + index + '"]'); }

  /* The name of a figure as its card says it, read from the block itself, for a
     thread whose label was not stored. */
  var Figures = {
    label: function (block) {
      if (!block) return "Bloc entier";
      var caption = block.querySelector("figcaption, caption, .chart-title, .fig-title");
      var title = caption ? collapse(caption.textContent).trim() : "";
      var image = block.querySelector("img");
      var kind = block.querySelector("table") ? "Tableau"
        : block.querySelector(".mermaid") ? "Diagramme"
        : block.querySelector("canvas") ? "Graphique"
        : image ? "Image" : null;
      if (!title && image) title = (image.getAttribute("alt") || "").trim();
      if (!kind) return title ? "Bloc : " + title : "Bloc entier";
      return title ? kind + " : " + title : kind;
    }
  };

  /* ========================================================== Highlights === */
  /* Every thread marks its passage, resolved ones faintly, so the filter the
     panel happens to show never hides a passage someone commented on. The
     whole layer is unwrapped and painted again on every paint. */
  var Highlights = (function () {
    var MARK = "vr-anchor";
    var BLOCK = "vr-commented";
    /* A block commented as a whole figure; distinct from figure-actions.js's
       `vr-figure`, which marks every figure and must survive a repaint. */
    var FIGURE = "vr-commented-figure";
    /* The passage, or the figure, the inline composer is open on. */
    var DRAFT = "vr-draft";
    var DRAFT_FIGURE = "vr-draft-figure";
    /* What a click on a commented block must leave to its own handler. A
       table's width grip is there because the click that ends its drag lands
       on it. */
    var FIGURE_SURFACE = "a, button, input, textarea, summary, img, canvas, svg, .mermaid, th, .table-edge";

    function paint() {
      clear();
      state.threads.forEach(function (thread) {
        if (!thread.anchor || thread.state === "orphaned") return;
        var block = document.querySelector('main [data-vr-block="' + thread.anchor.block_index + '"]');
        if (!block) return;
        if (wholeBlock(thread.anchor)) return markFigure(block, thread);
        if (thread.state === "drifted") return flagBlock(block, thread);
        var quote = collapse(thread.anchor.quote).trim();
        var view = TextView.read(block);
        var start = quote ? locate(view, quote, thread.anchor) : -1;
        if (start < 0) return flagBlock(block, thread);
        wrapRange(view, start, start + quote.length, function (mark) {
          mark.className = MARK + (thread.is_open ? "" : " resolved");
          mark.setAttribute("data-thread", thread.id);
        });
      });
      paintDraft(state.draft);
      emphasise(state.active, false);
    }

    /* The passage the inline composer writes on stays painted while it is
       open, as the selection it came from would have been; a figure is
       outlined. */
    function paintDraft(draft) {
      if (!draft) return;
      var block = blockAt(draft.anchor.block_index);
      if (!block) return;
      if (wholeBlock(draft.anchor)) return block.classList.add(DRAFT_FIGURE);
      var quote = collapse(draft.anchor.quote).trim();
      var view = TextView.read(block);
      var start = locate(view, quote, draft.anchor);
      if (start >= 0) wrapRange(view, start, start + quote.length, function (mark) { mark.className = DRAFT; });
    }

    /* The index the quote starts at, or -1 when the block no longer holds it.
       The words just before and after it break the tie when the same words
       occur several times. They are compared without whitespace, since the
       selection they were cut from and this view of the block space block
       boundaries differently. */
    function locate(view, quote, anchor) {
      var hits = [];
      for (var at = view.text.indexOf(quote); at !== -1; at = view.text.indexOf(quote, at + 1)) hits.push(at);
      if (hits.length < 2) return hits.length ? hits[0] : -1;
      var prefix = squash(anchor.prefix).slice(-24), suffix = squash(anchor.suffix).slice(0, 24);
      var best = hits[0], bestScore = -1;
      hits.forEach(function (hit) {
        var score = (prefix && squash(view.text.slice(0, hit)).slice(-prefix.length) === prefix ? 2 : 0) +
          (suffix && squash(view.text.slice(hit + quote.length)).indexOf(suffix) === 0 ? 1 : 0);
        if (score > bestScore) { bestScore = score; best = hit; }
      });
      return best;
    }

    /* The character range [start, end) as one mark per text node or formula it
       crosses, each dressed by `dress`. Splitting a node never moves the nodes
       the later slices name. */
    function wrapRange(view, start, end, dress) {
      var slices = [], current = null;
      for (var index = start; index < end; index++) {
        var point = view.points[index];
        if (!current || current.node !== point.node) {
          current = { node: point.node, from: point.offset || 0, to: (point.offset || 0) + 1 };
          slices.push(current);
        } else current.to = point.offset + 1;
      }
      slices.forEach(function (slice) { wrapSlice(slice, dress); });
    }

    function wrapSlice(slice, dress) {
      var target = slice.node;
      if (target.nodeType === Node.TEXT_NODE) {
        if (slice.from > 0) target = target.splitText(slice.from);
        if (slice.to - slice.from < target.nodeValue.length) target.splitText(slice.to - slice.from);
      }
      var mark = document.createElement("mark");
      dress(mark);
      target.parentNode.insertBefore(mark, target);
      mark.appendChild(target);
    }

    /* A block whose text no longer holds the quote keeps a rule in its margin,
       so the discussion stays findable without a false passage. */
    function flagBlock(block, thread) {
      block.classList.add(BLOCK);
      if (!thread.is_open) block.classList.add("resolved");
      block.setAttribute("data-thread", thread.id);
    }

    /* A commented figure carries the margin rule and an outline, plus a marker
       in its corner: the figure's own surface (an image, a diagram, a table
       header) keeps its clicks for zooming and sorting, so the marker is where
       its threads are reached. Several threads on one figure share the marker,
       which steps through them. */
    function markFigure(block, thread) {
      flagBlock(block, thread);
      block.classList.add(FIGURE);
      var marker = block.querySelector(":scope > .vr-figure-marker");
      if (!marker) {
        marker = el("button", "vr-figure-marker");
        marker.type = "button";
        marker.innerHTML = icon("comments");
        marker.setAttribute("data-threads", "");
        marker.addEventListener("click", function (event) {
          event.stopPropagation();
          var ids = marker.getAttribute("data-threads").split(" ");
          openThread(ids[(ids.indexOf(state.active) + 1) % ids.length]);
        });
        block.insertBefore(marker, block.firstChild);
      }
      var ids = (marker.getAttribute("data-threads") + " " + thread.id).trim().split(" ");
      marker.setAttribute("data-threads", ids.join(" "));
      if (thread.is_open) marker.classList.add("open");
      var label = ids.length > 1 ? ids.length + " fils sur cette figure" : "Fil " + thread.id + " sur cette figure";
      marker.setAttribute("aria-label", label);
      marker.title = label;
    }

    function clear() {
      document.querySelectorAll(".vr-figure-marker").forEach(function (marker) { marker.remove(); });
      document.querySelectorAll("." + FIGURE + ", ." + DRAFT_FIGURE).forEach(function (block) {
        block.classList.remove(FIGURE, DRAFT_FIGURE);
      });
      document.querySelectorAll("mark." + MARK + ", mark." + DRAFT).forEach(function (mark) {
        var parent = mark.parentNode;
        while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
        parent.removeChild(mark);
        parent.normalize();
      });
      document.querySelectorAll("." + BLOCK).forEach(function (block) {
        block.classList.remove(BLOCK, "resolved", "active");
        block.removeAttribute("data-thread");
      });
    }

    function emphasise(id, scroll) {
      var first = null;
      document.querySelectorAll("mark." + MARK + ", ." + BLOCK).forEach(function (node) {
        var on = Boolean(id) && node.getAttribute("data-thread") === id;
        node.classList.toggle("active", on);
        if (on && !first) first = node;
      });
      document.querySelectorAll(".vr-figure-marker").forEach(function (marker) {
        var on = Boolean(id) && marker.getAttribute("data-threads").split(" ").indexOf(id) >= 0;
        marker.classList.toggle("active", on);
        if (on) marker.closest(".vr-commented").classList.add("active");
      });
      if (scroll && first) first.scrollIntoView({ block: "center", behavior: "smooth" });
    }

    /* A click on a highlight opens its thread; one anywhere else in the
       document puts the active thread down. Neither steals the click that ends
       a selection, nor one on a link or a control. */
    document.addEventListener("click", function (event) {
      var target = event.target.nodeType === 1 ? event.target : event.target.parentElement;
      if (!target || !target.closest("main") || target.closest(FIGURE_SURFACE)) return;
      if (!collapsedSelection()) return;
      var node = target.closest("mark." + MARK + ", ." + BLOCK);
      if (node) openThread(node.getAttribute("data-thread"));
    });

    function collapsedSelection() {
      var selection = window.getSelection();
      return !selection || selection.isCollapsed;
    }

    return { paint: paint, emphasise: emphasise };
  })();

  /* A block's text as a highlight reads it: the document's text nodes, the
     diff's deleted words and badges left out, whitespace collapsed, a space
     where a block-level element opens or closes, and typeset math read back as
     its TeX. Each character keeps the point it came from — a text node and
     offset, or a whole typeset formula. */
  var TextView = (function () {
    var SEPARATORS = {};
    ("ADDRESS ARTICLE ASIDE BLOCKQUOTE BR DD DIV DL DT FIGCAPTION FIGURE FOOTER H1 H2 H3 H4 H5 H6 " +
      "HEADER HR LI MAIN NAV OL P PRE SECTION TABLE TBODY TD TH THEAD TR UL").split(" ")
      .forEach(function (tag) { SEPARATORS[tag] = true; });
    var DIFF_ONLY = "del.vr-del, .vr-badge";

    function typesetSources() {
      var sources = new Map();
      try {
        var items = (window.MathJax && MathJax.startup && MathJax.startup.document &&
          MathJax.startup.document.math) || [];
        items.forEach(function (item) {
          if (item.typesetRoot) sources.set(item.typesetRoot, item.start.delim + item.math + item.end.delim);
        });
      } catch (error) { /* MathJax not loaded or not done: read the glyphs' text */ }
      return sources;
    }

    function read(block) {
      var math = typesetSources(), points = [], text = "", pendingSpace = false;
      function append(value, point) {
        for (var index = 0; index < value.length; index++) {
          if (/\s/.test(value[index])) { pendingSpace = text.length > 0; continue; }
          var at = point(index);
          if (pendingSpace) { text += " "; points.push(at); pendingSpace = false; }
          text += value[index];
          points.push(at);
        }
      }
      function walk(parent) {
        for (var node = parent.firstChild; node; node = node.nextSibling) {
          if (node.nodeType === Node.TEXT_NODE) {
            (function (textNode) { append(textNode.nodeValue, function (offset) { return { node: textNode, offset: offset }; }); })(node);
          } else if (node.nodeType !== Node.ELEMENT_NODE || node.namespaceURI === "http://www.w3.org/2000/svg" ||
                     node.matches(DIFF_ONLY)) {
            continue;
          } else if (math.has(node)) {
            (function (formula) { append(math.get(formula), function () { return { node: formula }; }); })(node);
          } else {
            var separator = SEPARATORS[node.tagName];
            if (separator) pendingSpace = text.length > 0;
            walk(node);
            if (separator) pendingSpace = text.length > 0;
          }
        }
      }
      walk(block);
      return { text: text, points: points };
    }

    return { read: read };
  })();

  /* =========================================================== Utilities === */
  var ICONS = {
    comments: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    reopen: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
    close: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    rename: '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
    "delete": '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
    bot: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>'
  };

  /* Lucide glyphs (ISC), stroked in the current colour and sized by CSS. */
  function icon(name) {
    return '<svg class="vr-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + ICONS[name] + "</svg>";
  }

  function iconButton(glyph, label, onClick) {
    var node = el("button", "vr-icon-button");
    node.type = "button";
    node.innerHTML = icon(glyph);
    node.setAttribute("aria-label", label);
    node.title = label;
    node.addEventListener("click", function (event) { event.stopPropagation(); onClick(); });
    return node;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  /* Disables `button` while `promise` runs; a refusal is said out loud. */
  function busy(button, promise) {
    button.disabled = true;
    promise.catch(failed).then(function () { button.disabled = false; });
  }

  function failed(error) { alert("Écriture impossible : " + error.message); }

  function escapeHtml(value) {
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function collapse(value) { return String(value == null ? "" : value).replace(/\s+/g, " "); }
  function squash(value) { return String(value == null ? "" : value).replace(/\s+/g, ""); }

  function cssEscape(value) {
    return window.CSS && CSS.escape ? CSS.escape(value) : String(value).replace(/["\\]/g, "\\$&");
  }

  /* « à l'instant », « il y a 5 min », « il y a 3 h », « hier », « il y a 4 j »,
     then the date itself. */
  function relativeTime(iso) {
    var when = new Date(iso);
    if (isNaN(when.getTime())) return "";
    var seconds = (Date.now() - when.getTime()) / 1000;
    if (seconds < 60) return "à l'instant";
    if (seconds < 3600) return "il y a " + Math.floor(seconds / 60) + " min";
    if (seconds < 86400) return "il y a " + Math.floor(seconds / 3600) + " h";
    var days = Math.floor(seconds / 86400);
    if (days === 1) return "hier";
    if (days < 7) return "il y a " + days + " j";
    var sameYear = when.getFullYear() === new Date().getFullYear();
    return when.toLocaleDateString("fr-FR", sameYear
      ? { day: "numeric", month: "short" }
      : { day: "numeric", month: "short", year: "numeric" });
  }

  if (document.readyState !== "loading") boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();

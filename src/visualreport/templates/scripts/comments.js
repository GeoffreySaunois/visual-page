/* The comment layer.

   Reading works everywhere: every page is rendered with its threads embedded, so
   a file opened by double-click still shows the whole exchange. Writing needs the
   local server — when the API does not answer, the panel says how to start it
   instead of pretending to save.

   Threads are anchored on a block index plus the quoted words. Highlights are
   recomputed from the text at load time rather than baked into the HTML, which is
   what lets a thread survive an edit: if the words moved inside the block we find
   them again, and if they are gone the block itself is flagged. */
(function () {
  "use strict";

  var POLL_MS = 4000;
  var AUTHOR_KINDS = { human: "Geoffrey", agent: "Claude" };

  var state = {
    documentId: "",
    threads: [],
    revision: 0,
    filter: "open",
    active: null,
    api: null,          /* base URL once the server answered, null when offline */
    draftAnchor: null,  /* the selection being commented on */
    replying: null,     /* the thread whose reply box is open */
    editing: null,      /* the comment being rewritten */
    menu: null          /* the comment whose ⋮ menu is open */
  };

  var panel = document.getElementById("vr-panel");
  var list = document.getElementById("vr-threads");
  var foot = document.getElementById("vr-foot");
  var bubble = document.getElementById("vr-bubble");
  var toggle = document.getElementById("comments-toggle");
  var counter = document.getElementById("comments-count");
  var root = document.documentElement;

  /* ------------------------------------------------------------- Bootstrap -- */
  function boot() {
    var seed = document.getElementById("vr-bootstrap");
    var data = seed ? JSON.parse(seed.textContent) : { threads: [] };
    state.documentId = data.document_id || "";
    state.threads = data.threads || [];
    state.revision = data.revision || 0;
    paint();
    probeApi();
    bindControls();
    bindSelection();
    setInterval(poll, POLL_MS);
  }

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

  /* ----------------------------------------------------------------- Writes -- */
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

  function openThread(anchor, body) {
    return send("/threads", "POST", { anchor: anchor, body: body });
  }
  function reply(threadId, body) {
    return send("/threads/" + threadId + "/comments", "POST", { body: body });
  }
  function editComment(threadId, commentId, body) {
    return send("/threads/" + threadId + "/comments/" + commentId, "PATCH", { body: body });
  }
  function removeComment(threadId, commentId) {
    return send("/threads/" + threadId + "/comments/" + commentId, "DELETE", null);
  }
  function resolve(threadId) { return send("/threads/" + threadId + "/resolve", "POST", null); }
  function reopen(threadId) { return send("/threads/" + threadId + "/reopen", "POST", null); }
  function remove(threadId) { return send("/threads/" + threadId, "DELETE", null); }

  /* ------------------------------------------------------------- Selection -- */
  function bindSelection() {
    document.addEventListener("mouseup", function (event) {
      if (panel.contains(event.target) || event.target === bubble) return;
      setTimeout(considerSelection, 0);
    });
    bubble.addEventListener("click", startDraft);
  }

  function considerSelection() {
    var selection = window.getSelection();
    if (!selection || selection.isCollapsed) return hideBubble();
    var range = selection.getRangeAt(0);
    var block = blockOf(range.commonAncestorContainer);
    var quote = selection.toString().trim();
    if (!block || quote.length < 3) return hideBubble();
    state.draftAnchor = {
      block_index: parseInt(block.getAttribute("data-vr-block"), 10),
      quote: quote,
      prefix: contextBefore(block, range),
      suffix: contextAfter(block, range)
    };
    showBubble(range);
  }

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

  function showBubble(range) {
    var box = range.getBoundingClientRect();
    bubble.style.left = (box.left + box.width / 2 + window.scrollX) + "px";
    bubble.style.top = (box.top + window.scrollY - 8) + "px";
    bubble.classList.add("visible");
  }
  function hideBubble() { bubble.classList.remove("visible"); }

  function startDraft() {
    hideBubble();
    openPanel();
    paint();
    var field = document.getElementById("vr-draft-body");
    if (field) field.focus();
  }

  /* ------------------------------------------------------------- Painting --- */
  function paint() {
    counter.textContent = String(state.threads.filter(function (t) { return t.is_open; }).length);
    list.innerHTML = "";
    if (state.draftAnchor) list.appendChild(draftCard());
    var shown = state.threads.filter(matchesFilter);
    if (!shown.length && !state.draftAnchor) list.appendChild(emptyNotice());
    shown.forEach(function (thread) { list.appendChild(threadCard(thread)); });
    foot.innerHTML = "";
    foot.appendChild(state.api ? documentComposer() : offlineNotice());
    highlight();
  }

  function matchesFilter(thread) {
    if (state.filter === "all") return true;
    return state.filter === "open" ? thread.is_open : !thread.is_open;
  }

  function emptyNotice() {
    var node = element("div", "vr-empty");
    node.textContent = state.filter === "resolved"
      ? "Aucun fil résolu."
      : "Aucun commentaire. Sélectionne un passage du document pour en ouvrir un.";
    return node;
  }

  function offlineNotice() {
    var node = element("div", "vr-offline");
    node.innerHTML = "Lecture seule — le serveur de commentaires ne répond pas.<br>"
      + "Pour écrire : <code>visual-report serve</code> puis ouvre la page via "
      + "<code>http://127.0.0.1</code>.";
    return node;
  }

  function threadCard(thread) {
    var card = element("div", "vr-thread" + (thread.is_open ? "" : " resolved")
      + (state.active === thread.id ? " active" : ""));
    card.setAttribute("data-thread", thread.id);
    card.appendChild(threadHead(thread));
    if (thread.anchor) card.appendChild(quoteOf(thread));
    thread.comments.forEach(function (comment, index) {
      card.appendChild(messageOf(thread, comment, index === 0));
    });
    if (state.replying === thread.id) card.appendChild(replyComposer(thread));
    card.appendChild(actionsOf(thread));
    card.addEventListener("click", function () { focusThread(thread.id, false); });
    return card;
  }

  function threadHead(thread) {
    var head = element("div", "vr-thread-head");
    head.appendChild(text(element("span", "vr-tid"), thread.id));
    if (thread.awaiting) {
      head.appendChild(text(element("span", "vr-chip " + thread.awaiting),
        "attend " + AUTHOR_KINDS[thread.awaiting]));
    }
    if (!thread.is_open) head.appendChild(text(element("span", "vr-chip done"), "résolu"));
    if (thread.state === "drifted") {
      head.appendChild(text(element("span", "vr-chip state"), "texte réécrit"));
    }
    if (thread.state === "orphaned") {
      head.appendChild(text(element("span", "vr-chip state"), "bloc disparu"));
    }
    if (thread.anchor && thread.anchor.section) {
      head.appendChild(text(element("span", "vr-section"), "§ " + thread.anchor.section));
    }
    return head;
  }

  function quoteOf(thread) {
    var quote = text(element("blockquote", "vr-quote"), "« " + thread.anchor.quote + " »");
    quote.addEventListener("click", function (event) {
      event.stopPropagation();
      focusThread(thread.id, true);
    });
    return quote;
  }

  function messageOf(thread, comment, isFirst) {
    var node = element("div", "vr-msg");
    var head = element("div", "vr-msg-head");
    head.appendChild(text(element("span", "vr-author " + comment.author.kind), comment.author.name));
    head.appendChild(text(element("span", "vr-time"), stamp(comment.created_at)));
    if (comment.edited_at) head.appendChild(text(element("span", "vr-edited"), "modifié"));
    if (state.api) head.appendChild(menuOf(thread, comment, isFirst));
    node.appendChild(head);
    if (state.editing === comment.id) {
      node.appendChild(editComposer(thread, comment));
      return node;
    }
    var body = element("div", "vr-body");
    body.innerHTML = inlineFormat(comment.body);
    node.appendChild(body);
    return node;
  }

  /* The ⋮ overflow of a message: rewrite it, drop it, or drop the whole thread
     (offered on the first message, the one the thread hangs from). */
  function menuOf(thread, comment, isFirst) {
    var wrap = element("div", "vr-menu");
    var opener = button("⋮", function () {
      state.menu = state.menu === comment.id ? null : comment.id;
      paint();
    });
    opener.className = "vr-menu-btn";
    opener.title = "Modifier ou supprimer";
    wrap.appendChild(opener);
    if (state.menu !== comment.id) return wrap;

    var items = element("div", "vr-menu-items");
    items.appendChild(button("Modifier", function () {
      state.menu = null;
      state.editing = comment.id;
      paint();
      var field = document.getElementById("vr-edit-body");
      if (field) { field.focus(); field.setSelectionRange(field.value.length, field.value.length); }
    }));
    items.appendChild(danger("Supprimer le message", function () {
      state.menu = null;
      if (thread.comments.length === 1) {
        if (!confirm("C'est le seul message : le fil " + thread.id + " sera supprimé. Continuer ?")) {
          return paint();
        }
      }
      removeComment(thread.id, comment.id);
    }));
    if (isFirst && thread.comments.length > 1) {
      items.appendChild(danger("Supprimer le fil", function () {
        state.menu = null;
        if (confirm("Supprimer le fil " + thread.id + " et ses " + thread.comments.length + " messages ?")) {
          remove(thread.id);
        } else {
          paint();
        }
      }));
    }
    wrap.appendChild(items);
    return wrap;
  }

  function editComposer(thread, comment) {
    return composer({
      placeholder: "Modifier le message…",
      value: comment.body,
      id: "vr-edit-body",
      label: "Enregistrer",
      onCancel: function () { state.editing = null; paint(); },
      submit: function (body) {
        state.editing = null;
        return editComment(thread.id, comment.id, body);
      }
    });
  }

  function actionsOf(thread) {
    var actions = element("div", "vr-actions");
    if (!state.api) return actions;
    if (thread.is_open && state.replying !== thread.id) {
      actions.appendChild(button("Répondre", function () {
        state.replying = thread.id;
        paint();
        var field = document.getElementById("vr-reply-body");
        if (field) field.focus();
      }));
    }
    if (thread.is_open) actions.appendChild(button("Résoudre", function () { resolve(thread.id); }));
    else actions.appendChild(button("Réouvrir", function () { reopen(thread.id); }));
    return actions;
  }

  function replyComposer(thread) {
    return composer({
      placeholder: "Répondre…",
      id: "vr-reply-body",
      onCancel: function () { state.replying = null; paint(); },
      submit: function (body) {
        state.replying = null;
        return reply(thread.id, body);
      }
    });
  }

  function documentComposer() {
    var wrap = element("div", "");
    wrap.appendChild(composer({
      placeholder: "Commenter le document…",
      submit: function (body) { return openThread(null, body); }
    }));
    return wrap;
  }

  function draftCard() {
    var card = element("div", "vr-thread active");
    var head = element("div", "vr-thread-head");
    head.appendChild(text(element("span", "vr-chip human"), "nouveau fil"));
    card.appendChild(head);
    card.appendChild(text(element("blockquote", "vr-quote"), "« " + state.draftAnchor.quote + " »"));
    card.appendChild(composer({
      placeholder: "Ton commentaire sur ce passage…",
      id: "vr-draft-body",
      onCancel: function () { state.draftAnchor = null; paint(); },
      submit: function (body) {
        var anchor = state.draftAnchor;
        state.draftAnchor = null;
        return openThread(anchor, body);
      }
    }));
    return card;
  }

  /* options: {placeholder, submit, id?, value?, label?, onCancel?} */
  function composer(options) {
    var wrap = element("div", "vr-composer");
    var field = document.createElement("textarea");
    field.placeholder = options.placeholder;
    if (options.id) field.id = options.id;
    if (options.value) field.value = options.value;
    var send = document.createElement("button");
    send.className = "vr-send";
    send.textContent = options.label || "Envoyer";

    function fire() {
      var body = field.value.trim();
      if (!body) return;
      send.disabled = true;
      options.submit(body).catch(function (error) {
        send.disabled = false;
        alert("Écriture impossible : " + error.message);
      });
    }
    send.addEventListener("click", function (event) { event.stopPropagation(); fire(); });
    field.addEventListener("click", function (event) { event.stopPropagation(); });
    field.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) fire();
      if (event.key === "Escape" && options.onCancel) { event.stopPropagation(); options.onCancel(); }
    });

    var row = element("div", "vr-composer-row");
    row.appendChild(text(element("span", "vr-hint"), "⌘⏎ pour envoyer"));
    if (options.onCancel) row.appendChild(button("Annuler", options.onCancel));
    row.appendChild(send);
    wrap.appendChild(field);
    wrap.appendChild(row);
    return wrap;
  }

  /* ------------------------------------------------------------ Highlights -- */
  function highlight() {
    document.querySelectorAll("mark.vr-anchor").forEach(unwrap);
    document.querySelectorAll(".vr-b.vr-drifted").forEach(function (block) {
      block.classList.remove("vr-drifted");
    });
    state.threads.filter(matchesFilter).forEach(function (thread) {
      if (!thread.anchor) return;
      var block = document.querySelector('[data-vr-block="' + thread.anchor.block_index + '"]');
      if (!block) return;
      if (thread.state === "anchored") markQuote(block, thread);
      else if (thread.state === "drifted") block.classList.add("vr-drifted");
    });
  }

  function markQuote(block, thread) {
    var found = locate(block, thread.anchor.quote);
    if (!found) return block.classList.add("vr-drifted");
    found.forEach(function (node) {
      var mark = document.createElement("mark");
      mark.className = "vr-anchor" + (thread.is_open ? "" : " resolved");
      mark.setAttribute("data-thread", thread.id);
      mark.addEventListener("click", function (event) {
        event.stopPropagation();
        openPanel();
        focusThread(thread.id, false);
      });
      node.parentNode.insertBefore(mark, node);
      mark.appendChild(node);
    });
  }

  /* Text nodes covering `quote` inside `block`, split so they cover exactly it.
     Whitespace is normalized on both sides, because the quote was captured from
     a rendered selection and the document may have been reflowed since. */
  function locate(block, quote) {
    var chunks = textChunks(block);
    var raw = chunks.map(function (chunk) { return chunk.node.nodeValue; }).join("");
    var flat = flatten(raw);
    var needle = flatten(quote).text.trim();
    if (!needle) return null;
    var at = flat.text.indexOf(needle);
    if (at < 0) return null;
    return sliceChunks(chunks, flat.map[at], flat.map[at + needle.length - 1] + 1);
  }

  function textChunks(block) {
    var walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    var chunks = [], offset = 0, node;
    while ((node = walker.nextNode())) {
      chunks.push({ node: node, start: offset });
      offset += node.nodeValue.length;
    }
    return chunks;
  }

  /* A whitespace-collapsed copy of `raw`, plus the raw index of each kept char. */
  function flatten(raw) {
    var out = "", map = [], previousWasSpace = false;
    for (var index = 0; index < raw.length; index++) {
      var character = raw[index];
      if (/\s/.test(character)) {
        if (!previousWasSpace && out.length) { out += " "; map.push(index); }
        previousWasSpace = true;
      } else {
        out += character; map.push(index); previousWasSpace = false;
      }
    }
    return { text: out, map: map };
  }

  function sliceChunks(chunks, from, to) {
    var pieces = [];
    chunks.forEach(function (chunk) {
      var length = chunk.node.nodeValue.length;
      var start = Math.max(from - chunk.start, 0);
      var end = Math.min(to - chunk.start, length);
      if (start >= end) return;
      var node = chunk.node;
      if (start > 0) node = node.splitText(start);
      if (end - start < node.nodeValue.length) node.splitText(end - start);
      pieces.push(node);
    });
    return pieces.length ? pieces : null;
  }

  function unwrap(mark) {
    var parent = mark.parentNode;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
    parent.normalize();
  }

  /* --------------------------------------------------------------- Controls -- */
  function bindControls() {
    toggle.addEventListener("click", function () {
      if (root.getAttribute("data-comments") === "open") closePanel();
      else openPanel();
    });
    panel.querySelector(".vr-close").addEventListener("click", closePanel);
    panel.querySelectorAll(".vr-filters button").forEach(function (item) {
      item.addEventListener("click", function () {
        state.filter = item.getAttribute("data-filter");
        panel.querySelectorAll(".vr-filters button").forEach(function (other) {
          other.setAttribute("aria-pressed", other === item ? "true" : "false");
        });
        paint();
      });
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      hideBubble();
      /* Escape backs out of the innermost thing first. */
      if (state.menu || state.editing) { state.menu = null; state.editing = null; return paint(); }
      closePanel();
    });
    document.addEventListener("click", function (event) {
      if (state.menu && !event.target.closest(".vr-menu")) { state.menu = null; paint(); }
    });
  }

  function openPanel() {
    root.setAttribute("data-comments", "open");
    toggle.setAttribute("aria-pressed", "true");
  }
  function closePanel() {
    root.removeAttribute("data-comments");
    toggle.setAttribute("aria-pressed", "false");
  }

  function focusThread(threadId, scroll) {
    state.active = threadId;
    document.querySelectorAll(".vr-thread").forEach(function (card) {
      card.classList.toggle("active", card.getAttribute("data-thread") === threadId);
    });
    document.querySelectorAll("mark.vr-anchor").forEach(function (mark) {
      mark.classList.toggle("active", mark.getAttribute("data-thread") === threadId);
    });
    if (!scroll) return;
    var target = document.querySelector('mark.vr-anchor[data-thread="' + threadId + '"]');
    if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  /* ----------------------------------------------------------------- Utils -- */
  function element(tag, className) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    return node;
  }
  function text(node, value) { node.textContent = value; return node; }
  function button(label, onClick) {
    var node = document.createElement("button");
    node.type = "button";
    node.textContent = label;
    node.addEventListener("click", function (event) { event.stopPropagation(); onClick(); });
    return node;
  }
  function danger(label, onClick) {
    var node = button(label, onClick);
    node.className = "danger";
    return node;
  }
  function escapeHtml(value) {
    return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  /* Comment bodies are plain text, with the two inline forms both participants
     actually type: `code` and **bold**. */
  function inlineFormat(body) {
    return escapeHtml(body)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  }
  function stamp(iso) {
    var when = new Date(iso);
    return when.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  if (document.readyState !== "loading") boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();

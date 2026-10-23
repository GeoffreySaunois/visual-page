/* The document's table of contents in the sidebar — Gym Lab's outline.

   Built from the document's own h2/h3 (the h1 is the title, already above):
   the shallowest headings are the sections, numbered unless the author already
   numbered them, and each holds its subsections behind a disclosure. Only the
   section being read shows its subsections; the others open on demand, and a
   section opened or closed by hand stays that way.

   The current entry follows Lab's reading line: the last heading whose top has
   crossed a quarter of the viewport — the first one while none has, and the
   last one once the page is scrolled to its end, since a short closing section
   never reaches the line by itself. */
(function () {
  "use strict";

  var READING_LINE = 0.25;
  var MAX_HEADINGS = 300;
  /* A heading that already opens on its own number ("1.", "2)", "IV.", "A —"). */
  var NUMBERED = /^\s*(\d+|[IVXLC]+|[A-Z])[.)\s—–-]/;

  var list = document.getElementById("toc");
  var section = list && list.closest(".sidebar-contents");
  if (!list || !section) return;

  /* --- Outline --------------------------------------------------------- */

  function headingNodes() {
    return Array.prototype.filter.call(
      document.querySelectorAll("main h2, main h3"),
      function (node) { return !node.closest(".vr-changelog, nav, aside, .doc-head"); }
    ).slice(0, MAX_HEADINGS);
  }

  /* The heading's words alone: no permalink glyph, no deleted diff words. */
  function headingText(node) {
    var copy = node.cloneNode(true);
    copy.querySelectorAll(".headerlink, del").forEach(function (extra) { extra.remove(); });
    return copy.textContent.replace(/\s+/g, " ").trim();
  }

  function entries(nodes) {
    return nodes.map(function (node, index) {
      if (!node.id) node.id = "vr-heading-" + index;
      return { id: node.id, text: headingText(node), level: Number(node.tagName[1]) };
    });
  }

  /* Sections are the shallowest headings; deeper ones nest under the section before them. */
  function sections(items) {
    var top = Math.min.apply(null, items.map(function (item) { return item.level; }));
    var groups = [];
    items.forEach(function (item) {
      if (item.level === top || !groups.length) groups.push({ heading: item, children: [] });
      else groups[groups.length - 1].children.push({ id: item.id, text: item.text, depth: Math.min(item.level - top, 2) });
    });
    var authored = groups.some(function (group) { return NUMBERED.test(group.heading.text); });
    groups.forEach(function (group, index) { group.number = authored ? null : String(index + 1); });
    return groups;
  }

  /* --- Markup ---------------------------------------------------------- */

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function headingLink(item, number) {
    var link = make("a", "contents-link");
    link.href = "#" + encodeURIComponent(item.id);
    link.dataset.headingId = item.id;
    link.title = item.text;
    if (number) {
      var label = make("span", "contents-number", number);
      label.setAttribute("aria-hidden", "true");
      link.appendChild(label);
    }
    link.appendChild(make("span", "contents-text", item.text));
    return link;
  }

  function sectionNode(group) {
    var node = make("div", "contents-section");
    node.dataset.sectionId = group.heading.id;
    var row = make("div", "contents-row");
    row.appendChild(headingLink(group.heading, group.number));
    node.appendChild(row);
    if (!group.children.length) return node;
    var disclosure = make("button", "contents-toggle");
    disclosure.type = "button";
    disclosure.dataset.sectionId = group.heading.id;
    disclosure.setAttribute("aria-label", "Sous-sections de " + group.heading.text);
    disclosure.innerHTML = '<svg class="icon" aria-hidden="true"><use href="#vr-i-chevron-right"></use></svg>';
    var children = make("div", "contents-children");
    group.children.forEach(function (child) {
      var link = headingLink(child, null);
      link.dataset.depth = String(child.depth);
      children.appendChild(link);
    });
    row.appendChild(disclosure);
    node.appendChild(children);
    return node;
  }

  /* --- State ----------------------------------------------------------- */

  var nodes = headingNodes();
  var current = null;
  var opened = {};
  var closed = {};

  function sectionOf(id) {
    if (!id) return null;
    var link = list.querySelector('.contents-link[data-heading-id="' + CSS.escape(id) + '"]');
    return link ? link.closest(".contents-section") : null;
  }
  function reading() {
    var node = sectionOf(current);
    return node ? node.dataset.sectionId : null;
  }
  function isOpen(id) { return Boolean(opened[id]) || (reading() === id && !closed[id]); }

  /* A section opened by hand stays open; the section being read is open unless closed by hand. */
  function toggle(id) {
    var wasOpen = isOpen(id);
    delete opened[id]; delete closed[id];
    if (wasOpen && reading() === id) closed[id] = true;
    else if (!wasOpen && reading() !== id) opened[id] = true;
    paint();
  }

  function paint() {
    var readingId = reading();
    list.querySelectorAll(".contents-section").forEach(function (node) {
      var id = node.dataset.sectionId;
      var open = isOpen(id);
      node.classList.toggle("is-reading", id === readingId);
      var disclosure = node.querySelector(".contents-toggle");
      if (disclosure) disclosure.setAttribute("aria-expanded", String(open));
      var children = node.querySelector(".contents-children");
      if (children) children.hidden = !open;
    });
    list.querySelectorAll(".contents-link").forEach(function (link) {
      if (link.dataset.headingId === current) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
  }

  /* Scrolls the outline alone to bring its current entry into view: unlike
     `scrollIntoView`, it never moves the page. */
  function revealCurrent() {
    var entry = list.querySelector('[aria-current="true"]');
    if (!entry) return;
    var box = entry.getBoundingClientRect(), frame = list.getBoundingClientRect();
    if (box.top < frame.top) list.scrollTop -= frame.top - box.top;
    else if (box.bottom > frame.bottom) list.scrollTop += box.bottom - frame.bottom;
  }

  function mark(id) {
    if (id === current) return;
    var leaving = reading();
    current = id;
    if (leaving !== reading() && leaving) delete closed[leaving];
    paint();
    revealCurrent();
  }

  /* --- Reading line ---------------------------------------------------- */

  function atDocumentEnd() {
    return window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2;
  }
  function currentHeading() {
    if (!nodes.length) return null;
    if (atDocumentEnd()) return nodes[nodes.length - 1];
    var line = window.innerHeight * READING_LINE;
    var found = nodes[0];
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].getBoundingClientRect().top <= line) found = nodes[i];
      else break;
    }
    return found;
  }

  var scheduled = false;
  /* A click's smooth scroll passes every heading on its way; until it settles,
     the entry the reader picked stays current. */
  var travellingTo = null;
  var travelTimer = null;
  function track() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      if (travellingTo) return;
      var node = currentHeading();
      mark(node ? node.id : null);
    });
  }
  function settle() {
    clearTimeout(travelTimer);
    travelTimer = setTimeout(function () { travellingTo = null; track(); }, 120);
  }

  function goTo(id) {
    var target = document.getElementById(id);
    if (!target) return;
    var smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    travellingTo = id;
    mark(id);
    target.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
    try { history.replaceState(null, "", "#" + encodeURIComponent(id)); } catch (error) { /* file:// in some browsers */ }
    settle();
  }

  /* --- Wiring ---------------------------------------------------------- */

  var outline = nodes.length ? sections(entries(nodes)) : [];
  outline.forEach(function (group) { list.appendChild(sectionNode(group)); });
  section.hidden = !outline.length;

  list.addEventListener("click", function (event) {
    var disclosure = event.target.closest(".contents-toggle");
    if (disclosure) { toggle(disclosure.dataset.sectionId); return; }
    var link = event.target.closest(".contents-link");
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    goTo(link.dataset.headingId);
  });

  window.addEventListener("scroll", function () { if (travellingTo) settle(); else track(); }, { passive: true });
  window.addEventListener("resize", track);
  window.addEventListener("load", track);
  paint();
  track();
})();

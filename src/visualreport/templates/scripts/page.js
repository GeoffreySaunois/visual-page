/* The document's own behavior: theming, the iteration toggle, reading progress,
   the mobile drawer, TOC scroll-spy and sortable tables. No dependencies. */
(function () {
  "use strict";

  /* --- Theme toggle: system → light → dark → system, persisted ------------- */
  var root = document.documentElement;
  var toggle = document.getElementById("theme-toggle");
  function applyThemeGlyph() {
    var t = root.getAttribute("data-theme") || "auto";
    var glyph = t === "light" ? "☀" : t === "dark" ? "☾" : "◐";
    var label = t === "light" ? "clair" : t === "dark" ? "sombre" : "système";
    if (toggle) { toggle.textContent = glyph; toggle.title = "Thème : " + label + " (cliquer pour changer)"; }
  }
  applyThemeGlyph();
  if (toggle) toggle.addEventListener("click", function () {
    var current = root.getAttribute("data-theme") || "auto";
    var next = current === "auto" ? "light" : current === "light" ? "dark" : "auto";
    root.setAttribute("data-theme", next);
    localStorage.setItem("vr-theme", next);
    applyThemeGlyph();
    document.dispatchEvent(new CustomEvent("vr-themechange"));
  });

  /* --- Diff show/hide: "on" reviews changes, "off" shows the final doc ----- */
  var diffToggle = document.getElementById("diff-toggle");
  function applyDiffGlyph() {
    var on = root.getAttribute("data-diff") !== "off";
    if (!diffToggle) return;
    diffToggle.setAttribute("aria-pressed", on ? "true" : "false");
    diffToggle.innerHTML = on ? "Diff <b>on</b>" : "Diff <b>off</b>";
    diffToggle.title = on ? "Changements affichés — cliquer pour la version finale"
                          : "Version finale — cliquer pour revoir les changements";
  }
  applyDiffGlyph();
  if (diffToggle) diffToggle.addEventListener("click", function () {
    var on = root.getAttribute("data-diff") !== "off";
    root.setAttribute("data-diff", on ? "off" : "on");
    localStorage.setItem("vr-diff", on ? "off" : "on");
    applyDiffGlyph();
  });

  /* --- Reading progress bar ------------------------------------------------ */
  var bar = document.getElementById("progress");
  function updateProgress() {
    var max = root.scrollHeight - root.clientHeight;
    if (bar) bar.style.width = (max > 0 ? (root.scrollTop / max) * 100 : 0) + "%";
  }
  window.addEventListener("scroll", updateProgress, { passive: true });

  /* --- Mobile drawer ------------------------------------------------------- */
  var sidebar = document.querySelector(".sidebar");
  var menuButton = document.querySelector(".menu-btn");
  if (menuButton && sidebar) menuButton.addEventListener("click", function () {
    sidebar.classList.toggle("open");
  });
  document.querySelectorAll(".sidebar nav a").forEach(function (link) {
    link.addEventListener("click", function () { if (sidebar) sidebar.classList.remove("open"); });
  });

  /* --- TOC scroll-spy ------------------------------------------------------ */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll("#toc a"));
  var linkById = {};
  tocLinks.forEach(function (link) {
    linkById[decodeURIComponent(link.getAttribute("href")).slice(1)] = link;
  });
  var headings = Array.prototype.filter.call(
    document.querySelectorAll("main h2[id], main h3[id]"),
    function (heading) { return linkById[heading.id]; }
  );
  function setActive(id) {
    tocLinks.forEach(function (link) { link.classList.remove("active"); });
    if (linkById[id]) linkById[id].classList.add("active");
  }
  function spy() {
    var line = 120; /* px from the viewport top counted as "current" */
    var current = null;
    for (var i = 0; i < headings.length; i++) {
      if (headings[i].getBoundingClientRect().top <= line) current = headings[i].id;
      else break;
    }
    if (current) setActive(current);
    else if (headings.length) setActive(headings[0].id);
  }
  window.addEventListener("scroll", spy, { passive: true });

  /* --- Sortable tables ----------------------------------------------------- */
  /* Diff tables are layout components, not data tables: no sorting, no wrap. */
  document.querySelectorAll("main table:not(.diff-table)").forEach(function (table) {
    var wrap = document.createElement("div");
    wrap.className = "tablewrap";
    table.parentNode.insertBefore(wrap, table);
    wrap.appendChild(table);
    /* Overflowing table → let it use the free margins before scrolling. */
    if (table.scrollWidth > wrap.clientWidth + 1) wrap.classList.add("wide");
    var headers = table.querySelectorAll("thead th");
    headers.forEach(function (header, column) {
      header.addEventListener("click", function () { sortBy(table, headers, header, column); });
    });
  });

  function sortBy(table, headers, header, column) {
    var body = table.querySelector("tbody");
    if (!body) return;
    var rows = Array.prototype.slice.call(body.querySelectorAll("tr"));
    var ascending = !header.classList.contains("sorted-asc");
    headers.forEach(function (other) { other.classList.remove("sorted-asc", "sorted-desc"); });
    header.classList.add(ascending ? "sorted-asc" : "sorted-desc");
    rows.sort(function (left, right) {
      var a = (left.children[column] || {}).textContent || "";
      var b = (right.children[column] || {}).textContent || "";
      var na = parseFloat(a.replace(",", ".")), nb = parseFloat(b.replace(",", "."));
      if (!isNaN(na) && !isNaN(nb)) return ascending ? na - nb : nb - na;
      return ascending ? a.localeCompare(b, "fr") : b.localeCompare(a, "fr");
    });
    rows.forEach(function (row) { body.appendChild(row); });
  }

  /* --- Filmstrip: arrow-key / click navigation through an image sequence --- */
  document.querySelectorAll(".filmstrip").forEach(function (strip) {
    var slides = Array.prototype.slice.call(strip.querySelectorAll(".filmstrip-slide"));
    var counter = strip.querySelector(".filmstrip-count");
    var current = 0;
    function show(index) {
      current = (index + slides.length) % slides.length;
      slides.forEach(function (slide, i) { slide.classList.toggle("is-active", i === current); });
      if (counter) counter.textContent = (current + 1) + " / " + slides.length;
    }
    var prev = strip.querySelector(".filmstrip-prev");
    var next = strip.querySelector(".filmstrip-next");
    if (prev) prev.addEventListener("click", function () { show(current - 1); });
    if (next) next.addEventListener("click", function () { show(current + 1); });
    strip.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft") { show(current - 1); event.preventDefault(); }
      else if (event.key === "ArrowRight") { show(current + 1); event.preventDefault(); }
    });
    strip.addEventListener("mouseenter", function () { strip.focus({ preventScroll: true }); });
  });

  document.addEventListener("DOMContentLoaded", function () { updateProgress(); spy(); });
  updateProgress(); spy();
})();

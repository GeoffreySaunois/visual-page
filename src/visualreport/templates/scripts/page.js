/* The document's own behavior: the iteration toggle, the PDF export and its
   print hooks, sortable tables and filmstrips. The frame around the document
   (appearance, sidebar, table of contents, tooltips) has its own scripts. */
(function () {
  "use strict";

  var root = document.documentElement;

  /* --- Diff show/hide: "on" reviews changes, "off" shows the final doc ----- */
  var diffToggle = document.getElementById("diff-toggle");
  function applyDiffState() {
    if (!diffToggle) return;
    var on = root.getAttribute("data-diff") !== "off";
    diffToggle.setAttribute("aria-pressed", on ? "true" : "false");
    diffToggle.setAttribute("data-tooltip", on
      ? "Changements affichés — cliquer pour la version finale"
      : "Version finale — cliquer pour revoir les changements");
  }
  applyDiffState();
  if (diffToggle) diffToggle.addEventListener("click", function () {
    var on = root.getAttribute("data-diff") !== "off";
    root.setAttribute("data-diff", on ? "off" : "on");
    try { localStorage.setItem("vr-diff", on ? "off" : "on"); }
    catch (error) { /* the choice still applies to this page */ }
    applyDiffState();
  });

  /* --- PDF export: the browser's print dialog over the print stylesheet ---- */
  var pdfButton = document.getElementById("pdf-export");
  if (pdfButton) pdfButton.addEventListener("click", function () { window.print(); });

  /* Paper has no gestures: a PDF must never hide half the document behind a
     collapsed annex, nor leave a stacked tab panel without the name of the tab
     it came from. Both are undone after printing, so the screen is untouched. */
  window.addEventListener("beforeprint", function () { openAnnexes(); titleTabs(); });
  window.addEventListener("afterprint", function () { closeAnnexes(); untitleTabs(); });

  var openedForPrint = [];
  function openAnnexes() {
    openedForPrint = Array.prototype.slice.call(
      document.querySelectorAll("main details:not([open])")
    );
    openedForPrint.forEach(function (details) { details.open = true; });
  }
  function closeAnnexes() {
    openedForPrint.forEach(function (details) { details.open = false; });
    openedForPrint = [];
  }

  /* The print stylesheet stacks every panel of a tab set and drops the label
     bar, which on paper points at nothing. Each panel therefore takes its own
     tab's title along — paired by index, the way the stylesheet pairs them. */
  function titleTabs() {
    document.querySelectorAll(".tabbed-set").forEach(function (set) {
      var labels = set.querySelectorAll(".tabbed-labels > label");
      var panels = set.querySelectorAll(".tabbed-content > .tabbed-block");
      panels.forEach(function (panel, index) {
        if (!labels[index] || panel.querySelector(".tabbed-print-title")) return;
        var title = document.createElement("div");
        title.className = "tabbed-print-title";
        title.textContent = labels[index].textContent;
        panel.insertBefore(title, panel.firstChild);
      });
    });
  }
  function untitleTabs() {
    document.querySelectorAll(".tabbed-print-title").forEach(function (title) {
      title.remove();
    });
  }

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

})();

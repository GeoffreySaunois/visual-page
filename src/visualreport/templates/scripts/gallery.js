/* The gallery's behavior: the directory on screen, the search, the order of
   the pages, and the previews.

   The hash is the current directory ("#/swaap/gym"), so a page's back arrow
   and breadcrumb open their own folder and the browser's back button climbs
   out of one. A path the gallery does not hold falls back to the root, so a
   stale bookmark still lands somewhere.

   A preview is the page itself in an iframe: sandboxed with no permission at
   all, so it runs no script — no comment polling, no API call, no theme
   write, no focus — and has an opaque origin with no storage. It is mounted
   only while its card is near the viewport and dropped once the card is far
   away, so a gallery of hundreds of pages holds a screenful of documents. */
(function () {
  "use strict";

  var MOUNT_MARGIN = "400px 0px";
  var UNMOUNT_MARGIN = "2000px 0px";

  var archive = document.getElementById("archive");
  var dirs = Array.prototype.slice.call(archive.querySelectorAll(".dir"));
  var byPath = {};
  dirs.forEach(function (dir) { byPath[dir.dataset.path] = dir; });
  var cards = Array.prototype.slice.call(archive.querySelectorAll(".page-card"));
  var search = document.getElementById("search");
  var searchSummary = document.getElementById("search-summary");
  var noResults = document.getElementById("no-results");
  var sorts = document.getElementById("sorts");
  var crumbs = document.getElementById("gallery-crumbs");
  var heading = document.getElementById("gallery-heading");
  var up = document.getElementById("gallery-up");
  var treeLinks = Array.prototype.slice.call(document.querySelectorAll(".tree-link"));

  /* --- The directory on screen ---------------------------------------- */

  function currentPath() {
    var path;
    try { path = decodeURIComponent(location.hash.replace(/^#\/?/, "")); }
    catch (error) { path = ""; }
    return Object.prototype.hasOwnProperty.call(byPath, path) ? path : "";
  }

  function ancestors(path) {
    if (!path) return [];
    var parts = path.split("/");
    var trail = [];
    for (var depth = 1; depth < parts.length; depth++) {
      var ancestor = parts.slice(0, depth).join("/");
      if (byPath[ancestor]) trail.push(ancestor);
    }
    return trail;
  }

  function link(path, label) {
    var anchor = document.createElement("a");
    anchor.href = "#/" + path;
    anchor.textContent = label;
    return anchor;
  }

  function separator() {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "icon crumb-separator");
    svg.setAttribute("aria-hidden", "true");
    var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", "#vr-i-chevron-right");
    svg.appendChild(use);
    return svg;
  }

  /* The top bar names the directory and links each of its ancestors, as a
     page's top bar does; the arrow climbs one level. */
  function paintHeader(path) {
    var label = path ? byPath[path].dataset.label : "Galerie";
    heading.textContent = label;
    document.title = path ? label + " · Galerie" : "Galerie";
    crumbs.textContent = "";
    crumbs.hidden = !path;
    up.hidden = !path;
    if (!path) return;
    var trail = [""].concat(ancestors(path));
    trail.forEach(function (ancestor, index) {
      if (index) crumbs.appendChild(separator());
      crumbs.appendChild(link(ancestor, ancestor ? byPath[ancestor].dataset.label : "Galerie"));
    });
    var parent = trail[trail.length - 1];
    up.href = "#/" + parent;
    up.setAttribute("aria-label", "Retour à " + (parent ? byPath[parent].dataset.label : "la galerie"));
  }

  function paintTree(path) {
    treeLinks.forEach(function (row) {
      if (row.dataset.path === path) row.setAttribute("aria-current", "page");
      else row.removeAttribute("aria-current");
    });
  }

  function showDirectory() {
    var path = currentPath();
    dirs.forEach(function (dir) { dir.hidden = dir.dataset.path !== path; });
    /* The order applies to pages: a directory of folders only has none to offer. */
    sorts.hidden = !byPath[path] || !byPath[path].querySelector(".page-card");
    paintHeader(path);
    paintTree(path);
    window.scrollTo(0, 0);
    measure();
  }

  /* --- Order ----------------------------------------------------------- */

  var comparators = {
    "date": function (a, b) { return b.dataset.date.localeCompare(a.dataset.date); },
    "date-asc": function (a, b) { return a.dataset.date.localeCompare(b.dataset.date); },
    "title": function (a, b) { return a.dataset.title.localeCompare(b.dataset.title, "fr"); }
  };

  /* Pages reorder inside each directory; folders keep the taxonomy's order. */
  function applySort(key) {
    archive.querySelectorAll(".cards.pages").forEach(function (grid) {
      Array.prototype.slice.call(grid.children).sort(comparators[key]).forEach(function (card) {
        grid.appendChild(card);
      });
    });
  }

  sorts.addEventListener("click", function (event) {
    var button = event.target.closest("button[data-sort]");
    if (!button) return;
    sorts.querySelectorAll("button").forEach(function (other) {
      other.setAttribute("aria-pressed", String(other === button));
    });
    applySort(button.dataset.sort);
  });

  /* --- Search ---------------------------------------------------------- */

  function applyFilter() {
    var query = search.value.trim().toLowerCase();
    document.body.classList.toggle("searching", Boolean(query));
    if (query) sorts.hidden = false;
    var visible = 0;
    cards.forEach(function (card) {
      var match = !query || card.dataset.text.indexOf(query) >= 0;
      card.classList.toggle("hidden", !match);
      if (match) visible++;
    });
    dirs.forEach(function (dir) {
      dir.classList.toggle("silent", !dir.querySelector(".page-card:not(.hidden)"));
    });
    searchSummary.hidden = !query;
    searchSummary.textContent = query ? visible + " page" + (visible === 1 ? "" : "s") + " dans toute la galerie" : "";
    noResults.hidden = !query || visible > 0;
    if (!query) showDirectory();
    else measure();
  }

  search.addEventListener("input", applyFilter);
  window.addEventListener("hashchange", function () { search.value = ""; applyFilter(); });

  /* --- Previews -------------------------------------------------------- */

  var mounted = new Set();

  function mount(slot) {
    if (mounted.has(slot)) return;
    var frame = document.createElement("iframe");
    frame.setAttribute("sandbox", "");
    frame.setAttribute("tabindex", "-1");
    frame.setAttribute("aria-hidden", "true");
    frame.setAttribute("title", "");
    frame.setAttribute("referrerpolicy", "no-referrer");
    frame.addEventListener("load", function () { frame.classList.add("loaded"); }, { once: true });
    frame.src = slot.dataset.preview;
    slot.appendChild(frame);
    mounted.add(slot);
  }

  function unmount(slot) {
    if (!mounted.has(slot)) return;
    var frame = slot.querySelector("iframe");
    if (frame) frame.remove();
    mounted.delete(slot);
  }

  var slots = archive.querySelectorAll("[data-preview]");
  if ("IntersectionObserver" in window) {
    var near = new IntersectionObserver(function (changes) {
      changes.forEach(function (change) { if (change.isIntersecting) mount(change.target); });
    }, { rootMargin: MOUNT_MARGIN });
    var far = new IntersectionObserver(function (changes) {
      changes.forEach(function (change) { if (!change.isIntersecting) unmount(change.target); });
    }, { rootMargin: UNMOUNT_MARGIN });
    slots.forEach(function (slot) { near.observe(slot); far.observe(slot); });
  }

  /* Every card has one width, so one scale fits every preview: read off the
     first preview on screen whenever the layout may have changed. */
  function measure() {
    var thumb = archive.querySelector(".dir:not([hidden]) .thumb, body.searching .dir:not(.silent) .thumb");
    if (!thumb || !thumb.clientWidth) return;
    var styles = getComputedStyle(document.documentElement);
    var cropWidth = parseFloat(styles.getPropertyValue("--crop-w"));
    var inset = parseFloat(styles.getPropertyValue("--sheet-inset"));
    archive.style.setProperty("--thumb-scale", String(thumb.clientWidth / cropWidth));
    archive.style.setProperty("--sheet-scale", String((thumb.clientWidth - 2 * inset) / cropWidth));
  }

  if ("ResizeObserver" in window) new ResizeObserver(measure).observe(archive);
  else window.addEventListener("resize", measure);

  showDirectory();
})();

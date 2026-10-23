/* The sidebar: collapsed to a rail and back on wide screens — a preference kept
   per viewer, which the head script restored before the first paint — and a
   drawer over the page on phones, opened from the top bar's menu button. */
(function () {
  "use strict";

  var STORAGE_KEY = "vr-sidebar";
  var COLLAPSED_CLASS = "sidebar-collapsed";
  var DRAWER_MEDIA = window.matchMedia("(max-width: 700px)");

  var root = document.documentElement;
  var sidebar = document.getElementById("sidebar");
  var collapseButton = document.getElementById("sidebar-collapse");
  var menuButton = document.getElementById("mobile-menu");
  var shade = document.getElementById("sidebar-shade");
  if (!sidebar) return;

  /* --- Collapse (wide screens) ----------------------------------------- */

  function collapsed() { return root.classList.contains(COLLAPSED_CLASS); }

  function labelCollapse() {
    if (!collapseButton) return;
    var label = collapsed() ? "Déplier la barre latérale" : "Replier la barre latérale";
    collapseButton.setAttribute("aria-label", label);
    collapseButton.setAttribute("aria-expanded", String(!collapsed()));
  }

  function setCollapsed(value) {
    root.classList.toggle(COLLAPSED_CLASS, value);
    try { localStorage.setItem(STORAGE_KEY, value ? "collapsed" : "expanded"); }
    catch (error) { /* the rail still holds for this page */ }
    labelCollapse();
  }

  if (collapseButton) collapseButton.addEventListener("click", function () { setCollapsed(!collapsed()); });
  labelCollapse();

  /* --- Drawer (phones) ------------------------------------------------- */

  function setDrawer(open) {
    sidebar.classList.toggle("open", open);
    if (shade) shade.hidden = !open;
    if (menuButton) menuButton.setAttribute("aria-expanded", String(open));
    if (open) {
      var first = sidebar.querySelector("a, button");
      if (first) first.focus({ preventScroll: true });
    }
  }

  if (menuButton) menuButton.addEventListener("click", function () { setDrawer(!sidebar.classList.contains("open")); });
  if (shade) shade.addEventListener("click", function () { setDrawer(false); });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && sidebar.classList.contains("open")) {
      setDrawer(false);
      if (menuButton) menuButton.focus({ preventScroll: true });
    }
  });
  /* A section picked in the drawer closes it, so the reader lands on the text. */
  sidebar.addEventListener("click", function (event) {
    if (DRAWER_MEDIA.matches && event.target.closest(".contents-link")) setDrawer(false);
  });
  DRAWER_MEDIA.addEventListener("change", function () { setDrawer(false); });
})();

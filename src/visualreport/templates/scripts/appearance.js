/* The page's appearance: a mode (auto / light / dark) that decides whether the
   dark tokens apply, and a palette (navy / violet / grey) that picks which dark
   canvas they paint — Gym Lab's two choices, persisted per viewer.

   The head script already wrote both on <html> before the first paint; this
   keeps them current, drives the top bar's appearance menu, and tells the
   page's other scripts through a `vr-theme-change` event on `document`
   (detail `{mode, resolved, palette}`) whenever what is on screen changes. */
(function () {
  "use strict";

  var MODE_KEY = "vr-theme";
  var PALETTE_KEY = "vr-palette";
  var MODES = ["auto", "light", "dark"];
  var PALETTES = ["navy", "violet", "grey"];
  var MODE_ICONS = { auto: "monitor", light: "sun", dark: "moon" };
  var MODE_NAMES = { auto: "système", light: "clair", dark: "sombre" };

  var root = document.documentElement;
  var darkMedia = window.matchMedia("(prefers-color-scheme: dark)");
  var mode = readStored(MODE_KEY, MODES, "auto");
  var palette = readStored(PALETTE_KEY, PALETTES, "navy");

  function readStored(key, allowed, fallback) {
    try {
      var value = localStorage.getItem(key);
      return allowed.indexOf(value) >= 0 ? value : fallback;
    } catch (error) { return fallback; }
  }
  function writeStored(key, value) {
    try { localStorage.setItem(key, value); }
    catch (error) { /* the choice still applies to this page */ }
  }

  function resolved() {
    return mode === "dark" || (mode === "auto" && darkMedia.matches) ? "dark" : "light";
  }

  function paint() {
    root.setAttribute("data-theme", mode);
    root.setAttribute("data-palette", palette);
    root.setAttribute("data-resolved-theme", resolved());
  }

  function announce() {
    document.dispatchEvent(new CustomEvent("vr-theme-change", {
      detail: { mode: mode, resolved: resolved(), palette: palette }
    }));
  }

  function refresh() { paint(); syncMenu(); announce(); }

  function setMode(next) {
    if (MODES.indexOf(next) < 0 || next === mode) return;
    mode = next; writeStored(MODE_KEY, mode); refresh();
  }
  function setPalette(next) {
    if (PALETTES.indexOf(next) < 0 || next === palette) return;
    palette = next; writeStored(PALETTE_KEY, palette); refresh();
  }

  /* --- The menu -------------------------------------------------------- */

  var toggle = document.getElementById("appearance-toggle");
  var menu = document.getElementById("appearance-menu");

  function syncMenu() {
    if (!menu || !toggle) return;
    menu.querySelectorAll("[data-theme-mode]").forEach(function (option) {
      option.setAttribute("aria-pressed", String(option.dataset.themeMode === mode));
    });
    menu.querySelectorAll("[data-theme-palette]").forEach(function (option) {
      option.setAttribute("aria-pressed", String(option.dataset.themePalette === palette));
    });
    toggle.querySelector("use").setAttribute("href", "#vr-i-" + MODE_ICONS[mode]);
    toggle.setAttribute("aria-label", "Apparence — thème " + MODE_NAMES[mode]);
  }

  function place() {
    var anchor = toggle.getBoundingClientRect();
    menu.style.top = Math.round(anchor.bottom + 6) + "px";
    menu.style.right = Math.max(8, Math.round(window.innerWidth - anchor.right)) + "px";
  }
  function isOpen() { return !menu.hidden; }
  function open() {
    menu.hidden = false; place();
    toggle.setAttribute("aria-expanded", "true");
    var current = menu.querySelector('[aria-pressed="true"]');
    if (current) current.focus({ preventScroll: true });
  }
  function close(returnFocus) {
    if (!isOpen()) return;
    menu.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    if (returnFocus) toggle.focus({ preventScroll: true });
  }

  if (toggle && menu) {
    toggle.addEventListener("click", function () { if (isOpen()) close(false); else open(); });
    menu.addEventListener("click", function (event) {
      var option = event.target.closest(".menu-option");
      if (!option) return;
      if (option.dataset.themeMode) setMode(option.dataset.themeMode);
      if (option.dataset.themePalette) setPalette(option.dataset.themePalette);
    });
    document.addEventListener("pointerdown", function (event) {
      if (isOpen() && !menu.contains(event.target) && !toggle.contains(event.target)) close(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && isOpen()) { close(true); event.stopPropagation(); }
    });
    window.addEventListener("resize", function () { if (isOpen()) place(); });
  }

  /* --- Outside changes ------------------------------------------------- */

  darkMedia.addEventListener("change", function () { if (mode === "auto") refresh(); });
  /* Another tab changed a choice, or cleared the store outright (key null). */
  window.addEventListener("storage", function (event) {
    if (event.key !== null && event.key !== MODE_KEY && event.key !== PALETTE_KEY) return;
    mode = readStored(MODE_KEY, MODES, "auto");
    palette = readStored(PALETTE_KEY, PALETTES, "navy");
    refresh();
  });

  paint();
  syncMenu();
})();

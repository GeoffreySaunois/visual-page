/* The chrome's hover label — Gym Lab's tooltip pill in place of the native
   `title`. A control names its label with `data-tooltip`; an icon-only control
   (an `aria-label` and no visible text) is labelled by its `aria-label`. An
   optional `data-tooltip-shortcut` ("C") renders as a key chip after it.

   One floating element, placed under the control (above it when the viewport
   has no room). It shows after a short hover or at once on keyboard focus, and
   leaves on pointer leave, blur, press, Escape and scroll. */
(function () {
  "use strict";

  var SHOW_DELAY_MS = 350;
  var GAP_PX = 6;
  var MARGIN_PX = 8;

  var pill = document.createElement("div");
  pill.className = "vr-tooltip";
  pill.setAttribute("role", "tooltip");
  pill.hidden = true;
  document.body.appendChild(pill);

  var anchor = null;
  var timer = null;

  function labelOf(element) {
    if (element.hasAttribute("data-tooltip")) return element.getAttribute("data-tooltip").trim();
    if (element.hasAttribute("aria-label") && !element.textContent.trim()) return element.getAttribute("aria-label").trim();
    return "";
  }

  function hostOf(node) {
    var element = node instanceof Element ? node : node && node.parentElement;
    var host = element && element.closest("[data-tooltip], button[aria-label], a[aria-label]");
    return host && labelOf(host) ? host : null;
  }

  function fill(element) {
    pill.textContent = labelOf(element);
    var shortcut = element.getAttribute("data-tooltip-shortcut");
    if (shortcut) {
      var chip = document.createElement("kbd");
      chip.className = "vr-tooltip-shortcut";
      chip.textContent = shortcut;
      pill.appendChild(chip);
    }
  }

  function place(element) {
    var box = element.getBoundingClientRect();
    var size = pill.getBoundingClientRect();
    var top = box.bottom + GAP_PX;
    if (top + size.height > window.innerHeight - MARGIN_PX) top = box.top - GAP_PX - size.height;
    var left = box.left + box.width / 2 - size.width / 2;
    left = Math.min(Math.max(MARGIN_PX, left), window.innerWidth - size.width - MARGIN_PX);
    pill.style.top = Math.round(top) + "px";
    pill.style.left = Math.round(left) + "px";
  }

  function show(element) {
    anchor = element;
    fill(element);
    pill.hidden = false;
    place(element);
    requestAnimationFrame(function () { if (anchor === element) pill.classList.add("visible"); });
  }

  function hide() {
    clearTimeout(timer);
    anchor = null;
    pill.classList.remove("visible");
    pill.hidden = true;
  }

  document.addEventListener("pointerover", function (event) {
    if (event.pointerType === "touch") return;
    var host = hostOf(event.target);
    if (host === anchor) return;
    hide();
    if (host) timer = setTimeout(function () { show(host); }, SHOW_DELAY_MS);
  });
  document.addEventListener("pointerout", function (event) {
    var host = hostOf(event.target);
    if (host && !host.contains(event.relatedTarget)) hide();
  });
  document.addEventListener("focusin", function (event) {
    var host = hostOf(event.target);
    if (host && host.matches(":focus-visible")) show(host);
  });
  document.addEventListener("focusout", hide);
  document.addEventListener("pointerdown", hide);
  document.addEventListener("keydown", function (event) { if (event.key === "Escape") hide(); });
  window.addEventListener("scroll", hide, { passive: true });
})();

/* A copy action on every code block. The async Clipboard API needs a secure
   context (an archived page opened from disk may not be one), so a refusal
   falls back to copying a detached textarea's selection. The button carries
   only an icon, no text, so the block text a comment quotes is unchanged. */
(function () {
  "use strict";
  /* Icons come from the page's sprite (templates/icons/sprite.svg). */
  function icon(name) { return '<svg class="icon" aria-hidden="true"><use href="#vr-i-' + name + '"></use></svg>'; }
  var LABELS = { idle: "Copier le code", copied: "Copié", failed: "Copie indisponible" };

  /* The code as it reads with the diff hidden: deleted words are left out. */
  function codeText(pre) {
    var clone = pre.cloneNode(true);
    clone.querySelectorAll("del.vr-del").forEach(function (node) { node.remove(); });
    return clone.textContent.replace(/\n$/, "");
  }

  function copyBySelection(text) {
    var area = document.createElement("textarea");
    area.value = text; area.setAttribute("readonly", "");
    area.style.cssText = "position:fixed;top:0;left:0;opacity:0;pointer-events:none";
    document.body.appendChild(area); area.select();
    var copied = document.execCommand("copy");
    area.remove();
    var selection = window.getSelection(); if (selection) selection.removeAllRanges();
    if (!copied) throw new Error("copy refused");
  }

  function copy(text) {
    if (!navigator.clipboard) return Promise.resolve().then(function () { copyBySelection(text); });
    return navigator.clipboard.writeText(text).catch(function () { copyBySelection(text); });
  }

  function show(button, state) {
    button.innerHTML = icon(state === "copied" ? "check" : "copy");
    if (state === "idle") delete button.dataset.state; else button.dataset.state = state;
    button.setAttribute("aria-label", LABELS[state]); button.title = LABELS[state];
  }

  function button(pre) {
    var node = document.createElement("button");
    node.type = "button"; node.className = "code-copy";
    show(node, "idle");
    var reset = 0;
    node.addEventListener("click", function () {
      clearTimeout(reset);
      copy(codeText(pre))
        .then(function () { show(node, "copied"); })
        .catch(function () { show(node, "failed"); })
        .then(function () { reset = setTimeout(function () { show(node, "idle"); }, 1500); });
    });
    return node;
  }

  function attach() {
    document.querySelectorAll("main .highlight > pre").forEach(function (pre) {
      pre.parentElement.appendChild(button(pre));
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", attach);
  else attach();
})();

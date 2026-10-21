/* Plain-text pastes into native text fields, inserted by the page on Chrome
   155–156 for macOS.

   Those versions skip their own insertion when the clipboard's sequence token
   changes during the `paste` event, and a race in Chrome's macOS clipboard
   gives one pasteboard change a second token when an app writes the
   pasteboard and sends ⌘V right after — which is how dictation apps (Wispr
   Flow) and text expanders insert text. The `paste` event still carries the
   text, but nothing lands in the field. Chromium fixed the race in
   crbug.com/568453825, shipping in Chrome 157: this script can go once
   155–156 are gone. */
(function () {
  "use strict";

  var version = /Chrome\/(\d+)\./.exec(navigator.userAgent);
  var affected = /Macintosh/.test(navigator.userAgent) && version && (version[1] === "155" || version[1] === "156");
  if (!affected || window.__vrNativePaste) return;
  window.__vrNativePaste = true;

  var TEXT_INPUTS = ["text", "search", "url", "tel", "email", "password"];

  function editableTextField(target) {
    var field = target instanceof HTMLTextAreaElement ||
      (target instanceof HTMLInputElement && TEXT_INPUTS.indexOf(target.type) !== -1);
    return field && !target.disabled && !target.readOnly;
  }

  /* The text to insert, or null to leave the paste to the browser: a paste
     another handler took, one carrying files, or one outside a text field. */
  function pastedText(event) {
    if (event.defaultPrevented || !editableTextField(event.target)) return null;
    var data = event.clipboardData;
    if (!data || Array.prototype.indexOf.call(data.types, "Files") !== -1) return null;
    return data.getData("text/plain") || null;
  }

  /* On window, in the bubbling phase: page handlers see the paste first. */
  window.addEventListener("paste", function (event) {
    var text = pastedText(event);
    if (text === null) return;
    event.preventDefault();
    var field = event.target;
    /* Setting the selection closes the typing in progress, so the paste is its own undo step. */
    field.setSelectionRange(field.selectionStart, field.selectionEnd, field.selectionDirection);
    /* execCommand keeps the insertion on the field's undo stack, like a native paste. */
    document.execCommand("insertText", false, text);
  });
})();

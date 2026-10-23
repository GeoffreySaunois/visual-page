/* The full-size view of a document figure: a picture (an image, a diagram or a
   chart drawn as one) or a table, letterboxed in a modal with Download (for a
   picture) and Close over its top-right corner and its caption beneath it.
   `figure-actions.js` decides which gestures open it, through
   `window.vrLightbox.open(medium, opener)`:

     medium = { src, alt, file }            a picture, with its download name
            | { table, alt }                a table, shown full size and scrollable
            + gallery: { images, index, onClose }   a filmstrip, browsed with ←/→

   The dialog lives inside <main>, so a table shown in it keeps the document's
   table styles, and outside any block, so nothing in it is commentable. Escape,
   the backdrop and Close all end in `close`, which hands the focus back to the
   element the lightbox was opened from. */
(function () {
  "use strict";
  /* Icons come from the page's sprite (templates/icons/sprite.svg). */
  function icon(name) { return '<svg class="icon" aria-hidden="true"><use href="#vr-i-' + name + '"></use></svg>'; }
  var dialog = null, opener = null, gallery = null;

  function build() {
    dialog = document.createElement("dialog");
    dialog.className = "media-lightbox"; dialog.tabIndex = -1;
    dialog.innerHTML = '<div class="media-lightbox-frame"><img class="media-lightbox-image" alt="">'
      + '<div class="media-lightbox-table" tabindex="0"></div>'
      + '<button class="media-lightbox-step media-lightbox-prev" type="button" aria-label="Image précédente" hidden>&#8249;</button>'
      + '<button class="media-lightbox-step media-lightbox-next" type="button" aria-label="Image suivante" hidden>&#8250;</button>'
      + '<div class="media-lightbox-actions">'
      + '<a class="media-lightbox-action media-lightbox-download" aria-label="Télécharger" title="Télécharger">' + icon("download") + '</a>'
      + '<button class="media-lightbox-action media-lightbox-close" type="button" aria-label="Fermer" title="Fermer">' + icon("x") + '</button>'
      + '</div></div><div class="media-lightbox-footer"><p class="media-lightbox-caption"></p>'
      + '<span class="media-lightbox-count" hidden></span></div>';
    /* The backdrop is the only click that reaches the dialog element itself. */
    dialog.addEventListener("click", function (event) { if (event.target === dialog) dialog.close(); });
    dialog.querySelector(".media-lightbox-close").addEventListener("click", function () { dialog.close(); });
    dialog.querySelector(".media-lightbox-prev").addEventListener("click", function () { step(-1); });
    dialog.querySelector(".media-lightbox-next").addEventListener("click", function () { step(1); });
    dialog.addEventListener("keydown", function (event) {
      var delta = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
      if (!gallery || !delta) return;
      event.preventDefault(); step(delta);
    });
    dialog.addEventListener("close", finish);
    (document.querySelector("main") || document.body).appendChild(dialog);
  }

  function finish() {
    dialog.querySelector(".media-lightbox-table").replaceChildren();
    if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    var shown = gallery;
    opener = null; gallery = null;
    if (shown && shown.onClose) shown.onClose(shown.index);
  }

  function fill(medium) {
    var view = dialog.querySelector(".media-lightbox-image");
    var table = dialog.querySelector(".media-lightbox-table");
    var download = dialog.querySelector(".media-lightbox-download");
    table.replaceChildren();
    if (medium.table) {
      view.hidden = true; view.removeAttribute("src");
      table.hidden = false; table.appendChild(medium.table);
      download.hidden = true;
    } else {
      table.hidden = true;
      view.hidden = false; view.src = medium.src; view.alt = medium.alt || "";
      download.hidden = false; download.href = medium.src; download.download = medium.file || "image";
    }
    dialog.classList.toggle("is-table", !!medium.table);
    var caption = dialog.querySelector(".media-lightbox-caption");
    caption.textContent = medium.alt || ""; caption.hidden = !medium.alt;
    dialog.setAttribute("aria-label", medium.alt || "Figure");
    var count = dialog.querySelector(".media-lightbox-count");
    count.hidden = !gallery;
    count.textContent = gallery ? (gallery.index + 1) + " / " + gallery.images.length : "";
    dialog.querySelectorAll(".media-lightbox-step").forEach(function (control) { control.hidden = !gallery; });
  }

  function step(delta) {
    var size = gallery.images.length;
    gallery.index = (gallery.index + delta + size) % size;
    fill(gallery.images[gallery.index]);
  }

  function open(medium, from) {
    if (!dialog) build();
    opener = from; gallery = medium.gallery || null;
    fill(medium);
    dialog.showModal();
    /* The dialog itself takes the focus, not its first action: Escape and the
       arrows work at once, and no focus ring lands on Download. */
    dialog.focus();
  }

  window.vrLightbox = { open: open };
})();

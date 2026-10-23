/* The two actions of a document figure — a table, a Mermaid diagram, a chart or
   an image: Comment and Show full size, a pair of icon buttons in the figure's
   top-right corner. They fade in while the figure is hovered or one of them is
   focused (they are real buttons, so Tab reaches them), stay visible on touch
   screens, and are left out on paper. The buttons hold no text, so the block
   text a comment quotes is unchanged.

   Comment does not talk to the comment layer: it dispatches
   `vr-figure-comment` on `document` with `{block, label}` — `block` the element
   carrying the block's `data-vr-block` address (document/anchors.py), `label` a
   short human name for the figure — and the comment layer opens its composer
   on that block.

   Show full size opens the lightbox (`lightbox.js`). An image or a diagram also
   opens on a plain click on it; a table and a chart only from the button, since
   a click on them belongs to them (sorting, a chart's legend). An image inside a
   link keeps the link, and a click that ends a selection keeps the selection:
   only a selection the press itself made counts, so a stale one never disables
   every figure of the page. A diagram or a chart is shown as a picture drawn
   larger than in the column, so the lightbox shows it big and sharp; a
   filmstrip frame opens with its whole filmstrip, which turns to the frame the
   lightbox closed on. */
(function () {
  "use strict";
  /* Icons come from the page's sprite (templates/icons/sprite.svg). */
  var ICONS = { comment: "message-square-plus", expand: "maximize-2" };
  function icon(name) { return '<svg class="icon" aria-hidden="true"><use href="#vr-i-' + name + '"></use></svg>'; }
  var BLOCK = "[data-vr-block]";
  /* The shown copy's size in multiples of its size in the column. */
  var ENLARGEMENT = 2;
  /* The margin around a diagram's copy, in diagram units, so its outer nodes
     keep clear of the lightbox's edge. */
  var DIAGRAM_MARGIN = 16;

  /* ---- What a figure is ---------------------------------------------------- */

  function text(element) { return element ? element.textContent.replace(/\s+/g, " ").trim() : ""; }
  function named(kind, name) { return name ? kind + " : " + name : kind; }

  /* A figure's kind, its label for the comment layer, and what it shows full size. */
  var KINDS = {
    table: {
      label: function (figure) {
        var cells = Array.prototype.slice.call(figure.querySelectorAll("thead th")).slice(0, 3).map(text).filter(Boolean);
        return named("Tableau", cells.join(" · "));
      },
      medium: function (figure) { return { table: tableCopy(figure.querySelector("table")), alt: KINDS.table.label(figure) }; }
    },
    diagram: {
      label: function (figure) { return named("Diagramme", text(figure.querySelector("figcaption"))); },
      medium: function (figure) {
        var svg = figure.querySelector(".mermaid svg");
        return svg && { src: diagramImage(svg), alt: KINDS.diagram.label(figure), file: "diagramme.svg" };
      }
    },
    chart: {
      label: function (figure) { return named("Graphique", text(figure.querySelector(".fig-head")) || text(figure.querySelector("figcaption"))); },
      medium: function (figure) {
        var src = chartImage(figure.querySelector("canvas"));
        return src && { src: src, alt: KINDS.chart.label(figure), file: "graphique.png" };
      }
    },
    image: {
      label: function (frame) { return named("Image", (frame.querySelector("img").alt || "").trim()); },
      medium: function (frame) { return withFilmstrip(frame.querySelector("img")); }
    }
  };

  /* ---- The action pair ------------------------------------------------------ */

  function actionButton(name, label) {
    var button = document.createElement("button");
    button.type = "button"; button.className = "figure-action figure-" + name;
    button.innerHTML = icon(ICONS[name]);
    button.setAttribute("aria-label", label); button.title = label;
    button.dataset.action = name;
    return button;
  }

  /* `figure` gets the pair; a table's reset joins it, so the corner holds one row. */
  function equip(figure, kind) {
    if (figure.querySelector(":scope > .figure-actions")) return;
    figure.classList.add("vr-figure"); figure.dataset.figure = kind;
    var actions = document.createElement("span");
    actions.className = "figure-actions";
    var reset = figure.querySelector(":scope > .table-reset");
    if (reset) actions.appendChild(reset);
    if (figure.closest(BLOCK)) actions.appendChild(actionButton("comment", "Commenter"));
    actions.appendChild(actionButton("expand", "Afficher en grand"));
    figure.appendChild(actions);
  }

  /* An image is wrapped so the pair sits in its own corner. */
  function frameImage(image) {
    var frame = document.createElement("span");
    frame.className = "media-image";
    image.parentNode.insertBefore(frame, image);
    frame.appendChild(image);
    return frame;
  }

  /* A static table (merged cells) is framed like an interactive one. */
  function tableFigure(table) {
    var figure = table.closest("figure.data-table, figure.table-frame");
    if (figure) return figure;
    var holder = table.parentElement.classList.contains("tablewrap") ? table.parentElement : table;
    figure = document.createElement("figure");
    figure.className = "table-frame";
    holder.parentNode.insertBefore(figure, holder);
    figure.appendChild(holder);
    return figure;
  }

  function attach() {
    document.querySelectorAll("main table:not(.diff-table)").forEach(function (table) {
      if (!table.closest(".media-lightbox")) equip(tableFigure(table), "table");
    });
    document.querySelectorAll("main .mermaid").forEach(function (diagram) {
      equip(diagram.closest("figure") || diagram.parentElement, "diagram");
    });
    document.querySelectorAll("main canvas").forEach(function (canvas) {
      equip(canvas.closest("figure") || canvas.parentElement, "chart");
    });
    document.querySelectorAll("main img:not(a img)").forEach(function (image) {
      equip(frameImage(image), "image");
    });
  }

  /* ---- The copies a figure is shown as ------------------------------------ */

  function base64(value) {
    var bytes = new TextEncoder().encode(value), binary = "";
    for (var at = 0; at < bytes.length; at += 0x8000)
      binary += String.fromCharCode.apply(null, bytes.subarray(at, at + 0x8000));
    return btoa(binary);
  }

  /* Mermaid writes the diagram's styles, labels included, into the SVG itself,
     so the copy draws the same outside the page; it only needs a margin and an
     intrinsic size. */
  function diagramImage(svg) {
    var box = svg.viewBox.baseVal;
    if (!box || !box.width) return null;
    var copy = svg.cloneNode(true);
    var width = box.width + 2 * DIAGRAM_MARGIN, height = box.height + 2 * DIAGRAM_MARGIN;
    copy.removeAttribute("style");
    copy.setAttribute("viewBox", (box.x - DIAGRAM_MARGIN) + " " + (box.y - DIAGRAM_MARGIN) + " " + width + " " + height);
    copy.setAttribute("width", Math.round(width * ENLARGEMENT));
    copy.setAttribute("height", Math.round(height * ENLARGEMENT));
    return "data:image/svg+xml;base64," + base64(new XMLSerializer().serializeToString(copy));
  }

  /* The chart redrawn at a higher pixel ratio for the copy, then back: same
     layout, more pixels, and nothing changes on screen. */
  function chartImage(canvas) {
    var chart = canvas && window.Chart && window.Chart.getChart(canvas);
    if (!chart) return null;
    var ratio = chart.options.devicePixelRatio, animation = chart.options.animation;
    chart.stop();
    chart.options.animation = false;
    chart.options.devicePixelRatio = ENLARGEMENT * Math.max(1, window.devicePixelRatio || 1);
    chart.resize();
    var url = chart.toBase64Image("image/png");
    chart.options.devicePixelRatio = ratio; chart.resize();
    chart.options.animation = animation;
    return url;
  }

  /* The table as the reader arranged it (order, sort), at its natural width:
     the column sizes, grips and focus stops of the interactive table stay
     behind. */
  function tableCopy(table) {
    var copy = table.cloneNode(true);
    copy.querySelectorAll("colgroup, .col-grip").forEach(function (node) { node.remove(); });
    copy.querySelectorAll("[tabindex]").forEach(function (node) { node.removeAttribute("tabindex"); });
    copy.removeAttribute("style");
    return copy;
  }

  /* ---- Filmstrips ------------------------------------------------------------ */

  function picture(image) {
    return { src: image.currentSrc || image.src, alt: image.alt, file: image.alt || "image" };
  }

  function withFilmstrip(image) {
    var strip = image.closest(".filmstrip");
    var medium = picture(image);
    if (!strip) return medium;
    var images = Array.prototype.slice.call(strip.querySelectorAll(".filmstrip-slide img"));
    medium.gallery = {
      images: images.map(picture), index: images.indexOf(image),
      onClose: function (index) { turnFilmstrip(strip, index); }
    };
    return medium;
  }

  /* The filmstrip turns to the frame the lightbox closed on, through its own
     buttons, so its counter and arrows carry on from there. */
  function turnFilmstrip(strip, index) {
    var slides = Array.prototype.slice.call(strip.querySelectorAll(".filmstrip-slide"));
    var current = slides.findIndex(function (slide) { return slide.classList.contains("is-active"); });
    var next = strip.querySelector(".filmstrip-next");
    for (var steps = (index - current + slides.length) % slides.length; steps > 0; steps--) if (next) next.click();
  }

  /* ---- Gestures ---------------------------------------------------------------- */

  function show(figure, from) {
    var medium = KINDS[figure.dataset.figure].medium(figure);
    if (medium && (medium.src || medium.table)) window.vrLightbox.open(medium, from);
  }

  function comment(figure) {
    var block = figure.closest(BLOCK);
    if (!block) return;
    document.dispatchEvent(new CustomEvent("vr-figure-comment", {
      detail: { block: block, label: KINDS[figure.dataset.figure].label(figure) }
    }));
  }

  function plainClick(event) {
    return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
  }

  /* Whether the selection moved since the pointer went down: a drag-select. */
  var selecting = false;
  document.addEventListener("pointerdown", function () { selecting = false; });
  document.addEventListener("selectionchange", function () { selecting = true; });

  document.addEventListener("click", function (event) {
    var element = event.target.nodeType === 1 ? event.target : event.target.parentElement;
    var figure = element && element.closest(".vr-figure");
    if (!figure || element.closest(".media-lightbox")) return;
    var action = element.closest(".figure-action");
    if (action) {
      event.stopPropagation();
      if (action.dataset.action === "comment") comment(figure); else show(figure, action);
      return;
    }
    var selection = window.getSelection();
    if (!plainClick(event) || (selecting && selection && !selection.isCollapsed)) return;
    var kind = figure.dataset.figure;
    if (kind === "image" || (kind === "diagram" && element.closest(".mermaid"))) show(figure, figure.querySelector(".figure-expand"));
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", attach);
  else attach();
})();

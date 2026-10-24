/* The floating surface over a commented passage — Gym Lab's selection actions
   with the one action a page offers, Commenter. It first shows a toolbar over
   the selected words; choosing Commenter turns it, in place, into a composer
   for the passage: a field that grows with its text and then scrolls, where
   Enter saves, Shift+Enter breaks the line (on a touch screen Enter breaks it
   and the button saves), and Escape or × cancels. A figure skips the toolbar:
   its own Commenter button opens the composer beside it.

   The surface knows nothing of passages or threads. Its owner (comments.js)
   reads the selection, says where the passage is on screen (`offer`, `open`,
   `follow`, as a viewport rectangle) and what the actions do, through
   `actions`:

   - `choose()` — Commenter was picked on the toolbar; the owner answers with
     `open(rect, subject)`, or leaves the surface hidden.
   - `comment(text)` — the composer was submitted; it resolves true once the
     comment is saved, which closes the composer, and false to keep it open
     with its text (a refused write).
   - `closed(reason)` — the composer closed, `done` or `cancel`.
   - `dismissed()` — Escape on the toolbar.
   - `bounds()` — the box `{left, right, top}` the surface stays in: a column's
     sides, and the bottom of the bar above it.

   The surface is added to the page the first time it is shown, and exposed as
   `window.vrSelectionActions(actions)`. */
(function () {
  "use strict";

  var EDGE = 8;
  /* The field grows with its text up to this height, then scrolls. */
  var FIELD_MAX_HEIGHT = 168;
  var SUBJECTS = {
    passage: { label: "Commentaire sur le texte sélectionné", placeholder: "Commenter ce passage…" },
    figure: { label: "Commentaire sur la figure", placeholder: "Commenter cette figure…" }
  };

  /* Enter alone saves and Shift+Enter breaks the line. A touch keyboard has no
     Shift+Enter, so there Enter breaks the line and the button saves. */
  function coarsePointer() {
    return Boolean(window.matchMedia && window.matchMedia("(pointer: coarse)").matches);
  }
  function savesOnEnter(event) {
    return event.key === "Enter" && !event.shiftKey && !event.isComposing && !coarsePointer();
  }

  function glyph(name) {
    return '<svg class="icon vr-sa-icon" aria-hidden="true" focusable="false"><use href="#vr-i-' + name + '"></use></svg>';
  }

  function markup() {
    return '<div class="vr-sa-toolbar" role="toolbar" aria-label="Texte sélectionné">'
      + '<button type="button" data-selection-action="comment">'
      + glyph("message-square-plus") + "<span>Commenter</span></button></div>"
      + '<form class="vr-sa-composer" hidden>'
      + '<textarea class="vr-sa-field" id="vr-inline-comment" name="vr-inline-comment" rows="1" maxlength="10000"'
      + ' autocomplete="off" autocorrect="on" autocapitalize="sentences" spellcheck="true" inputmode="text"></textarea>'
      + '<div class="vr-sa-buttons">'
      + '<button type="button" class="vr-sa-cancel" aria-label="Annuler" data-tooltip-shortcut="Esc">' + glyph("x") + "</button>"
      + '<button type="submit" class="vr-sa-submit" aria-label="Enregistrer le commentaire">' + glyph("check") + "</button>"
      + "</div></form>";
  }

  function SelectionActions(actions) {
    this.actions = actions;
    this.subject = null;     /* "passage" | "figure" while a composer is open */
    this.busy = false;
    this.anchor = null;      /* the rectangle the surface was last placed against */
    this.below = false;      /* a finger's selection: iOS draws its callout above */
    this.singleLine = 0;
    this.root = null;
  }

  SelectionActions.prototype = {
    /* The toolbar is on screen, waiting for its action. */
    get offered() { return Boolean(this.root && !this.root.hidden && !this.toolbar.hidden); },
    /* A composer is open, whatever its text. */
    get composing() { return this.subject !== null; },

    /* The open composer's text, trimmed. */
    text: function () { return this.field ? this.field.value.trim() : ""; },
    contains: function (node) { return Boolean(this.root && node && this.root.contains(node)); },

    mount: function () {
      if (this.root) return;
      this.root = document.createElement("div");
      this.root.className = "vr-selection-actions";
      this.root.hidden = true;
      this.root.innerHTML = markup();
      document.body.appendChild(this.root);
      this.toolbar = this.root.querySelector(".vr-sa-toolbar");
      this.button = this.toolbar.querySelector("button");
      this.form = this.root.querySelector("form");
      this.field = this.form.querySelector("textarea");
      this.submitButton = this.form.querySelector(".vr-sa-submit");
      this.listen();
    },

    listen: function () {
      var self = this;
      /* A mouse press on the toolbar must not take the selection away before its action runs. */
      this.toolbar.addEventListener("mousedown", function (event) { event.preventDefault(); });
      this.button.addEventListener("click", function () { self.actions.choose(); });
      this.button.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        event.preventDefault(); event.stopPropagation();
        self.root.hidden = true;
        self.actions.dismissed();
      });
      this.form.addEventListener("submit", function (event) { event.preventDefault(); self.submit(); });
      this.form.querySelector(".vr-sa-cancel").addEventListener("click", function () { self.cancel(); });
      this.field.addEventListener("input", function () { self.fit(); self.controls(); });
      this.field.addEventListener("keydown", function (event) { self.composerKey(event); });
    },

    /* Shows the toolbar beside the passage at `rect`; `below` keeps it under the
       passage, out of the way of a touch selection's native callout. */
    offer: function (rect, below) {
      if (this.composing) return;
      this.mount();
      this.below = Boolean(below);
      this.root.classList.toggle("touch", this.below);
      this.show(this.toolbar);
      this.position(rect);
    },

    /* Puts the toolbar away; an open composer stays. */
    hide: function () {
      if (this.composing || !this.root) return;
      this.root.hidden = true;
    },

    /* Moves focus onto the toolbar's action, for a selection made with the keyboard. */
    focusToolbar: function () {
      if (!this.offered) return false;
      this.button.focus({ preventScroll: true });
      return true;
    },

    /* Opens the composer on `subject` beside `rect`, its caret in the field. */
    open: function (rect, subject) {
      this.mount();
      var copy = SUBJECTS[subject];
      this.subject = subject;
      this.field.value = "";
      this.field.placeholder = copy.placeholder;
      this.field.setAttribute("aria-label", copy.label);
      this.submitButton.setAttribute("data-tooltip-shortcut", coarsePointer() ? "" : "↩");
      /* The passage's selection is gone by now, and the native callout with it. */
      this.below = false;
      this.root.classList.remove("touch");
      this.show(this.form);
      /* One line is measured without the padding a previous composer's lines left on the field. */
      this.form.classList.remove("multiline");
      this.field.style.height = "auto";
      this.singleLine = this.field.scrollHeight;
      this.fit();
      this.controls();
      this.position(rect || this.root.getBoundingClientRect());
      this.field.focus({ preventScroll: true });
    },

    /* Keeps an open composer beside its passage; a passage off screen leaves it where it was. */
    follow: function (rect) {
      if (this.composing && rect) this.position(rect);
    },

    composerKey: function (event) {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); this.cancel(); }
      else if (savesOnEnter(event) || (event.key === "Enter" && (event.metaKey || event.ctrlKey))) {
        event.preventDefault();
        this.submit();
      }
    },

    /* The field is as tall as its lines, up to a cap past which it scrolls. */
    fit: function () {
      var field = this.field;
      field.style.height = "auto";
      field.style.height = Math.min(field.scrollHeight, FIELD_MAX_HEIGHT) + "px";
      field.style.overflowY = field.scrollHeight > FIELD_MAX_HEIGHT ? "auto" : "hidden";
      this.form.classList.toggle("multiline", field.scrollHeight > this.singleLine + 2);
      if (this.composing && this.anchor) this.position(this.anchor);
    },

    controls: function () {
      this.submitButton.disabled = this.busy || !this.text();
      this.field.readOnly = this.busy;
      this.form.setAttribute("aria-busy", String(this.busy));
    },

    submit: function () {
      if (!this.composing || this.busy || this.submitButton.disabled) return;
      var self = this, subject = this.subject;
      this.busy = true;
      this.controls();
      Promise.resolve(this.actions.comment(this.text())).catch(function () { return false; }).then(function (done) {
        self.busy = false;
        if (self.subject !== subject) return;
        self.controls();
        if (done) self.close("done");
        else self.field.focus({ preventScroll: true });
      });
    },

    /* Abandons the open composer and its text. */
    cancel: function () {
      if (this.composing) this.close("cancel");
    },

    close: function (reason) {
      this.subject = null;
      this.anchor = null;
      this.field.blur();
      this.field.value = "";
      this.root.hidden = true;
      this.actions.closed(reason);
    },

    show: function (part) {
      this.toolbar.hidden = part !== this.toolbar;
      this.form.hidden = part !== this.form;
      this.root.hidden = false;
    },

    /* Centred over the passage, or below it when there is no room above (always
       below for a finger's toolbar), within the owner's bounds and the visible
       part of the viewport under them — the one a phone's keyboard leaves. `rect` encloses
       every line of the passage on screen, so the surface never sits between two
       of them. */
    position: function (rect) {
      this.anchor = rect;
      var bounds = this.actions.bounds();
      this.root.style.setProperty("--vr-sa-room", Math.max(0, bounds.right - bounds.left - 2 * EDGE) + "px");
      var box = this.root.getBoundingClientRect();
      var view = window.visualViewport;
      var viewTop = Math.max(view ? view.offsetTop : 0, bounds.top || 0);
      var viewBottom = view ? view.offsetTop + view.height : window.innerHeight;
      var left = Math.max(bounds.left + EDGE,
        Math.min(rect.left + rect.width / 2 - box.width / 2, bounds.right - box.width - EDGE));
      var above = !this.below && rect.top - viewTop >= box.height + 2 * EDGE;
      var top = above ? rect.top - box.height - EDGE : rect.bottom + EDGE;
      top = Math.max(viewTop + EDGE, Math.min(top, viewBottom - box.height - EDGE));
      this.root.style.left = Math.round(left) + "px";
      this.root.style.top = Math.round(top) + "px";
    }
  };

  window.vrSelectionActions = function (actions) { return new SelectionActions(actions); };
})();

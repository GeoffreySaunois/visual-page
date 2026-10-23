/* Interactive document tables: columns sized to their content, a table width
   the reader drags wider than the prose (it stays centred), column resize,
   sort, column reorder by dragging a header, and a reset to the authored
   layout. Tables with merged cells and diff tables keep their static rendering.

   A reader's layout is a convenience kept in this browser only: saved in
   localStorage under the document and the block the table belongs to, applied
   again on the next visit when the table still has exactly the same columns,
   and forgotten once it is back to the authored one. Storage may be refused (a
   private window, a file:// page under strict settings): the tables then keep
   their layout for the visit. */
(() => {
  const CELL_CAP = 320;      // a cell wider than this wraps instead of widening its column
  const WORD_CAP = 200;      // a longer unbreakable token may break rather than widen its column
  const HEADER_CAP = 180;    // a header never widens its column past this; it clamps to two lines
  const TEXT_MIN = 180;      // a column whose cells reach this wide on one line reads as prose
  const PROSE_FLOOR = 120;   // narrowest a prose column gets to let the table fit
  const LONG_FLOOR = 220;    // a column of paragraphs wraps anyway: it always yields down to this
  const CELL_PADDING = 28;
  const COL_MIN = 48;
  const TABLE_MIN = 320;
  const DRAG_THRESHOLD = 6;
  const SAVE_DELAY = 400;
  const MAX_SAVED_COLUMNS = 100;   // layouts are kept for tables up to this many columns
  const KEY_LENGTH = 190;          // a column key stays within 200 characters with its `#n` suffix
  const ROOM_GUTTER = 16;          // a widened table keeps this clear of the reading area's edges
  const EMPTY = /^(|—|–|-|n\/a|na|none)$/i;
  // A leading number: 1,234.5 · 1 362 052 · $42 · 113.1% · −57 ms — but not 10-02 or 18:40.
  const NUMBER = /^\s*[$€£]?\s*([+-]?(?:(?:\d{1,3}(?:[,   ]\d{3})+|\d+)(?:\.\d+)?|\.\d+))(?![\w.]|[-:/]\d)/;

  class DataTable {
    constructor(table, id, store) {
      this.table = table;
      this.id = id;
      this.store = store;
      this.columnCount = table.rows[0].cells.length;
      this.rows = Array.from(table.tBodies[0].rows);
      this.order = [...Array(this.columnCount).keys()];
      this.sort = null;
      this.build();
      this.alignNumbers();
      table.querySelectorAll('td code').forEach(breakAtSeparators);
      this.metrics = this.measure();
      this.fitHeaders();
      this.keys = this.columnKeys();
      this.overrides = new Map();   // column → width the reader set by hand
      this.width = null;
      this.apply(null);
    }

    /* ------------------------------------------------------------ DOM --- */
    build() {
      const figure = document.createElement('figure');
      figure.className = 'data-table';
      const scroller = document.createElement('div');
      scroller.className = 'tablewrap';
      this.table.replaceWith(figure);
      scroller.append(this.table);
      this.colgroup = document.createElement('colgroup');
      this.colgroup.append(...this.order.map(() => document.createElement('col')));
      this.table.prepend(this.colgroup);
      this.resetButton = this.button('table-reset', 'Rétablir la mise en page');
      this.resetButton.innerHTML = RESET_ICON;
      this.resetButton.addEventListener('click', () => this.reset());
      figure.append(this.resetButton, scroller, this.edge('left'), this.edge('right'));
      this.figure = figure;
      this.scroller = scroller;
      scroller.addEventListener('scroll', () => this.markOverflow(), { passive: true });
      this.headers().forEach((th, i) => this.armHeader(th, i));
    }

    button(className, label) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = className; b.title = label; b.hidden = true;
      b.setAttribute('aria-label', label);
      return b;
    }

    edge(side) {
      const grip = document.createElement('span');
      grip.className = `table-edge table-edge-${side}`;
      grip.title = 'Redimensionner · double-clic pour ajuster';
      grip.addEventListener('pointerdown', e => this.dragWidth(e, side === 'right' ? 1 : -1));
      grip.addEventListener('dblclick', () => { this.width = this.contentWidth(); this.render(); });
      return grip;
    }

    headers() { return Array.from(this.table.tHead.rows[0].cells); }

    /* A numeric column without an authored alignment reads right-aligned. */
    alignNumbers() {
      for (let c = 0; c < this.columnCount; c++) {
        const cells = [this.headers()[c], ...this.rows.map(r => r.cells[c])];
        if (cells.some(cell => cell.style.textAlign || cell.getAttribute('align'))) continue;
        if (!this.isNumeric(this.rows.map(r => cellText(r.cells[c])))) continue;
        cells.forEach(cell => cell.classList.add('num'));
      }
    }

    isNumeric(keys) {
      return keys.some(k => !EMPTY.test(k)) && keys.every(k => EMPTY.test(k) || NUMBER.test(normalize(k)));
    }

    /* ----------------------------------------------------- Measurement --- */
    /* Four offscreen passes give, per column, the widest cell on one line, its
       longest unbreakable word, and the same two for its header. */
    measure() {
      const bodyLine = this.offscreenWidths({ header: false, wrap: false });
      const bodyWord = this.offscreenWidths({ header: false, wrap: true });
      const headLine = this.offscreenWidths({ header: true, wrap: false });
      const headWord = this.offscreenWidths({ header: true, wrap: true });
      return bodyLine.map((line, c) => {
        const word = Math.min(bodyWord[c], WORD_CAP);
        const body = Math.max(Math.min(line, CELL_CAP), word);
        const header = Math.min(HEADER_CAP, Math.max(headWord[c], Math.ceil((headLine[c] - CELL_PADDING) / 2) + CELL_PADDING));
        const ideal = Math.max(COL_MIN, body, header);
        // Only prose wraps gracefully: numbers, dates and identifiers keep their line.
        const prose = line > TEXT_MIN && line > 1.5 * bodyWord[c];
        const floor = prose ? Math.min(ideal, Math.max(PROSE_FLOOR, word, headWord[c])) : ideal;
        const yields = line > CELL_CAP ? Math.min(ideal, Math.max(LONG_FLOOR, word, headWord[c])) : ideal;
        return { ideal, floor, yields, full: Math.max(COL_MIN, line, header) };
      });
    }

    /* Widens each column until its header holds in two lines, up to the header
       cap; past it the header ellipsizes. */
    fitHeaders() {
      const cols = Array.from(this.colgroup.children);
      const total = () => `${this.metrics.reduce((sum, x) => sum + x.ideal, 0)}px`;
      this.metrics.forEach((m, c) => { cols[c].style.width = `${m.ideal}px`; });
      this.table.style.width = total();
      this.headers().forEach((th, c) => {
        const label = th.querySelector('.th-label');
        const m = this.metrics[c];
        const unyielding = m.yields === m.ideal;
        while (truncated(label) && m.ideal < HEADER_CAP) {
          m.ideal += 6;
          cols[c].style.width = `${m.ideal}px`;
          this.table.style.width = total();
        }
        // A column that never yields keeps the width its header needs.
        if (unyielding) m.yields = m.ideal;
        m.floor = Math.min(m.floor, m.ideal);
        m.full = Math.max(m.full, m.ideal);
      });
    }

    offscreenWidths({ header, wrap }) {
      const clone = this.table.cloneNode(true);
      clone.querySelector('colgroup').remove();
      clone.style.cssText = `position:absolute;visibility:hidden;left:-99999px;top:0;table-layout:auto;width:${wrap ? '1px' : 'auto'}`;
      const [kept, emptied] = header ? ['th', 'td'] : ['td', 'th'];
      clone.querySelectorAll(emptied).forEach(cell => { cell.textContent = ''; });
      clone.querySelectorAll(kept).forEach(cell => {
        cell.style.whiteSpace = wrap ? 'normal' : 'nowrap';
        cell.style.overflowWrap = 'normal';
        cell.querySelectorAll('*').forEach(el => { el.style.whiteSpace = wrap ? 'normal' : 'nowrap'; el.style.overflowWrap = 'normal'; el.style.webkitLineClamp = 'none'; el.style.display = 'inline'; });
      });
      this.figure.append(clone);   // inside the figure, so it measures with the same type settings
      const widths = Array.from(clone.rows[0].cells, c => Math.ceil(c.getBoundingClientRect().width) + 1);
      clone.remove();
      return widths;
    }

    /* Column widths for a table of the given width, in two steps. Paragraph
       columns wrap at any width, so they always yield down to their floor
       first. Short prose (labels, pair names) wraps only when that makes the
       whole table fit: otherwise it would grow taller and still scroll. */
    columnWidths(available) {
      const ideal = this.metrics.map((m, c) => this.overrides.get(c) ?? m.ideal);
      const yields = this.metrics.map((m, c) => this.overrides.get(c) ?? m.yields);
      const paragraphs = shrink(ideal, yields, available);
      const floors = this.metrics.map((m, c) => this.overrides.get(c) ?? Math.min(m.floor, paragraphs[c]));
      return sum(floors) <= available ? shrink(paragraphs, floors, available) : paragraphs;
    }

    contentWidth() { return this.metrics.reduce((sum, m, c) => sum + (this.overrides.get(c) ?? m.ideal), 0); }
    proseWidth() { return innerWidth(this.figure.parentElement); }
    /* A table widens symmetrically into the free margins of the reading area,
       or up to its half of a two-column layout. */
    roomWidth() {
      const column = this.figure.closest('.cols .col');
      if (column) return innerWidth(column);
      const area = this.figure.closest('main')?.parentElement || document.body;
      const prose = innerBox(this.figure.parentElement), room = innerBox(area);
      const margin = Math.min(prose.left - room.left, room.right - prose.right) - ROOM_GUTTER;
      return prose.right - prose.left + 2 * Math.max(0, margin);
    }

    /* ---------------------------------------------------------- Render --- */
    render() {
      const prose = this.proseWidth();
      const width = this.width === null ? prose : clamp(this.width, Math.min(TABLE_MIN, prose), this.roomWidth());
      this.figure.style.width = `${width}px`;
      this.figure.style.marginLeft = `${(prose - width) / 2}px`;
      this.widths = this.columnWidths(width);
      Array.from(this.colgroup.children).forEach((col, i) => { col.style.width = `${this.widths[this.order[i]]}px`; });
      // Pixels, not max(100%, …): Safari ignores that on a fixed-layout table and squeezes every column.
      this.table.style.width = `${Math.max(width, this.widths.reduce((a, b) => a + b, 0))}px`;
      this.headers().forEach((th, i) => {
        const sorted = this.sort && this.sort.column === this.order[i];
        th.classList.toggle('sorted-asc', !!sorted && this.sort.direction === 1);
        th.classList.toggle('sorted-desc', !!sorted && this.sort.direction === -1);
        th.setAttribute('aria-sort', sorted ? (this.sort.direction === 1 ? 'ascending' : 'descending') : 'none');
      });
      this.resetButton.hidden = !this.modified();
      this.markOverflow();
      this.markTruncatedHeaders();
      this.scheduleSave();
    }

    /* ----------------------------------------------------- Persistence --- */
    /* Columns are addressed by their header, so a saved layout survives rows
       being added and drops only the columns the author removed. A header
       without text is addressed by its position. */
    columnKeys() {
      const seen = new Map();
      return this.headers().map((th, c) => {
        const text = cellText(th).toLowerCase().slice(0, KEY_LENGTH) || `#${c + 1}`;
        const n = (seen.get(text) || 0) + 1; seen.set(text, n);
        return n === 1 ? text : `${text}#${n}`;
      });
    }

    layout() {
      return {
        version: 1,
        columns: this.keys,
        width: this.width === null ? null : Math.round(this.width),
        widths: Object.fromEntries([...this.overrides].map(([c, w]) => [this.keys[c], Math.round(w)])),
        order: this.order.map(c => this.keys[c]),
        sort: this.sort && { column: this.keys[this.sort.column], direction: this.sort.direction },
      };
    }

    /* Shows the saved layout, or the authored one for `null`. The store holds
       it already, so it is not written back. */
    apply(saved) {
      this.clearLayout();
      if (saved) this.restore(saved);
      this.saved = JSON.stringify(this.modified() ? this.layout() : null);
      this.render();
    }

    /* Takes what it can use from a saved layout and ignores the rest. */
    restore(saved) {
      const column = key => this.keys.indexOf(key);
      this.width = Number.isFinite(saved.width) ? saved.width : null;
      this.keys.forEach((k, c) => { if (Number.isFinite(saved.widths?.[k]) && saved.widths[k] > 0) this.overrides.set(c, saved.widths[k]); });
      const known = Array.isArray(saved.order) ? saved.order.map(column).filter((c, i, all) => c >= 0 && all.indexOf(c) === i) : [];
      this.moveColumnsTo([...known, ...this.order.filter(c => !known.includes(c))]);
      const sorted = saved.sort ? column(saved.sort.column) : -1;
      this.sort = sorted >= 0 && [1, -1].includes(saved.sort.direction) ? { column: sorted, direction: saved.sort.direction } : null;
      this.applySort();
    }

    /* Saves the layout once the reader pauses, and only when it differs from
       the one the store holds, so a window resize writes nothing. */
    scheduleSave() {
      if (this.id === null) return;
      clearTimeout(this.saveTimer);
      this.saveTimer = setTimeout(() => {
        const layout = this.modified() ? this.layout() : null;
        const serialized = JSON.stringify(layout);
        if (serialized === this.saved) return;
        this.saved = serialized;
        this.store.save(this.id, layout);
      }, SAVE_DELAY);
    }

    /* A header clamped to two lines shows its full text on hover. */
    markTruncatedHeaders() {
      this.table.querySelectorAll('.th-label').forEach(label => {
        if (truncated(label)) label.title = label.textContent.trim();
        else label.removeAttribute('title');
      });
    }

    /* Shades the edge that hides columns, since overlay scrollbars stay invisible. */
    markOverflow() {
      const { scrollLeft, scrollWidth, clientWidth } = this.scroller;
      this.figure.classList.toggle('more-left', scrollLeft > 1);
      this.figure.classList.toggle('more-right', scrollLeft + clientWidth < scrollWidth - 1);
    }

    modified() {
      return this.width !== null || this.sort !== null
        || this.order.some((c, i) => c !== i) || this.overrides.size > 0;
    }

    clearLayout() {
      this.width = null; this.overrides.clear();
      this.sort = null; this.applySort();
      this.moveColumnsTo([...Array(this.columnCount).keys()]);
    }

    reset() {
      this.clearLayout();
      this.render();
    }

    /* ----------------------------------------------------- Table width --- */
    dragWidth(event, sign) {
      event.preventDefault();
      const start = event.clientX;
      const initial = this.figure.getBoundingClientRect().width;
      this.track(event, e => { this.width = initial + 2 * sign * (e.clientX - start); this.render(); });
    }

    /* ---------------------------------------------------------- Header --- */
    armHeader(th, initialIndex) {
      th.dataset.column = initialIndex;
      const grip = document.createElement('span');
      grip.className = 'col-grip';
      grip.title = 'Glisser pour redimensionner · double-clic pour ajuster';
      grip.addEventListener('pointerdown', e => this.dragColumn(e, +th.dataset.column));
      grip.addEventListener('dblclick', e => { e.stopPropagation(); this.fitColumn(+th.dataset.column); });
      grip.addEventListener('click', e => e.stopPropagation());
      const inner = document.createElement('div');
      inner.className = 'th-inner';
      const label = document.createElement('span');
      label.className = 'th-label';
      label.append(...th.childNodes);
      inner.append(label);
      // The label sits in a flex row, which an authored text-align does not move.
      const align = th.style.textAlign || th.getAttribute('align');
      if (align === 'right' || align === 'center') inner.style.justifyContent = align === 'right' ? 'flex-end' : 'center';
      th.append(inner, grip);
      th.tabIndex = 0;
      th.addEventListener('pointerdown', e => this.pressHeader(e, th));
      th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.cycleSort(+th.dataset.column); } });
    }

    dragColumn(event, column) {
      event.preventDefault(); event.stopPropagation();
      const start = event.clientX;
      const initial = this.widths[column];
      this.track(event, e => { this.overrides.set(column, Math.max(COL_MIN, initial + e.clientX - start)); this.render(); });
    }

    fitColumn(column) {
      this.overrides.set(column, this.metrics[column].full);
      this.render();
    }

    /* A press on a header is a sort when it ends where it started, and a
       column move once it travels past the threshold. */
    pressHeader(event, th) {
      if (event.button !== 0) return;
      const start = event.clientX;
      let moving = false;
      this.track(event, e => {
        if (!moving && Math.abs(e.clientX - start) < DRAG_THRESHOLD) return;
        if (!moving) { moving = true; this.figure.classList.add('reordering'); th.classList.add('moving'); }
        this.showDropTarget(this.dropIndex(e.clientX));
      }, e => {
        this.figure.classList.remove('reordering'); th.classList.remove('moving');
        this.showDropTarget(null);
        if (moving) this.moveColumn(this.headers().indexOf(th), this.dropIndex(e.clientX));
        else this.cycleSort(+th.dataset.column);
      });
    }

    dropIndex(x) {
      const edges = this.headers().map(h => { const r = h.getBoundingClientRect(); return r.left + r.width / 2; });
      return edges.filter(mid => x > mid).length;
    }

    showDropTarget(index) {
      this.headers().forEach((h, i) => {
        h.classList.toggle('drop-before', index === i);
        h.classList.toggle('drop-after', index === this.columnCount && i === this.columnCount - 1);
      });
    }

    moveColumn(from, to) {
      const order = [...this.order];
      const [column] = order.splice(from, 1);
      order.splice(to > from ? to - 1 : to, 0, column);
      this.moveColumnsTo(order);
      this.render();
    }

    moveColumnsTo(order) {
      for (const row of this.table.rows) {
        const byColumn = new Map(Array.from(row.cells, (cell, i) => [this.order[i], cell]));
        row.append(...order.map(c => byColumn.get(c)));
      }
      this.order = order;
    }

    /* ------------------------------------------------------------ Sort --- */
    cycleSort(column) {
      const same = this.sort && this.sort.column === column;
      this.sort = !same ? { column, direction: 1 } : this.sort.direction === 1 ? { column, direction: -1 } : null;
      this.applySort();
      this.render();
    }

    applySort() {
      const body = this.table.tBodies[0];
      if (!this.sort) { body.append(...this.rows); return; }
      const { column, direction } = this.sort;
      const keys = this.rows.map(row => cellText(row.cells[this.order.indexOf(column)]));
      const numeric = this.isNumeric(keys);
      const ranked = this.rows.map((row, i) => ({ row, i, key: keys[i] }));
      ranked.sort((a, b) => {
        const ea = EMPTY.test(a.key), eb = EMPTY.test(b.key);
        if (ea || eb) return ea === eb ? a.i - b.i : ea ? 1 : -1;   // blanks always last
        const c = numeric ? leadingNumber(a.key) - leadingNumber(b.key)
          : a.key.localeCompare(b.key, undefined, { numeric: true, sensitivity: 'base' });
        return c * direction || a.i - b.i;
      });
      body.append(...ranked.map(r => r.row));
    }

    /* --------------------------------------------------------- Pointer --- */
    track(event, move, end = () => {}) {
      const target = event.currentTarget;
      target.setPointerCapture(event.pointerId);
      document.body.classList.add('table-dragging');
      const up = e => {
        target.removeEventListener('pointermove', move);
        target.removeEventListener('pointerup', up);
        target.removeEventListener('pointercancel', up);
        document.body.classList.remove('table-dragging');
        end(e);
      };
      target.addEventListener('pointermove', move);
      target.addEventListener('pointerup', up);
      target.addEventListener('pointercancel', up);
    }
  }

  const RESET_ICON = '<svg class="icon" aria-hidden="true"><use href="#vr-i-rotate-ccw"></use></svg>';
  /* Lets a long identifier or path wrap after / _ . - rather than at any
     letter. <wbr> adds no text, so quotes and highlights read the same. */
  const breakAtSeparators = code => {
    if (code.textContent.length < 16) return;
    for (const node of Array.from(code.childNodes).filter(n => n.nodeType === Node.TEXT_NODE)) {
      const parts = node.textContent.split(/(?<=[\/_.\-:])(?=.)/);
      if (parts.length < 2) continue;
      node.replaceWith(...parts.flatMap((part, i) => (i ? [document.createElement('wbr'), part] : [part])));
    }
  };
  const sum = values => values.reduce((a, b) => a + b, 0);
  /* Takes the excess over `room` out of each width in proportion to its slack
     above its floor, never going below the floors. */
  const shrink = (widths, floors, room) => {
    const slack = sum(widths) - sum(floors);
    const ratio = slack > 0 ? clamp((sum(widths) - room) / slack, 0, 1) : 0;
    return widths.map((w, c) => w - (w - floors[c]) * ratio);
  };
  const innerBox = el => {
    const rect = el.getBoundingClientRect(), style = getComputedStyle(el);
    const left = rect.left + el.clientLeft + parseFloat(style.paddingLeft);
    return { left, right: left + innerWidth(el) };
  };
  const innerWidth = el => {
    const style = getComputedStyle(el);
    return el.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  };
  const truncated = el => el.scrollHeight > el.clientHeight + 1;
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  const normalize = s => s.replace(/[−–]/g, '-');
  const cellText = cell => cell.textContent.replace(/\s+/g, ' ').trim();
  const leadingNumber = s => parseFloat(normalize(s).match(NUMBER)[1].replace(/[,\u00a0\u202f ]/g, ''));

  /* A static table is framed like an interactive one (figure-actions.js puts
     its actions in the frame's corner) and scrolls rather than spill out. */
  const scrollable = table => {
    const figure = document.createElement('figure');
    figure.className = 'table-frame';
    const wrap = document.createElement('div');
    wrap.className = 'tablewrap';
    table.replaceWith(figure); wrap.append(table); figure.append(wrap);
  };

  const interactive = table => !table.classList.contains('diff-table') && table.tHead && table.tBodies.length === 1
    && !table.querySelector('[colspan],[rowspan]');

  /* The reader's layouts, in this browser's storage. Every access is guarded:
     storage can be missing or throw, and a page must render the same without. */
  const documentId = document.querySelector('meta[name="report-document"]')?.content || location.pathname;
  const store = {
    key(id) { return `vr-table:${documentId}:${id}`; },
    load(id) {
      try { const value = JSON.parse(localStorage.getItem(this.key(id)) || 'null'); return isObject(value) ? value : null; }
      catch { return null; }
    },
    save(id, layout) {
      try {
        if (layout === null) localStorage.removeItem(this.key(id));
        else localStorage.setItem(this.key(id), JSON.stringify(layout));
      } catch { /* storage refused: the layout lasts for the visit */ }
    },
  };

  /* A table is saved under the block it belongs to, suffixed `~2`, `~3` when
     the block holds several. A table outside any block is not saved. */
  const tableIds = tables => {
    const seen = new Map();
    return tables.map(table => {
      const block = table.closest('[data-vr-block]')?.dataset.vrBlock;
      if (!block || table.rows[0].cells.length > MAX_SAVED_COLUMNS) return null;
      const n = (seen.get(block) || 0) + 1; seen.set(block, n);
      return n === 1 ? block : `${block}~${n}`;
    });
  };

  /* A saved layout applies only to a table with exactly the columns it was
     saved for: a rewrite that moved blocks around must not dress one table in
     another's layout. */
  const savedLayout = table => {
    if (table.id === null) return null;
    const layout = store.load(table.id);
    return layout && JSON.stringify(layout.columns) === JSON.stringify(table.keys) ? layout : null;
  };
  const isObject = value => typeof value === 'object' && value !== null && !Array.isArray(value);

  const start = () => {
    const all = Array.from(document.querySelectorAll('main table:not(.diff-table)'));
    all.filter(t => !interactive(t)).forEach(scrollable);
    const found = all.filter(interactive);
    const ids = tableIds(found);
    const tables = found.map((t, i) => new DataTable(t, ids[i], store));
    tables.forEach(t => { const layout = savedLayout(t); if (layout) t.apply(layout); });
    followRoom(tables);
  };

  /* A table's measure and the margins it may widen into change without the
     window resizing: the comments panel opening, closing or being dragged
     narrows the reading area, the sidebar collapses, a commented block gains
     its left rule. Every table renders again whenever the reading area or a
     table's own container changes width. */
  const followRoom = tables => {
    if (!tables.length) return;
    if (typeof ResizeObserver !== 'function') {
      addEventListener('resize', () => tables.forEach(t => t.render()));
      return;
    }
    const widths = new Map();
    let frame = 0;
    const observer = new ResizeObserver(entries => {
      const changed = entries.filter(e => {
        const width = e.contentRect.width;
        if (widths.get(e.target) === width) return false;
        widths.set(e.target, width);
        return true;
      });
      if (!changed.length || frame) return;
      frame = requestAnimationFrame(() => { frame = 0; tables.forEach(t => t.render()); });
    });
    const area = document.querySelector('main')?.parentElement;
    if (area) observer.observe(area);
    new Set(tables.map(t => t.figure.parentElement)).forEach(parent => observer.observe(parent));
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();

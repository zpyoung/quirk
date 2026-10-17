/*
 * quirk-kit: the component kit's runtime. One classic-script IIFE, so it works as an inline
 * <script> and as a side-effect import. It exposes nothing on window and defines elements only
 * through define(), which never redefines a tag that is already registered.
 *
 * Helpers every element builds on: define, whenReady, token, onTheme, bindData, readTable.
 * Elements so far: q-tabs, q-timeline, q-code, q-stat, q-table, q-chart, q-diff, q-diff-note, q-board,
 * q-sidenote, q-compare, q-flow. q-grid and q-panel are CSS only.
 */
(function () {
  'use strict';

  var themeWatchers = new WeakMap();
  var dataBindings = new WeakMap();

  function define(tag, cls) {
    if (typeof customElements === 'undefined' || customElements.get(tag)) {
      return;
    }
    customElements.define(tag, cls);
  }

  function whenReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () { fn(); }, { once: true });
    } else {
      fn();
    }
  }

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue('--q-' + name).trim();
  }

  function nextFrame(fn) {
    if (typeof requestAnimationFrame === 'function') {
      return requestAnimationFrame(fn);
    }
    return setTimeout(fn, 16);
  }

  function cancelFrame(handle) {
    if (typeof cancelAnimationFrame === 'function') {
      cancelAnimationFrame(handle);
    } else {
      clearTimeout(handle);
    }
  }

  /**
   * Calls fn, at most once per animation frame, whenever the effective theme may have changed
   * while el is connected: a quirk-theme event on document, a data-theme or class change on
   * <html>, or a prefers-color-scheme change. Returns a function that removes every listener;
   * call it from disconnectedCallback. Calling onTheme again for the same el replaces the
   * earlier registration, so a moved element never stacks listeners.
   */
  function onTheme(el, fn) {
    var previous = themeWatchers.get(el);
    if (previous) {
      previous();
    }

    var frame = 0;
    var stopped = false;
    var observer = null;
    var media = null;

    function stop() {
      if (stopped) {
        return;
      }
      stopped = true;
      if (frame) {
        cancelFrame(frame);
        frame = 0;
      }
      document.removeEventListener('quirk-theme', schedule);
      if (observer) {
        observer.disconnect();
      }
      if (media) {
        if (media.removeEventListener) {
          media.removeEventListener('change', schedule);
        } else if (media.removeListener) {
          media.removeListener(schedule);
        }
      }
      if (themeWatchers.get(el) === stop) {
        themeWatchers.delete(el);
      }
    }

    function run() {
      frame = 0;
      if (stopped) {
        return;
      }
      if (!el.isConnected) {
        stop();
        return;
      }
      fn();
    }

    function schedule() {
      if (!stopped && !frame) {
        frame = nextFrame(run);
      }
    }

    document.addEventListener('quirk-theme', schedule);
    if (typeof MutationObserver === 'function') {
      observer = new MutationObserver(schedule);
      observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme', 'class']
      });
    }
    if (typeof matchMedia === 'function') {
      media = matchMedia('(prefers-color-scheme: dark)');
      if (media.addEventListener) {
        media.addEventListener('change', schedule);
      } else if (media.addListener) {
        media.addListener(schedule);
      }
    }

    themeWatchers.set(el, stop);
    return stop;
  }

  function isRow(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function pickRows(data, key) {
    var rows = Array.isArray(data) ? data : (isRow(data) ? data[key] : null);
    return Array.isArray(rows) && rows.every(isRow) ? rows : null;
  }

  function showMessage(el, text) {
    var note = el.querySelector(':scope > [data-q-message]');
    if (!note) {
      note = document.createElement('p');
      note.setAttribute('data-q-kit', '');
      note.setAttribute('data-q-message', '');
      el.appendChild(note);
    }
    note.textContent = text;
  }

  function clearMessage(el) {
    var note = el.querySelector(':scope > [data-q-message]');
    if (note) {
      note.remove();
    }
  }

  /**
   * Feeds fn the array of row objects found under `key` of the page's quirkData(), once the
   * document is ready and again after every quirkData.onChange. A bare array is used whole.
   * When there is no quirkData, or its value is not usable, one short message is written into
   * el instead. Never throws. Binding the same el again swaps key and fn without a second
   * onChange registration.
   */
  function bindData(el, key, fn) {
    var binding = dataBindings.get(el);
    var first = !binding;
    if (first) {
      binding = {};
      dataBindings.set(el, binding);
    }
    binding.key = key;
    binding.fn = fn;

    function use(data) {
      var rows = pickRows(data, binding.key);
      if (!rows) {
        showMessage(el, 'No data found for "' + binding.key + '".');
        return;
      }
      clearMessage(el);
      try {
        binding.fn(rows);
      } catch (error) {
        showMessage(el, 'Could not draw the data.');
      }
    }

    function fail() {
      showMessage(el, 'No data is available.');
    }

    whenReady(function () {
      var source = window.quirkData;
      if (typeof source !== 'function') {
        fail();
        return;
      }
      if (first && typeof source.onChange === 'function') {
        source.onChange(function (data) {
          if (el.isConnected) {
            use(data);
          }
        });
      }
      var pending;
      try {
        pending = source();
      } catch (error) {
        fail();
        return;
      }
      Promise.resolve(pending).then(use, fail);
    });
  }

  function cellText(cell) {
    return cell.textContent.replace(/\s+/g, ' ').trim();
  }

  function rowTexts(tr) {
    return Array.prototype.map.call(tr.cells, cellText);
  }

  /** Reads the column headers from the last thead row and the cell texts of every tbody row. */
  function readTable(table) {
    var columns = [];
    var rows = [];
    var head = table.tHead;
    if (head && head.rows.length) {
      columns = rowTexts(head.rows[head.rows.length - 1]);
    }
    Array.prototype.forEach.call(table.tBodies, function (body) {
      Array.prototype.forEach.call(body.rows, function (tr) {
        rows.push(rowTexts(tr));
      });
    });
    return { columns: columns, rows: rows };
  }

  var uidCount = 0;

  function uid(prefix) {
    uidCount += 1;
    return prefix + uidCount;
  }

  /** Creates a node the kit inserts, marked so it can be found and removed again. */
  function kitNode(tag, text) {
    var node = document.createElement(tag);
    node.setAttribute('data-q-kit', '');
    if (text) {
      node.textContent = text;
    }
    return node;
  }

  function removeKitChildren(host) {
    Array.prototype.slice.call(host.children).forEach(function (child) {
      if (child.hasAttribute('data-q-kit')) {
        child.remove();
      }
    });
  }

  function directChildren(host, tagName) {
    return Array.prototype.filter.call(host.children, function (child) {
      return child.tagName === tagName;
    });
  }

  /**
   * Runs render on whenReady and again, coalesced to a microtask, whenever the host's children
   * change. The host's own rendering is not reported back: render runs with the observer
   * paused, and the records it caused are dropped.
   */
  function watchChildren(host, options, render) {
    var observer = null;
    var queued = false;
    var stopped = false;

    function run() {
      queued = false;
      if (stopped || !host.isConnected) {
        return;
      }
      if (observer) {
        observer.disconnect();
      }
      try {
        render();
      } finally {
        if (observer) {
          observer.observe(host, options);
          observer.takeRecords();
        }
      }
    }

    function schedule() {
      if (!queued) {
        queued = true;
        Promise.resolve().then(run);
      }
    }

    if (typeof MutationObserver === 'function') {
      observer = new MutationObserver(schedule);
    }
    whenReady(function () {
      run();
    });
    return function stop() {
      stopped = true;
      if (observer) {
        observer.disconnect();
      }
    };
  }

  var HEADING = /^H[2-6]$/;

  function firstHeading(section) {
    var first = section.firstElementChild;
    return first && HEADING.test(first.tagName) ? first : null;
  }

  /**
   * q-tabs: direct-child sections become APG tabs. The headings stay in their panels (visually
   * hidden on screen) and give the tab labels. Inactive panels carry data-q-inactive.
   */
  class QTabs extends HTMLElement {
    static get observedAttributes() {
      return ['label'];
    }

    connectedCallback() {
      if (this._stop) {
        this._stop();
      }
      var self = this;
      this._stop = watchChildren(this, { childList: true, subtree: true, characterData: true }, function () {
        self._render();
      });
    }

    disconnectedCallback() {
      if (this._stop) {
        this._stop();
        this._stop = null;
      }
    }

    attributeChangedCallback() {
      if (this._list && this._list.parentNode === this) {
        this._syncLabel();
      }
    }

    _syncLabel() {
      var label = this.getAttribute('label');
      if (label) {
        this._list.setAttribute('aria-label', label);
      } else {
        this._list.removeAttribute('aria-label');
      }
    }

    _render() {
      var sections = directChildren(this, 'SECTION');
      var headings = sections.map(firstHeading);
      var labels = sections.map(function (section, i) {
        var heading = headings[i];
        return heading ? heading.textContent.replace(/\s+/g, ' ').trim() : (section.getAttribute('aria-label') || 'Tab ' + (i + 1));
      });
      var signature = labels.join('\u0000');
      if (this._list && this._list.parentNode === this && signature === this._signature && sections.every(function (s) { return s.getAttribute('role') === 'tabpanel'; })) {
        return;
      }

      removeKitChildren(this);
      Array.prototype.forEach.call(this.querySelectorAll('[data-q-tab-heading]'), function (node) {
        node.removeAttribute('data-q-tab-heading');
      });
      this._signature = signature;
      this._list = null;
      this._tabs = [];
      this._panels = sections;
      if (!sections.length) {
        return;
      }
      if (typeof this._selected !== 'number' || this._selected >= sections.length) {
        this._selected = 0;
      }

      var list = kitNode('div');
      list.setAttribute('role', 'tablist');
      this._list = list;
      this._syncLabel();

      var self = this;
      sections.forEach(function (section, i) {
        if (!section.id || section.hasAttribute('data-q-id')) {
          section.id = uid('q-panel-');
          section.setAttribute('data-q-id', '');
        }
        var tab = document.createElement('button');
        tab.type = 'button';
        tab.id = uid('q-tab-');
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', section.id);
        tab.textContent = labels[i];
        tab.addEventListener('click', function () {
          self._select(i, false);
        });
        list.appendChild(tab);
        self._tabs.push(tab);

        section.setAttribute('role', 'tabpanel');
        section.setAttribute('tabindex', '0');
        section.setAttribute('aria-labelledby', tab.id);
        if (headings[i]) {
          headings[i].setAttribute('data-q-tab-heading', '');
        }
      });
      list.addEventListener('keydown', function (event) {
        self._onKey(event);
      });
      this.insertBefore(list, sections[0]);
      this._select(this._selected, false);
    }

    _select(index, focus) {
      this._selected = index;
      this._tabs.forEach(function (tab, i) {
        var on = i === index;
        tab.setAttribute('aria-selected', on ? 'true' : 'false');
        tab.setAttribute('tabindex', on ? '0' : '-1');
      });
      this._panels.forEach(function (panel, i) {
        if (i === index) {
          panel.removeAttribute('data-q-inactive');
        } else {
          panel.setAttribute('data-q-inactive', '');
        }
      });
      if (focus) {
        this._tabs[index].focus();
      }
    }

    _onKey(event) {
      var current = this._tabs.indexOf(event.target);
      if (current < 0 || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      var last = this._tabs.length - 1;
      var next;
      if (event.key === 'ArrowRight') {
        next = current === last ? 0 : current + 1;
      } else if (event.key === 'ArrowLeft') {
        next = current === 0 ? last : current - 1;
      } else if (event.key === 'Home') {
        next = 0;
      } else if (event.key === 'End') {
        next = last;
      } else {
        return;
      }
      event.preventDefault();
      this._select(next, true);
    }
  }

  var TONE_WORDS = { neutral: 'Neutral', success: 'Success', warning: 'Warning', danger: 'Danger' };

  /**
   * q-timeline: the rail and markers are CSS. This adds the tone as a visually hidden word at the
   * start of each toned item, so color is not the only signal.
   */
  class QTimeline extends HTMLElement {
    connectedCallback() {
      if (this._stop) {
        this._stop();
      }
      var self = this;
      this._stop = watchChildren(this, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-tone'] }, function () {
        self._render();
      });
    }

    disconnectedCallback() {
      if (this._stop) {
        this._stop();
        this._stop = null;
      }
    }

    _render() {
      Array.prototype.forEach.call(this.querySelectorAll(':scope > ol > li'), function (item) {
        removeKitChildren(item);
        var word = TONE_WORDS[item.getAttribute('data-tone')];
        if (word) {
          var note = kitNode('span', word + ': ');
          note.className = 'q-visually-hidden';
          item.insertBefore(note, item.firstChild);
        }
      });
    }
  }

  var COPY_NOTICE = 'Press Ctrl+C (⌘C on Mac) to copy';

  /**
   * The highlight.js language for an explicit language name, else for a file name's extension (or
   * the whole name, as in Makefile). Null when highlight.js is not on the page or knows neither, so
   * callers fall back to plain text.
   */
  function codeLanguage(language, filename) {
    var hljs = window.hljs;
    if (!hljs || typeof hljs.highlight !== 'function' || typeof hljs.getLanguage !== 'function') {
      return null;
    }
    var name = (language || '').trim().toLowerCase();
    if (!name && filename) {
      var base = filename.trim().split('/').pop().toLowerCase();
      var dot = base.lastIndexOf('.');
      name = dot > 0 ? base.slice(dot + 1) : base;
    }
    return name && hljs.getLanguage(name) ? name : null;
  }

  /** Fills node with text highlighted as language. highlight.js escapes the text it is given. */
  function highlightInto(node, text, language) {
    try {
      node.innerHTML = window.hljs.highlight(text, { language: language, ignoreIllegals: true }).value;
    } catch (error) {
      node.textContent = text;
    }
  }

  /**
   * q-code: adds a header bar with the optional filename and a Copy button above the <pre>. When
   * highlight.js is on the page and the language attribute or the filename's extension names a
   * language it knows, a highlighted copy, carrying the <pre>'s classes, replaces it on screen; Copy
   * still copies the authored text. When the clipboard refuses, the code is selected and the reader is told to copy
   * by hand.
   */
  class QCode extends HTMLElement {
    static get observedAttributes() {
      return ['filename', 'language'];
    }

    connectedCallback() {
      var self = this;
      whenReady(function () {
        if (self.isConnected) {
          self._render();
        }
      });
    }

    disconnectedCallback() {
      clearTimeout(this._copiedTimer);
      clearTimeout(this._noticeTimer);
    }

    attributeChangedCallback() {
      if (this._bar && this.isConnected) {
        this._render();
      }
    }

    _source() {
      var pre = this.querySelector('pre');
      return pre ? (pre.querySelector('code') || pre) : null;
    }

    _render() {
      var pre = this.querySelector('pre');
      removeKitChildren(this);
      this._bar = null;
      this._view = null;
      if (!pre) {
        return;
      }
      pre.removeAttribute('data-q-replaced');
      var self = this;
      var bar = kitNode('div');
      bar.setAttribute('data-q-bar', '');
      var filename = this.getAttribute('filename');
      if (filename) {
        bar.appendChild(kitNode('span', filename)).setAttribute('data-q-filename', '');
      }
      var button = kitNode('button', 'Copy');
      button.type = 'button';
      button.setAttribute('data-q-copy', '');
      button.addEventListener('click', function () {
        self._copy();
      });
      var status = kitNode('span');
      status.setAttribute('data-q-status', '');
      status.setAttribute('aria-live', 'polite');
      bar.appendChild(status);
      bar.appendChild(button);
      this._bar = bar;
      this._button = button;
      this._status = status;
      var source = this._source();
      var language = source ? codeLanguage(this.getAttribute('language'), filename) : null;
      if (language) {
        var view = kitNode('pre');
        view.className = pre.className;
        view.setAttribute('data-q-highlight', language);
        var code = document.createElement('code');
        code.className = 'hljs';
        highlightInto(code, source.textContent, language);
        view.appendChild(code);
        this.insertBefore(view, pre);
        pre.setAttribute('data-q-replaced', '');
        this._view = view;
      }
      this.insertBefore(bar, this.firstChild);
    }

    _say(text, ms) {
      clearTimeout(this._noticeTimer);
      this._status.textContent = text;
      var status = this._status;
      this._noticeTimer = setTimeout(function () {
        status.textContent = '';
      }, ms);
    }

    _copy() {
      var source = this._source();
      if (!source) {
        return;
      }
      var text = source.textContent;
      var self = this;
      var done = function () {
        clearTimeout(self._copiedTimer);
        self._button.textContent = 'Copied';
        self._say('Copied', 2000);
        self._copiedTimer = setTimeout(function () {
          self._button.textContent = 'Copy';
        }, 2000);
      };
      var blocked = function () {
        self._selectText(self._view || source);
        self._say(COPY_NOTICE, 10000);
      };
      var pending;
      try {
        pending = navigator.clipboard && typeof navigator.clipboard.writeText === 'function' ? navigator.clipboard.writeText(text) : null;
      } catch (error) {
        pending = null;
      }
      if (!pending) {
        blocked();
        return;
      }
      Promise.resolve(pending).then(done, blocked);
    }

    _selectText(node) {
      var selection = window.getSelection && window.getSelection();
      if (!selection) {
        return;
      }
      var range = document.createRange();
      range.selectNodeContents(node);
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }

  var SVG_NS = 'http://www.w3.org/2000/svg';
  var SPARK_WIDTH = 100;
  var SPARK_HEIGHT = 32;
  var SPARK_PAD = 3;

  /** Returns the numbers of a comma-separated list, or null unless there are at least two and all are finite. */
  function parsePoints(text) {
    if (!text || !text.trim()) {
      return null;
    }
    var values = text.split(',').map(function (part) {
      return part.trim() === '' ? NaN : Number(part);
    });
    return values.length >= 2 && values.every(isFinite) ? values : null;
  }

  function sparkline(values) {
    var min = Math.min.apply(null, values);
    var max = Math.max.apply(null, values);
    var span = max - min;
    var last = values.length - 1;
    var coords = values.map(function (value, i) {
      var x = (i * SPARK_WIDTH) / last;
      var y = span === 0 ? SPARK_HEIGHT / 2 : SPARK_PAD + (1 - (value - min) / span) * (SPARK_HEIGHT - 2 * SPARK_PAD);
      return x.toFixed(2) + ',' + y.toFixed(2);
    });
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + SPARK_WIDTH + ' ' + SPARK_HEIGHT);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    svg.setAttribute('data-q-kit', '');
    var line = document.createElementNS(SVG_NS, 'polyline');
    line.setAttribute('points', coords.join(' '));
    svg.appendChild(line);
    return svg;
  }

  /** Returns 1, -1 or 0 from a delta's leading +, -, minus sign or digit; a zero amount counts as 0. */
  function deltaSign(text) {
    var lead = text.trim().charAt(0);
    var sign;
    if (lead === '+' || /\d/.test(lead)) {
      sign = 1;
    } else if (lead === '-' || lead === '−') {
      sign = -1;
    } else {
      return 0;
    }
    var amount = text.replace(/,/g, '').match(/\d+(?:\.\d+)?|\.\d+/);
    return amount && Number(amount[0]) !== 0 ? sign : 0;
  }

  /**
   * q-stat: marks the delta good, bad or flat from its sign and the direction attribute, and draws
   * an optional decorative sparkline from the points attribute. Layout is CSS only.
   */
  class QStat extends HTMLElement {
    static get observedAttributes() {
      return ['direction', 'points'];
    }

    connectedCallback() {
      if (this._stop) {
        this._stop();
      }
      var self = this;
      this._stop = watchChildren(this, { childList: true, subtree: true, characterData: true }, function () {
        self._render();
      });
    }

    disconnectedCallback() {
      if (this._stop) {
        this._stop();
        this._stop = null;
      }
    }

    attributeChangedCallback() {
      if (this._stop && this.isConnected) {
        this._render();
      }
    }

    _render() {
      var delta = this.querySelector(':scope > [slot="delta"]');
      if (delta) {
        var sign = deltaSign(delta.textContent);
        var rising = this.getAttribute('direction') === 'down-good' ? -sign : sign;
        delta.setAttribute('data-q-trend', sign === 0 ? 'flat' : (rising > 0 ? 'good' : 'bad'));
      }

      var points = this.getAttribute('points') || '';
      var values = parsePoints(points);
      var current = this.querySelector(':scope > svg[data-q-kit]');
      if (current && values && current.getAttribute('data-q-points') === points) {
        return;
      }
      removeKitChildren(this);
      if (values) {
        var svg = sparkline(values);
        svg.setAttribute('data-q-points', points);
        this.appendChild(svg);
      }
    }
  }

  var MIN_ROWS_FOR_FILTER = 12;
  var rowOrder = new WeakMap();
  var rowCount = 0;

  /** The first number in a cell, ignoring thousands separators, or null when there is none. */
  function numberIn(text) {
    var found = text.replace(/,/g, '').match(/[-−]?\d+(?:\.\d+)?|[-−]?\.\d+/);
    return found ? Number(found[0].replace('−', '-')) : null;
  }

  /** The visual column a header or body cell starts at, counting the colspans before it. */
  function columnStart(cell) {
    var start = 0;
    var cells = cell.parentNode.cells;
    for (var i = 0; i < cells.length && cells[i] !== cell; i += 1) {
      start += cells[i].colSpan || 1;
    }
    return start;
  }

  /** The cell of a row that covers a visual column, or null when the row is shorter. */
  function cellAtColumn(tr, column) {
    var end = 0;
    for (var i = 0; i < tr.cells.length; i += 1) {
      end += tr.cells[i].colSpan || 1;
      if (column < end) {
        return tr.cells[i];
      }
    }
    return null;
  }

  function compareRows(a, b, numeric, dir) {
    var result = 0;
    if (numeric) {
      if (a.num === null || b.num === null) {
        if (a.num === b.num) {
          result = 0;
        } else {
          return a.num === null ? 1 : -1;
        }
      } else {
        result = (a.num - b.num) * dir;
      }
    } else {
      result = a.text.localeCompare(b.text) * dir;
    }
    return result || rowOrder.get(a.tr) - rowOrder.get(b.tr);
  }

  function sameOrder(a, b) {
    return a.length === b.length && a.every(function (item, i) { return item === b[i]; });
  }

  /**
   * q-table: wraps a real table. Each header gets a sort button that cycles ascending, descending
   * and back to the authored order. Numeric columns (th.num) sort by value, tables past twelve rows
   * get a filter box, and the element itself scrolls sideways. With data-from it fills a generated
   * tbody from quirkData().
   */
  class QTable extends HTMLElement {
    static get observedAttributes() {
      return ['data-from'];
    }

    connectedCallback() {
      if (this._stop) {
        this._stop();
      }
      var self = this;
      this._stop = watchChildren(this, { childList: true, subtree: true, characterData: true }, function () {
        self._render();
      });
      this._bind();
    }

    disconnectedCallback() {
      if (this._stop) {
        this._stop();
        this._stop = null;
      }
    }

    attributeChangedCallback(name, before, after) {
      if (!this._stop || before === after) {
        return;
      }
      if (after === null) {
        this._unbind();
      } else {
        this._bind();
      }
    }

    _table() {
      return this.querySelector('table');
    }

    _headers(table) {
      var head = table.tHead;
      var row = head && head.rows.length ? head.rows[head.rows.length - 1] : null;
      return row ? Array.prototype.filter.call(row.cells, function (cell) { return cell.tagName === 'TH'; }) : [];
    }

    /** How many visual columns the header row spans. */
    _width(table) {
      var head = table.tHead;
      var row = head && head.rows.length ? head.rows[head.rows.length - 1] : null;
      var width = 0;
      if (row) {
        Array.prototype.forEach.call(row.cells, function (cell) {
          width += cell.colSpan || 1;
        });
      }
      return width;
    }

    _bodies(table) {
      var all = Array.prototype.slice.call(table.tBodies);
      var generated = all.filter(function (body) { return body.hasAttribute('data-q-kit'); });
      return this.hasAttribute('data-from') && generated.length ? generated : all.filter(function (body) { return !body.hasAttribute('data-q-kit'); });
    }

    _bind() {
      var key = this.getAttribute('data-from');
      var self = this;
      if (key) {
        bindData(this, key, function (rows) {
          self._fill(rows);
        });
      }
    }

    _unbind() {
      var table = this._table();
      clearMessage(this);
      if (table) {
        Array.prototype.forEach.call(table.tBodies, function (body) {
          if (body.hasAttribute('data-q-kit')) {
            body.remove();
          } else if (body.hasAttribute('data-q-superseded')) {
            body.removeAttribute('data-q-superseded');
            body.hidden = false;
          }
        });
      }
      this._render();
    }

    /** Replaces the generated tbody with one row per data row; author tbodies stay but are hidden. */
    _fill(data) {
      var table = this._table();
      if (!table || !this.hasAttribute('data-from')) {
        return;
      }
      var columns = {};
      this._headers(table).forEach(function (th) {
        columns[columnStart(th)] = {
          key: th.getAttribute('data-key') || th.textContent.trim(),
          num: th.classList.contains('num')
        };
      });
      var width = this._width(table);
      Array.prototype.slice.call(table.tBodies).forEach(function (body) {
        if (body.hasAttribute('data-q-kit')) {
          body.remove();
        } else {
          body.setAttribute('data-q-superseded', '');
          body.hidden = true;
        }
      });
      var body = kitNode('tbody');
      data.forEach(function (record) {
        var tr = document.createElement('tr');
        for (var at = 0; at < width; at += 1) {
          var td = document.createElement('td');
          var column = columns[at];
          if (column) {
            var value = record[column.key];
            td.textContent = value === null || value === undefined ? '' : (typeof value === 'object' ? JSON.stringify(value) : String(value));
            if (column.num) {
              td.setAttribute('data-q-num', '');
            }
          }
          tr.appendChild(td);
        }
        body.appendChild(tr);
      });
      table.appendChild(body);
      this._render();
    }

    _ensureSortButton(th) {
      if (th.querySelector(':scope > button[data-q-sort]') || !th.textContent.trim()) {
        return;
      }
      var self = this;
      var button = kitNode('button');
      button.type = 'button';
      button.setAttribute('data-q-sort', '');
      while (th.firstChild) {
        button.appendChild(th.firstChild);
      }
      th.appendChild(button);
      button.addEventListener('click', function () {
        var column = columnStart(th);
        var sort = self._sort;
        if (sort && sort.column === column && sort.dir < 0) {
          self._sort = null;
          self._restoreOrder();
        } else {
          self._sort = sort && sort.column === column ? { column: column, dir: -1 } : { column: column, dir: 1 };
        }
        self._render();
      });
    }

    /** Puts every body's rows back in the order they had before the first sort. */
    _restoreOrder() {
      var table = this._table();
      if (!table) {
        return;
      }
      this._bodies(table).forEach(function (body) {
        var rows = Array.prototype.slice.call(body.rows);
        var original = rows.slice().sort(function (a, b) {
          return (rowOrder.get(a) || Number.MAX_SAFE_INTEGER) - (rowOrder.get(b) || Number.MAX_SAFE_INTEGER);
        });
        if (!sameOrder(rows, original)) {
          original.forEach(function (tr) {
            body.appendChild(tr);
          });
        }
      });
    }

    _sortBody(body, column, dir, numeric) {
      var rows = Array.prototype.slice.call(body.rows);
      var items = rows.map(function (tr) {
        if (!rowOrder.has(tr)) {
          rowCount += 1;
          rowOrder.set(tr, rowCount);
        }
        var cell = cellAtColumn(tr, column);
        var text = cell ? cellText(cell) : '';
        return { tr: tr, text: text, num: numeric ? numberIn(text) : null };
      });
      items.sort(function (a, b) {
        return compareRows(a, b, numeric, dir);
      });
      var sorted = items.map(function (item) { return item.tr; });
      if (!sameOrder(rows, sorted)) {
        sorted.forEach(function (tr) {
          body.appendChild(tr);
        });
      }
    }

    _syncFilter(total) {
      var bar = this.querySelector(':scope > [data-q-filter]');
      if (total <= MIN_ROWS_FOR_FILTER) {
        if (bar) {
          bar.remove();
        }
        this._query = '';
        this.removeAttribute('data-q-long');
        return null;
      }
      if (!bar) {
        var self = this;
        bar = kitNode('div');
        bar.setAttribute('data-q-filter', '');
        var input = document.createElement('input');
        input.type = 'search';
        input.setAttribute('aria-label', 'Filter rows');
        input.placeholder = 'Filter rows';
        input.value = this._query || '';
        input.addEventListener('input', function () {
          self._query = input.value;
          self._render();
        });
        var count = document.createElement('span');
        count.setAttribute('aria-live', 'polite');
        count.setAttribute('data-q-count', '');
        bar.appendChild(input);
        bar.appendChild(count);
        this.insertBefore(bar, this.firstChild);
      }
      this.setAttribute('data-q-long', '');
      return bar.querySelector('[data-q-count]');
    }

    _render() {
      var table = this._table();
      if (!table) {
        return;
      }
      var self = this;
      var heads = this._headers(table);
      var bodies = this._bodies(table);
      heads.forEach(function (th) {
        self._ensureSortButton(th);
      });

      var sortHead = this._sort ? heads.filter(function (th) { return columnStart(th) === self._sort.column; })[0] : null;
      var sort = sortHead ? this._sort : null;
      heads.forEach(function (th) {
        if (th === sortHead) {
          th.setAttribute('aria-sort', sort.dir > 0 ? 'ascending' : 'descending');
        } else {
          th.removeAttribute('aria-sort');
        }
      });
      bodies.forEach(function (body) {
        Array.prototype.forEach.call(body.rows, function (tr) {
          heads.forEach(function (th) {
            var cell = th.classList.contains('num') ? cellAtColumn(tr, columnStart(th)) : null;
            if (cell) {
              cell.setAttribute('data-q-num', '');
            }
          });
        });
        if (sort) {
          self._sortBody(body, sort.column, sort.dir, sortHead.classList.contains('num'));
        }
      });

      var rows = [];
      bodies.forEach(function (body) {
        rows = rows.concat(Array.prototype.slice.call(body.rows));
      });
      var count = this._syncFilter(rows.length);
      var query = count ? (this._query || '').trim().toLowerCase() : '';
      var shown = 0;
      rows.forEach(function (tr) {
        var match = !query || rowTexts(tr).join(' ').toLowerCase().indexOf(query) >= 0;
        if (match) {
          shown += 1;
          if (tr.hasAttribute('data-q-filtered')) {
            tr.removeAttribute('data-q-filtered');
            tr.hidden = false;
          }
        } else {
          tr.setAttribute('data-q-filtered', '');
          tr.hidden = true;
        }
      });
      if (count) {
        var text = shown + ' of ' + rows.length + ' rows';
        if (count.textContent !== text) {
          count.textContent = text;
        }
      }
    }
  }

  var MAX_SERIES = 8;
  var LABEL_LIMIT = 24;
  var UNSAFE_KEYS = { __proto__: true, constructor: true, prototype: true };

  function isPlainObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  /** Deep-merges source into target (plain objects only; anything else replaces) and returns target. */
  function deepMerge(target, source) {
    Object.keys(source).forEach(function (key) {
      if (UNSAFE_KEYS[key]) {
        return;
      }
      var value = source[key];
      if (isPlainObject(value)) {
        if (!isPlainObject(target[key])) {
          target[key] = {};
        }
        deepMerge(target[key], value);
      } else {
        target[key] = value;
      }
    });
    return target;
  }

  /** The color with a new alpha, for area fills; a color it can't parse comes back unchanged. */
  function withAlpha(color, alpha) {
    var hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(color);
    if (hex) {
      var digits = hex[1].length === 3 ? hex[1].replace(/./g, '$&$&') : hex[1];
      return 'rgba(' + parseInt(digits.slice(0, 2), 16) + ',' + parseInt(digits.slice(2, 4), 16) + ',' + parseInt(digits.slice(4, 6), 16) + ',' + alpha + ')';
    }
    var rgb = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/.exec(color);
    return rgb ? 'rgba(' + rgb[1] + ',' + rgb[2] + ',' + rgb[3] + ',' + alpha + ')' : color;
  }

  function truncateLabel(text) {
    return text.length > LABEL_LIMIT ? text.slice(0, LABEL_LIMIT - 1) + '…' : text;
  }

  /** A cell or record value as a finite number, or null when it holds none. */
  function toNumber(value) {
    if (typeof value === 'number') {
      return isFinite(value) ? value : null;
    }
    return typeof value === 'string' ? numberIn(value) : null;
  }

  function isEmpty(value) {
    return value === null || value === undefined || value === '';
  }

  function displayText(value) {
    return isEmpty(value) ? '' : (typeof value === 'object' ? JSON.stringify(value) : String(value));
  }

  function findColumn(columns, name) {
    var wanted = name.trim().toLowerCase();
    for (var i = 0; i < columns.length; i += 1) {
      if (columns[i].label.toLowerCase() === wanted || columns[i].key.toLowerCase() === wanted) {
        return i;
      }
    }
    return -1;
  }

  function chartPalette() {
    var colors = [];
    for (var n = 1; n <= MAX_SERIES; n += 1) {
      colors.push(token('color-chart-' + n));
    }
    return {
      colors: colors,
      text: token('color-text'),
      muted: token('color-text-muted'),
      border: token('color-border'),
      bg: token('color-bg'),
      surface: token('color-surface'),
      font: token('font-sans')
    };
  }

  /**
   * q-chart: draws a bar, line, area or donut Chart.js chart from a child table or from data-from.
   * The canvas is labelled with the summary attribute, the source table moves into a "Table view"
   * details inside the element, and every color comes from the theme tokens. Without Chart.js, or
   * with more than eight series, the table is shown open instead.
   */
  class QChart extends HTMLElement {
    static get observedAttributes() {
      return ['summary', 'type', 'x', 'y', 'stacked', 'horizontal', 'data-from'];
    }

    connectedCallback() {
      if (this._stop) {
        this._stop();
      }
      var self = this;
      this._stop = watchChildren(this, { childList: true, subtree: true, characterData: true }, function () {
        self._render();
      });
      this._offTheme = onTheme(this, function () {
        self._render();
      });
      this._beforePrint = function () {
        var details = self._details();
        if (details && !details.open) {
          details.open = true;
          self._printOpened = true;
        }
      };
      this._afterPrint = function () {
        var details = self._details();
        if (details && self._printOpened) {
          details.open = false;
        }
        self._printOpened = false;
      };
      window.addEventListener('beforeprint', this._beforePrint);
      window.addEventListener('afterprint', this._afterPrint);
      this._bind();
    }

    disconnectedCallback() {
      if (this._stop) {
        this._stop();
        this._stop = null;
      }
      if (this._offTheme) {
        this._offTheme();
        this._offTheme = null;
      }
      window.removeEventListener('beforeprint', this._beforePrint);
      window.removeEventListener('afterprint', this._afterPrint);
      this._destroyChart();
    }

    attributeChangedCallback(name, before, after) {
      if (!this._stop || before === after) {
        return;
      }
      if (name === 'data-from') {
        this._rows = null;
        this._bind();
        return;
      }
      var self = this;
      Promise.resolve().then(function () {
        if (self.isConnected) {
          self._render();
        }
      });
    }

    _bind() {
      var key = this.getAttribute('data-from');
      var self = this;
      if (!key) {
        clearMessage(this);
        return;
      }
      bindData(this, key, function (rows) {
        if (self.hasAttribute('data-from')) {
          self._rows = rows;
          self._render();
        }
      });
    }

    _details() {
      return this.querySelector(':scope > details[data-q-kit]');
    }

    _destroyChart() {
      var canvas = this.querySelector(':scope > [data-q-chart-box] > canvas');
      var chart = canvas && typeof window.Chart === 'function' && window.Chart.getChart ? window.Chart.getChart(canvas) : null;
      if (chart) {
        chart.destroy();
      }
    }

    /** The columns and rows to chart, or null when there is nothing to read yet. */
    _model() {
      var author = this.querySelector('table:not([data-q-kit])');
      if (!this.hasAttribute('data-from')) {
        if (!author) {
          return null;
        }
        var read = readTable(author);
        if (!read.columns.length) {
          return null;
        }
        return {
          author: author,
          columns: read.columns.map(function (label) { return { key: label, label: label }; }),
          rows: read.rows,
          bound: false
        };
      }
      if (!this._rows) {
        return null;
      }
      var columns;
      var heads = author ? Array.prototype.filter.call(author.querySelectorAll('thead > tr:last-child > th'), function (th) { return th.closest('table') === author; }) : [];
      if (heads.length) {
        columns = heads.map(function (th) {
          var label = th.textContent.replace(/\s+/g, ' ').trim();
          return { key: th.getAttribute('data-key') || label, label: label };
        });
      } else {
        var seen = {};
        columns = [];
        this._rows.forEach(function (record) {
          Object.keys(record).forEach(function (key) {
            if (!seen[key]) {
              seen[key] = true;
              columns.push({ key: key, label: key });
            }
          });
        });
      }
      return {
        author: heads.length ? author : null,
        columns: columns,
        rows: this._rows.map(function (record) {
          return columns.map(function (column) { return record[column.key]; });
        }),
        bound: true
      };
    }

    /** Resolves the category column and the series columns from x, y and the data. */
    _plan(model) {
      var x = 0;
      if (this.hasAttribute('x')) {
        var found = findColumn(model.columns, this.getAttribute('x'));
        x = found >= 0 ? found : 0;
      }
      var series = [];
      var skipped = [];
      if (this.hasAttribute('y')) {
        this.getAttribute('y').split(',').forEach(function (name) {
          var index = findColumn(model.columns, name);
          var charted = index >= 0 && model.rows.some(function (row) { return toNumber(row[index]) !== null; });
          if (charted && index !== x && series.indexOf(index) < 0) {
            series.push(index);
          }
        });
      } else {
        model.columns.forEach(function (column, index) {
          if (index === x) {
            return;
          }
          var filled = model.rows.filter(function (row) { return !isEmpty(row[index]); });
          var numbers = filled.filter(function (row) { return toNumber(row[index]) !== null; }).length;
          if (filled.length && numbers === filled.length) {
            series.push(index);
          } else if (filled.length) {
            skipped.push({ label: column.label, partial: numbers > 0 });
          }
        });
      }
      return { x: x, series: series, skipped: skipped };
    }

    _rawOptions() {
      var script = this.querySelector(':scope > script[type="application/json"]');
      if (!script || !script.textContent.trim()) {
        return { text: '', options: {} };
      }
      var text = script.textContent;
      try {
        var parsed = JSON.parse(text);
        if (isPlainObject(parsed)) {
          return { text: text, options: parsed };
        }
        console.warn('q-chart: the options block must hold a JSON object; ignoring it.');
      } catch (error) {
        console.warn('q-chart: the options block is not valid JSON; ignoring it.');
      }
      return { text: text, options: {} };
    }

    _ensureDetails() {
      var details = this._details();
      if (!details) {
        details = kitNode('details');
        details.appendChild(kitNode('summary', 'Table view'));
        this.appendChild(details);
      }
      return details;
    }

    /** Puts the table the reader can see inside the Table view; bound data fills a generated one. */
    _fillTable(details, model) {
      var generated = details.querySelector(':scope > table[data-q-kit]');
      if (model.author && model.author.parentNode !== details) {
        details.appendChild(model.author);
      }
      if (!model.bound) {
        if (generated) {
          generated.remove();
        }
        Array.prototype.forEach.call(model.author.tBodies, function (body) {
          if (body.hasAttribute('data-q-kit')) {
            body.remove();
          } else if (body.hasAttribute('data-q-superseded')) {
            body.removeAttribute('data-q-superseded');
            body.hidden = false;
          }
        });
        return;
      }
      var table = model.author;
      if (table) {
        if (generated) {
          generated.remove();
        }
      } else {
        table = generated || kitNode('table');
        if (!generated) {
          details.appendChild(table);
        }
        while (table.firstChild) {
          table.removeChild(table.firstChild);
        }
        var head = document.createElement('thead');
        var headRow = document.createElement('tr');
        model.columns.forEach(function (column) {
          var th = document.createElement('th');
          th.scope = 'col';
          th.textContent = column.label;
          headRow.appendChild(th);
        });
        head.appendChild(headRow);
        table.appendChild(head);
      }
      Array.prototype.slice.call(table.tBodies).forEach(function (body) {
        if (body.hasAttribute('data-q-kit')) {
          body.remove();
        } else {
          body.setAttribute('data-q-superseded', '');
          body.hidden = true;
        }
      });
      var numeric = model.columns.map(function (column, index) {
        var filled = model.rows.filter(function (row) { return !isEmpty(row[index]); });
        return filled.length > 0 && filled.every(function (row) { return typeof row[index] === 'number'; });
      });
      var body = kitNode('tbody');
      model.rows.forEach(function (row) {
        var tr = document.createElement('tr');
        row.forEach(function (value, index) {
          var td = document.createElement('td');
          td.textContent = displayText(value);
          if (numeric[index]) {
            td.setAttribute('data-q-num', '');
          }
          tr.appendChild(td);
        });
        body.appendChild(tr);
      });
      table.appendChild(body);
    }

    _setNote(text) {
      var note = this.querySelector(':scope > [data-q-note]');
      if (!text) {
        if (note) {
          note.remove();
        }
        return;
      }
      if (!note) {
        note = kitNode('p');
        note.setAttribute('data-q-note', '');
        this.insertBefore(note, this._details());
      }
      note.textContent = text;
    }

    _ensureBox(summary) {
      var box = this.querySelector(':scope > [data-q-chart-box]');
      if (!box) {
        box = kitNode('div');
        box.setAttribute('data-q-chart-box', '');
        this.insertBefore(box, this.firstChild);
      }
      var canvas = box.querySelector('canvas');
      if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.setAttribute('role', 'img');
        box.appendChild(canvas);
      }
      if (summary) {
        canvas.setAttribute('aria-label', summary);
      }
      return canvas;
    }

    _removeBox() {
      var box = this.querySelector(':scope > [data-q-chart-box]');
      if (box) {
        box.remove();
      }
    }

    _config(model, plan, palette, raw) {
      var type = this.getAttribute('type');
      type = type === 'line' || type === 'area' || type === 'donut' ? type : 'bar';
      var horizontal = type === 'bar' && this.hasAttribute('horizontal');
      var stacked = type !== 'donut' && this.hasAttribute('stacked');
      var full = model.rows.map(function (row) { return displayText(row[plan.x]); });
      var labels = full.map(truncateLabel);
      var columns = plan.series.slice(0, type === 'donut' ? 1 : MAX_SERIES);

      var datasets = columns.map(function (index, i) {
        var values = model.rows.map(function (row) { return toNumber(row[index]); });
        var color = palette.colors[i % MAX_SERIES];
        var label = model.columns[index].label;
        if (type === 'donut') {
          return {
            label: label,
            data: values,
            backgroundColor: values.map(function (_, n) { return palette.colors[n % MAX_SERIES]; }),
            borderColor: palette.bg,
            borderWidth: 2
          };
        }
        if (type === 'bar') {
          return { label: label, data: values, backgroundColor: color, borderColor: color, borderWidth: 1 };
        }
        return {
          label: label,
          data: values,
          borderColor: color,
          backgroundColor: type === 'area' ? withAlpha(color, 0.25) : color,
          pointBackgroundColor: color,
          pointBorderColor: color,
          fill: type === 'area',
          borderWidth: 2,
          pointRadius: 3,
          tension: 0
        };
      });

      var options = {
        font: { family: palette.font },
        plugins: {
          legend: { display: type === 'donut' || datasets.length > 1, position: 'bottom' },
          tooltip: {
            callbacks: {
              title: function (items) {
                return items && items.length ? full[items[0].dataIndex] : '';
              }
            }
          }
        }
      };
      var guarantees = {
        animation: false,
        maintainAspectRatio: false,
        responsive: true,
        color: palette.text,
        plugins: {
          legend: { labels: { color: palette.text } },
          tooltip: {
            backgroundColor: palette.surface,
            titleColor: palette.text,
            bodyColor: palette.text,
            borderColor: palette.border,
            borderWidth: 1
          }
        }
      };
      if (type !== 'donut') {
        var category = horizontal ? 'y' : 'x';
        var value = horizontal ? 'x' : 'y';
        options.indexAxis = horizontal ? 'y' : 'x';
        options.scales = {};
        options.scales[category] = { stacked: stacked, grid: { display: false } };
        options.scales[value] = { stacked: stacked, beginAtZero: true };
        guarantees.scales = {};
        [category, value].forEach(function (axis) {
          guarantees.scales[axis] = {
            ticks: { color: palette.muted },
            grid: { color: palette.border },
            border: { color: palette.border }
          };
        });
      }

      return {
        type: type === 'donut' ? 'doughnut' : (type === 'bar' ? 'bar' : 'line'),
        data: { labels: labels, datasets: datasets },
        options: deepMerge(deepMerge(options, raw), guarantees)
      };
    }

    _render() {
      var model = this._model();
      if (!model) {
        return;
      }
      var plan = this._plan(model);
      var palette = chartPalette();
      var raw = this._rawOptions();
      var summary = this.getAttribute('summary') || '';
      var hasChart = typeof window.Chart === 'function';
      var signature = JSON.stringify([
        summary, this.getAttribute('type'), this.getAttribute('x'), this.getAttribute('y'),
        this.hasAttribute('stacked'), this.hasAttribute('horizontal'),
        model.bound, model.columns, model.rows, plan, raw.text, palette, hasChart
      ]);
      var details = this._details();
      var canvas = this.querySelector(':scope > [data-q-chart-box] > canvas');
      var alive = this._mode !== 'chart' || (canvas && hasChart && window.Chart.getChart(canvas));
      if (signature === this._signature && details && alive) {
        return;
      }
      this._signature = signature;

      this._destroyChart();
      details = this._ensureDetails();
      this._fillTable(details, model);

      var mode = 'table';
      var note = '';
      var notCharted = plan.skipped.filter(function (column) { return plan.series.length || column.partial; });
      var skipNote = notCharted.length
        ? ' Not charted (non-numeric values): ' + notCharted.map(function (column) { return column.label; }).join(', ') + '.'
        : '';
      if (plan.series.length > MAX_SERIES) {
        note = 'Too many series to chart clearly (' + plan.series.length + '); showing the table.' + skipNote;
      } else if (!plan.series.length && model.rows.length) {
        note = 'No numeric columns to chart; showing the table.' + skipNote;
      } else if (hasChart && plan.series.length && model.rows.length) {
        mode = 'chart';
        note = skipNote.trim();
      }
      this._setNote(note);

      if (mode === 'chart') {
        canvas = this._ensureBox(summary);
        try {
          new window.Chart(canvas, this._config(model, plan, palette, raw.options));
        } catch (error) {
          console.warn('q-chart: could not draw the chart; showing the table.');
          mode = 'table';
        }
      }
      if (mode === 'table') {
        this._removeBox();
      }
      if (mode === 'table' && this._mode !== 'table') {
        details.open = true;
      } else if (mode === 'chart' && this._mode === 'table') {
        details.open = false;
      }
      this._mode = mode;
    }
  }

  var HUNK = /^@@ -([0-9]{1,9})(?:,([0-9]{1,9}))? \+([0-9]{1,9})(?:,([0-9]{1,9}))? @@/;

  /** The file path a "+++ " header names, with a leading b/ removed; null for /dev/null. */
  function diffPath(raw) {
    var path = raw.split('\t')[0].trim();
    if (path === '/dev/null') {
      return null;
    }
    return path.indexOf('b/') === 0 ? path.slice(2) : path;
  }

  /**
   * Turns unified diff text into display rows: file, hunk, meta, add, del and ctx. The state machine
   * and its numbering mirror the static check's diff-notes rule: hunk sizes only tell a real
   * "--- "/"+++ " pair from a removed or added line that looks like one, new-side numbers count
   * context and "+" lines, and a "-" line has no new number.
   */
  function parseDiff(text) {
    var lines = text.replace(/\r\n/g, '\n').split('\n');
    var rows = [];
    var file = null;
    var oldNo = null;
    var newNo = null;
    var oldLeft = 0;
    var newLeft = 0;
    var i = 0;

    function reset() {
      oldNo = null;
      newNo = null;
      oldLeft = 0;
      newLeft = 0;
    }

    function meta(line) {
      if (line !== '') {
        rows.push({ kind: 'meta', text: line });
      }
    }

    while (i < lines.length) {
      var line = lines[i];
      var next = lines[i + 1];
      if (line.indexOf('--- ') === 0 && next !== undefined && next.indexOf('+++ ') === 0) {
        var hunkFollows = lines[i + 2] !== undefined && lines[i + 2].indexOf('@@') === 0;
        if (!(oldLeft > 0 || newLeft > 0) || hunkFollows) {
          file = diffPath(next.slice(4));
          rows.push({ kind: 'file', text: file === null ? line.slice(4).split('\t')[0].trim() : file, file: file });
          reset();
          i += 2;
          continue;
        }
      }
      var hunk = HUNK.exec(line);
      if (hunk) {
        oldNo = Number(hunk[1]);
        newNo = Number(hunk[3]);
        oldLeft = hunk[2] !== undefined ? Number(hunk[2]) : 1;
        newLeft = hunk[4] !== undefined ? Number(hunk[4]) : 1;
        rows.push({ kind: 'hunk', text: line });
      } else if (newNo !== null) {
        if (line.charAt(0) === '+') {
          rows.push({ kind: 'add', file: file, newNo: newNo, text: line.slice(1) });
          newNo += 1;
          newLeft -= 1;
        } else if (line.charAt(0) === '-') {
          rows.push({ kind: 'del', file: file, oldNo: oldNo, text: line.slice(1) });
          oldNo += 1;
          oldLeft -= 1;
        } else if (line.charAt(0) === ' ' || (line === '' && oldLeft > 0 && newLeft > 0)) {
          rows.push({ kind: 'ctx', file: file, oldNo: oldNo, newNo: newNo, text: line.slice(1) });
          newNo += 1;
          oldNo += 1;
          oldLeft -= 1;
          newLeft -= 1;
        } else {
          if (line.charAt(0) !== '\\') {
            reset();
          }
          meta(line);
        }
      } else {
        if (line.indexOf('diff ') === 0) {
          reset();
        }
        meta(line);
      }
      i += 1;
    }
    return rows;
  }

  var DIFF_MARKERS = { add: '+', del: '-', ctx: ' ' };

  function diffCell(tag, attr, text) {
    var cell = document.createElement(tag);
    cell.setAttribute(attr, '');
    cell.textContent = text;
    return cell;
  }

  function diffRow(kind, cell) {
    var tr = document.createElement('tr');
    tr.className = 'q-diff-' + kind;
    tr.appendChild(cell);
    return tr;
  }

  function diffSpanningCell(tag, text) {
    var cell = document.createElement(tag);
    cell.colSpan = 3;
    var span = document.createElement('span');
    span.textContent = text;
    cell.appendChild(span);
    return cell;
  }

  function diffLineRow(row, language) {
    var tr = document.createElement('tr');
    tr.className = 'q-diff-' + row.kind;
    tr.appendChild(diffCell('td', 'data-q-old', row.oldNo === undefined ? '' : String(row.oldNo)));
    tr.appendChild(diffCell('td', 'data-q-new', row.newNo === undefined ? '' : String(row.newNo)));
    var code = document.createElement('td');
    code.setAttribute('data-q-code', '');
    var marker = document.createElement('span');
    marker.className = 'q-diff-marker';
    marker.textContent = DIFF_MARKERS[row.kind];
    code.appendChild(marker);
    if (language) {
      var text = document.createElement('span');
      highlightInto(text, row.text, language);
      code.appendChild(text);
    } else {
      code.appendChild(document.createTextNode(row.text));
    }
    tr.appendChild(code);
    return tr;
  }

  /** A table row holding a copy of the note's content, so the original stays untouched. */
  function diffNoteRow(note) {
    var tr = document.createElement('tr');
    tr.className = 'q-diff-note-row';
    var cell = document.createElement('td');
    cell.colSpan = 3;
    var body = document.createElement('div');
    body.setAttribute('data-q-note', '');
    var label = document.createElement('span');
    label.className = 'q-visually-hidden';
    label.textContent = 'Note: ';
    body.appendChild(label);
    Array.prototype.forEach.call(note.childNodes, function (child) {
      body.appendChild(child.cloneNode(true));
    });
    cell.appendChild(body);
    tr.appendChild(cell);
    return tr;
  }

  /**
   * q-diff: renders the wrapped <pre> of unified diff text as a table with file headers, +/- rows
   * and old/new line numbers, and puts each q-diff-note under its new-side line. Code is
   * highlighted per line by each file's extension when highlight.js is on the page. The <pre> and the
   * placed notes are only marked data-q-replaced, never removed, and only once the view exists. A
   * note that matches no line stays visible in place.
   */
  class QDiff extends HTMLElement {
    connectedCallback() {
      if (this._stop) {
        this._stop();
      }
      var self = this;
      this._stop = watchChildren(this, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['file', 'line'] }, function () {
        self._render();
      });
    }

    disconnectedCallback() {
      if (this._stop) {
        this._stop();
        this._stop = null;
      }
    }

    _render() {
      removeKitChildren(this);
      var pre = this.querySelector('pre');
      var notes = Array.prototype.slice.call(this.querySelectorAll('q-diff-note'));
      [pre].concat(notes).forEach(function (node) {
        if (node) {
          node.removeAttribute('data-q-replaced');
        }
      });
      if (!pre) {
        return;
      }
      var rows = parseDiff(pre.textContent);
      if (!rows.some(function (row) { return row.kind === 'add' || row.kind === 'del' || row.kind === 'ctx'; })) {
        return;
      }

      var table = document.createElement('table');
      var body = document.createElement('tbody');
      table.appendChild(body);
      var anchors = {};
      var languages = {};
      rows.forEach(function (row) {
        var tr;
        if (row.kind === 'file') {
          tr = diffRow('file', diffSpanningCell('th', row.text));
        } else if (row.kind === 'hunk' || row.kind === 'meta') {
          tr = diffRow(row.kind, diffSpanningCell('td', row.text));
        } else {
          if (!(row.file in languages)) {
            languages[row.file] = codeLanguage('', row.file);
          }
          tr = diffLineRow(row, languages[row.file]);
          var key = row.file + '\n' + row.newNo;
          if (row.newNo !== undefined && row.file !== null && !anchors[key]) {
            anchors[key] = tr;
          }
        }
        body.appendChild(tr);
      });

      var placed = [];
      notes.forEach(function (note) {
        var anchor = anchors[note.getAttribute('file') + '\n' + Number(note.getAttribute('line'))];
        if (!anchor || !/^[0-9]+$/.test((note.getAttribute('line') || '').trim())) {
          return;
        }
        var after = anchor;
        while (after.nextSibling && after.nextSibling.className === 'q-diff-note-row') {
          after = after.nextSibling;
        }
        body.insertBefore(diffNoteRow(note), after.nextSibling);
        placed.push(note);
      });

      var view = kitNode('div');
      view.setAttribute('data-q-diff', '');
      view.setAttribute('role', 'region');
      view.setAttribute('aria-label', 'Diff');
      view.tabIndex = 0;
      view.appendChild(table);
      this.insertBefore(view, pre.nextSibling);

      placed.forEach(function (note) {
        note.setAttribute('data-q-replaced', '');
      });
      pre.setAttribute('data-q-replaced', '');
    }
  }

  /** q-diff-note: free text that q-diff places under a line; the element itself has no behavior. */
  class QDiffNote extends HTMLElement {}

  var BOARD_SAVED = 'Saved in this browser only.';
  var BOARD_BLOCKED = 'Not saved: this browser blocks storage.';
  var BOARD_NO_ID = 'Not saved: this board has no id.';
  var BOARD_PROBE_KEY = 'quirk-board:probe';
  var BOARD_DRAG_DISTANCE = 5;
  var BOARD_NAME_LIMIT = 80;
  var BOARD_INTERACTIVE = 'select, button, a, input, textarea, label';
  var BOARD_ARROWS = { ArrowLeft: true, ArrowRight: true, ArrowUp: true, ArrowDown: true };

  function collapse(text) {
    return text.replace(/\s+/g, ' ').trim();
  }

  /** FNV-1a over the text: a short stable string that changes when the authored layout does. */
  function fingerprint(text) {
    var hash = 2166136261;
    for (var i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16) + '-' + text.length;
  }

  function boardSlug() {
    var segment = (location.pathname.split('/').pop() || '').replace(/\.html$/, '');
    return segment || 'index';
  }

  function boardCards(list) {
    return Array.prototype.filter.call(list.children, function (child) {
      return child.tagName === 'LI' && !child.hasAttribute('data-q-kit');
    });
  }

  /** A card's own text, without the controls the board inserted into it. */
  function boardCardText(card) {
    var clone = card.cloneNode(true);
    Array.prototype.forEach.call(clone.querySelectorAll('[data-q-kit]'), function (node) {
      node.remove();
    });
    return collapse(clone.textContent);
  }

  function boardName(text) {
    return text.length > BOARD_NAME_LIMIT ? text.slice(0, BOARD_NAME_LIMIT - 1) + '…' : text;
  }

  /**
   * q-board: direct-child sections are columns of cards. Cards move by pointer drag (mouse and
   * touch) and by Alt plus the arrow keys. The layout is saved to localStorage under the page slug
   * and board id, and dropped when the authored cards change.
   */
  class QBoard extends HTMLElement {
    static get observedAttributes() {
      return ['id'];
    }

    connectedCallback() {
      if (this._stop) {
        this._stop();
      }
      var self = this;
      this._stop = watchChildren(this, { childList: true }, function () {
        self._sync();
      });
    }

    disconnectedCallback() {
      if (this._stop) {
        this._stop();
        this._stop = null;
      }
      this._endPress();
      clearTimeout(this._noticeTimer);
    }

    attributeChangedCallback(name, previous, value) {
      if (this._ready && previous !== value && this.isConnected) {
        this._loadSaved();
        this._syncNote();
      }
    }

    _sync() {
      if (this._ready) {
        if (!this._bar || this._bar.parentNode !== this) {
          this._buildBar();
        }
        return;
      }
      var columns = [];
      directChildren(this, 'SECTION').forEach(function (section) {
        var list = directChildren(section, 'UL')[0];
        if (list) {
          columns.push({ section: section, list: list, heading: firstHeading(section) });
        }
      });
      if (columns.length) {
        this._setup(columns);
      }
    }

    _setup(columns) {
      this._ready = true;
      this._cols = columns;
      this._ids = new Map();
      this._byId = new Map();
      this._blocked = false;

      var self = this;
      var authored = [];
      columns.forEach(function (col, ci) {
        var ids = [];
        boardCards(col.list).forEach(function (card) {
          var base = card.getAttribute('data-id');
          base = base && base.trim() ? base.trim() : boardCardText(card);
          var id = base;
          for (var n = 2; self._byId.has(id); n += 1) {
            id = base + '#' + n;
          }
          self._ids.set(card, id);
          self._byId.set(id, card);
          ids.push(id);
        });
        authored.push(ids);
        if (col.heading && !col.heading.id) {
          col.heading.id = uid('q-board-heading-');
        }
        if (col.heading) {
          col.list.setAttribute('aria-labelledby', col.heading.id);
        }
      });
      this._authored = authored;
      this._fingerprint = fingerprint(JSON.stringify(columns.map(function (col, ci) {
        return [self._columnName(ci), authored[ci]];
      })));

      this._byId.forEach(function (card) {
        card.setAttribute('data-q-card', '');
        card.setAttribute('tabindex', '0');
        card.setAttribute('aria-keyshortcuts', 'Alt+ArrowLeft Alt+ArrowRight Alt+ArrowUp Alt+ArrowDown');
        var handle = kitNode('span', '⋮⋮');
        handle.setAttribute('data-q-handle', '');
        handle.setAttribute('aria-hidden', 'true');
        card.appendChild(handle);
      });

      this.addEventListener('keydown', function (event) {
        self._onKey(event);
      });
      this.addEventListener('pointerdown', function (event) {
        self._onPointerDown(event);
      });

      this._probeStorage();
      this._buildBar();
      this._loadSaved();
      this._syncNote();
    }

    _columnName(ci) {
      var heading = this._cols[ci].heading;
      return heading ? collapse(heading.textContent) : 'Column ' + (ci + 1);
    }

    _buildBar() {
      removeKitChildren(this);
      var self = this;
      var bar = kitNode('div');
      bar.setAttribute('data-q-bar', '');

      var reset = kitNode('button', 'Reset');
      reset.type = 'button';
      reset.addEventListener('click', function () {
        self._reset();
      });
      var copy = kitNode('button', 'Copy as Markdown');
      copy.type = 'button';
      copy.addEventListener('click', function () {
        self._copy();
      });
      var note = kitNode('span');
      note.setAttribute('data-q-note', '');
      var status = kitNode('span');
      status.setAttribute('data-q-status', '');
      status.setAttribute('aria-live', 'polite');
      var announce = kitNode('span');
      announce.className = 'q-visually-hidden';
      announce.setAttribute('data-q-announce', '');
      announce.setAttribute('aria-live', 'polite');

      bar.appendChild(reset);
      bar.appendChild(copy);
      bar.appendChild(note);
      bar.appendChild(status);
      bar.appendChild(announce);
      this._bar = bar;
      this._note = note;
      this._status = status;
      this._announcer = announce;
      this._exportBox = null;
      this.insertBefore(bar, this.firstChild);
      this._syncNote();
    }

    _syncNote() {
      if (!this._note) {
        return;
      }
      this._note.textContent = !this.getAttribute('id') ? BOARD_NO_ID : this._blocked ? BOARD_BLOCKED : BOARD_SAVED;
    }

    /* storage */

    _key() {
      var id = this.getAttribute('id');
      return id ? 'quirk-board:' + boardSlug() + ':' + id : null;
    }

    _probeStorage() {
      try {
        localStorage.setItem(BOARD_PROBE_KEY, '1');
        localStorage.removeItem(BOARD_PROBE_KEY);
      } catch (error) {
        this._blocked = true;
      }
    }

    _loadSaved() {
      var key = this._key();
      if (!key || this._blocked) {
        return false;
      }
      var raw;
      try {
        raw = localStorage.getItem(key);
      } catch (error) {
        this._blocked = true;
        return false;
      }
      if (raw === null) {
        return false;
      }
      var saved = null;
      try {
        saved = JSON.parse(raw);
      } catch (error) {
        saved = null;
      }
      var columns = this._validLayout(saved);
      if (!columns) {
        this._forget();
        return false;
      }
      this._place(columns);
      return true;
    }

    /** The saved column ids when they describe exactly this page's authored cards, else null. */
    _validLayout(saved) {
      if (!saved || typeof saved !== 'object' || saved.v !== 1 || saved.authored !== this._fingerprint) {
        return null;
      }
      if (!Array.isArray(saved.columns) || saved.columns.length !== this._cols.length) {
        return null;
      }
      var seen = new Set();
      for (var ci = 0; ci < saved.columns.length; ci += 1) {
        var ids = saved.columns[ci];
        if (!Array.isArray(ids)) {
          return null;
        }
        for (var i = 0; i < ids.length; i += 1) {
          if (typeof ids[i] !== 'string' || !this._byId.has(ids[i]) || seen.has(ids[i])) {
            return null;
          }
          seen.add(ids[i]);
        }
      }
      return seen.size === this._byId.size ? saved.columns : null;
    }

    _layout() {
      return this._cols.map(function (col, ci) {
        return boardCards(col.list).map(function (card) {
          return this._ids.get(card);
        }, this);
      }, this);
    }

    _save() {
      var key = this._key();
      if (!key || this._blocked) {
        return;
      }
      try {
        localStorage.setItem(key, JSON.stringify({ v: 1, authored: this._fingerprint, columns: this._layout() }));
      } catch (error) {
        this._blocked = true;
        this._syncNote();
      }
    }

    _forget() {
      var key = this._key();
      if (!key) {
        return;
      }
      try {
        localStorage.removeItem(key);
      } catch (error) {
        this._blocked = true;
        this._syncNote();
      }
    }

    _place(columns) {
      var self = this;
      columns.forEach(function (ids, ci) {
        ids.forEach(function (id) {
          self._cols[ci].list.appendChild(self._byId.get(id));
        });
      });
    }

    _reset() {
      this._place(this._authored);
      this._forget();
      this._hideExport();
      this._announce('Layout reset to the authored order.');
    }

    /* moves */

    _announce(text) {
      if (!this._announcer) {
        return;
      }
      var same = this._announcer.textContent.replace(/ /g, ' ') === text;
      this._announcer.textContent = same ? text + ' ' : text;
    }

    _where(card) {
      for (var ci = 0; ci < this._cols.length; ci += 1) {
        if (this._cols[ci].list === card.parentNode) {
          return { col: ci, index: boardCards(this._cols[ci].list).indexOf(card) };
        }
      }
      return null;
    }

    /** Puts card at index of column ci, keeps focus where it was, saves and announces. Returns false when nothing changed. */
    _move(card, ci, index) {
      var from = this._where(card);
      if (!from) {
        return false;
      }
      var list = this._cols[ci].list;
      var others = boardCards(list).filter(function (other) {
        return other !== card;
      });
      var at = Math.max(0, Math.min(index, others.length));
      if (from.col === ci && from.index === at) {
        return false;
      }
      var active = document.activeElement;
      list.insertBefore(card, others[at] || null);
      if (active && card.contains(active) && document.activeElement !== active) {
        active.focus({ preventScroll: true });
      }
      this._save();
      var name = boardName(boardCardText(card));
      var position = (at + 1) + ' of ' + (others.length + 1);
      if (from.col === ci) {
        this._announce('Moved "' + name + '" to position ' + position + ' in ' + this._columnName(ci) + '.');
      } else {
        this._announce('Moved "' + name + '" to ' + this._columnName(ci) + ', position ' + position + '.');
      }
      return true;
    }

    _onKey(event) {
      var card = event.target;
      if (!this._ids.has(card) || !event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || !BOARD_ARROWS[event.key]) {
        return;
      }
      event.preventDefault();
      var here = this._where(card);
      if (!here) {
        return;
      }
      var name = '"' + boardName(boardCardText(card)) + '"';
      var count = boardCards(this._cols[here.col].list).length;
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        var next = here.col + (event.key === 'ArrowRight' ? 1 : -1);
        if (next < 0 || next >= this._cols.length) {
          this._announce(name + ' is already in the ' + (next < 0 ? 'first' : 'last') + ' column.');
          return;
        }
        this._move(card, next, here.index);
      } else {
        var to = here.index + (event.key === 'ArrowDown' ? 1 : -1);
        if (to < 0 || to >= count) {
          this._announce(name + ' is already ' + (to < 0 ? 'first' : 'last') + ' in ' + this._columnName(here.col) + '.');
          return;
        }
        this._move(card, here.col, to);
      }
    }

    /* pointer drag */

    _onPointerDown(event) {
      if (this._press || event.defaultPrevented || (event.pointerType === 'mouse' && event.button !== 0)) {
        return;
      }
      var target = event.target;
      var card = target && target.closest ? target.closest('li') : null;
      if (!card || !this._ids.has(card) || target.closest(BOARD_INTERACTIVE)) {
        return;
      }
      if (event.pointerType !== 'mouse' && !target.closest('[data-q-handle]')) {
        return;
      }
      var self = this;
      var press = { card: card, x: event.clientX, y: event.clientY, started: false, drop: null };
      press.move = function (e) {
        self._onPointerMove(e);
      };
      press.up = function (e) {
        self._onPointerUp(e);
      };
      press.cancel = function () {
        self._endPress();
      };
      press.key = function (e) {
        if (e.key === 'Escape') {
          self._endPress();
        }
      };
      press.select = function (e) {
        e.preventDefault();
      };
      this._press = press;
      document.addEventListener('pointermove', press.move);
      document.addEventListener('pointerup', press.up);
      document.addEventListener('pointercancel', press.cancel);
      document.addEventListener('keydown', press.key);
      document.addEventListener('selectstart', press.select);
    }

    _onPointerMove(event) {
      var press = this._press;
      if (!press) {
        return;
      }
      var dx = event.clientX - press.x;
      var dy = event.clientY - press.y;
      if (!press.started) {
        if (Math.sqrt(dx * dx + dy * dy) < BOARD_DRAG_DISTANCE) {
          return;
        }
        press.started = true;
        press.card.setAttribute('data-q-dragging', '');
        this.setAttribute('data-q-busy', '');
        press.marker = kitNode('div');
        press.marker.setAttribute('data-q-drop', '');
        press.marker.setAttribute('aria-hidden', 'true');
        this.appendChild(press.marker);
      }
      press.card.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)';
      press.drop = this._dropAt(event.clientX, event.clientY, press.card);
      this._showMarker(press.marker, press.drop);
    }

    _onPointerUp(event) {
      var press = this._press;
      if (!press) {
        return;
      }
      var drop = press.started ? this._dropAt(event.clientX, event.clientY, press.card) : null;
      var card = press.card;
      this._endPress();
      if (drop) {
        this._move(card, drop.col, drop.index);
        card.focus({ preventScroll: true });
      }
    }

    _endPress() {
      var press = this._press;
      if (!press) {
        return;
      }
      this._press = null;
      document.removeEventListener('pointermove', press.move);
      document.removeEventListener('pointerup', press.up);
      document.removeEventListener('pointercancel', press.cancel);
      document.removeEventListener('keydown', press.key);
      document.removeEventListener('selectstart', press.select);
      if (press.started) {
        press.card.removeAttribute('data-q-dragging');
        press.card.style.removeProperty('transform');
        if (!press.card.getAttribute('style')) {
          press.card.removeAttribute('style');
        }
        this.removeAttribute('data-q-busy');
        if (press.marker) {
          press.marker.remove();
        }
      }
    }

    /** The column and slot under a viewport point, by geometry, ignoring the card being dragged. */
    _dropAt(x, y, dragged) {
      var best = 0;
      var bestDistance = Infinity;
      this._cols.forEach(function (col, ci) {
        var rect = col.section.getBoundingClientRect();
        var dx = x < rect.left ? rect.left - x : x > rect.right ? x - rect.right : 0;
        var dy = y < rect.top ? rect.top - y : y > rect.bottom ? y - rect.bottom : 0;
        var distance = dx * dx + dy * dy;
        if (distance < bestDistance) {
          bestDistance = distance;
          best = ci;
        }
      });
      var list = this._cols[best].list;
      var others = boardCards(list).filter(function (card) {
        return card !== dragged;
      });
      var index = others.length;
      for (var i = 0; i < others.length; i += 1) {
        var rect = others[i].getBoundingClientRect();
        if (y < rect.top + rect.height / 2) {
          index = i;
          break;
        }
      }
      var box = list.getBoundingClientRect();
      var line;
      if (index < others.length) {
        line = others[index].getBoundingClientRect().top;
      } else if (others.length) {
        line = others[others.length - 1].getBoundingClientRect().bottom;
      } else {
        line = box.top;
      }
      return { col: best, index: index, line: line, left: box.left, width: box.width };
    }

    _showMarker(marker, drop) {
      var host = this.getBoundingClientRect();
      marker.style.left = (drop.left - host.left) + 'px';
      marker.style.width = drop.width + 'px';
      marker.style.top = (drop.line - host.top - 2) + 'px';
    }

    /* export */

    _markdown() {
      var self = this;
      return this._cols.map(function (col, ci) {
        var lines = ['## ' + self._columnName(ci)];
        boardCards(col.list).forEach(function (card) {
          lines.push('- ' + boardCardText(card));
        });
        return lines.join('\n');
      }).join('\n\n');
    }

    _say(text, ms) {
      clearTimeout(this._noticeTimer);
      this._status.textContent = text;
      var status = this._status;
      this._noticeTimer = setTimeout(function () {
        status.textContent = '';
      }, ms);
    }

    _hideExport() {
      if (this._exportBox) {
        this._exportBox.remove();
        this._exportBox = null;
      }
    }

    _copy() {
      var text = this._markdown();
      var self = this;
      this._hideExport();
      var blocked = function () {
        var box = kitNode('textarea');
        box.setAttribute('data-q-export', '');
        box.setAttribute('aria-label', 'Board as Markdown');
        box.readOnly = true;
        box.rows = Math.min(text.split('\n').length, 12);
        box.value = text;
        self._bar.parentNode.insertBefore(box, self._bar.nextSibling);
        self._exportBox = box;
        box.focus({ preventScroll: true });
        box.select();
        self._say(COPY_NOTICE, 10000);
      };
      var pending;
      try {
        pending = navigator.clipboard && typeof navigator.clipboard.writeText === 'function' ? navigator.clipboard.writeText(text) : null;
      } catch (error) {
        pending = null;
      }
      if (!pending) {
        blocked();
        return;
      }
      Promise.resolve(pending).then(function () {
        self._say('Copied', 2000);
      }, blocked);
    }
  }

  /**
   * q-sidenote: highlights the words it wraps and shows its slot="note" child as a popover while
   * a mouse hovers the words or the note, or while the words have keyboard focus. A tap or click
   * keeps the note open until the next one, and Escape closes it. Without this script, and in
   * print, the note reads inline in parentheses after the words.
   */
  class QSidenote extends HTMLElement {
    connectedCallback() {
      var self = this;
      whenReady(function () {
        if (self.isConnected) {
          self._build();
        }
      });
    }

    disconnectedCallback() {
      if (this._listeners) {
        this._listeners.abort();
        this._listeners = null;
      }
      if (this._note) {
        this._note.removeAttribute('data-q-open');
        this._note.removeAttribute('data-q-above');
        this._note.style.removeProperty('left');
        this._note = null;
      }
      this.removeAttribute('data-q-ready');
      this.removeAttribute('tabindex');
      this.removeAttribute('aria-describedby');
    }

    _build() {
      if (this._note) {
        return;
      }
      var note = this.querySelector(':scope > [slot="note"]');
      if (!note) {
        return;
      }
      this._note = note;
      if (!note.id) {
        note.id = uid('q-sidenote-');
      }
      note.setAttribute('role', 'tooltip');
      this.setAttribute('tabindex', '0');
      this.setAttribute('aria-describedby', note.id);
      this.setAttribute('data-q-ready', '');

      var self = this;
      var pinned = false;
      var hovered = false;
      var focused = false;
      var leaveTimer = null;
      var controller = new AbortController();
      var on = { signal: controller.signal };
      this._listeners = controller;
      controller.signal.addEventListener('abort', function () {
        clearTimeout(leaveTimer);
      });

      function render() {
        var open = pinned || hovered || focused;
        if (open === note.hasAttribute('data-q-open')) {
          return;
        }
        if (!open) {
          note.removeAttribute('data-q-open');
          return;
        }
        note.removeAttribute('data-q-above');
        note.style.removeProperty('left');
        note.setAttribute('data-q-open', '');
        self._place();
      }

      this.addEventListener('pointerenter', function (event) {
        if (event.pointerType === 'mouse') {
          clearTimeout(leaveTimer);
          hovered = true;
          render();
        }
      }, on);
      // a short grace period lets the pointer cross the gap between the words and the note
      this.addEventListener('pointerleave', function (event) {
        if (event.pointerType === 'mouse') {
          clearTimeout(leaveTimer);
          leaveTimer = setTimeout(function () {
            hovered = false;
            render();
          }, 150);
        }
      }, on);
      this.addEventListener('focusin', function () {
        focused = true;
        render();
      }, on);
      this.addEventListener('focusout', function (event) {
        if (!self.contains(event.relatedTarget)) {
          focused = false;
          render();
        }
      }, on);
      this.addEventListener('click', function (event) {
        if (note.contains(event.target)) {
          return;
        }
        pinned = !pinned;
        if (!pinned) {
          hovered = false;
          focused = false;
        }
        render();
      }, on);
      this.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && note.hasAttribute('data-q-open')) {
          pinned = hovered = focused = false;
          render();
        }
      }, on);
    }

    /** Keeps an open note inside the viewport: shifted left from the right edge, flipped above near the bottom. */
    _place() {
      var note = this._note;
      var gutter = 8;
      var box = note.getBoundingClientRect();
      var shift = 0;
      if (box.right > window.innerWidth - gutter) {
        shift = window.innerWidth - gutter - box.right;
      }
      if (box.left + shift < gutter) {
        shift = gutter - box.left;
      }
      if (shift) {
        note.style.left = shift + 'px';
      }
      var words = this.getBoundingClientRect();
      if (box.bottom > window.innerHeight - gutter && words.top - box.height > gutter) {
        note.setAttribute('data-q-above', '');
      }
    }
  }

  /** The cells of a table row that are real cells, in order. */
  function rowCells(row) {
    return Array.prototype.slice.call(row.cells);
  }

  /** A copy of a cell's content for the stacked view, without ids that would duplicate the table's. */
  function cellContent(cell) {
    var box = document.createDocumentFragment();
    Array.prototype.forEach.call(cell.childNodes, function (node) {
      var copy = node.cloneNode(true);
      if (copy.nodeType === 1) {
        copy.removeAttribute('id');
        Array.prototype.forEach.call(copy.querySelectorAll('[id]'), function (inner) {
          inner.removeAttribute('id');
        });
      }
      box.appendChild(copy);
    });
    return box;
  }

  /**
   * q-compare: marks the recommended option's column and builds one block per option for narrow
   * screens, the recommended one first, each a heading and a criteria list. The stylesheet shows
   * the blocks and hides the table at 700px and below and in print. Without this script the table
   * scrolls inside its own box.
   */
  class QCompare extends HTMLElement {
    static get observedAttributes() {
      return ['recommended'];
    }

    connectedCallback() {
      if (this._stop) {
        this._stop();
      }
      var self = this;
      this._stop = watchChildren(this, { childList: true, subtree: true, characterData: true }, function () {
        self._render();
      });
    }

    disconnectedCallback() {
      if (this._stop) {
        this._stop();
        this._stop = null;
      }
    }

    attributeChangedCallback() {
      if (this._stop && this.isConnected) {
        this._render();
      }
    }

    _clear(table) {
      removeKitChildren(this);
      Array.prototype.forEach.call(table.querySelectorAll('[data-q-badge]'), function (badge) {
        badge.remove();
      });
      Array.prototype.forEach.call(table.querySelectorAll('[data-q-recommended]'), function (cell) {
        cell.removeAttribute('data-q-recommended');
      });
      this.removeAttribute('data-q-ready');
    }

    _render() {
      var table = this.querySelector(':scope > table');
      if (!table) {
        return;
      }
      this._clear(table);
      var rows = Array.prototype.slice.call(table.rows);
      if (!rows.length) {
        return;
      }
      var head = rowCells(rows[0]);
      var options = head.length - 1;
      if (options < 1) {
        return;
      }
      var wanted = Number(this.getAttribute('recommended'));
      var recommended = wanted >= 1 && wanted <= options && wanted === Math.floor(wanted) ? wanted : 0;

      var blocks = [];
      for (var i = 1; i <= options; i += 1) {
        var block = kitNode('div');
        block.setAttribute('data-q-option', '');
        var title = document.createElement('h3');
        title.textContent = cellText(head[i]);
        block.appendChild(title);
        var list = document.createElement('dl');
        for (var r = 1; r < rows.length; r += 1) {
          var cells = rowCells(rows[r]);
          if (!cells.length) {
            continue;
          }
          var term = document.createElement('dt');
          term.textContent = cellText(cells[0]);
          var detail = document.createElement('dd');
          if (cells[i]) {
            detail.appendChild(cellContent(cells[i]));
          }
          list.appendChild(term);
          list.appendChild(detail);
        }
        block.appendChild(list);
        if (i === recommended) {
          block.setAttribute('data-q-recommended', '');
          var inBlock = kitNode('span', ' Recommended');
          inBlock.setAttribute('data-q-badge', '');
          title.appendChild(inBlock);
          this._markColumn(rows, i);
          blocks.unshift(block);
        } else {
          blocks.push(block);
        }
      }

      var stack = kitNode('div');
      stack.setAttribute('data-q-stack', '');
      blocks.forEach(function (block) {
        stack.appendChild(block);
      });
      this.appendChild(stack);
      this.setAttribute('data-q-ready', '');
    }

    _markColumn(rows, column) {
      rows.forEach(function (row, index) {
        var cell = row.cells[column];
        if (!cell) {
          return;
        }
        cell.setAttribute('data-q-recommended', '');
        if (index === 0) {
          var badge = kitNode('span', ' Recommended');
          badge.setAttribute('data-q-badge', '');
          cell.appendChild(badge);
        }
      });
    }
  }
  var FLOW_COORD_KEYS = ['x', 'y', 'position', 'positions'];
  var FLOW_DETAIL_TAGS = {
    P: true, UL: true, OL: true, LI: true, CODE: true, PRE: true, A: true,
    EM: true, STRONG: true, B: true, I: true, BR: true, SPAN: true, KBD: true,
    SAMP: true, SUB: true, SUP: true, DL: true, DT: true, DD: true
  };

  function isSafeFlowHref(href) {
    var trimmed = String(href || '').replace(/[\s\u0000-\u001f]+/g, '').toLowerCase();
    if (!trimmed) {
      return false;
    }
    if (trimmed.charAt(0) === '#' || trimmed.charAt(0) === '/' || trimmed.indexOf('./') === 0 || trimmed.indexOf('../') === 0) {
      return true;
    }
    return /^(https?:|mailto:)/.test(trimmed);
  }

  function sanitizeFlowDetail(html) {
    var frag = document.createDocumentFragment();
    if (!html || typeof html !== 'string') {
      return frag;
    }
    var tpl = document.createElement('template');
    tpl.innerHTML = html;
    function clean(node) {
      if (node.nodeType === 3) {
        return document.createTextNode(node.nodeValue || '');
      }
      if (node.nodeType !== 1) {
        return null;
      }
      var tag = node.tagName ? node.tagName.toUpperCase() : '';
      if (!FLOW_DETAIL_TAGS[tag]) {
        return null;
      }
      var out = document.createElement(tag.toLowerCase());
      if (tag === 'A' && node.hasAttribute('href')) {
        var href = node.getAttribute('href') || '';
        if (isSafeFlowHref(href)) {
          out.setAttribute('href', href);
        }
      }
      var children = node.childNodes;
      for (var i = 0; i < children.length; i += 1) {
        var child = clean(children[i]);
        if (child) {
          out.appendChild(child);
        }
      }
      return out;
    }
    var roots = tpl.content.childNodes;
    for (var i = 0; i < roots.length; i += 1) {
      var cleaned = clean(roots[i]);
      if (cleaned) {
        frag.appendChild(cleaned);
      }
    }
    return frag;
  }

  // python str.strip parity: String.prototype.trim differs on U+FEFF, U+001C-U+001F and U+0085
  function isBlankFlowId(text) {
    return /^[\t-\r\u001c-\u001f \u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/.test(text);
  }

  function isValidFlowDetail(html) {
    if (!html || typeof html !== 'string') {
      return true;
    }
    if (/<(script|style|form|input|button|img|iframe|object|embed|svg|math|table)\b/i.test(html)) {
      return false;
    }
    var tpl = document.createElement('template');
    tpl.innerHTML = html;
    var ok = true;
    function walk(node) {
      if (!ok) {
        return;
      }
      if (node.nodeType === 1) {
        var tag = node.tagName ? node.tagName.toUpperCase() : '';
        if (!FLOW_DETAIL_TAGS[tag]) {
          ok = false;
          return;
        }
        var attrs = node.attributes || [];
        for (var i = 0; i < attrs.length; i += 1) {
          var name = attrs[i].name.toLowerCase();
          var val = attrs[i].value || '';
          if (name.indexOf('on') === 0 || name === 'src' || name === 'srcset' || name === 'action' || name === 'style') {
            ok = false;
            return;
          }
          if (name === 'href' && (tag !== 'A' || !isSafeFlowHref(val))) {
            ok = false;
            return;
          }
        }
      }
      var children = node.childNodes || [];
      for (var j = 0; j < children.length; j += 1) {
        walk(children[j]);
      }
    }
    walk(tpl.content);
    return ok;
  }

  function hasCoordKeys(obj) {
    if (!isRow(obj)) {
      return false;
    }
    for (var i = 0; i < FLOW_COORD_KEYS.length; i += 1) {
      if (Object.prototype.hasOwnProperty.call(obj, FLOW_COORD_KEYS[i])) {
        return true;
      }
    }
    return false;
  }

  function svgNode(tag, attrs) {
    var el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (attrs[k] !== null && attrs[k] !== undefined) {
          el.setAttribute(k, String(attrs[k]));
        }
      });
    }
    return el;
  }

  var FLOW_PULSE_SPEED = 180;
  var FLOW_PULSE_INTERVAL = 700;

  function edgeLength(rec) {
    try {
      var len = rec.basePath.getTotalLength();
      if (len > 0) {
        return len;
      }
    } catch (_e) {}
    var total = 0;
    for (var i = 1; i < rec.points.length; i += 1) {
      total += Math.hypot(rec.points[i].x - rec.points[i - 1].x, rec.points[i].y - rec.points[i - 1].y);
    }
    return Math.max(1, total);
  }

  /**
   * Time each lit edge so a pulse moving at FLOW_PULSE_SPEED crosses every edge at the same pace
   * and reaches the focused node, then leaves it, at one instant whichever branch it took.
   * Returns one {rec, offset, duration} per pulse, in milliseconds from the start of a wave.
   */
  function pulseSchedule(activePulses, focusId) {
    var items = activePulses.map(function (item) {
      return { rec: item.rec, down: item.down, len: edgeLength(item.rec) };
    });
    var toFocus = Object.create(null);
    toFocus[focusId] = 0;
    var fromFocus = Object.create(null);
    fromFocus[focusId] = 0;
    var changed = true;
    for (var pass = 0; changed && pass <= items.length; pass += 1) {
      changed = false;
      items.forEach(function (it) {
        var e = it.rec.edge;
        var known = it.down ? fromFocus : toFocus;
        var near = it.down ? e.from : e.to;
        var far = it.down ? e.to : e.from;
        if (near in known && (!(far in known) || known[near] + it.len < known[far])) {
          known[far] = known[near] + it.len;
          changed = true;
        }
      });
    }
    var lead = 0;
    items.forEach(function (it) {
      if (!it.down && it.rec.edge.to in toFocus) {
        lead = Math.max(lead, toFocus[it.rec.edge.to] + it.len);
      }
    });
    var msPerPx = 1000 / FLOW_PULSE_SPEED;
    return items.map(function (it) {
      var e = it.rec.edge;
      var start = it.down ? lead + (fromFocus[e.from] || 0) : lead - (toFocus[e.to] || 0) - it.len;
      return { rec: it.rec, offset: start * msPerPx, duration: it.len * msPerPx };
    });
  }

  var FLOW_DECISION_LINE_MAX = 120;
  var FLOW_DECISION_LINE_HEIGHT = 16;
  var FLOW_SUBPROCESS_EXTRA = 16;
  var FLOW_LOOP_PREFIX = '\u21a9 ';

  /**
   * Splits a decision label on word boundaries into lines no wider than the
   * cap. A single word wider than the cap keeps a line of its own.
   */
  function wrapFlowLabel(label, measure) {
    var lines = [];
    var current = '';
    label.split(/\s+/).forEach(function (word) {
      if (!word) {
        return;
      }
      var candidate = current ? current + ' ' + word : word;
      if (current && measure(candidate, 13, '600') > FLOW_DECISION_LINE_MAX) {
        lines.push(current);
        current = word;
      } else {
        current = candidate;
      }
    });
    if (current) {
      lines.push(current);
    }
    return lines.length ? lines : [label];
  }

  /**
   * Moves one end of an axis-aligned edge along its own segment, back into the
   * node, until it meets the outline of the diamond inscribed in the node's
   * box. Returns a new point list; ends that are not axis-aligned are kept.
   */
  function snapFlowEndToDiamond(pts, atStart, box) {
    var last = pts.length - 1;
    var p = atStart ? pts[0] : pts[last];
    var nb = atStart ? pts[1] : pts[last - 1];
    var a = box.width / 2;
    var b = box.height / 2;
    var cx = box.x + a;
    var cy = box.y + b;
    var moved = null;
    if (nb.y === p.y && nb.x !== p.x && Math.abs(p.y - cy) < b && p.x !== cx) {
      var sx = p.x > cx ? 1 : -1;
      var nx = cx + sx * a * (1 - Math.abs(p.y - cy) / b);
      if ((nb.x - cx) * sx > 0 && (nb.x - nx) * sx > 0) {
        moved = { x: nx, y: p.y };
      }
    } else if (nb.x === p.x && nb.y !== p.y && Math.abs(p.x - cx) < a && p.y !== cy) {
      var sy = p.y > cy ? 1 : -1;
      var ny = cy + sy * b * (1 - Math.abs(p.x - cx) / a);
      if ((nb.y - cy) * sy > 0 && (nb.y - ny) * sy > 0) {
        moved = { x: p.x, y: ny };
      }
    }
    if (!moved) {
      return pts;
    }
    var out = pts.slice();
    out[atStart ? 0 : last] = moved;
    return out;
  }

  /** Draws a polyline with each corner rounded by up to `radius` pixels. */
  function roundedFlowPath(pts, radius) {
    var d = 'M ' + pts[0].x + ' ' + pts[0].y;
    for (var i = 1; i < pts.length - 1; i += 1) {
      var p0 = pts[i - 1];
      var p1 = pts[i];
      var p2 = pts[i + 1];
      var len1 = Math.sqrt((p1.x - p0.x) * (p1.x - p0.x) + (p1.y - p0.y) * (p1.y - p0.y));
      var len2 = Math.sqrt((p2.x - p1.x) * (p2.x - p1.x) + (p2.y - p1.y) * (p2.y - p1.y));
      var r = Math.min(radius, len1 / 2, len2 / 2);
      if (r <= 0) {
        d += ' L ' + p1.x + ' ' + p1.y;
        continue;
      }
      d += ' L ' + (p1.x + (p0.x - p1.x) / len1 * r) + ' ' + (p1.y + (p0.y - p1.y) / len1 * r)
        + ' Q ' + p1.x + ' ' + p1.y + ' '
        + (p1.x + (p2.x - p1.x) / len2 * r) + ' ' + (p1.y + (p2.y - p1.y) / len2 * r);
    }
    return d + ' L ' + pts[pts.length - 1].x + ' ' + pts[pts.length - 1].y;
  }

  var FLOW_TRACE_MAX_LINES = 400;
  var FLOW_TRACE_STEP_MS = 1500;

  /** A trace value as the 2-space pretty print that the text list shows and the line limit counts. */
  function tracePretty(value) {
    return JSON.stringify(value, null, 2);
  }

  function traceStringOk(str) {
    for (var i = 0; i < str.length; i += 1) {
      var c = str.charCodeAt(i);
      if (c >= 0xd800 && c <= 0xdbff) {
        var d = str.charCodeAt(i + 1);
        if (!(d >= 0xdc00 && d <= 0xdfff)) {
          return false;
        }
        i += 1;
      } else if (c >= 0xdc00 && c <= 0xdfff) {
        return false;
      }
    }
    return true;
  }

  /**
   * Whether a trace value is JSON the Python build check also accepts: finite numbers, no unpaired
   * surrogates in strings or keys, and shallow enough to walk and pretty-print. Walks with an explicit
   * stack so a very deep value can't overflow the call stack.
   */
  function traceValueOk(value) {
    try {
      var stack = [value];
      while (stack.length) {
        var v = stack.pop();
        if (typeof v === 'number') {
          if (!isFinite(v)) {
            return false;
          }
        } else if (typeof v === 'string') {
          if (!traceStringOk(v)) {
            return false;
          }
        } else if (v !== null && typeof v === 'object') {
          var keys = Object.keys(v);
          for (var i = 0; i < keys.length; i += 1) {
            if (!Array.isArray(v) && !traceStringOk(keys[i])) {
              return false;
            }
            stack.push(v[keys[i]]);
          }
        }
      }
      return tracePretty(value).split('\n').length <= FLOW_TRACE_MAX_LINES;
    } catch (_e) {
      return false;
    }
  }

  /**
   * Whether every string and object key in the graph data can be written as UTF-8. Trace step values
   * are left to `traceValueOk`, which reports them under its own rule.
   */
  function flowGraphTextOk(raw) {
    var childCtx = {
      root: { traces: 'traces' },
      trace: { steps: 'steps' },
      step: { value: null }
    };
    var stack = [{ v: raw, ctx: 'root' }];
    while (stack.length) {
      var item = stack.pop();
      var v = item.v;
      if (typeof v === 'string') {
        if (!traceStringOk(v)) {
          return false;
        }
      } else if (Array.isArray(v)) {
        var next = item.ctx === 'traces' ? 'trace' : (item.ctx === 'steps' ? 'step' : 'any');
        for (var i = 0; i < v.length; i += 1) {
          stack.push({ v: v[i], ctx: next });
        }
      } else if (v !== null && typeof v === 'object') {
        var keys = Object.keys(v);
        var rules = childCtx[item.ctx] || {};
        for (var k = 0; k < keys.length; k += 1) {
          if (!traceStringOk(keys[k])) {
            return false;
          }
          var ctx = Object.prototype.hasOwnProperty.call(rules, keys[k]) ? rules[keys[k]] : 'any';
          if (ctx !== null) {
            stack.push({ v: v[keys[k]], ctx: ctx });
          }
        }
      }
    }
    return true;
  }

  function traceKind(value) {
    return Array.isArray(value) ? 'array' : (isRow(value) ? 'object' : 'scalar');
  }

  function traceEqual(a, b) {
    var kind = traceKind(a);
    if (kind !== traceKind(b)) {
      return false;
    }
    if (kind === 'scalar') {
      return a === b;
    }
    var keys = Object.keys(a);
    if (kind === 'array' ? a.length !== b.length : keys.length !== Object.keys(b).length) {
      return false;
    }
    return keys.every(function (k) {
      return Object.prototype.hasOwnProperty.call(b, k) && traceEqual(a[k], b[k]);
    });
  }

  function traceChildren(value) {
    return Array.isArray(value)
      ? value.map(function (item, i) { return [String(i), item]; })
      : Object.keys(value).map(function (k) { return [k, value[k]]; });
  }

  /** A field and everything under it carrying one change, for a value that is wholly new or wholly gone. */
  function traceWhole(key, value, change) {
    var field = { key: key, change: change, value: value, hasChange: change !== 'same' };
    if (traceKind(value) !== 'scalar') {
      field.children = traceChildren(value).map(function (pair) {
        return traceWhole(pair[0], pair[1], change);
      });
    }
    return field;
  }

  function traceDiffField(key, prev, next) {
    var kind = traceKind(next);
    if (kind === 'scalar' || kind !== traceKind(prev)) {
      if (traceEqual(prev, next)) {
        return { key: key, change: 'same', value: next, hasChange: false };
      }
      return { key: key, change: 'changed', value: next, old: prev, hasChange: true };
    }
    var children = [];
    var prevPairs = traceChildren(prev);
    var prevByKey = Object.create(null);
    prevPairs.forEach(function (pair) { prevByKey[pair[0]] = pair[1]; });
    var nextKeys = Object.create(null);
    traceChildren(next).forEach(function (pair) {
      nextKeys[pair[0]] = true;
      children.push(pair[0] in prevByKey
        ? traceDiffField(pair[0], prevByKey[pair[0]], pair[1])
        : traceWhole(pair[0], pair[1], 'added'));
    });
    prevPairs.forEach(function (pair) {
      if (!nextKeys[pair[0]]) {
        children.push(traceWhole(pair[0], pair[1], 'removed'));
      }
    });
    return {
      key: key,
      change: 'same',
      value: next,
      children: children,
      hasChange: children.some(function (c) { return c.hasChange; })
    };
  }

  /**
   * Cleans the `traces` payload, or returns null when any trace breaks the contract the build check
   * enforces. Each step gains `edge`, the index of its incoming edge, found from `via` or inferred
   * from the one edge that joins the two nodes.
   */
  function parseFlowTraces(raw, nodeMap, edges, edgeRefs) {
    if (raw === undefined) {
      return [];
    }
    if (!Array.isArray(raw)) {
      return null;
    }
    var has = Object.prototype.hasOwnProperty;
    var seen = Object.create(null);
    var traces = [];
    for (var ti = 0; ti < raw.length; ti += 1) {
      var t = raw[ti];
      if (!isRow(t) || typeof t.id !== 'string' || !t.id.trim() || typeof t.label !== 'string' || !t.label.trim()) {
        return null;
      }
      if (seen[t.id] || !Array.isArray(t.steps) || t.steps.length < 2) {
        return null;
      }
      seen[t.id] = true;
      var steps = [];
      for (var si = 0; si < t.steps.length; si += 1) {
        var s = t.steps[si];
        if (!isRow(s) || typeof s.node !== 'string' || !has.call(s, 'value')) {
          return null;
        }
        if (!has.call(nodeMap, s.node) || (s.note !== undefined && typeof s.note !== 'string')) {
          return null;
        }
        if (!traceValueOk(s.value)) {
          return null;
        }
        var edge = null;
        if (si === 0) {
          if (s.via !== undefined) {
            return null;
          }
        } else {
          var from = steps[si - 1].node;
          var candidates = edges.filter(function (e) { return e.from === from && e.to === s.node; });
          if (s.via !== undefined) {
            if (typeof s.via !== 'string' || !has.call(edgeRefs, s.via) || candidates.indexOf(edges[edgeRefs[s.via]]) < 0) {
              return null;
            }
            edge = edgeRefs[s.via];
          } else if (candidates.length === 1) {
            edge = candidates[0].index;
          } else {
            return null;
          }
        }
        steps.push({
          node: s.node,
          value: s.value,
          note: typeof s.note === 'string' ? s.note : null,
          via: typeof s.via === 'string' ? s.via : null,
          edge: edge
        });
      }
      traces.push({ id: t.id, label: t.label, steps: steps });
    }
    return traces;
  }

  /**
   * Compares one trace step's value with the step before it. Fields match by name inside objects
   * and by index inside arrays; a value whose type changes is one `changed` field, not a recursion.
   * With no previous step every field is `same`.
   */
  function traceDiff(prev, next, hasPrev) {
    return hasPrev ? traceDiffField(null, prev, next) : traceWhole(null, next, 'same');
  }

  var TRACE_MARKS = {
    same: ['', ''],
    added: ['+', 'added'],
    removed: ['−', 'removed'],
    changed: ['→', 'changed from']
  };
  var TRACE_OPEN_DEPTH = 3;

  function traceSpan(attr, text) {
    var span = document.createElement('span');
    span.setAttribute(attr, '');
    span.textContent = text;
    return span;
  }

  function traceMark(change) {
    var spec = TRACE_MARKS[change];
    var mark = traceSpan('data-q-flow-mark', spec[0]);
    if (spec[1]) {
      var spoken = document.createElement('span');
      spoken.className = 'q-visually-hidden';
      spoken.textContent = spec[1];
      mark.appendChild(spoken);
    }
    return mark;
  }

  /**
   * Builds the list item for one diffed field. Branches nest as `details` and start open while
   * shallow or holding a change; values are written with textContent only.
   */
  function renderTraceField(field, depth) {
    var li = document.createElement('li');
    li.setAttribute('data-q-flow-field', '');
    li.setAttribute('data-q-flow-change', field.change);
    if (field.hasChange) {
      li.setAttribute('data-q-flow-has-change', '');
    }
    li.setAttribute('data-q-flow-depth', String(depth));
    var key = field.key === null ? null : traceSpan('data-q-flow-key', field.key + ': ');
    if (field.children) {
      var branch = document.createElement('details');
      branch.setAttribute('data-q-flow-branch', '');
      branch.open = depth < TRACE_OPEN_DEPTH || field.hasChange;
      var summary = document.createElement('summary');
      summary.appendChild(traceMark(field.change));
      if (key) {
        summary.appendChild(key);
      }
      var isList = Array.isArray(field.value);
      var size = isList ? field.value.length : Object.keys(field.value).length;
      summary.appendChild(traceSpan('data-q-flow-count', isList ? '[' + size + ']' : '{' + size + '}'));
      branch.appendChild(summary);
      var nested = document.createElement('ul');
      field.children.forEach(function (child) {
        nested.appendChild(renderTraceField(child, depth + 1));
      });
      branch.appendChild(nested);
      li.appendChild(branch);
      return li;
    }
    li.appendChild(traceMark(field.change));
    if (key) {
      li.appendChild(key);
    }
    if (field.change === 'changed') {
      li.appendChild(traceSpan('data-q-flow-old', JSON.stringify(field.old)));
      li.appendChild(document.createTextNode(' → '));
      var fresh = traceSpan('data-q-flow-new', JSON.stringify(field.value));
      fresh.setAttribute('data-q-flow-val', '');
      li.appendChild(fresh);
    } else {
      li.appendChild(traceSpan('data-q-flow-val', JSON.stringify(field.value)));
    }
    return li;
  }

  class QFlow extends HTMLElement {
    static get observedAttributes() {
      return ['summary', 'direction', 'groups'];
    }

    connectedCallback() {
      var self = this;
      this._uid = this._uid || uid('q-flow-');
      this._layoutSeq = (this._layoutSeq || 0) + 1;
      this._pulseFrame = 0;
      this._focusedNode = null;
      this._focusedGroup = null;
      this._focusedAfterExpand = false;
      this._rovingId = null;
      this._onDocKey = this._onDocKey || function (e) {
        if (e.key === 'Escape' && (self.hasAttribute('data-q-flow-expanded') || self._focusedNode || self._focusedGroup || self._trace)) {
          self._handleEscape(e);
        }
      };
      this._onResize = this._onResize || function () {
        if (self.isConnected && self._bounds && !self.hasAttribute('data-q-flow-expanded')) {
          self._fitBounds(self._bounds, false);
        }
      };
      document.addEventListener('keydown', this._onDocKey);
      window.addEventListener('resize', this._onResize);
      onTheme(this, function () {
        self._applyTheme();
      });
      watchChildren(this, { childList: true, characterData: true, subtree: true }, function () {
        if (self.isConnected && self._signature() !== self._lastSig) {
          self._setup();
        }
      });
    }

    _signature() {
      var script = this.querySelector(':scope > script[type="application/json"]');
      return [
        script ? (script.textContent || '') : '',
        this.getAttribute('summary') || '',
        this.getAttribute('direction') || '',
        this.getAttribute('groups') || ''
      ].join('\u0000');
    }

    disconnectedCallback() {
      this._stopPulse();
      this._stopTracePlay();
      if (this._onDocKey) {
        document.removeEventListener('keydown', this._onDocKey);
      }
      if (this._onResize) {
        window.removeEventListener('resize', this._onResize);
      }
      var stopTheme = themeWatchers.get(this);
      if (stopTheme) {
        stopTheme();
      }
    }

    attributeChangedCallback() {
      if (this.isConnected && this._initialized && this._signature() !== this._lastSig) {
        this._setup();
      }
    }

    _parseData() {
      var script = this.querySelector(':scope > script[type="application/json"]');
      if (!script) {
        return null;
      }
      var raw;
      try {
        raw = JSON.parse(script.textContent || '');
      } catch (_e) {
        return null;
      }
      if (!isRow(raw) || hasCoordKeys(raw) || !Array.isArray(raw.nodes) || raw.nodes.length === 0 || raw.nodes.length > 200) {
        return null;
      }
      if (!flowGraphTextOk(raw)) {
        return null;
      }
      var kinds = isRow(raw.kinds) ? raw.kinds : {};
      var kindKeys = Object.keys(kinds);
      if (kindKeys.length > 8) {
        return null;
      }
      for (var k = 0; k < kindKeys.length; k += 1) {
        var c = kinds[kindKeys[k]];
        if (typeof c !== 'number' || c < 1 || c > 8 || Math.floor(c) !== c) {
          return null;
        }
      }
      var groups = Array.isArray(raw.groups) ? raw.groups : [];
      var edges = Array.isArray(raw.edges) ? raw.edges : [];
      var seenIds = {};
      var groupMap = {};
      for (var gi = 0; gi < groups.length; gi += 1) {
        var g = groups[gi];
        if (!isRow(g) || hasCoordKeys(g) || typeof g.id !== 'string' || !g.id || typeof g.label !== 'string' || !g.label) {
          return null;
        }
        if (seenIds[g.id]) {
          return null;
        }
        seenIds[g.id] = 'group';
        groupMap[g.id] = { id: g.id, label: g.label, parent: typeof g.parent === 'string' && g.parent ? g.parent : null };
      }
      for (var gj = 0; gj < groups.length; gj += 1) {
        var grp = groupMap[groups[gj].id];
        var walk = grp.parent;
        var visited = {};
        visited[grp.id] = true;
        while (walk) {
          if (!groupMap[walk] || visited[walk]) {
            return null;
          }
          visited[walk] = true;
          walk = groupMap[walk].parent;
        }
      }
      var nodeMap = {};
      var nodes = [];
      for (var ni = 0; ni < raw.nodes.length; ni += 1) {
        var n = raw.nodes[ni];
        if (!isRow(n) || hasCoordKeys(n) || typeof n.id !== 'string' || !n.id || typeof n.label !== 'string' || !n.label) {
          return null;
        }
        if (n.detail !== undefined && n.detail !== null && (typeof n.detail !== 'string' || !isValidFlowDetail(n.detail))) {
          return null;
        }
        if (seenIds[n.id]) {
          return null;
        }
        if (n.kind !== undefined && n.kind !== null) {
          if (typeof n.kind !== 'string' || !Object.prototype.hasOwnProperty.call(kinds, n.kind)) {
            return null;
          }
        }
        if (n.group !== undefined && n.group !== null) {
          if (typeof n.group !== 'string' || !groupMap[n.group]) {
            return null;
          }
        }
        var shape = 'box';
        if (n.shape !== undefined && n.shape !== null) {
          if (n.shape !== 'box' && n.shape !== 'decision' && n.shape !== 'subprocess') {
            return null;
          }
          shape = n.shape;
        }
        var flow = null;
        if (n.flow !== undefined && n.flow !== null) {
          if (shape !== 'subprocess' || typeof n.flow !== 'string' || isBlankFlowId(n.flow)) {
            return null;
          }
          flow = n.flow;
        }
        seenIds[n.id] = 'node';
        var cleanNode = {
          id: n.id,
          label: n.label,
          kind: typeof n.kind === 'string' ? n.kind : null,
          group: typeof n.group === 'string' ? n.group : null,
          detail: typeof n.detail === 'string' ? n.detail : null,
          shape: shape,
          flow: flow
        };
        nodeMap[n.id] = cleanNode;
        nodes.push(cleanNode);
      }
      var groupsMode = (this.getAttribute('groups') || 'panels').toLowerCase() === 'lanes' ? 'lanes' : 'panels';
      var topGroups = groups.filter(function (g) { return !groupMap[g.id].parent; });
      if (groupsMode === 'lanes') {
        if (topGroups.length === 0) {
          return null;
        }
        for (var nl = 0; nl < nodes.length; nl += 1) {
          if (!nodes[nl].group) {
            return null;
          }
        }
      }
      var cleanEdges = [];
      var edgeRefs = Object.create(null);
      for (var ei = 0; ei < edges.length; ei += 1) {
        var e = edges[ei];
        if (!isRow(e) || hasCoordKeys(e) || typeof e.from !== 'string' || typeof e.to !== 'string') {
          return null;
        }
        if (!nodeMap[e.from] || !nodeMap[e.to]) {
          return null;
        }
        if (e.loop !== undefined && e.loop !== null && typeof e.loop !== 'boolean') {
          return null;
        }
        var ref = null;
        if (e.id !== undefined) {
          if (typeof e.id !== 'string' || !e.id.trim() || Object.prototype.hasOwnProperty.call(edgeRefs, e.id)) {
            return null;
          }
          ref = e.id;
          edgeRefs[ref] = ei;
        }
        cleanEdges.push({
          id: 'e' + ei,
          ref: ref,
          index: ei,
          from: e.from,
          to: e.to,
          label: typeof e.label === 'string' && e.label.trim() ? e.label.trim() : null,
          async: e.async === true,
          loop: e.loop === true || e.from === e.to
        });
      }
      for (var di = 0; di < nodes.length; di += 1) {
        if (nodes[di].shape !== 'decision') {
          continue;
        }
        var exits = cleanEdges.filter(function (ce) { return ce.from === nodes[di].id; });
        if (exits.length < 2 || exits.some(function (ce) { return !ce.label; })) {
          return null;
        }
      }
      var traces = parseFlowTraces(raw.traces, nodeMap, cleanEdges, edgeRefs);
      if (!traces) {
        return null;
      }
      return {
        kinds: kinds,
        groups: groups.map(function (g) { return groupMap[g.id]; }),
        groupMap: groupMap,
        nodes: nodes,
        nodeMap: nodeMap,
        edges: cleanEdges,
        traces: traces,
        direction: (this.getAttribute('direction') || 'right').toLowerCase() === 'down' ? 'down' : 'right',
        groupsMode: groupsMode
      };
    }

    _ensureScaffold(data) {
      var stage = this.querySelector(':scope > [data-q-flow-stage]');
      if (!stage) {
        stage = kitNode('div');
        stage.className = 'q-flow-stage';
        stage.setAttribute('data-q-flow-stage', '');
        var existingDetails = this.querySelector(':scope > details[data-q-flow-list]');
        if (existingDetails) {
          this.insertBefore(stage, existingDetails);
        } else {
          this.appendChild(stage);
        }
      }
      var details = this.querySelector(':scope > details[data-q-flow-list]');
      if (!details) {
        details = kitNode('details');
        details.className = 'q-flow-list';
        details.setAttribute('data-q-flow-list', '');
        details.open = true;
        this.appendChild(details);
      }
      if (data) {
        this._populateList(details, data);
      }
      this._stage = stage;
      this._buildTracePanel(data);
      var live = this.querySelector(':scope > [data-q-flow-live]');
      if (!live) {
        live = kitNode('div');
        live.className = 'q-visually-hidden';
        live.setAttribute('aria-live', 'polite');
        live.setAttribute('data-q-flow-live', '');
        this.appendChild(live);
      }
      this._stage = stage;
      this._details = details;
      this._live = live;
    }

    /**
     * Creates the trace panel beside the stage, or drops it when the graph has no traces. The
     * panel starts closed; `_openTrace` shows it. The shell is rebuilt on every layout so the
     * picker always matches the traces in the payload.
     */
    _buildTracePanel(data) {
      var self = this;
      var panel = this.querySelector(':scope > [data-q-flow-trace-panel]');
      this._traceEls = null;
      if (!data || data.traces.length === 0) {
        if (panel) {
          panel.remove();
        }
        this._tracePanel = null;
        return;
      }
      if (!panel) {
        panel = kitNode('aside');
        panel.className = 'q-flow-trace';
        panel.setAttribute('data-q-flow-trace-panel', '');
        panel.setAttribute('aria-label', 'Trace');
        panel.setAttribute('tabindex', '-1');
        this.insertBefore(panel, this._stage.nextSibling);
      }
      panel.setAttribute('data-q-inactive', '');
      while (panel.firstChild) {
        panel.removeChild(panel.firstChild);
      }

      function part(tag, attr, cls) {
        var el = document.createElement(tag);
        el.setAttribute(attr, '');
        if (cls) {
          el.className = cls;
        }
        return el;
      }

      function button(attr, text) {
        var btn = part('button', attr);
        btn.type = 'button';
        btn.textContent = text;
        return btn;
      }

      var pickerRow = document.createElement('div');
      pickerRow.className = 'q-flow-trace-pick';
      var pickerId = this._uid + '-trace-picker';
      var pickerLabel = document.createElement('label');
      pickerLabel.setAttribute('for', pickerId);
      pickerLabel.textContent = 'Trace';
      var picker = part('select', 'data-q-flow-trace-picker');
      picker.id = pickerId;
      data.traces.forEach(function (trace) {
        var option = document.createElement('option');
        option.value = trace.id;
        option.textContent = trace.label;
        picker.appendChild(option);
      });
      pickerRow.appendChild(pickerLabel);
      pickerRow.appendChild(picker);
      panel.appendChild(pickerRow);

      var counter = part('p', 'data-q-flow-trace-counter', 'q-flow-trace-counter');
      counter.setAttribute('aria-live', 'polite');
      panel.appendChild(counter);

      var buttons = document.createElement('div');
      buttons.className = 'q-flow-trace-buttons';
      var back = button('data-q-flow-trace-back', 'Back');
      var next = button('data-q-flow-trace-next', 'Next');
      var play = button('data-q-flow-trace-play', 'Play');
      play.setAttribute('aria-pressed', 'false');
      buttons.appendChild(back);
      buttons.appendChild(next);
      buttons.appendChild(play);
      panel.appendChild(buttons);

      var dots = part('ol', 'data-q-flow-trace-dots', 'q-flow-trace-dots');
      panel.appendChild(dots);

      var note = part('p', 'data-q-flow-trace-note', 'q-flow-trace-note');
      note.setAttribute('data-q-inactive', '');
      panel.appendChild(note);

      var toggle = document.createElement('label');
      toggle.className = 'q-flow-trace-toggle';
      var changes = part('input', 'data-q-flow-trace-changes');
      changes.type = 'checkbox';
      toggle.appendChild(changes);
      toggle.appendChild(document.createTextNode(' Changes only'));
      panel.appendChild(toggle);

      var value = part('div', 'data-q-flow-trace-value', 'q-flow-trace-value');
      panel.appendChild(value);

      back.addEventListener('click', function () {
        self._traceStepBy(-1);
      });
      next.addEventListener('click', function () {
        self._traceStepBy(1);
      });
      play.addEventListener('click', function () {
        self._toggleTracePlay();
      });
      if (!panel._qFlowKeys) {
        // the panel outlives re-layouts, so the listener is installed once and reads the live picker
        panel._qFlowKeys = true;
        panel.addEventListener('keydown', function (ev) {
          var els = self._traceEls;
          if (!els || ev.target === els.picker || ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey) {
            return;
          }
          var delta = 0;
          if (ev.key === 'ArrowRight' || ev.key === 'ArrowDown') {
            delta = 1;
          } else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowUp') {
            delta = -1;
          }
          if (delta !== 0 && self._trace) {
            ev.preventDefault();
            self._traceStepBy(delta);
          }
        });
      }
      picker.addEventListener('change', function () {
        self._stopTracePlay();
        self._startTrace(picker.selectedIndex);
      });
      changes.addEventListener('change', function () {
        self._traceChangesOnly = changes.checked;
        if (self._trace) {
          self._renderTraceValue(self._trace.step);
        }
      });

      this._tracePanel = panel;
      this._traceEls = {
        picker: picker,
        counter: counter,
        back: back,
        next: next,
        play: play,
        dots: dots,
        note: note,
        changes: changes,
        value: value
      };
    }

    _populateList(details, data) {
      while (details.firstChild) {
        details.removeChild(details.firstChild);
      }
      var summary = document.createElement('summary');
      summary.textContent = 'Graph as a list';
      details.appendChild(summary);

      var body = document.createElement('div');
      body.setAttribute('data-q-flow-list-body', '');

      var outByNode = {};
      data.edges.forEach(function (e) {
        if (!outByNode[e.from]) {
          outByNode[e.from] = [];
        }
        outByNode[e.from].push(e);
      });

      function renderNodeItem(n) {
        var li = document.createElement('li');
        li.setAttribute('data-q-flow-list-node', n.id);
        var title = document.createElement('strong');
        title.textContent = n.label;
        li.appendChild(title);
        var titleMeta = [];
        if (n.shape !== 'box') {
          titleMeta.push(n.shape);
        }
        if (n.kind) {
          titleMeta.push(n.kind);
        }
        if (titleMeta.length) {
          li.appendChild(document.createTextNode(' (' + titleMeta.join(', ') + ')'));
        }
        var outs = outByNode[n.id] || [];
        if (n.shape === 'subprocess' && n.flow) {
          li.appendChild(document.createTextNode(': '));
          var flowLink = document.createElement('a');
          flowLink.setAttribute('href', '#' + n.flow);
          flowLink.textContent = 'opens the "' + n.flow + '" graph';
          li.appendChild(flowLink);
        }
        if (n.shape === 'decision') {
          li.appendChild(document.createTextNode(': ' + outs.map(function (e) {
            var exitTarget = data.nodeMap[e.to] ? data.nodeMap[e.to].label : e.to;
            return (e.label || '') + (e.loop ? ' \u21a9 ' : ' \u2192 ') + exitTarget + (e.async ? ' (async)' : '');
          }).join(', ')));
        }
        if (n.detail) {
          var det = document.createElement('div');
          det.setAttribute('data-q-flow-list-detail', '');
          det.appendChild(sanitizeFlowDetail(n.detail));
          li.appendChild(det);
        }
        if (outs.length && n.shape !== 'decision') {
          var edgeUl = document.createElement('ul');
          outs.forEach(function (e) {
            var eli = document.createElement('li');
            var targetLabel = data.nodeMap[e.to] ? data.nodeMap[e.to].label : e.to;
            if (e.loop) {
              eli.textContent = '\u21a9 returns to ' + (e.from === e.to ? 'itself' : targetLabel)
                + (e.label ? ': ' + e.label : '') + (e.async ? ' (async)' : '');
              edgeUl.appendChild(eli);
              return;
            }
            var meta = [];
            if (e.label) {
              meta.push(e.label);
            }
            if (e.async) {
              meta.push('async');
            }
            eli.textContent = '\u2192 ' + targetLabel + (meta.length ? ' (' + meta.join(', ') + ')' : '');
            edgeUl.appendChild(eli);
          });
          li.appendChild(edgeUl);
        }
        return li;
      }

      function renderGroupItem(g) {
        var li = document.createElement('li');
        li.setAttribute('data-q-flow-list-group', g.id);
        var title = document.createElement('strong');
        title.textContent = g.label;
        li.appendChild(title);
        var subUl = document.createElement('ul');
        data.groups.forEach(function (childG) {
          if (childG.parent === g.id) {
            subUl.appendChild(renderGroupItem(childG));
          }
        });
        data.nodes.forEach(function (n) {
          if (n.group === g.id) {
            subUl.appendChild(renderNodeItem(n));
          }
        });
        if (subUl.firstChild) {
          li.appendChild(subUl);
        }
        return li;
      }

      var rootUl = document.createElement('ul');
      data.groups.forEach(function (g) {
        if (!g.parent) {
          rootUl.appendChild(renderGroupItem(g));
        }
      });
      data.nodes.forEach(function (n) {
        if (!n.group) {
          rootUl.appendChild(renderNodeItem(n));
        }
      });
      body.appendChild(rootUl);
      data.traces.forEach(function (trace) {
        var block = document.createElement('div');
        block.setAttribute('data-q-flow-list-trace', trace.id);
        var heading = document.createElement('p');
        var headingText = document.createElement('strong');
        headingText.textContent = 'Trace: ' + trace.label;
        heading.appendChild(headingText);
        block.appendChild(heading);
        var ol = document.createElement('ol');
        trace.steps.forEach(function (step, i) {
          var li = document.createElement('li');
          li.setAttribute('data-q-flow-list-step', String(i + 1));
          var text = data.nodeMap[step.node].label;
          var edge = step.edge === null ? null : data.edges[step.edge];
          if (edge && (step.via !== null || edge.loop)) {
            text += edge.label
              ? ', via "' + edge.label + '"'
              : (step.via !== null ? ', via "' + step.via + '"' : ', around the loop');
          }
          if (step.note) {
            text += ': ' + step.note;
          }
          li.appendChild(document.createTextNode(text));
          var pre = document.createElement('pre');
          var code = document.createElement('code');
          code.textContent = tracePretty(step.value);
          pre.appendChild(code);
          li.appendChild(pre);
          ol.appendChild(li);
        });
        block.appendChild(ol);
        body.appendChild(block);
      });
      details.appendChild(body);
    }

    _failLayout(msg) {
      this._stopPulse();
      if (this._stage) {
        while (this._stage.firstChild) {
          this._stage.removeChild(this._stage.firstChild);
        }
        var p = document.createElement('p');
        p.className = 'q-flow-notice';
        p.setAttribute('data-q-flow-notice', '');
        p.textContent = msg;
        this._stage.appendChild(p);
      }
      if (this._details) {
        this._details.open = true;
      }
      this.setAttribute('data-q-flow-ready', 'error');
    }

    _measureTextFactory() {
      var canvas = document.createElement('canvas');
      var ctx = canvas.getContext && canvas.getContext('2d');
      var fontFamily = getComputedStyle(this).fontFamily || 'sans-serif';
      return function (text, sizePx, weight) {
        if (!text) {
          return 0;
        }
        if (ctx) {
          ctx.font = (weight || '400') + ' ' + sizePx + 'px ' + fontFamily;
          return Math.ceil(ctx.measureText(text).width);
        }
        return Math.ceil(String(text).length * sizePx * 0.6);
      };
    }

    _setup() {
      var self = this;
      this._initialized = true;
      this._lastSig = this._signature();
      this.removeAttribute('data-q-flow-ready');
      this._stopTracePlay();
      if (this._trace) {
        this._closeTrace(false);
      }
      this._traceChangesOnly = false;
      this._lastTraceIndex = 0;
      var data = this._parseData();
      this._ensureScaffold(data);
      if (!data) {
        this._failLayout('This graph could not be drawn. The full graph is listed below.');
        return;
      }
      if (!window.quirkFlow || typeof window.quirkFlow.ELK !== 'function') {
        this._failLayout('This graph could not be drawn. The full graph is listed below.');
        return;
      }
      this._data = data;
      var seq = ++this._layoutSeq;
      var fontsReady = (document.fonts && document.fonts.ready && typeof document.fonts.ready.then === 'function')
        ? document.fonts.ready.catch(function () {})
        : Promise.resolve();

      fontsReady.then(function () {
        if (!self.isConnected || seq !== self._layoutSeq) {
          return;
        }
        self._runLayout(data, seq);
      });
    }

    _runLayout(data, seq) {
      var self = this;
      var measure = this._measureTextFactory();
      var nodeSizes = {};
      var decisionLines = {};
      data.nodes.forEach(function (n) {
        if (n.shape === 'decision') {
          var lines = wrapFlowLabel(n.label, measure);
          var widest = Math.max.apply(null, lines.map(function (line) { return measure(line, 13, '600'); }));
          decisionLines[n.id] = lines;
          nodeSizes[n.id] = {
            width: Math.max(96, 2 * (widest + 12)),
            height: Math.max(64, 2 * (lines.length * FLOW_DECISION_LINE_HEIGHT + 8))
          };
          return;
        }
        var labelW = measure(n.label, 13, '600');
        var kindW = n.kind ? measure(n.kind.toUpperCase(), 10, '600') + 8 : 0;
        nodeSizes[n.id] = {
          width: Math.max(112, Math.max(labelW, kindW) + 28) + (n.shape === 'subprocess' ? FLOW_SUBPROCESS_EXTRA : 0),
          height: n.kind ? 48 : 38
        };
      });
      this._decisionLines = decisionLines;

      var topLanes = data.groups.filter(function (g) { return !g.parent; });
      var laneIndexByGroup = {};
      topLanes.forEach(function (g, idx) {
        laneIndexByGroup[g.id] = idx;
      });
      function topLaneIndex(groupId) {
        var cur = groupId;
        while (cur && data.groupMap[cur]) {
          if (!data.groupMap[cur].parent) {
            return laneIndexByGroup[cur];
          }
          cur = data.groupMap[cur].parent;
        }
        return 0;
      }

      function buildElkGroup(g) {
        var opts = {
          'elk.padding': '[top=38,left=18,bottom=18,right=18]'
        };
        if (data.groupsMode === 'lanes') {
          opts['elk.partitioning.partition'] = String(topLaneIndex(g.id));
        }
        var children = [];
        data.groups.forEach(function (cg) {
          if (cg.parent === g.id) {
            children.push(buildElkGroup(cg));
          }
        });
        data.nodes.forEach(function (n) {
          if (n.group === g.id) {
            var nOpts = {};
            if (data.groupsMode === 'lanes') {
              nOpts['elk.partitioning.partition'] = String(topLaneIndex(g.id));
            }
            children.push({
              id: n.id,
              width: nodeSizes[n.id].width,
              height: nodeSizes[n.id].height,
              layoutOptions: nOpts
            });
          }
        });
        var minW = Math.max(120, measure(g.label, 12, '600') + 36);
        return {
          id: g.id,
          width: minW,
          height: 60,
          layoutOptions: opts,
          children: children
        };
      }

      var rootChildren = [];
      data.groups.forEach(function (g) {
        if (!g.parent) {
          rootChildren.push(buildElkGroup(g));
        }
      });
      data.nodes.forEach(function (n) {
        if (!n.group) {
          rootChildren.push({
            id: n.id,
            width: nodeSizes[n.id].width,
            height: nodeSizes[n.id].height
          });
        }
      });

      var elkEdges = data.edges.map(function (e) {
        var labels = [];
        if (e.label) {
          var labelText = (e.loop ? FLOW_LOOP_PREFIX : '') + e.label;
          labels.push({
            text: labelText,
            width: measure(labelText, 11, '500') + 14,
            height: 20
          });
        }
        var turned = e.loop && e.from !== e.to;
        return {
          id: e.id,
          sources: [turned ? e.to : e.from],
          targets: [turned ? e.from : e.to],
          labels: labels
        };
      });

      var rootOptions = {
        'elk.algorithm': 'layered',
        'elk.direction': data.direction === 'down' ? 'DOWN' : 'RIGHT',
        'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
        'elk.edgeRouting': 'ORTHOGONAL',
        'elk.json.shapeCoords': 'ROOT',
        'elk.json.edgeCoords': 'ROOT',
        'elk.layered.spacing.nodeNodeBetweenLayers': '52',
        'elk.spacing.nodeNode': '28',
        'elk.spacing.edgeNode': '24',
        'elk.edgeLabels.inline': 'true'
      };
      if (data.groupsMode === 'lanes') {
        rootOptions['elk.partitioning.activate'] = 'true';
      }

      var elkGraph = {
        id: 'root',
        layoutOptions: rootOptions,
        children: rootChildren,
        edges: elkEdges
      };

      try {
        var elk = new window.quirkFlow.ELK();
        Promise.resolve(elk.layout(elkGraph)).then(function (laidOut) {
          if (!self.isConnected || seq !== self._layoutSeq) {
            return;
          }
          if (!laidOut || !Array.isArray(laidOut.children)) {
            self._failLayout('This graph could not be drawn. The full graph is listed below.');
            return;
          }
          self._renderGraph(data, laidOut);
        }).catch(function () {
          if (!self.isConnected || seq !== self._layoutSeq) {
            return;
          }
          self._failLayout('This graph could not be drawn. The full graph is listed below.');
        });
      } catch (_err) {
        this._failLayout('This graph could not be drawn. The full graph is listed below.');
      }
    }

    _renderGraph(data, laidOut) {
      var self = this;
      var groupBoxes = {};
      var nodeBoxes = {};
      var groupOrder = [];

      function collectShapes(items, depth) {
        (items || []).forEach(function (item) {
          if (data.groupMap[item.id]) {
            groupBoxes[item.id] = {
              id: item.id,
              x: item.x || 0,
              y: item.y || 0,
              width: item.width || 120,
              height: item.height || 80,
              depth: depth
            };
            groupOrder.push(item.id);
            if (item.children) {
              collectShapes(item.children, depth + 1);
            }
          } else if (data.nodeMap[item.id]) {
            nodeBoxes[item.id] = {
              id: item.id,
              x: item.x || 0,
              y: item.y || 0,
              width: item.width || 112,
              height: item.height || 40
            };
          }
        });
      }
      collectShapes(laidOut.children, 0);

      var laidOutEdges = laidOut.edges || [];
      var edgeShapes = data.edges.map(function (edge, idx) {
        var le = laidOutEdges[idx] || {};
        var pts = [];
        (le.sections || []).forEach(function (sec) {
          if (sec.startPoint && pts.length === 0) {
            pts.push(sec.startPoint);
          }
          (sec.bendPoints || []).forEach(function (bp) {
            pts.push(bp);
          });
          if (sec.endPoint) {
            pts.push(sec.endPoint);
          }
        });
        var fbFrom = nodeBoxes[edge.from];
        var fbTo = nodeBoxes[edge.to];
        var arcLabel = null;
        if (pts.length >= 2) {
          if (edge.loop && edge.from !== edge.to) {
            pts.reverse();
          }
        } else if (edge.from === edge.to && fbFrom) {
          if (data.direction === 'down') {
            var sideX = fbFrom.x + fbFrom.width;
            pts = [
              { x: sideX, y: fbFrom.y + fbFrom.height * 0.35 },
              { x: sideX + 18, y: fbFrom.y + fbFrom.height * 0.35 },
              { x: sideX + 18, y: fbFrom.y + fbFrom.height * 0.65 },
              { x: sideX, y: fbFrom.y + fbFrom.height * 0.65 }
            ];
            arcLabel = { x: sideX + 24, y: fbFrom.y + fbFrom.height / 2 - 10, width: 60, height: 20 };
          } else {
            pts = [
              { x: fbFrom.x + fbFrom.width * 0.35, y: fbFrom.y },
              { x: fbFrom.x + fbFrom.width * 0.35, y: fbFrom.y - 18 },
              { x: fbFrom.x + fbFrom.width * 0.65, y: fbFrom.y - 18 },
              { x: fbFrom.x + fbFrom.width * 0.65, y: fbFrom.y }
            ];
            arcLabel = { x: fbFrom.x + fbFrom.width / 2 - 30, y: fbFrom.y - 42, width: 60, height: 20 };
          }
        } else if (fbFrom && fbTo) {
          pts = [
            { x: fbFrom.x + fbFrom.width, y: fbFrom.y + fbFrom.height / 2 },
            { x: fbTo.x, y: fbTo.y + fbTo.height / 2 }
          ];
        } else {
          pts = [{ x: 0, y: 0 }, { x: 10, y: 0 }];
        }
        if (fbFrom && data.nodeMap[edge.from].shape === 'decision') {
          pts = snapFlowEndToDiamond(pts, true, fbFrom);
        }
        if (fbTo && data.nodeMap[edge.to].shape === 'decision') {
          pts = snapFlowEndToDiamond(pts, false, fbTo);
        }
        return { pts: pts, arcLabel: arcLabel };
      });

      var minX = Infinity;
      var minY = Infinity;
      var maxX = -Infinity;
      var maxY = -Infinity;
      function expandBounds(x, y, w, h) {
        if (x < minX) { minX = x; }
        if (y < minY) { minY = y; }
        if (x + w > maxX) { maxX = x + w; }
        if (y + h > maxY) { maxY = y + h; }
      }
      Object.keys(groupBoxes).forEach(function (gid) {
        var b = groupBoxes[gid];
        expandBounds(b.x, b.y, b.width, b.height);
      });
      Object.keys(nodeBoxes).forEach(function (nid) {
        var b = nodeBoxes[nid];
        expandBounds(b.x, b.y, b.width, b.height);
      });
      (laidOut.edges || []).forEach(function (le) {
        (le.sections || []).forEach(function (sec) {
          if (sec.startPoint) { expandBounds(sec.startPoint.x, sec.startPoint.y, 0, 0); }
          if (sec.endPoint) { expandBounds(sec.endPoint.x, sec.endPoint.y, 0, 0); }
          (sec.bendPoints || []).forEach(function (bp) {
            expandBounds(bp.x, bp.y, 0, 0);
          });
        });
        (le.labels || []).forEach(function (lbl) {
          expandBounds(lbl.x || 0, lbl.y || 0, lbl.width || 0, lbl.height || 0);
        });
      });
      edgeShapes.forEach(function (es) {
        if (es.arcLabel) {
          es.pts.forEach(function (pt) {
            expandBounds(pt.x, pt.y, 0, 0);
          });
          expandBounds(es.arcLabel.x, es.arcLabel.y, es.arcLabel.width, es.arcLabel.height);
        }
      });
      if (!isFinite(minX)) {
        minX = 0; minY = 0; maxX = 320; maxY = 180;
      }

      if (data.groupsMode === 'lanes') {
        data.groups.forEach(function (g) {
          if (!g.parent && groupBoxes[g.id]) {
            var b = groupBoxes[g.id];
            if (data.direction === 'down') {
              b.x = minX;
              b.width = maxX - minX;
            } else {
              b.y = minY;
              b.height = maxY - minY;
            }
          }
        });
      }

      this._groupBoxes = groupBoxes;
      this._nodeBoxes = nodeBoxes;
      this._bounds = {
        x: minX - 20,
        y: minY - 20,
        width: Math.max(160, (maxX - minX) + 40),
        height: Math.max(100, (maxY - minY) + 40)
      };

      while (this._stage.firstChild) {
        this._stage.removeChild(this._stage.firstChild);
      }

      var capH = Math.min(640, Math.max(260, Math.round((window.innerHeight || 800) * 0.66)));
      var naturalH = Math.round(this._bounds.height + 56);
      this._stage.style.height = Math.max(240, Math.min(capH, naturalH)) + 'px';

      var uid = this._uid;
      var svg = svgNode('svg', {
        'class': 'q-flow-svg',
        'data-q-flow-svg': '',
        'role': 'group',
        'aria-label': this.getAttribute('summary') || 'Interactive graph'
      });

      var defs = svgNode('defs');
      var markerNorm = svgNode('marker', {
        id: 'q-flow-arrow-' + uid,
        viewBox: '0 0 10 10',
        refX: '9',
        refY: '5',
        markerWidth: '6',
        markerHeight: '6',
        orient: 'auto-start-reverse'
      });
      markerNorm.appendChild(svgNode('path', { d: 'M 0 1 L 10 5 L 0 9 z', fill: 'var(--q-color-text-muted)' }));
      defs.appendChild(markerNorm);

      var markerLit = svgNode('marker', {
        id: 'q-flow-arrow-lit-' + uid,
        viewBox: '0 0 10 10',
        refX: '9',
        refY: '5',
        markerWidth: '6',
        markerHeight: '6',
        orient: 'auto-start-reverse'
      });
      markerLit.appendChild(svgNode('path', { d: 'M 0 1 L 10 5 L 0 9 z', fill: 'var(--q-color-accent)' }));
      defs.appendChild(markerLit);

      [['q-flow-return-', 'var(--q-color-text-muted)'], ['q-flow-return-lit-', 'var(--q-color-accent)']].forEach(function (spec) {
        var returnMarker = svgNode('marker', {
          id: spec[0] + uid,
          viewBox: '0 0 10 10',
          refX: '5',
          refY: '5',
          markerWidth: '6',
          markerHeight: '6',
          orient: 'auto'
        });
        returnMarker.appendChild(svgNode('circle', {
          cx: '5',
          cy: '5',
          r: '3',
          fill: 'var(--q-color-bg)',
          stroke: spec[1],
          'stroke-width': '1.5'
        }));
        defs.appendChild(returnMarker);
      });

      var grad = svgNode('radialGradient', { id: 'q-flow-grad-' + uid });
      grad.appendChild(svgNode('stop', { offset: '0%', 'stop-color': '#ffffff', 'stop-opacity': '1' }));
      grad.appendChild(svgNode('stop', { offset: '55%', 'stop-color': '#ffffff', 'stop-opacity': '1' }));
      grad.appendChild(svgNode('stop', { offset: '100%', 'stop-color': '#ffffff', 'stop-opacity': '0' }));
      defs.appendChild(grad);
      svg.appendChild(defs);

      var viewport = svgNode('g', { 'data-q-flow-viewport': '' });
      var groupsLayer = svgNode('g', { 'data-q-flow-groups': '' });
      var edgesLayer = svgNode('g', { 'data-q-flow-edges': '' });
      var nodesLayer = svgNode('g', { 'data-q-flow-nodes': '' });
      viewport.appendChild(groupsLayer);
      viewport.appendChild(edgesLayer);
      viewport.appendChild(nodesLayer);
      svg.appendChild(viewport);

      groupOrder.forEach(function (gid) {
        var g = data.groupMap[gid];
        var box = groupBoxes[gid];
        if (!g || !box) {
          return;
        }
        var isLane = data.groupsMode === 'lanes' && !g.parent;
        var gEl = svgNode('g', {
          'class': 'q-flow-group',
          'data-q-flow-group': gid,
          'data-q-flow-lane': isLane ? 'true' : 'false'
        });
        var tint = isLane
          ? 'color-mix(in srgb, var(--q-color-surface) 65%, var(--q-color-bg))'
          : (box.depth === 0
            ? 'color-mix(in srgb, var(--q-color-accent) 6%, var(--q-color-surface))'
            : 'color-mix(in srgb, var(--q-color-accent) 12%, var(--q-color-surface))');
        gEl.appendChild(svgNode('rect', {
          'data-q-flow-group-box': '',
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
          rx: isLane ? 4 : 8,
          fill: tint,
          stroke: 'var(--q-color-border)',
          'stroke-width': '1'
        }));
        var headerG = svgNode('g', {
          'data-q-flow-group-header': gid,
          'role': 'button',
          'aria-label': 'Focus group ' + g.label
        });
        headerG.appendChild(svgNode('rect', {
          x: box.x,
          y: box.y,
          width: box.width,
          height: 28,
          rx: isLane ? 4 : 8,
          fill: 'transparent'
        }));
        headerG.appendChild(svgNode('line', {
          x1: box.x,
          y1: box.y + 28,
          x2: box.x + box.width,
          y2: box.y + 28,
          stroke: 'var(--q-color-border)',
          'stroke-width': '1'
        }));
        var hText = svgNode('text', {
          x: box.x + 12,
          y: box.y + 18,
          fill: 'var(--q-color-text)',
          'font-size': '12',
          'font-weight': '600'
        });
        hText.textContent = g.label;
        headerG.appendChild(hText);
        headerG.addEventListener('click', function (ev) {
          ev.stopPropagation();
          if (self._trace) {
            self._closeTrace(false);
          }
          self._focusGroup(gid);
        });
        gEl.appendChild(headerG);
        groupsLayer.appendChild(gEl);
      });

      this._edgeRecords = [];
      data.edges.forEach(function (edge, idx) {
        var le = laidOutEdges[idx] || {};
        var pts = edgeShapes[idx].pts;
        var d = edge.from === edge.to
          ? roundedFlowPath(pts, 8)
          : pts.map(function (p, i) {
            return (i === 0 ? 'M ' : 'L ') + p.x + ' ' + p.y;
          }).join(' ');

        var maskId = 'q-flow-mask-' + uid + '-' + idx;
        var mask = svgNode('mask', {
          id: maskId,
          maskUnits: 'userSpaceOnUse',
          x: self._bounds.x - 40,
          y: self._bounds.y - 40,
          width: self._bounds.width + 80,
          height: self._bounds.height + 80
        });
        var maskDot = svgNode('circle', {
          'data-q-flow-mask-dot': '',
          cx: pts[0].x,
          cy: pts[0].y,
          r: '24',
          fill: 'url(#q-flow-grad-' + uid + ')'
        });
        mask.appendChild(maskDot);
        defs.appendChild(mask);

        var eG = svgNode('g', {
          'class': 'q-flow-edge',
          'data-q-flow-edge': String(idx),
          'data-q-flow-from': edge.from,
          'data-q-flow-to': edge.to,
          'data-q-flow-async': edge.async ? 'true' : 'false'
        });
        if (edge.loop) {
          eG.setAttribute('data-q-flow-loop', '');
        }
        var lineAttrs = {
          'data-q-flow-edge-line': '',
          d: d,
          fill: 'none',
          stroke: 'var(--q-color-text-muted)',
          'stroke-width': '1.75',
          'marker-end': 'url(#q-flow-arrow-' + uid + ')'
        };
        if (edge.async) {
          lineAttrs['stroke-dasharray'] = '6 4';
        }
        if (edge.loop) {
          lineAttrs['marker-start'] = 'url(#q-flow-return-' + uid + ')';
        }
        var basePath = svgNode('path', lineAttrs);
        eG.appendChild(basePath);

        var pulseAttrs = {
          'data-q-flow-edge-pulse': '',
          'data-q-inactive': '',
          d: d,
          fill: 'none',
          stroke: 'var(--q-color-accent)',
          'stroke-width': '6',
          'stroke-linecap': 'round',
          mask: 'url(#' + maskId + ')'
        };
        if (edge.async) {
          pulseAttrs['stroke-dasharray'] = '6 4';
        }
        var pulsePath = svgNode('path', pulseAttrs);
        eG.appendChild(pulsePath);

        if (edge.label) {
          var lbl = (le.labels && le.labels[0]) || edgeShapes[idx].arcLabel || {
            x: (pts[0].x + pts[pts.length - 1].x) / 2 - 30,
            y: (pts[0].y + pts[pts.length - 1].y) / 2 - 10,
            width: 60,
            height: 20
          };
          var lblG = svgNode('g', { 'data-q-flow-edge-label': '' });
          lblG.appendChild(svgNode('rect', {
            x: lbl.x,
            y: lbl.y,
            width: lbl.width,
            height: lbl.height,
            rx: '4',
            fill: 'var(--q-color-bg)',
            stroke: 'var(--q-color-border)',
            'stroke-width': '1'
          }));
          var lblT = svgNode('text', {
            x: lbl.x + lbl.width / 2,
            y: lbl.y + 14,
            'text-anchor': 'middle',
            fill: 'var(--q-color-text-muted)',
            'font-size': '11'
          });
          lblT.textContent = (edge.loop ? FLOW_LOOP_PREFIX : '') + edge.label;
          lblG.appendChild(lblT);
          eG.appendChild(lblG);
        }

        edgesLayer.appendChild(eG);
        self._edgeRecords.push({
          edge: edge,
          groupEl: eG,
          basePath: basePath,
          pulsePath: pulsePath,
          mask: mask,
          maskDots: [maskDot],
          points: pts
        });
      });

      this._rovingId = data.nodes[0].id;
      this._nodeElements = {};
      data.nodes.forEach(function (node, idx) {
        var box = nodeBoxes[node.id];
        if (!box) {
          return;
        }
        var colorIdx = node.kind ? data.kinds[node.kind] : null;
        var stripeColor = colorIdx ? 'var(--q-color-chart-' + colorIdx + ')' : 'var(--q-color-border)';
        var ariaMeta = [];
        if (node.shape !== 'box') {
          ariaMeta.push(node.shape);
        }
        if (node.kind) {
          ariaMeta.push(node.kind);
        }
        var nG = svgNode('g', {
          'class': 'q-flow-node',
          'data-q-flow-node': node.id,
          'data-q-flow-kind': node.kind || '',
          'data-q-flow-shape': node.shape,
          'role': 'button',
          'tabindex': idx === 0 ? '0' : '-1',
          'aria-label': node.label + (ariaMeta.length ? ' (' + ariaMeta.join(', ') + ')' : '')
        });
        if (node.shape === 'decision') {
          var cx = box.x + box.width / 2;
          var cy = box.y + box.height / 2;
          nG.appendChild(svgNode('polygon', {
            'data-q-flow-box': '',
            points: [
              cx + ',' + box.y,
              (box.x + box.width) + ',' + cy,
              cx + ',' + (box.y + box.height),
              box.x + ',' + cy
            ].join(' '),
            fill: 'var(--q-color-surface)',
            stroke: colorIdx ? stripeColor : 'var(--q-color-border)',
            'stroke-width': colorIdx ? '2' : '1'
          }));
          var dLines = (self._decisionLines && self._decisionLines[node.id]) || [node.label];
          var dText = svgNode('text', {
            'data-q-flow-label': '',
            'text-anchor': 'middle',
            fill: 'var(--q-color-text)',
            'font-size': '13',
            'font-weight': '600'
          });
          dLines.forEach(function (line, li) {
            var tspan = svgNode('tspan', {
              x: cx,
              y: cy + (li - (dLines.length - 1) / 2) * FLOW_DECISION_LINE_HEIGHT + 4.5
            });
            tspan.textContent = line;
            dText.appendChild(tspan);
          });
          nG.appendChild(dText);
        } else {
          var inset = node.shape === 'subprocess' ? FLOW_SUBPROCESS_EXTRA : 0;
          nG.appendChild(svgNode('rect', {
            'data-q-flow-box': '',
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            rx: '6',
            fill: 'var(--q-color-surface)',
            stroke: 'var(--q-color-border)',
            'stroke-width': '1'
          }));
          if (node.shape === 'subprocess') {
            [box.x + 8, box.x + box.width - 8].forEach(function (ruleX) {
              nG.appendChild(svgNode('line', {
                'data-q-flow-subprocess-rule': '',
                x1: ruleX,
                y1: box.y,
                x2: ruleX,
                y2: box.y + box.height,
                stroke: 'var(--q-color-border)',
                'stroke-width': '1'
              }));
            });
          }
          nG.appendChild(svgNode('rect', {
            'data-q-flow-stripe': '',
            x: box.x + inset,
            y: box.y,
            width: '4',
            height: box.height,
            rx: '2',
            fill: stripeColor
          }));
          if (node.kind) {
            var kText = svgNode('text', {
              'data-q-flow-kind-label': '',
              x: box.x + 12 + inset,
              y: box.y + 16,
              fill: 'var(--q-color-text-muted)',
              'font-size': '10',
              'font-weight': '600',
              'letter-spacing': '0.06em'
            });
            kText.textContent = node.kind.toUpperCase();
            nG.appendChild(kText);
            var lText = svgNode('text', {
              'data-q-flow-label': '',
              x: box.x + 12 + inset,
              y: box.y + 34,
              fill: 'var(--q-color-text)',
              'font-size': '13',
              'font-weight': '600'
            });
            lText.textContent = node.label;
            nG.appendChild(lText);
          } else {
            var cText = svgNode('text', {
              'data-q-flow-label': '',
              x: box.x + 12 + inset,
              y: box.y + 24,
              fill: 'var(--q-color-text)',
              'font-size': '13',
              'font-weight': '600'
            });
            cText.textContent = node.label;
            nG.appendChild(cText);
          }
        }

        nG.addEventListener('click', function (ev) {
          ev.stopPropagation();
          self._setRoving(node.id, false);
          if (self._trace) {
            self._traceNodeClick(node.id);
          } else {
            self._focusNode(node.id);
          }
        });
        nG.addEventListener('keydown', function (ev) {
          self._onNodeKey(ev, node.id);
        });
        nodesLayer.appendChild(nG);
        self._nodeElements[node.id] = nG;
      });

      svg.addEventListener('click', function (ev) {
        if ((ev.target === svg || ev.target === viewport) && !self._trace) {
          self._clearFocus();
        }
      });
      svg.addEventListener('keydown', function (ev) {
        self._onGraphKey(ev);
      });

      this._svg = svg;
      this._viewport = viewport;
      this._stage.appendChild(svg);
      this._buildControls();
      this._buildDrawer();
      this._setupZoom();
      this._fitBounds(this._bounds, false);

      if (this._details) {
        this._details.open = false;
      }
      this.setAttribute('data-q-flow-ready', 'true');
    }

    _buildControls() {
      var self = this;
      var bar = kitNode('div');
      bar.className = 'q-flow-controls';
      bar.setAttribute('data-q-flow-controls', '');
      bar.setAttribute('role', 'toolbar');
      bar.setAttribute('aria-label', 'Graph controls');

      function addBtn(action, label, text) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.setAttribute('data-q-flow-action', action);
        btn.setAttribute('aria-label', label);
        btn.textContent = text;
        btn.addEventListener('click', function (ev) {
          ev.stopPropagation();
          if (action === 'zoom-in') {
            self._zoomBy(1.25);
          } else if (action === 'zoom-out') {
            self._zoomBy(0.8);
          } else if (action === 'fit') {
            self._fitBounds(self._bounds, false);
          } else if (action === 'trace') {
            if (self._trace) {
              self._closeTrace(true);
            } else {
              self._openTrace(self._lastTraceIndex || 0);
            }
          } else if (action === 'expand') {
            self._toggleExpand();
          }
        });
        bar.appendChild(btn);
        return btn;
      }

      addBtn('zoom-in', 'Zoom in', '+');
      addBtn('zoom-out', 'Zoom out', '\u2212');
      addBtn('fit', 'Fit to view', 'Fit');
      this._traceBtn = null;
      if (this._data && this._data.traces.length > 0) {
        this._traceBtn = addBtn('trace', 'Step through a trace', 'Step through');
        this._traceBtn.setAttribute('aria-pressed', this._trace ? 'true' : 'false');
      }
      this._expandBtn =addBtn('expand', 'Expand graph', 'Expand');
      this._expandBtn.setAttribute('aria-pressed', this.hasAttribute('data-q-flow-expanded') ? 'true' : 'false');
      this._stage.appendChild(bar);
    }

    _buildDrawer() {
      var drawer = kitNode('aside');
      drawer.className = 'q-flow-drawer';
      drawer.setAttribute('data-q-flow-drawer', '');
      drawer.setAttribute('aria-label', 'Node details');
      drawer.setAttribute('data-q-inactive', '');
      this._drawer = drawer;
      this._stage.appendChild(drawer);
    }

    _setupZoom() {
      var self = this;
      var qf = window.quirkFlow;
      this._transform = { x: 0, y: 0, k: 1 };
      if (!qf || !qf.zoom || !qf.select) {
        return;
      }
      this._d3Zoom = qf.zoom()
        .scaleExtent([0.2, 4])
        .filter(function (event) {
          if (event.type === 'wheel') {
            return Boolean(event.ctrlKey || event.metaKey);
          }
          if (event.type === 'touchstart' || event.type === 'touchmove') {
            return Boolean(event.touches && event.touches.length >= 2);
          }
          if (event.type === 'mousedown') {
            return event.button === 0;
          }
          return !event.button;
        })
        .on('zoom', function (event) {
          var t = event.transform;
          self._transform = { x: t.x, y: t.y, k: t.k };
          if (self._viewport) {
            self._viewport.setAttribute('transform', 'translate(' + t.x + ',' + t.y + ') scale(' + t.k + ')');
          }
        });
      this._d3Selection = qf.select(this._svg);
      this._d3Selection.call(this._d3Zoom);
      this._d3Selection.on('dblclick.zoom', null);
    }

    _applyTransform(x, y, k) {
      var qf = window.quirkFlow;
      var clampedK = Math.max(0.2, Math.min(4, k));
      this._transform = { x: x, y: y, k: clampedK };
      if (this._d3Selection && this._d3Zoom && qf && qf.zoomIdentity) {
        this._d3Selection.call(this._d3Zoom.transform, qf.zoomIdentity.translate(x, y).scale(clampedK));
      } else if (this._viewport) {
        this._viewport.setAttribute('transform', 'translate(' + x + ',' + y + ') scale(' + clampedK + ')');
      }
    }

    _zoomBy(factor) {
      var rect = this._stage.getBoundingClientRect();
      var cx = (rect.width || 600) / 2;
      var cy = (rect.height || 320) / 2;
      var t = this._transform || { x: 0, y: 0, k: 1 };
      var nextK = Math.max(0.2, Math.min(4, t.k * factor));
      var ratio = nextK / t.k;
      var nextX = cx - (cx - t.x) * ratio;
      var nextY = cy - (cy - t.y) * ratio;
      this._applyTransform(nextX, nextY, nextK);
    }

    _fitBounds(bounds, reserveDrawer) {
      if (!bounds || !this._stage) {
        return;
      }
      var rect = this._stage.getBoundingClientRect();
      var availW = rect.width || 640;
      var availH = rect.height || 320;
      if (reserveDrawer && this._drawer && !this._drawer.hasAttribute('data-q-inactive')) {
        var dRect = this._drawer.getBoundingClientRect();
        if ((window.innerWidth || 1024) > 700) {
          availW = Math.max(160, availW - dRect.width);
        } else {
          availH = Math.max(120, availH - dRect.height);
        }
      }
      var pad = 28;
      var scaleX = Math.max(80, availW - pad * 2) / Math.max(1, bounds.width);
      var scaleY = Math.max(80, availH - pad * 2) / Math.max(1, bounds.height);
      var k = Math.max(0.2, Math.min(1.5, Math.min(scaleX, scaleY)));
      var tx = (availW - bounds.width * k) / 2 - bounds.x * k;
      var ty = (availH - bounds.height * k) / 2 - bounds.y * k;
      this._applyTransform(tx, ty, k);
    }

    _ensureNodeVisible(nodeId, avoidDrawer) {
      var box = this._nodeBoxes && this._nodeBoxes[nodeId];
      if (!box || !this._stage) {
        return;
      }
      var sRect = this._stage.getBoundingClientRect();
      var availW = sRect.width || 640;
      var availH = sRect.height || 320;
      if (avoidDrawer && this._drawer && !this._drawer.hasAttribute('data-q-inactive')) {
        var dRect = this._drawer.getBoundingClientRect();
        if ((window.innerWidth || 1024) > 700) {
          availW = Math.max(140, availW - dRect.width - 12);
        } else {
          availH = Math.max(100, availH - dRect.height - 12);
        }
      }
      var t = this._transform || { x: 0, y: 0, k: 1 };
      var left = box.x * t.k + t.x;
      var right = (box.x + box.width) * t.k + t.x;
      var top = box.y * t.k + t.y;
      var bottom = (box.y + box.height) * t.k + t.y;
      var nx = t.x;
      var ny = t.y;
      var margin = 20;
      if (right > availW - margin) {
        nx -= (right - (availW - margin));
      }
      if (left + (nx - t.x) < margin) {
        nx += (margin - (left + (nx - t.x)));
      }
      if (bottom > availH - margin) {
        ny -= (bottom - (availH - margin));
      }
      if (top + (ny - t.y) < margin) {
        ny += (margin - (top + (ny - t.y)));
      }
      if (nx !== t.x || ny !== t.y) {
        this._applyTransform(nx, ny, t.k);
      }
    }

    _toggleExpand() {
      var expanding = !this.hasAttribute('data-q-flow-expanded');
      if (expanding) {
        this.setAttribute('data-q-flow-expanded', '');
        this._focusedAfterExpand = false;
        if (this._expandBtn) {
          this._expandBtn.setAttribute('aria-pressed', 'true');
          this._expandBtn.textContent = 'Close';
        }
      } else {
        this.removeAttribute('data-q-flow-expanded');
        this._focusedAfterExpand = false;
        if (this._expandBtn) {
          this._expandBtn.setAttribute('aria-pressed', 'false');
          this._expandBtn.textContent = 'Expand';
        }
      }
    }

    _handleEscape(ev) {
      ev.preventDefault();
      ev.stopPropagation();
      if (this._trace) {
        this._closeTrace(true);
        return;
      }
      if (this.hasAttribute('data-q-flow-expanded') && !this._focusedAfterExpand) {
        this._toggleExpand();
        return;
      }
      if (this._focusedNode || this._focusedGroup) {
        this._clearFocus();
        this._focusedAfterExpand = false;
        return;
      }
      if (this.hasAttribute('data-q-flow-expanded')) {
        this._toggleExpand();
      }
    }

    _focusNode(nodeId) {
      var data = this._data;
      if (!data || !data.nodeMap[nodeId]) {
        return;
      }
      if (this.hasAttribute('data-q-flow-expanded')) {
        this._focusedAfterExpand = true;
      }
      this._focusedNode = nodeId;
      this._focusedGroup = null;

      var upNodes = {};
      var upEdges = {};
      var upDist = {};
      upDist[nodeId] = 0;
      var qUp = [nodeId];
      while (qUp.length) {
        var curUp = qUp.shift();
        data.edges.forEach(function (e) {
          if (!e.loop && e.to === curUp) {
            upEdges[e.index] = true;
            if (!Object.prototype.hasOwnProperty.call(upDist, e.from)) {
              upDist[e.from] = upDist[curUp] + 1;
              if (e.from !== nodeId) {
                upNodes[e.from] = true;
              }
              qUp.push(e.from);
            }
          }
        });
      }

      var downNodes = {};
      var downEdges = {};
      var downDist = {};
      downDist[nodeId] = 0;
      var qDown = [nodeId];
      while (qDown.length) {
        var curDown = qDown.shift();
        data.edges.forEach(function (e) {
          if (!e.loop && e.from === curDown) {
            downEdges[e.index] = true;
            if (!Object.prototype.hasOwnProperty.call(downDist, e.to)) {
              downDist[e.to] = downDist[curDown] + 1;
              if (e.to !== nodeId) {
                downNodes[e.to] = true;
              }
              qDown.push(e.to);
            }
          }
        });
      }

      var maxUp = 0;
      Object.keys(upEdges).forEach(function (eIdx) {
        var edge = data.edges[Number(eIdx)];
        var d = upDist[edge.from] || 1;
        if (d > maxUp) {
          maxUp = d;
        }
      });

      var edgeHops = {};
      Object.keys(upEdges).forEach(function (eIdx) {
        var edge = data.edges[Number(eIdx)];
        var d = upDist[edge.from] || 1;
        var hop = Math.max(0, maxUp - d);
        edgeHops[eIdx] = hop;
      });
      Object.keys(downEdges).forEach(function (eIdx) {
        var edge = data.edges[Number(eIdx)];
        var d = downDist[edge.from] || 0;
        var hop = maxUp + d;
        edgeHops[eIdx] = hop;
      });

      var litNodes = {};
      litNodes[nodeId] = true;
      Object.keys(upNodes).forEach(function (id) { litNodes[id] = true; });
      Object.keys(downNodes).forEach(function (id) { litNodes[id] = true; });

      var litGroups = {};
      Object.keys(litNodes).forEach(function (nid) {
        var gId = data.nodeMap[nid] && data.nodeMap[nid].group;
        while (gId && data.groupMap[gId]) {
          litGroups[gId] = true;
          gId = data.groupMap[gId].parent;
        }
      });

      Object.keys(this._nodeElements).forEach(function (nid) {
        var el = this._nodeElements[nid];
        if (nid === nodeId) {
          el.setAttribute('data-q-flow-selected', '');
        } else {
          el.removeAttribute('data-q-flow-selected');
        }
        if (litNodes[nid]) {
          el.setAttribute('data-q-flow-lit', '');
          el.removeAttribute('data-q-flow-dim');
        } else {
          el.removeAttribute('data-q-flow-lit');
          el.setAttribute('data-q-flow-dim', '');
        }
      }, this);

      var groupEls = this._stage.querySelectorAll('[data-q-flow-group]');
      for (var gi = 0; gi < groupEls.length; gi += 1) {
        var gEl = groupEls[gi];
        var gid = gEl.getAttribute('data-q-flow-group');
        if (litGroups[gid]) {
          gEl.setAttribute('data-q-flow-lit', '');
          gEl.removeAttribute('data-q-flow-dim');
        } else {
          gEl.removeAttribute('data-q-flow-lit');
          gEl.setAttribute('data-q-flow-dim', '');
        }
      }

      var reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
      var uid = this._uid;
      var activePulses = [];
      this._edgeRecords.forEach(function (rec, idx) {
        var isLoop = !!rec.edge.loop;
        var isLit = isLoop
          ? !!(litNodes[rec.edge.from] && litNodes[rec.edge.to])
          : Object.prototype.hasOwnProperty.call(edgeHops, idx);
        if (isLit) {
          rec.groupEl.setAttribute('data-q-flow-lit', '');
          if (isLoop) {
            rec.groupEl.removeAttribute('data-q-flow-hop');
            rec.basePath.setAttribute('marker-start', 'url(#q-flow-return-lit-' + uid + ')');
          } else {
            rec.groupEl.setAttribute('data-q-flow-hop', String(edgeHops[idx]));
          }
          rec.groupEl.removeAttribute('data-q-flow-dim');
          rec.basePath.setAttribute('stroke', 'var(--q-color-accent)');
          rec.basePath.setAttribute('stroke-width', reduced ? '3.5' : '2');
          rec.basePath.setAttribute('marker-end', 'url(#q-flow-arrow-lit-' + uid + ')');
          if (reduced || isLoop) {
            rec.pulsePath.setAttribute('data-q-inactive', '');
          } else {
            rec.pulsePath.removeAttribute('data-q-inactive');
            activePulses.push({ rec: rec, down: Object.prototype.hasOwnProperty.call(downEdges, idx) });
          }
        } else {
          rec.groupEl.removeAttribute('data-q-flow-lit');
          rec.groupEl.removeAttribute('data-q-flow-hop');
          rec.groupEl.setAttribute('data-q-flow-dim', '');
          rec.basePath.setAttribute('stroke', 'var(--q-color-text-muted)');
          rec.basePath.setAttribute('stroke-width', '1.75');
          rec.basePath.setAttribute('marker-end', 'url(#q-flow-arrow-' + uid + ')');
          if (isLoop) {
            rec.basePath.setAttribute('marker-start', 'url(#q-flow-return-' + uid + ')');
          }
          rec.pulsePath.setAttribute('data-q-inactive', '');
        }
      });

      if (reduced || activePulses.length === 0) {
        this.removeAttribute('data-q-flow-pulsing');
        this._stopPulse();
      } else {
        this.setAttribute('data-q-flow-pulsing', '');
        this._startPulse(pulseSchedule(activePulses, nodeId));
      }

      this._openDrawer(data.nodeMap[nodeId]);
      this._ensureNodeVisible(nodeId, true);

      var upCount = Object.keys(upNodes).length;
      var downCount = Object.keys(downNodes).length;
      var node = data.nodeMap[nodeId];
      if (this._live) {
        this._live.textContent = node.label + (node.shape !== 'box' ? ', ' + node.shape : '') + (node.kind ? ', ' + node.kind : '') + ', ' + upCount + ' upstream, ' + downCount + ' downstream';
      }
    }

    _startPulse(schedule) {
      var self = this;
      this._stopPulse();
      var startTime = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();

      function step(now) {
        if (!self.isConnected || !(self._focusedNode || self._trace)) {
          self._pulseFrame = 0;
          return;
        }
        var elapsed = (now || Date.now()) - startTime;
        for (var i = 0; i < schedule.length; i += 1) {
          self._placePulseDots(schedule[i], elapsed);
        }
        self._pulseFrame = nextFrame(step);
      }

      step(startTime);
    }

    _placePulseDots(item, elapsed) {
      var rec = item.rec;
      var sinceFirst = elapsed - item.offset;
      var used = 0;
      if (sinceFirst >= 0) {
        for (var t = sinceFirst % FLOW_PULSE_INTERVAL; t <= item.duration && t <= sinceFirst; t += FLOW_PULSE_INTERVAL) {
          var dot = rec.maskDots[used];
          if (!dot) {
            dot = rec.maskDots[0].cloneNode(false);
            rec.mask.appendChild(dot);
            rec.maskDots.push(dot);
          }
          var pt = this._pointAlong(rec.basePath, rec.points, t / item.duration);
          dot.setAttribute('cx', String(pt.x));
          dot.setAttribute('cy', String(pt.y));
          dot.removeAttribute('data-q-inactive');
          used += 1;
        }
      }
      for (var j = used; j < rec.maskDots.length; j += 1) {
        rec.maskDots[j].setAttribute('data-q-inactive', '');
      }
    }

    _pointAlong(pathEl, pts, frac) {
      var clamped = Math.max(0, Math.min(1, frac));
      try {
        if (pathEl && typeof pathEl.getTotalLength === 'function') {
          var len = pathEl.getTotalLength();
          if (len > 0) {
            return pathEl.getPointAtLength(clamped * len);
          }
        }
      } catch (_e) {}
      var a = pts[0] || { x: 0, y: 0 };
      var b = pts[pts.length - 1] || a;
      return {
        x: a.x + (b.x - a.x) * clamped,
        y: a.y + (b.y - a.y) * clamped
      };
    }

    _stopPulse() {
      if (this._pulseFrame) {
        cancelFrame(this._pulseFrame);
        this._pulseFrame = 0;
      }
    }

    _openDrawer(node) {
      var self = this;
      var data = this._data;
      var drawer = this._drawer;
      if (!drawer || !node || !data) {
        return;
      }
      while (drawer.firstChild) {
        drawer.removeChild(drawer.firstChild);
      }
      var head = document.createElement('div');
      head.setAttribute('data-q-flow-drawer-head', '');
      var h3 = document.createElement('h3');
      h3.textContent = node.label;
      head.appendChild(h3);

      var closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.setAttribute('data-q-flow-drawer-close', '');
      closeBtn.setAttribute('aria-label', 'Close details');
      closeBtn.textContent = 'Close';
      closeBtn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        self._clearFocus();
      });
      head.appendChild(closeBtn);
      drawer.appendChild(head);

      if (node.kind) {
        var kindBadge = document.createElement('div');
        kindBadge.setAttribute('data-q-flow-drawer-kind', '');
        var colorIdx = data.kinds[node.kind];
        if (colorIdx) {
          kindBadge.style.setProperty('--q-flow-kind-color', 'var(--q-color-chart-' + colorIdx + ')');
        }
        kindBadge.textContent = node.kind;
        drawer.appendChild(kindBadge);
      }

      if (node.detail) {
        var detBox = document.createElement('div');
        detBox.setAttribute('data-q-flow-drawer-detail', '');
        detBox.appendChild(sanitizeFlowDetail(node.detail));
        drawer.appendChild(detBox);
      }

      if (node.shape === 'subprocess' && node.flow) {
        var flowBox = document.createElement('div');
        flowBox.setAttribute('data-q-flow-drawer-flow', '');
        var linked = document.getElementById(node.flow);
        if (linked && linked !== self && linked.isConnected && linked.tagName === 'Q-FLOW') {
          var openBtn = document.createElement('button');
          openBtn.type = 'button';
          openBtn.setAttribute('data-q-flow-open-flow', '');
          openBtn.textContent = 'Open flow';
          openBtn.addEventListener('click', function (ev) {
            ev.stopPropagation();
            self._openLinkedFlow(linked);
          });
          flowBox.appendChild(openBtn);
        } else {
          var missing = document.createElement('p');
          missing.setAttribute('data-q-flow-flow-missing', '');
          missing.textContent = 'The linked flow "' + node.flow + '" isn\'t on this page.';
          flowBox.appendChild(missing);
        }
        drawer.appendChild(flowBox);
      }

      var incoming = data.edges.filter(function (e) { return e.to === node.id; });
      var outgoing = data.edges.filter(function (e) { return e.from === node.id; });

      function addEdgeSection(titleText, dirKey, list, isIncoming) {
        if (!list.length) {
          return;
        }
        var sec = document.createElement('div');
        sec.setAttribute('data-q-flow-drawer-edges', dirKey);
        var h4 = document.createElement('h4');
        h4.textContent = titleText;
        sec.appendChild(h4);
        var ul = document.createElement('ul');
        list.forEach(function (e) {
          var otherId = isIncoming ? e.from : e.to;
          var otherNode = data.nodeMap[otherId];
          var otherLabel = otherNode ? otherNode.label : otherId;
          var li = document.createElement('li');
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.setAttribute('data-q-flow-edge-btn', '');
          btn.setAttribute('data-q-flow-target', otherId);
          var parts = [];
          if (e.label) {
            parts.push(e.label);
          }
          parts.push((isIncoming ? 'from ' : 'to ') + otherLabel);
          if (e.async) {
            parts.push('(async)');
          }
          btn.textContent = parts.join(' ');
          btn.addEventListener('click', function (ev) {
            ev.stopPropagation();
            self._setRoving(otherId, false);
            self._focusNode(otherId);
          });
          li.appendChild(btn);
          ul.appendChild(li);
        });
        sec.appendChild(ul);
        drawer.appendChild(sec);
      }

      addEdgeSection('Incoming', 'in', incoming, true);
      addEdgeSection('Outgoing', 'out', outgoing, false);
      drawer.removeAttribute('data-q-inactive');
    }

    /**
     * Brings another graph on the page into view from a subprocess drawer.
     * This graph's focus and drawer stay as they were; the target's own focus is left alone.
     */
    _openLinkedFlow(target) {
      if (this.hasAttribute('data-q-flow-expanded')) {
        this._toggleExpand();
      }
      var reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
      target.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' });
      var entry = target.getAttribute('data-q-flow-ready') === 'true' && target._stage
        ? target._stage.querySelector('[data-q-flow-node][tabindex="0"]')
        : null;
      if (entry) {
        target._fitBounds(target._bounds, false);
        entry.focus({ preventScroll: true });
      } else {
        if (!target.hasAttribute('tabindex')) {
          target.setAttribute('tabindex', '-1');
        }
        target.focus({ preventScroll: true });
      }
    }

    _focusGroup(groupId) {
      var data = this._data;
      if (!data || !data.groupMap[groupId]) {
        return;
      }
      this._focusedGroup = groupId;
      this._focusedNode = null;
      this._stopPulse();
      this.removeAttribute('data-q-flow-pulsing');
      if (this._drawer) {
        this._drawer.setAttribute('data-q-inactive', '');
      }

      var inGroup = {};
      inGroup[groupId] = true;
      var changed = true;
      while (changed) {
        changed = false;
        data.groups.forEach(function (g) {
          if (g.parent && inGroup[g.parent] && !inGroup[g.id]) {
            inGroup[g.id] = true;
            changed = true;
          }
        });
      }

      var memberNodes = {};
      data.nodes.forEach(function (n) {
        if (n.group && inGroup[n.group]) {
          memberNodes[n.id] = true;
        }
      });

      Object.keys(this._nodeElements).forEach(function (nid) {
        var el = this._nodeElements[nid];
        el.removeAttribute('data-q-flow-selected');
        if (memberNodes[nid]) {
          el.setAttribute('data-q-flow-lit', '');
          el.removeAttribute('data-q-flow-dim');
        } else {
          el.removeAttribute('data-q-flow-lit');
          el.setAttribute('data-q-flow-dim', '');
        }
      }, this);

      var groupEls = this._stage.querySelectorAll('[data-q-flow-group]');
      for (var gi = 0; gi < groupEls.length; gi += 1) {
        var gEl = groupEls[gi];
        var gid = gEl.getAttribute('data-q-flow-group');
        if (inGroup[gid]) {
          gEl.setAttribute('data-q-flow-lit', '');
          gEl.removeAttribute('data-q-flow-dim');
        } else {
          gEl.removeAttribute('data-q-flow-lit');
          gEl.setAttribute('data-q-flow-dim', '');
        }
      }

      var uid = this._uid;
      this._edgeRecords.forEach(function (rec) {
        var inside = memberNodes[rec.edge.from] && memberNodes[rec.edge.to];
        rec.pulsePath.setAttribute('data-q-inactive', '');
        rec.groupEl.removeAttribute('data-q-flow-hop');
        rec.basePath.setAttribute('stroke', 'var(--q-color-text-muted)');
        rec.basePath.setAttribute('stroke-width', '1.75');
        rec.basePath.setAttribute('marker-end', 'url(#q-flow-arrow-' + uid + ')');
        if (rec.edge.loop) {
          rec.basePath.setAttribute('marker-start', 'url(#q-flow-return-' + uid + ')');
        }
        if (inside) {
          rec.groupEl.setAttribute('data-q-flow-lit', '');
          rec.groupEl.removeAttribute('data-q-flow-dim');
        } else {
          rec.groupEl.removeAttribute('data-q-flow-lit');
          rec.groupEl.setAttribute('data-q-flow-dim', '');
        }
      });

      var gBox = this._groupBoxes && this._groupBoxes[groupId];
      if (gBox) {
        this._fitBounds({
          x: gBox.x - 16,
          y: gBox.y - 16,
          width: gBox.width + 32,
          height: gBox.height + 32
        }, false);
      }
    }

    _clearFocus() {
      this._focusedNode = null;
      this._focusedGroup = null;
      this._stopPulse();
      this.removeAttribute('data-q-flow-pulsing');
      if (this._drawer) {
        this._drawer.setAttribute('data-q-inactive', '');
      }
      if (!this._stage) {
        return;
      }
      Object.keys(this._nodeElements || {}).forEach(function (nid) {
        var el = this._nodeElements[nid];
        el.removeAttribute('data-q-flow-selected');
        el.removeAttribute('data-q-flow-lit');
        el.removeAttribute('data-q-flow-dim');
      }, this);
      var groupEls = this._stage.querySelectorAll('[data-q-flow-group]');
      for (var gi = 0; gi < groupEls.length; gi += 1) {
        groupEls[gi].removeAttribute('data-q-flow-lit');
        groupEls[gi].removeAttribute('data-q-flow-dim');
      }
      var uid = this._uid;
      (this._edgeRecords || []).forEach(function (rec) {
        rec.groupEl.removeAttribute('data-q-flow-lit');
        rec.groupEl.removeAttribute('data-q-flow-dim');
        rec.groupEl.removeAttribute('data-q-flow-hop');
        rec.basePath.setAttribute('stroke', 'var(--q-color-text-muted)');
        rec.basePath.setAttribute('stroke-width', '1.75');
        rec.basePath.setAttribute('marker-end', 'url(#q-flow-arrow-' + uid + ')');
        if (rec.edge.loop) {
          rec.basePath.setAttribute('marker-start', 'url(#q-flow-return-' + uid + ')');
        }
        rec.pulsePath.setAttribute('data-q-inactive', '');
      });
    }

    /** Opens trace mode on a trace, the way the "Step through" button does, and moves focus to Next. */
    _openTrace(traceIndex) {
      if (this._startTrace(traceIndex) && this._traceEls) {
        this._traceEls.next.focus();
      }
    }

    /**
     * Puts trace mode on step 1 of a trace: clears focus, opens the panel and fits the canvas to
     * the narrower stage. Also what the picker runs, so it leaves DOM focus where it is.
     */
    _startTrace(traceIndex) {
      var data = this._data;
      var trace = data && data.traces[traceIndex];
      if (!trace || !this._tracePanel) {
        return false;
      }
      this._stopTracePlay();
      this._clearFocus();
      this._focusedAfterExpand = false;
      var nodes = {};
      var edges = {};
      trace.steps.forEach(function (step) {
        nodes[step.node] = true;
        if (step.edge !== null) {
          edges[step.edge] = true;
        }
      });
      this._trace = { index: traceIndex, step: 0, nodes: nodes, edges: edges };
      this._lastTraceIndex = traceIndex;
      this.setAttribute('data-q-flow-tracing', '');
      if (this._traceBtn) {
        this._traceBtn.setAttribute('aria-pressed', 'true');
      }
      this._tracePanel.removeAttribute('data-q-inactive');
      this._traceEls.picker.selectedIndex = traceIndex;
      this._buildTraceDots(trace);
      this._showTraceStep(0);
      this._fitBounds(this._bounds, false);
      this._ensureNodeVisible(trace.steps[0].node, false);
      return true;
    }

    /** Leaves trace mode and returns the graph to rest; the button gets focus back when asked. */
    _closeTrace(restoreFocus) {
      this._stopTracePlay();
      this._trace = null;
      this.removeAttribute('data-q-flow-tracing');
      if (this._traceBtn) {
        this._traceBtn.setAttribute('aria-pressed', 'false');
      }
      if (this._tracePanel) {
        this._tracePanel.setAttribute('data-q-inactive', '');
      }
      this._clearFocus();
      this._fitBounds(this._bounds, false);
      if (restoreFocus && this._traceBtn) {
        this._traceBtn.focus();
      }
    }

    /** Starts Play, or stops it when it is running. Play on the last step restarts from step 1. */
    _toggleTracePlay() {
      var self = this;
      var tr = this._trace;
      var data = this._data;
      var els = this._traceEls;
      if (!tr || !data || !els) {
        return;
      }
      if (this._tracePlayToken) {
        this._stopTracePlay();
        return;
      }
      var steps = data.traces[tr.index].steps;
      if (tr.step >= steps.length - 1) {
        this._showTraceStep(0);
      }
      var token = {};
      this._tracePlayToken = token;
      els.play.textContent = 'Pause';
      els.play.setAttribute('aria-pressed', 'true');
      var shownAt = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();

      function frame(now) {
        if (self._tracePlayToken !== token || !self.isConnected || !self._trace) {
          return;
        }
        var t = now || ((typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now());
        if (t - shownAt >= FLOW_TRACE_STEP_MS) {
          shownAt = t;
          self._showTraceStep(self._trace.step + 1);
          if (self._trace.step >= steps.length - 1) {
            self._stopTracePlay();
            return;
          }
        }
        self._tracePlayFrame = nextFrame(frame);
      }

      this._tracePlayFrame = nextFrame(frame);
    }

    /** Stops Play, if it is running, and shows the button as Play again. */
    _stopTracePlay() {
      this._tracePlayToken = null;
      if (this._tracePlayFrame) {
        cancelFrame(this._tracePlayFrame);
        this._tracePlayFrame = 0;
      }
      var els = this._traceEls;
      if (els) {
        els.play.textContent = 'Play';
        els.play.setAttribute('aria-pressed', 'false');
      }
    }

    _traceStepBy(delta) {
      if (this._trace) {
        this._stopTracePlay();
        this._showTraceStep(this._trace.step + delta);
      }
    }

    /**
     * A click on a node while tracing. A node on the trace jumps to its next visit after the
     * current step, or its first; a node off the trace leaves trace mode and takes focus.
     */
    _traceNodeClick(nodeId) {
      var tr = this._trace;
      var data = this._data;
      if (!tr || !data) {
        return;
      }
      this._stopTracePlay();
      if (!tr.nodes[nodeId]) {
        this._closeTrace(false);
        this._focusNode(nodeId);
        return;
      }
      var steps = data.traces[tr.index].steps;
      var target = -1;
      for (var i = 0; i < steps.length && target < 0; i += 1) {
        if (steps[i].node === nodeId && i > tr.step) {
          target = i;
        }
      }
      for (var j = 0; j < steps.length && target < 0; j += 1) {
        if (steps[j].node === nodeId) {
          target = j;
        }
      }
      this._showTraceStep(target);
    }

    _buildTraceDots(trace) {
      var self = this;
      var dots = this._traceEls.dots;
      while (dots.firstChild) {
        dots.removeChild(dots.firstChild);
      }
      trace.steps.forEach(function (step, i) {
        var li = document.createElement('li');
        var dot = document.createElement('button');
        dot.type = 'button';
        dot.setAttribute('data-q-flow-trace-dot', String(i + 1));
        dot.setAttribute('aria-label', 'Step ' + (i + 1) + ': ' + self._data.nodeMap[step.node].label);
        dot.textContent = String(i + 1);
        dot.addEventListener('click', function () {
          self._stopTracePlay();
          self._showTraceStep(i);
        });
        li.appendChild(dot);
        dots.appendChild(li);
      });
    }

    /**
     * Shows one trace step: the canvas lights the step's node and incoming edge and dims
     * everything off the trace's path, and the panel shows the step's note and value.
     */
    _showTraceStep(stepIndex) {
      var tr = this._trace;
      var data = this._data;
      if (!tr || !data) {
        return;
      }
      var trace = data.traces[tr.index];
      var i = Math.max(0, Math.min(trace.steps.length - 1, stepIndex));
      var step = trace.steps[i];
      tr.step = i;

      Object.keys(this._nodeElements).forEach(function (nid) {
        var el = this._nodeElements[nid];
        var current = nid === step.node;
        el.toggleAttribute('data-q-flow-selected', current);
        el.toggleAttribute('data-q-flow-lit', current);
        el.toggleAttribute('data-q-flow-dim', !tr.nodes[nid]);
      }, this);

      var holdsPath = {};
      Object.keys(tr.nodes).forEach(function (nid) {
        var gId = data.nodeMap[nid].group;
        while (gId && data.groupMap[gId]) {
          holdsPath[gId] = true;
          gId = data.groupMap[gId].parent;
        }
      });
      var groupEls = this._stage.querySelectorAll('[data-q-flow-group]');
      for (var gi = 0; gi < groupEls.length; gi += 1) {
        groupEls[gi].removeAttribute('data-q-flow-lit');
        groupEls[gi].toggleAttribute('data-q-flow-dim', !holdsPath[groupEls[gi].getAttribute('data-q-flow-group')]);
      }

      var reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
      var uid = this._uid;
      var currentRec = step.edge === null ? null : this._edgeRecords[step.edge];
      this._edgeRecords.forEach(function (rec) {
        var current = rec === currentRec;
        rec.groupEl.removeAttribute('data-q-flow-hop');
        rec.groupEl.toggleAttribute('data-q-flow-lit', current);
        rec.groupEl.toggleAttribute('data-q-flow-dim', !tr.edges[rec.edge.index]);
        rec.basePath.setAttribute('stroke', current ? 'var(--q-color-accent)' : 'var(--q-color-text-muted)');
        rec.basePath.setAttribute('stroke-width', current ? (reduced ? '3.5' : '2') : '1.75');
        rec.basePath.setAttribute('marker-end', 'url(#q-flow-arrow-' + (current ? 'lit-' : '') + uid + ')');
        if (rec.edge.loop) {
          rec.basePath.setAttribute('marker-start', 'url(#q-flow-return-' + (current ? 'lit-' : '') + uid + ')');
        }
        rec.pulsePath.setAttribute('data-q-inactive', '');
        if (!current || reduced) {
          rec.maskDots.forEach(function (dot) {
            dot.setAttribute('data-q-inactive', '');
          });
        }
      });

      if (currentRec && !reduced) {
        currentRec.pulsePath.removeAttribute('data-q-inactive');
        this.setAttribute('data-q-flow-pulsing', '');
        this._startPulse(pulseSchedule([{ rec: currentRec, down: true }], currentRec.edge.from));
      } else {
        this.removeAttribute('data-q-flow-pulsing');
        this._stopPulse();
      }

      this._ensureNodeVisible(step.node, false);
      this._renderTracePanel(i);
    }

    _renderTracePanel(i) {
      var els = this._traceEls;
      var data = this._data;
      var trace = data.traces[this._trace.index];
      var step = trace.steps[i];
      var label = data.nodeMap[step.node].label;

      els.counter.textContent = 'Step ' + (i + 1) + ' of ' + trace.steps.length;
      var spoken = document.createElement('span');
      spoken.className = 'q-visually-hidden';
      spoken.textContent = ', ' + label + (step.note ? ': ' + step.note : '');
      els.counter.appendChild(spoken);

      els.back.disabled = i === 0;
      els.next.disabled = i === trace.steps.length - 1;
      var dots = els.dots.querySelectorAll('[data-q-flow-trace-dot]');
      for (var d = 0; d < dots.length; d += 1) {
        if (d === i) {
          dots[d].setAttribute('aria-current', 'step');
        } else {
          dots[d].removeAttribute('aria-current');
        }
      }

      els.note.textContent = step.note || '';
      els.note.toggleAttribute('data-q-inactive', !step.note);
      els.changes.checked = !!this._traceChangesOnly;
      this._renderTraceValue(i);
    }

    _renderTraceValue(i) {
      var box = this._traceEls.value;
      var steps = this._data.traces[this._trace.index].steps;
      var root = traceDiff(i > 0 ? steps[i - 1].value : undefined, steps[i].value, i > 0);
      while (box.firstChild) {
        box.removeChild(box.firstChild);
      }
      if (this._traceChangesOnly && !root.hasChange) {
        var empty = document.createElement('p');
        empty.setAttribute('data-q-flow-trace-empty', '');
        empty.textContent = 'No changes at this step';
        box.appendChild(empty);
        return;
      }
      var tree = document.createElement('ul');
      tree.setAttribute('data-q-flow-tree', '');
      if (this._traceChangesOnly) {
        tree.setAttribute('data-q-flow-changes-only', '');
      }
      (root.children && root.change !== 'changed' ? root.children : [root]).forEach(function (field) {
        tree.appendChild(renderTraceField(field, 1));
      });
      box.appendChild(tree);
    }

    _setRoving(nodeId, moveDomFocus) {
      if (!this._nodeElements || !this._nodeElements[nodeId]) {
        return;
      }
      this._rovingId = nodeId;
      Object.keys(this._nodeElements).forEach(function (nid) {
        this._nodeElements[nid].setAttribute('tabindex', nid === nodeId ? '0' : '-1');
      }, this);
      if (moveDomFocus) {
        this._nodeElements[nodeId].focus();
        this._ensureNodeVisible(nodeId, true);
      }
    }

    _nearestNeighbor(fromId, key) {
      var boxes = this._nodeBoxes;
      if (!boxes || !boxes[fromId]) {
        return null;
      }
      var cur = boxes[fromId];
      var cx = cur.x + cur.width / 2;
      var cy = cur.y + cur.height / 2;
      var bestId = null;
      var bestScore = Infinity;
      Object.keys(boxes).forEach(function (nid) {
        if (nid === fromId) {
          return;
        }
        var b = boxes[nid];
        var bx = b.x + b.width / 2;
        var by = b.y + b.height / 2;
        var dx = bx - cx;
        var dy = by - cy;
        var primary = 0;
        var secondary = 0;
        if (key === 'ArrowRight' && dx > 2) { primary = dx; secondary = Math.abs(dy); }
        else if (key === 'ArrowLeft' && dx < -2) { primary = -dx; secondary = Math.abs(dy); }
        else if (key === 'ArrowDown' && dy > 2) { primary = dy; secondary = Math.abs(dx); }
        else if (key === 'ArrowUp' && dy < -2) { primary = -dy; secondary = Math.abs(dx); }
        if (primary > 0) {
          var score = primary + secondary * 1.5;
          if (score < bestScore) {
            bestScore = score;
            bestId = nid;
          }
        }
      });
      if (bestId) {
        return bestId;
      }
      var ids = this._data.nodes.map(function (n) { return n.id; });
      var idx = ids.indexOf(fromId);
      if (idx < 0) {
        return null;
      }
      if (key === 'ArrowRight' || key === 'ArrowDown') {
        return ids[(idx + 1) % ids.length];
      }
      return ids[(idx - 1 + ids.length) % ids.length];
    }

    _onNodeKey(ev, nodeId) {
      if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft' || ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        ev.stopPropagation();
        var nextId = this._nearestNeighbor(nodeId, ev.key);
        if (nextId) {
          this._setRoving(nextId, true);
        }
      } else if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        ev.stopPropagation();
        if (this._trace) {
          this._traceNodeClick(nodeId);
        } else {
          this._focusNode(nodeId);
        }
      } else {
        this._onGraphKey(ev);
      }
    }

    _onGraphKey(ev) {
      if (ev.key === '+' || ev.key === '=') {
        ev.preventDefault();
        ev.stopPropagation();
        this._zoomBy(1.25);
      } else if (ev.key === '-' || ev.key === '_') {
        ev.preventDefault();
        ev.stopPropagation();
        this._zoomBy(0.8);
      } else if (ev.key === '0') {
        ev.preventDefault();
        ev.stopPropagation();
        this._fitBounds(this._bounds, false);
      } else if (ev.key === 'Escape') {
        this._handleEscape(ev);
      }
    }

    _applyTheme() {
      /* SVG and drawer colors use var(--q-color-*) custom properties, so they update live without re-layout. */
    }
  }

  define('q-tabs', QTabs);
  define('q-timeline', QTimeline);
  define('q-code', QCode);
  define('q-stat', QStat);
  define('q-table', QTable);
  define('q-chart', QChart);
  define('q-diff', QDiff);
  define('q-diff-note', QDiffNote);
  define('q-board', QBoard);
  define('q-sidenote', QSidenote);
  define('q-compare', QCompare);
  define('q-flow', QFlow);
})();

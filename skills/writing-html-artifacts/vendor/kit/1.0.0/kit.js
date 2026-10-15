/*
 * quirk-kit: the component kit's runtime. One classic-script IIFE, so it works as an inline
 * <script> and as a side-effect import. It exposes nothing on window and defines elements only
 * through define(), which never redefines a tag that is already registered.
 *
 * Helpers every element builds on: define, whenReady, token, onTheme, bindData, readTable.
 * Elements so far: q-tabs, q-timeline, q-code, q-stat, q-table, q-chart, q-diff, q-diff-note, q-board.
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

  define('q-tabs', QTabs);
  define('q-timeline', QTimeline);
  define('q-code', QCode);
  define('q-stat', QStat);
  define('q-table', QTable);
  define('q-chart', QChart);
  define('q-diff', QDiff);
  define('q-diff-note', QDiffNote);
  define('q-board', QBoard);
})();

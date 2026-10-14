/*
 * quirk-kit: the component kit's runtime. One classic-script IIFE, so it works as an inline
 * <script> and as a side-effect import. It exposes nothing on window and defines elements only
 * through define(), which never redefines a tag that is already registered.
 *
 * Helpers every element builds on: define, whenReady, token, onTheme, bindData, readTable.
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
})();

/*
 * Shared page chrome for built artifacts: the light/dark/auto theme toggle and
 * window.quirkData(), the one way page code reads its data. Plain script, no network calls.
 *
 * quirkData() resolves from <script type="application/json" id="quirk-data"> when present,
 * otherwise from the file the viewer picks in <input type="file" id="quirk-data-picker">.
 * JSON parses as-is; CSV becomes an array of row objects keyed by the header row (values stay
 * strings).
 */
(function () {
  "use strict";

  var STORAGE_KEY = "quirk-theme";
  var MODES = ["auto", "light", "dark"];
  var root = document.documentElement;

  function storedMode() {
    try {
      var value = window.localStorage.getItem(STORAGE_KEY);
      return MODES.indexOf(value) >= 0 ? value : "auto";
    } catch (e) {
      return "auto";
    }
  }

  function storeMode(mode) {
    try {
      if (mode === "auto") {
        window.localStorage.removeItem(STORAGE_KEY);
      } else {
        window.localStorage.setItem(STORAGE_KEY, mode);
      }
    } catch (e) {
      /* storage can be blocked; the toggle still works for this page view */
    }
  }

  function currentMode() {
    var attr = root.getAttribute("data-theme");
    return attr === "light" || attr === "dark" ? attr : "auto";
  }

  function applyMode(mode) {
    if (mode === "auto") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", mode);
    }
  }

  function paintToggle(button) {
    var mode = currentMode();
    button.textContent = "Theme: " + mode;
    button.setAttribute("data-mode", mode);
    button.setAttribute("aria-label", "Color theme: " + mode + ". Activate to change.");
  }

  function initToggle() {
    applyMode(storedMode());
    var button = document.querySelector("[data-quirk-theme-toggle]");
    if (!button) {
      button = document.createElement("button");
      button.setAttribute("type", "button");
      button.setAttribute("data-quirk-theme-toggle", "");
      button.className = "q-theme-toggle";
      document.body.appendChild(button);
    }
    paintToggle(button);
    button.addEventListener("click", function () {
      var next = MODES[(MODES.indexOf(currentMode()) + 1) % MODES.length];
      applyMode(next);
      storeMode(next);
      paintToggle(button);
    });
  }

  function parseCSV(text) {
    var rows = [];
    var row = [];
    var cell = "";
    var quoted = false;
    var i = 0;
    var src = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
    while (i < src.length) {
      var ch = src.charAt(i);
      if (quoted) {
        if (ch === '"') {
          if (src.charAt(i + 1) === '"') {
            cell += '"';
            i += 1;
          } else {
            quoted = false;
          }
        } else {
          cell += ch;
        }
      } else if (ch === '"') {
        quoted = true;
      } else if (ch === ",") {
        row.push(cell);
        cell = "";
      } else if (ch === "\n" || ch === "\r") {
        if (ch === "\r" && src.charAt(i + 1) === "\n") {
          i += 1;
        }
        row.push(cell);
        rows.push(row);
        row = [];
        cell = "";
      } else {
        cell += ch;
      }
      i += 1;
    }
    if (cell !== "" || row.length > 0) {
      row.push(cell);
      rows.push(row);
    }
    rows = rows.filter(function (r) {
      return !(r.length === 1 && r[0] === "");
    });
    if (rows.length === 0) {
      return [];
    }
    var keys = rows[0];
    return rows.slice(1).map(function (r) {
      var obj = {};
      for (var k = 0; k < keys.length; k += 1) {
        obj[keys[k]] = k < r.length ? r[k] : "";
      }
      return obj;
    });
  }

  function parseData(text, name) {
    var body = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
    if (/\.csv$/i.test(name)) {
      return parseCSV(body);
    }
    if (/\.json$/i.test(name)) {
      return JSON.parse(body);
    }
    try {
      return JSON.parse(body);
    } catch (e) {
      return parseCSV(body);
    }
  }

  function readFile(file) {
    if (typeof file.text === "function") {
      return file.text();
    }
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        resolve(String(reader.result));
      };
      reader.onerror = function () {
        reject(reader.error);
      };
      reader.readAsText(file);
    });
  }

  function reportError(err) {
    var status = document.getElementById("quirk-data-status");
    var message = "Could not read that file: " + (err && err.message ? err.message : err);
    if (status) {
      status.textContent = message;
    }
  }

  var dataPromise = null;

  function loadData() {
    var embedded = document.getElementById("quirk-data");
    if (embedded) {
      try {
        return Promise.resolve(JSON.parse(embedded.textContent));
      } catch (e) {
        return Promise.reject(e);
      }
    }
    return new Promise(function (resolve) {
      document.addEventListener("change", function (event) {
        var target = event.target;
        if (!target || target.id !== "quirk-data-picker" || !target.files || !target.files[0]) {
          return;
        }
        var file = target.files[0];
        readFile(file)
          .then(function (text) {
            resolve(parseData(text, file.name || ""));
          })
          .catch(reportError);
      });
    });
  }

  window.quirkData = function () {
    if (!dataPromise) {
      dataPromise = loadData();
    }
    return dataPromise;
  };
  window.quirkData.parseCSV = parseCSV;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initToggle);
  } else {
    initToggle();
  }
})();

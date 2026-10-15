/*
 * Shared page chrome for built artifacts: the light/dark/auto theme toggle and
 * window.quirkData(), the one way page code reads its data. Plain script, no network calls.
 *
 * Theme: the toggle sets data-theme on <html> and, in step with the effective theme (the toggle,
 * or the OS scheme in auto mode, followed live), adds or removes the Web Awesome class wa-dark.
 * Whenever the mode or the effective theme changes, a "quirk-theme" CustomEvent fires on document
 * with detail {mode: "auto"|"light"|"dark", effective: "light"|"dark"}; pages rebuild charts on it.
 *
 * quirkData() resolves from <script type="application/json" id="quirk-data"> when present,
 * otherwise from the file the viewer picks in <input type="file" id="quirk-data-picker">.
 * JSON parses as-is; CSV becomes an array of row objects keyed by the header row (values stay
 * strings). Picking a different file re-resolves: quirkData() returns the latest pick, and
 * window.quirkData.onChange(callback) calls callback(data) after every pick.
 *
 * Nav: when the page has a .q-nav, the rail link for the section being read gets
 * aria-current="location" and loses it elsewhere. Without a nav nothing is observed.
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

  var darkQuery =
    typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  var lastState = null;

  function effectiveTheme(mode) {
    if (mode === "auto") {
      return darkQuery && darkQuery.matches ? "dark" : "light";
    }
    return mode;
  }

  function setDarkClass(on) {
    if (root.classList) {
      if (on) {
        root.classList.add("wa-dark");
      } else {
        root.classList.remove("wa-dark");
      }
      return;
    }
    var rest = String(root.className || "")
      .split(/\s+/)
      .filter(function (name) {
        return name && name !== "wa-dark";
      });
    if (on) {
      rest.push("wa-dark");
    }
    root.className = rest.join(" ");
  }

  function announce(mode, effective) {
    if (typeof CustomEvent !== "function" || typeof document.dispatchEvent !== "function") {
      return;
    }
    document.dispatchEvent(
      new CustomEvent("quirk-theme", { detail: { mode: mode, effective: effective } })
    );
  }

  function syncTheme(notify) {
    var mode = currentMode();
    var effective = effectiveTheme(mode);
    setDarkClass(effective === "dark");
    var changed = !lastState || lastState.mode !== mode || lastState.effective !== effective;
    lastState = { mode: mode, effective: effective };
    if (notify && changed) {
      announce(mode, effective);
    }
  }

  function applyMode(mode) {
    if (mode === "auto") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", mode);
    }
    syncTheme(true);
  }

  function watchOsScheme() {
    if (!darkQuery) {
      return;
    }
    var onChange = function () {
      syncTheme(true);
    };
    if (typeof darkQuery.addEventListener === "function") {
      darkQuery.addEventListener("change", onChange);
    } else if (typeof darkQuery.addListener === "function") {
      darkQuery.addListener(onChange);
    }
  }

  function paintToggle(button) {
    var mode = currentMode();
    button.textContent = "Theme: " + mode;
    button.setAttribute("data-mode", mode);
    button.setAttribute("aria-label", "Color theme: " + mode + ". Activate to change.");
  }

  function initToggle() {
    var initial = storedMode();
    if (initial === "auto") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", initial);
    }
    syncTheme(false);
    watchOsScheme();
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

  var pickedResolve = null;
  var pickedPromise = null;
  var pickSeq = 0;
  var changeCallbacks = [];

  function newPickedPromise() {
    pickedPromise = new Promise(function (resolve) {
      pickedResolve = resolve;
    });
  }

  function deliver(value) {
    if (pickedResolve) {
      pickedResolve(value);
      pickedResolve = null;
    } else {
      pickedPromise = Promise.resolve(value);
    }
    changeCallbacks.slice().forEach(function (callback) {
      try {
        callback(value);
      } catch (e) {
        reportError(e);
      }
    });
  }

  newPickedPromise();

  document.addEventListener("change", function (event) {
    var target = event.target;
    if (!target || target.id !== "quirk-data-picker" || !target.files || !target.files[0]) {
      return;
    }
    var file = target.files[0];
    pickSeq += 1;
    var seq = pickSeq;
    readFile(file)
      .then(function (text) {
        var value = parseData(text, file.name || "");
        if (seq === pickSeq) {
          deliver(value);
        }
      })
      .catch(reportError);
  });

  var embeddedPromise = null;

  function loadEmbedded(embedded) {
    if (!embeddedPromise) {
      try {
        embeddedPromise = Promise.resolve(JSON.parse(embedded.textContent));
      } catch (e) {
        embeddedPromise = Promise.reject(e);
      }
    }
    return embeddedPromise;
  }

  window.quirkData = function () {
    var embedded = document.getElementById("quirk-data");
    return embedded ? loadEmbedded(embedded) : pickedPromise;
  };
  window.quirkData.parseCSV = parseCSV;
  window.quirkData.onChange = function (callback) {
    if (typeof callback === "function") {
      changeCallbacks.push(callback);
    }
  };

  function initNav() {
    var nav = document.querySelector(".q-nav");
    if (!nav || typeof window.IntersectionObserver !== "function") {
      return;
    }
    var links = [];
    var headings = [];
    var anchors = nav.querySelectorAll(".q-nav-rail a[href^='#']");
    for (var i = 0; i < anchors.length; i += 1) {
      var heading = document.getElementById(anchors[i].getAttribute("href").slice(1));
      if (heading) {
        links.push(anchors[i]);
        headings.push(heading);
      }
    }
    if (headings.length === 0) {
      return;
    }
    var current = -1;
    var mark = function () {
      var line = window.innerHeight * 0.3;
      var next = -1;
      for (var k = 0; k < headings.length; k += 1) {
        if (headings[k].getBoundingClientRect().top <= line) {
          next = k;
        }
      }
      if (next === current) {
        return;
      }
      if (current >= 0) {
        links[current].removeAttribute("aria-current");
      }
      if (next >= 0) {
        links[next].setAttribute("aria-current", "location");
      }
      current = next;
    };
    var observer = new window.IntersectionObserver(mark, { rootMargin: "0px 0px -70% 0px" });
    for (var j = 0; j < headings.length; j += 1) {
      observer.observe(headings[j]);
    }
    mark();
  }

  function init() {
    initToggle();
    initNav();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

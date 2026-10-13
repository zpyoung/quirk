/*
 * Companion screen behavior, inlined into every screen as <script data-quirk-shell="companion">.
 * Reads the screen's nonce from the [data-quirk-nonce] element, posts a "click" event for every
 * option toggle and a "proceed" event for the Proceed button to /_quirk/event, polls /_quirk/state
 * every 2 s, and locks the page behind the "superseded" banner when the nonce changes or the
 * server answers 409. All requests are same-origin.
 */
(function () {
  "use strict";

  var group = document.querySelector("[data-quirk-nonce]");
  if (!group) {
    return;
  }
  var nonce = group.getAttribute("data-quirk-nonce");
  var multi = group.getAttribute("data-select") === "multi";
  var cards = Array.prototype.slice.call(group.querySelectorAll("[data-option-id]"));
  var noteField = document.querySelector("[data-quirk-note]");
  var proceedButton = document.querySelector("[data-quirk-proceed]");
  var banner = document.getElementById("q-superseded");
  var status = document.getElementById("q-status");
  var reload = document.querySelector("[data-quirk-reload]");
  var checkedAttr = multi ? "aria-pressed" : "aria-checked";
  var timer = null;
  var locked = false;

  function say(message) {
    status.textContent = message;
  }

  function selection() {
    return cards
      .filter(function (card) {
        return card.getAttribute(checkedAttr) === "true";
      })
      .map(function (card) {
        return card.getAttribute("data-option-id");
      });
  }

  function lock() {
    locked = true;
    cards.forEach(function (card) {
      card.disabled = true;
    });
    noteField.disabled = true;
    proceedButton.disabled = true;
  }

  function supersede() {
    if (timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
    lock();
    banner.hidden = false;
    say("");
  }

  function note() {
    var value = noteField.value.trim();
    return value === "" ? null : value;
  }

  function send(type, choice, text) {
    var body = {
      nonce: nonce,
      type: type,
      choice: choice,
      text: text,
      selected: selection(),
      note: note()
    };
    return window
      .fetch("/_quirk/event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      })
      .then(function (response) {
        if (response.status === 409) {
          supersede();
          return false;
        }
        if (!response.ok) {
          say("The companion rejected that (" + response.status + "). Tell the agent in the terminal.");
          return false;
        }
        return true;
      })
      .catch(function () {
        say("The companion server is not reachable. Tell the agent in the terminal.");
        return false;
      });
  }

  function syncRoving() {
    if (multi) {
      return;
    }
    var active = cards.filter(function (card) {
      return card.getAttribute("aria-checked") === "true";
    })[0] || cards[0];
    cards.forEach(function (card) {
      card.setAttribute("tabindex", card === active ? "0" : "-1");
    });
  }

  function choose(card) {
    if (locked) {
      return;
    }
    if (multi) {
      card.setAttribute("aria-pressed", card.getAttribute("aria-pressed") === "true" ? "false" : "true");
    } else {
      if (card.getAttribute("aria-checked") === "true") {
        return;
      }
      cards.forEach(function (other) {
        other.setAttribute("aria-checked", other === card ? "true" : "false");
      });
      syncRoving();
    }
    send("click", card.getAttribute("data-option-id"), card.getAttribute("data-label"));
  }

  cards.forEach(function (card, index) {
    card.addEventListener("click", function () {
      choose(card);
    });
    if (!multi) {
      card.addEventListener("keydown", function (event) {
        var step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[event.key];
        if (step === undefined) {
          return;
        }
        event.preventDefault();
        var next = cards[(index + step + cards.length) % cards.length];
        next.focus();
        choose(next);
      });
    }
  });

  proceedButton.addEventListener("click", function () {
    if (locked) {
      return;
    }
    send("proceed", null, "Proceed").then(function (sent) {
      if (sent) {
        lock();
        say("Sent. The agent has your choice; this screen is done.");
      }
    });
  });

  if (reload) {
    reload.addEventListener("click", function () {
      window.location.reload();
    });
  }

  function poll() {
    window
      .fetch("/_quirk/state", { cache: "no-store" })
      .then(function (response) {
        return response.json();
      })
      .then(function (state) {
        if (state && state.nonce && state.nonce !== nonce) {
          supersede();
        }
      })
      .catch(function () {});
  }

  syncRoving();
  timer = window.setInterval(poll, 2000);
})();

class QuirkArtifactSummary extends HTMLElement {
  connectedCallback() {
    this.render([
      ["BUGS", this.getAttribute("bugs")],
      ["DEFERRED", this.getAttribute("deferred")],
      ["TEST_BACKLOG", this.getAttribute("test-backlog")],
      ["proposals", this.getAttribute("proposals")],
      ["ADRs", this.getAttribute("adrs")],
    ]);
  }

  render(rows) {
    const card = buildCard(this.getAttribute("title") || "Typed artifact summary", this.getAttribute("status"));
    const list = document.createElement("dl");
    list.className = "quirk-kv";
    for (const [label, value] of rows) {
      appendKeyValue(list, label, value || "not reported");
    }
    appendSlottedFallback(card, this);
    card.append(list);
    this.replaceChildren(card);
  }
}

class QuirkTddCycle extends HTMLElement {
  connectedCallback() {
    const card = buildCard(this.getAttribute("title") || "TDD cycle", this.getAttribute("status"));
    const list = document.createElement("dl");
    list.className = "quirk-kv";
    appendKeyValue(list, "RED", this.getAttribute("red") || "not reported");
    appendKeyValue(list, "GREEN", this.getAttribute("green") || "not reported");
    appendKeyValue(list, "REFACTOR", this.getAttribute("refactor") || "not reported");
    appendKeyValue(list, "Verification", this.getAttribute("verification") || "not reported");
    appendKeyValue(list, "Deferred/skipped debt", this.getAttribute("debt") || "none reported");
    appendSlottedFallback(card, this);
    card.append(list);
    this.replaceChildren(card);
  }
}

class QuirkPlanReview extends HTMLElement {
  connectedCallback() {
    const card = buildCard(this.getAttribute("title") || "Plan readiness", this.getAttribute("status"));
    const list = document.createElement("dl");
    list.className = "quirk-kv";
    for (const key of ["scope", "clarity", "files", "tests", "risks", "handoff"]) {
      appendKeyValue(list, titleCase(key), this.getAttribute(key) || "not reviewed");
    }
    appendSlottedFallback(card, this);
    card.append(list);
    this.replaceChildren(card);
  }
}

class QuirkReviewFinding extends HTMLElement {
  connectedCallback() {
    const card = buildCard(`Review finding: ${this.getAttribute("severity") || "unspecified"}`, this.getAttribute("status"));
    const list = document.createElement("dl");
    list.className = "quirk-kv";
    appendKeyValue(list, "Path", this.getAttribute("path") || "not specified");
    appendKeyValue(list, "Recommendation", this.getAttribute("recommendation") || "not specified");
    appendSlottedFallback(card, this);
    card.append(list);
    this.replaceChildren(card);
  }
}

function buildCard(title, status) {
  const section = document.createElement("section");
  section.className = "quirk-card";
  const heading = document.createElement("h3");
  heading.textContent = title;
  section.append(heading);
  if (status) {
    const badge = document.createElement("span");
    badge.className = "quirk-badge";
    badge.textContent = status;
    section.append(badge);
  }
  return section;
}

function appendKeyValue(list, key, value) {
  const dt = document.createElement("dt");
  dt.textContent = key;
  const dd = document.createElement("dd");
  dd.textContent = value;
  list.append(dt, dd);
}

function appendSlottedFallback(card, source) {
  const fallback = source.textContent.trim();
  if (!fallback) return;
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = "Plain Markdown fallback";
  const pre = document.createElement("pre");
  pre.textContent = fallback;
  details.append(summary, pre);
  card.append(details);
}

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

customElements.define("quirk-artifact-summary", QuirkArtifactSummary);
customElements.define("quirk-tdd-cycle", QuirkTddCycle);
customElements.define("quirk-plan-review", QuirkPlanReview);
customElements.define("quirk-review-finding", QuirkReviewFinding);

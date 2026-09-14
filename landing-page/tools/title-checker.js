(function () {
  const statusEl = document.getElementById("check-status");
  const report = document.getElementById("report");
  const titleInput = document.getElementById("title-input");
  const checkBtn = document.getElementById("check-title-btn");
  const suggestBtn = document.getElementById("suggest-title-btn");
  const aiBtn = document.getElementById("ai-title-btn");
  const checkFeedBtn = document.getElementById("check-feed-titles-btn");
  const feedUrl = document.getElementById("feed-url");
  const feedFile = document.getElementById("feed-file");
  const panelOne = document.getElementById("panel-one");
  const panelFeed = document.getElementById("panel-feed");
  const modeOne = document.getElementById("mode-one");
  const modeFeed = document.getElementById("mode-feed");
  const verdictBanner = document.getElementById("verdict-banner");
  const verdictLabel = document.getElementById("verdict-label");
  const verdictDetail = document.getElementById("verdict-detail");
  const issuesHeading = document.getElementById("issues-heading");
  const issueList = document.getElementById("issue-list");
  const tipsHeading = document.getElementById("tips-heading");
  const tipList = document.getElementById("tip-list");
  const suggestBox = document.getElementById("suggest-box");
  const suggestText = document.getElementById("suggest-text");
  const suggestDisclaimer = document.getElementById("suggest-disclaimer");
  const copyBtn = document.getElementById("copy-suggest-btn");
  const feedSummary = document.getElementById("feed-summary");
  const feedSamplesWrap = document.getElementById("feed-samples-wrap");
  const feedSamples = document.getElementById("feed-samples");
  const feedDisclaimer = document.getElementById("feed-disclaimer");
  const reportHeading = document.getElementById("report-heading");

  const VERDICT_COPY = {
    ok: {
      label: "Looks solid",
      detail:
        "No noise or length problems. Soft apparel tips below are optional — we never invent attributes.",
    },
    improve: {
      label: "Can improve",
      detail:
        "Marketplace noise or length — tighten what is already in the title. We will not invent material, size, or audience.",
    },
    weak: {
      label: "Too weak",
      detail: "Not enough product signal to judge well. Start with product type and known attributes.",
    },
  };

  function setStatus(text, isError) {
    if (!statusEl) return;
    statusEl.hidden = !text;
    statusEl.textContent = text || "";
    statusEl.classList.toggle("tools-status--err", !!isError);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function missingLabel(code) {
    const map = {
      missing_material: "material",
      missing_style: "style",
      missing_audience: "audience",
      missing_color: "color",
      missing_size: "size",
    };
    return map[code] || null;
  }

  function setMode(mode) {
    const isFeed = mode === "feed";
    if (panelOne) panelOne.hidden = isFeed;
    if (panelFeed) panelFeed.hidden = !isFeed;
    if (modeOne) {
      modeOne.classList.toggle("is-on", !isFeed);
      modeOne.setAttribute("aria-selected", String(!isFeed));
    }
    if (modeFeed) {
      modeFeed.classList.toggle("is-on", isFeed);
      modeFeed.setAttribute("aria-selected", String(isFeed));
    }
    setStatus("");
  }

  function renderOneTitle(data, { focusSuggest } = {}) {
    if (!report) return;
    report.hidden = false;
    if (reportHeading) reportHeading.textContent = "Title report";
    if (feedSummary) feedSummary.hidden = true;
    if (feedSamplesWrap) feedSamplesWrap.hidden = true;
    if (verdictBanner) verdictBanner.hidden = false;
    if (suggestBox) suggestBox.hidden = false;

    const verdict = data.verdict || "improve";
    const copy = VERDICT_COPY[verdict] || VERDICT_COPY.improve;
    if (verdictBanner) verdictBanner.setAttribute("data-verdict", verdict);
    if (verdictLabel) verdictLabel.textContent = copy.label;
    if (verdictDetail) verdictDetail.textContent = copy.detail;

    const issues = data.issues || [];
    const tips = data.tips || [];

    if (issueList) {
      issueList.innerHTML = "";
      issues.forEach((issue) => {
        const li = document.createElement("li");
        li.className = "tools-issue";
        li.innerHTML =
          "<strong>" + escapeHtml(issue.label || issue.code) + "</strong>";
        if (issue.advice) {
          const tip = document.createElement("p");
          tip.className = "tools-issue-advice";
          tip.textContent = issue.advice;
          li.appendChild(tip);
        }
        issueList.appendChild(li);
      });
      if (!issues.length) {
        issueList.innerHTML =
          '<li class="tools-ok">No hard issues (noise / length) for this title.</li>';
      }
    }
    if (issuesHeading) issuesHeading.hidden = false;

    if (tipList) {
      tipList.innerHTML = "";
      if (tips.length) {
        const names = tips
          .map((t) => missingLabel(t.code) || t.label || t.code)
          .filter(Boolean);
        const li = document.createElement("li");
        li.className = "tools-issue tools-issue--missing";
        li.innerHTML =
          "<strong>Optional when known:</strong> " +
          escapeHtml(names.join(" / "));
        const tip = document.createElement("p");
        tip.className = "tools-issue-advice";
        tip.textContent =
          "Apparel-only tips. Add only attributes you already know — do not invent material, brand, or GTIN.";
        li.appendChild(tip);
        tipList.appendChild(li);
      }
    }
    if (tipsHeading) tipsHeading.hidden = !tips.length;

    const suggested = (data.suggested_title || "").trim();
    const input = (data.input || "").trim();
    const changed =
      Boolean(suggested) && suggested.toLowerCase() !== input.toLowerCase();
    if (suggestBox && suggestText) {
      if (changed) {
        suggestBox.hidden = false;
        suggestText.textContent = suggested;
        if (suggestDisclaimer) {
          const src =
            data.source === "ai" ? " (AI, filtered to your words)" : "";
          suggestDisclaimer.textContent =
            (data.disclaimer ||
              "Suggestion only — do not invent brand or GTIN.") + src;
        }
      } else {
        suggestBox.hidden = true;
      }
    }

    if (focusSuggest && suggestBox && !suggestBox.hidden) {
      suggestBox.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      report.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function renderFeedTitles(data) {
    report.hidden = false;
    if (reportHeading) reportHeading.textContent = "Feed titles report";
    if (verdictBanner) verdictBanner.hidden = true;
    if (suggestBox) suggestBox.hidden = true;
    if (feedSummary) {
      feedSummary.hidden = false;
      feedSummary.textContent =
        data.titles_checked +
        " titles checked · " +
        data.titles_with_issues +
        " with hard issues · " +
        data.title_issue_total +
        " hard issue flags" +
        (data.truncated ? " (sample capped)" : "");
    }
    if (issuesHeading) issuesHeading.hidden = false;
    if (issueList) {
      issueList.innerHTML = "";
      (data.buckets || []).forEach((b) => {
        const li = document.createElement("li");
        li.className = "tools-issue";
        li.innerHTML =
          "<strong>" +
          escapeHtml(b.label || b.code) +
          "</strong> · " +
          escapeHtml(String(b.count));
        if (b.advice) {
          const tip = document.createElement("p");
          tip.className = "tools-issue-advice";
          tip.textContent = b.advice;
          li.appendChild(tip);
        }
        issueList.appendChild(li);
      });
      if (!(data.buckets || []).length) {
        issueList.innerHTML =
          '<li class="tools-ok">No hard title issues (noise / length / empty) in this sample.</li>';
      }
    }
    const tipBuckets = data.tip_buckets || [];
    if (tipsHeading) tipsHeading.hidden = !tipBuckets.length;
    if (tipList) {
      tipList.innerHTML = "";
      tipBuckets.forEach((b) => {
        const li = document.createElement("li");
        li.className = "tools-issue tools-issue--missing";
        li.innerHTML =
          "<strong>" +
          escapeHtml(b.label || b.code) +
          "</strong> · " +
          escapeHtml(String(b.count));
        if (b.advice) {
          const tip = document.createElement("p");
          tip.className = "tools-issue-advice";
          tip.textContent = b.advice;
          li.appendChild(tip);
        }
        tipList.appendChild(li);
      });
    }
    if (feedSamplesWrap && feedSamples) {
      const samples = data.samples || [];
      feedSamplesWrap.hidden = !samples.length;
      feedSamples.innerHTML = "";
      samples.forEach((s) => {
        const li = document.createElement("li");
        li.className = "tools-issue";
        li.innerHTML =
          "<strong>" +
          escapeHtml(s.id || "") +
          "</strong> · " +
          escapeHtml(s.verdict || "") +
          "<p class=\"tools-issue-advice\">" +
          escapeHtml(s.title || "") +
          (s.suggested_title
            ? "<br><em>Suggest:</em> " + escapeHtml(s.suggested_title)
            : "") +
          "</p>";
        feedSamples.appendChild(li);
      });
    }
    if (feedDisclaimer) {
      feedDisclaimer.textContent = data.disclaimer || "";
    }
    report.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function runOne({ focusSuggest, useAi } = {}) {
    const title = (titleInput && titleInput.value) || "";
    if (!title.trim()) {
      setStatus("Paste a product title first.", true);
      return;
    }
    setStatus(useAi ? "Improving with AI…" : "Checking…");
    [checkBtn, suggestBtn, aiBtn].forEach((b) => b && (b.disabled = true));
    try {
      const endpoint = useAi
        ? "/api/public/title-check/ai"
        : "/api/public/title-check";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Check failed"
        );
      }
      setStatus(
        useAi && data.source === "rules"
          ? "AI unavailable — showing rule-based suggestion."
          : ""
      );
      renderOneTitle(data, { focusSuggest: focusSuggest || useAi });
    } catch (err) {
      setStatus(err.message || "Check failed", true);
    } finally {
      [checkBtn, suggestBtn, aiBtn].forEach((b) => b && (b.disabled = false));
    }
  }

  async function runFeedTitles() {
    const url = (feedUrl && feedUrl.value) || "";
    const file = feedFile && feedFile.files && feedFile.files[0];
    if (!url.trim() && !file) {
      setStatus("Paste a feed URL or choose an XML file.", true);
      return;
    }
    setStatus("Scanning titles…");
    if (checkFeedBtn) checkFeedBtn.disabled = true;
    try {
      let res;
      if (file) {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("max_items", "500");
        res = await fetch("/api/public/title-check/feed/upload", {
          method: "POST",
          body: fd,
        });
      } else {
        res = await fetch("/api/public/title-check/feed", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: url.trim(), max_items: 500 }),
        });
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Check failed"
        );
      }
      setStatus("");
      renderFeedTitles(data);
    } catch (err) {
      setStatus(err.message || "Check failed", true);
    } finally {
      if (checkFeedBtn) checkFeedBtn.disabled = false;
    }
  }

  if (modeOne) modeOne.addEventListener("click", () => setMode("one"));
  if (modeFeed) modeFeed.addEventListener("click", () => setMode("feed"));
  if (checkBtn)
    checkBtn.addEventListener("click", () =>
      runOne({ focusSuggest: false, useAi: false })
    );
  if (suggestBtn)
    suggestBtn.addEventListener("click", () =>
      runOne({ focusSuggest: true, useAi: false })
    );
  if (aiBtn)
    aiBtn.addEventListener("click", () =>
      runOne({ focusSuggest: true, useAi: true })
    );
  if (checkFeedBtn) checkFeedBtn.addEventListener("click", runFeedTitles);
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const t = (suggestText && suggestText.textContent) || "";
      if (!t) return;
      try {
        await navigator.clipboard.writeText(t);
        setStatus("Copied suggested title.");
      } catch {
        setStatus("Could not copy — select the text manually.", true);
      }
    });
  }
})();

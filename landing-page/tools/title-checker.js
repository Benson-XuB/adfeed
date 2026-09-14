(function () {
  const statusEl = document.getElementById("check-status");
  const report = document.getElementById("report");
  const titleInput = document.getElementById("title-input");
  const checkBtn = document.getElementById("check-title-btn");
  const suggestBtn = document.getElementById("suggest-title-btn");
  const aiBtn = document.getElementById("ai-title-btn");
  const verdictBanner = document.getElementById("verdict-banner");
  const verdictLabel = document.getElementById("verdict-label");
  const verdictDetail = document.getElementById("verdict-detail");
  const issuesHeading = document.getElementById("issues-heading");
  const issueList = document.getElementById("issue-list");
  const suggestBox = document.getElementById("suggest-box");
  const suggestText = document.getElementById("suggest-text");
  const suggestDisclaimer = document.getElementById("suggest-disclaimer");
  const copyBtn = document.getElementById("copy-suggest-btn");

  const VERDICT_COPY = {
    ok: {
      label: "Looks solid",
      detail: "This title already carries the main shopping signals we check for.",
    },
    improve: {
      label: "Can improve",
      detail: "Missing signals or marketplace noise — tighten before it hits Shopping cards.",
    },
    weak: {
      label: "Too weak",
      detail: "Not enough product signal to judge well. Start with audience + product type.",
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

  function renderReport(data, { focusSuggest } = {}) {
    if (!report) return;
    report.hidden = false;

    const verdict = data.verdict || "improve";
    const copy = VERDICT_COPY[verdict] || VERDICT_COPY.improve;
    if (verdictBanner) {
      verdictBanner.hidden = false;
      verdictBanner.setAttribute("data-verdict", verdict);
    }
    if (verdictLabel) verdictLabel.textContent = copy.label;
    if (verdictDetail) verdictDetail.textContent = copy.detail;

    const issues = data.issues || [];
    const missing = [];
    const other = [];
    issues.forEach((issue) => {
      const m = missingLabel(issue.code);
      if (m) missing.push(m);
      else other.push(issue);
    });

    if (issueList) {
      issueList.innerHTML = "";
      if (missing.length) {
        const li = document.createElement("li");
        li.className = "tools-issue tools-issue--missing";
        li.innerHTML = `<strong>Missing:</strong> ${escapeHtml(missing.join(" / "))}`;
        const tip = document.createElement("p");
        tip.className = "tools-issue-advice";
        tip.textContent =
          "Add only attributes you already know from the product — do not invent material, brand, or GTIN.";
        li.appendChild(tip);
        issueList.appendChild(li);
      }
      other.forEach((issue) => {
        const li = document.createElement("li");
        li.className = "tools-issue";
        li.innerHTML = `<strong>${escapeHtml(issue.label || issue.code)}</strong>`;
        if (issue.advice) {
          const tip = document.createElement("p");
          tip.className = "tools-issue-advice";
          tip.textContent = issue.advice;
          li.appendChild(tip);
        }
        issueList.appendChild(li);
      });
    }

    if (issuesHeading) {
      issuesHeading.hidden = !issues.length;
    }
    if (!issues.length && issueList) {
      issueList.innerHTML = '<li class="tools-ok">No issues flagged for this title.</li>';
    }

    const suggested = (data.suggested_title || "").trim();
    if (suggestBox && suggestText) {
      if (suggested) {
        suggestBox.hidden = false;
        suggestText.textContent = suggested;
        if (suggestDisclaimer) {
          const src = data.source === "ai" ? " (AI, filtered to your words)" : "";
          suggestDisclaimer.textContent =
            (data.disclaimer || "Suggestion only — do not invent brand or GTIN.") + src;
        }
      } else {
        suggestBox.hidden = true;
      }
    }

    if (focusSuggest && suggestBox && !suggestBox.hidden) {
      suggestBox.scrollIntoView({ behavior: "smooth", block: "center" });
      suggestBox.classList.add("is-highlight");
      window.setTimeout(() => suggestBox.classList.remove("is-highlight"), 1200);
    } else {
      report.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  async function runCheck({ focusSuggest, useAi } = {}) {
    const title = (titleInput && titleInput.value) || "";
    if (!title.trim()) {
      setStatus("Paste a product title first.", true);
      if (titleInput) titleInput.focus();
      return;
    }
    setStatus(useAi ? "Improving with AI…" : "Checking…");
    if (checkBtn) checkBtn.disabled = true;
    if (suggestBtn) suggestBtn.disabled = true;
    if (aiBtn) aiBtn.disabled = true;
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
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((d) => d.msg || d).join("; ")
              : "Check failed";
        throw new Error(detail);
      }
      setStatus(
        useAi && data.source === "rules"
          ? "AI unavailable — showing rule-based suggestion."
          : ""
      );
      renderReport(data, { focusSuggest: focusSuggest || useAi });
    } catch (err) {
      setStatus(err.message || "Check failed", true);
    } finally {
      if (checkBtn) checkBtn.disabled = false;
      if (suggestBtn) suggestBtn.disabled = false;
      if (aiBtn) aiBtn.disabled = false;
    }
  }

  if (checkBtn) {
    checkBtn.addEventListener("click", () =>
      runCheck({ focusSuggest: false, useAi: false })
    );
  }
  if (suggestBtn) {
    suggestBtn.addEventListener("click", () =>
      runCheck({ focusSuggest: true, useAi: false })
    );
  }
  if (aiBtn) {
    aiBtn.addEventListener("click", () =>
      runCheck({ focusSuggest: true, useAi: true })
    );
  }
  if (titleInput) {
    titleInput.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        runCheck({ focusSuggest: false });
      }
    });
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const text = (suggestText && suggestText.textContent) || "";
      if (!text) return;
      const original = copyBtn.textContent;
      try {
        await navigator.clipboard.writeText(text);
        copyBtn.textContent = "Copied";
      } catch (_) {
        copyBtn.textContent = "Copy failed";
      }
      window.setTimeout(() => {
        copyBtn.textContent = original || "Copy";
      }, 1500);
    });
  }
})();

(function () {
  const statusEl = document.getElementById("gi-status");
  const statusConnected = document.getElementById("gi-status-connected");
  const panel = document.getElementById("gi-panel");
  const disconnected = document.getElementById("gi-disconnected");
  const connected = document.getElementById("gi-connected");
  const merchantSelect = document.getElementById("merchant-select");
  const merchantId = document.getElementById("merchant-id");
  const merchantManual = document.getElementById("merchant-id-manual");
  const logoutBtn = document.getElementById("logout-btn");
  const report = document.getElementById("gi-report");
  const dx = document.getElementById("gi-dx");
  const waitlistSection = document.getElementById("waitlist");
  const params = new URLSearchParams(location.search);

  function setStatus(el, text, isError) {
    if (!el) return;
    el.hidden = !text;
    el.textContent = text || "";
    el.classList.toggle("tools-status--err", !!isError);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function asList(val) {
    if (Array.isArray(val)) return val.filter(Boolean);
    if (typeof val === "string" && val.trim()) return [val.trim()];
    return [];
  }

  function setConnectedUI(isConnected) {
    panel.dataset.state = isConnected ? "connected" : "disconnected";
    disconnected.hidden = isConnected;
    connected.hidden = !isConnected;
  }

  async function refreshStatus() {
    const res = await fetch("/api/public/google/status", { credentials: "same-origin" });
    const data = await res.json();
    const isConnected = !!data.connected;
    setConnectedUI(isConnected);
    if (isConnected) {
      setStatus(statusConnected, "");
      await loadAccounts();
    } else if (params.get("error")) {
      setStatus(statusEl, "Google connection failed (" + params.get("error") + "). Try again.", true);
    }
  }

  async function loadAccounts() {
    try {
      const res = await fetch("/api/public/google/accounts", { credentials: "same-origin" });
      if (!res.ok) {
        document.getElementById("gi-manual").hidden = false;
        return;
      }
      const data = await res.json();
      const accounts = data.accounts || [];
      if (!accounts.length) {
        document.getElementById("gi-manual").hidden = false;
        merchantSelect.innerHTML = '<option value="">Enter ID manually</option>';
        return;
      }
      merchantSelect.innerHTML = accounts
        .map(
          (a) =>
            `<option value="${escapeHtml(a.merchant_id)}">${escapeHtml(a.display_name)} · ${escapeHtml(a.merchant_id)}</option>`
        )
        .join("");
      merchantId.value = accounts[0].merchant_id;
      merchantSelect.onchange = () => {
        merchantId.value = merchantSelect.value;
      };
    } catch (_) {
      document.getElementById("gi-manual").hidden = false;
    }
  }

  function resolveMerchantId() {
    const manual = (merchantManual.value || "").trim();
    if (manual) return manual;
    return (merchantId.value || merchantSelect.value || "").trim();
  }

  async function loadIssues() {
    const mid = resolveMerchantId();
    if (!/^\d+$/.test(mid)) {
      setStatus(statusConnected, "Enter a numeric Merchant Center ID.", true);
      return;
    }
    setStatus(statusConnected, "Diagnosing…");
    try {
      const res = await fetch(
        "/api/public/google/issues?merchant_id=" + encodeURIComponent(mid) + "&limit=50",
        { credentials: "same-origin" }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Diagnosis failed");
      setStatus(statusConnected, "");
      render(data);
    } catch (err) {
      setStatus(statusConnected, err.message || "Failed", true);
    }
  }

  async function loadDemo(kind) {
    setStatus(statusEl, "");
    setStatus(statusConnected, "Loading demo…");
    try {
      const res = await fetch("/api/public/google/demo/" + encodeURIComponent(kind));
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Demo failed");
      setStatus(statusConnected, data.demo ? "Demo: " + kind : "");
      render(data);
    } catch (err) {
      setStatus(statusConnected, err.message || "Demo failed", true);
    }
  }

  function takeawayFor(type) {
    if (type === "ACCOUNT") return "Account problem → fix it in Merchant Center.";
    if (type === "FEED") return "Feed problem → clean product data, then generate a better feed.";
    if (type === "MIXED") return "Two issues — fix the account first, then the feed.";
    return "Nothing disapproved in this sample.";
  }

  function badgeFor(type) {
    if (type === "ACCOUNT") return "Account";
    if (type === "FEED") return "Feed";
    if (type === "MIXED") return "Mixed";
    return "Clear";
  }

  function evidenceHtml(type, d) {
    const problems = d.common_problems || [];
    const signalN = d.signal_count || d.affected_count || 0;
    const pctA = Math.round((d.account_share || 0) * 100);
    const pctF = Math.round((d.feed_share || 0) * 100);
    const feedOfferN = d.feed_offer_count || 0;
    const accountN = d.account_signal_count || 0;
    const feedN = d.feed_signal_count || 0;

    if (type === "ACCOUNT") {
      return `
        <details class="gi-evidence-weak">
          <summary>Why we think this (optional)</summary>
          <p>
            ${signalN} Merchant API signals in this sample look account-level (${pctA}%).
            Exact policy name is only shown in Merchant Center.
          </p>
        </details>
      `;
    }

    if (type === "FEED") {
      const rows = problems.length
        ? problems
            .map(
              (p) =>
                `<li><span>${escapeHtml(p.label)}</span><em>${escapeHtml(String(p.count))}</em></li>`
            )
            .join("")
        : "<li><span>Product / feed signals</span><em>" + escapeHtml(String(feedN || signalN)) + "</em></li>";
      return `
        <div class="gi-evidence-card">
          <p class="gi-evidence-card-lead">
            ${feedOfferN ? escapeHtml(String(feedOfferN)) + " products with feed issues in this sample" : escapeHtml(String(signalN)) + " feed-related signals in this sample"}
          </p>
          <p class="gi-evidence-card-sub">Issue type × count</p>
          <ul class="gi-evidence-table">${rows}</ul>
        </div>
      `;
    }

    if (type === "MIXED") {
      const rows = problems.length
        ? problems
            .map(
              (p) =>
                `<li><span>${escapeHtml(p.label)}</span><em>${escapeHtml(String(p.count))}</em></li>`
            )
            .join("")
        : "<li><span>Product / feed signals</span><em>" + escapeHtml(String(feedN)) + "</em></li>";
      return `
        <div class="gi-tracks">
          <article class="gi-track gi-track--account">
            <p class="gi-track-order">1 · Fix first</p>
            <h4>Account</h4>
            <p>${escapeHtml(String(accountN))} account-level signals (${pctA}%). Clear the Merchant Center policy warning before anything else.</p>
          </article>
          <article class="gi-track gi-track--feed">
            <p class="gi-track-order">2 · Then feed</p>
            <h4>Feed</h4>
            <p>${escapeHtml(String(feedN))} feed-related signals (${pctF}%). Clean these after the account is clear.</p>
            <ul class="gi-evidence-table">${rows}</ul>
          </article>
        </div>
      `;
    }

    return `<p class="gi-evidence-empty">No disapproval signals in this pull.</p>`;
  }

  function actionCta(type) {
    if (type === "ACCOUNT") {
      return '<a class="btn btn-primary" href="https://merchants.google.com/" target="_blank" rel="noopener">Open Merchant Center</a>';
    }
    if (type === "FEED") {
      return '<a class="btn btn-primary" href="#waitlist">Get early access</a><a class="btn btn-ghost" href="/tools/feed-checker">Check a feed URL</a>';
    }
    if (type === "MIXED") {
      return '<a class="btn btn-primary" href="https://merchants.google.com/" target="_blank" rel="noopener">Fix account first</a><a class="btn btn-ghost" href="#waitlist">Then get AdFeed for feed</a>';
    }
    return '<a class="btn btn-ghost" href="/tools/feed-checker">Check a feed URL</a><a class="btn btn-primary" href="#waitlist">Get early access</a>';
  }

  function adfeedHtml(type, data) {
    if (type === "ACCOUNT") {
      return `
        <p>AdFeed <strong>cannot</strong> clear account suspensions — only Merchant Center can.</p>
        <p class="gi-adfeed-soft">After your account is clear, if products are still rejected, AdFeed can help clean the feed.</p>
        <a class="gi-soft-link" href="#waitlist">Get early access →</a>
      `;
    }
    if (type === "FEED") {
      const helps = (data.adfeed_helps || []).slice(0, 3);
      return `
        <p><strong>AdFeed can help</strong> with the feed side:</p>
        <ul class="gi-adfeed-list">${helps.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>
        <div class="gi-cta-row">
          <a class="btn btn-primary" href="#waitlist">Get early access</a>
        </div>
      `;
    }
    if (type === "MIXED") {
      return `
        <p><strong>Order matters:</strong> account first (Merchant Center), then feed (AdFeed).</p>
        <p class="gi-adfeed-soft">AdFeed never invents GTINs and cannot clear account policy blocks.</p>
        <div class="gi-cta-row">
          <a class="btn btn-ghost" href="#waitlist">Get early access for feed cleanup</a>
        </div>
      `;
    }
    return `<p>Optional: join the waitlist if you want a cleaner Shopping feed later.</p>`;
  }

  function render(data) {
    const d = data.diagnosis || {};
    const type = d.issue_type || "NONE";
    const headline = d.headline || takeawayFor(type);
    const means = asList(d.what_this_means);
    const steps = asList(d.what_you_should_do);

    report.hidden = false;
    dx.dataset.type = type;
    if (data.demo) dx.dataset.demo = "1";
    else delete dx.dataset.demo;

    document.getElementById("gi-type-label").textContent = badgeFor(type);
    document.getElementById("gi-headline").textContent = headline;
    document.getElementById("gi-takeaway").textContent = takeawayFor(type);
    document.getElementById("gi-evidence-body").innerHTML = evidenceHtml(type, d);
    document.getElementById("gi-means").innerHTML = means
      .map((t) => `<p>${escapeHtml(t)}</p>`)
      .join("");
    document.getElementById("gi-steps").innerHTML = steps
      .map((t) => `<li>${escapeHtml(t)}</li>`)
      .join("");
    document.getElementById("gi-primary-cta").innerHTML = actionCta(type);
    document.getElementById("gi-adfeed-body").innerHTML = adfeedHtml(type, data);

    const waitlistDefault = document.getElementById("waitlist-default");
    const waitlistFeed = document.getElementById("waitlist-feed");
    const mode = type === "FEED" || type === "MIXED" ? "feed" : type === "ACCOUNT" ? "account" : "default";
    waitlistSection.hidden = false;
    waitlistSection.dataset.mode = mode;
    if (mode === "feed") {
      waitlistDefault.hidden = true;
      waitlistFeed.hidden = false;
    } else {
      waitlistDefault.hidden = false;
      waitlistFeed.hidden = true;
    }

    report.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  document.getElementById("load-issues-btn").addEventListener("click", loadIssues);
  document.getElementById("gi-manual-toggle").addEventListener("click", () => {
    const box = document.getElementById("gi-manual");
    box.hidden = !box.hidden;
  });
  logoutBtn.addEventListener("click", async () => {
    await fetch("/api/public/google/logout", { method: "POST", credentials: "same-origin" });
    location.href = "/tools/google-issues";
  });
  document.querySelectorAll("[data-demo]").forEach((btn) => {
    btn.addEventListener("click", () => loadDemo(btn.getAttribute("data-demo")));
  });

  const demoParam = params.get("demo");
  if (demoParam && /^(account|feed|mixed|none)$/.test(demoParam)) {
    loadDemo(demoParam);
  }
  refreshStatus();
})();

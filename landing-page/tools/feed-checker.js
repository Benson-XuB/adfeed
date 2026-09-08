(function () {
  const statusEl = document.getElementById("check-status");
  const report = document.getElementById("report");
  const meta = document.getElementById("report-meta");
  const bucketsEl = document.getElementById("report-buckets");
  const helpsEl = document.getElementById("report-helps");
  const cannotEl = document.getElementById("report-cannot");
  const urlInput = document.getElementById("feed-url");
  const fileInput = document.getElementById("feed-file");
  const panelUrl = document.getElementById("panel-url");
  const panelFile = document.getElementById("panel-file");

  document.querySelectorAll(".tools-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tools-tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      const which = tab.getAttribute("data-tab");
      panelUrl.hidden = which !== "url";
      panelFile.hidden = which !== "file";
    });
  });

  function setStatus(text, isError) {
    if (!statusEl) return;
    statusEl.hidden = !text;
    statusEl.textContent = text || "";
    statusEl.classList.toggle("tools-status--err", !!isError);
  }

  function renderList(el, items) {
    el.innerHTML = "";
    (items || []).forEach((t) => {
      const li = document.createElement("li");
      li.textContent = t;
      el.appendChild(li);
    });
  }

  function renderReport(data) {
    report.hidden = false;
    meta.textContent = data.truncated
      ? `Checked ${data.item_count} items (truncated to limit).`
      : `Checked ${data.item_count} items.`;
    bucketsEl.innerHTML = "";
    (data.buckets || []).forEach((b) => {
      const block = document.createElement("article");
      block.className = "tools-bucket";
      const samples = (b.samples || [])
        .map((s) => `<li><code>${escapeHtml(s.id || "")}</code> — ${escapeHtml(s.title || "")}</li>`)
        .join("");
      block.innerHTML = `
        <h3><span class="tools-count">${b.count}</span> ${escapeHtml(b.label || b.code)}</h3>
        <p>${escapeHtml(b.advice || "")}</p>
        ${samples ? `<ul class="tools-samples">${samples}</ul>` : ""}
      `;
      bucketsEl.appendChild(block);
    });
    if (!(data.buckets || []).length) {
      bucketsEl.innerHTML = "<p class=\"tools-ok\">No major issues in the sample we checked.</p>";
    }
    renderList(helpsEl, data.adfeed_helps);
    renderList(cannotEl, data.adfeed_cannot);
    report.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function runUrl() {
    const url = (urlInput.value || "").trim();
    if (!url) {
      setStatus("Enter a feed URL.", true);
      return;
    }
    setStatus("Checking…");
    try {
      const res = await fetch("/api/public/feed-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, max_items: 500 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Check failed");
      setStatus("");
      renderReport(data);
    } catch (err) {
      setStatus(err.message || "Check failed", true);
    }
  }

  async function runFile() {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      setStatus("Choose an XML file.", true);
      return;
    }
    setStatus("Checking…");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("max_items", "500");
      const res = await fetch("/api/public/feed-check/upload", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Check failed");
      setStatus("");
      renderReport(data);
    } catch (err) {
      setStatus(err.message || "Check failed", true);
    }
  }

  document.getElementById("check-url-btn").addEventListener("click", runUrl);
  document.getElementById("check-file-btn").addEventListener("click", runFile);
})();

(function () {
  const statusEl = document.getElementById("check-status");
  const report = document.getElementById("report");
  const meta = document.getElementById("report-meta");
  const summaryEl = document.getElementById("report-summary");
  const issuesHeading = document.getElementById("issues-heading");
  const bucketsEl = document.getElementById("report-buckets");
  const passedWrap = document.getElementById("report-passed");
  const passedList = document.getElementById("report-passed-list");
  const helpsEl = document.getElementById("report-helps");
  const cannotEl = document.getElementById("report-cannot");
  const urlInput = document.getElementById("feed-url");
  const fileInput = document.getElementById("feed-file");
  const panelUrl = document.getElementById("panel-url");
  const panelFile = document.getElementById("panel-file");
  const dropzone = document.getElementById("feed-dropzone");
  const dropTitle = document.getElementById("dropzone-title");
  const dropHint = document.getElementById("dropzone-hint");

  function setTab(which, { focus } = {}) {
    document.querySelectorAll(".tools-tab").forEach((t) => {
      const on = t.getAttribute("data-tab") === which;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    if (panelUrl) {
      const on = which === "url";
      panelUrl.classList.toggle("is-open", on);
      panelUrl.hidden = !on;
    }
    if (panelFile) {
      const on = which === "file";
      panelFile.classList.toggle("is-open", on);
      panelFile.hidden = !on;
    }
    if (focus && which === "url" && urlInput) urlInput.focus();
  }

  setTab("url");

  document.querySelectorAll(".tools-tab").forEach((tab) => {
    tab.addEventListener("click", () =>
      setTab(tab.getAttribute("data-tab"), { focus: true }),
    );
  });

  function setStatus(text, isError) {
    if (!statusEl) return;
    statusEl.hidden = !text;
    statusEl.textContent = text || "";
    statusEl.classList.toggle("tools-status--err", !!isError);
  }

  function isXmlFile(file) {
    if (!file) return false;
    const name = String(file.name || "").toLowerCase();
    const type = String(file.type || "").toLowerCase();
    return name.endsWith(".xml") || type.includes("xml");
  }

  function syncDropLabel() {
    const file = fileInput && fileInput.files && fileInput.files[0];
    if (!dropzone || !dropTitle || !dropHint) return;
    if (file) {
      dropzone.classList.add("has-file");
      dropTitle.textContent = file.name;
      dropHint.textContent = "Click or drop another file to replace";
    } else {
      dropzone.classList.remove("has-file");
      dropTitle.textContent = "Drop your feed XML here";
      dropHint.textContent = "or click to choose a file · .xml only";
    }
  }

  function assignFile(file) {
    if (!fileInput) return;
    if (!isXmlFile(file)) {
      setStatus("Please choose an XML feed file.", true);
      return;
    }
    try {
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;
    } catch (_) {
      // Safari / older: rely on native input change only
    }
    syncDropLabel();
    setStatus("");
  }

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      if (file && !isXmlFile(file)) {
        fileInput.value = "";
        setStatus("Please choose an XML feed file.", true);
        syncDropLabel();
        return;
      }
      syncDropLabel();
      setStatus("");
    });
  }

  if (dropzone) {
    dropzone.addEventListener("click", () => {
      fileInput && fileInput.click();
    });
    ["dragenter", "dragover"].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove("is-dragover");
      });
    });
    dropzone.addEventListener("drop", (e) => {
      const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) assignFile(file);
    });
    dropzone.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        fileInput && fileInput.click();
      }
    });
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
    const summary = data.summary || {};
    const buckets = data.buckets || [];
    const itemCount = data.item_count || 0;

    meta.textContent = data.truncated
      ? `Checked ${itemCount} products (truncated to limit).`
      : `Checked ${itemCount} products.`;

    if (summaryEl) {
      summaryEl.hidden = false;
      const types = summary.issue_types || buckets.length || 0;
      const affected = summary.affected_products;
      const ok = summary.ok_products;
      const breakdown = (summary.issue_breakdown || [])
        .map(
          (row) =>
            `<li><span class="tools-summary-n">${escapeHtml(String(row.count))}</span> ${escapeHtml(row.label || row.code)}</li>`,
        )
        .join("");
      summaryEl.innerHTML = `
        <p class="tools-assessment">${escapeHtml(summary.assessment || "")}</p>
        <div class="tools-summary-grid">
          <div>
            <p class="tools-summary-kicker">${types} issue type${types === 1 ? "" : "s"} found</p>
            ${breakdown ? `<ul class="tools-summary-list">${breakdown}</ul>` : "<p class=\"tools-ok\">No issue types in this sample.</p>"}
          </div>
          <div class="tools-summary-side">
            <p><strong>${escapeHtml(String(affected != null ? affected : "—"))}</strong> products need attention</p>
            <p><strong>${escapeHtml(String(ok != null ? ok : "—"))}</strong> products look OK in this check</p>
          </div>
        </div>
      `;
    }

    if (issuesHeading) issuesHeading.hidden = !buckets.length;
    bucketsEl.innerHTML = "";
    buckets.forEach((b, idx) => {
      const block = document.createElement("article");
      block.className = "tools-bucket";
      const n = b.count || 0;
      const samples = (b.samples || [])
        .map((s) => `<li><code>${escapeHtml(s.id || "")}</code> — ${escapeHtml(s.title || "")}</li>`)
        .join("");
      const num = String(idx + 1).padStart(2, "0");
      block.innerHTML = `
        <h3><span class="tools-bucket-idx">${num}</span> ${escapeHtml(b.label || b.code)}</h3>
        <p class="tools-bucket-meta">${n} product${n === 1 ? "" : "s"} affected</p>
        <p>${escapeHtml(b.advice || "")}</p>
        ${samples ? `<ul class="tools-samples">${samples}</ul>` : ""}
      `;
      bucketsEl.appendChild(block);
    });
    if (!buckets.length) {
      bucketsEl.innerHTML =
        '<p class="tools-ok">No issues flagged in the sample we checked.</p>';
    }

    const passed = summary.checks_passed || [];
    if (passedWrap && passedList) {
      if (passed.length) {
        passedWrap.hidden = false;
        passedList.innerHTML = "";
        passed.forEach((c) => {
          const li = document.createElement("li");
          li.textContent = c.label || c.code;
          passedList.appendChild(li);
        });
      } else {
        passedWrap.hidden = true;
      }
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
    if (!isXmlFile(file)) {
      setStatus("Please choose an XML feed file.", true);
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
  if (urlInput) {
    urlInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        runUrl();
      }
    });
  }
})();

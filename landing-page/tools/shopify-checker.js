(function () {
  const input = document.getElementById("shop-input");
  const btn = document.getElementById("check-shop-btn");
  const statusEl = document.getElementById("check-status");
  const report = document.getElementById("report");
  const summary = document.getElementById("summary-line");
  const disclaimer = document.getElementById("disclaimer");
  const list = document.getElementById("bucket-list");

  function setStatus(text, isError) {
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

  async function run() {
    const shop = (input.value || "").trim();
    if (!shop) {
      setStatus("Enter a *.myshopify.com store URL.", true);
      input.focus();
      return;
    }
    setStatus("Checking public catalog…");
    btn.disabled = true;
    try {
      const res = await fetch("/api/public/shopify-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shop }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Check failed"
        );
      }
      setStatus("");
      report.hidden = false;
      summary.textContent =
        data.products_checked +
        " products checked · " +
        data.issue_total +
        " potential issues found";
      disclaimer.textContent = data.disclaimer || "";
      list.innerHTML = "";
      (data.buckets || []).forEach((b) => {
        const li = document.createElement("li");
        li.className = "tools-issue";
        li.innerHTML =
          "<strong>" +
          escapeHtml(b.label || b.code) +
          "</strong> · " +
          escapeHtml(String(b.count)) +
          "<p class=\"tools-issue-advice\">" +
          escapeHtml(b.advice || "") +
          "</p>";
        list.appendChild(li);
      });
      if (!(data.buckets || []).length) {
        list.innerHTML =
          '<li class="tools-ok">No issues flagged in the public sample.</li>';
      }
      report.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setStatus(err.message || "Check failed", true);
    } finally {
      btn.disabled = false;
    }
  }

  btn.addEventListener("click", run);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") run();
  });
})();

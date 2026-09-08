/**
 * Shared waitlist form handler (focused waitlist page + optional product-page embeds).
 */
(function () {
  const form = document.getElementById("waitlist-form");
  const msg = document.getElementById("waitlist-msg");
  const note = document.getElementById("waitlist-note");
  const input = document.getElementById("waitlist-email");
  const shopInput = document.getElementById("waitlist-shop");
  const btn = document.getElementById("waitlist-btn");
  const success = document.getElementById("waitlist-success");
  const successTitle = document.getElementById("waitlist-success-title");
  const successBody = document.getElementById("waitlist-success-body");
  const demoLink = document.getElementById("waitlist-demo-link");
  if (!form || !msg || !btn || !input) return;

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const submitLabel =
    form.getAttribute("data-submit-label") || "Get Early Beta Access";
  const source = form.getAttribute("data-source") || "landing";
  const demoHref = form.getAttribute("data-success-demo") || "/#demo";
  if (demoLink) demoLink.href = demoHref;

  const fields = form.querySelector(".waitlist-fields") || form.querySelector(".waitlist-row");

  function showError(text) {
    form.classList.remove("waitlist--ok", "waitlist--dup");
    if (success) success.hidden = true;
    if (fields) fields.hidden = false;
    btn.hidden = false;
    msg.className = "waitlist-msg waitlist-msg--err";
    msg.textContent = text;
    msg.hidden = false;
    if (note) note.hidden = false;
    btn.disabled = false;
    btn.textContent = submitLabel;
    input.readOnly = false;
    if (shopInput) shopInput.readOnly = false;
  }

  function showDone({ duplicate, message, email }) {
    form.classList.remove("waitlist--ok", "waitlist--dup");
    form.classList.add(duplicate ? "waitlist--dup" : "waitlist--ok");
    if (note) note.hidden = true;
    msg.hidden = true;

    if (success) {
      if (fields) fields.hidden = true;
      btn.hidden = true;
      if (successTitle) {
        successTitle.textContent = duplicate
          ? "You’re already on the list"
          : "You’re on the waitlist!";
      }
      if (successBody) {
        successBody.textContent = duplicate
          ? "No need to submit again — we’ll email you when beta spots open."
          : "We’ll email you as soon as beta spots open.";
      }
      success.hidden = false;
      return;
    }

    msg.className =
      "waitlist-msg " + (duplicate ? "waitlist-msg--dup" : "waitlist-msg--ok");
    msg.innerHTML =
      '<span class="waitlist-check" aria-hidden="true">' +
      (duplicate ? "!" : "✓") +
      "</span> " +
      message;
    msg.hidden = false;
    btn.textContent = duplicate ? "Already registered" : "You're on the list ✓";
    btn.disabled = true;
    input.value = email;
    input.readOnly = true;
    if (shopInput) shopInput.readOnly = true;
  }

  function isValidEmail(email) {
    if (!email || email.length > 254) return false;
    if (email.includes("..") || email.includes(" ")) return false;
    return EMAIL_RE.test(email);
  }

  function normalizeShopUrl(raw) {
    const v = (raw || "").trim();
    if (!v) return "";
    if (v.length > 255) return null;
    if (/\s/.test(v)) return null;
    try {
      const withProto = /^https?:\/\//i.test(v) ? v : "https://" + v;
      const u = new URL(withProto);
      if (!u.hostname || u.hostname.indexOf(".") === -1) return null;
      return u.href.slice(0, 255);
    } catch (_) {
      return null;
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = input.value.trim().toLowerCase();
    if (!isValidEmail(email)) {
      showError("Enter a valid email address (example: you@company.com).");
      input.focus();
      return;
    }

    let shopifyUrl = "";
    if (shopInput && shopInput.value.trim()) {
      shopifyUrl = normalizeShopUrl(shopInput.value);
      if (shopifyUrl === null) {
        showError("Enter a valid store URL (example: your-store.myshopify.com).");
        shopInput.focus();
        return;
      }
    }

    btn.disabled = true;
    msg.hidden = true;
    msg.className = "waitlist-msg";
    form.classList.remove("waitlist--ok", "waitlist--dup");

    const payload = { email, source };
    if (shopifyUrl) payload.shopify_url = shopifyUrl;

    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail;
        const errText = Array.isArray(detail)
          ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
          : typeof detail === "string"
            ? detail
            : "Something went wrong. Try again.";
        throw new Error(errText);
      }
      const duplicate =
        data.status === "already_registered" || data.created === false;
      showDone({
        duplicate,
        message:
          data.message ||
          (duplicate
            ? "This email is already on the list."
            : "You're on the waitlist!"),
        email,
      });
    } catch (err) {
      showError(err.message || "Something went wrong. Try again.");
    }
  });
})();

/**
 * Shared waitlist form handler for the marketing landing page.
 */
(function () {
  const form = document.getElementById("waitlist-form");
  const msg = document.getElementById("waitlist-msg");
  const note = document.getElementById("waitlist-note");
  const input = document.getElementById("waitlist-email");
  const btn = document.getElementById("waitlist-btn");
  if (!form || !msg || !btn || !input) return;

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  function showError(text) {
    form.classList.remove("waitlist--ok", "waitlist--dup");
    msg.className = "waitlist-msg waitlist-msg--err";
    msg.textContent = text;
    msg.hidden = false;
    if (note) note.hidden = false;
    btn.disabled = false;
    btn.textContent = "Get early access";
    input.readOnly = false;
  }

  function showDone({ duplicate, message, email }) {
    form.classList.remove("waitlist--ok", "waitlist--dup");
    form.classList.add(duplicate ? "waitlist--dup" : "waitlist--ok");
    if (note) note.hidden = true;
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
  }

  function isValidEmail(email) {
    if (!email || email.length > 254) return false;
    if (email.includes("..") || email.includes(" ")) return false;
    return EMAIL_RE.test(email);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = input.value.trim().toLowerCase();
    if (!isValidEmail(email)) {
      showError("Enter a valid email address (example: you@company.com).");
      input.focus();
      return;
    }

    btn.disabled = true;
    msg.hidden = true;
    msg.className = "waitlist-msg";
    form.classList.remove("waitlist--ok", "waitlist--dup");

    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source: "landing-hero" }),
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
            : "You're on the list!"),
        email,
      });
    } catch (err) {
      showError(err.message || "Something went wrong. Try again.");
    }
  });
})();

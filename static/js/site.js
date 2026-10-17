/* Site behaviour: header, donate pop-up, copy buttons, counters. Loaded before Alpine. */

document.addEventListener("alpine:init", () => {
  Alpine.data("siteHeader", () => ({
    open: null,
    mobile: false,
    scrolled: false,
    init() {
      const onScroll = () => (this.scrolled = window.scrollY > 8);
      window.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
    },
    toggle(i) {
      this.open = this.open === i ? null : i;
    },
    close() {
      this.open = null;
      this.mobile = false;
    },
  }));

  // Donation form inside the pop-up and on /donate/.
  Alpine.data("donateForm", (cfg) => ({
    currency: cfg.currency,
    frequency: cfg.frequency || "one_time",
    method: cfg.method || "card",
    amount: cfg.amount || "",
    custom: "",
    presets: cfg.presets,
    minimums: cfg.minimums,
    symbols: { NGN: "₦", USD: "$" },
    bankCurrencies: cfg.bankCurrencies || [],
    cardCurrencies: cfg.cardCurrencies || [],
    tribute: false,
    get finalAmount() {
      return this.custom !== "" ? this.custom : this.amount;
    },
    get minimum() {
      return this.minimums[this.currency];
    },
    get belowMinimum() {
      const v = parseFloat(this.finalAmount);
      return !isNaN(v) && v < parseFloat(this.minimum);
    },
    pick(v) {
      this.amount = v;
      this.custom = "";
    },
    setCurrency(c) {
      this.currency = c;
      this.amount = this.presets[c][1] || this.presets[c][0] || "";
      this.custom = "";
      if (this.method === "card" && !this.cardCurrencies.includes(c)) this.method = "bank";
      if (this.method === "bank" && !this.bankCurrencies.includes(c)) this.method = "card";
    },
    fmt(v) {
      return this.symbols[this.currency] + Number(v).toLocaleString();
    },
  }));
});

// Open the donate pop-up for any [data-donate] link; fall back to the full page without JS.
function openDonateModal(url) {
  const root = document.getElementById("modal-root");
  if (!root || !window.htmx) {
    window.location.href = url;
    return;
  }
  const modalUrl = url.replace("/donate/", "/donate/modal/");
  htmx.ajax("GET", modalUrl, { target: "#modal-root", swap: "innerHTML" });
}

document.addEventListener("click", (e) => {
  const link = e.target.closest("[data-donate]");
  if (!link || e.metaKey || e.ctrlKey || e.shiftKey) return;
  e.preventDefault();
  openDonateModal(link.getAttribute("href"));
});

document.addEventListener("DOMContentLoaded", () => {
  // ?form=donate&appeal=CODE opens the pop-up on page load (links shared in emails and ads).
  const params = new URLSearchParams(window.location.search);
  if (params.get("form") === "donate") {
    params.delete("form");
    openDonateModal("/donate/?" + params.toString());
  }

  // Animated big-number counters.
  const counters = document.querySelectorAll("[data-count]");
  if ("IntersectionObserver" in window && counters.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        io.unobserve(entry.target);
        animateCount(entry.target);
      });
    });
    counters.forEach((el) => io.observe(el));
  }
});

function animateCount(el) {
  const text = el.dataset.count;
  const match = text.match(/^([^\d]*)([\d,.]+)(.*)$/);
  if (!match || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const [, prefix, numStr, suffix] = match;
  const target = parseFloat(numStr.replace(/,/g, ""));
  const decimals = (numStr.split(".")[1] || "").length;
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / 1200);
    const val = target * (1 - Math.pow(1 - t, 3));
    el.textContent = prefix + val.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix;
    if (t < 1) requestAnimationFrame(step);
    else el.textContent = text;
  };
  requestAnimationFrame(step);
}

// Copy-to-clipboard buttons: <button data-copy="0123456789">.
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-copy]");
  if (!btn) return;
  e.preventDefault();
  try {
    await navigator.clipboard.writeText(btn.dataset.copy);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = btn.dataset.copy;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  const label = btn.querySelector("[data-copy-label]");
  if (label) {
    const old = label.textContent;
    label.textContent = "Copied!";
    setTimeout(() => (label.textContent = old), 1800);
  }
});

// Share buttons use the native share sheet where available.
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-native-share]");
  if (!btn || !navigator.share) return;
  e.preventDefault();
  try {
    await navigator.share({ title: document.title, url: btn.dataset.url || window.location.href });
  } catch {}
});

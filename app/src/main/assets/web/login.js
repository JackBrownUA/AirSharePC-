(function () {
  "use strict";

  const I18N = window.__I18N__ || {};
  function t(key, vars) {
    let s = I18N[key] || key;
    if (vars) {
      for (const k of Object.keys(vars)) {
        s = s.replace(new RegExp("\\{" + k + "\\}", "g"), String(vars[k]));
      }
    }
    return s;
  }

  let pollTimer = null;
  let activeCid = null;

  function initSky() {
    const far = document.getElementById("layer-far");
    const near = document.getElementById("layer-near");
    if (!far || !near) return;
    for (let i = 0; i < 60; i++) {
      const s = document.createElement("div");
      s.className = "star";
      const sz = (1 + Math.random() * 2.2).toFixed(1) + "px";
      s.style.width = sz;
      s.style.height = sz;
      s.style.left = (Math.random() * 100).toFixed(2) + "%";
      s.style.top = (Math.random() * 100).toFixed(2) + "%";
      s.style.animationDelay = (Math.random() * 4).toFixed(2) + "s";
      (i % 2 === 0 ? far : near).appendChild(s);
    }
    for (let i = 0; i < 6; i++) {
      const c = document.createElement("div");
      c.className = "cloud";
      c.style.width = (140 + Math.random() * 180) + "px";
      c.style.height = (48 + Math.random() * 42) + "px";
      c.style.top = (8 + i * 14) + "%";
      c.style.left = (-20 + i * 16) + "%";
      c.style.animationDuration = (36 + i * 8) + "s";
      (i % 2 === 0 ? far : near).appendChild(c);
    }
    window.addEventListener("mousemove", (e) => {
      const dx = (e.clientX / window.innerWidth - 0.5) * 2;
      const dy = (e.clientY / window.innerHeight - 0.5) * 2;
      far.style.transform = `translate3d(${(-dx * 10).toFixed(1)}px, ${(-dy * 10).toFixed(1)}px, 0)`;
      near.style.transform = `translate3d(${(-dx * 22).toFixed(1)}px, ${(-dy * 22).toFixed(1)}px, 0)`;
    });
  }

  function setStatus(msg, isError) {
    const box = document.getElementById("status-area");
    box.style.display = msg ? "block" : "none";
    box.className = "status-box" + (isError ? " error" : "");
    box.textContent = msg || "";
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function startAuth(mode) {
    stopPolling();
    const codeEl = document.getElementById("code-display");
    codeEl.style.display = "none";
    setStatus(mode === "biometric" ? t("web_bio_waiting") : "...", false);

    try {
      const r = await fetch("/auth/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, action: "login" })
      });
      const data = await r.json();
      if (!r.ok) {
        setStatus(data.error || "Error", true);
        return;
      }
      activeCid = data.cid;
      if (mode === "pairs" && data.target) {
        codeEl.textContent = data.target;
        codeEl.style.display = "block";
        setStatus(t("web_pairs_waiting", { code: data.target }), false);
      } else {
        setStatus(t("web_bio_waiting"), false);
      }

      pollTimer = setInterval(async () => {
        if (!activeCid) return;
        try {
          const sr = await fetch("/auth/status?cid=" + encodeURIComponent(activeCid));
          const sd = await sr.json();
          if (sd.status === "approved") {
            stopPolling();
            const cr = await fetch("/auth/claim", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ cid: activeCid })
            });
            if (cr.ok) {
              window.location.href = "/";
            } else {
              setStatus("Session claim failed", true);
            }
          } else if (sd.status === "denied") {
            stopPolling();
            codeEl.style.display = "none";
            setStatus(t("web_dev_blocked"), true);
          } else if (sd.status === "cancelled" || sd.status === "expired" || sd.status === "missing") {
            stopPolling();
            codeEl.style.display = "none";
            setStatus(t("web_cancelled_retry"), false);
          }
        } catch (_) {}
      }, 950);
    } catch (_) {
      setStatus("Network error", true);
    }
  }

  async function submitPin(ev) {
    ev.preventDefault();
    stopPolling();
    const pin = document.getElementById("pin-input").value.trim();
    if (!pin) return;
    try {
      const r = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin, action: "login" })
      });
      const d = await r.json();
      if (r.ok && d.ok) {
        window.location.href = "/";
      } else {
        setStatus(d.error || t("toast_bad_pin"), true);
      }
    } catch (_) {
      setStatus("Network error", true);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const savedTheme = localStorage.getItem("airshare_theme") || window.__INIT_THEME__ || "dark";
    document.documentElement.setAttribute("data-theme", savedTheme);

    document.getElementById("login-sub").textContent = t("auth_req_sub");
    document.getElementById("btn-connect-bio").textContent = "👆 " + t("web_login_use_bio");
    document.getElementById("btn-connect-pairs").textContent = "🔢 " + t("web_login_use_pairs");
    document.getElementById("pin-summary").textContent = "🔑 " + t("web_login_use_pin");
    document.getElementById("btn-pin-submit").textContent = t("web_login_connect");

    const langSel = document.getElementById("lang-select");
    langSel.value = window.__INIT_LANG__ || "en";
    langSel.addEventListener("change", () => {
      document.cookie = "airshare_lang=" + langSel.value + "; path=/; max-age=31536000";
      window.location.href = "/?lang=" + encodeURIComponent(langSel.value);
    });

    document.getElementById("btn-theme").addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", cur);
      localStorage.setItem("airshare_theme", cur);
    });

    document.getElementById("btn-connect-bio").addEventListener("click", () => startAuth("biometric"));
    document.getElementById("btn-connect-pairs").addEventListener("click", () => startAuth("pairs"));
    document.getElementById("pin-form").addEventListener("submit", submitPin);

    initSky();
  });
})();

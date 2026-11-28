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
    const canvas = document.getElementById("skyCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let w = 0, h = 0;
    function resize() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    const stars = Array.from({ length: 220 }, () => ({
      x: Math.random(),
      y: Math.random(),
      r: Math.random() * 1.6 + 0.4,
      alpha: Math.random() * 0.6 + 0.3,
      speed: Math.random() * 0.02 + 0.008,
      phase: Math.random() * Math.PI * 2
    }));

    const meteors = [];
    let meteorTimer = 0;

    const clouds = Array.from({ length: 10 }, (_, i) => ({
      x: (i / 10) * (window.innerWidth || 1200) + Math.random() * 120,
      y: Math.random() * 0.65 + 0.06,
      scale: Math.random() * 0.7 + 0.6,
      speed: Math.random() * 0.25 + 0.12,
      alpha: Math.random() * 0.28 + 0.42
    }));

    function drawCloud(x, y, s, a) {
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(s, s);
      ctx.fillStyle = "rgba(255, 255, 255, " + a + ")";
      ctx.beginPath();
      ctx.arc(0, 0, 28, 0, Math.PI * 2);
      ctx.arc(26, -10, 34, 0, Math.PI * 2);
      ctx.arc(60, -4, 30, 0, Math.PI * 2);
      ctx.arc(84, 6, 22, 0, Math.PI * 2);
      ctx.arc(-24, 8, 22, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    function frame() {
      ctx.clearRect(0, 0, w, h);
      const isDark = document.documentElement.getAttribute("data-theme") === "dark" ||
        document.body.classList.contains("dark");

      if (isDark) {
        for (const s of stars) {
          s.phase += s.speed;
          const a = Math.max(0.1, Math.min(1, s.alpha + Math.sin(s.phase) * 0.35));
          ctx.fillStyle = "rgba(255, 255, 255, " + a.toFixed(3) + ")";
          ctx.beginPath();
          ctx.arc(s.x * w, s.y * h, s.r, 0, Math.PI * 2);
          ctx.fill();
        }

        meteorTimer++;
        if (meteorTimer > 140 && Math.random() < 0.03) {
          meteorTimer = 0;
          meteors.push({
            x: Math.random() * w * 0.8,
            y: Math.random() * h * 0.35,
            vx: 8 + Math.random() * 5,
            vy: 4 + Math.random() * 3,
            len: 70 + Math.random() * 50,
            life: 1
          });
        }

        for (let i = meteors.length - 1; i >= 0; i--) {
          const m = meteors[i];
          const grad = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * (m.len / 10), m.y - m.vy * (m.len / 10));
          grad.addColorStop(0, "rgba(255, 255, 255, " + m.life.toFixed(3) + ")");
          grad.addColorStop(1, "rgba(255, 255, 255, 0)");
          ctx.strokeStyle = grad;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(m.x, m.y);
          ctx.lineTo(m.x - m.vx * (m.len / 10), m.y - m.vy * (m.len / 10));
          ctx.stroke();
          m.x += m.vx;
          m.y += m.vy;
          m.life -= 0.025;
          if (m.life <= 0) meteors.splice(i, 1);
        }
      } else {
        for (const c of clouds) {
          c.x += c.speed;
          if (c.x - 120 > w) c.x = -140;
          drawCloud(c.x, c.y * h, c.scale, c.alpha);
        }
      }

      requestAnimationFrame(frame);
    }

    requestAnimationFrame(frame);
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
        setStatus(d.error || t("pin_hint"), true);
      }
    } catch (_) {
      setStatus("Network error", true);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const savedTheme = localStorage.getItem("airshare_theme") || window.__INIT_THEME__ || "dark";
    document.body.classList.remove("dark","light");document.body.classList.add(window.__INIT_THEME__||"dark");
    document.documentElement.setAttribute("data-theme", savedTheme);

    document.getElementById("login-sub").textContent = t("web_auth_prompt_sub");
    document.getElementById("btn-connect-bio").textContent = "👆 " + t("web_login_use_bio");
    document.getElementById("btn-connect-pairs").textContent = "🔢 " + t("web_login_use_pairs");
    document.getElementById("pin-summary").textContent = "🔑 " + t("web_login_use_pin");
    document.getElementById("btn-pin-submit").textContent = t("web_login_connect");
    const themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
      themeToggle.checked = savedTheme === "dark";
      document.body.classList.remove("dark", "light");
      document.body.classList.add(savedTheme);
      themeToggle.addEventListener("change", () => {
        const cur = themeToggle.checked ? "dark" : "light";
        document.documentElement.setAttribute("data-theme", cur);
        document.body.classList.remove("dark", "light");
        document.body.classList.add(cur);
        localStorage.setItem("airshare_theme", cur);
        document.cookie = "airshare_theme=" + cur + "; path=/; max-age=31536000";
      });
    }

    const LANGS = [
      { code: "en", label: "English", svg: '<svg width="18" height="12" viewBox="0 0 18 12"><rect width="18" height="12" fill="#012169"/><path d="M0,0 L18,12 M18,0 L0,12" stroke="#fff" stroke-width="2.2"/><path d="M0,0 L18,12 M18,0 L0,12" stroke="#C8102E" stroke-width="1.2"/><path d="M9,0 V12 M0,6 H18" stroke="#fff" stroke-width="3.6"/><path d="M9,0 V12 M0,6 H18" stroke="#C8102E" stroke-width="2"/></svg>' },
      { code: "ru", label: "Русский", svg: '<svg width="18" height="12" viewBox="0 0 18 12"><rect width="18" height="4" y="0" fill="#fff"/><rect width="18" height="4" y="4" fill="#0039A6"/><rect width="18" height="4" y="8" fill="#D52B1E"/></svg>' },
      { code: "uk", label: "Українська", svg: '<svg width="18" height="12" viewBox="0 0 18 12"><rect width="18" height="6" y="0" fill="#005BBB"/><rect width="18" height="6" y="6" fill="#FFD500"/></svg>' },
      { code: "es", label: "Español", svg: '<svg width="18" height="12" viewBox="0 0 18 12"><rect width="18" height="3" y="0" fill="#AA151B"/><rect width="18" height="6" y="3" fill="#F1BF00"/><rect width="18" height="3" y="9" fill="#AA151B"/></svg>' },
      { code: "de", label: "Deutsch", svg: '<svg width="18" height="12" viewBox="0 0 18 12"><rect width="18" height="4" y="0" fill="#000"/><rect width="18" height="4" y="4" fill="#DD0000"/><rect width="18" height="4" y="8" fill="#FFCE00"/></svg>' },
      { code: "lt", label: "Lietuvių", svg: '<svg width="18" height="12" viewBox="0 0 18 12"><rect width="18" height="4" y="0" fill="#FDB913"/><rect width="18" height="4" y="4" fill="#006A44"/><rect width="18" height="4" y="8" fill="#C1272D"/></svg>' }
    ];
    const curLang = window.__INIT_LANG__ || "en";
    const langBtn = document.getElementById("lang-btn");
    const langDropdown = document.getElementById("lang-dropdown");
    if (langBtn && langDropdown) {
      const active = LANGS.find(l => l.code === curLang) || LANGS[0];
      langBtn.innerHTML = active.svg + '<span>' + active.code.toUpperCase() + '</span>';
      langDropdown.innerHTML = LANGS.map(l =>
        '<button type="button" class="lang-option' + (l.code === active.code ? ' active' : '') + '" data-lang="' + l.code + '" style="display:flex;align-items:center;gap:8px;width:100%;padding:6px 10px;background:none;border:none;color:inherit;cursor:pointer;text-align:left;font-size:13px;">' +
        l.svg + '<span>' + l.label + '</span></button>'
      ).join("");
      langBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        langDropdown.style.display = langDropdown.style.display === "none" ? "block" : "none";
      });
      langDropdown.querySelectorAll("[data-lang]").forEach(btn => {
        btn.addEventListener("click", () => {
          const code = btn.getAttribute("data-lang");
          document.cookie = "airshare_lang=" + code + "; path=/; max-age=31536000";
          window.location.href = "/?lang=" + encodeURIComponent(code);
        });
      });
      document.addEventListener("click", () => {
        langDropdown.style.display = "none";
      });
    }
 

    document.getElementById("btn-connect-bio").addEventListener("click", () => startAuth("biometric"));
    document.getElementById("btn-connect-pairs").addEventListener("click", () => startAuth("pairs"));
    document.getElementById("pin-form").addEventListener("submit", submitPin);

    initSky();
  });
})();

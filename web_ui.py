# Веб-интерфейс AirShare PC: реалистичное звёздное небо с метеорами и 3D-параллаксом, тумблеры, предпросмотр фото/видео и экран ввода PIN

import html
import json
from i18n import tr


def get_css(theme="dark"):
    scheme = "light" if theme == "light" else "dark"
    return f"""
    :root {{ color-scheme: {scheme}; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        min-height: 100vh;
        overflow-x: hidden;
        transition: background 0.55s cubic-bezier(0.22, 1, 0.36, 1), color 0.45s ease;
        background: radial-gradient(ellipse at 50% 0%, #13192b 0%, #090c15 55%, #040508 100%);
        color: #eef2ff;
    }}
    body.light {{
        background: linear-gradient(135deg, #dfe9f3 0%, #eef2f7 50%, #d4e4f7 100%);
        color: #1a202c;
    }}
    #skyCanvas {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 0;
        pointer-events: none;
        transition: opacity 0.55s ease;
        opacity: 1;
    }}
    body.light #skyCanvas {{
        opacity: 0;
    }}
    @media (prefers-reduced-motion: reduce) {{
        body, .ctrl-pill, .switch-slider, .upload-btn, .download-btn, .thumb-box {{
            transition: none !important;
        }}
    }}
    /* Верхняя левая панель (Тема День/Ночь + 3D-Параллакс) и правая панель (Предпросмотр) */
    .top-controls {{
        position: fixed;
        top: 18px;
        left: 20px;
        z-index: 20;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }}
    .top-right-controls {{
        position: fixed;
        top: 18px;
        right: 20px;
        z-index: 20;
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    .ctrl-pill {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 8px 14px;
        border-radius: 30px;
        background: rgba(20, 26, 42, 0.72);
        border: 1px solid rgba(255, 255, 255, 0.16);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45), inset 0 1px 1px rgba(255, 255, 255, 0.18);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        font-size: 13.5px;
        font-weight: 500;
        color: #f1f5f9;
        user-select: none;
        transition: background 0.4s ease, border-color 0.4s ease, color 0.4s ease, box-shadow 0.4s ease;
    }}
    body.light .ctrl-pill {{
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid rgba(15, 23, 42, 0.12);
        color: #1e293b;
        box-shadow: 0 6px 20px rgba(30, 41, 59, 0.10), inset 0 1px 1px rgba(255, 255, 255, 0.9);
    }}
    .switch {{
        position: relative;
        display: inline-block;
        width: 46px;
        height: 25px;
    }}
    .switch input {{
        opacity: 0;
        width: 0;
        height: 0;
    }}
    .switch-slider {{
        position: absolute;
        cursor: pointer;
        top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(145deg, #283044, #1e2433);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 26px;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
        transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
    }}
    body.light .switch-slider {{
        background: linear-gradient(145deg, #cbd5e1, #94a3b8);
        border-color: rgba(0, 0, 0, 0.1);
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.15);
    }}
    .switch-slider:before {{
        position: absolute;
        content: "";
        height: 19px;
        width: 19px;
        left: 2px;
        bottom: 2px;
        background: radial-gradient(circle at 35% 30%, #ffffff, #dbeafe);
        border-radius: 50%;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.45);
        transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.35s ease;
    }}
    .switch input:checked + .switch-slider {{
        background: linear-gradient(135deg, #20c997, #12b886);
        border-color: rgba(56, 217, 169, 0.65);
        box-shadow: 0 0 12px rgba(32, 201, 151, 0.45), inset 0 1px 2px rgba(255, 255, 255, 0.35);
    }}
    .switch input:checked + .switch-slider:before {{
        transform: translateX(21px);
    }}
    .container {{
        position: relative;
        z-index: 1;
        max-width: 850px;
        margin: 0 auto;
        padding: 82px 20px 64px;
    }}
    .header {{
        text-align: center;
        margin-bottom: 34px;
    }}
    .header h1 {{
        color: #ffffff;
        font-size: 44px;
        font-weight: 600;
        letter-spacing: -0.5px;
        margin-bottom: 8px;
        text-shadow: 0 4px 28px rgba(99, 102, 241, 0.55);
        transition: color 0.4s ease, text-shadow 0.4s ease;
    }}
    body.light .header h1 {{
        color: #0f172a;
        text-shadow: 0 2px 12px rgba(15, 23, 42, 0.08);
    }}
    .header p {{
        color: rgba(226, 232, 240, 0.65);
        font-size: 14px;
        margin-bottom: 20px;
        word-break: break-all;
    }}
    body.light .header p {{
        color: #475569;
    }}
    .actions-bar {{
        display: flex;
        gap: 12px;
        justify-content: center;
        flex-wrap: wrap;
        margin-top: 8px;
    }}
    .upload-btn {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 12px 26px;
        background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 28px;
        color: #fff;
        cursor: pointer;
        font-size: 15px;
        font-weight: 500;
        text-decoration: none;
        box-shadow: 0 8px 22px rgba(59, 130, 246, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.35);
        transition: transform 0.2s ease, box-shadow 0.25s ease, filter 0.2s ease;
    }}
    .upload-btn:hover {{
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(59, 130, 246, 0.58), inset 0 1px 2px rgba(255, 255, 255, 0.5);
        filter: brightness(1.06);
    }}
    .upload-btn:active {{
        transform: translateY(1px);
    }}
    body.light .upload-btn {{
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.32), inset 0 1px 1px rgba(255, 255, 255, 0.4);
    }}
    .toolbar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 13px 18px;
        margin-bottom: 10px;
        border-radius: 14px;
        background: rgba(24, 30, 48, 0.68);
        border: 1px solid rgba(255, 255, 255, 0.10);
        backdrop-filter: blur(12px);
        font-size: 14px;
        flex-wrap: wrap;
        gap: 8px;
    }}
    body.light .toolbar {{
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid rgba(15, 23, 42, 0.08);
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
    }}
    .toolbar label {{
        display: flex;
        align-items: center;
        cursor: pointer;
        user-select: none;
    }}
    .pagination {{
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 14px;
        margin: 18px 0;
        font-size: 14px;
    }}
    .file-list {{
        list-style: none;
        border-radius: 16px;
        overflow: hidden;
        background: rgba(18, 23, 38, 0.68);
        border: 1px solid rgba(255, 255, 255, 0.11);
        backdrop-filter: blur(14px);
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.42);
    }}
    body.light .file-list {{
        background: rgba(255, 255, 255, 0.90);
        border: 1px solid rgba(15, 23, 42, 0.08);
        box-shadow: 0 8px 28px rgba(15, 23, 42, 0.07);
    }}
    .file-item {{
        padding: 15px 18px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.07);
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 14px;
        transition: background 0.2s ease;
    }}
    .file-item:hover {{
        background: rgba(255, 255, 255, 0.03);
    }}
    body.light .file-item {{
        border-bottom: 1px solid rgba(15, 23, 42, 0.07);
    }}
    body.light .file-item:hover {{
        background: rgba(37, 99, 235, 0.03);
    }}
    .file-item:last-child {{
        border-bottom: none;
    }}
    /* Миниатюра предпросмотра файла (скрыта, пока тумблер «Предпросмотр» выключен) */
    .thumb-box {{
        display: none;
        width: 46px;
        height: 46px;
        border-radius: 11px;
        overflow: hidden;
        flex-shrink: 0;
        position: relative;
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.18);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.38);
        align-items: center;
        justify-content: center;
    }}
    body.light .thumb-box {{
        background: #e2e8f0;
        border: 1px solid rgba(15, 23, 42, 0.12);
        box-shadow: 0 3px 10px rgba(15, 23, 42, 0.12);
    }}
    body.show-previews .thumb-box {{
        display: inline-flex;
    }}
    body.show-previews .has-thumb .doc-icon {{
        display: none;
    }}
    .file-thumb {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }}
    .vid-badge {{
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.32);
        color: #ffffff;
        font-size: 14px;
        text-shadow: 0 1px 4px rgba(0, 0, 0, 0.7);
        pointer-events: none;
    }}
    .file-info {{
        flex: 1;
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    .file-text-col {{
        flex: 1;
        min-width: 0;
    }}
    .file-link {{
        color: #f8fafc;
        text-decoration: none;
        font-size: 16.5px;
        font-weight: 500;
        display: block;
        margin-bottom: 4px;
        word-break: break-word;
        transition: color 0.2s ease;
    }}
    .file-link:hover {{
        color: #60a5fa;
    }}
    body.light .file-link {{
        color: #0f172a;
    }}
    body.light .file-link:hover {{
        color: #2563eb;
    }}
    .file-meta {{
        color: rgba(203, 213, 225, 0.55);
        font-size: 13px;
    }}
    body.light .file-meta {{
        color: #64748b;
    }}
    /* Объёмная 3D-кнопка скачивания файла */
    .download-btn {{
        width: 44px;
        height: 44px;
        flex-shrink: 0;
        border-radius: 14px;
        background: linear-gradient(145deg, #3b82f6 0%, #1d4ed8 100%);
        border: 1px solid rgba(147, 197, 253, 0.45);
        box-shadow: 0 5px 14px rgba(29, 78, 216, 0.48), inset 0 1.5px 1px rgba(255, 255, 255, 0.42), inset 0 -2px 3px rgba(0, 0, 0, 0.25);
        display: flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
        color: #ffffff;
        transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s ease, filter 0.2s ease;
    }}
    .download-btn:hover {{
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 8px 20px rgba(37, 99, 235, 0.65), inset 0 1.5px 2px rgba(255, 255, 255, 0.6);
        filter: brightness(1.08);
    }}
    .download-btn:active {{
        transform: translateY(1px) scale(0.97);
    }}
    .download-btn svg {{
        width: 21px;
        height: 21px;
        stroke: #ffffff;
        stroke-width: 2.3;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.35));
    }}
    .checkbox {{
        width: 20px;
        height: 20px;
        cursor: pointer;
        margin-right: 8px;
        flex-shrink: 0;
        accent-color: #3b82f6;
    }}
    /* Подпись автора в правом нижнем углу сайта */
    .credit-badge {{
        position: fixed;
        bottom: 14px;
        right: 18px;
        z-index: 15;
        padding: 6px 13px;
        border-radius: 20px;
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(8px);
        font-size: 12px;
        color: rgba(226, 232, 240, 0.72);
        letter-spacing: 0.2px;
        pointer-events: none;
    }}
    body.light .credit-badge {{
        background: rgba(255, 255, 255, 0.78);
        border: 1px solid rgba(15, 23, 42, 0.10);
        color: #475569;
    }}
    /* Карточка ввода PIN-кода при ручном открытии IP:порт */
    .pin-card {{
        max-width: 380px;
        margin: 90px auto 0;
        padding: 34px 28px;
        border-radius: 24px;
        background: rgba(20, 26, 44, 0.78);
        border: 1px solid rgba(255, 255, 255, 0.16);
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(18px);
        text-align: center;
    }}
    body.light .pin-card {{
        background: rgba(255, 255, 255, 0.88);
        border: 1px solid rgba(15, 23, 42, 0.1);
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.12);
    }}
    .pin-input {{
        width: 100%;
        padding: 14px 16px;
        margin: 18px 0 14px;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.22);
        background: rgba(10, 14, 26, 0.7);
        color: #fff;
        font-size: 22px;
        letter-spacing: 6px;
        text-align: center;
        outline: none;
    }}
    body.light .pin-input {{
        background: #f1f5f9;
        border-color: #cbd5e1;
        color: #0f172a;
    }}
    """


def get_download_svg():
    # Объёмная SVG-иконка скачивания вместо плоской стрелки
    return (
        '<svg viewBox="0 0 24 24">'
        '<path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 19h14"/>'
        '</svg>'
    )


def get_star_script():
    # Реалистичное плотное звёздное небо (260 звёзд в 3 слоях глубины) + падающие звёзды (метеоры) + 3D-параллакс
    return """
    (function(){
        const canvas = document.getElementById("skyCanvas");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        let w = window.innerWidth, h = window.innerHeight;
        canvas.width = w;
        canvas.height = h;

        let parallaxEnabled = true;
        try {
            const savedP = localStorage.getItem("airshare_parallax");
            if (savedP !== null) parallaxEnabled = (savedP === "1");
        } catch (e) {}

        const pToggle = document.getElementById("parallaxToggle");
        if (pToggle) {
            pToggle.checked = parallaxEnabled;
            pToggle.addEventListener("change", function() {
                parallaxEnabled = this.checked;
                try { localStorage.setItem("airshare_parallax", parallaxEnabled ? "1" : "0"); } catch (e) {}
            });
        }

        let targetX = 0, targetY = 0, curX = 0, curY = 0;
        window.addEventListener("mousemove", function(e) {
            if (!parallaxEnabled) return;
            targetX = (e.clientX / w - 0.5) * 48;
            targetY = (e.clientY / h - 0.5) * 48;
        });
        window.addEventListener("deviceorientation", function(e) {
            if (!parallaxEnabled || e.gamma === null || e.beta === null) return;
            targetX = Math.max(-35, Math.min(35, e.gamma)) * 1.1;
            targetY = Math.max(-35, Math.min(35, e.beta - 45)) * 1.1;
        });
        window.addEventListener("resize", function() {
            w = window.innerWidth;
            h = window.innerHeight;
            canvas.width = w;
            canvas.height = h;
        });

        const colors = ["#ffffff", "#e2e8f0", "#bae6fd", "#fef08a", "#c7d2fe"];
        const stars = [];
        for (let i = 0; i < 260; i++) {
            const depth = Math.random() * 0.85 + 0.15;
            stars.push({
                x: Math.random() * w,
                y: Math.random() * h,
                r: (Math.random() * 1.55 + 0.45) * depth,
                depth: depth,
                color: colors[Math.floor(Math.random() * colors.length)],
                phase: Math.random() * Math.PI * 2,
                speed: Math.random() * 0.025 + 0.008,
                drift: (Math.random() * 0.12 + 0.03) * depth
            });
        }

        const meteors = [];
        function spawnMeteor() {
            meteors.push({
                x: Math.random() * w * 0.9 + w * 0.1,
                y: Math.random() * h * 0.35,
                vx: -(Math.random() * 7 + 8),
                vy: (Math.random() * 4 + 5),
                len: Math.random() * 90 + 70,
                life: 1.0,
                decay: Math.random() * 0.015 + 0.014
            });
        }

        function animate() {
            requestAnimationFrame(animate);
            if (document.body.classList.contains("light")) return;

            ctx.clearRect(0, 0, w, h);
            if (parallaxEnabled) {
                curX += (targetX - curX) * 0.06;
                curY += (targetY - curY) * 0.06;
            } else {
                curX *= 0.92;
                curY *= 0.92;
            }

            for (let i = 0; i < stars.length; i++) {
                const s = stars[i];
                s.phase += s.speed;
                if (parallaxEnabled) {
                    s.x -= s.drift;
                    if (s.x < 0) s.x += w;
                }
                const alpha = 0.38 + 0.62 * (0.5 + 0.5 * Math.sin(s.phase));
                let sx = (s.x + curX * s.depth * 1.4 + w) % w;
                let sy = (s.y + curY * s.depth * 1.4 + h) % h;

                ctx.globalAlpha = alpha;
                ctx.fillStyle = s.color;
                ctx.beginPath();
                ctx.arc(sx, sy, s.r, 0, Math.PI * 2);
                ctx.fill();

                if (s.r > 1.35) {
                    ctx.globalAlpha = alpha * 0.25;
                    ctx.beginPath();
                    ctx.arc(sx, sy, s.r * 2.6, 0, Math.PI * 2);
                    ctx.fill();
                }
            }

            if (Math.random() < 0.022 && meteors.length < 3) {
                spawnMeteor();
            }

            for (let i = meteors.length - 1; i >= 0; i--) {
                const m = meteors[i];
                m.x += m.vx;
                m.y += m.vy;
                m.life -= m.decay;
                if (m.life <= 0 || m.x < -100 || m.y > h + 100) {
                    meteors.splice(i, 1);
                    continue;
                }
                const tailX = m.x - m.vx * (m.len / 10);
                const tailY = m.y - m.vy * (m.len / 10);
                const grad = ctx.createLinearGradient(m.x, m.y, tailX, tailY);
                grad.addColorStop(0, "rgba(255, 255, 255, " + m.life + ")");
                grad.addColorStop(0.3, "rgba(147, 197, 253, " + (m.life * 0.6) + ")");
                grad.addColorStop(1, "rgba(59, 130, 246, 0)");

                ctx.globalAlpha = 1.0;
                ctx.strokeStyle = grad;
                ctx.lineWidth = 2.0;
                ctx.beginPath();
                ctx.moveTo(m.x, m.y);
                ctx.lineTo(tailX, tailY);
                ctx.stroke();

                ctx.fillStyle = "#ffffff";
                ctx.globalAlpha = m.life;
                ctx.beginPath();
                ctx.arc(m.x, m.y, 2.2, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.globalAlpha = 1.0;
        }
        animate();
    })();
    """


def get_upload_script(lang="en"):
    msg_uploading = json.dumps(tr("web_uploading", lang))
    msg_done = json.dumps(tr("web_upload_done", lang))
    msg_err = json.dumps(tr("web_upload_err", lang))
    msg_warn = json.dumps(tr("web_select_warn", lang))
    msg_prep = json.dumps(tr("web_prep_zip", lang))
    return f"""
    function triggerUpload() {{
        const input = document.getElementById("up");
        if (input) {{
            input.value = "";
            input.click();
        }}
    }}

    async function uploadFiles(files) {{
        if (!files || files.length === 0) return;
        const st = document.getElementById("status");
        const cleanOrigin = window.location.protocol + "//" + window.location.host;
        const basePath = window.location.pathname || "/";
        let uploadedCount = 0;

        for (let i = 0; i < files.length; i++) {{
            const file = files[i];
            if (st) {{
                st.style.color = "#60a5fa";
                st.innerText = {msg_uploading} + " " + file.name + " (" + (i + 1) + "/" + files.length + ")...";
            }}
            try {{
                const targetUrl = cleanOrigin + basePath + "?upload=" + encodeURIComponent(file.name);
                const res = await fetch(targetUrl, {{
                    method: "POST",
                    body: file,
                    credentials: "same-origin",
                    headers: {{
                        "X-File-Name": encodeURIComponent(file.name)
                    }}
                }});
                if (!res.ok) {{
                    const errText = await res.text();
                    throw new Error(errText || ("HTTP " + res.status));
                }}
                uploadedCount++;
            }} catch (err) {{
                if (st) {{
                    st.style.color = "#ff453a";
                    st.innerText = {msg_err} + file.name + ": " + err.message;
                }}
                return;
            }}
        }}
        if (st && uploadedCount > 0) {{
            st.style.color = "#20c997";
            st.innerText = {msg_done} + uploadedCount;
        }}
        window.location.href = cleanOrigin + basePath;
    }}

    function toggleSelectAll(masterCheckbox) {{
        const boxes = document.querySelectorAll('input[name="files"]');
        for (let i = 0; i < boxes.length; i++) {{
            boxes[i].checked = masterCheckbox.checked;
        }}
    }}

    function submitSelectedDownload(event) {{
        const checked = document.querySelectorAll('input[name="files"]:checked');
        const st = document.getElementById("status");
        if (!checked || checked.length === 0) {{
            if (event) event.preventDefault();
            if (st) {{
                st.style.color = "#ff9f0a";
                st.innerText = {msg_warn};
            }}
            return false;
        }}
        if (st) {{
            st.style.color = "#60a5fa";
            st.innerText = {msg_prep};
        }}
        return true;
    }}
    """


def get_theme_script():
    return """
    function applyTheme(theme) {
        const isLight = (theme === "light");
        document.body.classList.toggle("light", isLight);
        document.body.classList.toggle("dark", !isLight);
        const tToggle = document.getElementById("themeToggle");
        if (tToggle) {
            tToggle.checked = !isLight;
        }
        const pPill = document.getElementById("parallaxPill");
        if (pPill) {
            pPill.style.opacity = isLight ? "0.45" : "1";
        }
        try {
            localStorage.setItem("airshare_theme", isLight ? "light" : "dark");
        } catch (e) {}
        document.cookie = "airshare_theme=" + (isLight ? "light" : "dark") + "; path=/; max-age=31536000; SameSite=Lax";
    }

    function onThemeSwitchChange(checkbox) {
        const nextTheme = checkbox.checked ? "dark" : "light";
        applyTheme(nextTheme);
    }

    let _thumbObserver = null;
    function _activateVisibleThumbs() {
        const mediaEls = document.querySelectorAll(".file-thumb[data-src]");
        if ("IntersectionObserver" in window) {
            if (!_thumbObserver) {
                _thumbObserver = new IntersectionObserver(function(entries) {
                    entries.forEach(function(entry) {
                        if (entry.isIntersecting && document.body.classList.contains("show-previews")) {
                            const el = entry.target;
                            if (el.dataset.src && !el.getAttribute("src")) {
                                el.setAttribute("src", el.dataset.src);
                            }
                            _thumbObserver.unobserve(el);
                        }
                    });
                }, { rootMargin: "160px 0px" });
            }
            mediaEls.forEach(function(el) {
                if (!el.getAttribute("src")) {
                    _thumbObserver.observe(el);
                }
            });
        } else {
            mediaEls.forEach(function(el) {
                if (el.dataset.src && !el.getAttribute("src")) {
                    el.setAttribute("src", el.dataset.src);
                }
            });
        }
    }

    function applyPreviewMode(enabled) {
        document.body.classList.toggle("show-previews", !!enabled);
        const prevToggle = document.getElementById("previewToggle");
        if (prevToggle) {
            prevToggle.checked = !!enabled;
        }
        try {
            localStorage.setItem("airshare_preview", enabled ? "1" : "0");
        } catch (e) {}
        if (enabled) {
            _activateVisibleThumbs();
        }
    }

    function onPreviewSwitchChange(checkbox) {
        applyPreviewMode(checkbox.checked);
    }

    (function initThemeAndPreview() {
        const url = new URL(window.location.href);
        const urlTheme = url.searchParams.get("theme");
        let saved = null;
        try {
            saved = localStorage.getItem("airshare_theme");
        } catch (e) {}
        if (urlTheme === "light" || urlTheme === "dark") {
            applyTheme(urlTheme);
        } else if (saved === "light" || saved === "dark") {
            applyTheme(saved);
        } else {
            applyTheme(document.body.classList.contains("light") ? "light" : "dark");
        }

        let savedPrev = false;
        try {
            savedPrev = (localStorage.getItem("airshare_preview") === "1");
        } catch (e) {}
        applyPreviewMode(savedPrev);
    })();
    """


def get_top_controls_html(theme="dark", lang="en", show_preview_toggle=False):
    is_dark_checked = "checked" if theme != "light" else ""
    left_html = (
        '<div class="top-controls">'
        '<label class="ctrl-pill" title="Тема День / Ночь">'
        '<span>☀️ / 🌙</span>'
        '<span class="switch">'
        f'<input type="checkbox" id="themeToggle" {is_dark_checked} onchange="onThemeSwitchChange(this)">'
        '<span class="switch-slider"></span>'
        '</span>'
        '</label>'
        '<label class="ctrl-pill" id="parallaxPill" title="Живые 3D-обои звёздного неба">'
        '<span>✨ Parallax 3D</span>'
        '<span class="switch">'
        '<input type="checkbox" id="parallaxToggle" checked>'
        '<span class="switch-slider"></span>'
        '</span>'
        '</label>'
        '</div>'
    )
    if not show_preview_toggle:
        return left_html
    preview_label = html.escape(tr("web_preview", lang))
    right_html = (
        '<div class="top-right-controls">'
        f'<label class="ctrl-pill" title="{preview_label}">'
        f'<span>{preview_label}</span>'
        '<span class="switch">'
        '<input type="checkbox" id="previewToggle" onchange="onPreviewSwitchChange(this)">'
        '<span class="switch-slider"></span>'
        '</span>'
        '</label>'
        '</div>'
    )
    return left_html + right_html


def get_pin_login_page(theme="dark", lang="en", error_msg=""):
    title_txt = html.escape(tr("web_auth_req", lang))
    hint_txt = html.escape(tr("pin_hint", lang))
    btn_txt = html.escape(tr("connect", lang))
    err_html = f'<p style="color:#ff453a;margin-top:10px;font-size:14px;">{html.escape(error_msg)}</p>' if error_msg else ""
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>AirShare PC — PIN</title>'
        f'<style>{get_css(theme)}</style>'
        f'</head><body class="{theme}">'
        '<canvas id="skyCanvas"></canvas>'
        f'{get_top_controls_html(theme, lang=lang, show_preview_toggle=False)}'
        '<div class="container">'
        '<div class="pin-card">'
        '<h1 style="font-size:30px;margin-bottom:8px;">AirShare PC</h1>'
        f'<p style="opacity:0.75;font-size:14px;">{title_txt}</p>'
        '<form method="GET" action="/">'
        f'<input type="password" name="pin" class="pin-input" placeholder="••••••" title="{hint_txt}" autofocus required>'
        f'<button type="submit" class="upload-btn" style="width:100%;">{btn_txt}</button>'
        '</form>'
        f'{err_html}'
        '</div></div>'
        '<div class="credit-badge">Crafted by JackBrownUA • Powered by Gemini</div>'
        f'<script>{get_star_script()}{get_theme_script()}</script>'
        '</body></html>'
    )

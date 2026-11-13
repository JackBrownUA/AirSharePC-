# Модуль кинотеатр-плеера AirShare PC (v1.3.5): мгновенное воспроизведение по локальной сети без дублирующих потоков, Resume Playback, PiP, мини-плеер и плавающий док прогресса

import html
import json
from i18n import tr


def get_player_css() -> str:
    return """
    /* Плавающая карточка прогресса загрузки в ЛЕВОМ НИЖНЕМ углу экрана */
    .upload-dock {
        position: fixed;
        bottom: 16px;
        left: 18px;
        z-index: 45;
        width: 320px;
        max-width: calc(100vw - 36px);
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(16, 22, 38, 0.88);
        border: 1px solid rgba(96, 165, 250, 0.38);
        box-shadow: 0 14px 36px rgba(0, 0, 0, 0.60), inset 0 1px 1px rgba(255, 255, 255, 0.18);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        display: none;
        flex-direction: column;
        gap: 8px;
        transition: opacity 0.3s ease, transform 0.3s ease;
    }
    body.light .upload-dock {
        background: rgba(255, 255, 255, 0.94);
        border-color: rgba(37, 99, 235, 0.32);
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.16);
    }
    .upload-dock.visible {
        display: flex;
    }
    .dock-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        font-weight: 600;
    }
    .dock-filename {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
    }
    .dock-pct {
        color: #38d9a9;
        font-variant-numeric: tabular-nums;
    }
    body.light .dock-pct {
        color: #0ca678;
    }
    .dock-bar-track {
        width: 100%;
        height: 7px;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.12);
        overflow: hidden;
    }
    body.light .dock-bar-track {
        background: #e2e8f0;
    }
    .dock-bar-fill {
        height: 100%;
        width: 0%;
        border-radius: 6px;
        background: linear-gradient(90deg, #3b82f6 0%, #20c997 100%);
        box-shadow: 0 0 10px rgba(32, 201, 151, 0.55);
        transition: width 0.12s linear;
    }
    .dock-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 11.5px;
        color: rgba(203, 213, 225, 0.78);
        font-variant-numeric: tabular-nums;
    }
    body.light .dock-meta {
        color: #475569;
    }
    /* Кинотеатр-плеер для мгновенного воспроизведения по локальной сети */
    .media-modal {
        position: fixed;
        inset: 0;
        z-index: 60;
        background: rgba(4, 6, 12, 0.88);
        display: none;
        align-items: center;
        justify-content: center;
        padding: 24px;
    }
    .media-modal.open {
        display: flex;
    }
    .media-modal.mini-player {
        inset: auto 20px 52px auto;
        width: 360px;
        height: auto;
        padding: 0;
        background: transparent;
        pointer-events: auto;
    }
    .player-shell {
        position: relative;
        width: 100%;
        max-width: 960px;
        border-radius: 24px;
        background: rgba(14, 18, 32, 0.94);
        border: 1px solid rgba(255, 255, 255, 0.18);
        box-shadow: 0 24px 64px rgba(0, 0, 0, 0.78);
        padding: 16px 18px 18px;
        z-index: 2;
    }
    .media-modal.mini-player .player-shell {
        padding: 10px 12px 12px;
        border-radius: 18px;
    }
    #ambilightCanvas {
        position: absolute;
        inset: -28px;
        width: calc(100% + 56px);
        height: calc(100% + 56px);
        z-index: -1;
        filter: blur(36px) saturate(1.6);
        opacity: 0;
        pointer-events: none;
        border-radius: 36px;
        transition: opacity 0.35s ease;
    }
    .player-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
        flex-wrap: wrap;
    }
    .player-title {
        font-size: 15px;
        font-weight: 600;
        color: #f8fafc;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 52%;
    }
    .player-top-btns {
        display: flex;
        align-items: center;
        gap: 7px;
        flex-wrap: wrap;
    }
    .p-chip-btn {
        padding: 5px 11px;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.16);
        background: rgba(30, 41, 59, 0.75);
        color: #e2e8f0;
        font-size: 12px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .p-chip-btn:hover, .p-chip-btn.active {
        background: rgba(59, 130, 246, 0.32);
        border-color: rgba(96, 165, 250, 0.65);
        color: #ffffff;
    }
    .p-chip-btn.close-btn:hover {
        background: rgba(239, 68, 68, 0.35);
        border-color: rgba(248, 113, 113, 0.65);
    }
    .player-stage {
        position: relative;
        width: 100%;
        border-radius: 16px;
        overflow: hidden;
        background: #04060c;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 220px;
        max-height: 72vh;
    }
    .media-modal.mini-player .player-stage {
        min-height: 150px;
        max-height: 210px;
    }
    #mainVideo, #mainImage {
        width: 100%;
        max-height: 70vh;
        display: none;
        object-fit: contain;
        outline: none;
    }
    .player-osd {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) scale(0.85);
        padding: 12px 22px;
        border-radius: 20px;
        background: rgba(15, 23, 42, 0.82);
        border: 1px solid rgba(255, 255, 255, 0.22);
        color: #ffffff;
        font-size: 18px;
        font-weight: 600;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.22s ease, transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .player-osd.show {
        opacity: 1;
        transform: translate(-50%, -50%) scale(1);
    }
    .resume-banner {
        position: absolute;
        bottom: 58px;
        left: 16px;
        z-index: 10;
        display: none;
        align-items: center;
        gap: 10px;
        padding: 8px 14px;
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.90);
        border: 1px solid rgba(56, 217, 169, 0.55);
        color: #f8fafc;
        font-size: 13px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.55);
    }
    .resume-banner.show {
        display: inline-flex;
    }
    .resume-action-btn {
        padding: 4px 11px;
        border-radius: 10px;
        border: none;
        background: linear-gradient(135deg, #20c997, #12b886);
        color: #fff;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
    }
    .timeline-wrap {
        position: relative;
        margin-top: 12px;
        padding: 6px 0;
        cursor: pointer;
        display: none;
    }
    .timeline-track {
        width: 100%;
        height: 6px;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.16);
        position: relative;
        overflow: hidden;
    }
    .timeline-fill {
        height: 100%;
        width: 0%;
        background: linear-gradient(90deg, #3b82f6, #20c997);
        border-radius: 6px;
    }
    .scrub-preview {
        position: absolute;
        bottom: 18px;
        left: 0;
        transform: translateX(-50%);
        padding: 4px 9px;
        border-radius: 8px;
        background: rgba(15, 23, 42, 0.94);
        border: 1px solid rgba(255, 255, 255, 0.22);
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.55);
        display: none;
        align-items: center;
        justify-content: center;
        pointer-events: none;
        z-index: 15;
    }
    .scrub-time {
        font-size: 11.5px;
        font-weight: 600;
        color: #e2e8f0;
        font-variant-numeric: tabular-nums;
    }
    """


def get_media_modal_html(lang: str = "en") -> str:
    ambi_txt = html.escape(tr("web_ambilight", lang))
    pip_txt = html.escape(tr("web_pip", lang))
    mini_txt = html.escape(tr("web_mini", lang))
    resume_btn_txt = html.escape(tr("web_resume_btn", lang))
    close_txt = html.escape(tr("close", lang))
    return (
        '<div class="media-modal" id="mediaModal">'
        '<div class="player-shell">'
        '<canvas id="ambilightCanvas" width="16" height="9"></canvas>'
        '<div class="player-header">'
        '<div class="player-title" id="playerTitle">AirShare Cinema</div>'
        '<div class="player-top-btns">'
        f'<button type="button" class="p-chip-btn" id="ambiBtn" onclick="toggleAmbilight(this)">{ambi_txt}</button>'
        f'<button type="button" class="p-chip-btn" onclick="togglePiP()">{pip_txt}</button>'
        f'<button type="button" class="p-chip-btn" onclick="toggleMiniPlayer()">{mini_txt}</button>'
        f'<button type="button" class="p-chip-btn close-btn" onclick="closeMediaPlayer()">✕ {close_txt}</button>'
        '</div></div>'
        '<div class="player-stage">'
        '<video id="mainVideo" controls playsinline preload="auto"></video>'
        '<img id="mainImage" alt="">'
        '<div class="player-osd" id="playerOsd"></div>'
        '<div class="resume-banner" id="resumeBanner">'
        '<span id="resumeText"></span>'
        f'<button type="button" class="resume-action-btn" onclick="confirmResumePlayback()">{resume_btn_txt}</button>'
        '</div></div>'
        '<div class="timeline-wrap" id="timelineWrap">'
        '<div class="scrub-preview" id="scrubPreview">'
        '<span class="scrub-time" id="scrubTime">00:00</span>'
        '</div>'
        '<div class="timeline-track"><div class="timeline-fill" id="timelineFill"></div></div>'
        '</div>'
        '</div></div>'
        '<div class="upload-dock" id="uploadProgressDock">'
        '<div class="dock-top">'
        '<span class="dock-filename" id="dockFileName">Uploading...</span>'
        '<span class="dock-pct" id="dockPct">0%</span>'
        '</div>'
        '<div class="dock-bar-track"><div class="dock-bar-fill" id="dockBarFill"></div></div>'
        '<div class="dock-meta">'
        '<span id="dockSpeed">0.0 MB/s</span>'
        '<span id="dockEta"></span>'
        '</div></div>'
    )


def get_player_script(lang: str = "en") -> str:
    msg_resume_ask = json.dumps(tr("web_resume_ask", lang))
    return f"""
    let _ambiEnabled = false;
    let _ambiRaf = null;
    let _currentMediaKey = "";
    let _osdTimer = null;

    function formatClock(sec) {{
        if (!isFinite(sec) || sec < 0) return "00:00";
        const s = Math.round(sec);
        const m = Math.floor(s / 60);
        const r = s % 60;
        return String(m).padStart(2, "0") + ":" + String(r).padStart(2, "0");
    }}

    function showPlayerOsd(text) {{
        const osd = document.getElementById("playerOsd");
        if (!osd) return;
        osd.innerText = text;
        osd.classList.add("show");
        if (_osdTimer) clearTimeout(_osdTimer);
        _osdTimer = setTimeout(function() {{ osd.classList.remove("show"); }}, 650);
    }}

    function _pauseBackgroundThumbVideos() {{
        const thumbs = document.querySelectorAll("video.file-thumb[src]");
        for (let i = 0; i < thumbs.length; i++) {{
            try {{
                thumbs[i].pause();
                if (thumbs[i].readyState < 2) {{
                    thumbs[i].removeAttribute("src");
                    thumbs[i].load();
                }}
            }} catch (e) {{}}
        }}
    }}

    function openMediaPlayer(url, filename, kind) {{
        const modal = document.getElementById("mediaModal");
        const vid = document.getElementById("mainVideo");
        const img = document.getElementById("mainImage");
        const tlWrap = document.getElementById("timelineWrap");
        const titleEl = document.getElementById("playerTitle");
        const resumeBanner = document.getElementById("resumeBanner");
        const resumeText = document.getElementById("resumeText");
        if (!modal || !vid || !img) return true;

        if (titleEl) titleEl.innerText = filename;
        _currentMediaKey = "airshare_pos_" + filename;
        modal.classList.add("open");

        if (kind === "image") {{
            vid.pause();
            vid.removeAttribute("src");
            vid.style.display = "none";
            if (tlWrap) tlWrap.style.display = "none";
            if (resumeBanner) resumeBanner.classList.remove("show");
            img.style.display = "block";
            img.onload = function() {{ drawAmbilightOnce(img); }};
            img.src = url;
        }} else {{
            _pauseBackgroundThumbVideos();
            img.style.display = "none";
            img.removeAttribute("src");
            vid.style.display = "block";
            if (tlWrap) tlWrap.style.display = "block";
            vid.src = url;
            try {{
                const savedVol = localStorage.getItem("airshare_vol");
                if (savedVol !== null) vid.volume = Math.max(0, Math.min(1, parseFloat(savedVol)));
            }} catch (e) {{}}
            vid.play().catch(function(){{}});
            if (_ambiEnabled) startAmbilightLoop();

            if (resumeBanner) resumeBanner.classList.remove("show");
            vid.onloadedmetadata = function() {{
                try {{
                    const savedSec = parseFloat(localStorage.getItem(_currentMediaKey) || "0");
                    if (savedSec > 5 && vid.duration && savedSec < vid.duration - 5) {{
                        const tpl = {msg_resume_ask};
                        if (resumeText) resumeText.innerText = tpl.replace("{{time}}", formatClock(savedSec));
                        if (resumeBanner) {{
                            resumeBanner.dataset.sec = String(savedSec);
                            resumeBanner.classList.add("show");
                        }}
                    }}
                }} catch (e) {{}}
            }};
        }}
        return false;
    }}

    function confirmResumePlayback() {{
        const vid = document.getElementById("mainVideo");
        const resumeBanner = document.getElementById("resumeBanner");
        if (vid && resumeBanner && resumeBanner.dataset.sec) {{
            vid.currentTime = parseFloat(resumeBanner.dataset.sec);
            resumeBanner.classList.remove("show");
            showPlayerOsd("▶ " + formatClock(vid.currentTime));
        }}
    }}

    function closeMediaPlayer() {{
        const modal = document.getElementById("mediaModal");
        const vid = document.getElementById("mainVideo");
        if (vid) {{
            vid.pause();
            vid.removeAttribute("src");
            try {{ vid.load(); }} catch (e) {{}}
        }}
        if (_ambiRaf) {{ cancelAnimationFrame(_ambiRaf); _ambiRaf = null; }}
        if (modal) {{
            modal.classList.remove("open");
            modal.classList.remove("mini-player");
        }}
        if (document.body.classList.contains("show-previews") && typeof _activateVisibleThumbs === "function") {{
            setTimeout(_activateVisibleThumbs, 150);
        }}
    }}

    function toggleAmbilight(btn) {{
        _ambiEnabled = !_ambiEnabled;
        const c = document.getElementById("ambilightCanvas");
        if (c) c.style.opacity = _ambiEnabled ? "0.75" : "0";
        if (btn) btn.classList.toggle("active", _ambiEnabled);
        if (_ambiEnabled) {{
            startAmbilightLoop();
        }} else if (_ambiRaf) {{
            cancelAnimationFrame(_ambiRaf);
            _ambiRaf = null;
        }}
    }}

    function toggleMiniPlayer() {{
        const modal = document.getElementById("mediaModal");
        if (modal) modal.classList.toggle("mini-player");
    }}

    async function togglePiP() {{
        const vid = document.getElementById("mainVideo");
        if (!vid) return;
        try {{
            if (document.pictureInPictureElement) {{
                await document.exitPictureInPicture();
            }} else if (vid.requestPictureInPicture) {{
                await vid.requestPictureInPicture();
            }} else {{
                toggleMiniPlayer();
            }}
        }} catch (e) {{
            toggleMiniPlayer();
        }}
    }}

    function drawAmbilightOnce(sourceEl) {{
        const canvas = document.getElementById("ambilightCanvas");
        if (!canvas || !_ambiEnabled) return;
        const ctx = canvas.getContext("2d");
        try {{
            ctx.drawImage(sourceEl, 0, 0, canvas.width, canvas.height);
        }} catch (e) {{}}
    }}

    function startAmbilightLoop() {{
        if (_ambiRaf) cancelAnimationFrame(_ambiRaf);
        if (!_ambiEnabled) return;
        const canvas = document.getElementById("ambilightCanvas");
        const vid = document.getElementById("mainVideo");
        if (!canvas || !vid) return;
        const ctx = canvas.getContext("2d");
        let lastDraw = 0;
        function step(ts) {{
            const modal = document.getElementById("mediaModal");
            if (!modal || !modal.classList.contains("open") || !_ambiEnabled) return;
            _ambiRaf = requestAnimationFrame(step);
            if (vid.paused || vid.ended || vid.seeking) return;
            if (ts - lastDraw < 220) return;
            lastDraw = ts;
            try {{
                ctx.drawImage(vid, 0, 0, canvas.width, canvas.height);
            }} catch (e) {{}}
        }}
        _ambiRaf = requestAnimationFrame(step);
    }}

    (function initPlayerInteractions() {{
        window.addEventListener("DOMContentLoaded", function() {{
            const vid = document.getElementById("mainVideo");
            const tlWrap = document.getElementById("timelineWrap");
            const tlFill = document.getElementById("timelineFill");
            const scrubBox = document.getElementById("scrubPreview");
            const scrubTime = document.getElementById("scrubTime");
            if (!vid) return;

            let lastSave = 0;
            vid.addEventListener("timeupdate", function() {{
                if (vid.duration && tlFill) {{
                    tlFill.style.width = ((vid.currentTime / vid.duration) * 100).toFixed(2) + "%";
                }}
                const now = Date.now();
                if (_currentMediaKey && now - lastSave > 2000 && vid.currentTime > 3) {{
                    lastSave = now;
                    try {{ localStorage.setItem(_currentMediaKey, String(vid.currentTime)); }} catch (e) {{}}
                }}
            }});

            vid.addEventListener("volumechange", function() {{
                try {{ localStorage.setItem("airshare_vol", String(vid.volume)); }} catch (e) {{}}
            }});

            vid.addEventListener("wheel", function(e) {{
                e.preventDefault();
                const delta = e.deltaY < 0 ? 0.05 : -0.05;
                vid.volume = Math.max(0, Math.min(1, vid.volume + delta));
                showPlayerOsd("🔊 " + Math.round(vid.volume * 100) + "%");
            }}, {{ passive: false }});

            if (tlWrap && scrubBox) {{
                tlWrap.addEventListener("mousemove", function(e) {{
                    if (!vid.duration) return;
                    const rect = tlWrap.getBoundingClientRect();
                    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                    const targetSec = ratio * vid.duration;
                    scrubBox.style.display = "flex";
                    scrubBox.style.left = (ratio * 100) + "%";
                    if (scrubTime) scrubTime.innerText = formatClock(targetSec);
                }});
                tlWrap.addEventListener("mouseleave", function() {{
                    scrubBox.style.display = "none";
                }});
                tlWrap.addEventListener("click", function(e) {{
                    if (!vid.duration) return;
                    const rect = tlWrap.getBoundingClientRect();
                    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                    vid.currentTime = ratio * vid.duration;
                }});
            }}

            document.addEventListener("keydown", function(e) {{
                const modal = document.getElementById("mediaModal");
                if (!modal || !modal.classList.contains("open")) return;
                if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
                if (e.key === "Escape") {{
                    closeMediaPlayer();
                }} else if (e.code === "Space" && vid.style.display !== "none") {{
                    e.preventDefault();
                    if (vid.paused) {{ vid.play(); showPlayerOsd("▶"); }}
                    else {{ vid.pause(); showPlayerOsd("⏸"); }}
                }} else if (e.key === "ArrowRight" && vid.style.display !== "none") {{
                    e.preventDefault();
                    vid.currentTime = Math.min(vid.duration || 0, vid.currentTime + 10);
                    showPlayerOsd("+10s ⏩");
                }} else if (e.key === "ArrowLeft" && vid.style.display !== "none") {{
                    e.preventDefault();
                    vid.currentTime = Math.max(0, vid.currentTime - 10);
                    showPlayerOsd("⏪ -10s");
                }} else if (e.key === "ArrowUp" && vid.style.display !== "none") {{
                    e.preventDefault();
                    vid.volume = Math.min(1, vid.volume + 0.05);
                    showPlayerOsd("🔊 " + Math.round(vid.volume * 100) + "%");
                }} else if (e.key === "ArrowDown" && vid.style.display !== "none") {{
                    e.preventDefault();
                    vid.volume = Math.max(0, vid.volume - 0.05);
                    showPlayerOsd("🔉 " + Math.round(vid.volume * 100) + "%");
                }} else if ((e.key === "m" || e.key === "M") && vid.style.display !== "none") {{
                    vid.muted = !vid.muted;
                    showPlayerOsd(vid.muted ? "🔇 Mute" : "🔊");
                }} else if ((e.key === "f" || e.key === "F") && vid.style.display !== "none") {{
                    if (vid.requestFullscreen) vid.requestFullscreen();
                }}
            }});
        }});
    }})();
    """

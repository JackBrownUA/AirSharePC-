"""
Web UI templates and styling for AirShare PC
Edit design here without touching server code
"""


def get_css(theme="dark"):
    """Returns CSS styles supporting both dark and light themes with instant switching"""
    return """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        min-height: 100vh;
        overflow-x: hidden;
        transition: background-color 0.25s ease, color 0.25s ease;
        background: #000;
        color: #e0e0e0;
    }
    body.light {
        background: #f5f5f7;
        color: #1d1d1f;
    }
    #starfield {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 0;
        pointer-events: none;
    }
    body.light #starfield {
        display: none;
    }
    .star {
        position: absolute;
        background: white;
        border-radius: 50%;
        animation: twinkle 3s infinite;
    }
    @keyframes twinkle {
        0%, 100% { opacity: 0.3; }
        50% { opacity: 1; }
    }
    .container {
        position: relative;
        z-index: 1;
        max-width: 820px;
        margin: 0 auto;
        padding: 60px 20px;
    }
    .header {
        text-align: center;
        margin-bottom: 36px;
    }
    .header h1 {
        color: #fff;
        font-size: 44px;
        font-weight: 300;
        margin-bottom: 10px;
        text-shadow: 0 0 40px rgba(102, 126, 234, 0.5);
    }
    body.light .header h1 {
        color: #1d1d1f;
        text-shadow: none;
    }
    .header p {
        color: rgba(255, 255, 255, 0.55);
        font-size: 14px;
        margin-bottom: 20px;
        word-break: break-all;
    }
    body.light .header p {
        color: rgba(0, 0, 0, 0.55);
    }
    .theme-toggle {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 10;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.18);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        font-size: 22px;
        color: #fff;
        transition: 0.25s;
    }
    .theme-toggle:hover {
        background: rgba(102, 126, 234, 0.35);
    }
    body.light .theme-toggle {
        background: #fff;
        border: 1px solid #d2d2d7;
        color: #1d1d1f;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    body.light .theme-toggle:hover {
        background: #f0f0f5;
    }
    .actions-bar {
        display: flex;
        gap: 12px;
        justify-content: center;
        flex-wrap: wrap;
        margin-top: 8px;
    }
    .upload-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 12px 24px;
        background: rgba(102, 126, 234, 0.25);
        border: 1px solid #667eea;
        border-radius: 25px;
        color: #fff;
        cursor: pointer;
        font-size: 15px;
        text-decoration: none;
        transition: 0.25s;
    }
    .upload-btn:hover {
        background: #667eea;
        color: #fff;
    }
    body.light .upload-btn {
        background: rgba(0, 122, 255, 0.1);
        border: 1px solid #007aff;
        color: #007aff;
    }
    body.light .upload-btn:hover {
        background: #007aff;
        color: #fff;
    }
    .toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.04);
        font-size: 14px;
    }
    body.light .toolbar {
        background: #fff;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
    }
    .toolbar label {
        display: flex;
        align-items: center;
        cursor: pointer;
        user-select: none;
    }
    .file-list {
        list-style: none;
        border-radius: 12px;
        overflow: hidden;
    }
    body.light .file-list {
        background: #fff;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    .file-item {
        padding: 16px 18px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
    }
    body.light .file-item {
        border-bottom: 1px solid #e5e5ea;
    }
    .file-item:last-child {
        border-bottom: none;
    }
    .file-info {
        flex: 1;
        min-width: 0;
    }
    .file-link {
        color: #fff;
        text-decoration: none;
        font-size: 17px;
        display: block;
        margin-bottom: 4px;
        word-break: break-word;
    }
    .file-link:hover {
        color: #667eea;
    }
    body.light .file-link {
        color: #1d1d1f;
    }
    body.light .file-link:hover {
        color: #007aff;
    }
    .file-meta {
        color: rgba(255, 255, 255, 0.45);
        font-size: 13px;
    }
    body.light .file-meta {
        color: rgba(0, 0, 0, 0.5);
    }
    .download-btn {
        width: 40px;
        height: 40px;
        flex-shrink: 0;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.14);
        display: flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
        color: #fff;
        transition: 0.25s;
    }
    .download-btn:hover {
        background: #667eea;
        border-color: #667eea;
        color: #fff;
    }
    body.light .download-btn {
        background: rgba(0, 122, 255, 0.1);
        border: 1px solid #007aff;
        color: #007aff;
    }
    body.light .download-btn:hover {
        background: #007aff;
        color: #fff;
    }
    .checkbox {
        width: 20px;
        height: 20px;
        cursor: pointer;
        margin-right: 8px;
        flex-shrink: 0;
    }
    """


def get_star_script():
    """JavaScript for star animation"""
    return """
    (function(){
        const sf = document.getElementById("starfield");
        if (sf && sf.children.length === 0) {
            for (let i = 0; i < 120; i++) {
                const s = document.createElement("div");
                s.className = "star";
                s.style.left = Math.random() * 100 + "%";
                s.style.top = Math.random() * 100 + "%";
                s.style.width = s.style.height = (Math.random() * 2.5 + 1) + "px";
                s.style.animationDelay = Math.random() * 3 + "s";
                sf.appendChild(s);
            }
        }
    })();
    """


def get_upload_script():
    """JavaScript for reliable file upload and batch download validation"""
    return """
    function triggerUpload() {
        const input = document.getElementById("up");
        if (input) {
            input.value = "";
            input.click();
        }
    }

    async function uploadFiles(files) {
        if (!files || files.length === 0) return;
        const st = document.getElementById("status");
        const basePath = window.location.pathname || "/";
        let uploadedCount = 0;

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            if (st) {
                st.style.color = "#667eea";
                st.innerText = "Загрузка " + file.name + " (" + (i + 1) + "/" + files.length + ")...";
            }
            try {
                const res = await fetch(basePath + "?upload=" + encodeURIComponent(file.name), {
                    method: "POST",
                    body: file,
                    credentials: "same-origin",
                    headers: {
                        "X-File-Name": encodeURIComponent(file.name)
                    }
                });
                if (!res.ok) {
                    const errText = await res.text();
                    throw new Error(errText || ("HTTP " + res.status));
                }
                uploadedCount++;
            } catch (err) {
                if (st) {
                    st.style.color = "#ff453a";
                    st.innerText = "Ошибка загрузки " + file.name + ": " + err.message;
                }
                return;
            }
        }
        if (st && uploadedCount > 0) {
            st.style.color = "#30d158";
            st.innerText = "Загружено файлов: " + uploadedCount + ". Обновление...";
        }
        window.location.href = basePath + window.location.search;
    }

    function toggleSelectAll(masterCheckbox) {
        const boxes = document.querySelectorAll('input[name="files"]');
        for (let i = 0; i < boxes.length; i++) {
            boxes[i].checked = masterCheckbox.checked;
        }
    }

    function submitSelectedDownload(event) {
        const checked = document.querySelectorAll('input[name="files"]:checked');
        const st = document.getElementById("status");
        if (!checked || checked.length === 0) {
            if (event) event.preventDefault();
            if (st) {
                st.style.color = "#ff9f0a";
                st.innerText = "Отметьте галочками хотя бы один файл или папку для скачивания.";
            }
            return false;
        }
        if (st) {
            st.style.color = "#667eea";
            st.innerText = "Подготовка архива (" + checked.length + " поз.)...";
        }
        return true;
    }
    """


def get_theme_script():
    """JavaScript for instant light/dark theme toggle with cookie & localStorage persistence"""
    return """
    function applyTheme(theme) {
        const isLight = (theme === "light");
        document.body.classList.toggle("light", isLight);
        document.body.classList.toggle("dark", !isLight);
        const btn = document.getElementById("themeBtn");
        if (btn) {
            btn.innerText = isLight ? "🌙" : "☀️";
            btn.title = isLight ? "Переключить на тёмную тему" : "Переключить на светлую тему";
        }
        try {
            localStorage.setItem("airshare_theme", isLight ? "light" : "dark");
        } catch (e) {}
        document.cookie = "airshare_theme=" + (isLight ? "light" : "dark") + "; path=/; max-age=31536000; SameSite=Lax";
    }

    function toggleTheme() {
        const isCurrentlyLight = document.body.classList.contains("light");
        const nextTheme = isCurrentlyLight ? "dark" : "light";
        applyTheme(nextTheme);
        const url = new URL(window.location.href);
        if (url.searchParams.has("theme")) {
            url.searchParams.set("theme", nextTheme);
            window.history.replaceState({}, "", url.toString());
        }
    }

    (function initTheme() {
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
        }
    })();
    """

# Модуль PWA (Progressive Web App) и мгновенного поиска по хранилищу для AirShare PC (v1.3.5)

import json
import os
import threading
import time

from config import APP_NAME, APP_VERSION
from i18n import tr
from security import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, is_temp_part_file, is_within_storage
from utils import format_size

PWA_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
    '<rect width="128" height="128" rx="28" fill="#090c15"/>'
    '<rect x="20" y="28" width="88" height="58" rx="10" fill="none" stroke="#3b82f6" stroke-width="6"/>'
    '<path d="M36 74 A28 28 0 0 1 92 74" fill="none" stroke="#20c997" stroke-width="6" stroke-linecap="round"/>'
    '<line x1="46" y1="100" x2="82" y2="100" stroke="#94a3b8" stroke-width="6" stroke-linecap="round"/>'
    '</svg>'
)

PWA_SW_JS = (
    "self.addEventListener('install', e => self.skipWaiting());\n"
    "self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));\n"
    "self.addEventListener('fetch', e => {});\n"
)


def serve_pwa_asset(handler, path_only: str) -> bool:
    if path_only == "/manifest.webmanifest":
        manifest = {
            "name": f"{APP_NAME} v{APP_VERSION}",
            "short_name": APP_NAME,
            "start_url": "/",
            "display": "standalone",
            "background_color": "#040508",
            "theme_color": "#090c15",
            "icons": [
                {
                    "src": "/icon.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any maskable",
                }
            ],
        }
        body = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/manifest+json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True
    if path_only == "/sw.js":
        body = PWA_SW_JS.encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/javascript; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True
    if path_only == "/icon.svg":
        body = PWA_ICON_SVG.encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        handler.send_header("Cache-Control", "public, max-age=86400")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True
    return False


def search_storage_index(
    real_storage: str,
    query_str: str,
    current_language: str,
    search_cache: dict,
    lock: threading.Lock,
) -> list:
    q = str(query_str or "").strip().lower()
    if not q:
        return []
    now = time.monotonic()
    with lock:
        cached_root = search_cache.get("root")
        cached_ts = search_cache.get("ts", 0.0)
        entries = search_cache.get("entries", [])

    if cached_root != real_storage or (now - cached_ts) > 5.0:
        new_entries = []
        try:
            for root, dirs, files in os.walk(real_storage, followlinks=False):
                dirs[:] = [d for d in dirs if not is_temp_part_file(d)]
                for d in dirs:
                    full_d = os.path.join(root, d)
                    if not is_within_storage(real_storage, full_d):
                        continue
                    rel_d = os.path.relpath(full_d, real_storage).replace("\\", "/")
                    new_entries.append((d.lower(), d, rel_d, True, tr("web_folder", current_language), "folder"))
                    if len(new_entries) >= 25000:
                        break
                for f in files:
                    if is_temp_part_file(f):
                        continue
                    full_f = os.path.join(root, f)
                    if not is_within_storage(real_storage, full_f):
                        continue
                    rel_f = os.path.relpath(full_f, real_storage).replace("\\", "/")
                    try:
                        sz = format_size(os.path.getsize(full_f))
                    except OSError:
                        sz = "—"
                    _, ext = os.path.splitext(f)
                    ext_low = ext.lower()
                    kind = "image" if ext_low in IMAGE_EXTENSIONS else ("video" if ext_low in VIDEO_EXTENSIONS else "file")
                    new_entries.append((f.lower(), f, rel_f, False, sz, kind))
                    if len(new_entries) >= 25000:
                        break
                if len(new_entries) >= 25000:
                    break
        except OSError:
            pass
        entries = new_entries
        with lock:
            search_cache["root"] = real_storage
            search_cache["ts"] = time.monotonic()
            search_cache["entries"] = entries

    matches = []
    for low_name, orig_name, rel_p, is_d, sz_str, kind in entries:
        if q in low_name:
            matches.append(
                {
                    "name": orig_name,
                    "rel_path": rel_p,
                    "is_dir": is_d,
                    "size_str": sz_str,
                    "kind": kind,
                }
            )
            if len(matches) >= 60:
                break
    return matches


def get_search_and_pwa_script() -> str:
    return """
    let _searchTimer = null;
    function onSearchInput(inputEl) {
        const q = (inputEl.value || "").trim().toLowerCase();
        const clearBtn = document.getElementById("searchClearBtn");
        if (clearBtn) clearBtn.style.display = q ? "block" : "none";

        const items = document.querySelectorAll("#mainFileList > li.file-item");
        items.forEach(function(li) {
            const name = (li.getAttribute("data-name") || "").toLowerCase();
            li.style.display = (!q || name.indexOf(q) !== -1) ? "flex" : "none";
        });

        const srvBox = document.getElementById("serverSearchBox");
        if (_searchTimer) clearTimeout(_searchTimer);
        if (q.length < 2) {
            if (srvBox) { srvBox.style.display = "none"; srvBox.innerHTML = ""; }
            return;
        }
        _searchTimer = setTimeout(async function() {
            try {
                const res = await fetch("?q=" + encodeURIComponent(q) + "&ajax=1", { credentials: "same-origin" });
                if (!res.ok) return;
                const data = await res.json();
                if (!srvBox || !data || !Array.isArray(data.results)) return;
                if (data.results.length === 0) {
                    srvBox.style.display = "none";
                    return;
                }
                srvBox.innerHTML = "";
                const ul = document.createElement("ul");
                ul.className = "file-list";
                ul.style.marginBottom = "14px";
                data.results.forEach(function(item) {
                    const encodedParts = String(item.rel_path || "").split("/").map(encodeURIComponent).join("/");
                    const safeHref = "/" + encodedParts + (item.is_dir ? "/" : "");
                    const li = document.createElement("li");
                    li.className = "file-item";
                    const info = document.createElement("div");
                    info.className = "file-info";
                    const col = document.createElement("div");
                    col.className = "file-text-col";
                    const a = document.createElement("a");
                    a.className = "file-link";
                    a.href = safeHref;
                    a.textContent = (item.is_dir ? "📁 " : "📄 ") + item.name;
                    if (!item.is_dir && (item.kind === "video" || item.kind === "image")) {
                        a.addEventListener("click", function(ev) {
                            ev.preventDefault();
                            openMediaPlayer(safeHref, item.name, item.kind);
                        });
                    }
                    const meta = document.createElement("div");
                    meta.className = "file-meta";
                    const s1 = document.createElement("span");
                    s1.textContent = item.rel_path;
                    const s2 = document.createElement("span");
                    s2.textContent = item.size_str;
                    meta.appendChild(s1);
                    meta.appendChild(s2);
                    col.appendChild(a);
                    col.appendChild(meta);
                    info.appendChild(col);
                    li.appendChild(info);
                    ul.appendChild(li);
                });
                srvBox.appendChild(ul);
                srvBox.style.display = "block";
            } catch (e) {}
        }, 220);
    }

    function clearSearch() {
        const inp = document.getElementById("fileSearchInput");
        if (inp) {
            inp.value = "";
            onSearchInput(inp);
            inp.focus();
        }
    }

    let _deferredPwaPrompt = null;
    if ("serviceWorker" in navigator) {
        window.addEventListener("load", function() {
            navigator.serviceWorker.register("/sw.js").catch(function(){});
        });
    }
    window.addEventListener("beforeinstallprompt", function(e) {
        e.preventDefault();
        _deferredPwaPrompt = e;
        const btn = document.getElementById("pwaInstallBtn");
        if (btn) btn.style.display = "inline-flex";
    });
    async function installPwaApp() {
        if (!_deferredPwaPrompt) return;
        _deferredPwaPrompt.prompt();
        await _deferredPwaPrompt.userChoice;
        _deferredPwaPrompt = null;
        const btn = document.getElementById("pwaInstallBtn");
        if (btn) btn.style.display = "none";
    }
    """

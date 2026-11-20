# Модуль мгновенного поиска по хранилищу для AirShare PC (v1.3.6)

import os
import threading
import time

from i18n import tr
from security import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, is_temp_part_file, is_within_storage
from utils import format_size


def _build_storage_entries(real_storage: str, current_language: str) -> list:
    new_entries = []
    skip_names = {".thumbnails", ".trash", ".Trashes"}
    try:
        for root, dirs, files in os.walk(real_storage, followlinks=False):
            rel_root = os.path.relpath(root, real_storage).replace("\\", "/")
            if rel_root == "Android":
                dirs[:] = [d for d in dirs if d not in ("data", "obb") and not is_temp_part_file(d)]
            else:
                dirs[:] = [d for d in dirs if d not in skip_names and not is_temp_part_file(d)]
            for d in dirs:
                full_d = os.path.join(root, d)
                if os.path.islink(full_d) and not is_within_storage(real_storage, full_d):
                    continue
                rel_d = os.path.relpath(full_d, real_storage).replace("\\", "/")
                new_entries.append((d.lower(), d, rel_d, True, tr("web_folder", current_language), "folder"))
                if len(new_entries) >= 50000:
                    break
            for f in files:
                if is_temp_part_file(f):
                    continue
                full_f = os.path.join(root, f)
                if os.path.islink(full_f) and not is_within_storage(real_storage, full_f):
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
                if len(new_entries) >= 50000:
                    break
            if len(new_entries) >= 50000:
                break
    except OSError:
        pass
    return new_entries


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
    need_sync_build = False
    need_bg_refresh = False
    with lock:
        cached_root = search_cache.get("root")
        cached_ts = search_cache.get("ts", 0.0)
        entries = list(search_cache.get("entries", []))
        is_building = bool(search_cache.get("building", False))
        if cached_root != real_storage or not entries:
            need_sync_build = True
            search_cache["building"] = True
        elif (now - cached_ts) > 45.0 and not is_building:
            need_bg_refresh = True
            search_cache["building"] = True

    if need_sync_build:
        try:
            entries = _build_storage_entries(real_storage, current_language)
        finally:
            with lock:
                search_cache["root"] = real_storage
                search_cache["ts"] = time.monotonic()
                search_cache["entries"] = entries
                search_cache["building"] = False
    elif need_bg_refresh:
        def _bg_job():
            new_entries = []
            try:
                new_entries = _build_storage_entries(real_storage, current_language)
            finally:
                with lock:
                    if new_entries:
                        search_cache["root"] = real_storage
                        search_cache["ts"] = time.monotonic()
                        search_cache["entries"] = new_entries
                    search_cache["building"] = False
        threading.Thread(target=_bg_job, daemon=True).start()

    tokens = [tok for tok in q.split() if tok]
    matches = []
    for low_name, orig_name, rel_p, is_d, sz_str, kind in entries:
        if all(tok in low_name for tok in tokens):
            matches.append(
                {
                    "name": orig_name,
                    "rel_path": rel_p,
                    "is_dir": is_d,
                    "size_str": sz_str,
                    "kind": kind,
                }
            )
            if len(matches) >= 250:
                break
    return matches


def get_search_and_pwa_script() -> str:
    return """
    let _searchTimer = null;
    function onSearchInput(inputEl) {
        const q = (inputEl.value || "").trim().toLowerCase();
        const clearBtn = document.getElementById("searchClearBtn");
        if (clearBtn) clearBtn.style.display = q ? "block" : "none";

        const tokens = q.split(/\\s+/).filter(Boolean);
        const items = document.querySelectorAll("#mainFileList > li.file-item");
        items.forEach(function(li) {
            const name = (li.getAttribute("data-name") || "").toLowerCase();
            const matched = tokens.length === 0 || tokens.every(function(tok) { return name.indexOf(tok) !== -1; });
            li.style.display = matched ? "flex" : "none";
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

    window.addEventListener("DOMContentLoaded", function() {
        const inp = document.getElementById("fileSearchInput");
        if (inp) {
            ["input", "keyup", "compositionend", "search"].forEach(function(evtName) {
                inp.addEventListener(evtName, function() { onSearchInput(inp); });
            });
        }
    });
    """

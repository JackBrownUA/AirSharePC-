# Модуль генерации HTML, CSS и клиентского JavaScript веб-интерфейса для AirShare PC (v1.3.5)

import html
import json

from i18n import SUPPORTED_LANGUAGES, tr
from player_ui import get_player_css, get_player_script
from pwa_search import get_search_and_pwa_script
from security import get_sha256_js

def get_flag_svg(code: str) -> str:
    code = (code or "en").lower()
    if code == "ru":
        return (
            '<svg class="flag-svg" viewBox="0 0 24 18">'
            '<rect width="24" height="6" y="0" fill="#ffffff"/>'
            '<rect width="24" height="6" y="6" fill="#0039a6"/>'
            '<rect width="24" height="6" y="12" fill="#d52b1e"/>'
            '</svg>'
        )
    if code == "uk":
        return (
            '<svg class="flag-svg" viewBox="0 0 24 18">'
            '<rect width="24" height="9" y="0" fill="#005bbb"/>'
            '<rect width="24" height="9" y="9" fill="#ffd500"/>'
            '</svg>'
        )
    if code == "de":
        return (
            '<svg class="flag-svg" viewBox="0 0 24 18">'
            '<rect width="24" height="6" y="0" fill="#111111"/>'
            '<rect width="24" height="6" y="6" fill="#dd0000"/>'
            '<rect width="24" height="6" y="12" fill="#ffce00"/>'
            '</svg>'
        )
    if code == "es":
        return (
            '<svg class="flag-svg" viewBox="0 0 24 18">'
            '<rect width="24" height="4.5" y="0" fill="#aa151b"/>'
            '<rect width="24" height="9" y="4.5" fill="#f1bf00"/>'
            '<rect width="24" height="4.5" y="13.5" fill="#aa151b"/>'
            '</svg>'
        )
    if code == "lt":
        return (
            '<svg class="flag-svg" viewBox="0 0 24 18">'
            '<rect width="24" height="6" y="0" fill="#fdb913"/>'
            '<rect width="24" height="6" y="6" fill="#006a44"/>'
            '<rect width="24" height="6" y="12" fill="#c1272d"/>'
            '</svg>'
        )
    return (
        '<svg class="flag-svg" viewBox="0 0 24 18">'
        '<rect width="24" height="18" fill="#012169"/>'
        '<path d="M0,0 L24,18 M24,0 L0,18" stroke="#ffffff" stroke-width="3.2"/>'
        '<path d="M0,0 L24,18 M24,0 L0,18" stroke="#c8102e" stroke-width="1.6"/>'
        '<path d="M12,0 V18 M0,9 H24" stroke="#ffffff" stroke-width="5.2"/>'
        '<path d="M12,0 V18 M0,9 H24" stroke="#c8102e" stroke-width="3"/>'
        '</svg>'
    )


def get_globe_svg() -> str:
    return (
        '<svg class="globe-svg" viewBox="0 0 24 24">'
        '<circle cx="12" cy="12" r="9"/>'
        '<ellipse cx="12" cy="12" rx="4.2" ry="9"/>'
        '<line x1="3.4" y1="9" x2="20.6" y2="9"/>'
        '<line x1="3.4" y1="15" x2="20.6" y2="15"/>'
        '</svg>'
    )



def get_file_icon_svg(name: str, is_dir: bool = False) -> str:
    if is_dir:
        return (
            '<svg class="ftype-svg" viewBox="0 0 24 24" fill="none">'
            '<path d="M3 6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6z" '
            'fill="rgba(59,130,246,0.22)" stroke="#60a5fa" stroke-width="1.8"/>'
            '</svg>'
        )
    ext = ("." + name.rsplit(".", 1)[-1]).lower() if "." in name else ""
    if ext == ".pdf":
        return (
            '<svg class="ftype-svg" viewBox="0 0 24 24" fill="none">'
            '<rect x="4" y="2.5" width="16" height="19" rx="3" fill="rgba(239,68,68,0.16)" stroke="#ef4444" stroke-width="1.8"/>'
            '<text x="12" y="15" text-anchor="middle" fill="#ef4444" font-size="6.4" font-weight="800" font-family="sans-serif">PDF</text>'
            '</svg>'
        )
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".heic"}:
        return (
            '<svg class="ftype-svg" viewBox="0 0 24 24" fill="none">'
            '<rect x="3" y="4" width="18" height="16" rx="3" fill="rgba(56,189,248,0.16)" stroke="#38bdf8" stroke-width="1.8"/>'
            '<circle cx="8.5" cy="9.5" r="1.6" fill="#38bdf8"/>'
            '<path d="M4.5 17l5-5 3.5 3.5 2.5-2.5 4 4" stroke="#38bdf8" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
            '</svg>'
        )
    if ext in {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".3gp"}:
        return (
            '<svg class="ftype-svg" viewBox="0 0 24 24" fill="none">'
            '<rect x="3" y="4" width="18" height="16" rx="3" fill="rgba(168,85,247,0.18)" stroke="#a855f7" stroke-width="1.8"/>'
            '<polygon points="10,8.5 16.5,12 10,15.5" fill="#c084fc"/>'
            '</svg>'
        )
    if ext in {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}:
        return (
            '<svg class="ftype-svg" viewBox="0 0 24 24" fill="none">'
            '<rect x="4" y="3" width="16" height="18" rx="3" fill="rgba(245,158,11,0.16)" stroke="#f59e0b" stroke-width="1.8"/>'
            '<path d="M10 15V8.5l5-1.2V14" stroke="#fbbf24" stroke-width="1.7" stroke-linecap="round"/>'
            '<circle cx="8.5" cy="15.5" r="1.6" fill="#fbbf24"/>'
            '<circle cx="13.5" cy="14.5" r="1.6" fill="#fbbf24"/>'
            '</svg>'
        )
    if ext in {".zip", ".rar", ".7z", ".tar", ".gz", ".xz"}:
        return (
            '<svg class="ftype-svg" viewBox="0 0 24 24" fill="none">'
            '<rect x="4" y="3" width="16" height="18" rx="3" fill="rgba(249,115,22,0.16)" stroke="#f97316" stroke-width="1.8"/>'
            '<path d="M12 4v10M10 7h4M10 10h4M10 13h4" stroke="#fb923c" stroke-width="1.7" stroke-linecap="round"/>'
            '</svg>'
        )
    if ext in {".txt", ".md", ".json", ".py", ".js", ".html", ".css", ".xml", ".csv", ".log"}:
        return (
            '<svg class="ftype-svg" viewBox="0 0 24 24" fill="none">'
            '<rect x="4" y="3" width="16" height="18" rx="3" fill="rgba(20,184,166,0.15)" stroke="#2dd4bf" stroke-width="1.8"/>'
            '<path d="M8 9h8M8 13h8M8 17h5" stroke="#2dd4bf" stroke-width="1.7" stroke-linecap="round"/>'
            '</svg>'
        )
    return (
        '<svg class="ftype-svg" viewBox="0 0 24 24" fill="none">'
        '<path d="M6 3h8l4 4v14a1.5 1.5 0 0 1-1.5 1.5h-10.5A1.5 1.5 0 0 1 4.5 21V4.5A1.5 1.5 0 0 1 6 3z" '
        'fill="rgba(255,255,255,0.9)" stroke="#94a3b8" stroke-width="1.6"/>'
        '<path d="M14 3v4h4" stroke="#94a3b8" stroke-width="1.5"/>'
        '</svg>'
    )


def get_css(theme="dark"):
    is_light = theme == "light"
    bg_init = "#f0f4fa" if is_light else "#040508"
    fg_init = "#0f172a" if is_light else "#f8fafc"

    base_css = f"""
    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    body {{
        background: {bg_init};
        color: {fg_init};
        padding: 20px;
        min-height: 100vh;
        overflow-x: hidden;
        position: relative;
        transition: background 0.35s ease, color 0.35s ease;
    }}
    body.dark {{
        background: radial-gradient(ellipse at 50% 0%, #101729 0%, #060811 55%, #020306 100%);
        color: #f8fafc;
    }}
    body.light {{
        background: linear-gradient(145deg, #f4f7fb 0%, #e5edf8 50%, #dbe6f5 100%);
        color: #0f172a;
    }}
    #skyCanvas {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 0;
        pointer-events: none;
        transition: opacity 0.45s ease;
    }}
    body.light #skyCanvas {{
        opacity: 1;
    }}
    body.dark #skyCanvas {{
        opacity: 1;
    }}
    .top-controls {{
        position: fixed;
        top: 14px;
        left: 16px;
        z-index: 20;
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }}
    .top-right-controls {{
        position: fixed;
        top: 14px;
        right: 16px;
        z-index: 25;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .ctrl-pill, .upload-btn, .download-btn, .checkbox, .p-chip-btn, .lang-item, .file-link {{
        touch-action: manipulation;
        -webkit-tap-highlight-color: transparent;
    }}
    .ctrl-pill {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 7px 13px;
        border-radius: 24px;
        background: rgba(20, 25, 40, 0.72);
        border: 1px solid rgba(255, 255, 255, 0.14);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.15);
        color: #e2e8f0;
        font-size: 13px;
        font-weight: 500;
        user-select: none;
        transition: transform 0.2s ease, background 0.3s ease, border-color 0.3s ease, color 0.3s ease, box-shadow 0.25s ease;
    }}
    .ctrl-pill:hover {{
        transform: translateY(-1px);
        border-color: rgba(96, 165, 250, 0.45);
    }}
    body.light .ctrl-pill {{
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid rgba(15, 23, 42, 0.12);
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08), inset 0 1px 1px rgba(255, 255, 255, 0.9);
        color: #1e293b;
    }}
    .lang-menu-wrap {{
        position: relative;
        display: inline-block;
    }}
    .lang-btn {{
        cursor: pointer;
        padding: 6px 11px;
        gap: 6px;
    }}
    .globe-svg {{
        width: 17px;
        height: 17px;
        stroke: #60a5fa;
        stroke-width: 1.9;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        flex-shrink: 0;
        transition: transform 0.25s ease, stroke 0.25s ease;
    }}
    .lang-btn:hover .globe-svg {{
        transform: rotate(15deg) scale(1.06);
        stroke: #93c5fd;
    }}
    body.light .globe-svg {{
        stroke: #2563eb;
    }}
    .lang-code-badge {{
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.4px;
    }}
    .lang-dropdown {{
        position: absolute;
        top: calc(100% + 8px);
        right: 0;
        width: 215px;
        padding: 8px;
        border-radius: 18px;
        background: rgba(16, 22, 36, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.16);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        box-shadow: 0 18px 42px rgba(0, 0, 0, 0.65), inset 0 1px 1px rgba(255, 255, 255, 0.18);
        opacity: 0;
        visibility: hidden;
        transform: translateY(-8px) scale(0.96);
        transform-origin: top right;
        transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), visibility 0.2s;
        z-index: 100;
    }}
    .lang-menu-wrap.open .lang-dropdown {{
        opacity: 1;
        visibility: visible;
        transform: translateY(0) scale(1);
    }}
    body.light .lang-dropdown {{
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid rgba(15, 23, 42, 0.12);
        box-shadow: 0 16px 38px rgba(15, 23, 42, 0.16), inset 0 1px 1px rgba(255, 255, 255, 0.9);
    }}
    .lang-dropdown-title {{
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.7px;
        color: rgba(148, 163, 184, 0.8);
        padding: 4px 10px 6px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 4px;
    }}
    body.light .lang-dropdown-title {{
        color: #64748b;
        border-bottom-color: rgba(15, 23, 42, 0.08);
    }}
    .lang-item {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        padding: 8px 10px;
        border-radius: 12px;
        border: none;
        background: transparent;
        color: #e2e8f0;
        font-size: 13.5px;
        font-weight: 500;
        cursor: pointer;
        text-align: left;
        transition: background 0.18s ease, color 0.18s ease, transform 0.15s ease;
    }}
    .lang-item:hover {{
        background: rgba(59, 130, 246, 0.18);
        color: #ffffff;
        transform: translateX(2px);
    }}
    .lang-item.active {{
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.28), rgba(37, 99, 235, 0.18));
        color: #60a5fa;
        font-weight: 600;
    }}
    body.light .lang-item {{
        color: #1e293b;
    }}
    body.light .lang-item:hover {{
        background: rgba(37, 99, 235, 0.10);
        color: #0f172a;
    }}
    body.light .lang-item.active {{
        background: rgba(37, 99, 235, 0.14);
        color: #2563eb;
    }}
    .lang-item-left {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .flag-svg {{
        width: 21px;
        height: 15px;
        border-radius: 3px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
        flex-shrink: 0;
    }}
    .lang-radio {{
        width: 15px;
        height: 15px;
        border-radius: 50%;
        border: 1.8px solid rgba(148, 163, 184, 0.55);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }}
    .lang-item.active .lang-radio {{
        border-color: #3b82f6;
        background: #3b82f6;
        box-shadow: 0 0 8px rgba(59, 130, 246, 0.6);
    }}
    .lang-item.active .lang-radio::after {{
        content: "";
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: #ffffff;
    }}
    .switch {{
        position: relative;
        display: inline-block;
        width: 38px;
        height: 21px;
    }}
    .switch input {{
        opacity: 0;
        width: 0;
        height: 0;
    }}
    .switch-slider {{
        position: absolute;
        cursor: pointer;
        inset: 0;
        background-color: rgba(148, 163, 184, 0.38);
        border-radius: 21px;
        transition: 0.28s;
    }}
    .switch-slider:before {{
        position: absolute;
        content: "";
        height: 15px;
        width: 15px;
        left: 3px;
        bottom: 3px;
        background-color: #ffffff;
        border-radius: 50%;
        transition: 0.28s;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    }}
    .switch input:checked + .switch-slider {{
        background: linear-gradient(135deg, #3b82f6, #20c997);
    }}
    .switch input:checked + .switch-slider:before {{
        transform: translateX(17px);
    }}
    .container {{
        max-width: 840px;
        margin: 46px auto 56px;
        position: relative;
        z-index: 2;
    }}
    .header {{
        padding: 13px 18px;
        border-radius: 16px;
        margin-bottom: 12px;
        text-align: center;
        background: rgba(18, 23, 38, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 8px 26px rgba(0, 0, 0, 0.42), inset 0 1px 1px rgba(255, 255, 255, 0.14);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
    }}
    body.light .header {{
        background: rgba(255, 255, 255, 0.84);
        border: 1px solid rgba(15, 23, 42, 0.08);
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.07), inset 0 1px 1px rgba(255, 255, 255, 0.9);
    }}
    .header h1 {{
        font-size: 20px;
        font-weight: 500;
        letter-spacing: 0.4px;
        margin-bottom: 2px;
    }}
    .header p {{
        color: rgba(203, 213, 225, 0.68);
        font-size: 12.5px;
        word-break: break-all;
    }}
    body.light .header p {{
        color: #475569;
    }}
    #status {{
        margin-top: 8px;
        color: #60a5fa;
        font-size: 13px;
    }}
    #status:empty {{
        display: none;
        margin-top: 0;
    }}
    .actions-bar {{
        display: flex;
        gap: 10px;
        justify-content: center;
        flex-wrap: wrap;
        margin-top: 9px;
    }}
    .upload-btn {{
        display: inline-block;
        padding: 8px 18px;
        border-radius: 18px;
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.28);
        cursor: pointer;
        font-size: 13.5px;
        font-weight: 500;
        text-decoration: none;
        box-shadow: 0 6px 18px rgba(59, 130, 246, 0.38), inset 0 1px 1px rgba(255, 255, 255, 0.35);
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
    .search-wrap {{
        position: relative;
        margin-bottom: 12px;
    }}
    .search-input {{
        width: 100%;
        padding: 13px 42px 13px 18px;
        border-radius: 14px;
        background: rgba(24, 30, 48, 0.74);
        border: 1px solid rgba(255, 255, 255, 0.14);
        backdrop-filter: blur(12px);
        color: #f8fafc;
        font-size: 15px;
        outline: none;
        transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.3s ease;
    }}
    .search-input:focus {{
        border-color: rgba(96, 165, 250, 0.75);
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.20);
    }}
    body.light .search-input {{
        background: rgba(255, 255, 255, 0.90);
        border-color: rgba(15, 23, 42, 0.12);
        color: #0f172a;
    }}
    .search-clear-btn {{
        position: absolute;
        right: 12px;
        top: 50%;
        transform: translateY(-50%);
        background: none;
        border: none;
        color: rgba(203, 213, 225, 0.7);
        font-size: 18px;
        cursor: pointer;
        display: none;
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
        cursor: pointer;
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
        cursor: pointer;
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
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }}
    body.light .file-meta {{
        color: #64748b;
    }}
    .hash-pill {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 1px 7px;
        border-radius: 8px;
        background: rgba(59, 130, 246, 0.14);
        border: 1px solid rgba(96, 165, 250, 0.26);
        color: #93c5fd;
        font-size: 11px;
        font-family: monospace;
        cursor: pointer;
        user-select: none;
        transition: background 0.2s ease, color 0.2s ease;
    }}
    .hash-pill:hover {{
        background: rgba(59, 130, 246, 0.28);
        color: #ffffff;
    }}
    body.light .hash-pill {{
        background: rgba(37, 99, 235, 0.10);
        border-color: rgba(37, 99, 235, 0.25);
        color: #1d4ed8;
    }}
    .item-actions {{
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
    }}
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
        appearance: none;
        -webkit-appearance: none;
        -moz-appearance: none;
        width: 20px;
        height: 20px;
        border-radius: 6px;
        border: 1.5px solid rgba(148, 163, 184, 0.36);
        background: rgba(15, 23, 42, 0.68);
        box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.38);
        cursor: pointer;
        margin-right: 10px;
        flex-shrink: 0;
        position: relative;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        vertical-align: middle;
        outline: none;
        transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1);
    }}
    .checkbox:hover {{
        border-color: rgba(96, 165, 250, 0.72);
        background: rgba(30, 41, 59, 0.85);
    }}
    .checkbox:active {{
        transform: scale(0.92);
    }}
    body.light .checkbox {{
        background: rgba(241, 245, 249, 0.92);
        border-color: rgba(100, 116, 139, 0.38);
        box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.06);
    }}
    body.light .checkbox:hover {{
        border-color: rgba(37, 99, 235, 0.65);
        background: #ffffff;
    }}
    .checkbox:checked,
    body.light .checkbox:checked {{
        background: linear-gradient(135deg, #3b82f6 0%, #20c997 100%);
        border-color: rgba(147, 197, 253, 0.65);
        box-shadow: 0 3px 10px rgba(59, 130, 246, 0.42), inset 0 1px 1px rgba(255, 255, 255, 0.35);
    }}
    .checkbox::after {{
        content: "";
        width: 5px;
        height: 9px;
        border: solid #ffffff;
        border-width: 0 2.2px 2.2px 0;
        border-radius: 1px;
        transform: rotate(45deg) scale(0);
        margin-top: -2px;
        transition: transform 0.18s cubic-bezier(0.34, 1.56, 0.64, 1);
    }}
    .checkbox:checked::after {{
        transform: rotate(45deg) scale(1);
    }}
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
    .pin-card {{
        max-width: 390px;
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
    .pin-input-wrap {{
        position: relative;
        width: 100%;
        margin: 18px 0 14px;
    }}
    .pin-input.masked {{
        -webkit-text-security: disc;
        text-security: disc;
    }}
    .pin-input {{
        width: 100%;
        padding: 14px 48px;
        margin: 0;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.22);
        background: rgba(10, 14, 26, 0.7);
        color: #fff;
        font-size: 22px;
        letter-spacing: 6px;
        text-align: center;
        outline: none;
        transition: border-color 0.25s ease, box-shadow 0.25s ease;
    }}
    .pin-input:focus {{
        border-color: rgba(96, 165, 250, 0.75);
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.22);
    }}
    body.light .pin-input {{
        background: #f1f5f9;
        border-color: #cbd5e1;
        color: #0f172a;
    }}
    .pin-eye-btn {{
        position: absolute;
        right: 10px;
        top: 50%;
        transform: translateY(-50%);
        width: 34px;
        height: 34px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(30, 41, 59, 0.65);
        color: rgba(226, 232, 240, 0.82);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        padding: 0;
        outline: none;
        user-select: none;
        -webkit-user-select: none;
        transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease;
    }}
    .pin-eye-btn:hover {{
        background: rgba(59, 130, 246, 0.28);
        border-color: rgba(96, 165, 250, 0.5);
        color: #ffffff;
    }}
    .pin-eye-btn.active {{
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        border-color: rgba(147, 197, 253, 0.75);
        color: #ffffff;
        transform: translateY(-50%) scale(0.94);
        box-shadow: 0 0 12px rgba(59, 130, 246, 0.55);
    }}
    body.light .pin-eye-btn {{
        background: rgba(226, 232, 240, 0.88);
        border-color: rgba(15, 23, 42, 0.12);
        color: #475569;
    }}
    body.light .pin-eye-btn:hover {{
        background: rgba(37, 99, 235, 0.15);
        color: #1d4ed8;
    }}
    body.light .pin-eye-btn.active {{
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: #ffffff;
    }}
    .pin-eye-btn svg {{
        width: 18px;
        height: 18px;
        stroke: currentColor;
        stroke-width: 2;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        pointer-events: none;
    }}

    @media (max-width: 720px) {{
        body {{
            padding: 12px 12px 24px;
        }}
        .top-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 6px;
            flex-wrap: wrap;
            margin-bottom: 12px;
            position: relative;
            z-index: 30;
        }}
        .top-controls,
        .top-right-controls {{
            position: static;
            gap: 6px;
            flex-wrap: wrap;
        }}
        #parallaxPill {{
            display: none !important;
        }}
        .ctrl-pill {{
            padding: 6px 10px;
            font-size: 12px;
            gap: 6px;
        }}
        .switch {{
            width: 34px;
            height: 19px;
        }}
        .switch-slider:before {{
            width: 13px;
            height: 13px;
        }}
        .switch input:checked + .switch-slider:before {{
            transform: translateX(15px);
        }}
        .container {{
            margin: 0 auto 18px;
        }}
        .header {{
            padding: 12px 14px;
        }}
        .header h1 {{
            font-size: 19px;
        }}
        .search-input {{
            padding: 11px 38px 11px 14px;
            font-size: 14px;
        }}
        .toolbar {{
            padding: 11px 14px;
            font-size: 13px;
        }}
        .file-item {{
            padding: 12px 12px;
            gap: 10px;
        }}
        .file-link {{
            font-size: 15px;
        }}
        .download-btn {{
            width: 38px;
            height: 38px;
            border-radius: 12px;
        }}
        .download-btn svg {{
            width: 18px;
            height: 18px;
        }}
        .credit-badge {{
            position: static;
            display: block;
            width: fit-content;
            margin: 18px auto 4px;
            font-size: 11.5px;
        }}
    }}

    body.light {{
        background: linear-gradient(180deg, #bae6fd 0%, #e0f2fe 50%, #f0f9ff 100%) !important;
        color: #0f172a;
    }}
    body.wide-view .container {{
        max-width: 96vw;
    }}
    body.wide-view #mainFileList {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
    }}
    .file-item {{
        padding: 7px 12px !important;
        min-height: 44px;
    }}
    .file-link {{
        font-size: 14px !important;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }}
    .ftype-svg {{
        width: 22px;
        height: 22px;
        flex-shrink: 0;
    }}
    .breadcrumbs {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        margin: 6px 0 10px;
        font-size: 13px;
        color: #94a3b8;
    }}
    .crumb-link {{
        color: #60a5fa;
        text-decoration: none;
        padding: 3px 8px;
        border-radius: 8px;
        background: rgba(59, 130, 246, 0.12);
        font-weight: 600;
    }}
    body.light .crumb-link {{
        color: #0369a1;
        background: rgba(14, 165, 233, 0.15);
    }}
    .nav-tabs {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
    }}
    .nav-tab {{
        padding: 7px 14px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.14);
        background: rgba(15,23,42,0.55);
        color: #cbd5e1;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
    }}
    .nav-tab.active {{
        background: #3b82f6;
        color: #ffffff;
        border-color: #60a5fa;
    }}
    body.light .nav-tab {{
        background: rgba(255,255,255,0.75);
        color: #1e293b;
        border-color: rgba(15,23,42,0.12);
    }}
    body.light .nav-tab.active {{
        background: #0284c7;
        color: #ffffff;
    }}
    .fav-strip {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
    }}
    .fav-chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 12px;
        border-radius: 999px;
        background: rgba(250, 204, 21, 0.14);
        border: 1px solid rgba(250, 204, 21, 0.35);
        color: #fde047;
        text-decoration: none;
        font-size: 12.5px;
        font-weight: 600;
    }}
    body.light .fav-chip {{
        background: rgba(234, 179, 8, 0.18);
        color: #854d0e;
        border-color: rgba(202, 138, 4, 0.4);
    }}
    .upload-dest-hint {{
        font-size: 12.5px;
        color: #94a3b8;
        margin-top: 6px;
    }}
    body.light .upload-dest-hint {{ color: #334155; }}
    .toolbar-actions {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
    }}
    .mini-btn {{
        padding: 5px 10px;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.16);
        background: rgba(255,255,255,0.08);
        color: inherit;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
    }}
    body.light .mini-btn {{
        background: rgba(255,255,255,0.85);
        border-color: rgba(15,23,42,0.16);
    }}
    .role-badge {{
        display: inline-block;
        padding: 3px 9px;
        border-radius: 999px;
        font-size: 11.5px;
        font-weight: 700;
        margin-left: 8px;
        background: rgba(32, 201, 151, 0.16);
        color: #20c997;
    }}
    .role-badge.guest {{
        background: rgba(245, 158, 11, 0.18);
        color: #fbbf24;
    }}
    .gallery-date {{
        font-size: 14px;
        font-weight: 700;
        margin: 14px 0 8px;
        opacity: 0.9;
    }}
    .gallery-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 8px;
    }}
    .gallery-card {{
        position: relative;
        aspect-ratio: 1 / 1;
        border-radius: 12px;
        overflow: hidden;
        background: rgba(15,23,42,0.6);
        cursor: pointer;
        border: 1px solid rgba(255,255,255,0.1);
    }}
    .gallery-card img, .gallery-card video {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        transition: transform 0.25s ease;
    }}
    .gallery-card:hover img {{ transform: scale(1.06); }}
    .ctx-menu {{
        position: fixed;
        z-index: 9999;
        min-width: 200px;
        background: rgba(15, 23, 42, 0.95);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid rgba(255,255,255,0.16);
        border-radius: 14px;
        padding: 6px;
        box-shadow: 0 16px 40px rgba(0,0,0,0.45);
        display: none;
    }}
    body.light .ctx-menu {{
        background: rgba(255,255,255,0.96);
        border-color: rgba(15,23,42,0.14);
        color: #0f172a;
    }}
    .ctx-item {{
        display: block;
        width: 100%;
        text-align: left;
        padding: 8px 12px;
        border: none;
        background: transparent;
        color: inherit;
        font-size: 13.5px;
        border-radius: 8px;
        cursor: pointer;
    }}
    .ctx-item:hover {{ background: rgba(59,130,246,0.22); }}
    .ctx-item.danger {{ color: #f87171; }}
    .drop-overlay {{
        position: fixed;
        inset: 0;
        z-index: 9000;
        background: rgba(37, 99, 235, 0.26);
        backdrop-filter: blur(6px);
        border: 3px dashed #60a5fa;
        display: none;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        font-weight: 700;
        color: #ffffff;
        pointer-events: none;
    }}
    .drop-overlay.active {{ display: flex; }}
    .file-item.drop-hover {{
        outline: 2px dashed #3b82f6;
        background: rgba(59,130,246,0.18) !important;
    }}
    .marquee-box {{
        position: fixed;
        border: 1.5px solid #60a5fa;
        background: rgba(59,130,246,0.18);
        pointer-events: none;
        z-index: 8000;
        display: none;
    }}
    .challenge-box {{
        margin: 16px 0;
        padding: 16px;
        border-radius: 16px;
        background: rgba(59,130,246,0.12);
        border: 1px solid rgba(96,165,250,0.3);
        text-align: center;
    }}
    .challenge-number {{
        font-size: 46px;
        font-weight: 800;
        letter-spacing: 4px;
        color: #60a5fa;
        margin: 6px 0;
    }}
    .qr-wrap {{
        margin: 12px auto 0;
        display: none;
        justify-content: center;
    }}
    .qr-wrap.visible {{ display: flex; }}
    @media (max-width: 720px) {{
        body.wide-view #mainFileList {{
            grid-template-columns: 1fr;
        }}
    }}

    """
    return base_css + get_player_css()


def get_download_svg():
    return (
        '<svg viewBox="0 0 24 24">'
        '<path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 19h14"/>'
        '</svg>'
    )


def get_star_script():
    return r"""
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

        const clouds = [];
        for (let i = 0; i < 11; i++) {
            const depth = Math.random() * 0.7 + 0.3;
            clouds.push({
                x: Math.random() * (w + 300) - 150,
                y: Math.random() * h * 0.72 + 20,
                scale: (Math.random() * 0.7 + 0.65) * depth,
                speed: (Math.random() * 0.35 + 0.18) * depth,
                depth: depth,
                alpha: 0.45 + depth * 0.35
            });
        }
        function drawCloud(cx, cy, sc, alpha) {
            ctx.save();
            ctx.globalAlpha = alpha;
            ctx.fillStyle = "#ffffff";
            ctx.beginPath();
            ctx.arc(cx, cy, 26 * sc, 0, Math.PI * 2);
            ctx.arc(cx + 24 * sc, cy - 10 * sc, 32 * sc, 0, Math.PI * 2);
            ctx.arc(cx + 56 * sc, cy - 4 * sc, 27 * sc, 0, Math.PI * 2);
            ctx.arc(cx + 76 * sc, cy + 6 * sc, 20 * sc, 0, Math.PI * 2);
            ctx.arc(cx - 22 * sc, cy + 7 * sc, 19 * sc, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }

        function animate() {
            requestAnimationFrame(animate);
            if (document.body.classList.contains("light")) {
                ctx.clearRect(0, 0, w, h);
                if (parallaxEnabled) {
                    curX += (targetX - curX) * 0.06;
                    curY += (targetY - curY) * 0.06;
                } else {
                    curX *= 0.92;
                    curY *= 0.92;
                }
                for (let i = 0; i < clouds.length; i++) {
                    const c = clouds[i];
                    c.x += c.speed;
                    if (c.x > w + 160) c.x = -180;
                    const px = c.x + curX * c.depth * 1.5;
                    const py = c.y + curY * c.depth * 1.1;
                    drawCloud(px, py, c.scale, c.alpha);
                }
                return;
            }

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
    msg_hash_ok = json.dumps(tr("web_hash_ok", lang))
    msg_hash_err = json.dumps(tr("web_hash_err", lang))
    msg_eta = json.dumps(tr("web_eta", lang))
    msg_restore = json.dumps(tr("web_trash_restore", lang))
    msg_purge = json.dumps(tr("web_trash_purge", lang))
    sha_js = get_sha256_js()
    player_js = get_player_script(lang)
    search_pwa_js = get_search_and_pwa_script()
    return f"""
    {sha_js}
    {player_js}
    {search_pwa_js}

    function triggerUpload() {{
        const input = document.getElementById("up");
        if (input) {{
            input.value = "";
            input.click();
        }}
    }}

    function uploadSingleViaXhr(url, file, clientSha, onProgress) {{
        return new Promise(function(resolve, reject) {{
            const xhr = new XMLHttpRequest();
            xhr.open("POST", url, true);
            xhr.withCredentials = true;
            xhr.setRequestHeader("Content-Type", "application/octet-stream");
            xhr.setRequestHeader("X-File-Name", encodeURIComponent(file.name));
            if (clientSha) {{
                xhr.setRequestHeader("X-Content-SHA256", clientSha);
            }}
            xhr.upload.onprogress = function(e) {{
                if (e.lengthComputable && onProgress) {{
                    onProgress(e.loaded, e.total);
                }}
            }};
            xhr.onload = function() {{
                if (xhr.status >= 200 && xhr.status < 300) {{
                    resolve(xhr.responseText);
                }} else {{
                    reject(new Error("HTTP " + xhr.status + (xhr.statusText ? " (" + xhr.statusText + ")" : "")));
                }}
            }};
            xhr.onerror = function() {{
                reject(new Error("Network error"));
            }};
            xhr.send(file);
        }});
    }}

    async function uploadFiles(files) {{
        if (!files || files.length === 0) return;
        const st = document.getElementById("status");
        const dock = document.getElementById("uploadProgressDock");
        const dockName = document.getElementById("dockFileName");
        const dockPct = document.getElementById("dockPct");
        const dockFill = document.getElementById("dockBarFill");
        const dockSpeed = document.getElementById("dockSpeed");
        const dockEta = document.getElementById("dockEta");
        const cleanOrigin = window.location.protocol + "//" + window.location.host;
        const basePath = window.location.pathname || "/";
        let uploadedCount = 0;
        let verifiedCount = 0;

        if (dock) dock.classList.add("visible");

        for (let i = 0; i < files.length; i++) {{
            const file = files[i];
            const labelPrefix = "(" + (i + 1) + "/" + files.length + ") " + file.name;
            if (st) {{
                st.style.color = "#60a5fa";
                st.innerText = {msg_uploading} + " " + labelPrefix + "...";
            }}
            if (dockName) dockName.innerText = labelPrefix;
            if (dockPct) dockPct.innerText = "0%";
            if (dockFill) dockFill.style.width = "0%";
            if (dockSpeed) dockSpeed.innerText = "SHA-256...";
            if (dockEta) dockEta.innerText = "";

            let clientSha = "";
            try {{
                clientSha = await computeFileSha256(file);
            }} catch (e) {{}}

            const tStart = performance.now();
            try {{
                const targetUrl = cleanOrigin + basePath + "?upload=" + encodeURIComponent(file.name);
                await uploadSingleViaXhr(targetUrl, file, clientSha, function(loaded, total) {{
                    const pct = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
                    const elapsedSec = Math.max(0.05, (performance.now() - tStart) / 1000);
                    const bytesPerSec = loaded / elapsedSec;
                    const mbps = (bytesPerSec / (1024 * 1024)).toFixed(1) + " MB/s";
                    const remSec = bytesPerSec > 0 ? (total - loaded) / bytesPerSec : 0;
                    if (dockPct) dockPct.innerText = pct + "%";
                    if (dockFill) dockFill.style.width = pct + "%";
                    if (dockSpeed) dockSpeed.innerText = mbps + (clientSha ? " • " + {msg_hash_ok} : "");
                    if (dockEta) dockEta.innerText = {msg_eta} + ": " + formatClock(remSec);
                }});
                uploadedCount++;
                if (clientSha) verifiedCount++;
            }} catch (err) {{
                if (st) {{
                    st.style.color = "#ff453a";
                    st.innerText = {msg_err} + file.name + ": " + err.message;
                }}
                if (dockSpeed) dockSpeed.innerText = {msg_hash_err};
                return;
            }}
        }}
        if (st && uploadedCount > 0) {{
            st.style.color = "#20c997";
            const hashNote = verifiedCount === uploadedCount ? " (" + {msg_hash_ok} + ")" : "";
            st.innerText = {msg_done} + uploadedCount + hashNote;
        }}
        window.location.href = cleanOrigin + basePath + (window.location.search || "");
    }}


    function toggleWideView() {{
        document.body.classList.toggle("wide-view");
        try {{
            localStorage.setItem("airshare_wide", document.body.classList.contains("wide-view") ? "1" : "0");
        }} catch (e) {{}}
    }}

    function invertSelection() {{
        const boxes = document.querySelectorAll('input[name="files"]');
        for (let i = 0; i < boxes.length; i++) {{
            if (boxes[i].closest("li") && boxes[i].closest("li").style.display !== "none") {{
                boxes[i].checked = !boxes[i].checked;
            }}
        }}
    }}

    function clearSelection() {{
        const boxes = document.querySelectorAll('input[name="files"]');
        for (let i = 0; i < boxes.length; i++) boxes[i].checked = false;
        const master = document.getElementById("masterSelectAll");
        if (master) master.checked = false;
    }}

    async function runServerOp(op, payload) {{
        const res = await fetch("?op=" + encodeURIComponent(op), {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            credentials: "same-origin",
            body: JSON.stringify(payload || {{}})
        }});
        if (!res.ok) {{
            const txt = await res.text();
            alert("Error (" + res.status + "): " + txt);
            return false;
        }}
        window.location.reload();
        return true;
    }}

    let _ctxTarget = null;
    function hideCtxMenu() {{
        const m = document.getElementById("ctxMenu");
        if (m) m.style.display = "none";
    }}

    function openCtxMenu(ev, el) {{
        ev.preventDefault();
        const m = document.getElementById("ctxMenu");
        if (!m || !el) return;
        _ctxTarget = {{
            rel: el.getAttribute("data-rel") || "",
            name: el.getAttribute("data-orig") || "",
            quoted: el.getAttribute("data-quoted") || "",
            isDir: el.getAttribute("data-dir") === "1",
            size: el.getAttribute("data-size") || "—"
        }};
        const isTrusted = document.body.getAttribute("data-trusted") === "1";
        m.querySelectorAll(".trusted-only").forEach(function(b) {{
            b.style.display = isTrusted ? "block" : "none";
        }});
        const x = Math.min(ev.clientX, window.innerWidth - 215);
        const y = Math.min(ev.clientY, window.innerHeight - 280);
        m.style.left = Math.max(8, x) + "px";
        m.style.top = Math.max(8, y) + "px";
        m.style.display = "block";
    }}

    async function ctxAction(act) {{
        hideCtxMenu();
        if (!_ctxTarget) return;
        const t = _ctxTarget;
        if (act === "open") {{
            window.location.href = t.isDir ? (t.quoted + "/") : t.quoted;
        }} else if (act === "download") {{
            window.location.href = t.isDir ? ("?zip=" + t.quoted) : ("?download=" + t.quoted);
        }} else if (act === "rename") {{
            const nn = prompt("New name:", t.name);
            if (nn && nn !== t.name) await runServerOp("rename", {{ path: t.rel, new_name: nn }});
        }} else if (act === "move" || act === "copy") {{
            const dest = prompt("Target folder (relative path, empty = root):", "");
            if (dest !== null) await runServerOp(act, {{ paths: [t.rel], dest_dir: dest }});
        }} else if (act === "fav") {{
            await runServerOp("fav", {{ rel_path: t.rel }});
        }} else if (act === "hide") {{
            await runServerOp("hide", {{ rel_path: t.rel }});
        }} else if (act === "trash") {{
            if (confirm("Move to Trash (30 days)? " + t.name)) {{
                await runServerOp("delete", {{ paths: [t.rel] }});
            }}
        }} else if (act === "props") {{
            const modal = document.getElementById("propsModal");
            const body = document.getElementById("propsBody");
            if (modal && body) {{
                body.innerText = "Name: " + t.name + " | Path: /" + t.rel + " | Size: " + t.size + (t.isDir ? "" : " | SHA-256: ...");
                modal.style.display = "flex";
                if (!t.isDir) {{
                    try {{
                        const res = await fetch("?hash=" + encodeURIComponent(t.rel), {{ credentials: "same-origin" }});
                        if (res.ok) {{
                            const data = await res.json();
                            if (data && data.sha256) {{
                                body.innerText = "Name: " + t.name + " | Path: /" + t.rel + " | Size: " + t.size + " | SHA-256: " + data.sha256;
                                copyTextFallback(data.sha256);
                            }}
                        }}
                    }} catch (e) {{}}
                }}
            }}
        }}
    }}

    async function createNewFolder() {{
        const name = prompt("Folder name:");
        if (!name) return;
        const curDir = decodeURIComponent(window.location.pathname || "/").replace(/^[/]+|[/]+$/g, "");
        await runServerOp("mkdir", {{ dir: curDir, name: name }});
    }}

    async function switchTab(tabName) {{
        document.querySelectorAll(".nav-tab").forEach(function(b) {{
            b.classList.toggle("active", b.getAttribute("data-tab") === tabName);
        }});
        const filesView = document.getElementById("filesTabPanel");
        const dynView = document.getElementById("dynamicTabPanel");
        if (!filesView || !dynView) return;
        if (tabName === "files") {{
            filesView.style.display = "block";
            dynView.style.display = "none";
            dynView.innerHTML = "";
            return;
        }}
        filesView.style.display = "none";
        dynView.style.display = "block";
        dynView.innerHTML = "<p>Loading...</p>";
        try {{
            const res = await fetch("?" + tabName + "=1&ajax=1", {{ credentials: "same-origin" }});
            const data = await res.json();
            dynView.innerHTML = "";
            if (tabName === "gallery") {{
                const groups = data.groups || [];
                if (!groups.length) {{ dynView.innerHTML = "<p>Empty</p>"; return; }}
                groups.forEach(function(g) {{
                    const h = document.createElement("div");
                    h.className = "gallery-date";
                    h.textContent = g.date;
                    dynView.appendChild(h);
                    const grid = document.createElement("div");
                    grid.className = "gallery-grid";
                    g.items.forEach(function(it) {{
                        const card = document.createElement("div");
                        card.className = "gallery-card";
                        const href = "/" + String(it.rel_path).split("/").map(encodeURIComponent).join("/");
                        if (it.kind === "image") {{
                            const img = document.createElement("img");
                            img.src = href + "?thumb=1";
                            img.loading = "lazy";
                            card.appendChild(img);
                        }} else {{
                            const vid = document.createElement("video");
                            vid.src = href + "?thumb=1#t=0.5";
                            vid.muted = true;
                            vid.preload = "metadata";
                            card.appendChild(vid);
                        }}
                        card.addEventListener("click", function() {{
                            openMediaPlayer(href, it.name, it.kind);
                        }});
                        grid.appendChild(card);
                    }});
                    dynView.appendChild(grid);
                }});
            }} else if (tabName === "recent") {{
                const items = data.results || [];
                const ul = document.createElement("ul");
                ul.className = "file-list";
                items.forEach(function(it) {{
                    const li = document.createElement("li");
                    li.className = "file-item";
                    const href = "/" + String(it.rel_path).split("/").map(encodeURIComponent).join("/");
                    const a = document.createElement("a");
                    a.className = "file-link";
                    a.href = href;
                    a.textContent = it.name;
                    if (it.kind === "image" || it.kind === "video") {{
                        a.addEventListener("click", function(e) {{ e.preventDefault(); openMediaPlayer(href, it.name, it.kind); }});
                    }}
                    const meta = document.createElement("span");
                    meta.style.fontSize = "12px";
                    meta.style.opacity = "0.7";
                    meta.textContent = it.rel_path + " • " + it.size_str;
                    li.appendChild(a);
                    li.appendChild(meta);
                    ul.appendChild(li);
                }});
                dynView.appendChild(ul);
            }} else if (tabName === "trash") {{
                const items = data.items || [];
                if (!items.length) {{ dynView.innerHTML = "<p>Trash is empty</p>"; return; }}
                const ul = document.createElement("ul");
                ul.className = "file-list";
                items.forEach(function(it) {{
                    const li = document.createElement("li");
                    li.className = "file-item";
                    const info = document.createElement("div");
                    info.innerText = it.name + " (" + it.orig_rel + ", " + it.days_left + "d left)";
                    const btns = document.createElement("div");
                    btns.className = "toolbar-actions";
                    const rBtn = document.createElement("button");
                    rBtn.type = "button";
                    rBtn.className = "mini-btn";
                    rBtn.textContent = {msg_restore};
                    rBtn.onclick = function() {{ runServerOp("restore", {{ ids: [it.id] }}); }};
                    const pBtn = document.createElement("button");
                    pBtn.type = "button";
                    pBtn.className = "mini-btn";
                    pBtn.style.color = "#f87171";
                    pBtn.textContent = {msg_purge};
                    pBtn.onclick = function() {{ runServerOp("purge", {{ ids: [it.id] }}); }};
                    btns.appendChild(rBtn);
                    btns.appendChild(pBtn);
                    li.appendChild(info);
                    li.appendChild(btns);
                    ul.appendChild(li);
                }});
                dynView.appendChild(ul);
            }}
        }} catch (e) {{
            dynView.innerHTML = "<p>Failed to load</p>";
        }}
    }}

    window.addEventListener("DOMContentLoaded", function() {{
        try {{
            if (localStorage.getItem("airshare_wide") === "1") document.body.classList.add("wide-view");
        }} catch (e) {{}}

        document.addEventListener("click", hideCtxMenu);

        // Drag & Drop файлов в окно или на папку
        const overlay = document.getElementById("dropOverlay");
        let dragCounter = 0;
        if (document.body.getAttribute("data-trusted") === "1") {{
            window.addEventListener("dragenter", function(e) {{
                if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) {{
                    dragCounter++;
                    if (overlay) overlay.classList.add("active");
                }}
            }});
            window.addEventListener("dragleave", function() {{
                dragCounter = Math.max(0, dragCounter - 1);
                if (dragCounter === 0 && overlay) overlay.classList.remove("active");
            }});
            window.addEventListener("dragover", function(e) {{ e.preventDefault(); }});
            window.addEventListener("drop", function(e) {{
                e.preventDefault();
                dragCounter = 0;
                if (overlay) overlay.classList.remove("active");
                if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {{
                    uploadFiles(e.dataTransfer.files);
                }}
            }});
        }}

        // Выделение рамкой (marquee) на ПК и свайпом на телефоне
        const listEl = document.getElementById("mainFileList");
        const mBox = document.getElementById("marqueeBox");
        if (listEl && mBox) {{
            let dragging = false, sx = 0, sy = 0;
            listEl.addEventListener("mousedown", function(e) {{
                if (e.button !== 0 || e.target.closest("a,button,input,label")) return;
                dragging = true;
                sx = e.clientX;
                sy = e.clientY;
                mBox.style.left = sx + "px";
                mBox.style.top = sy + "px";
                mBox.style.width = "0px";
                mBox.style.height = "0px";
                mBox.style.display = "block";
            }});
            window.addEventListener("mousemove", function(e) {{
                if (!dragging) return;
                const x1 = Math.min(sx, e.clientX), y1 = Math.min(sy, e.clientY);
                const x2 = Math.max(sx, e.clientX), y2 = Math.max(sy, e.clientY);
                mBox.style.left = x1 + "px";
                mBox.style.top = y1 + "px";
                mBox.style.width = (x2 - x1) + "px";
                mBox.style.height = (y2 - y1) + "px";
                listEl.querySelectorAll("li.file-item").forEach(function(li) {{
                    const r = li.getBoundingClientRect();
                    const hit = !(r.right < x1 || r.left > x2 || r.bottom < y1 || r.top > y2);
                    const cb = li.querySelector('input[name="files"]');
                    if (cb && hit) cb.checked = true;
                }});
            }});
            window.addEventListener("mouseup", function() {{
                if (dragging) {{
                    dragging = false;
                    mBox.style.display = "none";
                }}
            }});
        }}

        // Автообновление списка при изменениях на телефоне (SSE)
        if (window.EventSource) {{
            try {{
                const es = new EventSource("/events");
                es.addEventListener("reload", function() {{
                    window.location.reload();
                }});
            }} catch (e) {{}}
        }}
    }});

    function toggleSelectAll(masterCheckbox) {{
        const boxes = document.querySelectorAll('input[name="files"]');
        for (let i = 0; i < boxes.length; i++) {{
            if (boxes[i].closest("li").style.display !== "none") {{
                boxes[i].checked = masterCheckbox.checked;
            }}
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
    return r"""
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
    let _vidThumbQueue = [];
    let _activeVidThumbs = 0;

    function _pumpVideoThumbQueue() {
        const modal = document.getElementById("mediaModal");
        if (modal && modal.classList.contains("open")) return;
        if (!document.body.classList.contains("show-previews")) return;
        while (_activeVidThumbs < 2 && _vidThumbQueue.length > 0) {
            const vEl = _vidThumbQueue.shift();
            if (!vEl || vEl.getAttribute("src") || !vEl.dataset.src) continue;
            _activeVidThumbs++;
            let finished = false;
            let timerId = null;
            const done = function() {
                if (finished) return;
                finished = true;
                if (timerId) clearTimeout(timerId);
                vEl.removeEventListener("loadeddata", done);
                vEl.removeEventListener("error", done);
                _activeVidThumbs = Math.max(0, _activeVidThumbs - 1);
                _pumpVideoThumbQueue();
            };
            vEl.addEventListener("loadeddata", done);
            vEl.addEventListener("error", done);
            timerId = setTimeout(done, 1800);
            vEl.setAttribute("src", vEl.dataset.src);
        }
    }

    function _enqueueThumbElement(el) {
        if (!el || !el.dataset.src || el.getAttribute("src")) return;
        if (el.tagName === "VIDEO") {
            if (_vidThumbQueue.indexOf(el) === -1) {
                _vidThumbQueue.push(el);
            }
            _pumpVideoThumbQueue();
        } else {
            el.setAttribute("src", el.dataset.src);
        }
    }

    function _activateVisibleThumbs() {
        const mediaEls = document.querySelectorAll(".file-thumb[data-src]");
        if ("IntersectionObserver" in window) {
            if (!_thumbObserver) {
                _thumbObserver = new IntersectionObserver(function(entries) {
                    entries.forEach(function(entry) {
                        if (entry.isIntersecting && document.body.classList.contains("show-previews")) {
                            const el = entry.target;
                            _enqueueThumbElement(el);
                            _thumbObserver.unobserve(el);
                        }
                    });
                }, { rootMargin: "120px 0px" });
            }
            mediaEls.forEach(function(el) {
                if (!el.getAttribute("src")) {
                    _thumbObserver.observe(el);
                }
            });
        } else {
            mediaEls.forEach(function(el) {
                _enqueueThumbElement(el);
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

    function toggleLangMenu(event) {
        if (event) event.stopPropagation();
        const wrap = document.getElementById("langMenuWrap");
        if (wrap) {
            wrap.classList.toggle("open");
        }
    }

    function setWebLanguage(code) {
        try {
            localStorage.setItem("airshare_lang", code);
        } catch (e) {}
        document.cookie = "airshare_lang=" + encodeURIComponent(code) + "; path=/; max-age=31536000; SameSite=Lax";
        const url = new URL(window.location.href);
        url.searchParams.set("lang", code);
        window.location.href = url.toString();
    }

    (function initLangMenuAndPinEye() {
        document.addEventListener("click", function(e) {
            const wrap = document.getElementById("langMenuWrap");
            if (wrap && !wrap.contains(e.target)) {
                wrap.classList.remove("open");
            }
        });
        document.addEventListener("keydown", function(e) {
            if (e.key === "Escape") {
                const wrap = document.getElementById("langMenuWrap");
                if (wrap) wrap.classList.remove("open");
            }
        });

        const pinInput = document.getElementById("pinInput");
        const eyeBtn = document.getElementById("pinEyeBtn");
        const eyeClosed = document.getElementById("eyeClosedIcon");
        const eyeOpen = document.getElementById("eyeOpenIcon");
        if (pinInput && eyeBtn) {
            function showPin(e) {
                if (e && e.type === "mousedown" && e.button !== 0) return;
                if (e && e.cancelable) e.preventDefault();
                pinInput.classList.remove("masked");
                eyeBtn.classList.add("active");
                if (eyeClosed) eyeClosed.style.display = "none";
                if (eyeOpen) eyeOpen.style.display = "block";
            }
            function hidePin() {
                pinInput.classList.add("masked");
                eyeBtn.classList.remove("active");
                if (eyeClosed) eyeClosed.style.display = "block";
                if (eyeOpen) eyeOpen.style.display = "none";
            }
            eyeBtn.addEventListener("mousedown", showPin);
            eyeBtn.addEventListener("mouseup", hidePin);
            eyeBtn.addEventListener("mouseleave", hidePin);
            eyeBtn.addEventListener("touchstart", showPin, { passive: false });
            eyeBtn.addEventListener("touchend", hidePin);
            eyeBtn.addEventListener("touchcancel", hidePin);
            eyeBtn.addEventListener("blur", hidePin);
            window.addEventListener("mouseup", hidePin);
            window.addEventListener("blur", hidePin);
        }
    })();

    async function submitPinForm(e) {
        if (!window.fetch) return true;
        e.preventDefault();
        const form = e.target;
        const pinVal = (document.getElementById("pinInput") || {}).value || "";
        const nextInput = form.querySelector('input[name="next"]');
        const nextVal = (nextInput && nextInput.value) ? nextInput.value : "/";
        try {
            const body = "pin=" + encodeURIComponent(pinVal) + "&next=" + encodeURIComponent(nextVal);
            const res = await fetch("/login", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: body,
                credentials: "same-origin",
                redirect: "follow"
            });
            if (res.ok || res.redirected) {
                window.location.replace(nextVal);
                return false;
            }
            const htmlTxt = await res.text();
            document.open();
            document.write(htmlTxt);
            document.close();
        } catch (err) {
            form.submit();
        }
        return false;
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


def _get_lang_selector_html(lang="en"):
    cur_lang = (lang or "en").lower()
    lang_title = html.escape(tr("web_lang_title", cur_lang))
    items_html = []
    for code, native_name in SUPPORTED_LANGUAGES:
        active_cls = " active" if code == cur_lang else ""
        flag_svg = get_flag_svg(code)
        safe_name = html.escape(native_name)
        items_html.append(
            f'<button type="button" class="lang-item{active_cls}" onclick="setWebLanguage(\'{code}\')">'
            f'<span class="lang-item-left">{flag_svg}<span>{safe_name}</span></span>'
            '<span class="lang-radio"></span>'
            '</button>'
        )
    return (
        '<div class="lang-menu-wrap" id="langMenuWrap">'
        f'<button type="button" class="ctrl-pill lang-btn" id="langGlobeBtn" onclick="toggleLangMenu(event)" title="{lang_title}">'
        f'{get_globe_svg()}'
        f'<span class="lang-code-badge">{html.escape(cur_lang.upper())}</span>'
        '</button>'
        '<div class="lang-dropdown" id="langDropdown">'
        f'<div class="lang-dropdown-title">{lang_title}</div>'
        + "".join(items_html)
        + '</div></div>'
    )


def get_top_controls_html(theme="dark", lang="en", show_preview_toggle=False):
    is_dark_checked = "checked" if theme != "light" else ""
    cur_lang = (lang or "en").lower()
    theme_tip = html.escape(tr("web_theme_tip", cur_lang))
    parallax_tip = html.escape(tr("web_parallax_tip", cur_lang))
    left_html = (
        '<div class="top-controls">'
        f'<label class="ctrl-pill" title="{theme_tip}">'
        '<span>☀️ / 🌙</span>'
        '<span class="switch">'
        f'<input type="checkbox" id="themeToggle" {is_dark_checked} onchange="onThemeSwitchChange(this)">'
        '<span class="switch-slider"></span>'
        '</span>'
        '</label>'
        f'<label class="ctrl-pill" id="parallaxPill" title="{parallax_tip}">'
        '<span>✨ Parallax 3D</span>'
        '<span class="switch">'
        '<input type="checkbox" id="parallaxToggle" checked>'
        '<span class="switch-slider"></span>'
        '</span>'
        '</label>'
        '</div>'
    )
    preview_pill = ""
    if show_preview_toggle:
        preview_label = html.escape(tr("web_preview", cur_lang))
        preview_pill = (
            f'<label class="ctrl-pill" title="{preview_label}">'
            f'<span>{preview_label}</span>'
            '<span class="switch">'
            '<input type="checkbox" id="previewToggle" onchange="onPreviewSwitchChange(this)">'
            '<span class="switch-slider"></span>'
            '</span>'
            '</label>'
        )
    right_html = (
        '<div class="top-right-controls">'
        f'{preview_pill}'
        f'{_get_lang_selector_html(cur_lang)}'
        '</div>'
    )
    return '<div class="top-bar">' + left_html + right_html + '</div>'


def get_pin_login_page(theme="dark", lang="en", error_msg="", next_path="/"):
    title_txt = html.escape(tr("web_auth_prompt_title", lang))
    sub_txt = html.escape(tr("web_auth_prompt_sub", lang))
    connect_txt = html.escape(tr("web_auth_connect_btn", lang))
    qr_btn_txt = html.escape(tr("web_auth_qr_btn", lang))
    waiting_txt = html.escape(tr("web_auth_waiting", lang))
    denied_txt = html.escape(tr("web_auth_denied", lang))
    hint_txt = html.escape(tr("pin_hint", lang))
    show_pin_txt = html.escape(tr("web_show_pin", lang))
    btn_txt = html.escape(tr("connect", lang))
    safe_next = html.escape(next_path or "/", quote=True)
    err_html = f'<p style="color:#ff453a;margin-top:10px;font-size:14px;">{html.escape(error_msg)}</p>' if error_msg else ""
    eye_closed_svg = (
        '<svg id="eyeClosedIcon" viewBox="0 0 24 24">'
        '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94'
        'M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>'
        '<line x1="1" y1="1" x2="23" y2="23"/>'
        '</svg>'
    )
    eye_open_svg = (
        '<svg id="eyeOpenIcon" viewBox="0 0 24 24" style="display:none;">'
        '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>'
        '<circle cx="12" cy="12" r="3"/>'
        '</svg>'
    )
    challenge_js = f"""
    <script>
    let _cid = "";
    let _pollTimer = null;
    async function startChallengeLogin() {{
        const box = document.getElementById("challengeBox");
        const numEl = document.getElementById("challengeTarget");
        const stEl = document.getElementById("challengeStatus");
        const qrEl = document.getElementById("qrWrap");
        if (stEl) stEl.textContent = {json.dumps(waiting_txt)};
        try {{
            const res = await fetch("/auth/start", {{ method: "POST", credentials: "same-origin" }});
            const data = await res.json();
            _cid = data.cid || "";
            if (numEl) numEl.textContent = data.target || "--";
            if (qrEl && data.qr_svg) qrEl.innerHTML = data.qr_svg;
            if (box) box.style.display = "block";
            if (_pollTimer) clearInterval(_pollTimer);
            _pollTimer = setInterval(pollChallengeStatus, 1200);
        }} catch (e) {{}}
    }}
    function toggleQrLogin() {{
        const qrEl = document.getElementById("qrWrap");
        if (!qrEl) return;
        if (!_cid) {{
            startChallengeLogin().then(function() {{ qrEl.classList.add("visible"); }});
            return;
        }}
        qrEl.classList.toggle("visible");
    }}
    async function pollChallengeStatus() {{
        if (!_cid) return;
        try {{
            const res = await fetch("/auth/status?cid=" + encodeURIComponent(_cid), {{ credentials: "same-origin" }});
            const data = await res.json();
            if (data.status === "approved") {{
                clearInterval(_pollTimer);
                const claim = await fetch("/auth/claim", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    credentials: "same-origin",
                    body: JSON.stringify({{ cid: _cid }})
                }});
                if (claim.ok) {{
                    window.location.replace({json.dumps(next_path or "/")});
                }}
            }} else if (data.status === "denied" || data.status === "expired") {{
                clearInterval(_pollTimer);
                const stEl = document.getElementById("challengeStatus");
                if (stEl) stEl.textContent = {json.dumps(denied_txt)};
            }}
        }} catch (e) {{}}
    }}
    </script>
    """
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>AirShare PC</title>'
        f'<style>{get_css(theme)}</style>'
        f'</head><body class="{theme}">'
        '<canvas id="skyCanvas"></canvas>'
        f'{get_top_controls_html(theme, lang=lang, show_preview_toggle=False)}'
        '<div class="container">'
        '<div class="pin-card">'
        '<h1 style="font-size:30px;margin-bottom:8px;">AirShare PC</h1>'
        f'<p style="opacity:0.8;font-size:14px;">{title_txt}</p>'
        f'<p style="opacity:0.68;font-size:12.5px;margin-bottom:14px;">{sub_txt}</p>'
        f'<button type="button" id="connectChallengeBtn" class="upload-btn" style="width:100%;margin-bottom:10px;" onclick="startChallengeLogin()">{connect_txt}</button>'
        '<div id="challengeBox" class="challenge-box" style="display:none;">'
        '<div id="challengeTarget" class="challenge-number">--</div>'
        f'<div id="challengeStatus" style="font-size:13px;opacity:0.8;">{waiting_txt}</div>'
        '<div id="qrWrap" class="qr-wrap"></div>'
        '</div>'
        f'<button type="button" class="mini-btn" style="width:100%;padding:9px 12px;margin-bottom:14px;" onclick="toggleQrLogin()">📷 {qr_btn_txt}</button>'
        '<details style="text-align:left;opacity:0.75;font-size:12px;">'
        '<summary style="cursor:pointer;margin-bottom:8px;">PIN</summary>'
        '<form method="POST" action="/login" autocomplete="off" onsubmit="return submitPinForm(event)">'
        f'<input type="hidden" name="next" value="{safe_next}">'
        '<div class="pin-input-wrap">'
        f'<input type="text" id="pinInput" name="pin" class="pin-input masked" inputmode="numeric" placeholder="••••••" title="{hint_txt}" autocomplete="off" data-lpignore="true" data-1p-ignore="true" required>'
        f'<button type="button" class="pin-eye-btn" id="pinEyeBtn" title="{show_pin_txt}" aria-label="{show_pin_txt}">'
        f'{eye_closed_svg}{eye_open_svg}'
        '</button>'
        '</div>'
        f'<button type="submit" class="upload-btn" style="width:100%;">{btn_txt}</button>'
        '</form></details>'
        f'{err_html}'
        '</div></div>'
        '<div class="credit-badge">Crafted by JackBrownUA • Powered by Gemini</div>'
        f'<script>{get_star_script()}</script>'
        f'<script>{get_theme_script()}</script>'
        f'{challenge_js}'
        '</body></html>'
    )

# Веб-интерфейс AirShare PC (v1.3.5): вёрстка страницы, звёздное небо с метеорами и 3D-параллаксом, тумблеры, выбор языка и отправка файлов через XMLHttpRequest

import html
import json
from i18n import SUPPORTED_LANGUAGES, tr
from player_ui import get_media_modal_html, get_player_css, get_player_script
from pwa_search import get_search_and_pwa_script
from security import get_sha256_js

__all__ = [
    "get_css",
    "get_download_svg",
    "get_media_modal_html",
    "get_pin_login_page",
    "get_star_script",
    "get_theme_script",
    "get_top_controls_html",
    "get_upload_script",
]


def get_flag_svg(code="en"):
    if code == "uk":
        return (
            '<svg class="lang-flag" viewBox="0 0 28 20">'
            '<rect width="28" height="10" y="0" fill="#005BBB"/>'
            '<rect width="28" height="10" y="10" fill="#FFD500"/>'
            '</svg>'
        )
    if code == "ru":
        return (
            '<svg class="lang-flag" viewBox="0 0 28 20">'
            '<rect width="28" height="6.67" y="0" fill="#F8FAFC"/>'
            '<rect width="28" height="6.67" y="6.67" fill="#0039A6"/>'
            '<rect width="28" height="6.67" y="13.33" fill="#D52B1E"/>'
            '</svg>'
        )
    if code == "lt":
        return (
            '<svg class="lang-flag" viewBox="0 0 28 20">'
            '<rect width="28" height="6.67" y="0" fill="#FDB913"/>'
            '<rect width="28" height="6.67" y="6.67" fill="#006A44"/>'
            '<rect width="28" height="6.67" y="13.33" fill="#C1272D"/>'
            '</svg>'
        )
    if code == "de":
        return (
            '<svg class="lang-flag" viewBox="0 0 28 20">'
            '<rect width="28" height="6.67" y="0" fill="#1A1D21"/>'
            '<rect width="28" height="6.67" y="6.67" fill="#DD0000"/>'
            '<rect width="28" height="6.67" y="13.33" fill="#FFCE00"/>'
            '</svg>'
        )
    if code == "es":
        return (
            '<svg class="lang-flag" viewBox="0 0 28 20">'
            '<rect width="28" height="5" y="0" fill="#AA151B"/>'
            '<rect width="28" height="10" y="5" fill="#F1BF00"/>'
            '<rect width="28" height="5" y="15" fill="#AA151B"/>'
            '</svg>'
        )
    return (
        '<svg class="lang-flag" viewBox="0 0 28 20">'
        '<rect width="28" height="20" fill="#0A2975"/>'
        '<path d="M0,0 L28,20 M28,0 L0,20" stroke="#F8FAFC" stroke-width="3.2"/>'
        '<rect width="28" height="5.6" y="7.2" fill="#F8FAFC"/>'
        '<rect width="5.6" height="20" x="11.2" fill="#F8FAFC"/>'
        '<rect width="28" height="3.2" y="8.4" fill="#D1192A"/>'
        '<rect width="3.2" height="20" x="12.4" fill="#D1192A"/>'
        '</svg>'
    )


def get_globe_svg():
    return (
        '<svg class="globe-svg" viewBox="0 0 24 24">'
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M3.6 9h16.8M3.6 15h16.8"/>'
        '<path d="M11.5 3a17 17 0 0 0 0 18M12.5 3a17 17 0 0 1 0 18"/>'
        '</svg>'
    )


def get_css(theme="dark"):
    scheme = "light" if theme == "light" else "dark"
    base_css = f"""
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
        body, .ctrl-pill, .switch-slider, .upload-btn, .download-btn, .thumb-box, .lang-dropdown {{
            transition: none !important;
        }}
    }}
    .top-controls {{
        position: fixed;
        top: 18px;
        left: 20px;
        z-index: 30;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }}
    .top-right-controls {{
        position: fixed;
        top: 18px;
        right: 20px;
        z-index: 30;
        display: flex;
        align-items: center;
        gap: 10px;
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
    .pwa-install-btn {{
        display: none;
        cursor: pointer;
        border-color: rgba(56, 217, 169, 0.45);
        font-family: inherit;
    }}
    .pwa-install-btn:hover {{
        border-color: rgba(56, 217, 169, 0.85);
        box-shadow: 0 8px 24px rgba(32, 201, 151, 0.35);
    }}
    .lang-menu-wrap {{
        position: relative;
        display: inline-flex;
    }}
    .lang-btn {{
        cursor: pointer;
        padding: 8px 13px;
        gap: 7px;
        font-family: inherit;
        outline: none;
    }}
    .lang-btn:hover {{
        border-color: rgba(96, 165, 250, 0.55);
        box-shadow: 0 8px 26px rgba(59, 130, 246, 0.28), inset 0 1px 1px rgba(255, 255, 255, 0.28);
    }}
    .globe-svg {{
        width: 19px;
        height: 19px;
        stroke: #60a5fa;
        stroke-width: 1.9;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        flex-shrink: 0;
        transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1), stroke 0.3s ease;
    }}
    body.light .globe-svg {{
        stroke: #2563eb;
    }}
    .lang-btn:hover .globe-svg,
    .lang-menu-wrap.open .globe-svg {{
        transform: rotate(18deg) scale(1.08);
    }}
    .lang-code-badge {{
        font-size: 12.5px;
        font-weight: 600;
        letter-spacing: 0.4px;
    }}
    .lang-dropdown {{
        position: absolute;
        top: calc(100% + 10px);
        right: 0;
        width: 235px;
        padding: 12px;
        border-radius: 22px;
        background: rgba(18, 24, 40, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.18);
        box-shadow: 0 18px 46px rgba(0, 0, 0, 0.62), inset 0 1px 1px rgba(255, 255, 255, 0.20);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        opacity: 0;
        visibility: hidden;
        transform: translateY(-8px) scale(0.96);
        transform-origin: top right;
        transition: opacity 0.22s ease, transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), visibility 0.22s ease;
        z-index: 50;
    }}
    body.light .lang-dropdown {{
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid rgba(15, 23, 42, 0.12);
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.16), inset 0 1px 1px rgba(255, 255, 255, 0.9);
    }}
    .lang-menu-wrap.open .lang-dropdown {{
        opacity: 1;
        visibility: visible;
        transform: translateY(0) scale(1);
    }}
    .lang-dropdown-title {{
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: rgba(203, 213, 225, 0.68);
        padding: 2px 8px 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 6px;
    }}
    body.light .lang-dropdown-title {{
        color: #64748b;
        border-bottom-color: rgba(15, 23, 42, 0.08);
    }}
    .lang-item {{
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 9px 11px;
        margin-bottom: 4px;
        border-radius: 13px;
        border: 1px solid transparent;
        background: transparent;
        color: #f1f5f9;
        font-family: inherit;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        text-align: left;
        transition: background 0.18s ease, border-color 0.18s ease, transform 0.15s ease;
    }}
    .lang-item:last-child {{
        margin-bottom: 0;
    }}
    .lang-item:hover {{
        background: rgba(255, 255, 255, 0.07);
    }}
    .lang-item.active {{
        background: rgba(32, 201, 151, 0.14);
        border-color: rgba(32, 201, 151, 0.48);
    }}
    body.light .lang-item {{
        color: #0f172a;
    }}
    body.light .lang-item:hover {{
        background: rgba(15, 23, 42, 0.05);
    }}
    body.light .lang-item.active {{
        background: rgba(18, 184, 134, 0.12);
        border-color: rgba(18, 184, 134, 0.45);
    }}
    .lang-item-left {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .lang-flag {{
        width: 24px;
        height: 17px;
        border-radius: 3.5px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
        flex-shrink: 0;
    }}
    .lang-radio {{
        width: 18px;
        height: 18px;
        border-radius: 50%;
        border: 1.6px solid rgba(148, 163, 184, 0.55);
        background: rgba(30, 41, 59, 0.65);
        box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.45);
        position: relative;
        flex-shrink: 0;
        transition: all 0.2s ease;
    }}
    body.light .lang-radio {{
        background: #e2e8f0;
        border-color: #94a3b8;
    }}
    .lang-item.active .lang-radio {{
        border-color: #20c997;
        background: radial-gradient(circle at 35% 35%, #63e6be, #12b886);
        box-shadow: 0 0 10px rgba(32, 201, 151, 0.55);
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
        margin-bottom: 26px;
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
        margin-bottom: 18px;
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
        width: 20px;
        height: 20px;
        cursor: pointer;
        margin-right: 8px;
        flex-shrink: 0;
        accent-color: #3b82f6;
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
    """
    return base_css + get_player_css()


def get_download_svg():
    return (
        '<svg viewBox="0 0 24 24">'
        '<path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 19h14"/>'
        '</svg>'
    )


def get_star_script():
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
    msg_hash_ok = json.dumps(tr("web_hash_ok", lang))
    msg_hash_err = json.dumps(tr("web_hash_err", lang))
    msg_eta = json.dumps(tr("web_eta", lang))
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
                    reject(new Error(xhr.responseText || ("HTTP " + xhr.status)));
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
            st.innerText = {msg_done} + uploadedCount + " (" + {msg_hash_ok} + ")";
        }}
        window.location.href = cleanOrigin + basePath;
    }}

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
                pinInput.type = "text";
                eyeBtn.classList.add("active");
                if (eyeClosed) eyeClosed.style.display = "none";
                if (eyeOpen) eyeOpen.style.display = "block";
            }
            function hidePin() {
                if (pinInput.type !== "password") {
                    pinInput.type = "password";
                }
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
            f'<span class="lang-radio"></span>'
            f'</button>'
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
    theme_tip = html.escape(tr("web_theme_tip", lang))
    parallax_tip = html.escape(tr("web_parallax_tip", lang))
    pwa_txt = html.escape(tr("web_install_pwa", lang))
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
        preview_label = html.escape(tr("web_preview", lang))
        preview_pill = (
            f'<button type="button" class="ctrl-pill pwa-install-btn" id="pwaInstallBtn" onclick="installPwaApp()">{pwa_txt}</button>'
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
        f'{_get_lang_selector_html(lang)}'
        '</div>'
    )
    return left_html + right_html


def get_pin_login_page(theme="dark", lang="en", error_msg="", next_path="/"):
    title_txt = html.escape(tr("web_auth_req", lang))
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
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<link rel="manifest" href="/manifest.webmanifest">'
        '<title>AirShare PC — PIN</title>'
        f'<style>{get_css(theme)}</style>'
        f'</head><body class="{theme}">'
        '<canvas id="skyCanvas"></canvas>'
        f'{get_top_controls_html(theme, lang=lang, show_preview_toggle=False)}'
        '<div class="container">'
        '<div class="pin-card">'
        '<h1 style="font-size:30px;margin-bottom:8px;">AirShare PC</h1>'
        f'<p style="opacity:0.75;font-size:14px;">{title_txt}</p>'
        '<form method="POST" action="/login">'
        f'<input type="hidden" name="next" value="{safe_next}">'
        '<div class="pin-input-wrap">'
        f'<input type="password" id="pinInput" name="pin" class="pin-input" placeholder="••••••" title="{hint_txt}" autocomplete="off" autofocus required>'
        f'<button type="button" class="pin-eye-btn" id="pinEyeBtn" title="{show_pin_txt}" aria-label="{show_pin_txt}">'
        f'{eye_closed_svg}{eye_open_svg}'
        '</button>'
        '</div>'
        f'<button type="submit" class="upload-btn" style="width:100%;">{btn_txt}</button>'
        '</form>'
        f'{err_html}'
        '</div></div>'
        '<div class="credit-badge">Crafted by JackBrownUA • Powered by Gemini</div>'
        f'<script>{get_star_script()}{get_theme_script()}</script>'
        '</body></html>'
    )

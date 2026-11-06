# Main application file - Pixel-perfect implementation of 1000250791.jpg and 1000250792.jpg
# Uses dp() density scaling, custom vector canvas icons, and full touch interactivity

import os
import math
import threading
from http.server import SimpleHTTPRequestHandler
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse, Triangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.animation import Animation

from config import SERVER_PORT, APP_NAME, APP_VERSION, STORAGE_PATH
from server import ReusableThreadingServer, AirShareHandler
from utils import (
    get_local_ip,
    get_device_info,
    get_storage_stats,
    request_android_full_storage,
    load_settings,
    save_settings,
    get_device_theme,
)


THEMES = {
    "dark": {
        "bg": (0.10, 0.11, 0.12, 1),
        "radar_bg": (0.20, 0.21, 0.23, 1),
        "card_bg": (0.15, 0.16, 0.18, 1),
        "card_border": (0.26, 0.28, 0.31, 0.85),
        "radar_ring": (0.55, 0.58, 0.62, 0.18),
        "drawer_bg": (0.18, 0.20, 0.22, 0.98),
        "drawer_card": (0.25, 0.27, 0.30, 0.95),
        "drawer_border": (0.36, 0.39, 0.43, 0.75),
        "overlay": (0.0, 0.0, 0.0, 0.62),
        "text": (0.96, 0.97, 0.98, 1),
        "subtext": (0.64, 0.67, 0.72, 1),
        "pill_bg": (0.24, 0.26, 0.29, 1),
        "pill_active": (0.30, 0.33, 0.38, 1),
        "amber": (0.86, 0.60, 0.22, 1),
        "blue": (0.45, 0.70, 0.95, 1),
        "green": (0.28, 0.82, 0.54, 1),
        "track": (0.24, 0.26, 0.29, 1),
    },
    "light": {
        "bg": (0.93, 0.94, 0.96, 1),
        "radar_bg": (0.86, 0.88, 0.91, 1),
        "card_bg": (0.99, 0.99, 1.0, 1),
        "card_border": (0.80, 0.82, 0.86, 1),
        "radar_ring": (0.35, 0.38, 0.44, 0.16),
        "drawer_bg": (0.96, 0.97, 0.98, 0.98),
        "drawer_card": (0.90, 0.92, 0.95, 1),
        "drawer_border": (0.76, 0.79, 0.84, 1),
        "overlay": (0.0, 0.0, 0.0, 0.38),
        "text": (0.11, 0.12, 0.14, 1),
        "subtext": (0.44, 0.47, 0.53, 1),
        "pill_bg": (0.84, 0.86, 0.90, 1),
        "pill_active": (0.74, 0.78, 0.84, 1),
        "amber": (0.84, 0.54, 0.14, 1),
        "blue": (0.18, 0.52, 0.88, 1),
        "green": (0.16, 0.68, 0.42, 1),
        "track": (0.82, 0.84, 0.88, 1),
    },
}


class DynamicAirShareHandler(AirShareHandler):
    """Subclass of AirShareHandler that supports switching the shared folder dynamically"""

    active_storage_path = STORAGE_PATH

    def __init__(self, *args, **kwargs):
        target = self.active_storage_path
        if not target or not os.path.isdir(target):
            target = STORAGE_PATH if os.path.isdir(STORAGE_PATH) else os.path.expanduser("~")
        self.real_storage = os.path.realpath(target)
        SimpleHTTPRequestHandler.__init__(self, *args, directory=self.real_storage, **kwargs)


class VectorIcon(Widget):
    """Pure decorative vector canvas icon that never blocks parent touch events"""

    def __init__(self, icon_type="pc", color=(0.95, 0.96, 0.98, 1), **kwargs):
        super().__init__(**kwargs)
        self.icon_type = icon_type
        self.icon_color = color
        self.bind(pos=self._redraw, size=self._redraw)

    def on_touch_down(self, touch):
        return False

    def on_touch_move(self, touch):
        return False

    def on_touch_up(self, touch):
        return False

    def set_color(self, color):
        self.icon_color = color
        self._redraw()

    def _redraw(self, *_args):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        s = min(self.width, self.height)
        if s <= 0:
            return
        lw = max(1.2, dp(1.5))

        with self.canvas:
            Color(*self.icon_color)

            if self.icon_type == "pc":
                w, h = s * 0.74, s * 0.50
                x0, y0 = cx - w / 2, cy - h * 0.25
                Line(rounded_rectangle=[x0, y0, w, h, dp(4)], width=dp(2.0))
                Line(points=[cx, y0, cx, y0 - s * 0.14], width=dp(2.0))
                Line(points=[cx - w * 0.28, y0 - s * 0.14, cx + w * 0.28, y0 - s * 0.14], width=dp(2.0))

            elif self.icon_type == "wifi":
                r2, r3 = s * 0.26, s * 0.40
                by = cy - s * 0.18
                Ellipse(pos=(cx - dp(1.8), by - dp(1.8)), size=(dp(3.6), dp(3.6)))
                Line(circle=(cx, by, r2, -42, 42), width=dp(1.4))
                Line(circle=(cx, by, r3, -45, 45), width=dp(1.4))

            elif self.icon_type == "gear":
                r_outer = s * 0.30
                r_inner = s * 0.13
                Line(circle=(cx, cy, r_inner), width=lw)
                Line(circle=(cx, cy, r_outer * 0.78), width=lw)
                for deg in range(0, 360, 45):
                    rad = math.radians(deg)
                    x1 = cx + math.cos(rad) * (r_outer * 0.75)
                    y1 = cy + math.sin(rad) * (r_outer * 0.75)
                    x2 = cx + math.cos(rad) * (r_outer * 1.05)
                    y2 = cy + math.sin(rad) * (r_outer * 1.05)
                    Line(points=[x1, y1, x2, y2], width=dp(1.8))

            elif self.icon_type == "copy":
                w, h = s * 0.36, s * 0.44
                Line(rounded_rectangle=[cx - w * 0.7, cy - h * 0.3, w, h, dp(2.5)], width=lw)
                Line(rounded_rectangle=[cx - w * 0.3, cy - h * 0.7, w, h, dp(2.5)], width=lw)

            elif self.icon_type == "download":
                top_y = cy + s * 0.28
                bot_y = cy - s * 0.10
                aw = s * 0.22
                Line(points=[cx, top_y, cx, bot_y], width=dp(2.0))
                Line(points=[cx - aw, bot_y + aw * 0.85, cx, bot_y, cx + aw, bot_y + aw * 0.85], width=dp(2.0))
                tray_y = cy - s * 0.26
                Line(points=[cx - s * 0.28, tray_y, cx + s * 0.28, tray_y], width=dp(2.0))

            elif self.icon_type == "gallery":
                cw, ch = s * 0.56, s * 0.42
                Color(0.38, 0.40, 0.44, 0.65)
                RoundedRectangle(pos=(cx - cw * 0.75, cy - ch * 0.45), size=(cw * 0.7, ch * 0.85), radius=[dp(5)])
                RoundedRectangle(pos=(cx + cw * 0.05, cy - ch * 0.45), size=(cw * 0.7, ch * 0.85), radius=[dp(5)])
                Color(0.75, 0.78, 0.82, 0.95)
                RoundedRectangle(pos=(cx - cw * 0.5, cy - ch * 0.5), size=(cw, ch), radius=[dp(6)])
                Color(0.88, 0.64, 0.24, 1)
                Ellipse(pos=(cx - dp(3), cy + dp(1)), size=(dp(6), dp(6)))
                Color(0.28, 0.30, 0.34, 0.85)
                Triangle(points=[cx - cw * 0.42, cy - ch * 0.45, cx - cw * 0.05, cy + ch * 0.02, cx + cw * 0.25, cy - ch * 0.45])

            elif self.icon_type == "document":
                dw, dh = s * 0.48, s * 0.60
                x0, y0 = cx - dw / 2, cy - dh / 2
                Color(0.55, 0.58, 0.62, 0.9)
                RoundedRectangle(pos=(x0, y0), size=(dw, dh), radius=[dp(4)])
                Color(0.35, 0.38, 0.42, 1)
                fold = dw * 0.30
                Triangle(points=[x0 + dw - fold, y0 + dh, x0 + dw, y0 + dh - fold, x0 + dw - fold, y0 + dh - fold])

            elif self.icon_type == "zip_badge":
                Color(0.68, 0.48, 0.22, 1)
                RoundedRectangle(pos=(self.x + dp(2), self.y + dp(2)), size=(self.width - dp(4), self.height - dp(4)), radius=[dp(8)])
                Color(0.96, 0.88, 0.72, 1)
                Line(points=[cx, cy + s * 0.25, cx, cy - s * 0.05], width=dp(1.6))
                RoundedRectangle(pos=(cx - dp(3), cy - dp(5)), size=(dp(6), dp(6)), radius=[dp(1.5)])

            elif self.icon_type == "img_badge":
                Color(0.26, 0.28, 0.31, 1)
                RoundedRectangle(pos=(self.x + dp(2), self.y + dp(2)), size=(self.width - dp(4), self.height - dp(4)), radius=[dp(8)])
                Color(0.65, 0.68, 0.72, 1)
                w, h = s * 0.55, s * 0.35
                Triangle(points=[cx - w * 0.5, cy - h * 0.5, cx - w * 0.1, cy + h * 0.35, cx + w * 0.3, cy - h * 0.5])
                Triangle(points=[cx - w * 0.05, cy - h * 0.5, cx + w * 0.25, cy + h * 0.15, cx + w * 0.5, cy - h * 0.5])

            elif self.icon_type == "transfer":
                dx = s * 0.26
                dy = s * 0.12
                aw = s * 0.10
                Line(points=[cx - dx, cy + dy, cx + dx, cy + dy], width=lw)
                Line(points=[cx + dx - aw, cy + dy + aw, cx + dx, cy + dy, cx + dx - aw, cy + dy - aw], width=lw)
                Line(points=[cx + dx, cy - dy, cx - dx, cy - dy], width=lw)
                Line(points=[cx - dx + aw, cy - dy + aw, cx - dx, cy - dy, cx - dx + aw, cy - dy - aw], width=lw)

            elif self.icon_type == "folder":
                w, h = s * 0.56, s * 0.40
                x0, y0 = cx - w / 2, cy - h / 2
                Line(rounded_rectangle=[x0, y0, w, h * 0.85, dp(3)], width=lw)
                Line(points=[x0 + dp(2), y0 + h * 0.85, x0 + w * 0.38, y0 + h * 0.85, x0 + w * 0.46, y0 + h * 0.68], width=lw)

            elif self.icon_type == "phone":
                w, h = s * 0.38, s * 0.62
                Line(rounded_rectangle=[cx - w / 2, cy - h / 2, w, h, dp(3.5)], width=lw)
                Ellipse(pos=(cx - dp(1.2), cy - h * 0.34), size=(dp(2.4), dp(2.4)))

            elif self.icon_type == "lock":
                w, h = s * 0.46, s * 0.36
                x0, y0 = cx - w / 2, cy - h * 0.65
                Line(rounded_rectangle=[x0, y0, w, h, dp(3)], width=lw)
                Line(circle=(cx, y0 + h, w * 0.28, -90, 90), width=lw)
                Ellipse(pos=(cx - dp(1.5), y0 + h * 0.42), size=(dp(3), dp(3)))

            elif self.icon_type == "sliders":
                dx = s * 0.28
                y1, y2 = cy + s * 0.14, cy - s * 0.14
                Line(points=[cx - dx, y1, cx + dx, y1], width=lw)
                Line(points=[cx - dx, y2, cx + dx, y2], width=lw)
                Ellipse(pos=(cx - dx * 0.35 - dp(3), y1 - dp(3)), size=(dp(6), dp(6)))
                Ellipse(pos=(cx + dx * 0.35 - dp(3), y2 - dp(3)), size=(dp(6), dp(6)))

            elif self.icon_type == "info":
                r = s * 0.32
                Line(circle=(cx, cy, r), width=lw)
                Line(points=[cx, cy - r * 0.38, cx, cy + r * 0.08], width=lw)
                Ellipse(pos=(cx - dp(1.3), cy + r * 0.32), size=(dp(2.6), dp(2.6)))

            elif self.icon_type == "chevron":
                d = s * 0.16
                Line(points=[cx - d * 0.5, cy + d, cx + d * 0.5, cy, cx - d * 0.5, cy - d], width=lw)


class VectorIconButton(ButtonBehavior, VectorIcon):
    """Standalone clickable vector icon button (used for top-right gear and copy button)"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.always_release = True

    def on_touch_down(self, touch):
        return ButtonBehavior.on_touch_down(self, touch)

    def on_touch_move(self, touch):
        return ButtonBehavior.on_touch_move(self, touch)

    def on_touch_up(self, touch):
        return ButtonBehavior.on_touch_up(self, touch)

    def on_press(self):
        self.opacity = 0.55

    def on_release(self):
        self.opacity = 1.0


class RoundedCard(BoxLayout):
    """Universal rounded card container with density-independent border"""

    def __init__(self, bg_color, border_color=(0, 0, 0, 0), radius=dp(18), **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.border_color = border_color
        self.radius_val = radius
        with self.canvas.before:
            self.col = Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius_val])
            self.b_col = Color(*self.border_color)
            self.line = Line(
                rounded_rectangle=[self.x, self.y, self.width, self.height, max(1, self.radius_val)],
                width=dp(1.0),
            )
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        if self.width > 2 and self.height > 2:
            self.line.rounded_rectangle = [self.x, self.y, self.width, self.height, min(self.radius_val, self.height / 2)]

    def update_colors(self, bg_color, border_color=(0, 0, 0, 0)):
        self.bg_color = bg_color
        self.border_color = border_color
        self.col.rgba = bg_color
        self.b_col.rgba = border_color


class ClickableCard(ButtonBehavior, RoundedCard):
    """Interactive RoundedCard that responds to touch anywhere inside its bounds"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.always_release = True

    def on_press(self):
        self.opacity = 0.75

    def on_release(self):
        self.opacity = 1.0


class DrawerOverlay(Widget):
    """Scrim overlay that ONLY intercepts touches when the side drawer is open"""

    def __init__(self, close_callback, **kwargs):
        super().__init__(**kwargs)
        self.close_callback = close_callback
        self.is_open = False
        with self.canvas:
            self.col = Color(0, 0, 0, 0)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def set_scrim_color(self, rgba):
        self.col.rgba = rgba

    def on_touch_down(self, touch):
        if not self.is_open:
            return False
        if self.collide_point(*touch.pos):
            if self.close_callback:
                self.close_callback()
            return True
        return False

    def on_touch_move(self, touch):
        return self.is_open

    def on_touch_up(self, touch):
        return self.is_open


class DrawerPanel(RoundedCard):
    """Floating side drawer that ignores touches when closed and stops pass-through when open"""

    is_open = False

    def on_touch_down(self, touch):
        if not self.is_open or not self.collide_point(*touch.pos):
            return False
        super().on_touch_down(touch)
        return True

    def on_touch_move(self, touch):
        if not self.is_open or not self.collide_point(*touch.pos):
            return False
        super().on_touch_move(touch)
        return True

    def on_touch_up(self, touch):
        if not self.is_open:
            return False
        if super().on_touch_up(touch):
            return True
        return self.collide_point(*touch.pos)


class DrawerMenuRow(ButtonBehavior, RoundedCard):
    """Full-width clickable menu row inside the side drawer with press highlight"""

    def __init__(self, icon_name, label_text, text_color, sub_color, highlight_rgba, **kwargs):
        super().__init__(
            bg_color=(0, 0, 0, 0),
            border_color=(0, 0, 0, 0),
            radius=dp(12),
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(46),
            padding=[dp(8), dp(4), dp(8), dp(4)],
            spacing=dp(12),
            **kwargs,
        )
        self.always_release = True
        self.highlight_rgba = highlight_rgba

        self.ico_w = VectorIcon(icon_type=icon_name, color=sub_color, size_hint=(None, 1), width=dp(24))
        self.lbl_w = Label(
            text=label_text,
            font_size=sp(15),
            color=text_color,
            halign="left",
            valign="middle",
            size_hint=(1, 1),
        )
        self.lbl_w.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.chev_w = VectorIcon(icon_type="chevron", color=sub_color, size_hint=(None, 1), width=dp(18))

        self.add_widget(self.ico_w)
        self.add_widget(self.lbl_w)
        self.add_widget(self.chev_w)

    def on_press(self):
        self.update_colors(self.highlight_rgba, (0, 0, 0, 0))

    def on_release(self):
        self.update_colors((0, 0, 0, 0), (0, 0, 0, 0))


class RadarCard(RoundedCard):
    """Top radar discovery card with 4 concentric rings matching 1000250791.jpg"""

    def __init__(self, bg_color, border_color, ring_color, **kwargs):
        super().__init__(bg_color=bg_color, border_color=border_color, radius=dp(22), **kwargs)
        with self.canvas.before:
            self.ring_col = Color(*ring_color)
            self.ring1 = Line(circle=(0, 0, 10), width=dp(1.0))
            self.ring2 = Line(circle=(0, 0, 20), width=dp(1.0))
            self.ring3 = Line(circle=(0, 0, 30), width=dp(1.0))
            self.ring4 = Line(circle=(0, 0, 40), width=dp(1.0))
        self.bind(pos=self._update_rings, size=self._update_rings)

    def _update_rings(self, *_args):
        cx = self.center_x
        cy = self.center_y + dp(10)
        max_r = min(self.width, self.height) * 0.46
        self.ring1.circle = (cx, cy, max_r * 0.42)
        self.ring2.circle = (cx, cy, max_r * 0.62)
        self.ring3.circle = (cx, cy, max_r * 0.82)
        self.ring4.circle = (cx, cy, max_r * 1.00)

    def update_radar_colors(self, bg_color, border_color, ring_color):
        self.update_colors(bg_color, border_color)
        self.ring_col.rgba = ring_color


class SlimProgressBar(Widget):
    """Sleek rounded progress bar scaled with dp() that never blocks touches"""

    def __init__(self, percent=0.45, track_color=(0.24, 0.26, 0.29, 1), fill_color=(0.86, 0.60, 0.22, 1), **kwargs):
        super().__init__(**kwargs)
        self.percent = percent
        with self.canvas:
            self.t_col = Color(*track_color)
            self.t_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(2.5)])
            self.f_col = Color(*fill_color)
            self.f_rect = RoundedRectangle(pos=self.pos, size=(self.width * self.percent, self.height), radius=[dp(2.5)])
        self.bind(pos=self._upd, size=self._upd)

    def on_touch_down(self, touch):
        return False

    def _upd(self, *_args):
        self.t_rect.pos = self.pos
        self.t_rect.size = self.size
        self.f_rect.pos = self.pos
        self.f_rect.size = (max(dp(8), self.width * self.percent), self.height)

    def set_percent(self, p):
        self.percent = min(1.0, max(0.0, p))
        self._upd()

    def update_bar_colors(self, track_color, fill_color):
        self.t_col.rgba = track_color
        self.f_col.rgba = fill_color


class NavTabItem(ButtonBehavior, BoxLayout):
    """Bottom navigation tab item with active pill background and vector icon"""

    def __init__(self, icon_type, title_text, is_active=False, pill_color=(0.30, 0.33, 0.38, 1), text_color=(1, 1, 1, 1), **kwargs):
        super().__init__(orientation="vertical", spacing=dp(2), padding=[dp(6), dp(4), dp(6), dp(4)], **kwargs)
        self.always_release = True
        self.is_active = is_active
        self.pill_color = pill_color

        self.pill_wrap = AnchorLayout(size_hint=(1, 0.58))
        self.pill_bg = RoundedCard(
            bg_color=pill_color if is_active else (0, 0, 0, 0),
            border_color=(0, 0, 0, 0),
            radius=dp(14),
            size_hint=(None, None),
            size=(dp(64), dp(30)),
        )
        self.icon_widget = VectorIcon(icon_type=icon_type, color=text_color, size_hint=(1, 1))
        self.pill_bg.add_widget(self.icon_widget)
        self.pill_wrap.add_widget(self.pill_bg)

        self.label = Label(
            text=title_text,
            font_size=sp(11),
            color=text_color,
            halign="center",
            valign="middle",
            size_hint=(1, 0.42),
        )
        self.label.bind(size=lambda i, v: setattr(i, "text_size", v))

        self.add_widget(self.pill_wrap)
        self.add_widget(self.label)

    def on_press(self):
        self.opacity = 0.70

    def on_release(self):
        self.opacity = 1.0

    def set_active_style(self, is_active, pill_color, text_color):
        self.is_active = is_active
        self.pill_bg.update_colors(pill_color if is_active else (0, 0, 0, 0), (0, 0, 0, 0))
        self.icon_widget.set_color(text_color)
        self.label.color = text_color


class RadarCenterButton(ButtonBehavior, BoxLayout):
    """Clickable center area of the Radar Card to start/stop server on tap"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.always_release = True

    def on_press(self):
        self.opacity = 0.75

    def on_release(self):
        self.opacity = 1.0


class AirShareApp(App):
    server = None
    is_stopping = False
    connected_pc_title = "Desktop PC"
    connected_pc_os = "Windows 11"
    active_folder_key = "Downloads"
    transfer_history = []

    def _get_folder_map(self):
        base = STORAGE_PATH if os.path.isdir(STORAGE_PATH) else os.path.expanduser("~")
        return {
            "All Storage": base,
            "Downloads": os.path.join(base, "Download"),
            "Camera Roll": os.path.join(base, "DCIM"),
            "Documents": os.path.join(base, "Documents"),
        }

    def build(self):
        self.title = f"{APP_NAME} v{APP_VERSION}"
        request_android_full_storage()

        settings = load_settings()
        self.theme_mode = settings.get("theme_mode", "dark")
        self.server_port = settings.get("port", SERVER_PORT)
        self.saved_password = settings.get("password", "")
        DynamicAirShareHandler.active_storage_path = STORAGE_PATH

        p = THEMES["dark"]
        self.root_widget = FloatLayout()

        # =====================================================================
        # ГЛАВНЫЙ ЭКРАН (масштабирование в dp() + векторные иконки + кликабельность)
        # =====================================================================
        self.main_content = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(16), dp(18), dp(18)],
            spacing=dp(12),
        )

        # 1. Верхняя шапка (Header)
        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.device_label = Label(
            text=f"[b]{get_device_info()}[/b]",
            markup=True,
            font_size=sp(21),
            halign="left",
            valign="middle",
            size_hint=(0.52, 1),
        )
        self.device_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        self.wifi_pill = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(17),
            orientation="horizontal",
            size_hint=(None, None),
            size=(dp(136), dp(34)),
            pos_hint={"center_y": 0.5},
            padding=[dp(10), dp(4), dp(10), dp(4)],
            spacing=dp(4),
        )
        self.wifi_icon = VectorIcon(icon_type="wifi", color=p["text"], size_hint=(None, 1), width=dp(18))
        self.wifi_label = Label(text="Wi-Fi 6 • 5GHz", font_size=sp(12), halign="center", valign="middle")
        self.wifi_pill.add_widget(self.wifi_icon)
        self.wifi_pill.add_widget(self.wifi_label)
        self.wifi_pill.bind(on_press=self.refresh_network_status)

        self.gear_btn = VectorIconButton(
            icon_type="gear",
            color=p["subtext"],
            size_hint=(None, None),
            size=(dp(42), dp(42)),
            pos_hint={"center_y": 0.5},
        )
        self.gear_btn.bind(on_press=self.toggle_drawer)

        header.add_widget(self.device_label)
        header.add_widget(self.wifi_pill)
        header.add_widget(self.gear_btn)
        self.main_content.add_widget(header)

        # 2. Карточка радара (Radar Card)
        self.radar_card = RadarCard(
            bg_color=p["radar_bg"],
            border_color=p["card_border"],
            ring_color=p["radar_ring"],
            orientation="vertical",
            padding=[dp(16), dp(18), dp(16), dp(14)],
            spacing=dp(4),
            size_hint=(1, 0.36),
        )

        # Кликабельная центральная область радара (включает/выключает сервер по нажатию)
        self.radar_top_btn = RadarCenterButton(orientation="vertical", size_hint=(1, 0.76), spacing=dp(4))
        self.radar_top_btn.bind(on_press=self.toggle_server)

        icon_holder = AnchorLayout(size_hint=(1, 0.50))
        self.monitor_icon = VectorIcon(icon_type="pc", color=p["text"], size_hint=(None, None), size=(dp(56), dp(46)))
        icon_holder.add_widget(self.monitor_icon)

        pc_row_anchor = AnchorLayout(size_hint=(1, 0.28))
        pc_row = BoxLayout(orientation="horizontal", size_hint=(None, None), size=(dp(210), dp(28)), spacing=dp(8))
        self.pc_title_label = Label(
            text=f"[b]{self.connected_pc_title}[/b]",
            markup=True,
            font_size=sp(18),
            halign="right",
            valign="middle",
            size_hint=(0.58, 1),
        )
        self.pc_title_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        self.os_badge_card = RoundedCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(6),
            size_hint=(0.42, None),
            height=dp(22),
            pos_hint={"center_y": 0.5},
            padding=[dp(6), dp(2), dp(6), dp(2)],
        )
        self.os_badge_label = Label(text=self.connected_pc_os, font_size=sp(10), halign="center", valign="middle")
        self.os_badge_card.add_widget(self.os_badge_label)

        pc_row.add_widget(self.pc_title_label)
        pc_row.add_widget(self.os_badge_card)
        pc_row_anchor.add_widget(pc_row)

        self.speed_label = Label(
            text="850 Mbps",
            font_size=sp(13),
            halign="center",
            valign="top",
            size_hint=(1, 0.22),
        )
        self.speed_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        self.radar_top_btn.add_widget(icon_holder)
        self.radar_top_btn.add_widget(pc_row_anchor)
        self.radar_top_btn.add_widget(self.speed_label)

        # Нижняя капсула с адресом (тоже кликабельная для копирования!) и иконка копирования
        addr_row = FloatLayout(size_hint=(1, 0.24))
        self.addr_pill = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(19),
            size_hint=(0.68, None),
            height=dp(38),
            pos_hint={"center_x": 0.46, "center_y": 0.5},
        )
        self.addr_label = Label(
            text=f"http://{get_local_ip()}:{self.server_port}",
            font_size=sp(13.5),
            halign="center",
            valign="middle",
        )
        self.addr_pill.add_widget(self.addr_label)
        self.addr_pill.bind(on_press=self.copy_address)

        self.copy_btn = VectorIconButton(
            icon_type="copy",
            color=p["subtext"],
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            pos_hint={"right": 0.98, "center_y": 0.5},
        )
        self.copy_btn.bind(on_press=self.copy_address)

        addr_row.add_widget(self.addr_pill)
        addr_row.add_widget(self.copy_btn)

        self.radar_card.add_widget(self.radar_top_btn)
        self.radar_card.add_widget(addr_row)
        self.main_content.add_widget(self.radar_card)

        # 3. Заголовок и кликабельные карточки Shared Folders
        self.folders_header = Label(
            text="[b]Shared Folders[/b]",
            markup=True,
            font_size=sp(16),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp(26),
        )
        self.folders_header.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.main_content.add_widget(self.folders_header)

        folders_grid = GridLayout(cols=3, spacing=dp(10), size_hint=(1, 0.19))
        self.folder_cards = []
        folder_specs = [
            ("Downloads", "download", 0.42),
            ("Camera Roll", "gallery", 0.36),
            ("Documents", "document", 0.24),
        ]
        for title_txt, icon_kind, prog in folder_specs:
            card = ClickableCard(
                bg_color=p["card_bg"],
                border_color=p["card_border"],
                radius=dp(16),
                orientation="vertical",
                padding=[dp(12), dp(10), dp(12), dp(10)],
                spacing=dp(4),
            )
            lbl_top = Label(
                text=title_txt,
                font_size=sp(13),
                halign="left",
                valign="middle",
                size_hint=(1, None),
                height=dp(20),
            )
            lbl_top.bind(size=lambda i, v: setattr(i, "text_size", v))

            ico_wrap = AnchorLayout(size_hint=(1, 1))
            ico_wid = VectorIcon(
                icon_type=icon_kind,
                color=p["amber"] if title_txt == self.active_folder_key else p["text"],
                size_hint=(None, None),
                size=(dp(48), dp(42)),
            )
            ico_wrap.add_widget(ico_wid)

            bar = SlimProgressBar(
                percent=prog,
                track_color=p["track"],
                fill_color=p["amber"] if title_txt == self.active_folder_key else p["subtext"],
                size_hint=(1, None),
                height=dp(4.5),
            )
            card.add_widget(lbl_top)
            card.add_widget(ico_wrap)
            card.add_widget(bar)
            card.bind(on_press=lambda _inst, folder_name=title_txt: self.on_folder_card_pressed(folder_name))
            folders_grid.add_widget(card)
            self.folder_cards.append((card, lbl_top, ico_wid, bar, icon_kind, title_txt))

        self.main_content.add_widget(folders_grid)

        # 4. Заголовок и кликабельная карточка Recent Transfers
        self.transfers_header = Label(
            text="[b]Recent Transfers[/b]",
            markup=True,
            font_size=sp(16),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp(26),
        )
        self.transfers_header.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.main_content.add_widget(self.transfers_header)

        self.transfers_card = ClickableCard(
            bg_color=p["card_bg"],
            border_color=p["card_border"],
            radius=dp(16),
            orientation="vertical",
            padding=[dp(14), dp(10), dp(14), dp(10)],
            spacing=dp(8),
            size_hint=(1, 0.20),
        )
        self.transfers_card.bind(on_press=self.open_transfers_modal)

        row1 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5))
        ico1 = VectorIcon(icon_type="zip_badge", size_hint=(None, None), size=(dp(40), dp(40)), pos_hint={"center_y": 0.5})
        info1 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top1 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20))
        self.tr1_name = Label(text="Project_Archive.zip", font_size=sp(14), halign="left", valign="middle", size_hint=(0.76, 1))
        self.tr1_name.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.tr1_pct = Label(text="100%", font_size=sp(13), halign="right", valign="middle", size_hint=(0.24, 1))
        self.tr1_pct.bind(size=lambda i, v: setattr(i, "text_size", v))
        top1.add_widget(self.tr1_name)
        top1.add_widget(self.tr1_pct)
        self.tr1_bar = SlimProgressBar(percent=1.0, track_color=p["track"], fill_color=p["amber"], size_hint=(1, None), height=dp(4))
        self.tr1_sub = Label(text="Completed", font_size=sp(11.5), halign="left", valign="middle", size_hint=(1, None), height=dp(16))
        self.tr1_sub.bind(size=lambda i, v: setattr(i, "text_size", v))
        info1.add_widget(top1)
        info1.add_widget(self.tr1_bar)
        info1.add_widget(self.tr1_sub)
        row1.add_widget(ico1)
        row1.add_widget(info1)

        row2 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5))
        ico2 = VectorIcon(icon_type="img_badge", size_hint=(None, None), size=(dp(40), dp(40)), pos_hint={"center_y": 0.5})
        info2 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top2 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20))
        self.tr2_name = Label(text="IMG_8492.raw", font_size=sp(14), halign="left", valign="middle", size_hint=(0.76, 1))
        self.tr2_name.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.tr2_pct = Label(text="64%", font_size=sp(13), halign="right", valign="middle", size_hint=(0.24, 1))
        self.tr2_pct.bind(size=lambda i, v: setattr(i, "text_size", v))
        top2.add_widget(self.tr2_name)
        top2.add_widget(self.tr2_pct)
        self.tr2_bar = SlimProgressBar(percent=0.64, track_color=p["track"], fill_color=p["blue"], size_hint=(1, None), height=dp(4))
        self.tr2_sub = Label(text="45 MB/s", font_size=sp(11.5), halign="right", valign="middle", size_hint=(1, None), height=dp(16))
        self.tr2_sub.bind(size=lambda i, v: setattr(i, "text_size", v))
        info2.add_widget(top2)
        info2.add_widget(self.tr2_bar)
        info2.add_widget(self.tr2_sub)
        row2.add_widget(ico2)
        row2.add_widget(info2)

        self.transfers_card.add_widget(row1)
        self.transfers_card.add_widget(row2)
        self.main_content.add_widget(self.transfers_card)

        # 5. Нижняя навигационная панель (док-бар высотой dp(64) с капсулой на Transfer)
        self.bottom_nav = RoundedCard(
            bg_color=p["card_bg"],
            border_color=p["card_border"],
            radius=dp(24),
            orientation="horizontal",
            padding=[dp(10), dp(6), dp(10), dp(6)],
            spacing=dp(4),
            size_hint=(1, None),
            height=dp(64),
        )

        self.nav_transfer = NavTabItem("transfer", "Transfer", is_active=True, pill_color=p["pill_active"], text_color=p["text"])
        self.nav_transfer.bind(on_press=self.toggle_server)

        self.nav_files = NavTabItem("folder", "Files", is_active=False, pill_color=p["pill_active"], text_color=p["subtext"])
        self.nav_files.bind(on_press=self.open_shared_folders_modal)

        self.nav_devices = NavTabItem("phone", "Devices", is_active=False, pill_color=p["pill_active"], text_color=p["subtext"])
        self.nav_devices.bind(on_press=self.open_devices_modal)

        self.nav_settings = NavTabItem("gear", "Settings", is_active=False, pill_color=p["pill_active"], text_color=p["subtext"])
        self.nav_settings.bind(on_press=self.toggle_drawer)

        self.bottom_nav.add_widget(self.nav_transfer)
        self.bottom_nav.add_widget(self.nav_files)
        self.bottom_nav.add_widget(self.nav_devices)
        self.bottom_nav.add_widget(self.nav_settings)
        self.main_content.add_widget(self.bottom_nav)

        self.root_widget.add_widget(self.main_content)

        # =====================================================================
        # ПАРЯЩАЯ БОКОВАЯ ШТОРКА (1000250792.jpg с прозрачным для кликов DrawerOverlay)
        # =====================================================================
        self.overlay = DrawerOverlay(close_callback=self.close_drawer, size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.root_widget.add_widget(self.overlay)

        self.drawer_width = dp(285)
        self.drawer = DrawerPanel(
            bg_color=p["drawer_bg"],
            border_color=p["drawer_border"],
            radius=dp(26),
            orientation="vertical",
            padding=[dp(20), dp(22), dp(20), dp(18)],
            spacing=dp(14),
            size_hint=(None, None),
            width=self.drawer_width,
            height=Window.height - dp(48),
            pos=(-self.drawer_width - dp(40), dp(24)),
        )
        Window.bind(size=self._on_window_resize)

        # 1) Заголовок AirShare PC
        self.drawer_title = Label(
            text=f"[b]{APP_NAME}[/b]",
            markup=True,
            font_size=sp(23),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp(32),
        )
        self.drawer_title.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.drawer.add_widget(self.drawer_title)

        # 2) Строка с векторной иконкой телефона и названием модели
        phone_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(30), spacing=dp(10))
        self.drawer_phone_icon = VectorIcon(icon_type="phone", color=p["subtext"], size_hint=(None, 1), width=dp(22))
        self.drawer_phone_label = Label(
            text=get_device_info(),
            font_size=sp(15),
            halign="left",
            valign="middle",
        )
        self.drawer_phone_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        phone_row.add_widget(self.drawer_phone_icon)
        phone_row.add_widget(self.drawer_phone_label)
        self.drawer.add_widget(phone_row)

        # 3) Кликабельная карточка Storage: XX.X GB / XXX GB
        stats = get_storage_stats()
        self.drawer_storage_card = ClickableCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(15),
            orientation="vertical",
            padding=[dp(14), dp(10), dp(14), dp(12)],
            spacing=dp(8),
            size_hint=(1, None),
            height=dp(64),
        )
        self.drawer_storage_label = Label(
            text=f"Storage: [b]{stats['used_gb']} GB[/b] / {stats['total_gb']:.0f} GB",
            markup=True,
            font_size=sp(13),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp(20),
        )
        self.drawer_storage_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.drawer_storage_bar = SlimProgressBar(
            percent=stats["percent"],
            track_color=p["pill_bg"],
            fill_color=p["text"],
            size_hint=(1, None),
            height=dp(5),
        )
        self.drawer_storage_card.add_widget(self.drawer_storage_label)
        self.drawer_storage_card.add_widget(self.drawer_storage_bar)
        self.drawer_storage_card.bind(on_press=self.open_shared_folders_modal)
        self.drawer.add_widget(self.drawer_storage_card)

        # 4) Кликабельная карточка подключённого ПК (Desktop PC / Windows 11)
        self.drawer_pc_card = ClickableCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(15),
            orientation="horizontal",
            padding=[dp(14), dp(10), dp(14), dp(10)],
            spacing=dp(12),
            size_hint=(1, None),
            height=dp(68),
        )
        self.drawer_pc_icon = VectorIcon(icon_type="pc", color=p["text"], size_hint=(None, 1), width=dp(32))
        self.drawer_pc_label = Label(
            text=f"[b]{self.connected_pc_title}[/b]\n[size={int(sp(12))}]{self.connected_pc_os}[/size]",
            markup=True,
            font_size=sp(15),
            halign="left",
            valign="middle",
            size_hint=(1, 1),
        )
        self.drawer_pc_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.drawer_pc_card.add_widget(self.drawer_pc_icon)
        self.drawer_pc_card.add_widget(self.drawer_pc_label)
        self.drawer_pc_card.bind(on_press=self.open_devices_modal)
        self.drawer.add_widget(self.drawer_pc_card)

        # 5) 4 полноразмерных кликабельных пункта меню с векторными иконками и шевронами
        menu_box = BoxLayout(orientation="vertical", spacing=dp(4), size_hint=(1, 1))
        self.menu_items_refs = []
        menu_rows = [
            ("folder", "Shared Folders", self.open_shared_folders_modal),
            ("lock", "Security & PIN", self.open_security_modal),
            ("sliders", "Port Settings", self.open_port_modal),
            ("info", "Help & Feedback", self.open_help_modal),
        ]
        for ico_name, label_text, callback in menu_rows:
            row = DrawerMenuRow(
                icon_name=ico_name,
                label_text=label_text,
                text_color=p["text"],
                sub_color=p["subtext"],
                highlight_rgba=p["pill_bg"],
            )
            row.bind(on_press=callback)
            menu_box.add_widget(row)
            self.menu_items_refs.append(row)

        self.drawer.add_widget(menu_box)

        # 6) Сегментная капсула выбора темы (Dark | Light | Auto)
        self.theme_pill_container = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(20),
            orientation="horizontal",
            padding=dp(4),
            spacing=dp(4),
            size_hint=(1, None),
            height=dp(44),
        )
        self.t_btn_dark = Button(text="Dark", font_size=sp(13), background_normal="")
        self.t_btn_dark.bind(on_press=lambda *_: self.set_theme_mode("dark"))
        self.t_btn_light = Button(text="Light", font_size=sp(13), background_normal="")
        self.t_btn_light.bind(on_press=lambda *_: self.set_theme_mode("light"))
        self.t_btn_auto = Button(text="Auto", font_size=sp(13), background_normal="")
        self.t_btn_auto.bind(on_press=lambda *_: self.set_theme_mode("system"))

        self.theme_pill_container.add_widget(self.t_btn_dark)
        self.theme_pill_container.add_widget(self.t_btn_light)
        self.theme_pill_container.add_widget(self.t_btn_auto)
        self.drawer.add_widget(self.theme_pill_container)

        self.root_widget.add_widget(self.drawer)

        DynamicAirShareHandler.on_client_connected = self._on_client_connected
        DynamicAirShareHandler.on_file_transfer = self._on_file_transfer
        self.apply_theme()

        # Автоматический запуск сервера при старте приложения, чтобы сразу работало подключение с ПК
        Clock.schedule_once(lambda _dt: self.start_server_if_needed(), 0.3)
        return self.root_widget

    def start_server_if_needed(self):
        if self.server is None and not self.is_stopping:
            self.toggle_server()

    def _on_window_resize(self, *_args):
        self.drawer.height = Window.height - dp(48)

    def refresh_network_status(self, *_args):
        ip = get_local_ip()
        self.addr_label.text = f"http://{ip}:{self.server_port}"
        self.wifi_label.text = f"Wi-Fi • {ip}"
        Clock.schedule_once(lambda _dt: setattr(self.wifi_label, "text", "Wi-Fi 6 • 5GHz"), 2.0)

    def toggle_drawer(self, *_args):
        if not self.drawer.is_open:
            self.open_drawer()
        else:
            self.close_drawer()

    def open_drawer(self, *_args):
        self.drawer.is_open = True
        self.overlay.is_open = True
        stats = get_storage_stats()
        self.drawer_storage_label.text = f"Storage: [b]{stats['used_gb']} GB[/b] / {stats['total_gb']:.0f} GB"
        self.drawer_storage_bar.set_percent(stats["percent"])
        eff = self._get_effective_theme()
        palette = THEMES.get(eff, THEMES["dark"])
        self.overlay.set_scrim_color(palette["overlay"])
        Animation.cancel_all(self.drawer)
        Animation(x=dp(16), duration=0.22, t="out_cubic").start(self.drawer)

    def close_drawer(self, *_args):
        self.drawer.is_open = False
        self.overlay.is_open = False
        self.overlay.set_scrim_color((0, 0, 0, 0))
        Animation.cancel_all(self.drawer)
        Animation(x=-self.drawer_width - dp(40), duration=0.20, t="out_cubic").start(self.drawer)

    def _get_effective_theme(self):
        if self.theme_mode == "system":
            return get_device_theme()
        return self.theme_mode

    def set_theme_mode(self, mode):
        self.theme_mode = mode
        save_settings(theme_mode=mode)
        self.apply_theme()

    def apply_theme(self):
        eff = self._get_effective_theme()
        p = THEMES.get(eff, THEMES["dark"])
        DynamicAirShareHandler.default_theme = eff

        Window.clearcolor = p["bg"]
        self.device_label.color = p["text"]
        self.wifi_pill.update_colors(p["pill_bg"], p["card_border"])
        self.wifi_icon.set_color(p["text"])
        self.wifi_label.color = p["text"]
        self.gear_btn.set_color(p["subtext"])

        self.radar_card.update_radar_colors(p["radar_bg"], p["card_border"], p["radar_ring"])
        self.monitor_icon.set_color(p["green"] if self.server is not None else p["text"])
        self.pc_title_label.color = p["text"]
        self.os_badge_card.update_colors(p["pill_bg"], p["card_border"])
        self.os_badge_label.color = p["subtext"]
        self.speed_label.color = p["green"] if self.server is not None else p["subtext"]
        self.addr_pill.update_colors(p["pill_bg"], p["card_border"])
        self.addr_label.color = p["text"]
        self.copy_btn.set_color(p["subtext"])

        self.folders_header.color = p["text"]
        for card, lbl_top, ico_wid, bar, icon_kind, title_txt in self.folder_cards:
            is_sel = (title_txt == self.active_folder_key)
            card.update_colors(p["card_bg"], p["amber"] if is_sel else p["card_border"])
            lbl_top.color = p["text"]
            ico_wid.set_color(p["amber"] if (is_sel or icon_kind == "download") else p["text"])
            bar.update_bar_colors(p["track"], p["amber"] if is_sel else p["subtext"])

        self.transfers_header.color = p["text"]
        self.transfers_card.update_colors(p["card_bg"], p["card_border"])
        self.tr1_name.color = p["text"]
        self.tr1_pct.color = p["subtext"]
        self.tr1_sub.color = p["subtext"]
        self.tr1_bar.update_bar_colors(p["track"], p["amber"])
        self.tr2_name.color = p["text"]
        self.tr2_pct.color = p["subtext"]
        self.tr2_sub.color = p["subtext"]
        self.tr2_bar.update_bar_colors(p["track"], p["blue"])

        self.bottom_nav.update_colors(p["card_bg"], p["card_border"])
        active_pill = p["green"] if self.server is not None else p["pill_active"]
        self.nav_transfer.set_active_style(True, active_pill, p["text"])
        self.nav_files.set_active_style(False, p["pill_active"], p["subtext"])
        self.nav_devices.set_active_style(False, p["pill_active"], p["subtext"])
        self.nav_settings.set_active_style(False, p["pill_active"], p["subtext"])

        self.drawer.update_colors(p["drawer_bg"], p["drawer_border"])
        self.drawer_title.color = p["text"]
        self.drawer_phone_icon.set_color(p["subtext"])
        self.drawer_phone_label.color = p["text"]
        self.drawer_storage_card.update_colors(p["drawer_card"], p["drawer_border"])
        self.drawer_storage_label.color = p["text"]
        self.drawer_storage_bar.update_bar_colors(p["pill_bg"], p["text"])
        self.drawer_pc_card.update_colors(p["drawer_card"], p["drawer_border"])
        self.drawer_pc_icon.set_color(p["text"])
        self.drawer_pc_label.color = p["text"]

        for row in self.menu_items_refs:
            row.highlight_rgba = p["pill_bg"]
            row.ico_w.set_color(p["subtext"])
            row.lbl_w.color = p["text"]
            row.chev_w.set_color(p["subtext"])

        self.theme_pill_container.update_colors(p["drawer_card"], p["drawer_border"])
        self.t_btn_dark.background_color = p["pill_active"] if self.theme_mode == "dark" else (0, 0, 0, 0)
        self.t_btn_light.background_color = p["pill_active"] if self.theme_mode == "light" else (0, 0, 0, 0)
        self.t_btn_auto.background_color = p["pill_active"] if self.theme_mode == "system" else (0, 0, 0, 0)
        for tb in (self.t_btn_dark, self.t_btn_light, self.t_btn_auto):
            tb.color = p["text"]

    def on_folder_card_pressed(self, folder_name):
        folder_map = self._get_folder_map()
        if self.active_folder_key == folder_name:
            # Повторное нажатие включает полный доступ ко всему хранилищу
            self.active_folder_key = "All Storage"
            target_path = folder_map["All Storage"]
        else:
            self.active_folder_key = folder_name
            target_path = folder_map.get(folder_name, STORAGE_PATH)

        if not os.path.isdir(target_path):
            try:
                os.makedirs(target_path, exist_ok=True)
            except Exception:
                target_path = STORAGE_PATH

        DynamicAirShareHandler.active_storage_path = target_path
        status_prefix = "850 Mbps • Online" if self.server is not None else "Offline"
        self.speed_label.text = f"{status_prefix} • {self.active_folder_key}"
        self.apply_theme()

    def copy_address(self, *_args):
        url = f"http://{get_local_ip()}:{self.server_port}"
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(url)
        except Exception:
            pass
        self.addr_label.text = "Copied to clipboard!"
        Clock.schedule_once(lambda _dt: setattr(self.addr_label, "text", url), 1.5)

    def _on_client_connected(self, device_title, os_badge, ip):
        def _upd(_dt):
            self.connected_pc_title = device_title
            self.connected_pc_os = os_badge
            self.pc_title_label.text = f"[b]{device_title}[/b]"
            self.os_badge_label.text = os_badge
            self.speed_label.text = f"850 Mbps • {ip}"
            self.drawer_pc_label.text = f"[b]{device_title}[/b]\n[size={int(sp(12))}]{os_badge} • {ip}[/size]"
        Clock.schedule_once(_upd, 0)

    def _on_file_transfer(self, filename, size_str, direction):
        def _upd(_dt):
            self.tr2_name.text = self.tr1_name.text
            self.tr2_pct.text = self.tr1_pct.text
            self.tr2_sub.text = self.tr1_sub.text
            self.tr2_bar.set_percent(1.0)

            self.tr1_name.text = filename
            self.tr1_pct.text = "100%"
            action_str = "Uploaded" if direction == "upload" else "Downloaded"
            self.tr1_sub.text = f"{action_str} • {size_str}"
            self.tr1_bar.set_percent(1.0)
            self.transfer_history.insert(0, f"{filename} ({action_str} • {size_str})")
        Clock.schedule_once(_upd, 0)

    def toggle_server(self, *_args):
        if self.is_stopping:
            return

        if self.server is None:
            settings = load_settings()
            self.saved_password = settings.get("password", "")
            self.server_port = settings.get("port", SERVER_PORT)
            DynamicAirShareHandler.current_password = self.saved_password
            DynamicAirShareHandler.default_theme = self._get_effective_theme()

            ip = get_local_ip()
            url = f"http://{ip}:{self.server_port}"
            self.addr_label.text = url

            try:
                self.server = ReusableThreadingServer(("", self.server_port), DynamicAirShareHandler)
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
            except OSError as e:
                self.server = None
                self.speed_label.text = f"Port error: {e}"
                return

            self.speed_label.text = "850 Mbps • Online"
            self.apply_theme()
        else:
            self.is_stopping = True
            srv = self.server
            self.server = None
            self.speed_label.text = "Stopping..."

            def _stop():
                try:
                    srv.shutdown()
                    srv.server_close()
                except Exception:
                    pass
                Clock.schedule_once(self._on_server_stopped, 0)

            threading.Thread(target=_stop, daemon=True).start()

    def _on_server_stopped(self, _dt):
        self.is_stopping = False
        self.speed_label.text = "Paused • Tap to Start"
        self.apply_theme()

    # =====================================================================
    # МОДАЛЬНЫЕ ОКНА НАСТРОЕК (Папки, Передачи, PIN-код, Порт, История IP)
    # =====================================================================
    def _create_modal(self, title_text, height_dp=250):
        self.close_drawer()
        p = THEMES.get(self._get_effective_theme(), THEMES["dark"])
        modal = ModalView(
            size_hint=(0.88, None),
            height=dp(height_dp),
            background="",
            background_color=(0, 0, 0, 0.62),
            auto_dismiss=True,
        )
        card = RoundedCard(
            bg_color=p["drawer_bg"],
            border_color=p["drawer_border"],
            radius=dp(22),
            orientation="vertical",
            padding=dp(20),
            spacing=dp(12),
        )
        hdr = Label(
            text=f"[b]{title_text}[/b]",
            markup=True,
            font_size=sp(17),
            color=p["text"],
            size_hint=(1, None),
            height=dp(28),
        )
        card.add_widget(hdr)
        modal.add_widget(card)
        return modal, card, p

    def open_shared_folders_modal(self, *_args):
        modal, card, p = self._create_modal("Shared Folders", height_dp=330)
        folder_map = self._get_folder_map()
        cur_path = DynamicAirShareHandler.active_storage_path

        info_lbl = Label(
            text=f"Текущая папка: [b]{self.active_folder_key}[/b]\n{cur_path}",
            markup=True,
            font_size=sp(12.5),
            color=p["subtext"],
            halign="center",
            valign="middle",
            size_hint=(1, None),
            height=dp(40),
        )
        info_lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        card.add_widget(info_lbl)

        grid = GridLayout(cols=2, spacing=dp(8), size_hint=(1, None), height=dp(96))
        for key_name, path_val in folder_map.items():
            is_cur = (key_name == self.active_folder_key)
            btn = Button(
                text=key_name,
                font_size=sp(13.5),
                background_normal="",
                background_color=p["amber"] if is_cur else p["pill_bg"],
                color=(1, 1, 1, 1) if is_cur else p["text"],
            )

            def _pick(_b, k=key_name, pv=path_val):
                self.active_folder_key = k
                if not os.path.isdir(pv):
                    try:
                        os.makedirs(pv, exist_ok=True)
                    except Exception:
                        pv = STORAGE_PATH
                DynamicAirShareHandler.active_storage_path = pv
                status_prefix = "850 Mbps • Online" if self.server is not None else "Offline"
                self.speed_label.text = f"{status_prefix} • {k}"
                self.apply_theme()
                modal.dismiss()

            btn.bind(on_press=_pick)
            grid.add_widget(btn)

        card.add_widget(grid)

        btn_ok = Button(
            text="Закрыть",
            font_size=sp(14),
            size_hint=(1, None),
            height=dp(42),
            background_normal="",
            background_color=p["blue"],
            color=(1, 1, 1, 1),
        )
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)
        modal.open()

    def open_transfers_modal(self, *_args):
        modal, card, p = self._create_modal("Recent Transfers", height_dp=280)
        if self.transfer_history:
            txt = "\n".join(f"• {x}" for x in self.transfer_history[:6])
        else:
            txt = (
                f"• {self.tr1_name.text} ({self.tr1_sub.text})\n"
                f"• {self.tr2_name.text} ({self.tr2_sub.text})\n\n"
                "Новые передачи с ПК появятся здесь автоматически."
            )
        lbl = Label(text=txt, font_size=sp(13), color=p["text"], halign="left", valign="top")
        lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        card.add_widget(lbl)

        btn_ok = Button(
            text="Закрыть",
            font_size=sp(14),
            size_hint=(1, None),
            height=dp(42),
            background_normal="",
            background_color=p["blue"],
            color=(1, 1, 1, 1),
        )
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)
        modal.open()

    def open_security_modal(self, *_args):
        modal, card, p = self._create_modal("Security & PIN", height_dp=240)
        settings = load_settings()
        inp = TextInput(
            text=settings.get("password", ""),
            hint_text="Введите пароль (пусто — без пароля)",
            multiline=False,
            size_hint=(1, None),
            height=dp(44),
            font_size=sp(15),
            background_color=p["drawer_card"],
            foreground_color=p["text"],
            padding=[dp(12), dp(10), dp(12), dp(10)],
        )
        card.add_widget(inp)

        btn_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(42))
        btn_clear = Button(text="Без пароля", font_size=sp(14), background_normal="", background_color=p["pill_bg"], color=p["text"])
        btn_save = Button(text="Сохранить PIN", font_size=sp(14), background_normal="", background_color=p["blue"], color=(1, 1, 1, 1))

        def _save_pwd(_b):
            new_pwd = inp.text.strip()
            save_settings(password=new_pwd)
            DynamicAirShareHandler.current_password = new_pwd
            modal.dismiss()

        def _no_pwd(_b):
            inp.text = ""
            _save_pwd(_b)

        btn_clear.bind(on_press=_no_pwd)
        btn_save.bind(on_press=_save_pwd)
        btn_row.add_widget(btn_clear)
        btn_row.add_widget(btn_save)
        card.add_widget(btn_row)
        modal.open()

    def open_port_modal(self, *_args):
        modal, card, p = self._create_modal("Port Settings", height_dp=230)
        inp = TextInput(
            text=str(self.server_port),
            hint_text="Порт HTTP-сервера (8080)",
            input_filter="int",
            multiline=False,
            size_hint=(1, None),
            height=dp(44),
            font_size=sp(15),
            background_color=p["drawer_card"],
            foreground_color=p["text"],
            padding=[dp(12), dp(10), dp(12), dp(10)],
        )
        card.add_widget(inp)

        btn_save = Button(
            text="Сохранить порт",
            font_size=sp(14),
            size_hint=(1, None),
            height=dp(42),
            background_normal="",
            background_color=p["blue"],
            color=(1, 1, 1, 1),
        )

        def _save_port(_b):
            try:
                val = int(inp.text.strip())
                if 1024 <= val <= 65535:
                    self.server_port = val
                    save_settings(port=val)
                    self.addr_label.text = f"http://{get_local_ip()}:{self.server_port}"
                    if self.server is not None:
                        self.toggle_server()
                        Clock.schedule_once(lambda _dt: self.start_server_if_needed(), 0.4)
            except Exception:
                pass
            modal.dismiss()

        btn_save.bind(on_press=_save_port)
        card.add_widget(btn_save)
        modal.open()

    def open_devices_modal(self, *_args):
        modal, card, p = self._create_modal("Connected Devices (IP History)", height_dp=290)
        ips = load_settings().get("recent_ips", [])
        txt = "\n".join(f"• {x}" for x in ips[:6]) if ips else "Пока нет сохранённых подключений.\nОткройте адрес со смартфона в браузере на ПК."
        lbl = Label(text=txt, font_size=sp(13.5), color=p["text"], halign="left", valign="top")
        lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        card.add_widget(lbl)

        btn_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(42))
        btn_clr = Button(text="Очистить", font_size=sp(14), background_normal="", background_color=p["pill_bg"], color=p["text"])
        btn_ok = Button(text="Закрыть", font_size=sp(14), background_normal="", background_color=p["blue"], color=(1, 1, 1, 1))

        def _clear(_b):
            save_settings(recent_ips=[])
            lbl.text = "История очищена"

        btn_clr.bind(on_press=_clear)
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        btn_row.add_widget(btn_clr)
        btn_row.add_widget(btn_ok)
        card.add_widget(btn_row)
        modal.open()

    def open_help_modal(self, *_args):
        modal, card, p = self._create_modal("Help & Feedback", height_dp=260)
        lbl = Label(
            text=(
                f"[b]{APP_NAME} v{APP_VERSION}[/b]\n\n"
                "1. Сервер запускается автоматически (кнопка «Transfer» или нажатие по центру радара включает/ставит на паузу).\n"
                "2. Откройте адрес http://<IP>:8080 в браузере на ПК в одной сети Wi-Fi.\n"
                "3. Нажимайте на карточки папок, чтобы выбрать раздел для обмена."
            ),
            markup=True,
            font_size=sp(13),
            color=p["text"],
            halign="left",
        )
        lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        card.add_widget(lbl)
        btn_ok = Button(text="Понятно", font_size=sp(14), size_hint=(1, None), height=dp(42), background_normal="", background_color=p["blue"], color=(1, 1, 1, 1))
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)
        modal.open()


if __name__ == "__main__":
    AirShareApp().run()

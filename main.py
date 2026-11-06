# Main application file - Redesigned Radar Card with Connect/Disconnect, WakeLock Switch,
# Header Status Dot (Green/Red/Yellow), Active Bottom Nav Tabs, and Rounded Glass Modals

import os
import math
import threading
from http.server import SimpleHTTPRequestHandler
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.graphics import (
    Color,
    RoundedRectangle,
    Line,
    Ellipse,
    Triangle,
    PushMatrix,
    PopMatrix,
    Translate,
    Scale,
)
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
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
        "bg": (0.095, 0.102, 0.114, 1),
        "radar_bg": (0.18, 0.192, 0.212, 1),
        "radar_glow": (0.32, 0.35, 0.40, 0.16),
        "card_bg": (0.145, 0.155, 0.172, 1),
        "card_border": (0.27, 0.29, 0.32, 0.85),
        "radar_ring": (0.62, 0.66, 0.72, 0.13),
        "drawer_bg": (0.15, 0.165, 0.185, 0.88),
        "drawer_card": (0.22, 0.24, 0.27, 0.78),
        "drawer_border": (0.40, 0.43, 0.48, 0.62),
        "modal_bg": (0.155, 0.17, 0.19, 0.96),
        "overlay": (0.0, 0.0, 0.0, 0.56),
        "text": (0.96, 0.97, 0.98, 1),
        "subtext": (0.62, 0.65, 0.70, 1),
        "pill_bg": (0.22, 0.24, 0.27, 1),
        "pill_active": (0.29, 0.32, 0.36, 1),
        "amber": (0.88, 0.61, 0.22, 1),
        "blue": (0.38, 0.72, 0.98, 1),
        "green": (0.20, 0.78, 0.46, 1),
        "red": (0.88, 0.28, 0.30, 1),
        "yellow": (0.96, 0.78, 0.18, 1),
        "track": (0.22, 0.235, 0.26, 1),
    },
    "light": {
        "bg": (0.93, 0.94, 0.96, 1),
        "radar_bg": (0.86, 0.88, 0.92, 1),
        "radar_glow": (1.0, 1.0, 1.0, 0.35),
        "card_bg": (0.99, 0.99, 1.0, 1),
        "card_border": (0.80, 0.82, 0.86, 1),
        "radar_ring": (0.35, 0.38, 0.44, 0.14),
        "drawer_bg": (0.95, 0.96, 0.98, 0.90),
        "drawer_card": (0.89, 0.91, 0.95, 0.82),
        "drawer_border": (0.74, 0.77, 0.82, 0.75),
        "modal_bg": (0.96, 0.97, 0.99, 0.98),
        "overlay": (0.0, 0.0, 0.0, 0.36),
        "text": (0.11, 0.12, 0.14, 1),
        "subtext": (0.44, 0.47, 0.53, 1),
        "pill_bg": (0.83, 0.85, 0.89, 1),
        "pill_active": (0.72, 0.76, 0.82, 1),
        "amber": (0.84, 0.54, 0.14, 1),
        "blue": (0.24, 0.62, 0.94, 1),
        "green": (0.16, 0.72, 0.42, 1),
        "red": (0.84, 0.24, 0.26, 1),
        "yellow": (0.90, 0.68, 0.12, 1),
        "track": (0.80, 0.82, 0.86, 1),
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


class StatusDot(Widget):
    """Glowing status indicator dot next to the device name (Green = Online, Red = Stopped, Yellow = Issue)"""

    def __init__(self, dot_color=(0.88, 0.28, 0.30, 1), **kwargs):
        super().__init__(**kwargs)
        self.dot_color = dot_color
        with self.canvas:
            self.halo_col = Color(dot_color[0], dot_color[1], dot_color[2], 0.26)
            self.halo = Ellipse(pos=(0, 0), size=(dp(18), dp(18)))
            self.core_col = Color(*dot_color)
            self.core = Ellipse(pos=(0, 0), size=(dp(10), dp(10)))
        self.bind(pos=self._upd, size=self._upd)
        Clock.schedule_once(self._upd, 0)

    def _upd(self, *_args):
        cx, cy = self.center_x, self.center_y
        hr = dp(8.5)
        cr = dp(4.8)
        self.halo.pos = (cx - hr, cy - hr)
        self.halo.size = (hr * 2, hr * 2)
        self.core.pos = (cx - cr, cy - cr)
        self.core.size = (cr * 2, cr * 2)

    def set_status_color(self, rgba):
        self.dot_color = rgba
        self.halo_col.rgba = (rgba[0], rgba[1], rgba[2], 0.28)
        self.core_col.rgba = rgba


class AnimatedToggleSwitch(ButtonBehavior, Widget):
    """Smooth animated toggle switch: thumb glides right & turns light-blue when ON, glides left & turns white when OFF"""

    thumb_pos = NumericProperty(0.0)

    def __init__(self, active=False, **kwargs):
        super().__init__(**kwargs)
        self.always_release = True
        self.is_active = bool(active)
        self.thumb_pos = 1.0 if self.is_active else 0.0
        with self.canvas:
            self.track_col = Color(0.24, 0.26, 0.30, 1)
            self.track_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            self.border_col = Color(0.40, 0.44, 0.50, 0.65)
            self.track_line = Line(rounded_rectangle=[self.x, self.y, self.width, self.height, dp(14)], width=dp(1.0))
            self.thumb_col = Color(0.96, 0.97, 0.98, 1)
            self.thumb_ellipse = Ellipse(pos=(0, 0), size=(dp(20), dp(20)))
        self.bind(pos=self._upd, size=self._upd, thumb_pos=self._upd)
        Clock.schedule_once(self._upd, 0)

    def _upd(self, *_args):
        w, h = self.width, self.height
        if w <= 2 or h <= 2:
            return
        r = h * 0.5
        self.track_rect.pos = self.pos
        self.track_rect.size = self.size
        self.track_rect.radius = [r]
        self.track_line.rounded_rectangle = [self.x, self.y, w, h, r]

        # Interpolate colors between OFF (white thumb on dark track) and ON (light-blue thumb & glowing track)
        t = max(0.0, min(1.0, self.thumb_pos))
        tr = 0.22 + (0.18 - 0.22) * t
        tg = 0.24 + (0.36 - 0.24) * t
        tb = 0.28 + (0.54 - 0.28) * t
        self.track_col.rgba = (tr, tg, tb, 1.0)
        self.border_col.rgba = (0.38, 0.72, 0.98, 0.75) if t > 0.5 else (0.40, 0.44, 0.50, 0.55)

        cr = 0.97 + (0.42 - 0.97) * t
        cg = 0.98 + (0.76 - 0.98) * t
        cb = 0.99 + (1.00 - 0.99) * t
        self.thumb_col.rgba = (cr, cg, cb, 1.0)

        pad = dp(3.5)
        d = h - pad * 2
        min_x = self.x + pad
        max_x = self.x + w - pad - d
        cur_x = min_x + (max_x - min_x) * t
        cur_y = self.y + pad
        self.thumb_ellipse.pos = (cur_x, cur_y)
        self.thumb_ellipse.size = (d, d)

    def set_active(self, active, animate=True):
        self.is_active = bool(active)
        target = 1.0 if self.is_active else 0.0
        Animation.cancel_all(self, "thumb_pos")
        if animate:
            Animation(thumb_pos=target, duration=0.22, t="out_cubic").start(self)
        else:
            self.thumb_pos = target


class VectorIcon(Widget):
    """Hardware-translated vector canvas icon: guaranteed initial draw + 120 FPS zero-rebuild movement"""

    def __init__(self, icon_type="pc", color=(0.95, 0.96, 0.98, 1), **kwargs):
        super().__init__(**kwargs)
        self.icon_type = icon_type
        self.icon_color = color
        self._drawn = False
        with self.canvas.before:
            PushMatrix()
            self._trans = Translate(self.x, self.y)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._update_pos, size=self._redraw)
        Clock.schedule_once(self._redraw, 0)

    def _update_pos(self, *_args):
        self._trans.x = self.x
        self._trans.y = self.y
        if not self._drawn:
            self._redraw()

    def on_touch_down(self, touch):
        return False

    def on_touch_move(self, touch):
        return False

    def on_touch_up(self, touch):
        return False

    def set_color(self, color):
        if self.icon_color != color:
            self.icon_color = color
            self._redraw()

    def _redraw(self, *_args):
        self._trans.x = self.x
        self._trans.y = self.y
        self.canvas.clear()
        w_full, h_full = self.width, self.height
        s = min(w_full, h_full)
        if s <= 2:
            return
        self._drawn = True
        cx, cy = w_full * 0.5, h_full * 0.5
        lw = max(1.2, dp(1.55))

        with self.canvas:
            Color(*self.icon_color)

            if self.icon_type == "pc":
                mw, mh = s * 0.76, s * 0.52
                x0, y0 = cx - mw * 0.5, cy - mh * 0.22
                Color(0.13, 0.14, 0.16, 0.90)
                RoundedRectangle(pos=(x0 + dp(2), y0 + dp(2)), size=(mw - dp(4), mh - dp(4)), radius=[dp(4)])
                Color(*self.icon_color)
                Line(rounded_rectangle=[x0, y0, mw, mh, dp(5)], width=dp(2.0))
                neck_h = s * 0.13
                Line(points=[cx - mw * 0.08, y0, cx - mw * 0.11, y0 - neck_h], width=dp(1.6))
                Line(points=[cx + mw * 0.08, y0, cx + mw * 0.11, y0 - neck_h], width=dp(1.6))
                Line(points=[cx - mw * 0.28, y0 - neck_h, cx + mw * 0.28, y0 - neck_h], width=dp(2.0))

            elif self.icon_type == "wifi":
                r2, r3 = s * 0.26, s * 0.42
                by = cy - s * 0.18
                Ellipse(pos=(cx - dp(1.8), by - dp(1.8)), size=(dp(3.6), dp(3.6)))
                Line(circle=(cx, by, r2, -44, 44), width=dp(1.4))
                Line(circle=(cx, by, r3, -46, 46), width=dp(1.4))

            elif self.icon_type == "gear":
                r_outer = s * 0.27
                r_inner = s * 0.12
                Line(circle=(cx, cy, r_inner), width=dp(1.5))
                Line(circle=(cx, cy, r_outer * 0.82), width=dp(1.7))
                for deg in range(0, 360, 45):
                    rad = math.radians(deg)
                    x1 = cx + math.cos(rad) * (r_outer * 0.80)
                    y1 = cy + math.sin(rad) * (r_outer * 0.80)
                    x2 = cx + math.cos(rad) * (r_outer * 1.02)
                    y2 = cy + math.sin(rad) * (r_outer * 1.02)
                    Line(points=[x1, y1, x2, y2], width=dp(2.1))

            elif self.icon_type == "copy":
                w, h = s * 0.36, s * 0.44
                Line(rounded_rectangle=[cx - w * 0.68, cy - h * 0.28, w, h, dp(3)], width=lw)
                Color(0.18, 0.20, 0.22, 1)
                RoundedRectangle(pos=(cx - w * 0.28, cy - h * 0.68), size=(w, h), radius=[dp(3)])
                Color(*self.icon_color)
                Line(rounded_rectangle=[cx - w * 0.28, cy - h * 0.68, w, h, dp(3)], width=lw)

            elif self.icon_type == "download":
                Color(0.88, 0.61, 0.22, 0.15)
                Ellipse(pos=(cx - s * 0.40, cy - s * 0.40), size=(s * 0.80, s * 0.80))
                Color(*self.icon_color)
                top_y = cy + s * 0.25
                bot_y = cy - s * 0.10
                aw = s * 0.20
                Line(points=[cx, top_y, cx, bot_y], width=dp(2.1))
                Line(points=[cx - aw, bot_y + aw * 0.85, cx, bot_y, cx + aw, bot_y + aw * 0.85], width=dp(2.1))
                tray_y = cy - s * 0.24
                Line(points=[cx - s * 0.26, tray_y, cx + s * 0.26, tray_y], width=dp(2.1))

            elif self.icon_type == "gallery":
                cw, ch = s * 0.62, s * 0.46
                Color(0.32, 0.35, 0.39, 0.75)
                RoundedRectangle(pos=(cx - cw * 0.72, cy - ch * 0.44), size=(cw * 0.65, ch * 0.86), radius=[dp(5)])
                RoundedRectangle(pos=(cx + cw * 0.07, cy - ch * 0.44), size=(cw * 0.65, ch * 0.86), radius=[dp(5)])
                Color(0.76, 0.79, 0.84, 0.98)
                RoundedRectangle(pos=(cx - cw * 0.50, cy - ch * 0.50), size=(cw, ch), radius=[dp(6)])
                Color(0.24, 0.26, 0.30, 0.95)
                Triangle(points=[cx - cw * 0.42, cy - ch * 0.46, cx - cw * 0.06, cy + ch * 0.06, cx + cw * 0.26, cy - ch * 0.46])
                Color(0.90, 0.64, 0.22, 1)
                Ellipse(pos=(cx - cw * 0.22, cy + ch * 0.06), size=(dp(5.5), dp(5.5)))

            elif self.icon_type == "document":
                dw, dh = s * 0.50, s * 0.62
                x0, y0 = cx - dw * 0.5, cy - dh * 0.5
                Color(0.62, 0.65, 0.70, 0.95)
                RoundedRectangle(pos=(x0, y0), size=(dw, dh), radius=[dp(5)])
                fold = dw * 0.32
                Color(0.38, 0.41, 0.46, 1)
                Triangle(points=[x0 + dw - fold, y0 + dh, x0 + dw, y0 + dh - fold, x0 + dw - fold, y0 + dh - fold])

            elif self.icon_type == "zip_badge":
                Color(0.68, 0.47, 0.20, 1)
                RoundedRectangle(pos=(dp(2), dp(2)), size=(w_full - dp(4), h_full - dp(4)), radius=[dp(10)])
                Color(0.84, 0.62, 0.32, 0.55)
                Line(rounded_rectangle=[dp(2), dp(2), w_full - dp(4), h_full - dp(4), dp(10)], width=dp(1.0))
                Color(0.98, 0.90, 0.74, 1)
                for step in range(3):
                    ty = cy + s * 0.24 - step * dp(4.2)
                    Line(points=[cx - dp(2.5), ty, cx + dp(2.5), ty], width=dp(1.4))
                RoundedRectangle(pos=(cx - dp(3.5), cy - dp(6)), size=(dp(7), dp(8)), radius=[dp(2)])
                Color(0.68, 0.47, 0.20, 1)
                Ellipse(pos=(cx - dp(1.5), cy - dp(3.5)), size=(dp(3), dp(3)))

            elif self.icon_type == "img_badge":
                Color(0.24, 0.26, 0.29, 1)
                RoundedRectangle(pos=(dp(2), dp(2)), size=(w_full - dp(4), h_full - dp(4)), radius=[dp(10)])
                Color(0.36, 0.39, 0.44, 0.7)
                Line(rounded_rectangle=[dp(2), dp(2), w_full - dp(4), h_full - dp(4), dp(10)], width=dp(1.0))
                Color(0.72, 0.75, 0.80, 0.95)
                mw, mh = s * 0.52, s * 0.32
                Triangle(points=[cx - mw * 0.52, cy - mh * 0.55, cx - mw * 0.10, cy + mh * 0.32, cx + mw * 0.28, cy - mh * 0.55])
                Color(0.54, 0.57, 0.62, 0.95)
                Triangle(points=[cx - mw * 0.02, cy - mh * 0.55, cx + mw * 0.26, cy + mh * 0.12, cx + mw * 0.54, cy - mh * 0.55])
                Color(0.82, 0.85, 0.90, 1)
                Ellipse(pos=(cx - mw * 0.38, cy + mh * 0.18), size=(dp(4.2), dp(4.2)))

            elif self.icon_type == "transfer":
                dx = s * 0.25
                dy = s * 0.12
                aw = s * 0.10
                Line(points=[cx - dx, cy + dy, cx + dx, cy + dy], width=dp(1.8))
                Line(points=[cx + dx - aw, cy + dy + aw, cx + dx, cy + dy, cx + dx - aw, cy + dy - aw], width=dp(1.8))
                Line(points=[cx + dx, cy - dy, cx - dx, cy - dy], width=dp(1.8))
                Line(points=[cx - dx + aw, cy - dy + aw, cx - dx, cy - dy, cx - dx + aw, cy - dy - aw], width=dp(1.8))

            elif self.icon_type == "folder":
                fw, fh = s * 0.54, s * 0.38
                x0, y0 = cx - fw * 0.5, cy - fh * 0.5
                Line(
                    points=[
                        x0,
                        y0 + fh * 0.82,
                        x0,
                        y0,
                        x0 + fw,
                        y0,
                        x0 + fw,
                        y0 + fh * 0.72,
                        x0 + fw * 0.46,
                        y0 + fh * 0.72,
                        x0 + fw * 0.36,
                        y0 + fh * 0.95,
                        x0,
                        y0 + fh * 0.95,
                        x0,
                        y0 + fh * 0.82,
                    ],
                    width=lw,
                    joint="round",
                )

            elif self.icon_type == "phone":
                w, h = s * 0.36, s * 0.60
                Line(rounded_rectangle=[cx - w * 0.5, cy - h * 0.5, w, h, dp(3.5)], width=lw)
                Ellipse(pos=(cx - dp(1.3), cy - h * 0.34), size=(dp(2.6), dp(2.6)))

            elif self.icon_type == "lock":
                w, h = s * 0.44, s * 0.35
                x0, y0 = cx - w * 0.5, cy - h * 0.62
                Line(rounded_rectangle=[x0, y0, w, h, dp(3)], width=lw)
                Line(circle=(cx, y0 + h, w * 0.28, -90, 90), width=lw)
                Ellipse(pos=(cx - dp(1.5), y0 + h * 0.42), size=(dp(3), dp(3)))

            elif self.icon_type == "sliders":
                dx = s * 0.27
                y1, y2 = cy + s * 0.14, cy - s * 0.14
                Line(points=[cx - dx, y1, cx + dx, y1], width=lw)
                Line(points=[cx - dx, y2, cx + dx, y2], width=lw)
                Ellipse(pos=(cx - dx * 0.35 - dp(3), y1 - dp(3)), size=(dp(6), dp(6)))
                Ellipse(pos=(cx + dx * 0.35 - dp(3), y2 - dp(3)), size=(dp(6), dp(6)))

            elif self.icon_type == "info":
                r = s * 0.31
                Line(circle=(cx, cy, r), width=lw)
                Line(points=[cx, cy - r * 0.36, cx, cy + r * 0.08], width=lw)
                Ellipse(pos=(cx - dp(1.3), cy + r * 0.32), size=(dp(2.6), dp(2.6)))

            elif self.icon_type == "chevron":
                d = s * 0.16
                Line(points=[cx - d * 0.5, cy + d, cx + d * 0.5, cy, cx - d * 0.5, cy - d], width=lw)

            elif self.icon_type == "check":
                d = s * 0.22
                Line(points=[cx - d, cy, cx - d * 0.25, cy - d * 0.75, cx + d, cy + d * 0.65], width=dp(2.0))


class VectorIconButton(ButtonBehavior, VectorIcon):
    """Standalone clickable vector icon button with spring press animation"""

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
        Animation.cancel_all(self, "opacity")
        Animation(opacity=0.55, duration=0.07).start(self)

    def on_release(self):
        Animation.cancel_all(self, "opacity")
        Animation(opacity=1.0, duration=0.16, t="out_quad").start(self)


class RoundedCard(BoxLayout):
    """Universal rounded card container with hardware-accelerated scale/offset support"""

    scale_val = NumericProperty(1.0)
    offset_x = NumericProperty(0.0)
    offset_y = NumericProperty(0.0)

    def __init__(self, bg_color, border_color=(0, 0, 0, 0), radius=dp(18), **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.border_color = border_color
        self.radius_val = radius
        with self.canvas.before:
            PushMatrix()
            self._mat_trans1 = Translate(0, 0)
            self._mat_scale = Scale(1.0, 1.0, 1.0)
            self._mat_trans2 = Translate(0, 0)
            self.col = Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius_val])
            self.b_col = Color(*self.border_color)
            self.line = Line(
                rounded_rectangle=[self.x, self.y, self.width, self.height, max(1, self.radius_val)],
                width=dp(1.0),
            )
        with self.canvas.after:
            PopMatrix()
        self.bind(
            pos=self._update,
            size=self._update,
            scale_val=self._update_matrix,
            offset_x=self._update_matrix,
            offset_y=self._update_matrix,
        )

    def _update_matrix(self, *_args):
        cx, cy = self.center_x, self.center_y
        self._mat_trans1.x = cx + self.offset_x
        self._mat_trans1.y = cy + self.offset_y
        self._mat_scale.x = self.scale_val
        self._mat_scale.y = self.scale_val
        self._mat_trans2.x = -cx
        self._mat_trans2.y = -cy

    def _update(self, *_args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        if self.width > 2 and self.height > 2:
            self.line.rounded_rectangle = [
                self.x,
                self.y,
                self.width,
                self.height,
                min(self.radius_val, self.height * 0.5),
            ]
        self._update_matrix()

    def update_colors(self, bg_color, border_color=(0, 0, 0, 0)):
        self.bg_color = bg_color
        self.border_color = border_color
        self.col.rgba = bg_color
        self.b_col.rgba = border_color


class ClickableCard(ButtonBehavior, RoundedCard):
    """Interactive RoundedCard with smooth macOS-style tactile spring bounce on tap"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.always_release = True

    def on_press(self):
        Animation.cancel_all(self, "scale_val")
        Animation(scale_val=0.95, duration=0.07, t="out_quad").start(self)

    def on_release(self):
        Animation.cancel_all(self, "scale_val")
        Animation(scale_val=1.0, duration=0.22, t="out_back").start(self)


class RoundedActionButton(ClickableCard):
    """Sleek rounded pill button replacing standard sharp-cornered Kivy Buttons inside modals"""

    def __init__(self, text="", bg_color=(0.38, 0.72, 0.98, 1), border_color=(0, 0, 0, 0), text_color=(1, 1, 1, 1), font_size=sp(14), radius=dp(15), **kwargs):
        super().__init__(bg_color=bg_color, border_color=border_color, radius=radius, **kwargs)
        self.lbl = Label(
            text=f"[b]{text}[/b]",
            markup=True,
            font_size=font_size,
            color=text_color,
            halign="center",
            valign="middle",
        )
        self.lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.add_widget(self.lbl)

    def set_text(self, text):
        self.lbl.text = f"[b]{text}[/b]"


class DrawerOverlay(Widget):
    """Animated scrim overlay that smoothly fades in/out and only intercepts touches when open"""

    scrim_alpha = NumericProperty(0.0)

    def __init__(self, close_callback, **kwargs):
        super().__init__(**kwargs)
        self.close_callback = close_callback
        self.is_open = False
        self.base_rgb = (0, 0, 0)
        with self.canvas:
            self.col = Color(0, 0, 0, 0)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._upd, size=self._upd, scrim_alpha=self._upd_alpha)

    def _upd(self, *_args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def _upd_alpha(self, *_args):
        self.col.rgba = (self.base_rgb[0], self.base_rgb[1], self.base_rgb[2], self.scrim_alpha)

    def animate_to(self, target_rgba, duration=0.28):
        self.base_rgb = (target_rgba[0], target_rgba[1], target_rgba[2])
        Animation.cancel_all(self, "scrim_alpha")
        Animation(scrim_alpha=target_rgba[3], duration=duration, t="out_quad").start(self)

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
    """Floating side drawer with smooth GPU spring animation"""

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
    """Full-width clickable menu row inside the side drawer with spring bounce"""

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
        Animation.cancel_all(self, "scale_val")
        Animation(scale_val=0.96, duration=0.07).start(self)

    def on_release(self):
        self.update_colors((0, 0, 0, 0), (0, 0, 0, 0))
        Animation.cancel_all(self, "scale_val")
        Animation(scale_val=1.0, duration=0.18, t="out_back").start(self)


class RadarCard(RoundedCard):
    """Top radar card with soft center glow and 4 concentric rings"""

    def __init__(self, bg_color, border_color, ring_color, glow_color, **kwargs):
        super().__init__(bg_color=bg_color, border_color=border_color, radius=dp(24), **kwargs)
        with self.canvas.before:
            self.glow_col = Color(*glow_color)
            self.glow_outer = Ellipse(pos=(0, 0), size=(10, 10))
            self.ring_col = Color(*ring_color)
            self.ring1 = Line(circle=(0, 0, 10), width=dp(1.0))
            self.ring2 = Line(circle=(0, 0, 20), width=dp(1.0))
            self.ring3 = Line(circle=(0, 0, 30), width=dp(1.0))
            self.ring4 = Line(circle=(0, 0, 40), width=dp(1.0))
        self.bind(pos=self._update_rings, size=self._update_rings)

    def _update_rings(self, *_args):
        cx = self.center_x
        cy = self.y + self.height * 0.62
        max_r = min(self.width, self.height) * 0.45
        glow_r = max_r * 0.72
        self.glow_outer.pos = (cx - glow_r, cy - glow_r)
        self.glow_outer.size = (glow_r * 2, glow_r * 2)
        self.ring1.circle = (cx, cy, max_r * 0.40)
        self.ring2.circle = (cx, cy, max_r * 0.60)
        self.ring3.circle = (cx, cy, max_r * 0.80)
        self.ring4.circle = (cx, cy, max_r * 1.00)

    def update_radar_colors(self, bg_color, border_color, ring_color, glow_color):
        self.update_colors(bg_color, border_color)
        self.ring_col.rgba = ring_color
        self.glow_col.rgba = glow_color


class SlimProgressBar(Widget):
    """Sleek rounded progress bar scaled with dp() that never blocks touches"""

    def __init__(self, percent=0.45, track_color=(0.22, 0.235, 0.26, 1), fill_color=(0.88, 0.61, 0.22, 1), **kwargs):
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
        self.f_rect.size = (max(dp(10), self.width * self.percent), self.height)

    def set_percent(self, p):
        self.percent = min(1.0, max(0.0, p))
        self._upd()

    def update_bar_colors(self, track_color, fill_color):
        self.t_col.rgba = track_color
        self.f_col.rgba = fill_color


class NavTabItem(ButtonBehavior, BoxLayout):
    """Bottom navigation tab item with active pill background, vector icon, and spring bounce"""

    def __init__(self, icon_type, title_text, is_active=False, pill_color=(0.29, 0.32, 0.36, 1), text_color=(1, 1, 1, 1), **kwargs):
        super().__init__(orientation="vertical", spacing=dp(2), padding=[dp(4), dp(4), dp(4), dp(4)], **kwargs)
        self.always_release = True
        self.is_active = is_active
        self.pill_color = pill_color

        self.pill_wrap = AnchorLayout(size_hint=(1, 0.58))
        self.pill_bg = RoundedCard(
            bg_color=pill_color if is_active else (0, 0, 0, 0),
            border_color=(0.44, 0.48, 0.54, 0.50) if is_active else (0, 0, 0, 0),
            radius=dp(15),
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
        Animation.cancel_all(self.pill_bg, "scale_val")
        Animation(scale_val=0.88, duration=0.07, t="out_quad").start(self.pill_bg)

    def on_release(self):
        Animation.cancel_all(self.pill_bg, "scale_val")
        Animation(scale_val=1.0, duration=0.24, t="out_back").start(self.pill_bg)

    def set_active_style(self, is_active, pill_color, text_color):
        self.is_active = is_active
        border_c = (0.44, 0.48, 0.54, 0.50) if is_active else (0, 0, 0, 0)
        self.pill_bg.update_colors(pill_color if is_active else (0, 0, 0, 0), border_c)
        self.icon_widget.set_color(text_color)
        self.label.color = text_color


class MacModalContainer(FloatLayout):
    """macOS-style genie/spring popup modal that blooms smoothly out of the clicked button"""

    scrim_alpha = NumericProperty(0.0)

    def __init__(self, card_widget, origin_pos=None, scrim_rgba=(0, 0, 0, 0.56), on_dismiss_cb=None, **kwargs):
        super().__init__(size_hint=(1, 1), pos_hint={"x": 0, "y": 0}, **kwargs)
        self.card = card_widget
        self.origin_pos = origin_pos
        self.scrim_rgba = scrim_rgba
        self.on_dismiss_cb = on_dismiss_cb
        self.is_closing = False

        with self.canvas.before:
            self.scrim_col = Color(scrim_rgba[0], scrim_rgba[1], scrim_rgba[2], 0.0)
            self.scrim_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._upd_scrim, size=self._upd_scrim, scrim_alpha=self._upd_alpha)

        self.add_widget(self.card)

    def _upd_scrim(self, *_args):
        self.scrim_rect.pos = self.pos
        self.scrim_rect.size = self.size

    def _upd_alpha(self, *_args):
        self.col.rgba = (self.scrim_rgba[0], self.scrim_rgba[1], self.scrim_rgba[2], self.scrim_alpha)

    def animate_open(self):
        cx, cy = Window.width * 0.5, Window.height * 0.5
        if self.origin_pos:
            ox, oy = self.origin_pos
            dx = (ox - cx) * 0.55
            dy = (oy - cy) * 0.55
        else:
            dx, dy = 0, -dp(45)

        self.card.scale_val = 0.22
        self.card.offset_x = dx
        self.card.offset_y = dy
        self.card.opacity = 0.0

        Animation(scrim_alpha=self.scrim_rgba[3], duration=0.22, t="out_quad").start(self)
        anim = Animation(
            scale_val=1.0,
            offset_x=0.0,
            offset_y=0.0,
            opacity=1.0,
            duration=0.30,
            t="out_back",
        )
        anim.start(self.card)

    def dismiss(self, *_args):
        if self.is_closing:
            return
        self.is_closing = True
        if callable(self.on_dismiss_cb):
            self.on_dismiss_cb()

        cx, cy = Window.width * 0.5, Window.height * 0.5
        if self.origin_pos:
            ox, oy = self.origin_pos
            dx = (ox - cx) * 0.45
            dy = (oy - cy) * 0.45
        else:
            dx, dy = 0, -dp(35)

        Animation(scrim_alpha=0.0, duration=0.18, t="in_quad").start(self)
        anim = Animation(
            scale_val=0.25,
            offset_x=dx,
            offset_y=dy,
            opacity=0.0,
            duration=0.18,
            t="in_back",
        )
        anim.bind(on_complete=self._remove_self)
        anim.start(self.card)

    def _remove_self(self, *_args):
        if self.parent:
            self.parent.remove_widget(self)

    def on_touch_down(self, touch):
        if self.card.collide_point(*touch.pos):
            super().on_touch_down(touch)
            return True
        self.dismiss()
        return True

    def on_touch_move(self, touch):
        if self.card.collide_point(*touch.pos):
            super().on_touch_move(touch)
        return True

    def on_touch_up(self, touch):
        super().on_touch_up(touch)
        return True


class AirShareApp(App):
    server = None
    is_stopping = False
    has_server_error = False
    active_folder_key = "All Storage"
    active_nav_tab = "transfer"
    keep_alive_locked = True
    _wake_lock = None
    transfer_history = []
    active_modal = None

    def _get_folder_map(self):
        base = STORAGE_PATH if os.path.isdir(STORAGE_PATH) else os.path.expanduser("~")
        return {
            "All Storage": (base, "folder", "Вся память устройства"),
            "Downloads": (os.path.join(base, "Download"), "download", "Загрузки из браузера и мессенджеров"),
            "Camera Roll": (os.path.join(base, "DCIM"), "gallery", "Фотографии и видео с камеры"),
            "Documents": (os.path.join(base, "Documents"), "document", "Документы и рабочие файлы"),
        }

    def get_connection_url(self):
        """Build exact copy-paste URL for PC browser, including basic auth PIN if set"""
        ip = get_local_ip()
        pwd = (self.saved_password or "").strip()
        if pwd:
            return f"http://airshare:{pwd}@{ip}:{self.server_port}"
        return f"http://{ip}:{self.server_port}"

    def update_connection_url_display(self):
        url = self.get_connection_url()
        self.addr_label.text = url
        length = len(url)
        if length > 38:
            self.addr_label.font_size = sp(10.5)
        elif length > 30:
            self.addr_label.font_size = sp(11.5)
        else:
            self.addr_label.font_size = sp(13.5)

    def set_keep_alive(self, enabled):
        """Enable or disable background wake lock safely without crashing"""
        self.keep_alive_locked = bool(enabled)
        if hasattr(self, "keep_alive_switch"):
            self.keep_alive_switch.set_active(self.keep_alive_locked, animate=True)
        try:
            Window.allow_screensaver = not self.keep_alive_locked
        except Exception:
            pass

        try:
            from kivy.utils import platform
            if platform == "android":
                from jnius import autoclass
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = getattr(PythonActivity, "mActivity", None)
                if activity is not None:
                    Context = autoclass("android.content.Context")
                    PowerManager = autoclass("android.os.PowerManager")
                    if self.keep_alive_locked:
                        if self._wake_lock is None:
                            pm = activity.getSystemService(Context.POWER_SERVICE)
                            if pm is not None:
                                self._wake_lock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AirSharePC::ServerWakeLock")
                        if self._wake_lock is not None and not self._wake_lock.isHeld():
                            self._wake_lock.acquire()
                    else:
                        if self._wake_lock is not None and self._wake_lock.isHeld():
                            self._wake_lock.release()
        except Exception:
            pass

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
        # ГЛАВНЫЙ ЭКРАН (Без Shared Folders, с индикатором статуса и кнопкой Connect/Disconnect)
        # =====================================================================
        self.main_content = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(14), dp(18), dp(16)],
            spacing=dp(14),
        )

        # 1. Верхняя шапка: Имя устройства + Индикатор (Зелёный/Красный/Жёлтый) слева, Wi-Fi справа
        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(42), spacing=dp(8))
        name_box = BoxLayout(orientation="horizontal", size_hint=(0.58, 1), spacing=dp(8))

        self.status_dot = StatusDot(
            dot_color=p["red"],
            size_hint=(None, None),
            size=(dp(18), dp(18)),
            pos_hint={"center_y": 0.5},
        )

        dev_name = get_device_info()
        self.device_label = Label(
            text=f"[b]{dev_name}[/b]",
            markup=True,
            font_size=sp(20) if len(dev_name) <= 14 else sp(16.5),
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
            size_hint=(1, 1),
        )
        self.device_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        name_box.add_widget(self.status_dot)
        name_box.add_widget(self.device_label)

        wifi_anchor = AnchorLayout(anchor_x="right", anchor_y="center", size_hint=(0.42, 1))
        self.wifi_pill = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(17),
            orientation="horizontal",
            size_hint=(None, None),
            size=(dp(140), dp(34)),
            padding=[dp(12), dp(4), dp(12), dp(4)],
            spacing=dp(6),
        )
        self.wifi_icon = VectorIcon(icon_type="wifi", color=p["text"], size_hint=(None, 1), width=dp(18))
        self.wifi_label = Label(text="Wi-Fi 6 • 5GHz", font_size=sp(12), halign="center", valign="middle")
        self.wifi_pill.add_widget(self.wifi_icon)
        self.wifi_pill.add_widget(self.wifi_label)
        self.wifi_pill.bind(on_press=self.refresh_network_status)
        wifi_anchor.add_widget(self.wifi_pill)

        header.add_widget(name_box)
        header.add_widget(wifi_anchor)
        self.main_content.add_widget(header)

        # 2. Главная карточка радара: Иконка ПК + Кнопка Connect/Disconnect + Ползунок блокировки + URL
        self.radar_card = RadarCard(
            bg_color=p["radar_bg"],
            border_color=p["card_border"],
            ring_color=p["radar_ring"],
            glow_color=p["radar_glow"],
            orientation="vertical",
            padding=[dp(16), dp(20), dp(16), dp(16)],
            spacing=dp(10),
            size_hint=(1, 0.54),
        )

        # Иконка монитора в центре колец радара
        icon_holder = AnchorLayout(size_hint=(1, 0.30))
        self.monitor_icon = VectorIcon(icon_type="pc", color=p["text"], size_hint=(None, None), size=(dp(68), dp(54)))
        icon_holder.add_widget(self.monitor_icon)

        # Крупная кнопка Connect (зелёная) / Disconnect (красная) с плавной анимацией
        btn_anchor = AnchorLayout(size_hint=(1, 0.24))
        self.connect_btn = RoundedActionButton(
            text="Connect",
            bg_color=p["green"],
            border_color=(1, 1, 1, 0.18),
            text_color=(1, 1, 1, 1),
            font_size=sp(17),
            radius=dp(23),
            size_hint=(None, None),
            size=(dp(190), dp(46)),
        )
        self.connect_btn.bind(on_press=self.toggle_server)
        btn_anchor.add_widget(self.connect_btn)

        # Ползунок «Активен при заблокированном экране» под кнопкой Connect/Disconnect
        keep_alive_anchor = AnchorLayout(size_hint=(1, 0.20))
        self.keep_alive_row = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(16),
            orientation="horizontal",
            size_hint=(0.92, None),
            height=dp(40),
            padding=[dp(14), dp(6), dp(12), dp(6)],
            spacing=dp(10),
        )
        self.keep_alive_label = Label(
            text="Активен при заблокированном экране",
            font_size=sp(12),
            halign="left",
            valign="middle",
            size_hint=(1, 1),
        )
        self.keep_alive_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        self.keep_alive_switch = AnimatedToggleSwitch(
            active=self.keep_alive_locked,
            size_hint=(None, None),
            size=(dp(48), dp(26)),
            pos_hint={"center_y": 0.5},
        )
        self.keep_alive_switch.bind(on_press=lambda *_: self.set_keep_alive(not self.keep_alive_locked))
        self.keep_alive_row.bind(on_press=lambda *_: self.set_keep_alive(not self.keep_alive_locked))

        self.keep_alive_row.add_widget(self.keep_alive_label)
        self.keep_alive_row.add_widget(self.keep_alive_switch)
        keep_alive_anchor.add_widget(self.keep_alive_row)

        # Нижняя капсула с адресом (адаптивная ширина + авто-размер шрифта без вылезания за края)
        addr_row = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 0.22),
            spacing=dp(8),
            padding=[dp(4), dp(2), dp(4), dp(2)],
        )
        self.addr_pill = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(19),
            size_hint=(1, None),
            height=dp(40),
            pos_hint={"center_y": 0.5},
            padding=[dp(12), dp(4), dp(12), dp(4)],
        )
        self.addr_label = Label(
            text="",
            font_size=sp(12),
            halign="center",
            valign="middle",
            shorten=True,
            shorten_from="center",
        )
        self.addr_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.addr_pill.add_widget(self.addr_label)
        self.addr_pill.bind(on_press=self.copy_address)

        self.copy_btn = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(14),
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            pos_hint={"center_y": 0.5},
        )
        self.copy_icon = VectorIcon(icon_type="copy", color=p["text"], size_hint=(1, 1))
        self.copy_btn.add_widget(self.copy_icon)
        self.copy_btn.bind(on_press=self.copy_address)

        addr_row.add_widget(self.addr_pill)
        addr_row.add_widget(self.copy_btn)

        self.radar_card.add_widget(icon_holder)
        self.radar_card.add_widget(btn_anchor)
        self.radar_card.add_widget(keep_alive_anchor)
        self.radar_card.add_widget(addr_row)
        self.main_content.add_widget(self.radar_card)

        # 3. Заголовок и карточка Recent Transfers
        self.transfers_header = Label(
            text="[b]Recent Transfers[/b]",
            markup=True,
            font_size=sp(16),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp(24),
        )
        self.transfers_header.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.main_content.add_widget(self.transfers_header)

        self.transfers_card = ClickableCard(
            bg_color=p["card_bg"],
            border_color=p["card_border"],
            radius=dp(18),
            orientation="vertical",
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(10),
            size_hint=(1, 0.28),
        )
        self.transfers_card.bind(on_press=self.open_transfers_modal)

        row1 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5))
        ico1 = VectorIcon(icon_type="zip_badge", size_hint=(None, None), size=(dp(42), dp(42)), pos_hint={"center_y": 0.5})
        info1 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top1 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20))
        self.tr1_name = Label(text="Project_Archive.zip", font_size=sp(14), halign="left", valign="middle", size_hint=(0.76, 1))
        self.tr1_name.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.tr1_pct = Label(text="100%", font_size=sp(13), halign="right", valign="middle", size_hint=(0.24, 1))
        self.tr1_pct.bind(size=lambda i, v: setattr(i, "text_size", v))
        top1.add_widget(self.tr1_name)
        top1.add_widget(self.tr1_pct)
        self.tr1_bar = SlimProgressBar(percent=1.0, track_color=p["track"], fill_color=p["amber"], size_hint=(1, None), height=dp(4.2))
        self.tr1_sub = Label(text="Completed", font_size=sp(11.5), halign="left", valign="middle", size_hint=(1, None), height=dp(16))
        self.tr1_sub.bind(size=lambda i, v: setattr(i, "text_size", v))
        info1.add_widget(top1)
        info1.add_widget(self.tr1_bar)
        info1.add_widget(self.tr1_sub)
        row1.add_widget(ico1)
        row1.add_widget(info1)

        row2 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5))
        ico2 = VectorIcon(icon_type="img_badge", size_hint=(None, None), size=(dp(42), dp(42)), pos_hint={"center_y": 0.5})
        info2 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top2 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20))
        self.tr2_name = Label(text="IMG_8492.raw", font_size=sp(14), halign="left", valign="middle", size_hint=(0.76, 1))
        self.tr2_name.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.tr2_pct = Label(text="64%", font_size=sp(13), halign="right", valign="middle", size_hint=(0.24, 1))
        self.tr2_pct.bind(size=lambda i, v: setattr(i, "text_size", v))
        top2.add_widget(self.tr2_name)
        top2.add_widget(self.tr2_pct)
        self.tr2_bar = SlimProgressBar(percent=0.64, track_color=p["track"], fill_color=p["blue"], size_hint=(1, None), height=dp(4.2))
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

        # 4. Нижняя навигационная панель с подсветкой выбранной вкладки (Transfer, Files, Devices, Settings)
        self.bottom_nav = RoundedCard(
            bg_color=p["card_bg"],
            border_color=p["card_border"],
            radius=dp(26),
            orientation="horizontal",
            padding=[dp(10), dp(6), dp(10), dp(6)],
            spacing=dp(4),
            size_hint=(1, None),
            height=dp(64),
        )

        self.nav_transfer = NavTabItem("transfer", "Transfer", is_active=True, pill_color=p["pill_active"], text_color=p["text"])
        self.nav_transfer.bind(

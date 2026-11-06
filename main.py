# Main application file - AirShare PC v1.1.0
# Includes StatusDot (Green/Red/Yellow), Connect/Disconnect button, animated WakeLock switch,
# auto-auth URL without overflow, active bottom nav tabs, and macOS-style spring modals

import os, math, threading
from http.server import SimpleHTTPRequestHandler
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse, Triangle, PushMatrix, PopMatrix, Translate, Scale
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.animation import Animation

from config import SERVER_PORT, APP_NAME, APP_VERSION, STORAGE_PATH
from server import ReusableThreadingServer, AirShareHandler
from utils import (
    get_local_ip, get_device_info, get_storage_stats,
    request_android_full_storage, load_settings, save_settings, get_device_theme,
)

THEMES = {
    "dark": {
        "bg": (0.095, 0.102, 0.114, 1), "radar_bg": (0.18, 0.192, 0.212, 1), "radar_glow": (0.32, 0.35, 0.40, 0.16),
        "card_bg": (0.145, 0.155, 0.172, 1), "card_border": (0.27, 0.29, 0.32, 0.85), "radar_ring": (0.62, 0.66, 0.72, 0.13),
        "drawer_bg": (0.15, 0.165, 0.185, 0.88), "drawer_card": (0.22, 0.24, 0.27, 0.78), "drawer_border": (0.40, 0.43, 0.48, 0.62),
        "modal_bg": (0.155, 0.17, 0.19, 0.96), "overlay": (0.0, 0.0, 0.0, 0.56), "text": (0.96, 0.97, 0.98, 1),
        "subtext": (0.62, 0.65, 0.70, 1), "pill_bg": (0.22, 0.24, 0.27, 1), "pill_active": (0.29, 0.32, 0.36, 1),
        "amber": (0.88, 0.61, 0.22, 1), "blue": (0.38, 0.72, 0.98, 1), "green": (0.20, 0.78, 0.46, 1),
        "red": (0.88, 0.28, 0.30, 1), "yellow": (0.96, 0.78, 0.18, 1), "track": (0.22, 0.235, 0.26, 1),
    },
    "light": {
        "bg": (0.93, 0.94, 0.96, 1), "radar_bg": (0.86, 0.88, 0.92, 1), "radar_glow": (1.0, 1.0, 1.0, 0.35),
        "card_bg": (0.99, 0.99, 1.0, 1), "card_border": (0.80, 0.82, 0.86, 1), "radar_ring": (0.35, 0.38, 0.44, 0.14),
        "drawer_bg": (0.95, 0.96, 0.98, 0.90), "drawer_card": (0.89, 0.91, 0.95, 0.82), "drawer_border": (0.74, 0.77, 0.82, 0.75),
        "modal_bg": (0.96, 0.97, 0.99, 0.98), "overlay": (0.0, 0.0, 0.0, 0.36), "text": (0.11, 0.12, 0.14, 1),
        "subtext": (0.44, 0.47, 0.53, 1), "pill_bg": (0.83, 0.85, 0.89, 1), "pill_active": (0.72, 0.76, 0.82, 1),
        "amber": (0.84, 0.54, 0.14, 1), "blue": (0.24, 0.62, 0.94, 1), "green": (0.16, 0.72, 0.42, 1),
        "red": (0.84, 0.24, 0.26, 1), "yellow": (0.90, 0.68, 0.12, 1), "track": (0.80, 0.82, 0.86, 1),
    },
}


def _lbl(text="", size=14, halign="left", valign="middle", markup=False, **kw):
    w = Label(text=text, font_size=sp(size), halign=halign, valign=valign, markup=markup, **kw)
    w.bind(size=lambda i, v: setattr(i, "text_size", v))
    return w


class DynamicAirShareHandler(AirShareHandler):
    active_storage_path = STORAGE_PATH

    def __init__(self, *args, **kwargs):
        t = self.active_storage_path
        if not t or not os.path.isdir(t):
            t = STORAGE_PATH if os.path.isdir(STORAGE_PATH) else os.path.expanduser("~")
        self.real_storage = os.path.realpath(t)
        SimpleHTTPRequestHandler.__init__(self, *args, directory=self.real_storage, **kwargs)


class StatusDot(Widget):
    def __init__(self, dot_color=(0.88, 0.28, 0.30, 1), **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self.halo_col = Color(dot_color[0], dot_color[1], dot_color[2], 0.26)
            self.halo = Ellipse(pos=(0, 0), size=(dp(18), dp(18)))
            self.core_col = Color(*dot_color)
            self.core = Ellipse(pos=(0, 0), size=(dp(10), dp(10)))
        self.bind(pos=self._upd, size=self._upd)
        Clock.schedule_once(self._upd, 0)

    def _upd(self, *_args):
        cx, cy, hr, cr = self.center_x, self.center_y, dp(8.5), dp(4.8)
        self.halo.pos, self.halo.size = (cx - hr, cy - hr), (hr * 2, hr * 2)
        self.core.pos, self.core.size = (cx - cr, cy - cr), (cr * 2, cr * 2)

    def set_status_color(self, rgba):
        self.halo_col.rgba = (rgba[0], rgba[1], rgba[2], 0.28)
        self.core_col.rgba = rgba


class AnimatedToggleSwitch(ButtonBehavior, Widget):
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
        self.track_rect.pos, self.track_rect.size, self.track_rect.radius = self.pos, self.size, [r]
        self.track_line.rounded_rectangle = [self.x, self.y, w, h, r]
        t = max(0.0, min(1.0, self.thumb_pos))
        self.track_col.rgba = (0.22 - 0.04 * t, 0.24 + 0.12 * t, 0.28 + 0.26 * t, 1.0)
        self.border_col.rgba = (0.38, 0.72, 0.98, 0.75) if t > 0.5 else (0.40, 0.44, 0.50, 0.55)
        self.thumb_col.rgba = (0.97 - 0.55 * t, 0.98 - 0.22 * t, 0.99 + 0.01 * t, 1.0)
        pad, d = dp(3.5), h - dp(7.0)
        self.thumb_ellipse.pos = (self.x + pad + (w - pad * 2 - d) * t, self.y + pad)
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
    on_touch_down = on_touch_move = on_touch_up = lambda self, touch: False

    def __init__(self, icon_type="pc", color=(0.95, 0.96, 0.98, 1), **kwargs):
        super().__init__(**kwargs)
        self.icon_type, self.icon_color, self._drawn = icon_type, color, False
        with self.canvas.before:
            PushMatrix()
            self._trans = Translate(self.x, self.y)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._update_pos, size=self._redraw)
        Clock.schedule_once(self._redraw, 0)

    def _update_pos(self, *_args):
        self._trans.x, self._trans.y = self.x, self.y
        if not self._drawn:
            self._redraw()

    def set_color(self, color):
        if self.icon_color != color:
            self.icon_color = color
            self._redraw()

    def _redraw(self, *_args):
        self._trans.x, self._trans.y = self.x, self.y
        self.canvas.clear()
        w_full, h_full = self.width, self.height
        s = min(w_full, h_full)
        if s <= 2:
            return
        self._drawn = True
        cx, cy, lw, t = w_full * 0.5, h_full * 0.5, max(1.2, dp(1.55)), self.icon_type
        with self.canvas:
            Color(*self.icon_color)
            if t == "pc":
                mw, mh = s * 0.76, s * 0.52
                x0, y0, nh = cx - mw * 0.5, cy - mh * 0.22, s * 0.13
                Color(0.13, 0.14, 0.16, 0.90)
                RoundedRectangle(pos=(x0 + dp(2), y0 + dp(2)), size=(mw - dp(4), mh - dp(4)), radius=[dp(4)])
                Color(*self.icon_color)
                Line(rounded_rectangle=[x0, y0, mw, mh, dp(5)], width=dp(2.0))
                Line(points=[cx - mw * 0.08, y0, cx - mw * 0.11, y0 - nh], width=dp(1.6))
                Line(points=[cx + mw * 0.08, y0, cx + mw * 0.11, y0 - nh], width=dp(1.6))
                Line(points=[cx - mw * 0.28, y0 - nh, cx + mw * 0.28, y0 - nh], width=dp(2.0))
            elif t == "wifi":
                by = cy - s * 0.18
                Ellipse(pos=(cx - dp(1.8), by - dp(1.8)), size=(dp(3.6), dp(3.6)))
                Line(circle=(cx, by, s * 0.26, -44, 44), width=dp(1.4))
                Line(circle=(cx, by, s * 0.42, -46, 46), width=dp(1.4))
            elif t == "gear":
                ro, ri = s * 0.27, s * 0.12
                Line(circle=(cx, cy, ri), width=dp(1.5))
                Line(circle=(cx, cy, ro * 0.82), width=dp(1.7))
                for deg in range(0, 360, 45):
                    rad = math.radians(deg)
                    Line(points=[cx + math.cos(rad) * ro * 0.8, cy + math.sin(rad) * ro * 0.8,
                                 cx + math.cos(rad) * ro * 1.02, cy + math.sin(rad) * ro * 1.02], width=dp(2.1))
            elif t == "copy":
                w, h = s * 0.36, s * 0.44
                Line(rounded_rectangle=[cx - w * 0.68, cy - h * 0.28, w, h, dp(3)], width=lw)
                Color(0.18, 0.20, 0.22, 1)
                RoundedRectangle(pos=(cx - w * 0.28, cy - h * 0.68), size=(w, h), radius=[dp(3)])
                Color(*self.icon_color)
                Line(rounded_rectangle=[cx - w * 0.28, cy - h * 0.68, w, h, dp(3)], width=lw)
            elif t == "download":
                Color(0.88, 0.61, 0.22, 0.15)
                Ellipse(pos=(cx - s * 0.40, cy - s * 0.40), size=(s * 0.80, s * 0.80))
                Color(*self.icon_color)
                top_y, bot_y, aw = cy + s * 0.25, cy - s * 0.10, s * 0.20
                Line(points=[cx, top_y, cx, bot_y], width=dp(2.1))
                Line(points=[cx - aw, bot_y + aw * 0.85, cx, bot_y, cx + aw, bot_y + aw * 0.85], width=dp(2.1))
                Line(points=[cx - s * 0.26, cy - s * 0.24, cx + s * 0.26, cy - s * 0.24], width=dp(2.1))
            elif t == "gallery":
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
            elif t == "document":
                dw, dh = s * 0.50, s * 0.62
                x0, y0, fold = cx - dw * 0.5, cy - dh * 0.5, dw * 0.32
                Color(0.62, 0.65, 0.70, 0.95)
                RoundedRectangle(pos=(x0, y0), size=(dw, dh), radius=[dp(5)])
                Color(0.38, 0.41, 0.46, 1)
                Triangle(points=[x0 + dw - fold, y0 + dh, x0 + dw, y0 + dh - fold, x0 + dw - fold, y0 + dh - fold])
            elif t == "zip_badge":
                Color(0.68, 0.47, 0.20, 1)
                RoundedRectangle(pos=(dp(2), dp(2)), size=(w_full - dp(4), h_full - dp(4)), radius=[dp(10)])
                Color(0.98, 0.90, 0.74, 1)
                for step in range(3):
                    ty = cy + s * 0.24 - step * dp(4.2)
                    Line(points=[cx - dp(2.5), ty, cx + dp(2.5), ty], width=dp(1.4))
                RoundedRectangle(pos=(cx - dp(3.5), cy - dp(6)), size=(dp(7), dp(8)), radius=[dp(2)])
            elif t == "img_badge":
                Color(0.24, 0.26, 0.29, 1)
                RoundedRectangle(pos=(dp(2), dp(2)), size=(w_full - dp(4), h_full - dp(4)), radius=[dp(10)])
                Color(0.72, 0.75, 0.80, 0.95)
                mw, mh = s * 0.52, s * 0.32
                Triangle(points=[cx - mw * 0.52, cy - mh * 0.55, cx - mw * 0.10, cy + mh * 0.32, cx + mw * 0.28, cy - mh * 0.55])
                Color(0.54, 0.57, 0.62, 0.95)
                Triangle(points=[cx - mw * 0.02, cy - mh * 0.55, cx + mw * 0.26, cy + mh * 0.12, cx + mw * 0.54, cy - mh * 0.55])
                Color(0.82, 0.85, 0.90, 1)
                Ellipse(pos=(cx - mw * 0.38, cy + mh * 0.18), size=(dp(4.2), dp(4.2)))
            elif t == "transfer":
                dx, dy, aw = s * 0.25, s * 0.12, s * 0.10
                Line(points=[cx - dx, cy + dy, cx + dx, cy + dy], width=dp(1.8))
                Line(points=[cx + dx - aw, cy + dy + aw, cx + dx, cy + dy, cx + dx - aw, cy + dy - aw], width=dp(1.8))
                Line(points=[cx + dx, cy - dy, cx - dx, cy - dy], width=dp(1.8))
                Line(points=[cx - dx + aw, cy - dy + aw, cx - dx, cy - dy, cx - dx + aw, cy - dy - aw], width=dp(1.8))
            elif t == "folder":
                fw, fh = s * 0.54, s * 0.38
                x0, y0 = cx - fw * 0.5, cy - fh * 0.5
                Line(points=[x0, y0 + fh * 0.82, x0, y0, x0 + fw, y0, x0 + fw, y0 + fh * 0.72,
                             x0 + fw * 0.46, y0 + fh * 0.72, x0 + fw * 0.36, y0 + fh * 0.95,
                             x0, y0 + fh * 0.95, x0, y0 + fh * 0.82], width=lw, joint="round")
            elif t == "phone":
                w, h = s * 0.36, s * 0.60
                Line(rounded_rectangle=[cx - w * 0.5, cy - h * 0.5, w, h, dp(3.5)], width=lw)
                Ellipse(pos=(cx - dp(1.3), cy - h * 0.34), size=(dp(2.6), dp(2.6)))
            elif t == "lock":
                w, h = s * 0.44, s * 0.35
                x0, y0 = cx - w * 0.5, cy - h * 0.62
                Line(rounded_rectangle=[x0, y0, w, h, dp(3)], width=lw)
                Line(circle=(cx, y0 + h, w * 0.28, -90, 90), width=lw)
                Ellipse(pos=(cx - dp(1.5), y0 + h * 0.42), size=(dp(3), dp(3)))
            elif t == "sliders":
                dx, y1, y2 = s * 0.27, cy + s * 0.14, cy - s * 0.14
                Line(points=[cx - dx, y1, cx + dx, y1], width=lw)
                Line(points=[cx - dx, y2, cx + dx, y2], width=lw)
                Ellipse(pos=(cx - dx * 0.35 - dp(3), y1 - dp(3)), size=(dp(6), dp(6)))
                Ellipse(pos=(cx + dx * 0.35 - dp(3), y2 - dp(3)), size=(dp(6), dp(6)))
            elif t == "info":
                r = s * 0.31
                Line(circle=(cx, cy, r), width=lw)
                Line(points=[cx, cy - r * 0.36, cx, cy + r * 0.08], width=lw)
                Ellipse(pos=(cx - dp(1.3), cy + r * 0.32), size=(dp(2.6), dp(2.6)))
            elif t == "chevron":
                d = s * 0.16
                Line(points=[cx - d * 0.5, cy + d, cx + d * 0.5, cy, cx - d * 0.5, cy - d], width=lw)
            elif t == "check":
                d = s * 0.22
                Line(points=[cx - d, cy, cx - d * 0.25, cy - d * 0.75, cx + d, cy + d * 0.65], width=dp(2.0))


class RoundedCard(BoxLayout):
    scale_val = NumericProperty(1.0)
    offset_x = NumericProperty(0.0)
    offset_y = NumericProperty(0.0)

    def __init__(self, bg_color, border_color=(0, 0, 0, 0), radius=dp(18), **kwargs):
        super().__init__(**kwargs)
        self.bg_color, self.border_color, self.radius_val = bg_color, border_color, radius
        with self.canvas.before:
            PushMatrix()
            self._mat_trans1 = Translate(0, 0)
            self._mat_scale = Scale(1.0, 1.0, 1.0)
            self._mat_trans2 = Translate(0, 0)
            self.col = Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius_val])
            self.b_col = Color(*self.border_color)
            self.line = Line(rounded_rectangle=[self.x, self.y, self.width, self.height, max(1, self.radius_val)], width=dp(1.0))
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._update, size=self._update, scale_val=self._update_matrix, offset_x=self._update_matrix, offset_y=self._update_matrix)

    def _update_matrix(self, *_args):
        cx, cy = self.center_x, self.center_y
        self._mat_trans1.x, self._mat_trans1.y = cx + self.offset_x, cy + self.offset_y
        self._mat_scale.x = self._mat_scale.y = self.scale_val
        self._mat_trans2.x, self._mat_trans2.y = -cx, -cy

    def _update(self, *_args):
        self.rect.pos, self.rect.size = self.pos, self.size
        if self.width > 2 and self.height > 2:
            self.line.rounded_rectangle = [self.x, self.y, self.width, self.height, min(self.radius_val, self.height * 0.5)]
        self._update_matrix()

    def update_colors(self, bg_color, border_color=(0, 0, 0, 0)):
        self.bg_color, self.border_color = bg_color, border_color
        self.col.rgba, self.b_col.rgba = bg_color, border_color


class ClickableCard(ButtonBehavior, RoundedCard):
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
    def __init__(self, text="", bg_color=(0.38, 0.72, 0.98, 1), border_color=(0, 0, 0, 0), text_color=(1, 1, 1, 1), font_size=sp(14), radius=dp(15), **kwargs):
        super().__init__(bg_color=bg_color, border_color=border_color, radius=radius, **kwargs)
        self.lbl = _lbl(f"[b]{text}[/b]", size=font_size / sp(1), halign="center", markup=True, color=text_color)
        self.add_widget(self.lbl)

    def set_text(self, text):
        self.lbl.text = f"[b]{text}[/b]"


class DrawerOverlay(Widget):
    scrim_alpha = NumericProperty(0.0)

    def __init__(self, close_callback, **kwargs):
        super().__init__(**kwargs)
        self.close_callback, self.is_open, self.base_rgb = close_callback, False, (0, 0, 0)
        with self.canvas:
            self.col = Color(0, 0, 0, 0)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._upd, size=self._upd, scrim_alpha=self._upd_alpha)

    def _upd(self, *_args):
        self.rect.pos, self.rect.size = self.pos, self.size

    def _upd_alpha(self, *_args):
        self.col.rgba = (self.base_rgb[0], self.base_rgb[1], self.base_rgb[2], self.scrim_alpha)

    def animate_to(self, target_rgba, duration=0.28):
        self.base_rgb = target_rgba[:3]
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
        return True if super().on_touch_up(touch) else self.collide_point(*touch.pos)


class DrawerMenuRow(ButtonBehavior, RoundedCard):
    def __init__(self, icon_name, label_text, text_color, sub_color, highlight_rgba, **kwargs):
        super().__init__(bg_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0), radius=dp(12), orientation="horizontal",
                         size_hint=(1, None), height=dp(46), padding=[dp(8), dp(4), dp(8), dp(4)], spacing=dp(12), **kwargs)
        self.always_release, self.highlight_rgba = True, highlight_rgba
        self.ico_w = VectorIcon(icon_type=icon_name, color=sub_color, size_hint=(None, 1), width=dp(24))
        self.lbl_w = _lbl(label_text, size=15, color=text_color)
        self.chev_w = VectorIcon(icon_type="chevron", color=sub_color, size_hint=(None, 1), width=dp(18))
        for w in (self.ico_w, self.lbl_w, self.chev_w):
            self.add_widget(w)

    def on_press(self):
        self.update_colors(self.highlight_rgba, (0, 0, 0, 0))
        Animation.cancel_all(self, "scale_val")
        Animation(scale_val=0.96, duration=0.07).start(self)

    def on_release(self):
        self.update_colors((0, 0, 0, 0), (0, 0, 0, 0))
        Animation.cancel_all(self, "scale_val")
        Animation(scale_val=1.0, duration=0.18, t="out_back").start(self)


class RadarCard(RoundedCard):
    def __init__(self, bg_color, border_color, ring_color, glow_color, **kwargs):
        super().__init__(bg_color=bg_color, border_color=border_color, radius=dp(24), **kwargs)
        with self.canvas.before:
            self.glow_col = Color(*glow_color)
            self.glow_outer = Ellipse(pos=(0, 0), size=(10, 10))
            self.ring_col = Color(*ring_color)
            self.rings = [Line(circle=(0, 0, 10), width=dp(1.0)) for _ in range(4)]
        self.bind(pos=self._update_rings, size=self._update_rings)

    def _update_rings(self, *_args):
        cx, cy = self.center_x, self.y + self.height * 0.62
        max_r = min(self.width, self.height) * 0.45
        glow_r = max_r * 0.72
        self.glow_outer.pos, self.glow_outer.size = (cx - glow_r, cy - glow_r), (glow_r * 2, glow_r * 2)
        for idx, factor in enumerate((0.40, 0.60, 0.80, 1.00)):
            self.rings[idx].circle = (cx, cy, max_r * factor)

    def update_radar_colors(self, bg_color, border_color, ring_color, glow_color):
        self.update_colors(bg_color, border_color)
        self.ring_col.rgba, self.glow_col.rgba = ring_color, glow_color


class SlimProgressBar(Widget):
    on_touch_down = lambda self, touch: False

    def __init__(self, percent=0.45, track_color=(0.22, 0.235, 0.26, 1), fill_color=(0.88, 0.61, 0.22, 1), **kwargs):
        super().__init__(**kwargs)
        self.percent = percent
        with self.canvas:
            self.t_col = Color(*track_color)
            self.t_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(2.5)])
            self.f_col = Color(*fill_color)
            self.f_rect = RoundedRectangle(pos=self.pos, size=(self.width * self.percent, self.height), radius=[dp(2.5)])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_args):
        self.t_rect.pos, self.t_rect.size = self.pos, self.size
        self.f_rect.pos, self.f_rect.size = self.pos, (max(dp(10), self.width * self.percent), self.height)

    def set_percent(self, p):
        self.percent = min(1.0, max(0.0, p))
        self._upd()

    def update_bar_colors(self, track_color, fill_color):
        self.t_col.rgba, self.f_col.rgba = track_color, fill_color


class NavTabItem(ButtonBehavior, BoxLayout):
    def __init__(self, icon_type, title_text, is_active=False, pill_color=(0.29, 0.32, 0.36, 1), text_color=(1, 1, 1, 1), **kwargs):
        super().__init__(orientation="vertical", spacing=dp(2), padding=[dp(4), dp(4), dp(4), dp(4)], **kwargs)
        self.always_release = True
        self.pill_wrap = AnchorLayout(size_hint=(1, 0.58))
        self.pill_bg = RoundedCard(bg_color=pill_color if is_active else (0, 0, 0, 0),
                                   border_color=(0.44, 0.48, 0.54, 0.50) if is_active else (0, 0, 0, 0),
                                   radius=dp(15), size_hint=(None, None), size=(dp(64), dp(30)))
        self.icon_widget = VectorIcon(icon_type=icon_type, color=text_color, size_hint=(1, 1))
        self.pill_bg.add_widget(self.icon_widget)
        self.pill_wrap.add_widget(self.pill_bg)
        self.label = _lbl(title_text, size=11, halign="center", color=text_color, size_hint=(1, 0.42))
        self.add_widget(self.pill_wrap)
        self.add_widget(self.label)

    def on_press(self):
        Animation.cancel_all(self.pill_bg, "scale_val")
        Animation(scale_val=0.88, duration=0.07, t="out_quad").start(self.pill_bg)

    def on_release(self):
        Animation.cancel_all(self.pill_bg, "scale_val")
        Animation(scale_val=1.0, duration=0.24, t="out_back").start(self.pill_bg)

    def set_active_style(self, is_active, pill_color, text_color):
        border_c = (0.44, 0.48, 0.54, 0.50) if is_active else (0, 0, 0, 0)
        self.pill_bg.update_colors(pill_color if is_active else (0, 0, 0, 0), border_c)
        self.icon_widget.set_color(text_color)
        self.label.color = text_color


class MacModalContainer(FloatLayout):
    scrim_alpha = NumericProperty(0.0)

    def __init__(self, card_widget, origin_pos=None, scrim_rgba=(0, 0, 0, 0.56), on_dismiss_cb=None, **kwargs):
        super().__init__(size_hint=(1, 1), pos_hint={"x": 0, "y": 0}, **kwargs)
        self.card, self.origin_pos, self.scrim_rgba, self.on_dismiss_cb, self.is_closing = card_widget, origin_pos, scrim_rgba, on_dismiss_cb, False
        with self.canvas.before:
            self.scrim_col = Color(scrim_rgba[0], scrim_rgba[1], scrim_rgba[2], 0.0)
            self.scrim_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._upd_scrim, size=self._upd_scrim, scrim_alpha=self._upd_alpha)
        self.add_widget(self.card)

    def _upd_scrim(self, *_args):
        self.scrim_rect.pos, self.scrim_rect.size = self.pos, self.size

    def _upd_alpha(self, *_args):
        self.scrim_col.rgba = (self.scrim_rgba[0], self.scrim_rgba[1], self.scrim_rgba[2], self.scrim_alpha)

    def animate_open(self):
        cx, cy = Window.width * 0.5, Window.height * 0.5
        dx, dy = ((self.origin_pos[0] - cx) * 0.55, (self.origin_pos[1] - cy) * 0.55) if self.origin_pos else (0, -dp(45))
        self.card.scale_val, self.card.offset_x, self.card.offset_y, self.card.opacity = 0.22, dx, dy, 0.0
        Animation(scrim_alpha=self.scrim_rgba[3], duration=0.22, t="out_quad").start(self)
        Animation(scale_val=1.0, offset_x=0.0, offset_y=0.0, opacity=1.0, duration=0.30, t="out_back").start(self.card)

    def dismiss(self, *_args):
        if self.is_closing:
            return
        self.is_closing = True
        if callable(self.on_dismiss_cb):
            self.on_dismiss_cb()
        cx, cy = Window.width * 0.5, Window.height * 0.5
        dx, dy = ((self.origin_pos[0] - cx) * 0.45, (self.origin_pos[1] - cy) * 0.45) if self.origin_pos else (0, -dp(35))
        Animation(scrim_alpha=0.0, duration=0.18, t="in_quad").start(self)
        anim = Animation(scale_val=0.25, offset_x=dx, offset_y=dy, opacity=0.0, duration=0.18, t="in_back")
        anim.bind(on_complete=lambda *_: self.parent and self.parent.remove_widget(self))
        anim.start(self.card)

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
        ip, pwd = get_local_ip(), (self.saved_password or "").strip()
        return f"http://airshare:{pwd}@{ip}:{self.server_port}" if pwd else f"http://{ip}:{self.server_port}"

    def update_connection_url_display(self):
        url = self.get_connection_url()
        self.addr_label.text = url
        self.addr_label.font_size = sp(10.5) if len(url) > 38 else (sp(11.5) if len(url) > 30 else sp(13.5))

    def set_keep_alive(self, enabled):
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
                                self._wake_lock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AirSharePC::WakeLock")
                        if self._wake_lock is not None and not self._wake_lock.isHeld():
                            self._wake_lock.acquire()
                    elif self._wake_lock is not None and self._wake_lock.isHeld():
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
        self.main_content = BoxLayout(orientation="vertical", padding=[dp(18), dp(14), dp(18), dp(16)], spacing=dp(14))

        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(42), spacing=dp(8))
        name_box = BoxLayout(orientation="horizontal", size_hint=(0.58, 1), spacing=dp(8))
        self.status_dot = StatusDot(dot_color=p["red"], size_hint=(None, None), size=(dp(18), dp(18)), pos_hint={"center_y": 0.5})
        dev_name = get_device_info()
        self.device_label = _lbl(f"[b]{dev_name}[/b]", size=20 if len(dev_name) <= 14 else 16.5, markup=True, shorten=True, shorten_from="right")
        name_box.add_widget(self.status_dot)
        name_box.add_widget(self.device_label)

        wifi_anchor = AnchorLayout(anchor_x="right", anchor_y="center", size_hint=(0.42, 1))
        self.wifi_pill = ClickableCard(bg_color=p["pill_bg"], border_color=p["card_border"], radius=dp(17),
                                       orientation="horizontal", size_hint=(None, None), size=(dp(140), dp(34)),
                                       padding=[dp(12), dp(4), dp(12), dp(4)], spacing=dp(6))
        self.wifi_icon = VectorIcon(icon_type="wifi", color=p["text"], size_hint=(None, 1), width=dp(18))
        self.wifi_label = _lbl("Wi-Fi 6 • 5GHz", size=12, halign="center")
        self.wifi_pill.add_widget(self.wifi_icon)
        self.wifi_pill.add_widget(self.wifi_label)
        self.wifi_pill.bind(on_press=self.refresh_network_status)
        wifi_anchor.add_widget(self.wifi_pill)
        header.add_widget(name_box)
        header.add_widget(wifi_anchor)
        self.main_content.add_widget(header)

        self.radar_card = RadarCard(bg_color=p["radar_bg"], border_color=p["card_border"], ring_color=p["radar_ring"],
                                    glow_color=p["radar_glow"], orientation="vertical",
                                    padding=[dp(16), dp(20), dp(16), dp(16)], spacing=dp(10), size_hint=(1, 0.54))
        icon_holder = AnchorLayout(size_hint=(1, 0.30))
        self.monitor_icon = VectorIcon(icon_type="pc", color=p["text"], size_hint=(None, None), size=(dp(68), dp(54)))
        icon_holder.add_widget(self.monitor_icon)

        btn_anchor = AnchorLayout(size_hint=(1, 0.24))
        self.connect_btn = RoundedActionButton(text="Connect", bg_color=p["green"], border_color=(1, 1, 1, 0.18),
                                               font_size=sp(17), radius=dp(23), size_hint=(None, None), size=(dp(190), dp(46)))
        self.connect_btn.bind(on_press=self.toggle_server)
        btn_anchor.add_widget(self.connect_btn)

        keep_alive_anchor = AnchorLayout(size_hint=(1, 0.20))
        self.keep_alive_row = ClickableCard(bg_color=p["pill_bg"], border_color=p["card_border"], radius=dp(16),
                                            orientation="horizontal", size_hint=(0.92, None), height=dp(40),
                                            padding=[dp(14), dp(6), dp(12), dp(6)], spacing=dp(10))
        self.keep_alive_label = _lbl("Активен при заблокированном экране", size=12)
        self.keep_alive_switch = AnimatedToggleSwitch(active=self.keep_alive_locked, size_hint=(None, None),
                                                      size=(dp(48), dp(26)), pos_hint={"center_y": 0.5})
        self.keep_alive_switch.bind(on_press=lambda *_: self.set_keep_alive(not self.keep_alive_locked))
        self.keep_alive_row.bind(on_press=lambda *_: self.set_keep_alive(not self.keep_alive_locked))
        self.keep_alive_row.add_widget(self.keep_alive_label)
        self.keep_alive_row.add_widget(self.keep_alive_switch)
        keep_alive_anchor.add_widget(self.keep_alive_row)

        addr_row = BoxLayout(orientation="horizontal", size_hint=(1, 0.22), spacing=dp(8), padding=[dp(4), dp(2), dp(4), dp(2)])
        self.addr_pill = ClickableCard(bg_color=p["pill_bg"], border_color=p["card_border"], radius=dp(19),
                                       size_hint=(1, None), height=dp(40), pos_hint={"center_y": 0.5}, padding=[dp(12), dp(4), dp(12), dp(4)])
        self.addr_label = _lbl("", size=12, halign="center", shorten=True, shorten_from="center")
        self.addr_pill.add_widget(self.addr_label)
        self.addr_pill.bind(on_press=self.copy_address)

        self.copy_btn = ClickableCard(bg_color=p["pill_bg"], border_color=p["card_border"], radius=dp(14),
                                      size_hint=(None, None), size=(dp(40), dp(40)), pos_hint={"center_y": 0.5})
        self.copy_icon = VectorIcon(icon_type="copy", color=p["text"], size_hint=(1, 1))
        self.copy_btn.add_widget(self.copy_icon)
        self.copy_btn.bind(on_press=self.copy_address)
        addr_row.add_widget(self.addr_pill)
        addr_row.add_widget(self.copy_btn)

        for w in (icon_holder, btn_anchor, keep_alive_anchor, addr_row):
            self.radar_card.add_widget(w)
        self.main_content.add_widget(self.radar_card)

        self.transfers_header = _lbl("[b]Recent Transfers[/b]", size=16, markup=True, size_hint=(1, None), height=dp(24))
        self.main_content.add_widget(self.transfers_header)

        self.transfers_card = ClickableCard(bg_color=p["card_bg"], border_color=p["card_border"], radius=dp(18),
                                            orientation="vertical", padding=[dp(14), dp(12), dp(14), dp(12)],
                                            spacing=dp(10), size_hint=(1, 0.28))
        self.transfers_card.bind(on_press=self.open_transfers_modal)

        row1 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5))
        ico1 = VectorIcon(icon_type="zip_badge", size_hint=(None, None), size=(dp(42), dp(42)), pos_hint={"center_y": 0.5})
        info1 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top1 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20))
        self.tr1_name = _lbl("Project_Archive.zip", size=14, size_hint=(0.76, 1))
        self.tr1_pct = _lbl("100%", size=13, halign="right", size_hint=(0.24, 1))
        top1.add_widget(self.tr1_name)
        top1.add_widget(self.tr1_pct)
        self.tr1_bar = SlimProgressBar(percent=1.0, track_color=p["track"], fill_color=p["amber"], size_hint=(1, None), height=dp(4.2))
        self.tr1_sub = _lbl("Completed", size=11.5, size_hint=(1, None), height=dp(16))
        for w in (top1, self.tr1_bar, self.tr1_sub):
            info1.add_widget(w)
        row1.add_widget(ico1)
        row1.add_widget(info1)

        row2 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5))
        ico2 = VectorIcon(icon_type="img_badge", size_hint=(None, None), size=(dp(42), dp(42)), pos_hint={"center_y": 0.5})
        info2 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top2 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20))
        self.tr2_name = _lbl("IMG_8492.raw", size=14, size_hint=(0.76, 1))
        self.tr2_pct = _lbl("64%", size=13, halign="right", size_hint=(0.24, 1))
        top2.add_widget(self.tr2_name)
        top2.add_widget(self.tr2_pct)
        self.tr2_bar = SlimProgressBar(percent=0.64, track_color=p["track"], fill_color=p["blue"], size_hint=(1, None), height=dp(4.2))
        self.tr2_sub = _lbl("45 MB/s", size=11.5, halign="right", size_hint=(1, None), height=dp(16))
        for w in (top2, self.tr2_bar, self.tr2_sub):
            info2.add_widget(w)
        row2.add_widget(ico2)
        row2.add_widget(info2)

        self.transfers_card.add_widget(row1)
        self.transfers_card.add_widget(row2)
        self.main_content.add_widget(self.transfers_card)

        self.bottom_nav = RoundedCard(bg_color=p["card_bg"], border_color=p["card_border"], radius=dp(26),
                                      orientation="horizontal", padding=[dp(10), dp(6), dp(10), dp(6)],
                                      spacing=dp(4), size_hint=(1, None), height=dp(64))
        self.nav_transfer = NavTabItem("transfer", "Transfer", is_active=True, pill_color=p["pill_active"], text_color=p["text"])
        self.nav_transfer.bind(on_press=self._on_nav_transfer)
        self.nav_files = NavTabItem("folder", "Files", is_active=False, pill_color=p["pill_active"], text_color=p["subtext"])
        self.nav_files.bind(on_press=self._on_nav_files)
        self.nav_devices = NavTabItem("phone", "Devices", is_active=False, pill_color=p["pill_active"], text_color=p["subtext"])
        self.nav_devices.bind(on_press=self._on_nav_devices)
        self.nav_settings = NavTabItem("gear", "Settings", is_active=False, pill_color=p["pill_active"], text_color=p["subtext"])
        self.nav_settings.bind(on_press=self._on_nav_settings)
        for tab in (self.nav_transfer, self.nav_files, self.nav_devices, self.nav_settings):
            self.bottom_nav.add_widget(tab)
        self.main_content.add_widget(self.bottom_nav)
        self.root_widget.add_widget(self.main_content)

        self.overlay = DrawerOverlay(close_callback=self.close_drawer, size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.root_widget.add_widget(self.overlay)

        self.drawer_width = dp(285)
        self.drawer = DrawerPanel(bg_color=p["drawer_bg"], border_color=p["drawer_border"], radius=dp(26),
                                  orientation="vertical", padding=[dp(20), dp(22), dp(20), dp(18)], spacing=dp(14),
                                  size_hint=(None, None), width=self.drawer_width, height=Window.height - dp(48),
                                  pos=(-self.drawer_width - dp(40), dp(24)))
        self.drawer.opacity = 0.0
        Window.bind(size=self._on_window_resize)

        self.drawer_title = _lbl(f"[b]{APP_NAME}[/b]", size=23, markup=True, size_hint=(1, None), height=dp(32))
        self.drawer.add_widget(self.drawer_title)

        phone_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(30), spacing=dp(10))
        self.drawer_phone_icon = VectorIcon(icon_type="phone", color=p["subtext"], size_hint=(None, 1), width=dp(22))
        self.drawer_phone_label = _lbl(dev_name, size=15, shorten=True, shorten_from="right")
        phone_row.add_widget(self.drawer_phone_icon)
        phone_row.add_widget(self.drawer_phone_label)
        self.drawer.add_widget(phone_row)

        stats = get_storage_stats()
        self.drawer_storage_card = ClickableCard(bg_color=p["drawer_card"], border_color=p["drawer_border"], radius=dp(15),
                                                 orientation="vertical", padding=[dp(14), dp(10), dp(14), dp(12)],
                                                 spacing=dp(8), size_hint=(1, None), height=dp(64))
        self.drawer_storage_label = _lbl(f"Storage: [b]{stats['used_gb']} GB[/b] / {stats['total_gb']:.0f} GB",
                                         size=13, markup=True, size_hint=(1, None), height=dp(20))
        self.drawer_storage_bar = SlimProgressBar(percent=stats["percent"], track_color=p["pill_bg"], fill_color=p["text"],
                                                  size_hint=(1, None), height=dp(5))
        self.drawer_storage_card.add_widget(self.drawer_storage_label)
        self.drawer_storage_card.add_widget(self.drawer_storage_bar)
        self.drawer_storage_card.bind(on_press=self.open_shared_folders_modal)
        self.drawer.add_widget(self.drawer_storage_card)

        self.drawer_status_card = ClickableCard(bg_color=p["drawer_card"], border_color=p["drawer_border"], radius=dp(15),
                                                orientation="horizontal", padding=[dp(14), dp(10), dp(14), dp(10)],
                                                spacing=dp(12), size_hint=(1, None), height=dp(66))
        self.drawer_status_icon = VectorIcon(icon_type="pc", color=p["text"], size_hint=(None, 1), width=dp(32))
        self.drawer_status_label = _lbl("[b]Server Stopped[/b]\n[size=12sp]Tap to start[/size]", size=14.5, markup=True)
        self.drawer_status_card.add_widget(self.drawer_status_icon)
        self.drawer_status_card.add_widget(self.drawer_status_label)
        self.drawer_status_card.bind(on_press=self.toggle_server)
        self.drawer.add_widget(self.drawer_status_card)

        menu_box = BoxLayout(orientation="vertical", spacing=dp(4), size_hint=(1, 1))
        self.menu_items_refs = []
        for ico_name, label_text, cb in [
            ("folder", "Shared Folders", self.open_shared_folders_modal),
            ("lock", "Security & PIN", self.open_security_modal),
            ("sliders", "Port Settings", self.open_port_modal),
            ("info", "Help & Feedback", self.open_help_modal),
        ]:
            row = DrawerMenuRow(ico_name, label_text, p["text"], p["subtext"], p["pill_bg"])
            row.bind(on_press=cb)
            menu_box.add_widget(row)
            self.menu_items_refs.append(row)
        self.drawer.add_widget(menu_box)

        self.theme_pill_container = RoundedCard(bg_color=p["drawer_card"], border_color=p["drawer_border"], radius=dp(20),
                                                orientation="horizontal", padding=dp(4), spacing=dp(4),
                                                size_hint=(1, None), height=dp(44))
        self.t_btn_dark = RoundedActionButton(text="Dark", radius=dp(16), font_size=sp(13))
        self.t_btn_dark.bind(on_press=lambda *_: self.set_theme_mode("dark"))
        self.t_btn_light = RoundedActionButton(text="Light", radius=dp(16), font_size=sp(13))
        self.t_btn_light.bind(on_press=lambda *_: self.set_theme_mode("light"))
        self.t_btn_auto = RoundedActionButton(text="Auto", radius=dp(16), font_size=sp(13))
        self.t_btn_auto.bind(on_press=lambda *_: self.set_theme_mode("system"))
        for b in (self.t_btn_dark, self.t_btn_light, self.t_btn_auto):
            self.theme_pill_container.add_widget(b)
        self.drawer.add_widget(self.theme_pill_container)
        self.root_widget.add_widget(self.drawer)

        DynamicAirShareHandler.on_client_connected = self._on_client_connected
        DynamicAirShareHandler.on_file_transfer = self._on_file_transfer
        self.update_connection_url_display()
        self.apply_theme()
        return self.root_widget

    def set_active_nav(self, tab_name):
        self.active_nav_tab = tab_name
        p = THEMES.get(self._get_effective_theme(), THEMES["dark"])
        for name, widget in [("transfer", self.nav_transfer), ("files", self.nav_files),
                             ("devices", self.nav_devices), ("settings", self.nav_settings)]:
            act = (tab_name == name)
            widget.set_active_style(act, p["pill_active"], p["text"] if act else p["subtext"])

    def _on_nav_transfer(self, *_args):
        self.set_active_nav("transfer")
        self.toggle_server()

    def _on_nav_files(self, inst, *_args):
        self.set_active_nav("files")
        self.open_shared_folders_modal(inst)

    def _on_nav_devices(self, inst, *_args):
        self.set_active_nav("devices")
        self.open_devices_modal(inst)

    def _on_nav_settings(self, *_args):
        if not self.drawer.is_open:
            self.set_active_nav("settings")
            self.open_drawer()
        else:
            self.close_drawer()

    def _on_window_resize(self, *_args):
        self.drawer.height = Window.height - dp(48)

    def refresh_network_status(self, *_args):
        self.update_connection_url_display()
        self.wifi_label.text = f"Wi-Fi • {get_local_ip()}"
        Clock.schedule_once(lambda _dt: setattr(self.wifi_label, "text", "Wi-Fi 6 • 5GHz"), 2.0)

    def open_drawer(self, *_args):
        self.drawer.is_open = self.overlay.is_open = True
        self.set_active_nav("settings")
        stats = get_storage_stats()
        self.drawer_storage_label.text = f"Storage: [b]{stats['used_gb']} GB[/b] / {stats['total_gb']:.0f} GB"
        self.drawer_storage_bar.set_percent(stats["percent"])
        palette = THEMES.get(self._get_effective_theme(), THEMES["dark"])
        self.overlay.animate_to(palette["overlay"], duration=0.30)
        Animation.cancel_all(self.drawer)
        self.drawer.scale_val = 0.96
        Animation(x=dp(16), scale_val=1.0, opacity=1.0, duration=0.30, t="out_cubic").start(self.drawer)

    def close_drawer(self, *_args):
        if not self.drawer.is_open:
            return
        self.drawer.is_open = self.overlay.is_open = False
        if self.active_modal is None:
            self.set_active_nav("transfer")
        self.overlay.animate_to((0, 0, 0, 0), duration=0.24)
        Animation.cancel_all(self.drawer)
        Animation(x=-self.drawer_width - dp(35), scale_val=0.96, opacity=0.0, duration=0.25, t="out_cubic").start(self.drawer)

    def _get_effective_theme(self):
        return get_device_theme() if self.theme_mode == "system" else self.theme_mode

    def set_theme_mode(self, mode):
        self.theme_mode = mode
        save_settings(theme_mode=mode)
        self.apply_theme()

    def _update_status_indicators(self, p):
        ip = get_local_ip()
        is_online = self.server is not None
        has_issue = self.has_server_error or (is_online and ip in ("127.0.0.1", "0.0.0.0"))
        self.status_dot.set_status_color(p["yellow"] if has_issue else (p["green"] if is_online else p["red"]))
        if is_online:
            self.connect_btn.set_text("Disconnect")
            self.connect_btn.update_colors(p["red"], (1, 1, 1, 0.22))
            self.drawer_status_label.text = f"[b]Server Active[/b]\n[size={int(sp(12))}]Port {self.server_port} • {self.active_folder_key}[/size]"
            self.drawer_status_icon.set_color(p["green"])
        else:
            self.connect_btn.set_text("Connect")
            self.connect_btn.update_colors(p["green"], (1, 1, 1, 0.22))
            self.drawer_status_label.text = f"[b]Server Stopped[/b]\n[size={int(sp(12))}]Tap to start on port {self.server_port}[/size]"
            self.drawer_status_icon.set_color(p["subtext"])

    def apply_theme(self):
        eff = self._get_effective_theme()
        p = THEMES.get(eff, THEMES["dark"])
        DynamicAirShareHandler.default_theme = eff
        Window.clearcolor = p["bg"]
        self.device_label.color = self.wifi_label.color = p["text"]
        self.wifi_pill.update_colors(p["pill_bg"], p["card_border"])
        self.wifi_icon.set_color(p["text"])
        self.radar_card.update_radar_colors(p["radar_bg"], p["card_border"], p["radar_ring"], p["radar_glow"])
        self.monitor_icon.set_color(p["text"])
        self.keep_alive_row.update_colors(p["pill_bg"], p["card_border"])
        self.keep_alive_label.color = p["text"]
        self.addr_pill.update_colors(p["pill_bg"], p["card_border"])
        self.addr_label.color = p["text"]
        self.copy_btn.update_colors(p["pill_bg"], p["card_border"])
        self.copy_icon.set_color(p["text"])
        self._update_status_indicators(p)

        self.transfers_header.color = self.tr1_name.color = self.tr2_name.color = p["text"]
        self.transfers_card.update_colors(p["card_bg"], p["card_border"])
        self.tr1_pct.color = self.tr1_sub.color = self.tr2_pct.color = self.tr2_sub.color = p["subtext"]
        self.tr1_bar.update_bar_colors(p["track"], p["amber"])
        self.tr2_bar.update_bar_colors(p["track"], p["blue"])

        self.bottom_nav.update_colors(p["card_bg"], p["card_border"])
        self.set_active_nav(self.active_nav_tab)

        self.drawer.update_colors(p["drawer_bg"], p["drawer_border"])
        self.drawer_title.color = self.drawer_phone_label.color = self.drawer_storage_label.color = self.drawer_status_label.color = p["text"]
        self.drawer_phone_icon.set_color(p["subtext"])
        self.drawer_storage_card.update_colors(p["drawer_card"], p["drawer_border"])
        self.drawer_storage_bar.update_bar_colors(p["pill_bg"], p["text"])
        self.drawer_status_card.update_colors(p["drawer_card"], p["drawer_border"])

        for row in self.menu_items_refs:
            row.highlight_rgba = p["pill_bg"]
            row.ico_w.set_color(p["subtext"])
            row.lbl_w.color = p["text"]
            row.chev_w.set_color(p["subtext"])

        self.theme_pill_container.update_colors(p["drawer_card"], p["drawer_border"])
        for mode_key, btn in (("dark", self.t_btn_dark), ("light", self.t_btn_light), ("system", self.t_btn_auto)):
            act = (self.theme_mode == mode_key)
            btn.update_colors(p["pill_active"] if act else (0, 0, 0, 0), p["drawer_border"] if act else (0, 0, 0, 0))
            btn.lbl.color = p["text"] if act else p["subtext"]

    def copy_address(self, *_args):
        url = self.get_connection_url()
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(url)
        except Exception:
            pass
        self.addr_label.text = "Copied to clipboard!"
        self.addr_label.font_size = sp(13)
        Clock.schedule_once(lambda _dt: self.update_connection_url_display(), 1.3)

    def _on_client_connected(self, device_title, os_badge, ip):
        Clock.schedule_once(lambda _dt: setattr(self.drawer_status_label, "text", f"[b]{device_title}[/b]\n[size={int(sp(12))}]{os_badge} • {ip}[/size]"), 0)

    def _on_file_transfer(self, filename, size_str, direction):
        def _upd(_dt):
            self.tr2_name.text, self.tr2_pct.text, self.tr2_sub.text = self.tr1_name.text, self.tr1_pct.text, self.tr1_sub.text
            self.tr2_bar.set_percent(1.0)
            self.tr1_name.text, self.tr1_pct.text = filename, "100%"
            act = "Uploaded" if direction == "upload" else "Downloaded"
            self.tr1_sub.text = f"{act} • {size_str}"
            self.tr1_bar.set_percent(1.0)
            self.transfer_history.insert(0, f"{filename} ({act} • {size_str})")
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
            self.update_connection_url_display()
            try:
                self.server = ReusableThreadingServer(("", self.server_port), DynamicAirShareHandler)
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
                self.has_server_error = False
                self.set_keep_alive(True)
            except OSError:
                self.server = None
                self.has_server_error = True
            self.apply_theme()
        else:
            self.is_stopping = True
            srv, self.server = self.server, None

            def _stop():
                try:
                    srv.shutdown()
                    srv.server_close()
                except Exception:
                    pass
                Clock.schedule_once(self._on_server_stopped, 0)

            threading.Thread(target=_stop, daemon=True).start()

    def _on_server_stopped(self, _dt):
        self.is_stopping = self.has_server_error = False
        self.set_keep_alive(False)
        self.apply_theme()

    def _create_mac_modal(self, title_text, subtitle_text="", height_dp=280, source_widget=None):
        origin = None
        if source_widget is not None and hasattr(source_widget, "to_window"):
            try:
                origin = source_widget.to_window(source_widget.center_x, source_widget.center_y)
            except Exception:
                origin = None
        if self.drawer.is_open:
            self.drawer.is_open = self.overlay.is_open = False
            self.overlay.animate_to((0, 0, 0, 0), duration=0.20)
            Animation.cancel_all(self.drawer)
            Animation(x=-self.drawer_width - dp(35), opacity=0.0, duration=0.20, t="out_cubic").start(self.drawer)
        if self.active_modal is not None and self.active_modal.parent:
            self.root_widget.remove_widget(self.active_modal)
            self.active_modal = None

        p = THEMES.get(self._get_effective_theme(), THEMES["dark"])
        card = RoundedCard(bg_color=p["modal_bg"], border_color=p["drawer_border"], radius=dp(26),
                           orientation="vertical", padding=[dp(20), dp(20), dp(20), dp(18)], spacing=dp(12),
                           size_hint=(0.90, None), height=dp(height_dp), pos_hint={"center_x": 0.5, "center_y": 0.5})
        card.add_widget(_lbl(f"[b]{title_text}[/b]", size=18, markup=True, color=p["text"], size_hint=(1, None), height=dp(26)))
        if subtitle_text:
            card.add_widget(_lbl(subtitle_text, size=12.5, markup=True, color=p["subtext"], size_hint=(1, None), height=dp(20)))

        modal = MacModalContainer(card_widget=card, origin_pos=origin, scrim_rgba=p["overlay"],
                                  on_dismiss_cb=lambda: (not self.drawer.is_open) and self.set_active_nav("transfer"))
        self.active_modal = modal
        self.root_widget.add_widget(modal)
        modal.animate_open()
        return modal, card, p

    def open_shared_folders_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Shared Folders", "Выберите папку для раздачи на ПК:", 395, source_widget)
        list_box = BoxLayout(orientation="vertical", spacing=dp(8), size_hint=(1, 1))
        for key_name, (path_val, icon_kind, desc_txt) in self._get_folder_map().items():
            is_cur = (key_name == self.active_folder_key)
            item_card = ClickableCard(bg_color=p["pill_active"] if is_cur else p["drawer_card"],
                                      border_color=p["amber"] if is_cur else p["drawer_border"], radius=dp(16),
                                      orientation="horizontal", size_hint=(1, None), height=dp(54),
                                      padding=[dp(12), dp(8), dp(12), dp(8)], spacing=dp(12))
            ico = VectorIcon(icon_type=icon_kind, color=p["amber"] if is_cur else p["text"],
                             size_hint=(None, None), size=(dp(30), dp(30)), pos_hint={"center_y": 0.5})
            txt_lbl = _lbl(f"[b]{key_name}[/b]\n[size={int(sp(11))}]{desc_txt}[/size]", size=13.5, markup=True, color=p["text"])
            right_ico = VectorIcon(icon_type="check" if is_cur else "chevron", color=p["amber"] if is_cur else p["subtext"],
                                   size_hint=(None, None), size=(dp(22), dp(22)), pos_hint={"center_y": 0.5})

            def _pick(_inst, k=key_name, pv=path_val):
                self.active_folder_key = k
                if not os.path.isdir(pv):
                    try:
                        os.makedirs(pv, exist_ok=True)
                    except Exception:
                        pv = STORAGE_PATH
                DynamicAirShareHandler.active_storage_path = pv
                self.apply_theme()
                modal.dismiss()

            item_card.bind(on_press=_pick)
            for w in (ico, txt_lbl, right_ico):
                item_card.add_widget(w)
            list_box.add_widget(item_card)
        card.add_widget(list_box)
        btn_ok = RoundedActionButton("Закрыть", bg_color=p["pill_bg"], border_color=p["drawer_border"], text_color=p["text"], size_hint=(1, None), height=dp(44))
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)

    def open_transfers_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Recent Transfers", "История переданных файлов за сессию:", 285, source_widget)
        inner = RoundedCard(bg_color=p["drawer_card"], border_color=p["drawer_border"], radius=dp(16), padding=dp(14), size_hint=(1, 1))
        txt = "\n".join(f"• {x}" for x in self.transfer_history[:6]) if self.transfer_history else f"• {self.tr1_name.text} ({self.tr1_sub.text})\n• {self.tr2_name.text} ({self.tr2_sub.text})"
        inner.add_widget(_lbl(txt, size=13, valign="top", color=p["text"]))
        card.add_widget(inner)
        btn_ok = RoundedActionButton("Закрыть", bg_color=p["pill_bg"], border_color=p["drawer_border"], text_color=p["text"], size_hint=(1, None), height=dp(44))
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)

    def open_security_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Security & PIN", "Пароль автоматически добавится в ссылку:", 255, source_widget)
        inp_wrap = RoundedCard(bg_color=p["drawer_card"], border_color=p["drawer_border"], radius=dp(14), size_hint=(1, None), height=dp(46), padding=[dp(10), dp(4), dp(10), dp(4)])
        inp = TextInput(text=load_settings().get("password", ""), hint_text="Введите PIN (пусто — без пароля)", multiline=False,
                        font_size=sp(14.5), background_color=(0, 0, 0, 0), foreground_color=p["text"], cursor_color=p["blue"], padding=[dp(6), dp(8), dp(6), dp(8)])
        inp_wrap.add_widget(inp)
        card.add_widget(inp_wrap)
        btn_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(44))
        btn_clear = RoundedActionButton("Без пароля", bg_color=p["pill_bg"], border_color=p["drawer_border"], text_color=p["text"])
        btn_save = RoundedActionButton("Сохранить PIN", bg_color=p["blue"], border_color=(1, 1, 1, 0.2), text_color=(1, 1, 1, 1))

        def _save(val):
            save_settings(password=val)
            self.saved_password = DynamicAirShareHandler.current_password = val
            self.update_connection_url_display()
            modal.dismiss()

        btn_clear.bind(on_press=lambda *_: _save(""))
        btn_save.bind(on_press=lambda *_: _save(inp.text.strip()))
        btn_row.add_widget(btn_clear)
        btn_row.add_widget(btn_save)
        card.add_widget(btn_row)

    def open_port_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Port Settings", "Укажите порт сервера (1024–65535):", 245, source_widget)
        inp_wrap = RoundedCard(bg_color=p["drawer_card"], border_color=p["drawer_border"], radius=dp(14), size_hint=(1, None), height=dp(46), padding=[dp(10), dp(4), dp(10), dp(4)])
        inp = TextInput(text=str(self.server_port), hint_text="8080", input_filter="int", multiline=False,
                        font_size=sp(15), background_color=(0, 0, 0, 0), foreground_color=p["text"], cursor_color=p["blue"], padding=[dp(6), dp(8), dp(6), dp(8)])
        inp_wrap.add_widget(inp)
        card.add_widget(inp_wrap)
        btn_save = RoundedActionButton("Сохранить порт", bg_color=p["blue"], border_color=(1, 1, 1, 0.2), size_hint=(1, None), height=dp(44))

        def _save_port(_b):
            try:
                val = int(inp.text.strip())
                if 1024 <= val <= 65535:
                    self.server_port = val
                    save_settings(port=val)
                    self.update_connection_url_display()
            except Exception:
                pass
            modal.dismiss()

        btn_save.bind(on_press=_save_port)
        card.add_widget(btn_save)

    def open_devices_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Connected Devices", "История подключённых IP-адресов:", 295, source_widget)
        inner = RoundedCard(bg_color=p["drawer_card"], border_color=p["drawer_border"], radius=dp(16), padding=dp(14), size_hint=(1, 1))
        ips = load_settings().get("recent_ips", [])
        lbl = _lbl("\n".join(f"• {x}" for x in ips[:6]) if ips else "Пока нет сохранённых подключений.\nОткройте ссылку в браузере на ПК.", size=13, valign="top", color=p["text"])
        inner.add_widget(lbl)
        card.add_widget(inner)
        btn_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(44))
        btn_clr = RoundedActionButton("Очистить", bg_color=p["pill_bg"], border_color=p["drawer_border"], text_color=p["text"])
        btn_ok = RoundedActionButton("Закрыть", bg_color=p["blue"], border_color=(1, 1, 1, 0.2))
        btn_clr.bind(on_press=lambda *_: (save_settings(recent_ips=[]), setattr(lbl, "text", "История очищена")))
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        btn_row.add_widget(btn_clr)
        btn_row.add_widget(btn_ok)
        card.add_widget(btn_row)

    def open_help_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Help & Feedback", f"{APP_NAME} v{APP_VERSION}", 275, source_widget)
        inner = RoundedCard(bg_color=p["drawer_card"], border_color=p["drawer_border"], radius=dp(16), padding=dp(14), size_hint=(1, 1))
        inner.add_widget(_lbl("1. Нажмите зелёную кнопку «Connect» для запуска.\n2. Скопируйте ссылку и откройте её в браузере на ПК.\n3. Во вкладке «Files» выберите папку для раздачи.", size=13, color=p["text"]))
        card.add_widget(inner)
        btn_ok = RoundedActionButton("Понятно", bg_color=p["blue"], border_color=(1, 1, 1, 0.2), size_hint=(1, None), height=dp(44))
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)


if __name__ == "__main__":
    AirShareApp().run()

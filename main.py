# Main application file - Pixel-perfect implementation of 1000250791.jpg and 1000250792.jpg
# Hardware-accelerated 120 FPS macOS-style spring animations, frosted glass drawer, and auto-auth URL

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
from kivy.uix.button import Button
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
        "radar_bg": (0.185, 0.198, 0.218, 1),
        "radar_glow": (0.32, 0.35, 0.40, 0.18),
        "card_bg": (0.145, 0.155, 0.172, 1),
        "card_border": (0.27, 0.29, 0.32, 0.85),
        "radar_ring": (0.62, 0.66, 0.72, 0.14),
        "drawer_bg": (0.16, 0.175, 0.195, 0.86),
        "drawer_card": (0.22, 0.24, 0.27, 0.76),
        "drawer_border": (0.42, 0.45, 0.50, 0.60),
        "overlay": (0.0, 0.0, 0.0, 0.52),
        "text": (0.96, 0.97, 0.98, 1),
        "subtext": (0.62, 0.65, 0.70, 1),
        "pill_bg": (0.23, 0.248, 0.275, 1),
        "pill_active": (0.28, 0.305, 0.34, 1),
        "amber": (0.88, 0.61, 0.22, 1),
        "amber_glow": (0.88, 0.61, 0.22, 0.12),
        "silver_bar": (0.68, 0.71, 0.76, 1),
        "blue": (0.44, 0.69, 0.96, 1),
        "green": (0.30, 0.84, 0.56, 1),
        "track": (0.22, 0.235, 0.26, 1),
    },
    "light": {
        "bg": (0.93, 0.94, 0.96, 1),
        "radar_bg": (0.85, 0.87, 0.91, 1),
        "radar_glow": (1.0, 1.0, 1.0, 0.35),
        "card_bg": (0.99, 0.99, 1.0, 1),
        "card_border": (0.80, 0.82, 0.86, 1),
        "radar_ring": (0.35, 0.38, 0.44, 0.15),
        "drawer_bg": (0.96, 0.97, 0.98, 0.88),
        "drawer_card": (0.90, 0.92, 0.95, 0.78),
        "drawer_border": (0.76, 0.79, 0.84, 0.70),
        "overlay": (0.0, 0.0, 0.0, 0.32),
        "text": (0.11, 0.12, 0.14, 1),
        "subtext": (0.44, 0.47, 0.53, 1),
        "pill_bg": (0.83, 0.85, 0.89, 1),
        "pill_active": (0.73, 0.77, 0.83, 1),
        "amber": (0.84, 0.54, 0.14, 1),
        "amber_glow": (0.84, 0.54, 0.14, 0.12),
        "silver_bar": (0.46, 0.50, 0.56, 1),
        "blue": (0.20, 0.54, 0.90, 1),
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
    """Hardware-translated vector canvas icon: moving pos never clears or rebuilds canvas (120 FPS)"""

    def __init__(self, icon_type="pc", color=(0.95, 0.96, 0.98, 1), **kwargs):
        super().__init__(**kwargs)
        self.icon_type = icon_type
        self.icon_color = color
        with self.canvas.before:
            PushMatrix()
            self._trans = Translate(self.x, self.y)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._update_pos, size=self._redraw)

    def _update_pos(self, *_args):
        self._trans.x = self.x
        self._trans.y = self.y

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
        self.canvas.clear()
        w_full, h_full = self.width, self.height
        s = min(w_full, h_full)
        if s <= 2:
            return
        cx, cy = w_full * 0.5, h_full * 0.5
        lw = max(1.2, dp(1.55))

        with self.canvas:
            Color(*self.icon_color)

            if self.icon_type == "pc":
                # Detailed monitor matching 1000250791.jpg (bezel, dark inner screen, stand, base)
                mw, mh = s * 0.76, s * 0.52
                x0, y0 = cx - mw * 0.5, cy - mh * 0.22
                Color(0.13, 0.14, 0.16, 0.90)
                RoundedRectangle(pos=(x0 + dp(2), y0 + dp(2)), size=(mw - dp(4), mh - dp(4)), radius=[dp(4)])
                Color(*self.icon_color)
                Line(rounded_rectangle=[x0, y0, mw, mh, dp(5)], width=dp(2.0))
                # Stand neck and base
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
                # Refined gear icon with compact teeth and smooth inner ring
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
                w, h = s * 0.34, s * 0.42
                Line(rounded_rectangle=[cx - w * 0.68, cy - h * 0.28, w, h, dp(3)], width=lw)
                Color(0.18, 0.20, 0.22, 1)
                RoundedRectangle(pos=(cx - w * 0.28, cy - h * 0.68), size=(w, h), radius=[dp(3)])
                Color(*self.icon_color)
                Line(rounded_rectangle=[cx - w * 0.28, cy - h * 0.68, w, h, dp(3)], width=lw)

            elif self.icon_type == "download":
                # Soft golden halo + crisp download arrow + tray matching 1000250791.jpg
                Color(0.88, 0.61, 0.22, 0.13)
                Ellipse(pos=(cx - s * 0.40, cy - s * 0.40), size=(s * 0.80, s * 0.80))
                Color(*self.icon_color)
                top_y = cy + s * 0.25
                bot_y = cy - s * 0.10
                aw = s * 0.20
                Line(points=[cx, top_y, cx, bot_y], width=dp(2.2))
                Line(points=[cx - aw, bot_y + aw * 0.85, cx, bot_y, cx + aw, bot_y + aw * 0.85], width=dp(2.2))
                tray_y = cy - s * 0.24
                Line(points=[cx - s * 0.26, tray_y, cx + s * 0.26, tray_y], width=dp(2.2))

            elif self.icon_type == "gallery":
                # Layered photo stack matching Camera Roll in 1000250791.jpg
                cw, ch = s * 0.62, s * 0.46
                # Left and right back cards
                Color(0.32, 0.35, 0.39, 0.75)
                RoundedRectangle(pos=(cx - cw * 0.72, cy - ch * 0.44), size=(cw * 0.65, ch * 0.86), radius=[dp(6)])
                RoundedRectangle(pos=(cx + cw * 0.07, cy - ch * 0.44), size=(cw * 0.65, ch * 0.86), radius=[dp(6)])
                Color(0.46, 0.49, 0.54, 0.55)
                Line(rounded_rectangle=[cx - cw * 0.72, cy - ch * 0.44, cw * 0.65, ch * 0.86, dp(6)], width=dp(1.0))
                Line(rounded_rectangle=[cx + cw * 0.07, cy - ch * 0.44, cw * 0.65, ch * 0.86, dp(6)], width=dp(1.0))
                # Main center photo card
                Color(0.76, 0.79, 0.84, 0.98)
                RoundedRectangle(pos=(cx - cw * 0.50, cy - ch * 0.50), size=(cw, ch), radius=[dp(7)])
                # Mountain silhouettes inside center card
                Color(0.24, 0.26, 0.30, 0.95)
                Triangle(
                    points=[
                        cx - cw * 0.42,
                        cy - ch * 0.46,
                        cx - cw * 0.06,
                        cy + ch * 0.06,
                        cx + cw * 0.26,
                        cy - ch * 0.46,
                    ]
                )
                Color(0.34, 0.37, 0.42, 0.90)
                Triangle(
                    points=[
                        cx - cw * 0.02,
                        cy - ch * 0.46,
                        cx + cw * 0.22,
                        cy - ch * 0.06,
                        cx + cw * 0.44,
                        cy - ch * 0.46,
                    ]
                )
                # Warm golden sun dot
                Color(0.90, 0.64, 0.22, 1)
                Ellipse(pos=(cx - cw * 0.22, cy + ch * 0.06), size=(dp(6.5), dp(6.5)))

            elif self.icon_type == "document":
                # Stacked 3D document sheet with folded corner matching Documents in 1000250791.jpg
                dw, dh = s * 0.50, s * 0.62
                x0, y0 = cx - dw * 0.5, cy - dh * 0.5
                # Subtle back page shadow
                Color(0.34, 0.37, 0.41, 0.65)
                RoundedRectangle(pos=(x0 - dp(3), y0 - dp(2)), size=(dw, dh), radius=[dp(5)])
                # Front sheet
                Color(0.62, 0.65, 0.70, 0.95)
                RoundedRectangle(pos=(x0, y0), size=(dw, dh), radius=[dp(5)])
                # Folded corner
                fold = dw * 0.32
                Color(0.38, 0.41, 0.46, 1)
                Triangle(points=[x0 + dw - fold, y0 + dh, x0 + dw, y0 + dh - fold, x0 + dw - fold, y0 + dh - fold])
                # Subtle text lines
                Color(0.42, 0.45, 0.50, 0.85)
                Line(points=[x0 + dw * 0.22, cy + dh * 0.05, x0 + dw * 0.72, cy + dh * 0.05], width=dp(1.4))
                Line(points=[x0 + dw * 0.22, cy - dh * 0.12, x0 + dw * 0.78, cy - dh * 0.12], width=dp(1.4))
                Line(points=[x0 + dw * 0.22, cy - dh * 0.28, x0 + dw * 0.58, cy - dh * 0.28], width=dp(1.4))

            elif self.icon_type == "zip_badge":
                # Warm amber archive badge with zipper track & pull tab matching 1000250791.jpg
                Color(0.68, 0.47, 0.20, 1)
                RoundedRectangle(pos=(dp(2), dp(2)), size=(w_full - dp(4), h_full - dp(4)), radius=[dp(10)])
                Color(0.84, 0.62, 0.32, 0.55)
                Line(rounded_rectangle=[dp(2), dp(2), w_full - dp(4), h_full - dp(4), dp(10)], width=dp(1.0))
                Color(0.98, 0.90, 0.74, 1)
                # Zipper teeth
                for step in range(3):
                    ty = cy + s * 0.24 - step * dp(4.2)
                    Line(points=[cx - dp(2.5), ty, cx + dp(2.5), ty], width=dp(1.4))
                # Zipper pull tab
                RoundedRectangle(pos=(cx - dp(3.5), cy - dp(6)), size=(dp(7), dp(8)), radius=[dp(2)])
                Color(0.68, 0.47, 0.20, 1)
                Ellipse(pos=(cx - dp(1.5), cy - dp(3.5)), size=(dp(3), dp(3)))

            elif self.icon_type == "img_badge":
                # Dark slate image badge with sun + mountains matching 1000250791.jpg
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
                # Clean folder outline with raised left tab
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


class VectorIconButton(ButtonBehavior, VectorIcon):
    """Standalone clickable vector icon button with spring press animation"""

    scale_val = NumericProperty(1.0)

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
        Animation(scale_val=0.95, duration=0.08, t="out_quad").start(self)

    def on_release(self):
        Animation.cancel_all(self, "scale_val")
        Animation(scale_val=1.0, duration=0.22, t="out_back").start(self)


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
    """Top radar discovery card with soft center glow and 4 concentric rings matching 1000250791.jpg"""

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
        cy = self.y + self.height * 0.56
        max_r = min(self.width, self.height) * 0.47
        glow_r = max_r * 0.72
        self.glow_outer.pos = (cx - glow_r, cy - glow_r)
        self.glow_outer.size = (glow_r * 2, glow_r * 2)
        self.ring1.circle = (cx, cy, max_r * 0.42)
        self.ring2.circle = (cx, cy, max_r * 0.62)
        self.ring3.circle = (cx, cy, max_r * 0.82)
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

    def __init__(self, icon_type, title_text, is_active=False, pill_color=(0.28, 0.305, 0.34, 1), text_color=(1, 1, 1, 1), **kwargs):
        super().__init__(orientation="vertical", spacing=dp(2), padding=[dp(4), dp(4), dp(4), dp(4)], **kwargs)
        self.always_release = True
        self.is_active = is_active
        self.pill_color = pill_color

        self.pill_wrap = AnchorLayout(size_hint=(1, 0.58))
        self.pill_bg = RoundedCard(
            bg_color=pill_color if is_active else (0, 0, 0, 0),
            border_color=(0.40, 0.43, 0.48, 0.45) if is_active else (0, 0, 0, 0),
            radius=dp(15),
            size_hint=(None, None),
            size=(dp(62), dp(30)),
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
        border_c = (0.42, 0.45, 0.50, 0.45) if is_active else (0, 0, 0, 0)
        self.pill_bg.update_colors(pill_color if is_active else (0, 0, 0, 0), border_c)
        self.icon_widget.set_color(text_color)
        self.label.color = text_color


class RadarCenterButton(ButtonBehavior, BoxLayout):
    """Clickable center area of the Radar Card with subtle press feedback"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.always_release = True

    def on_press(self):
        self.opacity = 0.78

    def on_release(self):
        self.opacity = 1.0


class MacModalContainer(FloatLayout):
    """macOS-style genie/spring popup modal that blooms smoothly out of the clicked button"""

    scrim_alpha = NumericProperty(0.0)

    def __init__(self, card_widget, origin_pos=None, scrim_rgba=(0, 0, 0, 0.52), **kwargs):
        super().__init__(size_hint=(1, 1), pos_hint={"x": 0, "y": 0}, **kwargs)
        self.card = card_widget
        self.origin_pos = origin_pos
        self.scrim_rgba = scrim_rgba
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
        self.scrim_col.rgba = (self.scrim_rgba[0], self.scrim_rgba[1], self.scrim_rgba[2], self.scrim_alpha)

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
    connected_pc_title = "Desktop PC"
    connected_pc_os = "Windows 11"
    active_folder_key = "Downloads"
    transfer_history = []
    active_modal = None

    def _get_folder_map(self):
        base = STORAGE_PATH if os.path.isdir(STORAGE_PATH) else os.path.expanduser("~")
        return {
            "All Storage": base,
            "Downloads": os.path.join(base, "Download"),
            "Camera Roll": os.path.join(base, "DCIM"),
            "Documents": os.path.join(base, "Documents"),
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
        if "@" in url:
            self.addr_label.font_size = sp(11.5)
        else:
            self.addr_label.font_size = sp(13)

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
        # ГЛАВНЫЙ ЭКРАН (Точное соответствие 1000250791.jpg, без верхней шестерёнки)
        # =====================================================================
        self.main_content = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(14), dp(18), dp(16)],
            spacing=dp(12),
        )

        # 1. Верхняя шапка: слева имя смартфона, справа капсула Wi-Fi 6 • 5GHz (без лишней шестерёнки)
        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(42), spacing=dp(8))
        self.device_label = Label(
            text=f"[b]{get_device_info()}[/b]",
            markup=True,
            font_size=sp(22),
            halign="left",
            valign="middle",
            size_hint=(0.56, 1),
        )
        self.device_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        wifi_anchor = AnchorLayout(anchor_x="right", anchor_y="center", size_hint=(0.44, 1))
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

        header.add_widget(self.device_label)
        header.add_widget(wifi_anchor)
        self.main_content.add_widget(header)

        # 2. Карточка радара (Radar Card с мягким свечением и 4 концентрическими кольцами)
        self.radar_card = RadarCard(
            bg_color=p["radar_bg"],
            border_color=p["card_border"],
            ring_color=p["radar_ring"],
            glow_color=p["radar_glow"],
            orientation="vertical",
            padding=[dp(16), dp(18), dp(16), dp(14)],
            spacing=dp(4),
            size_hint=(1, 0.36),
        )

        self.radar_top_btn = RadarCenterButton(orientation="vertical", size_hint=(1, 0.75), spacing=dp(2))
        self.radar_top_btn.bind(on_press=self.toggle_server)

        icon_holder = AnchorLayout(size_hint=(1, 0.48))
        self.monitor_icon = VectorIcon(icon_type="pc", color=p["text"], size_hint=(None, None), size=(dp(62), dp(50)))
        icon_holder.add_widget(self.monitor_icon)

        pc_row_anchor = AnchorLayout(size_hint=(1, 0.28))
        pc_row = BoxLayout(orientation="horizontal", size_hint=(None, None), size=(dp(216), dp(28)), spacing=dp(8))
        self.pc_title_label = Label(
            text=f"[b]{self.connected_pc_title}[/b]",
            markup=True,
            font_size=sp(18.5),
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
        self.os_badge_label = Label(text=self.connected_pc_os, font_size=sp(10.5), halign="center", valign="middle")
        self.os_badge_card.add_widget(self.os_badge_label)

        pc_row.add_widget(self.pc_title_label)
        pc_row.add_widget(self.os_badge_card)
        pc_row_anchor.add_widget(pc_row)

        self.speed_label = Label(
            text="850 Mbps",
            font_size=sp(13.5),
            halign="center",
            valign="top",
            size_hint=(1, 0.24),
        )
        self.speed_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        self.radar_top_btn.add_widget(icon_holder)
        self.radar_top_btn.add_widget(pc_row_anchor)
        self.radar_top_btn.add_widget(self.speed_label)

        # Нижняя капсула с адресом строго по центру и кнопка копирования справа
        addr_row = FloatLayout(size_hint=(1, 0.25))
        self.addr_pill = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(18),
            size_hint=(0.74, None),
            height=dp(36),
            pos_hint={"center_x": 0.48, "center_y": 0.5},
        )
        self.addr_label = Label(
            text=self.get_connection_url(),
            font_size=sp(11.5) if "@" in self.get_connection_url() else sp(13),
            halign="center",
            valign="middle",
        )
        self.addr_pill.add_widget(self.addr_label)
        self.addr_pill.bind(on_press=self.copy_address)

        self.copy_btn = VectorIconButton(
            icon_type="copy",
            color=p["subtext"],
            size_hint=(None, None),
            size=(dp(36), dp(36)),
            pos_hint={"right": 0.98, "center_y": 0.5},
        )
        self.copy_btn.bind(on_press=self.copy_address)

        addr_row.add_widget(self.addr_pill)
        addr_row.add_widget(self.copy_btn)

        self.radar_card.add_widget(self.radar_top_btn)
        self.radar_card.add_widget(addr_row)
        self.main_content.add_widget(self.radar_card)

        # 3. Заголовок и 3 карточки Shared Folders (Downloads, Camera Roll, Documents)
        self.folders_header = Label(
            text="[b]Shared Folders[/b]",
            markup=True,
            font_size=sp(16),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp(24),
        )
        self.folders_header.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.main_content.add_widget(self.folders_header)

        folders_grid = GridLayout(cols=3, spacing=dp(10), size_hint=(1, 0.19))
        self.folder_cards = []
        folder_specs = [
            ("Downloads", "download", 0.42),
            ("Camera Roll", "gallery", 0.38),
            ("Documents", "document", 0.28),
        ]
        for title_txt, icon_kind, prog in folder_specs:
            card = ClickableCard(
                bg_color=p["card_bg"],
                border_color=p["card_border"],
                radius=dp(18),
                orientation="vertical",
                padding=[dp(12), dp(10), dp(12), dp(10)],
                spacing=dp(4),
            )
            lbl_top = Label(
                text=title_txt,
                font_size=sp(12.5),
                halign="left",
                valign="middle",
                size_hint=(1, None),
                height=dp(18),
            )
            lbl_top.bind(size=lambda i, v: setattr(i, "text_size", v))

            ico_wrap = AnchorLayout(size_hint=(1, 1))
            ico_wid = VectorIcon(
                icon_type=icon_kind,
                color=p["amber"] if icon_kind == "download" else p["text"],
                size_hint=(None, None),
                size=(dp(56), dp(46)),
            )
            ico_wrap.add_widget(ico_wid)

            bar = SlimProgressBar(
                percent=prog,
                track_color=p["track"],
                fill_color=p["amber"] if title_txt == self.active_folder_key else p["silver_bar"],
                size_hint=(1, None),
                height=dp(4.5),
            )
            card.add_widget(lbl_top)
            card.add_widget(ico_wrap)
            card.add_widget(bar)
            card.bind(on_press=lambda inst, folder_name=title_txt: self.on_folder_card_pressed(folder_name, inst))
            folders_grid.add_widget(card)
            self.folder_cards.append((card, lbl_top, ico_wid, bar, icon_kind, title_txt))

        self.main_content.add_widget(folders_grid)

        # 4. Заголовок и карточка Recent Transfers
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
            size_hint=(1, 0.21),
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

        # 5. Нижняя навигационная панель (Transfer, Files, Devices, Settings)
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
        # ПАРЯЩАЯ БОКОВАЯ ШТОРКА (1000250792.jpg с матовым полупрозрачным стеклом)
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
        self.drawer.opacity = 0.0
        Window.bind(size=self._on_window_resize)

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

        Clock.schedule_once(lambda _dt: self.start_server_if_needed(), 0.25)
        return self.root_widget

    def start_server_if_needed(self):
        if self.server is None and not self.is_stopping:
            self.toggle_server()

    def _on_window_resize(self, *_args):
        self.drawer.height = Window.height - dp(48)

    def refresh_network_status(self, *_args):
        self.update_connection_url_display()
        ip = get_local_ip()
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
        self.overlay.animate_to(palette["overlay"], duration=0.32)

        Animation.cancel_all(self.drawer)
        self.drawer.scale_val = 0.96
        Animation(
            x=dp(16),
            scale_val=1.0,
            opacity=1.0,
            duration=0.32,
            t="out_cubic",
        ).start(self.drawer)

    def close_drawer(self, *_args):
        if not self.drawer.is_open:
            return
        self.drawer.is_open = False
        self.overlay.is_open = False
        self.overlay.animate_to((0, 0, 0, 0), duration=0.25)
        Animation.cancel_all(self.drawer)
        Animation(
            x=-self.drawer_width - dp(35),
            scale_val=0.96,
            opacity=0.0,
            duration=0.26,
            t="out_cubic",
        ).start(self.drawer)

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

        self.radar_card.update_radar_colors(p["radar_bg"], p["card_border"], p["radar_ring"], p["radar_glow"])
        self.monitor_icon.set_color(p["text"])
        self.pc_title_label.color = p["text"]
        self.os_badge_card.update_colors(p["pill_bg"], p["card_border"])
        self.os_badge_label.color = p["subtext"]
        self.speed_label.color = p["subtext"]
        self.addr_pill.update_colors(p["pill_bg"], p["card_border"])
        self.addr_label.color = p["text"]
        self.copy_btn.set_color(p["subtext"])

        self.folders_header.color = p["text"]
        for card, lbl_top, ico_wid, bar, icon_kind, title_txt in self.folder_cards:
            is_sel = (title_txt == self.active_folder_key)
            card.update_colors(p["card_bg"], p["card_border"])
            lbl_top.color = p["text"]
            ico_wid.set_color(p["amber"] if icon_kind == "download" else p["text"])
            bar.update_bar_colors(p["track"], p["amber"] if is_sel else p["silver_bar"])

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
        self.nav_transfer.set_active_style(True, p["pill_active"], p["text"])
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

    def on_folder_card_pressed(self, folder_name, card_inst=None):
        folder_map = self._get_folder_map()
        self.active_folder_key = folder_name
        target_path = folder_map.get(folder_name, STORAGE_PATH)
        if not os.path.isdir(target_path):
            try:
                os.makedirs(target_path, exist_ok=True)
            except Exception:
                target_path = STORAGE_PATH

        DynamicAirShareHandler.active_storage_path = target_path
        self.apply_theme()
        self.open_shared_folders_modal(card_inst)

    def copy_address(self, *_args):
        url = self.get_connection_url()
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(url)
        except Exception:
            pass
        self.addr_label.text = "Copied to clipboard!"
        Clock.schedule_once(lambda _dt: self.update_connection_url_display(), 1.4)

    def _on_client_connected(self, device_title, os_badge, ip):
        def _upd(_dt):
            self.connected_pc_title = device_title
            self.connected_pc_os = os_badge
            self.pc_title_label.text = f"[b]{device_title}[/b]"
            self.os_badge_label.text = os_badge
            self.speed_label.text = "850 Mbps"
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

            self.update_connection_url_display()

            try:
                self.server = ReusableThreadingServer(("", self.server_port), DynamicAirShareHandler)
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
            except OSError as e:
                self.server = None
                self.speed_label.text = f"Port error: {e}"
                return

            self.speed_label.text = "850 Mbps"
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
    # ПЛАВНЫЕ ОКНА В СТИЛЕ macOS ("ВУХ" ИЗ ТОЧКИ НАЖАТИЯ)
    # =====================================================================
    def _create_mac_modal(self, title_text, height_dp=250, source_widget=None):
        origin = None
        if source_widget is not None and hasattr(source_widget, "to_window"):
            try:
                origin = source_widget.to_window(source_widget.center_x, source_widget.center_y)
            except Exception:
                origin = None

        self.close_drawer()
        if self.active_modal is not None and self.active_modal.parent:
            self.root_widget.remove_widget(self.active_modal)
            self.active_modal = None

        p = THEMES.get(self._get_effective_theme(), THEMES["dark"])
        card = RoundedCard(
            bg_color=p["drawer_bg"],
            border_color=p["drawer_border"],
            radius=dp(24),
            orientation="vertical",
            padding=dp(20),
            spacing=dp(12),
            size_hint=(0.88, None),
            height=dp(height_dp),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        hdr = Label(
            text=f"[b]{title_text}[/b]",
            markup=True,
            font_size=sp(17.5),
            color=p["text"],
            size_hint=(1, None),
            height=dp(28),
        )
        card.add_widget(hdr)

        modal = MacModalContainer(card_widget=card, origin_pos=origin, scrim_rgba=p["overlay"])
        self.active_modal = modal
        self.root_widget.add_widget(modal)
        modal.animate_open()
        return modal, card, p

    def open_shared_folders_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Shared Folders", height_dp=320, source_widget=source_widget)
        folder_map = self._get_folder_map()
        cur_path = DynamicAirShareHandler.active_storage_path

        info_lbl = Label(
            text=f"Активный раздел: [b]{self.active_folder_key}[/b]\n{cur_path}",
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
                self.apply_theme()
                modal.dismiss()

            btn.bind(on_press=_pick)
            grid.add_widget(btn)

        card.add_widget(grid)

        btn_ok = Button(
            text="Готово",
            font_size=sp(14),
            size_hint=(1, None),
            height=dp(42),
            background_normal="",
            background_color=p["blue"],
            color=(1, 1, 1, 1),
        )
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)

    def open_transfers_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Recent Transfers", height_dp=270, source_widget=source_widget)
        if self.transfer_history:
            txt = "\n".join(f"• {x}" for x in self.transfer_history[:6])
        else:
            txt = (
                f"• {self.tr1_name.text} ({self.tr1_sub.text})\n"
                f"• {self.tr2_name.text} ({self.tr2_sub.text})\n\n"
                "Переданные с ПК и скачанные файлы отображаются здесь."
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

    def open_security_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Security & PIN", height_dp=240, source_widget=source_widget)
        settings = load_settings()
        inp = TextInput(
            text=settings.get("password", ""),
            hint_text="Введите PIN или пароль (пусто — без пароля)",
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
            self.saved_password = new_pwd
            DynamicAirShareHandler.current_password = new_pwd
            self.update_connection_url_display()
            modal.dismiss()

        def _no_pwd(_b):
            inp.text = ""
            _save_pwd(_b)

        btn_clear.bind(on_press=_no_pwd)
        btn_save.bind(on_press=_save_pwd)
        btn_row.add_widget(btn_clear)
        btn_row.add_widget(btn_save)
        card.add_widget(btn_row)

    def open_port_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Port Settings", height_dp=230, source_widget=source_widget)
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
                    self.update_connection_url_display()
                    if self.server is not None:
                        self.toggle_server()
                        Clock.schedule_once(lambda _dt: self.start_server_if_needed(), 0.4)
            except Exception:
                pass
            modal.dismiss()

        btn_save.bind(on_press=_save_port)
        card.add_widget(btn_save)

    def open_devices_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Connected Devices (IP History)", height_dp=285, source_widget=source_widget)
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

    def open_help_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Help & Feedback", height_dp=255, source_widget=source_widget)
        lbl = Label(
            text=(
                f"[b]{APP_NAME} v{APP_VERSION}[/b]\n\n"
                "1. Сервер активен (нажатие по центру радара или «Transfer» ставит на паузу / запускает).\n"
                "2. Откройте адрес со страницы в браузере на ПК в одной сети Wi-Fi.\n"
                "3. Нажимайте на карточки папок для выбора раздела."
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


if __name__ == "__main__":
    AirShareApp().run()

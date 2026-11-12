# Пользовательские Kivy-виджеты для AirShare PC (иконки, флаги, 3D радио-кнопки, тост-уведомления, экран загрузки и модальные окна)

import math
import os
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (
    Color,
    Ellipse,
    Line,
    PopMatrix,
    PushMatrix,
    Rectangle,
    RoundedRectangle,
    Scale,
    Translate,
    Triangle,
)
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from android_bridge import is_android_activity_paused
from i18n import tr


def make_label(text="", size=14, halign="left", valign="middle", markup=False, **kw):
    if kw.get("shorten_from") == "middle":
        kw["shorten_from"] = "center"
    w = Label(text=text, font_size=sp(size), halign=halign, valign=valign, markup=markup, **kw)
    w.bind(size=lambda i, v: setattr(i, "text_size", v))
    return w


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


class FlagBadge(Widget):
    # Векторный значок флага страны (Kivy на Android не рендерит эмодзи-флаги из шрифта)
    on_touch_down = on_touch_move = on_touch_up = lambda self, touch: False

    def __init__(self, lang_code="en", **kwargs):
        super().__init__(**kwargs)
        self.lang_code = lang_code
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_once(self._redraw, 0)

    def _redraw(self, *_args):
        self.canvas.clear()
        w, h = self.width, self.height
        if w <= 2 or h <= 2:
            return
        fw, fh = min(w, dp(28)), min(h, dp(20))
        x0 = self.center_x - fw * 0.5
        y0 = self.center_y - fh * 0.5
        code = self.lang_code

        with self.canvas:
            if code == "uk":
                Color(1.0, 0.84, 0.0, 1)
                Rectangle(pos=(x0, y0), size=(fw, fh * 0.5))
                Color(0.0, 0.36, 0.74, 1)
                Rectangle(pos=(x0, y0 + fh * 0.5), size=(fw, fh * 0.5))
            elif code == "ru":
                sh = fh / 3.0
                Color(0.84, 0.16, 0.12, 1)
                Rectangle(pos=(x0, y0), size=(fw, sh))
                Color(0.0, 0.24, 0.66, 1)
                Rectangle(pos=(x0, y0 + sh), size=(fw, sh))
                Color(0.96, 0.97, 0.99, 1)
                Rectangle(pos=(x0, y0 + sh * 2.0), size=(fw, sh))
            elif code == "lt":
                sh = fh / 3.0
                Color(0.76, 0.15, 0.18, 1)
                Rectangle(pos=(x0, y0), size=(fw, sh))
                Color(0.0, 0.42, 0.27, 1)
                Rectangle(pos=(x0, y0 + sh), size=(fw, sh))
                Color(0.99, 0.73, 0.07, 1)
                Rectangle(pos=(x0, y0 + sh * 2.0), size=(fw, sh))
            elif code == "de":
                sh = fh / 3.0
                Color(1.0, 0.80, 0.0, 1)
                Rectangle(pos=(x0, y0), size=(fw, sh))
                Color(0.86, 0.12, 0.12, 1)
                Rectangle(pos=(x0, y0 + sh), size=(fw, sh))
                Color(0.10, 0.11, 0.13, 1)
                Rectangle(pos=(x0, y0 + sh * 2.0), size=(fw, sh))
            elif code == "es":
                Color(0.78, 0.08, 0.12, 1)
                Rectangle(pos=(x0, y0), size=(fw, fh))
                Color(1.0, 0.77, 0.0, 1)
                Rectangle(pos=(x0, y0 + fh * 0.25), size=(fw, fh * 0.50))
            else:
                # English (UK flag motif)
                Color(0.04, 0.16, 0.46, 1)
                Rectangle(pos=(x0, y0), size=(fw, fh))
                Color(0.96, 0.97, 0.99, 1)
                Line(points=[x0 + dp(1), y0 + dp(1), x0 + fw - dp(1), y0 + fh - dp(1)], width=dp(1.8))
                Line(points=[x0 + dp(1), y0 + fh - dp(1), x0 + fw - dp(1), y0 + dp(1)], width=dp(1.8))
                Rectangle(pos=(x0, y0 + fh * 0.36), size=(fw, fh * 0.28))
                Rectangle(pos=(x0 + fw * 0.40, y0), size=(fw * 0.20, fh))
                Color(0.82, 0.10, 0.16, 1)
                Rectangle(pos=(x0, y0 + fh * 0.42), size=(fw, fh * 0.16))
                Rectangle(pos=(x0 + fw * 0.44, y0), size=(fw * 0.12, fh))

            Color(1, 1, 1, 0.22)
            Line(rounded_rectangle=[x0, y0, fw, fh, dp(3)], width=dp(1.0))


class RadioCircle(Widget):
    # Полуобъёмный серый кружочек, который при выборе плавно заполняется изумрудно-зелёным цветом
    fill_val = NumericProperty(0.0)
    on_touch_down = on_touch_move = on_touch_up = lambda self, touch: False

    def __init__(self, selected=False, **kwargs):
        super().__init__(**kwargs)
        self.is_selected = bool(selected)
        self.fill_val = 1.0 if self.is_selected else 0.0
        self.bind(pos=self._redraw, size=self._redraw, fill_val=self._redraw)
        Clock.schedule_once(self._redraw, 0)

    def set_selected(self, selected, animate=True):
        self.is_selected = bool(selected)
        target = 1.0 if self.is_selected else 0.0
        Animation.cancel_all(self, "fill_val")
        if animate:
            Animation(fill_val=target, duration=0.22, t="out_back").start(self)
        else:
            self.fill_val = target

    def _redraw(self, *_args):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        r = dp(10.5)
        t = max(0.0, min(1.0, self.fill_val))
        with self.canvas:
            # Внешняя мягкая тень для полуобъёма
            Color(0.05, 0.06, 0.07, 0.48)
            Ellipse(pos=(cx - r - dp(1), cy - r - dp(1.5)), size=((r + dp(1)) * 2, (r + dp(1)) * 2))

            # Основа кружочка (серый градиентный тон)
            Color(0.22, 0.24, 0.28, 1.0)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))

            # Внутренний верхний блик для 3D-эффекта
            Color(0.65, 0.70, 0.78, 0.25 * (1.0 - t * 0.5))
            Line(circle=(cx, cy, r - dp(1.2), -65, 65), width=dp(1.2))

            # Контур серого кружочка
            Color(0.46 * (1.0 - t) + 0.20 * t, 0.50 * (1.0 - t) + 0.78 * t, 0.56 * (1.0 - t) + 0.46 * t, 0.90)
            Line(circle=(cx, cy, r), width=dp(1.35))

            if t > 0.01:
                # Свечение и зелёное заполнение при выборе
                glow_r = (r + dp(3.0)) * min(1.0, t)
                Color(0.20, 0.78, 0.46, 0.24 * min(1.0, t))
                Ellipse(pos=(cx - glow_r, cy - glow_r), size=(glow_r * 2, glow_r * 2))

                fill_r = (r - dp(2.2)) * t
                Color(0.20, 0.78, 0.46, 1.0)
                Ellipse(pos=(cx - fill_r, cy - fill_r), size=(fill_r * 2, fill_r * 2))

                # Лёгкий глянцевый блик поверх зелёного кружочка
                hl_r = fill_r * 0.45
                Color(0.75, 0.98, 0.85, 0.38 * min(1.0, t))
                Ellipse(pos=(cx - hl_r * 0.8, cy + fill_r * 0.18 - hl_r * 0.5), size=(hl_r * 1.6, hl_r))


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
                mw, mh = s * 0.72, s * 0.48
                x0, y0, nh = cx - mw * 0.5, cy - mh * 0.22, s * 0.13
                Color(0.13, 0.14, 0.16, 0.92)
                RoundedRectangle(pos=(x0 + dp(1.5), y0 + dp(1.5)), size=(mw - dp(3), mh - dp(3)), radius=[dp(4)])
                Color(*self.icon_color)
                Line(rounded_rectangle=[x0, y0, mw, mh, dp(4.5)], width=dp(1.9))
                Line(points=[cx - mw * 0.08, y0, cx - mw * 0.11, y0 - nh], width=dp(1.5))
                Line(points=[cx + mw * 0.08, y0, cx + mw * 0.11, y0 - nh], width=dp(1.5))
                Line(points=[cx - mw * 0.28, y0 - nh, cx + mw * 0.28, y0 - nh], width=dp(1.9))
            elif t == "wifi":
                by = cy - s * 0.18
                Ellipse(pos=(cx - dp(1.8), by - dp(1.8)), size=(dp(3.6), dp(3.6)))
                Line(circle=(cx, by, s * 0.26, -44, 44), width=dp(1.4))
                Line(circle=(cx, by, s * 0.42, -46, 46), width=dp(1.4))
            elif t == "globe":
                r = s * 0.32
                Line(circle=(cx, cy, r), width=lw)
                Line(ellipse=(cx - r * 0.48, cy - r, r * 0.96, r * 2.0), width=dp(1.3))
                Line(points=[cx - r, cy, cx + r, cy], width=dp(1.3))
                Line(points=[cx, cy - r, cx, cy + r], width=dp(1.3))
            elif t == "gear":
                ro, ri = s * 0.27, s * 0.12
                Line(circle=(cx, cy, ri), width=dp(1.5))
                Line(circle=(cx, cy, ro * 0.82), width=dp(1.7))
                for deg in range(0, 360, 45):
                    rad = math.radians(deg)
                    Line(
                        points=[
                            cx + math.cos(rad) * ro * 0.8,
                            cy + math.sin(rad) * ro * 0.8,
                            cx + math.cos(rad) * ro * 1.02,
                            cy + math.sin(rad) * ro * 1.02,
                        ],
                        width=dp(2.1),
                    )
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
                Triangle(
                    points=[
                        cx - mw * 0.52,
                        cy - mh * 0.55,
                        cx - mw * 0.10,
                        cy + mh * 0.32,
                        cx + mw * 0.28,
                        cy - mh * 0.55,
                    ]
                )
                Color(0.54, 0.57, 0.62, 0.95)
                Triangle(
                    points=[
                        cx - mw * 0.02,
                        cy - mh * 0.55,
                        cx + mw * 0.26,
                        cy + mh * 0.12,
                        cx + mw * 0.54,
                        cy - mh * 0.55,
                    ]
                )
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


class VectorIconButton(ButtonBehavior, VectorIcon):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.always_release = True


class RoundedCard(BoxLayout):
    scale_val = NumericProperty(1.0)
    offset_x = NumericProperty(0.0)
    offset_y = NumericProperty(0.0)

    def __init__(self, bg_color, border_color=(0, 0, 0, 0), radius=dp(18), **kwargs):
        super().__init__(**kwargs)
        self.bg_color, self.border_color, self.radius_val = bg_color, border_color, radius
        has_fill = len(bg_color) < 4 or bg_color[3] > 0.4
        shadow_a = 0.28 if has_fill else 0.0
        bevel_a = 0.14 if has_fill else 0.0
        with self.canvas.before:
            PushMatrix()
            self._mat_trans1 = Translate(0, 0)
            self._mat_scale = Scale(1.0, 1.0, 1.0)
            self._mat_trans2 = Translate(0, 0)
            self.sh_col = Color(0, 0, 0, shadow_a)
            self.sh_rect = RoundedRectangle(pos=(self.x, self.y - dp(2.5)), size=self.size, radius=[self.radius_val])
            self.col = Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius_val])
            self.bev_col = Color(1, 1, 1, bevel_a)
            self.bev_line = Line(points=[], width=dp(1.1))
            self.b_col = Color(*self.border_color)
            self.line = Line(
                rounded_rectangle=[self.x, self.y, self.width, self.height, max(1, self.radius_val)], width=dp(1.1)
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
        self._mat_trans1.x, self._mat_trans1.y = cx + self.offset_x, cy + self.offset_y
        self._mat_scale.x = self._mat_scale.y = self.scale_val
        self._mat_trans2.x, self._mat_trans2.y = -cx, -cy

    def _update(self, *_args):
        self.rect.pos, self.rect.size = self.pos, self.size
        self.sh_rect.pos, self.sh_rect.size = (self.x, self.y - dp(2.5)), self.size
        if self.width > 2 and self.height > 2:
            r = min(self.radius_val, self.height * 0.5)
            self.line.rounded_rectangle = [self.x, self.y, self.width, self.height, r]
            inset = max(dp(8), r * 0.75)
            if self.width > inset * 2:
                self.bev_line.points = [self.x + inset, self.top - dp(1.2), self.right - inset, self.top - dp(1.2)]
        self._update_matrix()

    def update_colors(self, bg_color, border_color=(0, 0, 0, 0)):
        self.bg_color, self.border_color = bg_color, border_color
        self.col.rgba, self.b_col.rgba = bg_color, border_color
        has_fill = len(bg_color) < 4 or bg_color[3] > 0.4
        self.sh_col.rgba = (0, 0, 0, 0.28 if has_fill else 0.0)
        self.bev_col.rgba = (1, 1, 1, 0.14 if has_fill else 0.0)


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
    def __init__(
        self,
        text="",
        bg_color=(0.38, 0.72, 0.98, 1),
        border_color=(0, 0, 0, 0),
        text_color=(1, 1, 1, 1),
        font_size=sp(14),
        radius=dp(15),
        **kwargs,
    ):
        super().__init__(bg_color=bg_color, border_color=border_color, radius=radius, **kwargs)
        self.lbl = make_label(f"[b]{text}[/b]", size=font_size / sp(1), halign="center", markup=True, color=text_color)
        self.add_widget(self.lbl)

    def set_text(self, text):
        self.lbl.text = f"[b]{text}[/b]"


class RadarCenterButton(RoundedActionButton):
    pass


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
        self.always_release, self.highlight_rgba = True, highlight_rgba
        self.ico_w = VectorIcon(icon_type=icon_name, color=sub_color, size_hint=(None, 1), width=dp(24))
        self.lbl_w = make_label(label_text, size=15, color=text_color)
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
        self.target_widget = None
        self.wave_phase = 0.0
        self._wave_ev = None
        with self.canvas.after:
            self.glow_col = Color(*glow_color)
            self.glow_outer = Ellipse(pos=(0, 0), size=(dp(10), dp(10)))
            self.ring_col = Color(*ring_color)
            self.rings = [Line(points=[], close=True, width=dp(1.25)) for _ in range(3)]
        self.bind(pos=self._update_rings, size=self._update_rings)

    def attach_target(self, widget):
        self.target_widget = widget
        if widget is not None:
            widget.bind(pos=self._update_rings, size=self._update_rings)
        Clock.schedule_once(self._update_rings, 0)

    def set_wave_active(self, active):
        if active and self._wave_ev is None:
            self._wave_ev = Clock.schedule_interval(self._step_wave, 1.0 / 15.0)
        elif not active and self._wave_ev is not None:
            self._wave_ev.cancel()
            self._wave_ev = None
            self.wave_phase = 0.0
            self._update_rings()

    def _step_wave(self, _dt):
        if is_android_activity_paused():
            return
        self.wave_phase = (self.wave_phase + 0.14) % (2.0 * math.pi)
        self._update_rings()

    def _update_rings(self, *_args):
        if self.width <= 4 or self.height <= 4:
            return
        if self.target_widget is not None and self.target_widget.width > 2:
            cx, cy = self.target_widget.center_x, self.target_widget.center_y
        else:
            cx, cy = self.center_x, self.y + self.height * 0.78

        top_room = max(dp(24), self.top - cy - dp(8))
        max_r = min(dp(44), top_room * 0.92, self.width * 0.22)
        glow_r = max_r * 0.78
        self.glow_outer.pos = (cx - glow_r, cy - glow_r)
        self.glow_outer.size = (glow_r * 2.0, glow_r * 2.0)

        radii = (max_r * 0.62, max_r * 0.81, max_r * 1.00)
        amps = (dp(1.4), dp(1.8), dp(2.1))
        steps = 64
        for idx, base_r in enumerate(radii):
            amp = amps[idx]
            phase = self.wave_phase + idx * 1.15
            pts = []
            for s in range(steps):
                ang = (2.0 * math.pi * s) / steps
                wave = amp * math.sin(6.0 * ang + phase) + (amp * 0.35) * math.cos(3.0 * ang - phase)
                r = base_r + wave
                pts.extend((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
            self.rings[idx].points = pts

    def update_radar_colors(self, bg_color, border_color, ring_color, glow_color):
        self.update_colors(bg_color, border_color)
        self.ring_col.rgba, self.glow_col.rgba = ring_color, glow_color
        self._update_rings()


class SlimProgressBar(Widget):
    on_touch_down = lambda self, touch: False

    def __init__(self, percent=0.45, track_color=(0.22, 0.235, 0.26, 1), fill_color=(0.88, 0.61, 0.22, 1), **kwargs):
        super().__init__(**kwargs)
        self.percent = percent
        with self.canvas:
            self.t_col = Color(*track_color)
            self.t_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(2.5)])
            self.f_col = Color(*fill_color)
            self.f_rect = RoundedRectangle(
                pos=self.pos, size=(self.width * self.percent, self.height), radius=[dp(2.5)]
            )
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_args):
        self.t_rect.pos, self.t_rect.size = self.pos, self.size
        fill_w = max(dp(6), self.width * self.percent) if self.percent > 0 else 0
        self.f_rect.pos, self.f_rect.size = self.pos, (fill_w, self.height)

    def set_percent(self, p):
        self.percent = min(1.0, max(0.0, p))
        self._upd()

    def update_bar_colors(self, track_color, fill_color):
        self.t_col.rgba, self.f_col.rgba = track_color, fill_color


class NavTabItem(ButtonBehavior, BoxLayout):
    def __init__(
        self,
        icon_type,
        title_text,
        is_active=False,
        pill_color=(0.29, 0.32, 0.36, 1),
        text_color=(1, 1, 1, 1),
        **kwargs,
    ):
        super().__init__(orientation="vertical", spacing=dp(2), padding=[dp(4), dp(4), dp(4), dp(4)], **kwargs)
        self.always_release = True
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
        self.label = make_label(title_text, size=11, halign="center", color=text_color, size_hint=(1, 0.42))
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


class ToastBanner(RoundedCard):
    # Всплывающее сверху уведомление о подключении устройства или неверном PIN
    on_touch_down = on_touch_move = on_touch_up = lambda self, touch: False

    def __init__(self, **kwargs):
        super().__init__(
            bg_color=(0.16, 0.18, 0.21, 0.96),
            border_color=(0.20, 0.78, 0.46, 0.80),
            radius=dp(18),
            orientation="horizontal",
            padding=[dp(14), dp(8), dp(14), dp(8)],
            spacing=dp(10),
            size_hint=(0.88, None),
            height=dp(42),
            pos_hint={"center_x": 0.5},
            **kwargs,
        )
        self.opacity = 0.0
        self.y = Window.height + dp(20)
        self.dot = StatusDot(dot_color=(0.20, 0.78, 0.46, 1), size_hint=(None, None), size=(dp(16), dp(16)), pos_hint={"center_y": 0.5})
        self.lbl = make_label("", size=12.5, halign="left", markup=True, shorten=True)
        self.add_widget(self.dot)
        self.add_widget(self.lbl)
        self._hide_ev = None

    def show_message(self, text, dot_color=(0.20, 0.78, 0.46, 1), text_color=(0.96, 0.97, 0.98, 1), bg_color=(0.16, 0.18, 0.21, 0.96)):
        if self._hide_ev is not None:
            self._hide_ev.cancel()
        self.lbl.text = f"[b]{text}[/b]"
        self.lbl.color = text_color
        self.dot.set_status_color(dot_color)
        self.update_colors(bg_color, (dot_color[0], dot_color[1], dot_color[2], 0.75))
        Animation.cancel_all(self)
        self.y = Window.height + dp(10)
        target_y = Window.height - dp(68)
        Animation(y=target_y, opacity=1.0, duration=0.25, t="out_back").start(self)
        self._hide_ev = Clock.schedule_once(self._hide, 2.8)

    def _hide(self, *_args):
        Animation(y=Window.height + dp(20), opacity=0.0, duration=0.22, t="in_quad").start(self)


class AppSplashScreen(FloatLayout):
    progress = NumericProperty(0.0)

    def __init__(self, lang="en", version="1.2.0", on_dismiss=None, **kwargs):
        super().__init__(size_hint=(1, 1), pos_hint={"x": 0, "y": 0}, **kwargs)
        self.on_dismiss = on_dismiss
        self.is_dismissed = False

        with self.canvas.before:
            self.bg_col = Color(0.08, 0.09, 0.10, 1.0)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        center_box = BoxLayout(
            orientation="vertical",
            spacing=dp(14),
            size_hint=(None, None),
            size=(dp(260), dp(305)),
            pos_hint={"center_x": 0.5, "center_y": 0.52},
        )

        icon_anchor = AnchorLayout(size_hint=(1, None), height=dp(136))
        icon_path = None
        for candidate in ("splash_logo.png", "icon.png", "1794233814531.jpg"):
            if os.path.exists(candidate):
                icon_path = candidate
                break

        if icon_path:
            self.icon_img = Image(source=icon_path, size_hint=(None, None), size=(dp(156), dp(128)), keep_ratio=True)
            icon_anchor.add_widget(self.icon_img)
        else:
            self.icon_img = VectorIcon(
                icon_type="pc", color=(0.20, 0.78, 0.46, 1), size_hint=(None, None), size=(dp(90), dp(90))
            )
            icon_anchor.add_widget(self.icon_img)
        center_box.add_widget(icon_anchor)

        self.title_lbl = make_label(
            "[b]AirShare PC[/b]",
            size=24,
            halign="center",
            markup=True,
            color=(0.96, 0.97, 0.98, 1),
            size_hint=(1, None),
            height=dp(32),
        )
        self.sub_lbl = make_label(
            tr("splash_sub", lang),
            size=13,
            halign="center",
            color=(0.58, 0.62, 0.68, 1),
            size_hint=(1, None),
            height=dp(20),
        )
        center_box.add_widget(self.title_lbl)
        center_box.add_widget(self.sub_lbl)

        bar_anchor = AnchorLayout(size_hint=(1, None), height=dp(28))
        self.bar = SlimProgressBar(
            percent=0.0,
            track_color=(0.18, 0.20, 0.23, 1),
            fill_color=(0.20, 0.78, 0.46, 1),
            size_hint=(0.80, None),
            height=dp(4.5),
        )
        bar_anchor.add_widget(self.bar)
        center_box.add_widget(bar_anchor)

        self.version_lbl = make_label(
            tr("splash_ver", lang, ver=version),
            size=11,
            halign="center",
            color=(0.40, 0.44, 0.50, 1),
            size_hint=(1, None),
            height=dp(18),
        )
        center_box.add_widget(self.version_lbl)

        self.add_widget(center_box)
        Clock.schedule_once(self._start_splash_anim, 0.05)

    def _upd_bg(self, *_args):
        self.bg_rect.pos, self.bg_rect.size = self.pos, self.size

    def _start_splash_anim(self, *_args):
        anim = Animation(progress=1.0, duration=0.85, t="in_out_sine")
        anim.bind(on_progress=lambda _a, _w, p: self.bar.set_percent(p))
        anim.bind(on_complete=self._finish_splash)
        anim.start(self)

    def _finish_splash(self, *_args):
        if self.is_dismissed:
            return
        self.is_dismissed = True
        fade = Animation(opacity=0.0, duration=0.32, t="out_quad")

        def _cleanup(*_):
            if self.parent:
                self.parent.remove_widget(self)
            if callable(self.on_dismiss):
                self.on_dismiss()

        fade.bind(on_complete=_cleanup)
        fade.start(self)

    def on_touch_down(self, touch):
        return not self.is_dismissed

    def on_touch_move(self, touch):
        return not self.is_dismissed

    def on_touch_up(self, touch):
        return not self.is_dismissed


class MacModalContainer(FloatLayout):
    scrim_alpha = NumericProperty(0.0)

    def __init__(self, card_widget, origin_pos=None, scrim_rgba=(0, 0, 0, 0.56), on_dismiss_cb=None, **kwargs):
        super().__init__(size_hint=(1, 1), pos_hint={"x": 0, "y": 0}, **kwargs)
        self.card, self.origin_pos, self.scrim_rgba, self.on_dismiss_cb, self.is_closing = (
            card_widget,
            origin_pos,
            scrim_rgba,
            on_dismiss_cb,
            False,
        )
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
        dx, dy = (
            ((self.origin_pos[0] - cx) * 0.55, (self.origin_pos[1] - cy) * 0.55) if self.origin_pos else (0, -dp(45))
        )
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
        dx, dy = (
            ((self.origin_pos[0] - cx) * 0.45, (self.origin_pos[1] - cy) * 0.45) if self.origin_pos else (0, -dp(35))
        )
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

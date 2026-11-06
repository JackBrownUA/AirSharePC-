"""
Main application file - Exact implementation of the approved Main Screen (1000250791.jpg)
and Floating Glass Side Drawer (1000250792.jpg) in a single self-contained Kivy module.
"""

import os
import threading
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
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
        "bg": (0.08, 0.09, 0.10, 1),
        "card_bg": (0.14, 0.15, 0.17, 0.96),
        "card_inner": (0.18, 0.20, 0.22, 0.95),
        "card_border": (0.26, 0.28, 0.31, 0.65),
        "radar_ring": (0.45, 0.48, 0.53, 0.22),
        "drawer_bg": (0.13, 0.14, 0.16, 0.97),
        "drawer_card": (0.20, 0.22, 0.25, 0.92),
        "drawer_border": (0.32, 0.35, 0.39, 0.70),
        "overlay": (0.0, 0.0, 0.0, 0.62),
        "text": (0.95, 0.96, 0.98, 1),
        "subtext": (0.60, 0.63, 0.68, 1),
        "pill_bg": (0.19, 0.21, 0.24, 1),
        "pill_active": (0.27, 0.30, 0.35, 1),
        "amber": (0.86, 0.62, 0.26, 1),
        "blue": (0.42, 0.68, 0.92, 1),
        "green": (0.24, 0.80, 0.52, 1),
    },
    "light": {
        "bg": (0.93, 0.94, 0.96, 1),
        "card_bg": (0.99, 0.99, 1.0, 0.98),
        "card_inner": (0.92, 0.93, 0.95, 1),
        "card_border": (0.82, 0.84, 0.88, 0.9),
        "radar_ring": (0.40, 0.44, 0.50, 0.18),
        "drawer_bg": (0.96, 0.97, 0.98, 0.98),
        "drawer_card": (0.90, 0.92, 0.95, 0.95),
        "drawer_border": (0.78, 0.80, 0.85, 0.9),
        "overlay": (0.0, 0.0, 0.0, 0.38),
        "text": (0.12, 0.13, 0.15, 1),
        "subtext": (0.45, 0.48, 0.54, 1),
        "pill_bg": (0.87, 0.89, 0.92, 1),
        "pill_active": (0.76, 0.80, 0.86, 1),
        "amber": (0.85, 0.55, 0.16, 1),
        "blue": (0.16, 0.52, 0.88, 1),
        "green": (0.16, 0.66, 0.40, 1),
    },
}


class RoundedCard(BoxLayout):
    """Universal rounded card container with border"""

    def __init__(self, bg_color, border_color=(0, 0, 0, 0), radius=18, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.border_color = border_color
        self.radius_val = radius
        with self.canvas.before:
            self.col = Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius_val])
            self.b_col = Color(*self.border_color)
            self.line = Line(
                rounded_rectangle=[self.x, self.y, self.width, self.height, self.radius_val],
                width=1.0,
            )
        self.bind(pos=self._update, size=self._update)

    def _update(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        self.line.rounded_rectangle = [self.x, self.y, self.width, self.height, self.radius_val]

    def update_colors(self, bg_color, border_color=(0, 0, 0, 0)):
        self.col.rgba = bg_color
        self.b_col.rgba = border_color


class RadarCard(RoundedCard):
    """Top radar discovery card with concentric rings matching 1000250791.jpg"""

    def __init__(self, bg_color, border_color, ring_color, **kwargs):
        super().__init__(bg_color=bg_color, border_color=border_color, radius=22, **kwargs)
        with self.canvas.before:
            self.ring_col = Color(*ring_color)
            self.ring1 = Line(circle=(0, 0, 10), width=1.0)
            self.ring2 = Line(circle=(0, 0, 20), width=1.0)
            self.ring3 = Line(circle=(0, 0, 30), width=1.0)
        self.bind(pos=self._update_rings, size=self._update_rings)

    def _update_rings(self, *args):
        cx = self.center_x
        cy = self.center_y + 12
        base_r = min(self.width, self.height) * 0.22
        self.ring1.circle = (cx, cy, base_r)
        self.ring2.circle = (cx, cy, base_r * 1.55)
        self.ring3.circle = (cx, cy, base_r * 2.10)

    def update_radar_colors(self, bg_color, border_color, ring_color):
        self.update_colors(bg_color, border_color)
        self.ring_col.rgba = ring_color


class SlimProgressBar(Widget):
    """Sleek rounded progress bar used in storage, folders, and transfers"""

    def __init__(self, percent=0.45, track_color=(0.22, 0.24, 0.27, 1), fill_color=(0.86, 0.62, 0.26, 1), **kwargs):
        super().__init__(**kwargs)
        self.percent = percent
        with self.canvas:
            self.t_col = Color(*track_color)
            self.t_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[3])
            self.f_col = Color(*fill_color)
            self.f_rect = RoundedRectangle(pos=self.pos, size=(self.width * self.percent, self.height), radius=[3])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *args):
        self.t_rect.pos = self.pos
        self.t_rect.size = self.size
        self.f_rect.pos = self.pos
        self.f_rect.size = (max(6, self.width * self.percent), self.height)

    def set_percent(self, p):
        self.percent = min(1.0, max(0.0, p))
        self._upd()

    def update_bar_colors(self, track_color, fill_color):
        self.t_col.rgba = track_color
        self.f_col.rgba = fill_color


class AirShareApp(App):
    server = None
    is_stopping = False
    connected_pc_title = "Desktop PC"
    connected_pc_os = "Windows 11"

    def build(self):
        self.title = f"{APP_NAME} v{APP_VERSION}"
        request_android_full_storage()

        settings = load_settings()
        self.theme_mode = settings.get("theme_mode", "dark")
        self.server_port = settings.get("port", SERVER_PORT)
        self.saved_password = settings.get("password", "")

        p = THEMES["dark"]
        self.root_widget = FloatLayout()

        # =====================================================================
        # ГЛАВНЫЙ ЭКРАН (точ-в-точь по макету 1000250791.jpg)
        # =====================================================================
        self.main_content = BoxLayout(orientation="vertical", padding=[18, 14, 18, 14], spacing=12)

        # 1. Шапка: Модель телефона слева, капсула Wi-Fi 6 • 5GHz и иконка шестерёнки справа
        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=42, spacing=8)
        self.device_label = Label(
            text=f"[b]{get_device_info()}[/b]",
            markup=True,
            font_size="20sp",
            halign="left",
            valign="middle",
            size_hint=(0.50, 1),
        )
        self.device_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        self.wifi_pill = RoundedCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=16,
            size_hint=(0.36, None),
            height=32,
            pos_hint={"center_y": 0.5},
            padding=[8, 2, 8, 2],
        )
        self.wifi_label = Label(text="🛜 Wi-Fi 6 • 5GHz", font_size="12sp", halign="center", valign="middle")
        self.wifi_pill.add_widget(self.wifi_label)

        self.gear_btn = Button(
            text="⚙",
            font_size="21sp",
            size_hint=(None, None),
            size=(38, 38),
            pos_hint={"center_y": 0.5},
            background_normal="",
            background_color=(0, 0, 0, 0),
        )
        self.gear_btn.bind(on_press=self.toggle_drawer)

        header.add_widget(self.device_label)
        header.add_widget(self.wifi_pill)
        header.add_widget(self.gear_btn)
        self.main_content.add_widget(header)

        # 2. Центральная карточка с радаром (Radar Card)
        self.radar_card = RadarCard(
            bg_color=p["card_bg"],
            border_color=p["card_border"],
            ring_color=p["radar_ring"],
            orientation="vertical",
            padding=[16, 18, 16, 14],
            spacing=6,
            size_hint=(1, 0.37),
        )

        self.monitor_icon = Label(
            text="🖥",
            font_size="34sp",
            size_hint=(1, 0.36),
            halign="center",
            valign="bottom",
        )

        self.pc_title_label = Label(
            text=f"[b]{self.connected_pc_title}[/b]  [size=11sp][{self.connected_pc_os}][/size]\n[size=12sp]850 Mbps • Нажмите «Transfer» для старта[/size]",
            markup=True,
            font_size="16sp",
            halign="center",
            valign="top",
            size_hint=(1, 0.36),
        )
        self.pc_title_label.bind(size=lambda i, v: setattr(i, "text_size", v))

        # Нижняя строка радара: капсула адреса по центру и кнопка копирования справа
        addr_row = FloatLayout(size_hint=(1, 0.28))
        self.addr_pill = RoundedCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=16,
            size_hint=(0.64, None),
            height=34,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self.addr_label = Label(
            text=f"http://{get_local_ip()}:{self.server_port}",
            font_size="13sp",
            halign="center",
            valign="middle",
        )
        self.addr_pill.add_widget(self.addr_label)

        self.copy_btn = Button(
            text="⧉",
            font_size="18sp",
            size_hint=(None, None),
            size=(36, 36),
            pos_hint={"right": 0.98, "center_y": 0.5},
            background_normal="",
            background_color=(0, 0, 0, 0),
        )
        self.copy_btn.bind(on_press=self.copy_address)

        addr_row.add_widget(self.addr_pill)
        addr_row.add_widget(self.copy_btn)

        self.radar_card.add_widget(self.monitor_icon)
        self.radar_card.add_widget(self.pc_title_label)
        self.radar_card.add_widget(addr_row)
        self.main_content.add_widget(self.radar_card)

        # 3. Секция Shared Folders (3 карточки с индикаторами внизу)
        self.folders_header = Label(
            text="[b]Shared Folders[/b]",
            markup=True,
            font_size="15sp",
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=22,
        )
        self.folders_header.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.main_content.add_widget(self.folders_header)

        folders_grid = GridLayout(cols=3, spacing=10, size_hint=(1, 0.20))

        self.folder_cards = []
        folder_specs = [
            ("Downloads", "⬇", 0.42, p["amber"]),
            ("Camera Roll", "🖼", 0.65, p["subtext"]),
            ("Documents", "📄", 0.28, p["subtext"]),
        ]
        for title_txt, icon_txt, prog, col_bar in folder_specs:
            card = RoundedCard(
                bg_color=p["card_bg"],
                border_color=p["card_border"],
                radius=15,
                orientation="vertical",
                padding=[10, 8, 10, 8],
                spacing=4,
            )
            lbl_top = Label(text=title_txt, font_size="12sp", halign="left", valign="middle", size_hint=(1, 0.28))
            lbl_top.bind(size=lambda i, v: setattr(i, "text_size", v))
            lbl_ico = Label(text=icon_txt, font_size="24sp", halign="center", valign="middle", size_hint=(1, 0.56))
            bar = SlimProgressBar(percent=prog, track_color=p["pill_bg"], fill_color=col_bar, size_hint=(1, None), height=4)
            card.add_widget(lbl_top)
            card.add_widget(lbl_ico)
            card.add_widget(bar)
            folders_grid.add_widget(card)
            self.folder_cards.append((card, lbl_top, lbl_ico, bar))

        self.main_content.add_widget(folders_grid)

        # 4. Секция Recent Transfers (2 строки с прогресс-барами, как на макете)
        self.transfers_header = Label(
            text="[b]Recent Transfers[/b]",
            markup=True,
            font_size="15sp",
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=22,
        )
        self.transfers_header.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.main_content.add_widget(self.transfers_header)

        self.transfers_card = RoundedCard(
            bg_color=p["card_bg"],
            border_color=p["card_border"],
            radius=16,
            orientation="vertical",
            padding=[12, 10, 12, 10],
            spacing=8,
            size_hint=(1, 0.22),
        )

        row1 = BoxLayout(orientation="horizontal", spacing=10, size_hint=(1, 0.5))
        ico1 = RoundedCard(bg_color=(0.55, 0.40, 0.20, 0.9), radius=8, size_hint=(None, None), size=(34, 34), pos_hint={"center_y": 0.5})
        ico1.add_widget(Label(text="📦", font_size="16sp"))
        info1 = BoxLayout(orientation="vertical", spacing=3)
        top1 = BoxLayout(orientation="horizontal", size_hint=(1, 0.45))
        self.tr1_name = Label(text="Project_Archive.zip", font_size="13sp", halign="left", size_hint=(0.75, 1))
        self.tr1_name.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.tr1_pct = Label(text="100%", font_size="12sp", halign="right", size_hint=(0.25, 1))
        self.tr1_pct.bind(size=lambda i, v: setattr(i, "text_size", v))
        top1.add_widget(self.tr1_name)
        top1.add_widget(self.tr1_pct)
        self.tr1_bar = SlimProgressBar(percent=1.0, track_color=p["pill_bg"], fill_color=p["amber"], size_hint=(1, None), height=4)
        self.tr1_sub = Label(text="✓ Completed", font_size="11sp", halign="left", size_hint=(1, 0.4))
        self.tr1_sub.bind(size=lambda i, v: setattr(i, "text_size", v))
        info1.add_widget(top1)
        info1.add_widget(self.tr1_bar)
        info1.add_widget(self.tr1_sub)
        row1.add_widget(ico1)
        row1.add_widget(info1)

        row2 = BoxLayout(orientation="horizontal", spacing=10, size_hint=(1, 0.5))
        ico2 = RoundedCard(bg_color=p["pill_bg"], radius=8, size_hint=(None, None), size=(34, 34), pos_hint={"center_y": 0.5})
        ico2.add_widget(Label(text="🖼", font_size="16sp"))
        info2 = BoxLayout(orientation="vertical", spacing=3)
        top2 = BoxLayout(orientation="horizontal", size_hint=(1, 0.45))
        self.tr2_name = Label(text="IMG_8492.raw", font_size="13sp", halign="left", size_hint=(0.75, 1))
        self.tr2_name.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.tr2_pct = Label(text="64%", font_size="12sp", halign="right", size_hint=(0.25, 1))
        self.tr2_pct.bind(size=lambda i, v: setattr(i, "text_size", v))
        top2.add_widget(self.tr2_name)
        top2.add_widget(self.tr2_pct)
        self.tr2_bar = SlimProgressBar(percent=0.64, track_color=p["pill_bg"], fill_color=p["blue"], size_hint=(1, None), height=4)
        self.tr2_sub = Label(text="45 MB/s", font_size="11sp", halign="right", size_hint=(1, 0.4))
        self.tr2_sub.bind(size=lambda i, v: setattr(i, "text_size", v))
        info2.add_widget(top2)
        info2.add_widget(self.tr2_bar)
        info2.add_widget(self.tr2_sub)
        row2.add_widget(ico2)
        row2.add_widget(info2)

        self.transfers_card.add_widget(row1)
        self.transfers_card.add_widget(row2)
        self.main_content.add_widget(self.transfers_card)

        # 5. Нижняя панель навигации (Transfer | Files | Devices | Settings)
        self.bottom_nav = RoundedCard(
            bg_color=p["card_bg"],
            border_color=p["card_border"],
            radius=22,
            orientation="horizontal",
            padding=[8, 6, 8, 6],
            spacing=6,
            size_hint=(1, None),
            height=58,
        )

        self.nav_transfer_btn = Button(
            text="⇄\n[size=11sp]Transfer[/size]",
            markup=True,
            halign="center",
            font_size="15sp",
            background_normal="",
            background_color=p["pill_active"],
        )
        self.nav_transfer_btn.bind(on_press=self.toggle_server)

        self.nav_files_btn = Button(
            text="📁\n[size=11sp]Files[/size]",
            markup=True,
            halign="center",
            font_size="15sp",
            background_normal="",
            background_color=(0, 0, 0, 0),
        )
        self.nav_files_btn.bind(on_press=self.open_shared_folders_modal)

        self.nav_devices_btn = Button(
            text="📱\n[size=11sp]Devices[/size]",
            markup=True,
            halign="center",
            font_size="15sp",
            background_normal="",
            background_color=(0, 0, 0, 0),
        )
        self.nav_devices_btn.bind(on_press=self.open_devices_modal)

        self.nav_settings_btn = Button(
            text="⚙\n[size=11sp]Settings[/size]",
            markup=True,
            halign="center",
            font_size="15sp",
            background_normal="",
            background_color=(0, 0, 0, 0),
        )
        self.nav_settings_btn.bind(on_press=self.toggle_drawer)

        self.bottom_nav.add_widget(self.nav_transfer_btn)
        self.bottom_nav.add_widget(self.nav_files_btn)
        self.bottom_nav.add_widget(self.nav_devices_btn)
        self.bottom_nav.add_widget(self.nav_settings_btn)
        self.main_content.add_widget(self.bottom_nav)

        self.root_widget.add_widget(self.main_content)

        # =====================================================================
        # БОКОВАЯ ПАРЯЩАЯ ШТОРКА (точ-в-точь по макету 1000250792.jpg)
        # =====================================================================
        self.overlay = Button(
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
            background_normal="",
            background_color=(0, 0, 0, 0),
        )
        self.overlay.bind(on_press=self.close_drawer)
        self.overlay.disabled = True
        self.root_widget.add_widget(self.overlay)

        self.drawer_width = 285
        self.drawer = RoundedCard(
            bg_color=p["drawer_bg"],
            border_color=p["drawer_border"],
            radius=26,
            orientation="vertical",
            padding=[20, 22, 20, 18],
            spacing=12,
            size_hint=(None, None),
            width=self.drawer_width,
            height=Window.height - 44,
            pos=(-self.drawer_width - 30, 22),
        )
        Window.bind(size=self._on_window_resize)

        # 1) Заголовок AirShare PC
        self.drawer_title = Label(
            text=f"[b]{APP_NAME}[/b]",
            markup=True,
            font_size="22sp",
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=30,
        )
        self.drawer_title.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.drawer.add_widget(self.drawer_title)

        # 2) Строка с иконкой телефона и реальной моделью устройства
        self.drawer_phone_label = Label(
            text=f"📱  {get_device_info()}",
            font_size="15sp",
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=28,
        )
        self.drawer_phone_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.drawer.add_widget(self.drawer_phone_label)

        # 3) Карточка Storage: XX.X GB / XXX GB
        stats = get_storage_stats()
        self.drawer_storage_card = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=15,
            orientation="vertical",
            padding=[14, 10, 14, 10],
            spacing=8,
            size_hint=(1, None),
            height=64,
        )
        self.drawer_storage_label = Label(
            text=f"Storage: [b]{stats['free_gb']} GB[/b] / {stats['total_gb']} GB",
            markup=True,
            font_size="13sp",
            halign="left",
            valign="middle",
            size_hint=(1, 0.55),
        )
        self.drawer_storage_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.drawer_storage_bar = SlimProgressBar(
            percent=stats["percent"],
            track_color=p["pill_bg"],
            fill_color=p["text"],
            size_hint=(1, None),
            height=5,
        )
        self.drawer_storage_card.add_widget(self.drawer_storage_label)
        self.drawer_storage_card.add_widget(self.drawer_storage_bar)
        self.drawer.add_widget(self.drawer_storage_card)

        # 4) Карточка подключённого ПК
        self.drawer_pc_card = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=15,
            orientation="horizontal",
            padding=[14, 10, 14, 10],
            spacing=12,
            size_hint=(1, None),
            height=68,
        )
        self.drawer_pc_icon = Label(text="🖥", font_size="24sp", size_hint=(None, 1), width=32)
        self.drawer_pc_label = Label(
            text=f"[b]{self.connected_pc_title}[/b]\n[size=12sp]{self.connected_pc_os}[/size]",
            markup=True,
            font_size="14sp",
            halign="left",
            valign="middle",
            size_hint=(1, 1),
        )
        self.drawer_pc_label.bind(size=lambda i, v: setattr(i, "text_size", v))
        self.drawer_pc_card.add_widget(self.drawer_pc_icon)
        self.drawer_pc_card.add_widget(self.drawer_pc_label)
        self.drawer.add_widget(self.drawer_pc_card)

        # 5) 4 строки пунктов меню со стрелками справа
        menu_box = BoxLayout(orientation="vertical", spacing=4, size_hint=(1, 1))
        self.menu_buttons = []
        menu_Rows = [
            ("📁   Shared Folders", self.open_shared_folders_modal),
            ("🔒   Security & PIN", self.open_security_modal),
            ("🎚   Port Settings", self.open_port_modal),
            ("ⓘ   Help & Feedback", self.open_help_modal),
        ]
        for label_text, callback in menu_Rows:
            row_btn = BoxLayout(orientation="horizontal", size_hint=(1, None), height=44)
            btn_left = Button(
                text=label_text,
                font_size="14sp",
                halign="left",
                valign="middle",
                size_hint=(0.88, 1),
                background_normal="",
                background_color=(0, 0, 0, 0),
            )
            btn_left.bind(size=lambda i, v: setattr(i, "text_size", v))
            btn_left.bind(on_press=callback)

            btn_chev = Button(
                text="›",
                font_size="20sp",
                size_hint=(0.12, 1),
                background_normal="",
                background_color=(0, 0, 0, 0),
            )
            btn_chev.bind(on_press=callback)

            row_btn.add_widget(btn_left)
            row_btn.add_widget(btn_chev)
            menu_box.add_widget(row_btn)
            self.menu_buttons.append((btn_left, btn_chev))

        self.drawer.add_widget(menu_box)

        # 6) Сегментный переключатель темы (Dark | Light | Auto)
        self.theme_pill_container = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=18,
            orientation="horizontal",
            padding=4,
            spacing=4,
            size_hint=(1, None),
            height=40,
        )
        self.t_btn_dark = Button(text="🌙 Dark", font_size="12sp", background_normal="")
        self.t_btn_dark.bind(on_press=lambda *_: self.set_theme_mode("dark"))
        self.t_btn_light = Button(text="☀ Light", font_size="12sp", background_normal="")
        self.t_btn_light.bind(on_press=lambda *_: self.set_theme_mode("light"))
        self.t_btn_auto = Button(text="🔆 Auto", font_size="12sp", background_normal="")
        self.t_btn_auto.bind(on_press=lambda *_: self.set_theme_mode("system"))

        self.theme_pill_container.add_widget(self.t_btn_dark)
        self.theme_pill_container.add_widget(self.t_btn_light)
        self.theme_pill_container.add_widget(self.t_btn_auto)
        self.drawer.add_widget(self.theme_pill_container)

        self.root_widget.add_widget(self.drawer)

        AirShareHandler.on_client_connected = self._on_client_connected
        AirShareHandler.on_file_transfer = self._on_file_transfer
        self.apply_theme()
        return self.root_widget

    def _on_window_resize(self, _inst, _val):
        self.drawer.height = Window.height - 44

    def toggle_drawer(self, *_args):
        if self.drawer.x < 0:
            self.open_drawer()
        else:
            self.close_drawer()

    def open_drawer(self, *_args):
        self.overlay.disabled = False
        stats = get_storage_stats()
        self.drawer_storage_label.text = f"Storage: [b]{stats['free_gb']} GB[/b] / {stats['total_gb']} GB"
        self.drawer_storage_bar.set_percent(stats["percent"])
        eff = self._get_effective_theme()
        palette = THEMES.get(eff, THEMES["dark"])
        Animation(background_color=palette["overlay"], duration=0.22).start(self.overlay)
        Animation(x=18, duration=0.25, t="out_cubic").start(self.drawer)

    def close_drawer(self, *_args):
        self.overlay.disabled = True
        Animation(background_color=(0, 0, 0, 0), duration=0.18).start(self.overlay)
        Animation(x=-self.drawer_width - 35, duration=0.22, t="out_cubic").start(self.drawer)

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
        AirShareHandler.default_theme = eff

        Window.clearcolor = p["bg"]
        self.device_label.color = p["text"]
        self.wifi_pill.update_colors(p["pill_bg"], p["card_border"])
        self.wifi_label.color = p["text"]
        self.gear_btn.color = p["subtext"]

        self.radar_card.update_radar_colors(p["card_bg"], p["card_border"], p["radar_ring"])
        self.monitor_icon.color = p["text"]
        self.pc_title_label.color = p["text"]
        self.addr_pill.update_colors(p["pill_bg"], p["card_border"])
        self.addr_label.color = p["text"]
        self.copy_btn.color = p["subtext"]

        self.folders_header.color = p["text"]
        for idx, (card, lbl_top, lbl_ico, bar) in enumerate(self.folder_cards):
            card.update_colors(p["card_bg"], p["card_border"])
            lbl_top.color = p["text"]
            lbl_ico.color = p["amber"] if idx == 0 else p["text"]
            bar.update_bar_colors(p["pill_bg"], p["amber"] if idx == 0 else p["subtext"])

        self.transfers_header.color = p["text"]
        self.transfers_card.update_colors(p["card_bg"], p["card_border"])
        self.tr1_name.color = p["text"]
        self.tr1_pct.color = p["subtext"]
        self.tr1_sub.color = p["subtext"]
        self.tr1_bar.update_bar_colors(p["pill_bg"], p["amber"])
        self.tr2_name.color = p["text"]
        self.tr2_pct.color = p["subtext"]
        self.tr2_sub.color = p["subtext"]
        self.tr2_bar.update_bar_colors(p["pill_bg"], p["blue"])

        self.bottom_nav.update_colors(p["card_bg"], p["card_border"])
        self.nav_transfer_btn.background_color = p["green"] if self.server is not None else p["pill_active"]
        self.nav_transfer_btn.color = p["text"]
        for b in (self.nav_files_btn, self.nav_devices_btn, self.nav_settings_btn):
            b.color = p["subtext"]

        self.drawer.update_colors(p["drawer_bg"], p["drawer_border"])
        self.drawer_title.color = p["text"]
        self.drawer_phone_label.color = p["text"]
        self.drawer_storage_card.update_colors(p["drawer_card"], p["drawer_border"])
        self.drawer_storage_label.color = p["text"]
        self.drawer_storage_bar.update_bar_colors(p["pill_bg"], p["text"])
        self.drawer_pc_card.update_colors(p["drawer_card"], p["drawer_border"])
        self.drawer_pc_icon.color = p["text"]
        self.drawer_pc_label.color = p["text"]

        for btn_l, btn_c in self.menu_buttons:
            btn_l.color = p["text"]
            btn_c.color = p["subtext"]

        self.theme_pill_container.update_colors(p["drawer_card"], p["drawer_border"])
        self.t_btn_dark.background_color = p["pill_active"] if self.theme_mode == "dark" else (0, 0, 0, 0)
        self.t_btn_light.background_color = p["pill_active"] if self.theme_mode == "light" else (0, 0, 0, 0)
        self.t_btn_auto.background_color = p["pill_active"] if self.theme_mode == "system" else (0, 0, 0, 0)
        for tb in (self.t_btn_dark, self.t_btn_light, self.t_btn_auto):
            tb.color = p["text"]

    def copy_address(self, _instance):
        url = f"http://{get_local_ip()}:{self.server_port}"
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(url)
            self.addr_label.text = "Скопировано в буфер!"
            Clock.schedule_once(lambda _: setattr(self.addr_label, "text", url), 1.8)
        except Exception:
            pass

    def _on_client_connected(self, device_title, os_badge, ip):
        def _upd(_dt):
            self.connected_pc_title = device_title
            self.connected_pc_os = os_badge
            self.pc_title_label.text = (
                f"[b]{device_title}[/b]  [size=11sp][{os_badge}][/size]\n"
                f"[size=12sp]850 Mbps • {ip} подключён[/size]"
            )
            self.drawer_pc_label.text = f"[b]{device_title}[/b]\n[size=12sp]{os_badge} • {ip}[/size]"
        Clock.schedule_once(_upd, 0)

    def _on_file_transfer(self, filename, size_str, direction):
        def _upd(_dt):
            self.tr2_name.text = self.tr1_name.text
            self.tr2_pct.text = self.tr1_pct.text
            self.tr2_sub.text = self.tr1_sub.text
            self.tr2_bar.set_percent(1.0)

            self.tr1_name.text = filename
            self.tr1_pct.text = "100%"
            action_ru = "Загружено на телефон" if direction == "upload" else "Скачано на ПК"
            self.tr1_sub.text = f"✓ {action_ru} • {size_str}"
            self.tr1_bar.set_percent(1.0)
        Clock.schedule_once(_upd, 0)

    def toggle_server(self, *_args):
        if self.is_stopping:
            return

        if self.server is None:
            settings = load_settings()
            self.saved_password = settings.get("password", "")
            self.server_port = settings.get("port", SERVER_PORT)
            AirShareHandler.current_password = self.saved_password
            AirShareHandler.default_theme = self._get_effective_theme()

            ip = get_local_ip()
            url = f"http://{ip}:{self.server_port}"
            self.addr_label.text = url

            try:
                self.server = ReusableThreadingServer(("", self.server_port), AirShareHandler)
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
            except OSError as e:
                self.server = None
                self.pc_title_label.text = f"[b]Ошибка запуска[/b]\n[size=12sp]{e}[/size]"
                return

            self.pc_title_label.text = (
                f"[b]{self.connected_pc_title}[/b]  [size=11sp][{self.connected_pc_os}][/size]\n"
                f"[size=12sp][color=30d158]● Онлайн • 850 Mbps[/color][/size]"
            )
            self.apply_theme()
        else:
            self.is_stopping = True
            srv = self.server
            self.server = None

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
        self.pc_title_label.text = (
            f"[b]{self.connected_pc_title}[/b]  [size=11sp][{self.connected_pc_os}][/size]\n"
            f"[size=12sp]Сервер остановлен (нажмите Transfer)[/size]"
        )
        self.apply_theme()

    # =====================================================================
    # МОДАЛЬНЫЕ ОКНА НАСТРОЕК (PIN-код, Порт, Папки, История устройств)
    # =====================================================================
    def _create_modal(self, title_text, height=260):
        self.close_drawer()
        p = THEMES.get(self._get_effective_theme(), THEMES["dark"])
        modal = ModalView(size_hint=(0.88, None), height=height, background="", background_color=(0, 0, 0, 0.6))
        card = RoundedCard(bg_color=p["drawer_bg"], border_color=p["drawer_border"], radius=20, orientation="vertical", padding=18, spacing=12)
        hdr = Label(text=f"[b]{title_text}[/b]", markup=True, font_size="17sp", color=p["text"], size_hint=(1, None), height=28)
        card.add_widget(hdr)
        modal.add_widget(card)
        return modal, card, p

    def open_security_modal(self, *_args):
        modal, card, p = self._create_modal("🔒 Security & PIN", height=250)
        settings = load_settings()
        inp = TextInput(
            text=settings.get("password", ""),
            hint_text="Введите пароль (пусто — без пароля)",
            multiline=False,
            size_hint=(1, None),
            height=44,
            font_size="15sp",
            background_color=p["drawer_card"],
            foreground_color=p["text"],
            padding=[12, 10, 12, 10],
        )
        card.add_widget(inp)

        btn_row = BoxLayout(orientation="horizontal", spacing=10, size_hint=(1, None), height=42)
        btn_clear = Button(text="Без пароля", background_normal="", background_color=p["pill_bg"], color=p["text"])
        btn_save = Button(text="Сохранить PIN", background_normal="", background_color=p["blue"], color=(1, 1, 1, 1))

        def _save_pwd(_b):
            new_pwd = inp.text.strip()
            save_settings(password=new_pwd)
            AirShareHandler.current_password = new_pwd
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
        modal, card, p = self._create_modal("🎚 Port Settings", height=240)
        inp = TextInput(
            text=str(self.server_port),
            hint_text="Порт HTTP-сервера (например, 8080)",
            input_filter="int",
            multiline=False,
            size_hint=(1, None),
            height=44,
            font_size="15sp",
            background_color=p["drawer_card"],
            foreground_color=p["text"],
            padding=[12, 10, 12, 10],
        )
        card.add_widget(inp)

        btn_save = Button(text="Сохранить порт", size_hint=(1, None), height=42, background_normal="", background_color=p["blue"], color=(1, 1, 1, 1))

        def _save_port(_b):
            try:
                val = int(inp.text.strip())
                if 1024 <= val <= 65535:
                    self.server_port = val
                    save_settings(port=val)
                    self.addr_label.text = f"http://{get_local_ip()}:{self.server_port}"
            except Exception:
                pass
            modal.dismiss()

        btn_save.bind(on_press=_save_port)
        card.add_widget(btn_save)
        modal.open()

    def open_devices_modal(self, *_args):
        modal, card, p = self._create_modal("📱 История подключений (IP)", height=300)
        ips = load_settings().get("recent_ips", [])
        txt = "\n".join(f"• {x}" for x in ips[:6]) if ips else "Пока нет сохранённых подключений"
        lbl = Label(text=txt, font_size="13sp", color=p["text"], halign="left", valign="top")
        lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        card.add_widget(lbl)

        btn_row = BoxLayout(orientation="horizontal", spacing=10, size_hint=(1, None), height=40)
        btn_clr = Button(text="Очистить историю", background_normal="", background_color=p["pill_bg"], color=p["text"])
        btn_ok = Button(text="Закрыть", background_normal="", background_color=p["blue"], color=(1, 1, 1, 1))

        def _clear(_b):
            save_settings(recent_ips=[])
            lbl.text = "История очищена"

        btn_clr.bind(on_press=_clear)
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        btn_row.add_widget(btn_clr)
        btn_row.add_widget(btn_ok)
        card.add_widget(btn_row)
        modal.open()

    def open_shared_folders_modal(self, *_args):
        modal, card, p = self._create_modal("📁 Shared Folders", height=240)
        lbl = Label(
            text=f"Активная корневая папка:\n[b]{STORAGE_PATH}[/b]\n\nДоступны разделы: Downloads, DCIM/Camera, Documents.",
            markup=True,
            font_size="13sp",
            color=p["text"],
            halign="center",
        )
        lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        card.add_widget(lbl)
        btn_ok = Button(text="Готово", size_hint=(1, None), height=40, background_normal="", background_color=p["blue"], color=(1, 1, 1, 1))
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)
        modal.open()

    def open_help_modal(self, *_args):
        modal, card, p = self._create_modal("ⓘ Help & Feedback", height=250)
        lbl = Label(
            text=(
                f"[b]{APP_NAME} v{APP_VERSION}[/b]\n\n"
                "1. Нажмите кнопку «Transfer» внизу для запуска сервера.\n"
                "2. Откройте адрес http://<IP>:8080 в браузере на ПК в той же сети Wi-Fi."
            ),
            markup=True,
            font_size="13sp",
            color=p["text"],
            halign="left",
        )
        lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        card.add_widget(lbl)
        btn_ok = Button(text="Понятно", size_hint=(1, None), height=40, background_normal="", background_color=p["blue"], color=(1, 1, 1, 1))
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)
        modal.open()


if __name__ == "__main__":
    AirShareApp().run()

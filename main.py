# Главный модуль приложения AirShare PC: управление жизненным циклом Kivy UI и фоновым HTTP-сервером

import logging
import os
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput

from config import APP_NAME, APP_VERSION, SERVER_PORT, STORAGE_PATH
from server import AirShareHandler, ReusableThreadingServer
from themes import THEMES
from ui_widgets import (
    AnimatedToggleSwitch,
    ClickableCard,
    DrawerMenuRow,
    DrawerOverlay,
    DrawerPanel,
    MacModalContainer,
    NavTabItem,
    RadarCard,
    RoundedActionButton,
    RoundedCard,
    SlimProgressBar,
    StatusDot,
    VectorIcon,
    make_label,
)
from utils import (
    generate_pin,
    get_device_info,
    get_device_theme,
    get_local_ip,
    get_network_label,
    get_storage_stats,
    load_settings,
    request_android_full_storage,
    save_settings,
)

logger = logging.getLogger("airshare.app")


class DynamicAirShareHandler(AirShareHandler):
    # Позволяет менять раздаваемую папку (All Storage, Downloads, DCIM, Documents) без перезапуска приложения
    active_storage_path = STORAGE_PATH

    def __init__(self, *args, **kwargs):
        target = self.active_storage_path
        if not target or not os.path.isdir(target):
            target = STORAGE_PATH if os.path.isdir(STORAGE_PATH) else os.path.expanduser("~")
        self.real_storage = os.path.realpath(target)
        SimpleHTTPRequestHandler.__init__(self, *args, directory=self.real_storage, **kwargs)


class AirShareApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Все изменяемые состояния храним на экземпляре приложения, а не в атрибутах класса
        self.server = None
        self.is_stopping = False
        self.has_server_error = False
        self.active_folder_key = "All Storage"
        self.active_nav_tab = "transfer"
        self.keep_alive_locked = True
        self._wake_lock = None
        self._wifi_lock = None
        self.transfer_history = []
        self.active_modal = None
        self.theme_mode = "dark"
        self.server_port = SERVER_PORT
        self.saved_password = ""

    def _get_folder_map(self):
        base = STORAGE_PATH if os.path.isdir(STORAGE_PATH) else os.path.expanduser("~")
        return {
            "All Storage": (base, "folder", "Вся память устройства"),
            "Downloads": (os.path.join(base, "Download"), "download", "Загрузки из браузера и мессенджеров"),
            "Camera Roll": (os.path.join(base, "DCIM"), "gallery", "Фотографии и видео с камеры"),
            "Documents": (os.path.join(base, "Documents"), "document", "Документы и рабочие файлы"),
        }

    def get_connection_url(self):
        # Экранируем PIN через urllib.parse.quote, чтобы спецсимволы не ломали URL авторизации
        ip = get_local_ip()
        pwd = (self.saved_password or "").strip()
        if not pwd:
            pwd = load_settings().get("password", "")
            self.saved_password = pwd
        quoted_pwd = urllib.parse.quote(pwd, safe="")
        return f"http://airshare:{quoted_pwd}@{ip}:{self.server_port}"

    def update_connection_url_display(self):
        url = self.get_connection_url()
        self.addr_label.text = url
        self.addr_label.font_size = sp(10.5) if len(url) > 38 else (sp(11.5) if len(url) > 30 else sp(13.5))

    def set_keep_alive(self, enabled):
        # Удерживаем CPU WakeLock и высокопроизводительный WifiLock, чтобы передача не обрывалась при гашении экрана
        self.keep_alive_locked = bool(enabled)
        if hasattr(self, "keep_alive_switch"):
            self.keep_alive_switch.set_active(self.keep_alive_locked, animate=True)
        try:
            Window.allow_screensaver = not self.keep_alive_locked
        except Exception as exc:
            logger.debug("Не удалось изменить Window.allow_screensaver: %s", exc)
        try:
            from kivy.utils import platform
            if platform == "android":
                from jnius import autoclass
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = getattr(PythonActivity, "mActivity", None)
                if activity is not None:
                    Context = autoclass("android.content.Context")
                    PowerManager = autoclass("android.os.PowerManager")
                    WifiManager = autoclass("android.net.wifi.WifiManager")
                    if self.keep_alive_locked:
                        if self._wake_lock is None:
                            pm = activity.getSystemService(Context.POWER_SERVICE)
                            if pm is not None:
                                self._wake_lock = pm.newWakeLock(
                                    PowerManager.PARTIAL_WAKE_LOCK, "AirSharePC::WakeLock"
                                )
                        if self._wake_lock is not None and not self._wake_lock.isHeld():
                            self._wake_lock.acquire()

                        if self._wifi_lock is None:
                            wm = activity.getApplicationContext().getSystemService(Context.WIFI_SERVICE)
                            if wm is not None:
                                self._wifi_lock = wm.createWifiLock(
                                    WifiManager.WIFI_MODE_FULL_HIGH_PERF, "AirSharePC::WifiLock"
                                )
                        if self._wifi_lock is not None and not self._wifi_lock.isHeld():
                            self._wifi_lock.acquire()
                    else:
                        if self._wake_lock is not None and self._wake_lock.isHeld():
                            self._wake_lock.release()
                        if self._wifi_lock is not None and self._wifi_lock.isHeld():
                            self._wifi_lock.release()
        except Exception as exc:
            logger.warning("Не удалось переключить WakeLock/WifiLock: %s", exc)

    def build(self):
        self.title = f"{APP_NAME} v{APP_VERSION}"
        self.transfer_history = []
        request_android_full_storage()
        settings = load_settings()
        self.theme_mode = settings.get("theme_mode", "dark")
        self.server_port = settings.get("port", SERVER_PORT)
        self.saved_password = settings.get("password", "")
        DynamicAirShareHandler.active_storage_path = STORAGE_PATH
        DynamicAirShareHandler.current_password = self.saved_password

        p = THEMES["dark"]
        self.root_widget = FloatLayout()
        self.main_content = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(14), dp(18), dp(16)],
            spacing=dp(12),
        )

        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(42), spacing=dp(8))
        name_box = BoxLayout(orientation="horizontal", size_hint=(0.56, 1), spacing=dp(8))
        self.status_dot = StatusDot(
            dot_color=p["red"], size_hint=(None, None), size=(dp(18), dp(18)), pos_hint={"center_y": 0.5}
        )
        dev_name = get_device_info()
        self.device_label = make_label(
            f"[b]{dev_name}[/b]",
            size=20 if len(dev_name) <= 14 else 16.5,
            markup=True,
            shorten=True,
            shorten_from="right",
        )
        name_box.add_widget(self.status_dot)
        name_box.add_widget(self.device_label)

        wifi_anchor = AnchorLayout(anchor_x="right", anchor_y="center", size_hint=(0.44, 1))
        self.wifi_pill = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(17),
            orientation="horizontal",
            size_hint=(None, None),
            size=(dp(148), dp(34)),
            padding=[dp(10), dp(4), dp(10), dp(4)],
            spacing=dp(6),
        )
        self.wifi_icon = VectorIcon(icon_type="wifi", color=p["text"], size_hint=(None, 1), width=dp(18))
        self.wifi_label = make_label(get_network_label(), size=11.5, halign="center", shorten=True)
        self.wifi_pill.add_widget(self.wifi_icon)
        self.wifi_pill.add_widget(self.wifi_label)
        self.wifi_pill.bind(on_press=self.refresh_network_status)
        wifi_anchor.add_widget(self.wifi_pill)
        header.add_widget(name_box)
        header.add_widget(wifi_anchor)
        self.main_content.add_widget(header)

        self.radar_card = RadarCard(
            bg_color=p["radar_bg"],
            border_color=p["card_border"],
            ring_color=p["radar_ring"],
            glow_color=p["radar_glow"],
            orientation="vertical",
            padding=[dp(16), dp(16), dp(16), dp(12)],
            spacing=dp(8),
            size_hint=(1, 0.55),
        )
        # Компактная иконка монитора с запасом места сверху и снизу, чтобы волнистые круги не задевали края и кнопку Connect
        icon_holder = AnchorLayout(size_hint=(1, 0.34))
        self.monitor_icon = VectorIcon(
            icon_type="pc", color=p["text"], size_hint=(None, None), size=(dp(56), dp(44))
        )
        icon_holder.add_widget(self.monitor_icon)
        self.radar_card.attach_target(self.monitor_icon)

        btn_anchor = AnchorLayout(size_hint=(1, 0.22))
        self.connect_btn = RoundedActionButton(
            text="Connect",
            bg_color=p["green"],
            border_color=(1, 1, 1, 0.18),
            font_size=sp(17),
            radius=dp(23),
            size_hint=(None, None),
            size=(dp(190), dp(45)),
        )
        self.connect_btn.bind(on_press=self.toggle_server)
        btn_anchor.add_widget(self.connect_btn)

        keep_alive_anchor = AnchorLayout(size_hint=(1, 0.18))
        self.keep_alive_row = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(16),
            orientation="horizontal",
            size_hint=(0.94, None),
            height=dp(38),
            padding=[dp(14), dp(5), dp(12), dp(5)],
            spacing=dp(10),
        )
        self.keep_alive_label = make_label("Активен при заблокированном экране", size=12)
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

        addr_row = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 0.18),
            spacing=dp(8),
            padding=[dp(4), dp(2), dp(4), dp(2)],
        )
        self.addr_pill = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(19),
            size_hint=(1, None),
            height=dp(38),
            pos_hint={"center_y": 0.5},
            padding=[dp(12), dp(4), dp(12), dp(4)],
        )
        self.addr_label = make_label("", size=12, halign="center", shorten=True, shorten_from="center")
        self.addr_pill.add_widget(self.addr_label)
        self.addr_pill.bind(on_press=self.copy_address)

        self.copy_btn = ClickableCard(
            bg_color=p["pill_bg"],
            border_color=p["card_border"],
            radius=dp(14),
            size_hint=(None, None),
            size=(dp(38), dp(38)),
            pos_hint={"center_y": 0.5},
        )
        self.copy_icon = VectorIcon(icon_type="copy", color=p["text"], size_hint=(1, 1))
        self.copy_btn.add_widget(self.copy_icon)
        self.copy_btn.bind(on_press=self.copy_address)
        addr_row.add_widget(self.addr_pill)
        addr_row.add_widget(self.copy_btn)

        # Короткое предупреждение о том, что HTTP не шифруется и предназначен для домашней сети
        self.http_warn_label = make_label(
            "HTTP без шифрования • используйте в домашней сети",
            size=10.5,
            halign="center",
            size_hint=(1, 0.08),
        )

        for w in (icon_holder, btn_anchor, keep_alive_anchor, addr_row, self.http_warn_label):
            self.radar_card.add_widget(w)
        self.main_content.add_widget(self.radar_card)

        self.transfers_header = make_label(
            "[b]Recent Transfers[/b]", size=16, markup=True, size_hint=(1, None), height=dp(24)
        )
        self.main_content.add_widget(self.transfers_header)

        self.transfers_card = ClickableCard(
            bg_color=p["card_bg"],
            border_color=p["card_border"],
            radius=dp(18),
            orientation="vertical",
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(10),
            size_hint=(1, 0.27),
        )
        self.transfers_card.bind(on_press=self.open_transfers_modal)

        row1 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5))
        ico1 = VectorIcon(
            icon_type="zip_badge", size_hint=(None, None), size=(dp(42), dp(42)), pos_hint={"center_y": 0.5}
        )
        info1 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top1 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20))
        self.tr1_name = make_label("Нет активных передач", size=14, size_hint=(0.76, 1))
        self.tr1_pct = make_label("—", size=13, halign="right", size_hint=(0.24, 1))
        top1.add_widget(self.tr1_name)
        top1.add_widget(self.tr1_pct)
        self.tr1_bar = SlimProgressBar(
            percent=0.0, track_color=p["track"], fill_color=p["amber"], size_hint=(1, None), height=dp(4.2)
        )
        self.tr1_sub = make_label("Ожидание подключения с ПК", size=11.5, size_hint=(1, None), height=dp(16))
        for w in (top1, self.tr1_bar, self.tr1_sub):
            info1.add_widget(w)
        row1.add_widget(ico1)
        row1.add_widget(info1)

        row2 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5))
        ico2 = VectorIcon(
            icon_type="img_badge", size_hint=(None, None), size=(dp(42), dp(42)), pos_hint={"center_y": 0.5}
        )
        info2 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top2 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20))
        self.tr2_name = make_label("История сессии", size=14, size_hint=(0.76, 1))
        self.tr2_pct = make_label("—", size=13, halign="right", size_hint=(0.24, 1))
        top2.add_widget(self.tr2_name)
        top2.add_widget(self.tr2_pct)
        self.tr2_bar = SlimProgressBar(
            percent=0.0, track_color=p["track"], fill_color=p["blue"], size_hint=(1, None), height=dp(4.2)
        )
        self.tr2_sub = make_label(
            "Переданные файлы появятся здесь", size=11.5, halign="left", size_hint=(1, None), height=dp(16)
        )
        for w in (top2, self.tr2_bar, self.tr2_sub):
            info2.add_widget(w)
        row2.add_widget(ico2)
        row2.add_widget(info2)

        self.transfers_card.add_widget(row1)
        self.transfers_card.add_widget(row2)
        self.main_content.add_widget(self.transfers_card)

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
        self.nav_transfer = NavTabItem(
            "transfer", "Transfer", is_active=True, pill_color=p["pill_active"], text_color=p["text"]
        )
        self.nav_transfer.bind(on_press=self._on_nav_transfer)
        self.nav_files = NavTabItem(
            "folder", "Files", is_active=False, pill_color=p["pill_active"], text_color=p["subtext"]
        )
        self.nav_files.bind(on_press=self._on_nav_files)
        self.nav_devices = NavTabItem(
            "phone", "Devices", is_active=False, pill_color=p["pill_active"], text_color=p["subtext"]
        )
        self.nav_devices.bind(on_press=self._on_nav_devices)
        self.nav_settings = NavTabItem(
            "gear", "Settings", is_active=False, pill_color=p["pill_active"], text_color=p["subtext"]
        )
        self.nav_settings.bind(on_press=self._on_nav_settings)
        for tab in (self.nav_transfer, self.nav_files, self.nav_devices, self.nav_settings):
            self.bottom_nav.add_widget(tab)
        self.main_content.add_widget(self.bottom_nav)
        self.root_widget.add_widget(self.main_content)

        self.overlay = DrawerOverlay(
            close_callback=self.close_drawer, size_hint=(1, 1), pos_hint={"x": 0, "y": 0}
        )
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

        self.drawer_title = make_label(
            f"[b]{APP_NAME}[/b]", size=23, markup=True, size_hint=(1, None), height=dp(32)
        )
        self.drawer.add_widget(self.drawer_title)

        phone_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(30), spacing=dp(10))
        self.drawer_phone_icon = VectorIcon(
            icon_type="phone", color=p["subtext"], size_hint=(None, 1), width=dp(22)
        )
        self.drawer_phone_label = make_label(dev_name, size=15, shorten=True, shorten_from="right")
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
        self.drawer_storage_label = make_label(
            stats["text"], size=13, markup=True, size_hint=(1, None), height=dp(20)
        )
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

        self.drawer_status_card = ClickableCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(15),
            orientation="horizontal",
            padding=[dp(14), dp(10), dp(14), dp(10)],
            spacing=dp(12),
            size_hint=(1, None),
            height=dp(66),
        )
        self.drawer_status_icon = VectorIcon(icon_type="pc", color=p["text"], size_hint=(None, 1), width=dp(32))
        self.drawer_status_label = make_label(
            "[b]Server Stopped[/b]\n[size=12sp]Tap to start[/size]", size=14.5, markup=True
        )
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

    def on_stop(self):
        # Корректно освобождаем WakeLock/WifiLock и останавливаем сервер при закрытии приложения
        self.radar_card.set_wave_active(False)
        self.set_keep_alive(False)
        if self.server is not None:
            srv, self.server = self.server, None
            try:
                srv.shutdown()
                srv.server_close()
            except Exception as exc:
                logger.debug("Ошибка при остановке сервера в on_stop: %s", exc)

    def set_active_nav(self, tab_name):
        self.active_nav_tab = tab_name
        p = THEMES.get(self._get_effective_theme(), THEMES["dark"])
        for name, widget in [
            ("transfer", self.nav_transfer),
            ("files", self.nav_files),
            ("devices", self.nav_devices),
            ("settings", self.nav_settings),
        ]:
            act = tab_name == name
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
        self.wifi_label.text = get_network_label()

    def open_drawer(self, *_args):
        self.drawer.is_open = self.overlay.is_open = True
        self.set_active_nav("settings")
        stats = get_storage_stats()
        self.drawer_storage_label.text = stats["text"]
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
        Animation(
            x=-self.drawer_width - dp(35), scale_val=0.96, opacity=0.0, duration=0.25, t="out_cubic"
        ).start(self.drawer)

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
        self.radar_card.set_wave_active(is_online)
        self.wifi_label.text = get_network_label()
        if is_online:
            self.connect_btn.set_text("Disconnect")
            self.connect_btn.update_colors(p["red"], (1, 1, 1, 0.22))
            self.drawer_status_label.text = (
                f"[b]Server Active[/b]\n[size={int(sp(12))}]Port {self.server_port} • {self.active_folder_key}[/size]"
            )
            self.drawer_status_icon.set_color(p["green"])
        else:
            self.connect_btn.set_text("Connect")
            self.connect_btn.update_colors(p["green"], (1, 1, 1, 0.22))
            self.drawer_status_label.text = (
                f"[b]Server Stopped[/b]\n[size={int(sp(12))}]Tap to start on port {self.server_port}[/size]"
            )
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
        self.http_warn_label.color = p["subtext"]
        self._update_status_indicators(p)

        self.transfers_header.color = self.tr1_name.color = self.tr2_name.color = p["text"]
        self.transfers_card.update_colors(p["card_bg"], p["card_border"])
        self.tr1_pct.color = self.tr1_sub.color = self.tr2_pct.color = self.tr2_sub.color = p["subtext"]
        self.tr1_bar.update_bar_colors(p["track"], p["amber"])
        self.tr2_bar.update_bar_colors(p["track"], p["blue"])

        self.bottom_nav.update_colors(p["card_bg"], p["card_border"])
        self.set_active_nav(self.active_nav_tab)

        self.drawer.update_colors(p["drawer_bg"], p["drawer_border"])
        self.drawer_title.color = self.drawer_phone_label.color = p["text"]
        self.drawer_storage_label.color = self.drawer_status_label.color = p["text"]
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
            act = self.theme_mode == mode_key
            btn.update_colors(
                p["pill_active"] if act else (0, 0, 0, 0),
                p["drawer_border"] if act else (0, 0, 0, 0),
            )
            btn.lbl.color = p["text"] if act else p["subtext"]

    def copy_address(self, *_args):
        url = self.get_connection_url()
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(url)
        except Exception as exc:
            logger.debug("Не удалось скопировать ссылку в буфер обмена: %s", exc)
        self.addr_label.text = "Copied to clipboard!"
        self.addr_label.font_size = sp(13)
        Clock.schedule_once(lambda _dt: self.update_connection_url_display(), 1.3)

    def _on_client_connected(self, device_title, os_badge, ip):
        Clock.schedule_once(
            lambda _dt: setattr(
                self.drawer_status_label,
                "text",
                f"[b]{device_title}[/b]\n[size={int(sp(12))}]{os_badge} • {ip}[/size]",
            ),
            0,
        )

    def _on_file_transfer(self, filename, size_str, direction):
        def _upd(_dt):
            if self.transfer_history:
                self.tr2_name.text = self.tr1_name.text
                self.tr2_pct.text = self.tr1_pct.text
                self.tr2_sub.text = self.tr1_sub.text
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
            except OSError as exc:
                logger.error("Не удалось запустить HTTP-сервер на порту %s: %s", self.server_port, exc)
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
                except Exception as exc:
                    logger.debug("Ошибка при остановке сервера: %s", exc)
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
        card = RoundedCard(
            bg_color=p["modal_bg"],
            border_color=p["drawer_border"],
            radius=dp(26),
            orientation="vertical",
            padding=[dp(20), dp(20), dp(20), dp(18)],
            spacing=dp(12),
            size_hint=(0.90, None),
            height=dp(height_dp),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        card.add_widget(
            make_label(
                f"[b]{title_text}[/b]", size=18, markup=True, color=p["text"], size_hint=(1, None), height=dp(26)
            )
        )
        if subtitle_text:
            card.add_widget(
                make_label(
                    subtitle_text, size=12.5, markup=True, color=p["subtext"], size_hint=(1, None), height=dp(20)
                )
            )

        modal = MacModalContainer(
            card_widget=card,
            origin_pos=origin,
            scrim_rgba=p["overlay"],
            on_dismiss_cb=lambda: (not self.drawer.is_open) and self.set_active_nav("transfer"),
        )
        self.active_modal = modal
        self.root_widget.add_widget(modal)
        modal.animate_open()
        return modal, card, p

    def open_shared_folders_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal(
            "Shared Folders", "Выберите папку для раздачи на ПК:", 395, source_widget
        )
        list_box = BoxLayout(orientation="vertical", spacing=dp(8), size_hint=(1, 1))
        for key_name, (path_val, icon_kind, desc_txt) in self._get_folder_map().items():
            is_cur = key_name == self.active_folder_key
            item_card = ClickableCard(
                bg_color=p["pill_active"] if is_cur else p["drawer_card"],
                border_color=p["amber"] if is_cur else p["drawer_border"],
                radius=dp(16),
                orientation="horizontal",
                size_hint=(1, None),
                height=dp(54),
                padding=[dp(12), dp(8), dp(12), dp(8)],
                spacing=dp(12),
            )
            ico = VectorIcon(
                icon_type=icon_kind,
                color=p["amber"] if is_cur else p["text"],
                size_hint=(None, None),
                size=(dp(30), dp(30)),
                pos_hint={"center_y": 0.5},
            )
            txt_lbl = make_label(
                f"[b]{key_name}[/b]\n[size={int(sp(11))}]{desc_txt}[/size]",
                size=13.5,
                markup=True,
                color=p["text"],
            )
            right_ico = VectorIcon(
                icon_type="check" if is_cur else "chevron",
                color=p["amber"] if is_cur else p["subtext"],
                size_hint=(None, None),
                size=(dp(22), dp(22)),
                pos_hint={"center_y": 0.5},
            )

            def _pick(_inst, k=key_name, pv=path_val):
                self.active_folder_key = k
                if not os.path.isdir(pv):
                    try:
                        os.makedirs(pv, exist_ok=True)
                    except OSError:
                        pv = STORAGE_PATH
                DynamicAirShareHandler.active_storage_path = pv
                self.apply_theme()
                modal.dismiss()

            item_card.bind(on_press=_pick)
            for w in (ico, txt_lbl, right_ico):
                item_card.add_widget(w)
            list_box.add_widget(item_card)
        card.add_widget(list_box)
        btn_ok = RoundedActionButton(
            "Закрыть",
            bg_color=p["pill_bg"],
            border_color=p["drawer_border"],
            text_color=p["text"],
            size_hint=(1, None),
            height=dp(44),
        )
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)

    def open_transfers_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal(
            "Recent Transfers", "История переданных файлов за сессию:", 285, source_widget
        )
        inner = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(16),
            padding=dp(14),
            size_hint=(1, 1),
        )
        if self.transfer_history:
            txt = "\n".join(f"• {x}" for x in self.transfer_history[:6])
        else:
            txt = "За текущую сессию файлы ещё не передавались."
        inner.add_widget(make_label(txt, size=13, valign="top", color=p["text"]))
        card.add_widget(inner)
        btn_ok = RoundedActionButton(
            "Закрыть",
            bg_color=p["pill_bg"],
            border_color=p["drawer_border"],
            text_color=p["text"],
            size_hint=(1, None),
            height=dp(44),
        )
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)

    def open_security_modal(self, source_widget=None, *_args):
        # PIN-код никогда не может быть пустым: кнопка «Новый PIN» генерирует случайный 6-значный код
        modal, card, p = self._create_mac_modal(
            "Security & PIN", "PIN обязателен и автоматически встраивается в ссылку:", 255, source_widget
        )
        inp_wrap = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(14),
            size_hint=(1, None),
            height=dp(46),
            padding=[dp(10), dp(4), dp(10), dp(4)],
        )
        inp = TextInput(
            text=load_settings().get("password", ""),
            hint_text="Введите PIN (минимум 4–6 символов)",
            multiline=False,
            font_size=sp(14.5),
            background_color=(0, 0, 0, 0),
            foreground_color=p["text"],
            cursor_color=p["blue"],
            padding=[dp(6), dp(8), dp(6), dp(8)],
        )
        inp_wrap.add_widget(inp)
        card.add_widget(inp_wrap)
        btn_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(44))
        btn_gen = RoundedActionButton(
            "Новый PIN", bg_color=p["pill_bg"], border_color=p["drawer_border"], text_color=p["text"]
        )
        btn_save = RoundedActionButton(
            "Сохранить PIN", bg_color=p["blue"], border_color=(1, 1, 1, 0.2), text_color=(1, 1, 1, 1)
        )

        def _save(val):
            saved = save_settings(password=val)
            final_pwd = saved["password"]
            self.saved_password = DynamicAirShareHandler.current_password = final_pwd
            DynamicAirShareHandler.reset_rate_limits()
            self.update_connection_url_display()
            modal.dismiss()

        btn_gen.bind(on_press=lambda *_: _save(generate_pin()))
        btn_save.bind(on_press=lambda *_: _save(inp.text.strip() or generate_pin()))
        btn_row.add_widget(btn_gen)
        btn_row.add_widget(btn_save)
        card.add_widget(btn_row)

    def open_port_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal(
            "Port Settings", "Укажите порт сервера (1024–65535):", 245, source_widget
        )
        inp_wrap = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(14),
            size_hint=(1, None),
            height=dp(46),
            padding=[dp(10), dp(4), dp(10), dp(4)],
        )
        inp = TextInput(
            text=str(self.server_port),
            hint_text="8080",
            input_filter="int",
            multiline=False,
            font_size=sp(15),
            background_color=(0, 0, 0, 0),
            foreground_color=p["text"],
            cursor_color=p["blue"],
            padding=[dp(6), dp(8), dp(6), dp(8)],
        )
        inp_wrap.add_widget(inp)
        card.add_widget(inp_wrap)
        btn_save = RoundedActionButton(
            "Сохранить порт", bg_color=p["blue"], border_color=(1, 1, 1, 0.2), size_hint=(1, None), height=dp(44)
        )

        def _save_port(_b):
            try:
                val = int(inp.text.strip())
                if 1024 <= val <= 65535:
                    self.server_port = val
                    save_settings(port=val)
                    self.update_connection_url_display()
            except ValueError:
                pass
            modal.dismiss()

        btn_save.bind(on_press=_save_port)
        card.add_widget(btn_save)

    def open_devices_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal(
            "Connected Devices", "История подключённых IP-адресов:", 295, source_widget
        )
        inner = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(16),
            padding=dp(14),
            size_hint=(1, 1),
        )
        ips = load_settings().get("recent_ips", [])
        lbl = make_label(
            "\n".join(f"• {x}" for x in ips[:6])
            if ips
            else "Пока нет сохранённых подключений.\nОткройте ссылку в браузере на ПК.",
            size=13,
            valign="top",
            color=p["text"],
        )
        inner.add_widget(lbl)
        card.add_widget(inner)
        btn_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(44))
        btn_clr = RoundedActionButton(
            "Очистить", bg_color=p["pill_bg"], border_color=p["drawer_border"], text_color=p["text"]
        )
        btn_ok = RoundedActionButton("Закрыть", bg_color=p["blue"], border_color=(1, 1, 1, 0.2))
        btn_clr.bind(on_press=lambda *_: (save_settings(recent_ips=[]), setattr(lbl, "text", "История очищена")))
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        btn_row.add_widget(btn_clr)
        btn_row.add_widget(btn_ok)
        card.add_widget(btn_row)

    def open_help_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal("Help & Feedback", f"{APP_NAME} v{APP_VERSION}", 275, source_widget)
        inner = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(16),
            padding=dp(14),
            size_hint=(1, 1),
        )
        inner.add_widget(
            make_label(
                "1. Нажмите зелёную кнопку «Connect» для запуска.\n"
                "2. Скопируйте ссылку и откройте её в браузере на ПК.\n"
                "3. Во вкладке «Files» выберите папку для раздачи.",
                size=13,
                color=p["text"],
            )
        )
        card.add_widget(inner)
        btn_ok = RoundedActionButton(
            "Понятно", bg_color=p["blue"], border_color=(1, 1, 1, 0.2), size_hint=(1, None), height=dp(44)
        )
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)


if __name__ == "__main__":
    AirShareApp().run()

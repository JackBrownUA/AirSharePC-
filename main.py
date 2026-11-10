# Главный модуль приложения AirShare PC: многоязычный интерфейс, контроль Wi-Fi, выбор папки и управление сервером

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
from i18n import SUPPORTED_LANGUAGES, tr
from server import AirShareHandler, ReusableThreadingServer
from themes import THEMES
from ui_widgets import (
    AnimatedToggleSwitch,
    AppSplashScreen,
    ClickableCard,
    DrawerMenuRow,
    DrawerOverlay,
    DrawerPanel,
    FlagBadge,
    MacModalContainer,
    NavTabItem,
    RadarCard,
    RadioCircle,
    RoundedActionButton,
    RoundedCard,
    SlimProgressBar,
    StatusDot,
    ToastBanner,
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
    is_wifi_connected,
    load_settings,
    request_android_full_storage,
    request_ignore_battery_optimizations,
    save_settings,
)

logger = logging.getLogger("airshare.app")


class DynamicAirShareHandler(AirShareHandler):
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
        self.server = None
        self.is_stopping = False
        self.has_server_error = False
        # По умолчанию раздаём безопасную папку Downloads (п. 28.b); весь накопитель включается с предупреждением
        self.active_folder_key = "Downloads"
        self.active_nav_tab = "transfer"
        self.keep_alive_locked = True
        self._wake_lock = None
        self._wifi_lock = None
        self._battery_opt_requested = False
        self.transfer_history = []
        self.active_modal = None
        self.theme_mode = "dark"
        self.language = "en"
        self.server_port = SERVER_PORT
        self.saved_password = ""

    def _t(self, key, **kwargs):
        return tr(key, self.language, **kwargs)

    def _get_folder_map(self):
        base = STORAGE_PATH if os.path.isdir(STORAGE_PATH) else os.path.expanduser("~")
        return {
            "Downloads": (os.path.join(base, "Download"), "download", self._t("folder_dl_title"), self._t("folder_dl_desc")),
            "Camera Roll": (os.path.join(base, "DCIM"), "gallery", self._t("folder_cam_title"), self._t("folder_cam_desc")),
            "Documents": (os.path.join(base, "Documents"), "document", self._t("folder_doc_title"), self._t("folder_doc_desc")),
            "All Storage": (base, "folder", self._t("folder_all_title"), self._t("folder_all_desc")),
        }

    def _resolve_folder_path(self, folder_key):
        fmap = self._get_folder_map()
        path_val = fmap.get(folder_key, fmap["Downloads"])[0]
        if not os.path.isdir(path_val):
            try:
                os.makedirs(path_val, exist_ok=True)
            except OSError:
                path_val = STORAGE_PATH
        return path_val

    def get_connection_url(self):
        # Полная ссылка с ?pin= для автоматического входа без Basic Auth при копировании
        if not is_wifi_connected():
            return self._t("no_wifi_url")
        ip = get_local_ip()
        pwd = (self.saved_password or "").strip()
        if not pwd:
            pwd = load_settings().get("password", "")
            self.saved_password = pwd
        quoted_pwd = urllib.parse.quote(pwd, safe="")
        return f"http://{ip}:{self.server_port}/?pin={quoted_pwd}"

    def get_display_url_text(self):
        # На экране показываем короткий адрес и PIN, чтобы его было легко ввести вручную в браузере
        if not is_wifi_connected():
            return self._t("no_wifi_url")
        ip = get_local_ip()
        pwd = (self.saved_password or "").strip() or load_settings().get("password", "")
        return f"http://{ip}:{self.server_port}  •  PIN: {pwd}"

    def update_connection_url_display(self):
        disp = self.get_display_url_text()
        self.addr_label.text = disp
        self.addr_label.font_size = sp(11.5) if len(disp) > 34 else sp(12.5)

    def set_keep_alive(self, enabled):
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
                                wifi_mode = getattr(WifiManager, "WIFI_MODE_FULL_LOW_LATENCY", WifiManager.WIFI_MODE_FULL_HIGH_PERF)
                                self._wifi_lock = wm.createWifiLock(wifi_mode, "AirSharePC::WifiLock")
                                self._wifi_lock.setReferenceCounted(False)
                        if self._wifi_lock is not None and not self._wifi_lock.isHeld():
                            self._wifi_lock.acquire()
                    else:
                        if self._wake_lock is not None and self._wake_lock.isHeld():
                            self._wake_lock.release()
                        if self._wifi_lock is not None and self._wifi_lock.isHeld():
                            self._wifi_lock.release()
        except Exception as exc:
            logger.warning("Не удалось переключить WakeLock/WifiLock: %s", exc)

    def _apply_android_system_insets(self, *_args):
        # На Android 15+ (targetSdkVersion 35) учитываем системные отступы статус-бара и нижней панели навигации
        try:
            from kivy.utils import platform
            if platform != "android":
                return
            from jnius import autoclass
            BuildVersion = autoclass("android.os.Build$VERSION")
            if BuildVersion.SDK_INT < 35:
                return
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = getattr(PythonActivity, "mActivity", None)
            if activity is None or activity.getApplicationInfo().targetSdkVersion < 35:
                return
            window = activity.getWindow()
            decor = window.getDecorView() if window is not None else None
            insets = decor.getRootWindowInsets() if decor is not None else None
            if insets is None:
                return
            WindowInsetsType = autoclass("android.view.WindowInsets$Type")
            bars = insets.getInsets(WindowInsetsType.systemBars())
            top_px = max(0, int(bars.top))
            bot_px = max(0, int(bars.bottom))
            if top_px > 0 or bot_px > 0:
                self.main_content.padding = [dp(18), dp(12) + top_px, dp(18), dp(12) + bot_px]
        except Exception as exc:
            logger.debug("Не удалось применить системные отступы Android 15+: %s", exc)

    def build(self):
        self.title = f"{APP_NAME} v{APP_VERSION}"
        self.transfer_history = []
        settings = load_settings()
        self.theme_mode = settings.get("theme_mode", "dark")
        self.language = settings.get("language", "en")
        self.server_port = settings.get("port", SERVER_PORT)
        self.saved_password = settings.get("password", "")
        DynamicAirShareHandler.active_storage_path = self._resolve_folder_path(self.active_folder_key)
        DynamicAirShareHandler.current_password = self.saved_password
        DynamicAirShareHandler.current_language = self.language

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
            size=(dp(136), dp(34)),
            padding=[dp(10), dp(4), dp(10), dp(4)],
            spacing=dp(6),
        )
        self.wifi_icon = VectorIcon(icon_type="wifi", color=p["text"], size_hint=(None, 1), width=dp(18))
        self.wifi_label = make_label(get_network_label(self.language), size=12, halign="center", shorten=True)
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
        icon_holder = AnchorLayout(size_hint=(1, 0.34))
        self.monitor_icon = VectorIcon(
            icon_type="pc", color=p["text"], size_hint=(None, None), size=(dp(56), dp(44))
        )
        icon_holder.add_widget(self.monitor_icon)
        self.radar_card.attach_target(self.monitor_icon)

        btn_anchor = AnchorLayout(size_hint=(1, 0.22))
        self.connect_btn = RoundedActionButton(
            text=self._t("connect"),
            bg_color=p["green"],
            border_color=(1, 1, 1, 0.18),
            font_size=sp(16.5),
            radius=dp(23),
            size_hint=(None, None),
            size=(dp(196), dp(45)),
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
        self.keep_alive_label = make_label(self._t("keep_alive"), size=12)
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

        self.http_warn_label = make_label(
            self._t("http_warn"),
            size=10.5,
            halign="center",
            size_hint=(1, 0.08),
        )

        for w in (icon_holder, btn_anchor, keep_alive_anchor, addr_row, self.http_warn_label):
            self.radar_card.add_widget(w)
        self.main_content.add_widget(self.radar_card)

        self.transfers_header = make_label(
            f"[b]{self._t('recent_transfers')}[/b]", size=16, markup=True, size_hint=(1, None), height=dp(24)
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

        self.tr_row1 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5))
        ico1 = VectorIcon(
            icon_type="zip_badge", size_hint=(None, None), size=(dp(42), dp(42)), pos_hint={"center_y": 0.5}
        )
        info1 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top1 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(24))
        self.tr1_name = make_label(
            self._t("no_active_transfers"),
            size=13.5,
            size_hint=(0.76, 1),
            shorten=True,
            shorten_from="center",
            max_lines=1,
        )
        self.tr1_pct = make_label("—", size=13, halign="right", size_hint=(0.24, 1))
        top1.add_widget(self.tr1_name)
        top1.add_widget(self.tr1_pct)
        self.tr1_bar = SlimProgressBar(
            percent=0.0, track_color=p["track"], fill_color=p["amber"], size_hint=(1, None), height=dp(4.2)
        )
        self.tr1_sub = make_label(self._t("waiting_pc"), size=11.5, size_hint=(1, None), height=dp(16))
        for w in (top1, self.tr1_bar, self.tr1_sub):
            info1.add_widget(w)
        self.tr_row1.add_widget(ico1)
        self.tr_row1.add_widget(info1)

        # Вторая строка передач скрыта, пока в сессии меньше 2 переданных файлов (п. 19)
        self.tr_row2 = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, 0.5), opacity=0.0)
        ico2 = VectorIcon(
            icon_type="img_badge", size_hint=(None, None), size=(dp(42), dp(42)), pos_hint={"center_y": 0.5}
        )
        info2 = BoxLayout(orientation="vertical", spacing=dp(3), pos_hint={"center_y": 0.5})
        top2 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(24))
        self.tr2_name = make_label(
            "",
            size=13.5,
            size_hint=(0.76, 1),
            shorten=True,
            shorten_from="center",
            max_lines=1,
        )
        self.tr2_pct = make_label("", size=13, halign="right", size_hint=(0.24, 1))
        top2.add_widget(self.tr2_name)
        top2.add_widget(self.tr2_pct)
        self.tr2_bar = SlimProgressBar(
            percent=0.0, track_color=p["track"], fill_color=p["blue"], size_hint=(1, None), height=dp(4.2)
        )
        self.tr2_sub = make_label("", size=11.5, halign="left", size_hint=(1, None), height=dp(16))
        for w in (top2, self.tr2_bar, self.tr2_sub):
            info2.add_widget(w)
        self.tr_row2.add_widget(ico2)
        self.tr_row2.add_widget(info2)

        self.transfers_card.add_widget(self.tr_row1)
        self.transfers_card.add_widget(self.tr_row2)
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
            "transfer", self._t("nav_transfer"), is_active=True, pill_color=p["pill_active"], text_color=p["text"]
        )
        self.nav_transfer.bind(on_press=self._on_nav_transfer)
        self.nav_files = NavTabItem(
            "folder", self._t("nav_files"), is_active=False, pill_color=p["pill_active"], text_color=p["subtext"]
        )
        self.nav_files.bind(on_press=self._on_nav_files)
        self.nav_devices = NavTabItem(
            "phone", self._t("nav_devices"), is_active=False, pill_color=p["pill_active"], text_color=p["subtext"]
        )
        self.nav_devices.bind(on_press=self._on_nav_devices)
        self.nav_settings = NavTabItem(
            "gear", self._t("nav_settings"), is_active=False, pill_color=p["pill_active"], text_color=p["subtext"]
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

        stats = get_storage_stats(self.language)
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
        self.drawer_status_label = make_label("", size=14.0, markup=True)
        self.drawer_status_card.add_widget(self.drawer_status_icon)
        self.drawer_status_card.add_widget(self.drawer_status_label)
        self.drawer_status_card.bind(on_press=self.toggle_server)
        self.drawer.add_widget(self.drawer_status_card)

        # В боковой панели вместо дублирующего Shared Folders первой строкой стоит выбор языка (Language) с иконкой глобуса
        menu_box = BoxLayout(orientation="vertical", spacing=dp(4), size_hint=(1, 1))
        self.menu_items_refs = []
        for menu_key, ico_name, cb in [
            ("menu_language", "globe", self.open_language_modal),
            ("menu_security", "lock", self.open_security_modal),
            ("menu_port", "sliders", self.open_port_modal),
            ("menu_help", "info", self.open_help_modal),
        ]:
            row = DrawerMenuRow(ico_name, self._t(menu_key), p["text"], p["subtext"], p["pill_bg"])
            row.menu_key = menu_key
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
        self.t_btn_dark = RoundedActionButton(text=self._t("theme_dark"), radius=dp(16), font_size=sp(12.5))
        self.t_btn_dark.bind(on_press=lambda *_: self.set_theme_mode("dark"))
        self.t_btn_light = RoundedActionButton(text=self._t("theme_light"), radius=dp(16), font_size=sp(12.5))
        self.t_btn_light.bind(on_press=lambda *_: self.set_theme_mode("light"))
        self.t_btn_auto = RoundedActionButton(text=self._t("theme_auto"), radius=dp(16), font_size=sp(12.5))
        self.t_btn_auto.bind(on_press=lambda *_: self.set_theme_mode("system"))
        for b in (self.t_btn_dark, self.t_btn_light, self.t_btn_auto):
            self.theme_pill_container.add_widget(b)
        self.drawer.add_widget(self.theme_pill_container)
        self.root_widget.add_widget(self.drawer)

        self.toast_banner = ToastBanner()
        self.root_widget.add_widget(self.toast_banner)

        DynamicAirShareHandler.on_client_connected = self._on_client_connected
        DynamicAirShareHandler.on_file_transfer = self._on_file_transfer
        DynamicAirShareHandler.on_bad_pin_attempt = self._on_bad_pin_attempt
        self.update_connection_url_display()
        self.apply_theme()

        self.splash_screen = AppSplashScreen(lang=self.language, version=APP_VERSION)
        self.root_widget.add_widget(self.splash_screen)
        Clock.schedule_once(self._apply_android_system_insets, 0.35)

        return self.root_widget

    def show_toast(self, message, kind="info"):
        p = THEMES.get(self._get_effective_theme(), THEMES["dark"])
        dot_c = p["red"] if kind == "error" else (p["amber"] if kind == "warn" else p["green"])
        self.toast_banner.show_message(message, dot_color=dot_c, text_color=p["text"], bg_color=p["modal_bg"])

    def set_language(self, lang_code):
        self.language = lang_code
        save_settings(language=lang_code)
        DynamicAirShareHandler.current_language = lang_code
        self.apply_language()
        self.apply_theme()

    def apply_language(self):
        self.wifi_label.text = get_network_label(self.language)
        self.keep_alive_label.text = self._t("keep_alive")
        self.http_warn_label.text = self._t("http_warn")
        self.transfers_header.text = f"[b]{self._t('recent_transfers')}[/b]"
        if not self.transfer_history:
            self.tr1_name.text = self._t("no_active_transfers")
            self.tr1_sub.text = self._t("waiting_pc")
            self.tr_row2.opacity = 0.0

        self.nav_transfer.label.text = self._t("nav_transfer")
        self.nav_files.label.text = self._t("nav_files")
        self.nav_devices.label.text = self._t("nav_devices")
        self.nav_settings.label.text = self._t("nav_settings")

        stats = get_storage_stats(self.language)
        self.drawer_storage_label.text = stats["text"]

        for row in self.menu_items_refs:
            row.lbl_w.text = self._t(row.menu_key)

        self.t_btn_dark.set_text(self._t("theme_dark"))
        self.t_btn_light.set_text(self._t("theme_light"))
        self.t_btn_auto.set_text(self._t("theme_auto"))
        self.update_connection_url_display()

    def on_pause(self):
        # Возвращаем True, чтобы Android/Kivy не замораживал фоновый HTTP-сервер при сворачивании приложения
        if self.server is not None and self.keep_alive_locked:
            self.set_keep_alive(True)
        return True

    def on_resume(self):
        if self.server is not None and self.keep_alive_locked:
            self.set_keep_alive(True)
        self.refresh_network_status()

    def on_stop(self):
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
        self.wifi_label.text = get_network_label(self.language)
        p = THEMES.get(self._get_effective_theme(), THEMES["dark"])
        self._update_status_indicators(p)

    def open_drawer(self, *_args):
        self.drawer.is_open = self.overlay.is_open = True
        self.set_active_nav("settings")
        stats = get_storage_stats(self.language)
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
        wifi_ok = is_wifi_connected()
        is_online = self.server is not None
        has_issue = self.has_server_error or (is_online and not wifi_ok)
        self.status_dot.set_status_color(p["yellow"] if has_issue else (p["green"] if is_online else p["red"]))
        self.radar_card.set_wave_active(is_online and wifi_ok)
        self.wifi_label.text = get_network_label(self.language)
        self.wifi_icon.set_color(p["green"] if wifi_ok else p["subtext"])

        fmap = self._get_folder_map()
        cur_folder_title = fmap.get(self.active_folder_key, fmap["Downloads"])[2]

        if is_online:
            self.connect_btn.set_text(self._t("disconnect"))
            self.connect_btn.update_colors(p["red"], (1, 1, 1, 0.22))
            sub = self._t("port_folder_fmt", port=self.server_port, folder=cur_folder_title)
            self.drawer_status_label.text = f"[b]{self._t('server_active')}[/b]\n[size={int(sp(11.5))}]{sub}[/size]"
            self.drawer_status_icon.set_color(p["green"])
        else:
            self.connect_btn.set_text(self._t("connect"))
            self.connect_btn.update_colors(p["green"], (1, 1, 1, 0.22))
            sub = self._t("tap_to_start_port", port=self.server_port)
            self.drawer_status_label.text = f"[b]{self._t('server_stopped')}[/b]\n[size={int(sp(11.5))}]{sub}[/size]"
            self.drawer_status_icon.set_color(p["subtext"])

    def apply_theme(self):
        eff = self._get_effective_theme()
        p = THEMES.get(eff, THEMES["dark"])
        DynamicAirShareHandler.default_theme = eff
        Window.clearcolor = p["bg"]
        self.device_label.color = self.wifi_label.color = p["text"]
        self.wifi_pill.update_colors(p["pill_bg"], p["card_border"])
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
        if not is_wifi_connected():
            self.open_no_wifi_modal(self.addr_pill)
            return
        url = self.get_connection_url()
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(url)
        except Exception as exc:
            logger.debug("Не удалось скопировать ссылку в буфер обмена: %s", exc)
        self.addr_label.text = self._t("copied_clipboard")
        self.addr_label.font_size = sp(12.5)
        Clock.schedule_once(lambda _dt: self.update_connection_url_display(), 1.3)

    def _on_client_connected(self, device_title, os_badge, ip, is_first=False):
        def _upd(_dt):
            self.drawer_status_label.text = f"[b]{device_title}[/b]\n[size={int(sp(11.5))}]{os_badge} • {ip}[/size]"
            if is_first:
                self.show_toast(self._t("toast_connected", dev=device_title, ip=ip), kind="info")

        Clock.schedule_once(_upd, 0)

    def _on_bad_pin_attempt(self, ip):
        Clock.schedule_once(lambda _dt: self.show_toast(self._t("toast_bad_pin", ip=ip), kind="error"), 0)

    def _on_file_transfer(self, filename, size_str, direction):
        def _upd(_dt):
            if self.transfer_history:
                self.tr2_name.text = self.tr1_name.text
                self.tr2_pct.text = self.tr1_pct.text
                self.tr2_sub.text = self.tr1_sub.text
                self.tr2_bar.set_percent(1.0)
                self.tr_row2.opacity = 1.0
            self.tr1_name.text, self.tr1_pct.text = filename, "100%"
            act = self._t("uploaded") if direction == "upload" else self._t("downloaded")
            self.tr1_sub.text = f"{act} • {size_str}"
            self.tr1_bar.set_percent(1.0)
            self.transfer_history.insert(0, f"{filename} ({act} • {size_str})")

        Clock.schedule_once(_upd, 0)

    def toggle_server(self, *_args):
        if self.is_stopping:
            return
        if self.server is None:
            # Проверяем подключение к Wi-Fi перед запуском сервера (п. 13)
            if not is_wifi_connected():
                self.open_no_wifi_modal(self.connect_btn)
                self.update_connection_url_display()
                self.apply_theme()
                return

            settings = load_settings()
            self.saved_password = settings.get("password", "")
            self.server_port = settings.get("port", SERVER_PORT)
            DynamicAirShareHandler.current_password = self.saved_password
            DynamicAirShareHandler.default_theme = self._get_effective_theme()
            DynamicAirShareHandler.current_language = self.language
            DynamicAirShareHandler._notified_ips.clear()
            self.update_connection_url_display()

            bind_ip = get_local_ip()
            try:
                # Привязываем сокет именно к локальному Wi-Fi IP, а не к 0.0.0.0 (п. 13)
                self.server = ReusableThreadingServer((bind_ip, self.server_port), DynamicAirShareHandler)
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
                self.has_server_error = False
                self.set_keep_alive(True)
                if self.keep_alive_locked and not self._battery_opt_requested:
                    self._battery_opt_requested = True
                    request_ignore_battery_optimizations()
            except OSError as exc:
                logger.error("Не удалось запустить HTTP-сервер на %s:%s: %s", bind_ip, self.server_port, exc)
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
            spacing=dp(10),
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

    def open_no_wifi_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal(self._t("no_wifi_title"), "", 235, source_widget)
        inner = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(16),
            padding=dp(14),
            size_hint=(1, 1),
        )
        inner.add_widget(make_label(self._t("no_wifi_body"), size=13, color=p["text"]))
        card.add_widget(inner)
        btn_ok = RoundedActionButton(
            self._t("ok_understand"),
            bg_color=p["blue"],
            border_color=(1, 1, 1, 0.2),
            size_hint=(1, None),
            height=dp(44),
        )
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)

    def open_language_modal(self, source_widget=None, *_args):
        # Модальное окно выбора из 6 языков с увеличенной высотой (490dp) и фиксированным контейнером списка
        modal, card, p = self._create_mac_modal(
            self._t("lang_title"), self._t("lang_subtitle"), 490, source_widget
        )
        list_holder = AnchorLayout(anchor_x="center", anchor_y="center", size_hint=(1, 1))
        list_box = BoxLayout(orientation="vertical", spacing=dp(6), size_hint=(1, None), height=dp(282))
        list_holder.add_widget(list_box)
        radio_map = {}

        for code, native_name in SUPPORTED_LANGUAGES:
            is_sel = code == self.language
            row_card = ClickableCard(
                bg_color=p["pill_active"] if is_sel else p["drawer_card"],
                border_color=p["green"] if is_sel else p["drawer_border"],
                radius=dp(14),
                orientation="horizontal",
                size_hint=(1, None),
                height=dp(42),
                padding=[dp(12), dp(5), dp(14), dp(5)],
                spacing=dp(12),
            )
            flag_w = FlagBadge(lang_code=code, size_hint=(None, None), size=(dp(30), dp(22)), pos_hint={"center_y": 0.5})
            name_lbl = make_label(f"[b]{native_name}[/b]", size=14.5, markup=True, color=p["text"])
            radio_w = RadioCircle(selected=is_sel, size_hint=(None, None), size=(dp(26), dp(26)), pos_hint={"center_y": 0.5})
            radio_map[code] = (row_card, radio_w)

            def _select_lang(_inst, c=code):
                for other_c, (r_card, r_circle) in radio_map.items():
                    sel = other_c == c
                    r_circle.set_selected(sel, animate=True)
                    r_card.update_colors(
                        p["pill_active"] if sel else p["drawer_card"],
                        p["green"] if sel else p["drawer_border"],
                    )
                self.set_language(c)
                Clock.schedule_once(lambda _dt: modal.dismiss(), 0.24)

            row_card.bind(on_press=_select_lang)
            for w in (flag_w, name_lbl, radio_w):
                row_card.add_widget(w)
            list_box.add_widget(row_card)

        card.add_widget(list_holder)
        btn_close = RoundedActionButton(
            self._t("close"),
            bg_color=p["pill_bg"],
            border_color=p["drawer_border"],
            text_color=p["text"],
            size_hint=(1, None),
            height=dp(42),
        )
        btn_close.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_close)

    def _apply_folder_selection(self, key_name, path_val):
        self.active_folder_key = key_name
        if not os.path.isdir(path_val):
            try:
                os.makedirs(path_val, exist_ok=True)
            except OSError:
                path_val = STORAGE_PATH
        DynamicAirShareHandler.active_storage_path = path_val
        self.apply_theme()

    def open_all_storage_confirm_modal(self, path_val, source_widget=None):
        # Объёмное окно предупреждения в тон приложения: красная кнопка «Отмена» и зелёная «Разрешить» без жёлтой рамки
        modal, card, p = self._create_mac_modal(
            self._t("all_storage_warn_title"), "", 260, source_widget
        )
        inner = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(16),
            padding=dp(14),
            size_hint=(1, 1),
        )
        inner.add_widget(make_label(self._t("all_storage_warn_body"), size=13, color=p["text"]))
        card.add_widget(inner)

        btn_row = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint=(1, None), height=dp(46))
        btn_cancel = RoundedActionButton(
            self._t("cancel"),
            bg_color=p["red"],
            border_color=(1, 0.65, 0.65, 0.38),
            text_color=(1, 1, 1, 1),
            radius=dp(16),
        )
        btn_confirm = RoundedActionButton(
            self._t("confirm_allow"),
            bg_color=p["green"],
            border_color=(0.65, 1, 0.80, 0.38),
            text_color=(1, 1, 1, 1),
            radius=dp(16),
        )

        def _confirm(*_):
            request_android_full_storage()
            self._apply_folder_selection("All Storage", path_val)
            modal.dismiss()

        btn_cancel.bind(on_press=lambda *_: modal.dismiss())
        btn_confirm.bind(on_press=_confirm)
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_confirm)
        card.add_widget(btn_row)

    def open_shared_folders_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal(
            self._t("folders_title"), self._t("folders_subtitle"), 435, source_widget
        )
        list_box = BoxLayout(orientation="vertical", spacing=dp(8), size_hint=(1, 1))
        for key_name, (path_val, icon_kind, title_txt, desc_txt) in self._get_folder_map().items():
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
                f"[b]{title_txt}[/b]\n[size={int(sp(11))}]{desc_txt}[/size]",
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

            def _pick(inst, k=key_name, pv=path_val):
                if k == "All Storage" and self.active_folder_key != "All Storage":
                    modal.dismiss()
                    Clock.schedule_once(lambda _dt: self.open_all_storage_confirm_modal(pv, inst), 0.20)
                else:
                    self._apply_folder_selection(k, pv)
                    modal.dismiss()

            item_card.bind(on_press=_pick)
            for w in (ico, txt_lbl, right_ico):
                item_card.add_widget(w)
            list_box.add_widget(item_card)
        card.add_widget(list_box)
        btn_ok = RoundedActionButton(
            self._t("close"),
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
            self._t("recent_transfers"), "", 275, source_widget
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
            txt = self._t("no_transfers_yet")
        inner.add_widget(make_label(txt, size=13, valign="top", color=p["text"]))
        card.add_widget(inner)
        btn_ok = RoundedActionButton(
            self._t("close"),
            bg_color=p["pill_bg"],
            border_color=p["drawer_border"],
            text_color=p["text"],
            size_hint=(1, None),
            height=dp(44),
        )
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)

    def open_security_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal(
            self._t("pin_title"), self._t("pin_subtitle"), 255, source_widget
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
            hint_text=self._t("pin_hint"),
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
            self._t("pin_new"), bg_color=p["pill_bg"], border_color=p["drawer_border"], text_color=p["text"]
        )
        btn_save = RoundedActionButton(
            self._t("pin_save"), bg_color=p["blue"], border_color=(1, 1, 1, 0.2), text_color=(1, 1, 1, 1)
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
            self._t("port_title"), self._t("port_subtitle"), 245, source_widget
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
            self._t("port_save"), bg_color=p["blue"], border_color=(1, 1, 1, 0.2), size_hint=(1, None), height=dp(44)
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
        # Список подключённых устройств с кнопкой «Отключить» / «Разрешить» напротив каждого IP (п. 3)
        modal, card, p = self._create_mac_modal(
            self._t("devices_title"), self._t("devices_subtitle"), 345, source_widget
        )
        list_box = BoxLayout(orientation="vertical", spacing=dp(8), size_hint=(1, 1))

        def _populate():
            list_box.clear_widgets()
            cur_ips = load_settings().get("recent_ips", [])
            if not cur_ips:
                empty_card = RoundedCard(
                    bg_color=p["drawer_card"],
                    border_color=p["drawer_border"],
                    radius=dp(16),
                    padding=dp(14),
                    size_hint=(1, 1),
                )
                empty_card.add_widget(make_label(self._t("no_devices_yet"), size=13, valign="top", color=p["text"]))
                list_box.add_widget(empty_card)
                return

            for entry in cur_ips[:4]:
                raw_ip = entry.split("•")[-1].strip() if "•" in entry else entry.strip()
                is_blocked = DynamicAirShareHandler.is_ip_disconnected(raw_ip)

                dev_row = RoundedCard(
                    bg_color=p["drawer_card"],
                    border_color=p["drawer_border"],
                    radius=dp(14),
                    orientation="horizontal",
                    size_hint=(1, None),
                    height=dp(48),
                    padding=[dp(12), dp(6), dp(8), dp(6)],
                    spacing=dp(8),
                )
                dev_lbl = make_label(entry, size=12, color=p["subtext"] if is_blocked else p["text"], shorten=True)
                act_btn = RoundedActionButton(
                    text=self._t("btn_allow_dev") if is_blocked else self._t("btn_disconnect_dev"),
                    bg_color=p["green"] if is_blocked else p["red"],
                    border_color=(1, 1, 1, 0.18),
                    font_size=sp(11.5),
                    radius=dp(11),
                    size_hint=(None, None),
                    size=(dp(94), dp(32)),
                    pos_hint={"center_y": 0.5},
                )

                def _toggle_ip(_b, ip_val=raw_ip, currently_blocked=is_blocked):
                    DynamicAirShareHandler.set_ip_disconnected(ip_val, not currently_blocked)
                    toast_key = "toast_dev_allowed" if currently_blocked else "toast_dev_blocked"
                    self.show_toast(self._t(toast_key, ip=ip_val), kind="info" if currently_blocked else "warn")
                    _populate()

                act_btn.bind(on_press=_toggle_ip)
                dev_row.add_widget(dev_lbl)
                dev_row.add_widget(act_btn)
                list_box.add_widget(dev_row)

        _populate()
        card.add_widget(list_box)

        btn_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(44))
        btn_clr = RoundedActionButton(
            self._t("clear_history"), bg_color=p["pill_bg"], border_color=p["drawer_border"], text_color=p["text"]
        )
        btn_ok = RoundedActionButton(self._t("close"), bg_color=p["blue"], border_color=(1, 1, 1, 0.2))

        def _clear(*_):
            save_settings(recent_ips=[])
            _populate()

        btn_clr.bind(on_press=_clear)
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        btn_row.add_widget(btn_clr)
        btn_row.add_widget(btn_ok)
        card.add_widget(btn_row)

    def open_help_modal(self, source_widget=None, *_args):
        modal, card, p = self._create_mac_modal(
            self._t("help_title"), f"{APP_NAME} v{APP_VERSION}", 460, source_widget
        )
        inner = RoundedCard(
            bg_color=p["drawer_card"],
            border_color=p["drawer_border"],
            radius=dp(16),
            padding=[dp(16), dp(14), dp(16), dp(14)],
            size_hint=(1, 1),
        )
        inner.add_widget(make_label(self._t("help_body"), size=12.5, valign="top", color=p["text"]))
        card.add_widget(inner)
        credit_lbl = make_label(
            "Crafted by JackBrownUA • Powered by Gemini",
            size=11,
            halign="center",
            color=p["subtext"],
            size_hint=(1, None),
            height=dp(18),
        )
        card.add_widget(credit_lbl)
        btn_ok = RoundedActionButton(
            self._t("ok_understand"),
            bg_color=p["blue"],
            border_color=(1, 1, 1, 0.2),
            size_hint=(1, None),
            height=dp(44),
        )
        btn_ok.bind(on_press=lambda *_: modal.dismiss())
        card.add_widget(btn_ok)


if __name__ == "__main__":
    AirShareApp().run()

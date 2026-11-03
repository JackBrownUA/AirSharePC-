"""
Main application file - Kivy UI for AirShare PC
"""

import threading
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

from config import SERVER_PORT, APP_NAME, APP_VERSION
from server import ReusableThreadingServer, AirShareHandler
from utils import (
    get_local_ip,
    request_android_full_storage,
    load_settings,
    save_settings,
    add_recent_ip,
    get_device_theme,
)


THEMES = {
    "dark": {
        "bg": (0.07, 0.08, 0.12, 1),
        "text": (0.95, 0.96, 0.98, 1),
        "subtext": (0.68, 0.72, 0.80, 1),
        "input_bg": (0.14, 0.16, 0.22, 1),
        "input_fg": (0.96, 0.97, 1.0, 1),
        "btn_primary": (0.25, 0.52, 0.96, 1),
        "btn_danger": (0.90, 0.24, 0.24, 1),
        "btn_secondary": (0.22, 0.25, 0.34, 1),
    },
    "light": {
        "bg": (0.95, 0.96, 0.97, 1),
        "text": (0.11, 0.11, 0.13, 1),
        "subtext": (0.40, 0.42, 0.46, 1),
        "input_bg": (1.0, 1.0, 1.0, 1),
        "input_fg": (0.11, 0.11, 0.13, 1),
        "btn_primary": (0.0, 0.48, 1.0, 1),
        "btn_danger": (0.88, 0.20, 0.20, 1),
        "btn_secondary": (0.78, 0.80, 0.84, 1),
    },
}


class AirShareApp(App):
    server = None
    is_stopping = False

    def build(self):
        self.title = f"{APP_NAME} v{APP_VERSION}"
        request_android_full_storage()

        settings = load_settings()
        self.theme_mode = settings.get("theme_mode", "system")
        self.recent_ips = settings.get("recent_ips", [])
        saved_password = settings.get("password", "")

        layout = BoxLayout(orientation="vertical", padding=24, spacing=14)

        # Верхняя панель: заголовок и переключатель темы (Системная / Темная / Светлая)
        top_bar = BoxLayout(orientation="horizontal", size_hint=(1, 0.10), spacing=10)
        self.title_label = Label(
            text=f"[b]{APP_NAME}[/b] v{APP_VERSION}",
            markup=True,
            font_size="19sp",
            halign="left",
            valign="middle",
            size_hint=(0.55, 1),
        )
        self.title_label.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        self.theme_btn = Button(
            text=self._get_theme_btn_label(),
            size_hint=(0.45, 1),
            font_size="14sp",
            background_normal="",
        )
        self.theme_btn.bind(on_press=self.cycle_theme_mode)
        top_bar.add_widget(self.title_label)
        top_bar.add_widget(self.theme_btn)

        # Статус сервера и адрес подключения
        self.status_label = Label(
            text=f"{APP_NAME}\nСервер остановлен",
            font_size="18sp",
            halign="center",
            valign="middle",
            size_hint=(1, 0.24),
        )
        self.status_label.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        # Поле установки собственного пароля + кнопка сохранения
        pwd_row = BoxLayout(orientation="horizontal", size_hint=(1, 0.12), spacing=10)
        self.pin_input = TextInput(
            text=saved_password,
            hint_text="Установите свой пароль (пусто — без пароля)",
            multiline=False,
            size_hint=(0.68, 1),
            font_size="16sp",
            padding=[12, 12, 12, 12],
        )
        self.pin_input.bind(text=self.on_password_changed)

        self.save_pwd_btn = Button(
            text="Сохранить пароль",
            size_hint=(0.32, 1),
            font_size="14sp",
            background_normal="",
        )
        self.save_pwd_btn.bind(on_press=self.save_custom_password)
        pwd_row.add_widget(self.pin_input)
        pwd_row.add_widget(self.save_pwd_btn)

        # Блок истории последних IP-адресов
        ip_header_row = BoxLayout(orientation="horizontal", size_hint=(1, 0.08), spacing=10)
        self.ip_title_label = Label(
            text="Последние IP-адреса:",
            font_size="15sp",
            halign="left",
            valign="middle",
            size_hint=(0.72, 1),
        )
        self.ip_title_label.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        self.clear_ips_btn = Button(
            text="Очистить",
            size_hint=(0.28, 1),
            font_size="13sp",
            background_normal="",
        )
        self.clear_ips_btn.bind(on_press=self.clear_recent_ips)
        ip_header_row.add_widget(self.ip_title_label)
        ip_header_row.add_widget(self.clear_ips_btn)

        self.ip_history_label = Label(
            text=self._format_recent_ips(),
            font_size="14sp",
            halign="left",
            valign="top",
            size_hint=(1, 0.24),
        )
        self.ip_history_label.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        # Кнопка запуска / остановки сервера
        self.toggle_btn = Button(
            text="ЗАПУСТИТЬ СЕРВЕР",
            size_hint=(1, 0.18),
            font_size="18sp",
            bold=True,
            background_normal="",
        )
        self.toggle_btn.bind(on_press=self.toggle_server)

        layout.add_widget(top_bar)
        layout.add_widget(self.status_label)
        layout.add_widget(pwd_row)
        layout.add_widget(ip_header_row)
        layout.add_widget(self.ip_history_label)
        layout.add_widget(self.toggle_btn)

        AirShareHandler.on_client_ip = self._on_client_connected_ip
        self.apply_current_theme()
        return layout

    def on_resume(self):
        """Re-apply system theme when returning to the app on Android"""
        if self.theme_mode == "system":
            self.apply_current_theme()
        return True

    def _get_effective_theme(self):
        if self.theme_mode == "system":
            return get_device_theme()
        return self.theme_mode

    def _get_theme_btn_label(self):
        eff = self._get_effective_theme()
        eff_ru = "Тёмная" if eff == "dark" else "Светлая"
        if self.theme_mode == "system":
            return f"Тема: Авто ({eff_ru})"
        return f"Тема: {eff_ru}"

    def cycle_theme_mode(self, _instance):
        order = ["system", "dark", "light"]
        idx = order.index(self.theme_mode) if self.theme_mode in order else 0
        self.theme_mode = order[(idx + 1) % len(order)]
        save_settings(theme_mode=self.theme_mode)
        self.apply_current_theme()

    def apply_current_theme(self):
        eff = self._get_effective_theme()
        palette = THEMES.get(eff, THEMES["dark"])
        AirShareHandler.default_theme = eff

        Window.clearcolor = palette["bg"]
        self.title_label.color = palette["text"]
        self.status_label.color = palette["text"]
        self.ip_title_label.color = palette["subtext"]
        self.ip_history_label.color = palette["text"]

        self.pin_input.background_color = palette["input_bg"]
        self.pin_input.foreground_color = palette["input_fg"]
        self.pin_input.cursor_color = palette["btn_primary"]

        self.theme_btn.text = self._get_theme_btn_label()
        self.theme_btn.background_color = palette["btn_secondary"]
        self.theme_btn.color = palette["text"]

        self.save_pwd_btn.background_color = palette["btn_primary"]
        self.save_pwd_btn.color = (1, 1, 1, 1)

        self.clear_ips_btn.background_color = palette["btn_secondary"]
        self.clear_ips_btn.color = palette["text"]

        if self.server is None:
            self.toggle_btn.background_color = palette["btn_primary"]
        else:
            self.toggle_btn.background_color = palette["btn_danger"]
        self.toggle_btn.color = (1, 1, 1, 1)

    def _format_recent_ips(self):
        if not self.recent_ips:
            return "Пока нет сохранённых IP-адресов"
        return "\n".join(f"• {item}" for item in self.recent_ips[:6])

    def _on_client_connected_ip(self, client_ip):
        def _update(_dt):
            self.recent_ips = load_settings().get("recent_ips", [])
            self.ip_history_label.text = self._format_recent_ips()
        Clock.schedule_once(_update, 0)

    def clear_recent_ips(self, _instance):
        self.recent_ips = []
        save_settings(recent_ips=[])
        self.ip_history_label.text = self._format_recent_ips()

    def on_password_changed(self, _instance, value):
        pwd = value.strip()
        if self.server is not None:
            AirShareHandler.current_password = pwd

    def save_custom_password(self, _instance):
        password = self.pin_input.text.strip()
        save_settings(password=password)
        AirShareHandler.current_password = password
        if self.server is not None:
            ip = get_local_ip()
            self.status_label.text = (
                f"Сервер запущен!\n"
                f"Откройте в браузере: http://{ip}:{SERVER_PORT}\n"
                f"Пароль сохранён: {password or 'Без пароля'}"
            )
        else:
            self.status_label.text = f"Пароль сохранён: {password or 'Без пароля'}\nСервер остановлен"

    def toggle_server(self, _instance):
        if self.is_stopping:
            return

        if self.server is None:
            password = self.pin_input.text.strip()
            save_settings(password=password)
            AirShareHandler.current_password = password
            AirShareHandler.default_theme = self._get_effective_theme()

            ip = get_local_ip()
            server_url = f"http://{ip}:{SERVER_PORT}"
            self.recent_ips = add_recent_ip(server_url)
            self.ip_history_label.text = self._format_recent_ips()

            try:
                self.server = ReusableThreadingServer(("", SERVER_PORT), AirShareHandler)
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
            except OSError as e:
                self.server = None
                self.status_label.text = f"Ошибка запуска сервера:\n{e}"
                return

            self.status_label.text = (
                f"Сервер запущен!\n"
                f"Откройте в браузере: {server_url}\n"
                f"Пароль: {password or 'Без пароля'}"
            )
            self.toggle_btn.text = "ОСТАНОВИТЬ СЕРВЕР"
            self.apply_current_theme()
        else:
            self.is_stopping = True
            self.toggle_btn.text = "ОСТАНОВКА..."
            srv = self.server
            self.server = None

            def _stop_in_bg():
                try:
                    srv.shutdown()
                    srv.server_close()
                except Exception:
                    pass
                Clock.schedule_once(self._on_server_stopped, 0)

            threading.Thread(target=_stop_in_bg, daemon=True).start()

    def _on_server_stopped(self, _dt):
        self.is_stopping = False
        self.status_label.text = f"{APP_NAME}\nСервер остановлен"
        self.toggle_btn.text = "ЗАПУСТИТЬ СЕРВЕР"
        self.apply_current_theme()


if __name__ == "__main__":
    AirShareApp().run()

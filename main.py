"""
Main application file - Kivy UI for AirShare PC
"""

import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from config import SERVER_PORT, DEFAULT_PASSWORD, APP_NAME, APP_VERSION
from server import ReusableThreadingServer, AirShareHandler
from utils import get_local_ip, request_android_full_storage

class AirShareApp(App):
    server = None

    def build(self):
        self.title = f"{APP_NAME} v{APP_VERSION}"
        request_android_full_storage()
        
        layout = BoxLayout(orientation="vertical", padding=30, spacing=20)

        self.status_label = Label(
            text=f"{APP_NAME}\nServer stopped",
            font_size="20sp",
            halign="center"
        )
        
        self.pin_input = TextInput(
            text=DEFAULT_PASSWORD,
            hint_text="Password (PIN)",
            multiline=False,
            size_hint=(1, 0.18),
            font_size="18sp"
        )
        
        self.toggle_btn = Button(
            text="START SERVER",
            size_hint=(1, 0.28),
            background_color=(0.2, 0.6, 1, 1),
            font_size="18sp"
        )
        self.toggle_btn.bind(on_press=self.toggle_server)

        layout.add_widget(self.status_label)
        layout.add_widget(self.pin_input)
        layout.add_widget(self.toggle_btn)
        return layout

    def toggle_server(self, instance):
        if self.server is None:
            password = self.pin_input.text.strip()
            AirShareHandler.current_password = password
            
            ip = get_local_ip()
            self.server = ReusableThreadingServer(("", SERVER_PORT), AirShareHandler)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            
            self.status_label.text = (
                f"Server running!\n\n"
                f"Open in browser:\nhttp://{ip}:{SERVER_PORT}\n\n"
                f"Password: {password or 'No password'}"
            )
            self.toggle_btn.text = "STOP SERVER"
            self.toggle_btn.background_color = (0.9, 0.2, 0.2, 1)
        else:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.status_label.text = f"{APP_NAME}\nServer stopped"
            self.toggle_btn.text = "START SERVER"
            self.toggle_btn.background_color = (0.2, 0.6, 1, 1)

if __name__ == "__main__":
    AirShareApp().run()

# Модуль интеграции с Android / Pyjnius для AirShare PC (v1.3.5): Wi-Fi IP, имя устройства, системная тема, права памяти и фоновый режим

import logging
import socket
import struct

from config import APP_NAME
from i18n import tr

logger = logging.getLogger("airshare.android")

WIFI_IFACE_PREFIXES = ("wlan", "swlan", "ap", "softap", "wifi", "p2p", "eth", "rndis", "en", "wl")
NOTIFICATION_ID = 1001
NOTIFICATION_CHANNEL_ID = "airshare_fg_service"


def get_android_wifi_ip(is_private_lan_ip_fn):
    try:
        from jnius import autoclass
        NetworkInterface = autoclass("java.net.NetworkInterface")
        interfaces = NetworkInterface.getNetworkInterfaces()
        if interfaces is not None:
            while interfaces.hasMoreElements():
                nif = interfaces.nextElement()
                if nif is None or not nif.isUp() or nif.isLoopback():
                    continue
                name = str(nif.getName() or "").lower()
                if not name.startswith(WIFI_IFACE_PREFIXES):
                    continue
                addrs = nif.getInetAddresses()
                while addrs.hasMoreElements():
                    addr = addrs.nextElement()
                    if addr is None or addr.isLoopbackAddress():
                        continue
                    host = str(addr.getHostAddress() or "").split("%")[0].strip()
                    if is_private_lan_ip_fn(host):
                        return host
    except Exception as exc:
        logger.debug("Не удалось проверить NetworkInterface на Android: %s", exc)

    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        activity = getattr(PythonActivity, "mActivity", None)
        if activity is not None:
            wm = activity.getApplicationContext().getSystemService(Context.WIFI_SERVICE)
            if wm is not None and wm.isWifiEnabled():
                info = wm.getConnectionInfo()
                if info is not None:
                    ip_int = info.getIpAddress()
                    if ip_int:
                        ip_str = socket.inet_ntoa(struct.pack("<I", ip_int & 0xFFFFFFFF))
                        if is_private_lan_ip_fn(ip_str):
                            return ip_str
    except Exception as exc:
        logger.debug("Не удалось получить IP через WifiManager: %s", exc)

    return None


def get_android_device_name() -> str:
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        SettingsGlobal = autoclass("android.provider.Settings$Global")
        activity = PythonActivity.mActivity
        if activity is not None:
            resolver = activity.getContentResolver()
            dev_name = SettingsGlobal.getString(resolver, "device_name")
            if dev_name and str(dev_name).strip():
                return str(dev_name).strip()
    except Exception as exc:
        logger.debug("Не удалось получить Settings.Global.device_name: %s", exc)

    try:
        from jnius import autoclass
        Build = autoclass("android.os.Build")
        model = str(Build.MODEL or "").strip()
        known_models = {
            "SM-S928B": "Galaxy S24 Ultra",
            "SM-S928U": "Galaxy S24 Ultra",
            "SM-S928N": "Galaxy S24 Ultra",
            "SM-S926B": "Galaxy S24+",
            "SM-S921B": "Galaxy S24",
            "SM-S918B": "Galaxy S23 Ultra",
        }
        if model in known_models:
            return known_models[model]
        manufacturer = str(Build.MANUFACTURER or "").capitalize()
        if model.startswith(manufacturer):
            return model
        full_name = f"{manufacturer} {model}".strip()
        if full_name:
            return full_name
    except Exception as exc:
        logger.debug("Не удалось прочитать android.os.Build: %s", exc)
    return "Android Device"


def get_android_system_theme() -> str:
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Configuration = autoclass("android.content.res.Configuration")
        activity = PythonActivity.mActivity
        if activity is not None:
            ui_mode = activity.getResources().getConfiguration().uiMode
            night_mask = ui_mode & Configuration.UI_MODE_NIGHT_MASK
            if night_mask == Configuration.UI_MODE_NIGHT_NO:
                return "light"
            if night_mask == Configuration.UI_MODE_NIGHT_YES:
                return "dark"
    except Exception as exc:
        logger.debug("Не удалось определить системную тему Android: %s", exc)
    return "dark"


def has_android_storage_permission() -> bool:
    try:
        from kivy.utils import platform
    except Exception:
        return True
    if platform != "android":
        return True
    try:
        from jnius import autoclass
        BuildVersion = autoclass("android.os.Build$VERSION")
        if BuildVersion.SDK_INT >= 30:
            Environment = autoclass("android.os.Environment")
            return bool(Environment.isExternalStorageManager())
    except Exception as exc:
        logger.debug("Ошибка проверки Environment.isExternalStorageManager(): %s", exc)
    return True


def request_android_full_storage():
    try:
        from kivy.utils import platform
    except Exception:
        return
    if platform != "android":
        return
    try:
        from jnius import autoclass
        BuildVersion = autoclass("android.os.Build$VERSION")
        if BuildVersion.SDK_INT >= 30:
            Environment = autoclass("android.os.Environment")
            if not Environment.isExternalStorageManager():
                Intent = autoclass("android.content.Intent")
                Settings = autoclass("android.provider.Settings")
                Uri = autoclass("android.net.Uri")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = PythonActivity.mActivity
                intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                uri = Uri.parse(f"package:{activity.getPackageName()}")
                intent.setData(uri)
                activity.startActivity(intent)
        else:
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
    except Exception as exc:
        logger.warning("Не удалось запросить доступ к хранилищу Android: %s", exc)


def set_android_foreground_notification(active=True, url_text="", lang="en"):
    try:
        from kivy.utils import platform
    except Exception:
        return
    if platform != "android":
        return
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        activity = getattr(PythonActivity, "mActivity", None)
        if activity is None:
            return
        nm = activity.getSystemService(Context.NOTIFICATION_SERVICE)
        if nm is None:
            return
        if not active:
            nm.cancel(NOTIFICATION_ID)
            return

        BuildVersion = autoclass("android.os.Build$VERSION")
        if BuildVersion.SDK_INT >= 26:
            NotificationChannel = autoclass("android.app.NotificationChannel")
            NotificationManager = autoclass("android.app.NotificationManager")
            channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                APP_NAME,
                NotificationManager.IMPORTANCE_LOW,
            )
            nm.createNotificationChannel(channel)
            NotificationBuilder = autoclass("android.app.Notification$Builder")
            builder = NotificationBuilder(activity, NOTIFICATION_CHANNEL_ID)
        else:
            NotificationBuilder = autoclass("android.app.Notification$Builder")
            builder = NotificationBuilder(activity)

        app_info = activity.getApplicationInfo()
        icon_id = app_info.icon if app_info is not None and app_info.icon else 17301659
        title_str = f"{APP_NAME} — {tr('server_active', lang)}"
        body_str = url_text or tr("wifi_online", lang)

        Intent = autoclass("android.content.Intent")
        PendingIntent = autoclass("android.app.PendingIntent")
        intent = Intent(activity, activity.getClass())
        intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP)
        pi_flags = PendingIntent.FLAG_UPDATE_CURRENT
        if BuildVersion.SDK_INT >= 23:
            pi_flags |= PendingIntent.FLAG_IMMUTABLE
        pending_intent = PendingIntent.getActivity(activity, 0, intent, pi_flags)

        builder.setContentTitle(title_str)
        builder.setContentText(body_str)
        builder.setSmallIcon(icon_id)
        builder.setOngoing(True)
        builder.setContentIntent(pending_intent)
        notif = builder.build()
        nm.notify(NOTIFICATION_ID, notif)
    except Exception as exc:
        logger.debug("Не удалось обновить фоновое уведомление Android: %s", exc)


def is_android_activity_paused() -> bool:
    try:
        from kivy.utils import platform
        if platform != "android":
            return False
        from jnius import autoclass
        SDLActivity = autoclass("org.libsdl.app.SDLActivity")
        return bool(getattr(SDLActivity, "sIsActivityPaused", False))
    except Exception:
        return False

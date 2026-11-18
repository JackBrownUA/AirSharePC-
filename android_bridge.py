# Модуль интеграции с Android / Pyjnius для AirShare PC (v1.3.5): Wi-Fi IP, имя устройства, системная тема, права памяти, фоновый Foreground Service и уведомление со счётчиками передач

import logging
import socket
import struct

from config import APP_NAME
from i18n import tr

logger = logging.getLogger("airshare.android")

PRIMARY_WIFI_PREFIXES = ("wlan", "swlan", "wifi", "eth", "en", "wl")
SECONDARY_WIFI_PREFIXES = ("ap", "softap", "rndis", "p2p")
WIFI_IFACE_PREFIXES = PRIMARY_WIFI_PREFIXES + SECONDARY_WIFI_PREFIXES
NOTIFICATION_ID = 1001
NOTIFICATION_CHANNEL_ID = "airshare_fg_service"
_fg_service_running = False


def get_android_wifi_ip(is_private_lan_ip_fn):
    try:
        from jnius import autoclass
        NetworkInterface = autoclass("java.net.NetworkInterface")
        interfaces = NetworkInterface.getNetworkInterfaces()
        fallback_ip = None
        if interfaces is not None:
            while interfaces.hasMoreElements():
                nif = interfaces.nextElement()
                if nif is None or not nif.isUp() or nif.isLoopback():
                    continue
                name = str(nif.getName() or "").lower()
                if not name.startswith(WIFI_IFACE_PREFIXES):
                    continue
                is_primary = name.startswith(PRIMARY_WIFI_PREFIXES)
                addrs = nif.getInetAddresses()
                while addrs.hasMoreElements():
                    addr = addrs.nextElement()
                    if addr is None or addr.isLoopbackAddress():
                        continue
                    host = str(addr.getHostAddress() or "").split("%")[0].strip()
                    if is_private_lan_ip_fn(host):
                        if is_primary:
                            return host
                        if fallback_ip is None:
                            fallback_ip = host
        if fallback_ip:
            return fallback_ip
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


def request_android_notification_permission():
    try:
        from kivy.utils import platform
    except Exception:
        return
    if platform != "android":
        return
    try:
        from jnius import autoclass
        BuildVersion = autoclass("android.os.Build$VERSION")
        if BuildVersion.SDK_INT >= 33:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = getattr(PythonActivity, "mActivity", None)
            if activity is not None:
                perm = "android.permission.POST_NOTIFICATIONS"
                try:
                    if activity.checkSelfPermission(perm) != 0:
                        activity.requestPermissions([perm], 1002)
                        return
                except Exception:
                    pass
            try:
                from android.permissions import request_permissions
                request_permissions(["android.permission.POST_NOTIFICATIONS"])
            except Exception:
                pass
    except Exception as exc:
        logger.debug("Не удалось запросить разрешение POST_NOTIFICATIONS: %s", exc)


def move_android_task_to_back() -> bool:
    try:
        from kivy.utils import platform
        if platform != "android":
            return False
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = getattr(PythonActivity, "mActivity", None)
        if activity is not None:
            return bool(activity.moveTaskToBack(True))
    except Exception as exc:
        logger.debug("Не удалось свернуть Activity в фон: %s", exc)
    return False


def set_android_foreground_notification(
    active=True,
    url_text="",
    lang="en",
    sent_count=0,
    received_count=0,
):
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

        title_str = f"{APP_NAME} — {tr('server_active', lang)}"
        stats_str = tr("notif_stats_fmt", lang, sent=int(sent_count), received=int(received_count))
        clean_url = (url_text or "").strip()
        body_str = f"{stats_str}\n{clean_url}" if clean_url else stats_str

        # 1. Запускаем нативный Foreground Service только при старте сервера, а при обновлениях счётчиков обновляем через nm.notify
        global _fg_service_running
        try:
            Intent = autoclass("android.content.Intent")
            ServiceClass = autoclass("org.kivy.android.AirShareKeepAliveService")
            srv_intent = Intent(activity, ServiceClass)
            if not active:
                _fg_service_running = False
                srv_intent.setAction("STOP")
                activity.startService(srv_intent)
            elif not _fg_service_running:
                srv_intent.putExtra("title", title_str)
                srv_intent.putExtra("body", body_str)
                BuildVersion = autoclass("android.os.Build$VERSION")
                if BuildVersion.SDK_INT >= 26:
                    activity.startForegroundService(srv_intent)
                else:
                    activity.startService(srv_intent)
                _fg_service_running = True
        except Exception as svc_exc:
            logger.debug("AirShareKeepAliveService fallback: %s", svc_exc)

        # 2. Напрямую обновляем уведомление в шторке через NotificationManager
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
                f"{APP_NAME} — {tr('keep_alive', lang)}",
                NotificationManager.IMPORTANCE_LOW,
            )
            channel.setShowBadge(False)
            nm.createNotificationChannel(channel)
            NotificationBuilder = autoclass("android.app.Notification$Builder")
            builder = NotificationBuilder(activity, NOTIFICATION_CHANNEL_ID)
        else:
            NotificationBuilder = autoclass("android.app.Notification$Builder")
            builder = NotificationBuilder(activity)

        app_info = activity.getApplicationInfo()
        icon_id = app_info.icon if app_info is not None and app_info.icon else 17301659

        Intent = autoclass("android.content.Intent")
        PendingIntent = autoclass("android.app.PendingIntent")
        intent = Intent(activity, activity.getClass())
        intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP)
        pi_flags = PendingIntent.FLAG_UPDATE_CURRENT
        if BuildVersion.SDK_INT >= 23:
            pi_flags |= PendingIntent.FLAG_IMMUTABLE
        pending_intent = PendingIntent.getActivity(activity, 0, intent, pi_flags)

        builder.setContentTitle(title_str)
        builder.setContentText(stats_str)
        try:
            BigTextStyle = autoclass("android.app.Notification$BigTextStyle")
            builder.setStyle(BigTextStyle().bigText(body_str))
        except Exception:
            pass
        builder.setSmallIcon(icon_id)
        builder.setOngoing(True)
        builder.setOnlyAlertOnce(True)
        builder.setContentIntent(pending_intent)
        notif = builder.build()
        nm.notify(NOTIFICATION_ID, notif)
    except Exception as exc:
        logger.debug("Не удалось обновить фоновое уведомление Android: %s", exc)


_sdl_activity_cls = None
_is_android_platform = None


def is_android_activity_paused() -> bool:
    global _sdl_activity_cls, _is_android_platform
    try:
        if _is_android_platform is None:
            from kivy.utils import platform
            _is_android_platform = (platform == "android")
        if not _is_android_platform:
            return False
        if _sdl_activity_cls is None:
            from jnius import autoclass
            _sdl_activity_cls = autoclass("org.libsdl.app.SDLActivity")
        return bool(getattr(_sdl_activity_cls, "sIsActivityPaused", False))
    except Exception:
        return False

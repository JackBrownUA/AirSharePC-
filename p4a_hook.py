# Хук сборки python-for-android (p4a.hook) для AirShare PC (v1.3.5):
# 1. Выставляет TARGET_API = "36" (targetSdkVersion=36, compileSdkVersion=36 и target=android-36) для Android 16/17.
# 2. Генерирует нативный Java Foreground Service (AirShareKeepAliveService.java) в основном процессе приложения и регистрирует его в AndroidManifest.xml (защита от Cached App Freezer).
# 3. Патчит SDLActivity.java (отключает блокировку Python GIL внутри SDLActivity.nativePause() при сворачивании приложения, чтобы фоновый HTTP/HTTPS-сервер работал без остановок).
# 4. Патчит HIDDeviceManager.java (SDL2) флагом RECEIVER_EXPORTED (2) для Android 14–17.
# 5. Восстанавливает стандартный сертификат CN=Android Debug, O=Android, C=US и отключает pip install -U pip в p4a.

import os
import re
import shutil
import subprocess
from pathlib import Path

TARGET_API = "36"
FALLBACK_COMPILE_API = "35"

KEEP_ALIVE_SERVICE_JAVA = """package org.kivy.android;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

public class AirShareKeepAliveService extends Service {
    private static final String CHANNEL_ID = "airshare_fg_service";
    private static final int NOTIF_ID = 1001;
    private PowerManager.WakeLock wakeLock;
    private WifiManager.WifiLock wifiLock;

    @Override
    public void onCreate() {
        super.onCreate();
        acquireLocks();
    }

    private void acquireLocks() {
        try {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            if (pm != null && (wakeLock == null || !wakeLock.isHeld())) {
                wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AirSharePC::ServiceWakeLock");
                wakeLock.setReferenceCounted(false);
                wakeLock.acquire();
            }
            WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wm != null && (wifiLock == null || !wifiLock.isHeld())) {
                int mode = (Build.VERSION.SDK_INT >= 29) ? 4 : WifiManager.WIFI_MODE_FULL_HIGH_PERF;
                wifiLock = wm.createWifiLock(mode, "AirSharePC::ServiceWifiLock");
                wifiLock.setReferenceCounted(false);
                wifiLock.acquire();
            }
        } catch (Throwable ignored) {}
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && "STOP".equals(intent.getAction())) {
            try {
                stopForeground(true);
            } catch (Throwable ignored) {}
            stopSelf();
            return START_NOT_STICKY;
        }
        acquireLocks();
        String title = (intent != null && intent.getStringExtra("title") != null)
                ? intent.getStringExtra("title") : "AirShare PC — Server Active";
        String body = (intent != null && intent.getStringExtra("body") != null)
                ? intent.getStringExtra("body") : "Wi-Fi Server Running";
        try {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (Build.VERSION.SDK_INT >= 26 && nm != null) {
                NotificationChannel ch = new NotificationChannel(
                        CHANNEL_ID, "AirShare PC", NotificationManager.IMPORTANCE_LOW);
                nm.createNotificationChannel(ch);
            }
            Notification.Builder builder = (Build.VERSION.SDK_INT >= 26)
                    ? new Notification.Builder(this, CHANNEL_ID)
                    : new Notification.Builder(this);
            int iconId = getApplicationInfo().icon;
            if (iconId == 0) iconId = android.R.drawable.stat_sys_upload_done;
            Intent openIntent = new Intent(this, PythonActivity.class);
            openIntent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            int piFlags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= 23) piFlags |= PendingIntent.FLAG_IMMUTABLE;
            PendingIntent pi = PendingIntent.getActivity(this, 0, openIntent, piFlags);
            builder.setContentTitle(title)
                   .setContentText(body)
                   .setSmallIcon(iconId)
                   .setOngoing(true)
                   .setContentIntent(pi);
            Notification notif = builder.build();
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
            } else {
                startForeground(NOTIF_ID, notif);
            }
        } catch (Throwable ignored) {}
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        try {
            if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
            if (wifiLock != null && wifiLock.isHeld()) wifiLock.release();
        } catch (Throwable ignored) {}
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
"""


def _ensure_sdk_platform() -> str:
    sdk_candidates = []
    for env_var in ("ANDROIDSDK", "ANDROID_HOME", "ANDROID_SDK_ROOT"):
        val = os.environ.get(env_var)
        if val:
            sdk_candidates.append(Path(val))
    sdk_candidates.append(Path.home() / ".buildozer" / "android" / "platform" / "android-sdk")
    sdk_candidates.append(Path.cwd() / ".buildozer" / "android" / "platform" / "android-sdk")

    sdk_root = None
    for cand in sdk_candidates:
        if (cand / "platforms").is_dir():
            sdk_root = cand
            break

    if sdk_root is None:
        return TARGET_API

    target_plat = sdk_root / "platforms" / f"android-{TARGET_API}"
    if target_plat.is_dir():
        return TARGET_API

    sdkmanager_bins = list(sdk_root.glob("cmdline-tools/*/bin/sdkmanager")) + list(
        sdk_root.glob("tools/bin/sdkmanager")
    )
    if sdkmanager_bins:
        try:
            subprocess.run(
                [str(sdkmanager_bins[0]), f"platforms;android-{TARGET_API}"],
                input=b"y\ny\ny\n",
                timeout=120,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    if target_plat.is_dir():
        return TARGET_API
    if (sdk_root / "platforms" / f"android-{FALLBACK_COMPILE_API}").is_dir():
        return FALLBACK_COMPILE_API
    return TARGET_API


def _patch_project_properties(path_obj: Path, compile_api: str = TARGET_API) -> bool:
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = re.sub(r"target=android-\d+", f"target=android-{compile_api}", old_text)
    if f"target=android-{compile_api}" not in new_text:
        new_text = f"target=android-{compile_api}\n" + new_text
    if new_text != old_text:
        path_obj.write_text(new_text, encoding="utf-8")
        return True
    return False


def _patch_gradle_file(path_obj: Path, compile_api: str = TARGET_API) -> bool:
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = re.sub(r"compileSdkVersion\s+\d+", f"compileSdkVersion {compile_api}", old_text)
    new_text = re.sub(r"targetSdkVersion\s+\d+", f"targetSdkVersion {TARGET_API}", new_text)
    if new_text != old_text:
        path_obj.write_text(new_text, encoding="utf-8")
        return True
    return False


def _patch_manifest_file(path_obj: Path) -> bool:
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = re.sub(
        r'android:targetSdkVersion="[^"]*"',
        f'android:targetSdkVersion="{TARGET_API}"',
        old_text,
    )
    new_text = new_text.replace('android:requestLegacyExternalStorage="true"', "")
    new_text = re.sub(
        r"<uses-permission[^>]*REQUEST_IGNORE_BATTERY_OPTIMIZATIONS[^>]*/>\s*",
        "",
        new_text,
    )
    # Добавляем разрешения FOREGROUND_SERVICE и сам сервис AirShareKeepAliveService в манифест, если это скомпилированный AndroidManifest.xml
    if "<application" in new_text and "{%" not in new_text:
        fg_perms = (
            '<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />\n'
            '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />\n    '
        )
        if "android.permission.FOREGROUND_SERVICE_DATA_SYNC" not in new_text:
            new_text = new_text.replace("<application", fg_perms + "<application", 1)
        svc_tag = (
            '<service android:name="org.kivy.android.AirShareKeepAliveService" '
            'android:exported="false" android:foregroundServiceType="dataSync" />\n    '
        )
        if "org.kivy.android.AirShareKeepAliveService" not in new_text:
            new_text = new_text.replace("</application>", "    " + svc_tag + "</application>", 1)

    if new_text != old_text:
        path_obj.write_text(new_text, encoding="utf-8")
        return True
    return False


def _patch_hid_device_manager(path_obj: Path) -> bool:
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = old_text
    usb_old = "mContext.registerReceiver(mUsbBroadcast, filter);"
    usb_new = (
        "if (android.os.Build.VERSION.SDK_INT >= 33) { "
        "mContext.registerReceiver(mUsbBroadcast, filter, 2); "
        "} else { mContext.registerReceiver(mUsbBroadcast, filter); }"
    )
    if "mContext.registerReceiver(mUsbBroadcast, filter, 2)" not in new_text and usb_old in new_text:
        new_text = new_text.replace(usb_old, usb_new)

    bt_old = "mContext.registerReceiver(mBluetoothBroadcast, filter);"
    bt_new = (
        "if (android.os.Build.VERSION.SDK_INT >= 33) { "
        "mContext.registerReceiver(mBluetoothBroadcast, filter, 2); "
        "} else { mContext.registerReceiver(mBluetoothBroadcast, filter); }"
    )
    if "mContext.registerReceiver(mBluetoothBroadcast, filter, 2)" not in new_text and bt_old in new_text:
        new_text = new_text.replace(bt_old, bt_new)

    if new_text != old_text:
        path_obj.write_text(new_text, encoding="utf-8")
        return True
    return False


def _patch_sdl_activity_keep_alive(path_obj: Path) -> bool:
    # В SDLActivity.java вызов SDLActivity.nativePause() блокирует C-семафор Android_PauseSem, пока поток Kivy держит Python GIL!
    # Из-за этого при сворачивании приложения фоновые потоки HTTP-сервера замирают.
    # Отключаем вызов nativePause()/nativeResume() и выставляем флаг sIsActivityPaused для Python.
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = old_text
    if "sIsActivityPaused" not in new_text and "class SDLActivity" in new_text:
        new_text = new_text.replace(
            "public static boolean mIsPaused",
            "public static volatile boolean sIsActivityPaused = false;\n    public static boolean mIsPaused",
            1,
        )
    if "SDLActivity.nativePause();" in new_text:
        new_text = new_text.replace(
            "SDLActivity.nativePause();",
            "sIsActivityPaused = true; /* AirShare: do not lock Python GIL in nativePause */",
        )
    if "SDLActivity.nativeResume();" in new_text:
        new_text = new_text.replace(
            "SDLActivity.nativeResume();",
            "sIsActivityPaused = false; /* AirShare: Python GIL stayed active */",
        )
    # Также обеспечиваем запись AirShareKeepAliveService.java рядом в org/kivy/android
    try:
        java_root = path_obj.parent.parent.parent.parent
        kivy_dir = java_root / "org" / "kivy" / "android"
        if kivy_dir.is_dir():
            svc_file = kivy_dir / "AirShareKeepAliveService.java"
            if not svc_file.exists() or svc_file.read_text(encoding="utf-8") != KEEP_ALIVE_SERVICE_JAVA:
                svc_file.write_text(KEEP_ALIVE_SERVICE_JAVA, encoding="utf-8")
    except Exception:
        pass

    if new_text != old_text:
        path_obj.write_text(new_text, encoding="utf-8")
        return True
    return False


def _patch_p4a_venv_pip_upgrade(path_obj: Path) -> bool:
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    if "pip install -U pip" not in old_text:
        return False
    new_text = old_text.replace("pip install -U pip", "true")
    if new_text != old_text:
        path_obj.write_text(new_text, encoding="utf-8")
        return True
    return False


def _restore_standard_debug_keystore():
    if not shutil.which("keytool"):
        return
    android_dir = Path.home() / ".android"
    ks_path = android_dir / "debug.keystore"
    old_marker = android_dir / ".airshare_ks_v2"
    std_marker = android_dir / ".airshare_std_debug_ks"
    if ks_path.exists() and std_marker.exists() and not old_marker.exists():
        return
    try:
        android_dir.mkdir(parents=True, exist_ok=True)
        if old_marker.exists():
            old_marker.unlink()
        if ks_path.exists():
            ks_path.unlink()
        subprocess.run(
            [
                "keytool",
                "-genkeypair",
                "-v",
                "-keystore",
                str(ks_path),
                "-storepass",
                "android",
                "-alias",
                "androiddebugkey",
                "-keypass",
                "android",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "10000",
                "-dname",
                "CN=Android Debug, O=Android, C=US",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        std_marker.write_text("ok\n", encoding="utf-8")
    except Exception:
        pass


def patch_build_tree(root_dir=None) -> dict:
    compile_api = _ensure_sdk_platform()
    counts = {"props": 0, "gradle": 0, "manifest": 0, "hid": 0, "sdl": 0, "p4a_pip": 0}
    search_roots = []
    if root_dir is not None:
        search_roots.append(Path(root_dir))
    cwd_buildozer = Path.cwd() / ".buildozer"
    if cwd_buildozer.exists():
        search_roots.append(cwd_buildozer)

    seen = set()
    for base in search_roots:
        if not base.exists():
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for fname in filenames:
                fpath = Path(dirpath) / fname
                real_key = str(fpath)
                if real_key in seen:
                    continue
                seen.add(real_key)
                if fname == "project.properties":
                    if _patch_project_properties(fpath, compile_api):
                        counts["props"] += 1
                elif fname in ("build.gradle", "build.tmpl.gradle"):
                    if _patch_gradle_file(fpath, compile_api):
                        counts["gradle"] += 1
                elif fname.startswith("AndroidManifest") and fname.endswith(".xml"):
                    if _patch_manifest_file(fpath):
                        counts["manifest"] += 1
                elif fname == "HIDDeviceManager.java":
                    if _patch_hid_device_manager(fpath):
                        counts["hid"] += 1
                elif fname == "SDLActivity.java":
                    if _patch_sdl_activity_keep_alive(fpath):
                        counts["sdl"] += 1
                elif fname == "build.py" and "pythonforandroid" in str(fpath):
                    if _patch_p4a_venv_pip_upgrade(fpath):
                        counts["p4a_pip"] += 1
    return counts


def _extract_dist_dir(toolchain):
    if toolchain is None:
        return None
    dist = getattr(toolchain, "_dist", None) or getattr(toolchain, "dist", None)
    if dist is not None:
        dist_dir = getattr(dist, "dist_dir", None)
        if dist_dir:
            return Path(dist_dir)
    ctx = getattr(toolchain, "ctx", None)
    if ctx is not None:
        dist = getattr(ctx, "dist", None)
        if dist is not None and getattr(dist, "dist_dir", None):
            return Path(dist.dist_dir)
    return None


def before_apk_build(toolchain=None, *_args, **_kwargs):
    _restore_standard_debug_keystore()
    dist_dir = _extract_dist_dir(toolchain)
    counts = patch_build_tree(dist_dir)
    print(f"[AirShare p4a_hook] before_apk_build (target API {TARGET_API}) patched: {counts}")


def after_apk_build(toolchain=None, *_args, **_kwargs):
    _restore_standard_debug_keystore()
    dist_dir = _extract_dist_dir(toolchain)
    counts = patch_build_tree(dist_dir)
    print(f"[AirShare p4a_hook] after_apk_build (target API {TARGET_API}) patched: {counts}")


def after_apk_assemble(toolchain=None, *_args, **_kwargs):
    dist_dir = _extract_dist_dir(toolchain)
    counts = patch_build_tree(dist_dir)
    print(f"[AirShare p4a_hook] after_apk_assemble (target API {TARGET_API}) patched: {counts}")


_restore_standard_debug_keystore()
patch_build_tree()

# Хук сборки python-for-android (p4a.hook) для AirShare PC (v1.3.5):
# 1. Выставляет TARGET_API = "35" (targetSdkVersion=35, compileSdkVersion=35 и target=android-35).
# 2. Генерирует нативный Java Foreground Service (AirShareKeepAliveService.java) с WakeLock, WifiLock, MulticastLock и живым уведомлением в шторке (передано/получено файлов) и регистрирует его в AndroidManifest.xml и AndroidManifest.tmpl.xml.
# 3. Патчит SDLActivity.java (отключает блокировку Python GIL внутри SDLActivity.nativePause() при выходе из приложения и блокировке экрана, чтобы фоновый HTTP-сервер работал без остановок).
# 4. Патчит HIDDeviceManager.java (SDL2) флагом RECEIVER_EXPORTED (2) для Android 14+.
# 5. Восстанавливает стандартный сертификат CN=Android Debug, O=Android, C=US и отключает pip install -U pip в p4a.

import os
import re
import shutil
import subprocess
from pathlib import Path

TARGET_API = "35"

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
    private WifiManager.MulticastLock multicastLock;

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
            if (wm != null) {
                if (wifiLock == null || !wifiLock.isHeld()) {
                    int mode = (Build.VERSION.SDK_INT >= 29) ? 4 : WifiManager.WIFI_MODE_FULL_HIGH_PERF;
                    wifiLock = wm.createWifiLock(mode, "AirSharePC::ServiceWifiLock");
                    wifiLock.setReferenceCounted(false);
                    wifiLock.acquire();
                }
                if (multicastLock == null || !multicastLock.isHeld()) {
                    multicastLock = wm.createMulticastLock("AirSharePC::ServiceMulticastLock");
                    multicastLock.setReferenceCounted(false);
                    multicastLock.acquire();
                }
            }
        } catch (Throwable ignored) {}
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || "STOP".equals(intent.getAction())) {
            releaseLocks();
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
                ? intent.getStringExtra("body") : "Sent: 0 • Received: 0";
        try {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (Build.VERSION.SDK_INT >= 26 && nm != null) {
                NotificationChannel ch = new NotificationChannel(
                        CHANNEL_ID, "AirShare PC", NotificationManager.IMPORTANCE_LOW);
                ch.setShowBadge(false);
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
                   .setStyle(new Notification.BigTextStyle().bigText(body))
                   .setSmallIcon(iconId)
                   .setOngoing(true)
                   .setOnlyAlertOnce(true)
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

    private void releaseLocks() {
        try {
            if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        } catch (Throwable ignored) {}
        try {
            if (wifiLock != null && wifiLock.isHeld()) wifiLock.release();
        } catch (Throwable ignored) {}
        try {
            if (multicastLock != null && multicastLock.isHeld()) multicastLock.release();
        } catch (Throwable ignored) {}
    }

    public void onTimeout(int startId) {
        releaseLocks();
        try {
            stopForeground(true);
        } catch (Throwable ignored) {}
        stopSelf(startId);
    }

    public void onTimeout(int startId, int fgsType) {
        onTimeout(startId);
    }

    @Override
    public void onDestroy() {
        releaseLocks();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
"""


def _patch_project_properties(path_obj: Path, compile_api: str = TARGET_API) -> bool:
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = re.sub(r"target=android-\d+", f"target=android-{compile_api}", old_text)
    if f"target=android-{compile_api}" not in new_text:
        new_text = f"target=android-{compile_api}\n" + new_text
    if "SDLActivity.nativePause();" in new_text:
        raise RuntimeError(f"Failed to patch SDLActivity.nativePause() in {path_obj}")
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
    # Добавляем разрешения FOREGROUND_SERVICE, FOREGROUND_SERVICE_DATA_SYNC, POST_NOTIFICATIONS и сам AirShareKeepAliveService
    if "<application" in new_text:
        required_perms = [
            "android.permission.FOREGROUND_SERVICE",
            "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
            "android.permission.POST_NOTIFICATIONS",
        ]
        perm_block = ""
        for perm in required_perms:
            if f'"{perm}"' not in new_text:
                perm_block += f'    <uses-permission android:name="{perm}" />\n'
        if perm_block:
            new_text = new_text.replace("<application", perm_block + "    <application", 1)

        svc_tag = (
            '    <service android:name="org.kivy.android.AirShareKeepAliveService" '
            'android:enabled="true" android:exported="false" '
            'android:stopWithTask="false" android:foregroundServiceType="dataSync" />\n'
        )
        if "org.kivy.android.AirShareKeepAliveService" not in new_text and "</application>" in new_text:
            new_text = new_text.replace("</application>", svc_tag + "    </application>", 1)

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
    # В SDLActivity.java вызов SDLActivity.nativePause() блокирует C-семафор Android_PauseSem, пока поток Kivy держит Python GIL.
    # Отключаем вызов nativePause()/nativeResume(), синхронизируем флаг sIsActivityPaused в onPause/onResume и записываем AirShareKeepAliveService.java.
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = old_text
    if "sIsActivityPaused" not in new_text and "class SDLActivity" in new_text:
        if "public static boolean mIsPaused" in new_text:
            new_text = new_text.replace(
                "public static boolean mIsPaused",
                "public static volatile boolean sIsActivityPaused = false;\n    public static boolean mIsPaused",
                1,
            )
        else:
            new_text = new_text.replace(
                "class SDLActivity",
                "class SDLActivity",
                1,
            )
            idx = new_text.find("{", new_text.find("class SDLActivity"))
            if idx != -1:
                new_text = (
                    new_text[: idx + 1]
                    + "\n    public static volatile boolean sIsActivityPaused = false;\n"
                    + new_text[idx + 1 :]
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

    # Записываем AirShareKeepAliveService.java рядом в org/kivy/android
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
    counts = {"props": 0, "gradle": 0, "manifest": 0, "hid": 0, "sdl": 0, "p4a_pip": 0}
    search_roots = []
    if root_dir is not None:
        search_roots.append(Path(root_dir))
    try:
        hook_dir = Path(__file__).resolve().parent
        if (hook_dir / ".buildozer").exists():
            search_roots.append(hook_dir / ".buildozer")
    except Exception:
        pass
    cwd_path = Path.cwd()
    if (cwd_path / ".buildozer").exists():
        search_roots.append(cwd_path / ".buildozer")
    if ".buildozer" in str(cwd_path):
        search_roots.append(cwd_path)
    home_buildozer = Path.home() / ".buildozer"
    if home_buildozer.exists():
        search_roots.append(home_buildozer)

    target_exact = {
        "project.properties",
        "build.gradle",
        "build.tmpl.gradle",
        "HIDDeviceManager.java",
        "SDLActivity.java",
        "PythonActivity.java",
        "build.py",
    }
    skip_dirs = {"android-ndk", "android-sdk", "ndk", "packages", "other_builds", ".git"}
    seen = set()
    for base in search_roots:
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith("android-ndk")]
            for fname in filenames:
                if fname not in target_exact and not (fname.startswith("AndroidManifest") and fname.endswith(".xml")):
                    continue
                fpath = Path(dirpath) / fname
                real_key = str(fpath)
                if real_key in seen:
                    continue
                seen.add(real_key)
                if fname == "project.properties":
                    if _patch_project_properties(fpath, TARGET_API):
                        counts["props"] += 1
                elif fname in ("build.gradle", "build.tmpl.gradle"):
                    if _patch_gradle_file(fpath, TARGET_API):
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
                elif fname == "PythonActivity.java":
                    try:
                        svc_file = fpath.parent / "AirShareKeepAliveService.java"
                        if not svc_file.exists() or svc_file.read_text(encoding="utf-8") != KEEP_ALIVE_SERVICE_JAVA:
                            svc_file.write_text(KEEP_ALIVE_SERVICE_JAVA, encoding="utf-8")
                    except Exception:
                        pass
                elif fname == "build.py" and "pythonforandroid" in str(fpath):
                    if _patch_p4a_venv_pip_upgrade(fpath):
                        counts["p4a_pip"] += 1
    return counts


def _extract_dist_dir(toolchain):
    if toolchain is None:
        return None
    for attr in ("dist_dir", "_dist", "dist", "ctx"):
        val = getattr(toolchain, attr, None)
        if val is not None:
            if isinstance(val, (str, Path)):
                return Path(val)
            sub_dir = getattr(val, "dist_dir", None)
            if sub_dir:
                return Path(sub_dir)
            sub_dist = getattr(val, "dist", None)
            if sub_dist is not None and getattr(sub_dist, "dist_dir", None):
                return Path(sub_dist.dist_dir)
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
    print(f"[AirShare p4a_hook] after_apk_assemble (target API {TARGET_API}) completed")


_restore_standard_debug_keystore()
patch_build_tree()

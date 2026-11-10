# Хук сборки python-for-android (p4a.hook) для AirShare PC:
# 1. Принудительно обновляет target=android-35 в закэшированном project.properties (обход бага Buildozer с кэшем).
# 2. Выставляет targetSdkVersion=35 и compileSdkVersion=35 в build.gradle и AndroidManifest.xml (убирает окно Play Защиты).
# 3. Патчит HIDDeviceManager.java (SDL2) флагом RECEIVER_EXPORTED (2) для Android 14/15+ (предотвращает SecurityException при старте).
# 4. Отключает самообновление pip (pip install -U pip) в pythonforandroid/build.py (обход бага p4a #3364 с capture_logging).

import os
import re
import shutil
import subprocess
from pathlib import Path

TARGET_API = "35"


def _patch_project_properties(path_obj: Path) -> bool:
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = re.sub(r"target=android-\d+", f"target=android-{TARGET_API}", old_text)
    if f"target=android-{TARGET_API}" not in new_text:
        new_text = f"target=android-{TARGET_API}\n" + new_text
    if new_text != old_text:
        path_obj.write_text(new_text, encoding="utf-8")
        return True
    return False


def _patch_gradle_file(path_obj: Path) -> bool:
    try:
        old_text = path_obj.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = re.sub(r"compileSdkVersion\s+\d+", f"compileSdkVersion {TARGET_API}", old_text)
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


def _patch_p4a_venv_pip_upgrade(path_obj: Path) -> bool:
    # Обход бага kivy/python-for-android#3364: pip install -U pip ломает venv на Python 3.14 (capture_logging)
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


def _ensure_custom_keystore():
    if not shutil.which("keytool"):
        return
    android_dir = Path.home() / ".android"
    ks_path = android_dir / "debug.keystore"
    marker_path = android_dir / ".airshare_ks_v2"
    if ks_path.exists() and marker_path.exists():
        return
    try:
        android_dir.mkdir(parents=True, exist_ok=True)
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
                "CN=JackBrownUA, OU=AirSharePC, O=JackBrownUA, L=Kyiv, ST=Kyiv, C=UA",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        marker_path.write_text("ok\n", encoding="utf-8")
    except Exception:
        pass


def patch_build_tree(root_dir=None) -> dict:
    counts = {"props": 0, "gradle": 0, "manifest": 0, "hid": 0, "p4a_pip": 0}
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
                    if _patch_project_properties(fpath):
                        counts["props"] += 1
                elif fname in ("build.gradle", "build.tmpl.gradle"):
                    if _patch_gradle_file(fpath):
                        counts["gradle"] += 1
                elif fname.startswith("AndroidManifest") and fname.endswith(".xml"):
                    if _patch_manifest_file(fpath):
                        counts["manifest"] += 1
                elif fname == "HIDDeviceManager.java":
                    if _patch_hid_device_manager(fpath):
                        counts["hid"] += 1
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
    _ensure_custom_keystore()
    dist_dir = _extract_dist_dir(toolchain)
    counts = patch_build_tree(dist_dir)
    print(f"[AirShare p4a_hook] before_apk_build patched: {counts}")


def after_apk_build(toolchain=None, *_args, **_kwargs):
    _ensure_custom_keystore()
    dist_dir = _extract_dist_dir(toolchain)
    counts = patch_build_tree(dist_dir)
    print(f"[AirShare p4a_hook] after_apk_build patched: {counts}")


def after_apk_assemble(toolchain=None, *_args, **_kwargs):
    dist_dir = _extract_dist_dir(toolchain)
    counts = patch_build_tree(dist_dir)
    print(f"[AirShare p4a_hook] after_apk_assemble patched: {counts}")


# Выполняем патч также сразу при импорте модуля p4a_hook
_ensure_custom_keystore()
patch_build_tree()

# Модуль файловых операций на сервере AirShare PC (v1.3.6):
# - Избранные и скрытые папки (хранятся на телефоне)
# - Корзина на 30 дней (.airshare_trash) с автоочисткой и восстановлением
# - Переименование, перемещение, копирование и создание папок без перекачки по Wi-Fi
# - Разделы «Последние файлы» и «Галерея» (группировка по датам)
# - Генерация и кэширование лёгких миниатюр (JPEG) на Android

import datetime
import json
import logging
import os
import secrets
import shutil
import time

from config import THUMB_CACHE_DIR, TRASH_DIR_NAME, TRASH_RETENTION_DAYS
from security import (
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    is_temp_part_file,
    is_within_storage,
    reserve_unique_filepath,
)
from utils import format_size

logger = logging.getLogger("airshare.file_ops")

DEFAULT_FAVORITE_FOLDERS = ["Download", "DCIM"]
DEFAULT_HIDDEN_FOLDERS = ["Android", "Alarms", "Audiobooks", "Backups"]


def is_internal_hidden_name(name: str) -> bool:
    return name == TRASH_DIR_NAME or is_temp_part_file(name)


def _trash_root(real_storage: str) -> str:
    return os.path.join(real_storage, TRASH_DIR_NAME)


def _trash_meta_path(real_storage: str) -> str:
    return os.path.join(_trash_root(real_storage), ".meta.json")


def _load_trash_meta(real_storage: str) -> dict:
    meta_path = _trash_meta_path(real_storage)
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_trash_meta(real_storage: str, data: dict):
    troot = _trash_root(real_storage)
    os.makedirs(troot, exist_ok=True)
    meta_path = _trash_meta_path(real_storage)
    tmp = f"{meta_path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, meta_path)


def cleanup_expired_trash(real_storage: str, retention_days: int = TRASH_RETENTION_DAYS) -> int:
    troot = _trash_root(real_storage)
    if not os.path.isdir(troot):
        return 0
    meta = _load_trash_meta(real_storage)
    now = time.time()
    max_age = max(1, int(retention_days)) * 86400
    removed = 0
    changed = False

    for tid in list(meta.keys()):
        entry = meta.get(tid) or {}
        deleted_at = float(entry.get("deleted_at", 0.0))
        if (now - deleted_at) >= max_age:
            item_path = os.path.join(troot, tid)
            try:
                if os.path.isdir(item_path) and not os.path.islink(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                elif os.path.exists(item_path) or os.path.islink(item_path):
                    os.remove(item_path)
            except OSError:
                pass
            meta.pop(tid, None)
            removed += 1
            changed = True

    if changed:
        try:
            _save_trash_meta(real_storage, meta)
        except OSError:
            pass
    return removed


def move_to_trash(real_storage: str, rel_paths: list) -> list:
    troot = _trash_root(real_storage)
    os.makedirs(troot, exist_ok=True)
    meta = _load_trash_meta(real_storage)
    moved = []

    for raw_rel in rel_paths:
        clean_rel = str(raw_rel or "").replace("\x00", "").replace("\\", "/").lstrip("/")
        if not clean_rel or clean_rel == TRASH_DIR_NAME or clean_rel.startswith(f"{TRASH_DIR_NAME}/"):
            continue
        full_src = os.path.realpath(os.path.join(real_storage, clean_rel))
        if not is_within_storage(real_storage, full_src) or full_src == real_storage:
            continue
        if not os.path.exists(full_src):
            continue
        tid = f"{int(time.time())}_{secrets.token_hex(4)}"
        dest = os.path.join(troot, tid)
        try:
            shutil.move(full_src, dest)
            meta[tid] = {
                "id": tid,
                "name": os.path.basename(full_src),
                "orig_rel": clean_rel,
                "is_dir": os.path.isdir(dest),
                "deleted_at": time.time(),
            }
            moved.append(clean_rel)
        except OSError as exc:
            logger.warning("Не удалось переместить в корзину %s: %s", clean_rel, exc)

    if moved:
        _save_trash_meta(real_storage, meta)
    return moved


def list_trash_items(real_storage: str) -> list:
    cleanup_expired_trash(real_storage)
    troot = _trash_root(real_storage)
    if not os.path.isdir(troot):
        return []
    meta = _load_trash_meta(real_storage)
    now = time.time()
    max_age = TRASH_RETENTION_DAYS * 86400
    items = []
    for tid, entry in meta.items():
        p = os.path.join(troot, tid)
        if not os.path.exists(p):
            continue
        deleted_at = float(entry.get("deleted_at", now))
        days_left = max(0, int((max_age - (now - deleted_at)) // 86400) + 1)
        try:
            sz = "—" if entry.get("is_dir") else format_size(os.path.getsize(p))
        except OSError:
            sz = "—"
        items.append(
            {
                "id": tid,
                "name": entry.get("name", tid),
                "orig_rel": entry.get("orig_rel", ""),
                "is_dir": bool(entry.get("is_dir", False)),
                "size_str": sz,
                "days_left": days_left,
            }
        )
    items.sort(key=lambda x: x["id"], reverse=True)
    return items


def restore_from_trash(real_storage: str, trash_ids: list) -> list:
    troot = _trash_root(real_storage)
    meta = _load_trash_meta(real_storage)
    restored = []
    for tid in trash_ids:
        clean_id = os.path.basename(str(tid or "").replace("\x00", ""))
        entry = meta.get(clean_id)
        if not entry:
            continue
        src = os.path.join(troot, clean_id)
        if not os.path.exists(src):
            meta.pop(clean_id, None)
            continue
        orig_rel = str(entry.get("orig_rel", entry.get("name", clean_id))).lstrip("/")
        parent_rel = os.path.dirname(orig_rel)
        target_dir = os.path.realpath(os.path.join(real_storage, parent_rel)) if parent_rel else real_storage
        if not is_within_storage(real_storage, target_dir):
            target_dir = real_storage
        os.makedirs(target_dir, exist_ok=True)
        dest_name = os.path.basename(orig_rel) or entry.get("name", clean_id)
        dest_path, _final_name = reserve_unique_filepath(target_dir, dest_name)
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            shutil.move(src, dest_path)
            meta.pop(clean_id, None)
            restored.append(orig_rel)
        except OSError as exc:
            logger.warning("Ошибка восстановления %s: %s", clean_id, exc)
    _save_trash_meta(real_storage, meta)
    return restored


def purge_from_trash(real_storage: str, trash_ids: list) -> int:
    troot = _trash_root(real_storage)
    meta = _load_trash_meta(real_storage)
    count = 0
    for tid in trash_ids:
        clean_id = os.path.basename(str(tid or "").replace("\x00", ""))
        src = os.path.join(troot, clean_id)
        if os.path.exists(src):
            try:
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.rmtree(src, ignore_errors=True)
                else:
                    os.remove(src)
                count += 1
            except OSError:
                pass
        if clean_id in meta:
            meta.pop(clean_id, None)
    _save_trash_meta(real_storage, meta)
    return count


def rename_item(real_storage: str, rel_path: str, new_name: str):
    clean_rel = str(rel_path or "").replace("\x00", "").replace("\\", "/").lstrip("/")
    clean_new = os.path.basename(str(new_name or "").replace("\x00", "").strip())
    if not clean_rel or not clean_new or clean_new in (".", "..") or is_internal_hidden_name(clean_new):
        return False, "Invalid name"
    src = os.path.realpath(os.path.join(real_storage, clean_rel))
    if not is_within_storage(real_storage, src) or src == real_storage or not os.path.exists(src):
        return False, "Not found"
    parent = os.path.dirname(src)
    dest = os.path.realpath(os.path.join(parent, clean_new))
    if not is_within_storage(real_storage, dest):
        return False, "Forbidden"
    if os.path.exists(dest):
        return False, "Already exists"
    try:
        os.replace(src, dest)
        return True, clean_new
    except OSError as exc:
        return False, str(exc)


def move_or_copy_items(real_storage: str, rel_paths: list, dest_rel_dir: str, copy_mode: bool = False):
    clean_dest_rel = str(dest_rel_dir or "").replace("\x00", "").replace("\\", "/").lstrip("/")
    dest_dir = os.path.realpath(os.path.join(real_storage, clean_dest_rel)) if clean_dest_rel else real_storage
    if not is_within_storage(real_storage, dest_dir) or not os.path.isdir(dest_dir):
        return False, "Invalid target folder", []

    done = []
    for raw_rel in rel_paths:
        clean_rel = str(raw_rel or "").replace("\x00", "").replace("\\", "/").lstrip("/")
        if not clean_rel:
            continue
        src = os.path.realpath(os.path.join(real_storage, clean_rel))
        if not is_within_storage(real_storage, src) or src == real_storage or not os.path.exists(src):
            continue
        if os.path.isdir(src) and os.path.commonpath([src, dest_dir]) == src:
            continue
        base_name = os.path.basename(src)
        target_path, _final_name = reserve_unique_filepath(dest_dir, base_name)
        try:
            if os.path.exists(target_path):
                os.remove(target_path)
            if copy_mode:
                if os.path.isdir(src):
                    shutil.copytree(src, target_path, symlinks=False)
                else:
                    shutil.copy2(src, target_path)
            else:
                shutil.move(src, target_path)
            done.append(clean_rel)
        except OSError as exc:
            logger.warning("Ошибка %s %s -> %s: %s", "копирования" if copy_mode else "перемещения", clean_rel, dest_dir, exc)
    return len(done) > 0, ("OK" if done else "No items processed"), done


def create_folder(real_storage: str, rel_parent: str, folder_name: str):
    clean_parent = str(rel_parent or "").replace("\x00", "").replace("\\", "/").lstrip("/")
    clean_name = os.path.basename(str(folder_name or "").replace("\x00", "").strip())
    if not clean_name or clean_name in (".", "..") or is_internal_hidden_name(clean_name):
        return False, "Invalid folder name"
    parent_dir = os.path.realpath(os.path.join(real_storage, clean_parent)) if clean_parent else real_storage
    if not is_within_storage(real_storage, parent_dir) or not os.path.isdir(parent_dir):
        return False, "Invalid parent"
    target = os.path.realpath(os.path.join(parent_dir, clean_name))
    if not is_within_storage(real_storage, target):
        return False, "Forbidden"
    try:
        os.makedirs(target, exist_ok=False)
        return True, clean_name
    except FileExistsError:
        return False, "Already exists"
    except OSError as exc:
        return False, str(exc)


def scan_recent_and_gallery(real_storage: str, hidden_items: list, limit_recent: int = 80, limit_gallery: int = 400):
    hidden_set = set(hidden_items or []) | {TRASH_DIR_NAME}
    recent = []
    gallery_raw = []
    skip_names = {".thumbnails", ".trash", ".Trashes", TRASH_DIR_NAME}

    try:
        for root, dirs, files in os.walk(real_storage, followlinks=False):
            rel_root = os.path.relpath(root, real_storage).replace("\\", "/")
            if rel_root == ".":
                rel_root = ""
            filtered_dirs = []
            for d in dirs:
                if d in skip_names or is_internal_hidden_name(d) or d.startswith("."):
                    continue
                rel_d = f"{rel_root}/{d}" if rel_root else d
                if d in hidden_set or rel_d in hidden_set:
                    continue
                filtered_dirs.append(d)
            dirs[:] = filtered_dirs

            for f in files:
                if is_internal_hidden_name(f) or f.startswith("."):
                    continue
                full_f = os.path.join(root, f)
                if os.path.islink(full_f) and not is_within_storage(real_storage, full_f):
                    continue
                rel_f = f"{rel_root}/{f}" if rel_root else f
                try:
                    st = os.stat(full_f)
                except OSError:
                    continue
                _, ext = os.path.splitext(f)
                ext_l = ext.lower()
                kind = "image" if ext_l in IMAGE_EXTENSIONS else ("video" if ext_l in VIDEO_EXTENSIONS else "file")
                entry = {
                    "name": f,
                    "rel_path": rel_f,
                    "size_str": format_size(st.st_size),
                    "mtime": st.st_mtime,
                    "kind": kind,
                }
                recent.append(entry)
                if kind in ("image", "video"):
                    gallery_raw.append(entry)
                if len(recent) >= 6000:
                    break
            if len(recent) >= 6000:
                break
    except OSError:
        pass

    recent.sort(key=lambda x: x["mtime"], reverse=True)
    gallery_raw.sort(key=lambda x: x["mtime"], reverse=True)

    groups = []
    by_date = {}
    for item in gallery_raw[:limit_gallery]:
        dt_str = datetime.datetime.fromtimestamp(item["mtime"]).strftime("%Y-%m-%d")
        if dt_str not in by_date:
            by_date[dt_str] = []
            groups.append({"date": dt_str, "items": by_date[dt_str]})
        by_date[dt_str].append(item)

    return recent[:limit_recent], groups


def get_or_create_cached_thumbnail(target_file: str, st_stat, max_dim: int = 260) -> bytes:
    # На Android генерируем и кэшируем сжатый JPEG-эскиз через BitmapFactory / ThumbnailUtils
    try:
        from kivy.utils import platform
    except Exception:
        platform = "unknown"

    if platform != "android":
        return b""

    try:
        import hashlib
        cache_key = hashlib.sha1(f"{target_file}:{st_stat.st_mtime_ns}:{st_stat.st_size}".encode("utf-8")).hexdigest()
        os.makedirs(THUMB_CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(THUMB_CACHE_DIR, f"{cache_key}.jpg")
        if os.path.isfile(cache_file):
            with open(cache_file, "rb") as f:
                return f.read()

        from jnius import autoclass
        _, ext = os.path.splitext(target_file)
        ext_l = ext.lower()
        bmp = None
        if ext_l in VIDEO_EXTENSIONS:
            ThumbnailUtils = autoclass("android.media.ThumbnailUtils")
            MediaImages = autoclass("android.provider.MediaStore$Images$Thumbnails")
            bmp = ThumbnailUtils.createVideoThumbnail(target_file, MediaImages.MINI_KIND)
        elif ext_l in IMAGE_EXTENSIONS:
            BitmapFactory = autoclass("android.graphics.BitmapFactory")
            Options = autoclass("android.graphics.BitmapFactory$Options")
            opts = Options()
            opts.inJustDecodeBounds = True
            BitmapFactory.decodeFile(target_file, opts)
            w, h = int(opts.outWidth), int(opts.outHeight)
            sample = 1
            while (w // sample) > max_dim * 2 and (h // sample) > max_dim * 2:
                sample *= 2
            opts2 = Options()
            opts2.inSampleSize = sample
            bmp = BitmapFactory.decodeFile(target_file, opts2)

        if bmp is not None:
            ByteArrayOutputStream = autoclass("java.io.ByteArrayOutputStream")
            CompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")
            baos = ByteArrayOutputStream()
            bmp.compress(CompressFormat.JPEG, 76, baos)
            jpeg_bytes = bytes(baos.toByteArray())
            bmp.recycle()
            if jpeg_bytes:
                with open(cache_file, "wb") as cf:
                    cf.write(jpeg_bytes)
                return jpeg_bytes
    except Exception as exc:
        logger.debug("Ошибка генерации эскиза %s: %s", target_file, exc)
    return b""

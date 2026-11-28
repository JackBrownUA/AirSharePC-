package com.airshare.airshare.server

import com.airshare.airshare.SettingsStore
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.Locale

object FileOps {
    const val TRASH_DIR_NAME = ".airshare_trash"

    fun isInternalHidden(name: String): Boolean =
        name == TRASH_DIR_NAME || name == ".nomedia" || SecurityManager.isTempPartFile(name)

    private fun trashRoot(storage: File): File = File(storage, TRASH_DIR_NAME)
    private fun trashMetaFile(storage: File): File = File(trashRoot(storage), ".meta.json")

    private fun loadTrashMeta(storage: File): JSONObject {
        val f = trashMetaFile(storage)
        if (!f.isFile) return JSONObject()
        return try {
            JSONObject(f.readText(Charsets.UTF_8))
        } catch (_: Exception) {
            JSONObject()
        }
    }

    private fun saveTrashMeta(storage: File, meta: JSONObject) {
        val dir = trashRoot(storage)
        if (!dir.exists()) dir.mkdirs()
        val nomedia = File(dir, ".nomedia")
        if (!nomedia.exists()) {
            try { nomedia.createNewFile() } catch (_: Exception) {}
        }
        val target = trashMetaFile(storage)
        val tmp = File(dir, ".meta.json.tmp")
        tmp.writeText(meta.toString(2), Charsets.UTF_8)
        tmp.renameTo(target)
    }

    private fun cleanRel(raw: String): String =
        raw.replace("\u0000", "").replace("\\", "/").trimStart('/')

    fun moveToTrash(storage: File, relPaths: List<String>): List<String> {
        val dir = trashRoot(storage)
        if (!dir.exists()) dir.mkdirs()
        val nomedia = File(dir, ".nomedia")
        if (!nomedia.exists()) try { nomedia.createNewFile() } catch (_: Exception) {}
        val meta = loadTrashMeta(storage)
        val moved = mutableListOf<String>()

        for (raw in relPaths) {
            val rel = cleanRel(raw)
            if (rel.isEmpty() || rel == TRASH_DIR_NAME || rel.startsWith("$TRASH_DIR_NAME/")) continue
            val src = File(storage, rel)
            if (!SecurityManager.isWithinStorage(storage, src) || src.canonicalPath == storage.canonicalPath) continue
            if (!src.exists()) continue
            val tid = "${System.currentTimeMillis() / 1000L}_${SecurityManager.randomHex(4)}"
            val dest = File(dir, tid)
            val ok = src.renameTo(dest) || run {
                try {
                    src.copyRecursively(dest, overwrite = true)
                    src.deleteRecursively()
                    true
                } catch (_: Exception) {
                    false
                }
            }
            if (ok) {
                meta.put(
                    tid,
                    JSONObject()
                        .put("id", tid)
                        .put("name", src.name)
                        .put("orig_rel", rel)
                        .put("is_dir", dest.isDirectory)
                        .put("deleted_at", System.currentTimeMillis() / 1000L),
                )
                moved.add(rel)
            }
        }
        if (moved.isNotEmpty()) saveTrashMeta(storage, meta)
        return moved
    }

    fun listTrashItems(storage: File): JSONArray {
        val dir = trashRoot(storage)
        val arr = JSONArray()
        if (!dir.isDirectory) return arr
        val meta = loadTrashMeta(storage)
        val keys = mutableListOf<String>()
        val it = meta.keys()
        while (it.hasNext()) keys.add(it.next())
        keys.sortDescending()

        for (tid in keys) {
            val entry = meta.optJSONObject(tid) ?: continue
            val itemFile = File(dir, tid)
            if (!itemFile.exists()) continue
            val isDir = entry.optBoolean("is_dir", itemFile.isDirectory)
            val sz = if (isDir) "—" else SettingsStore.formatSize(itemFile.length())
            arr.put(
                JSONObject()
                    .put("id", tid)
                    .put("name", entry.optString("name", tid))
                    .put("orig_rel", entry.optString("orig_rel", ""))
                    .put("is_dir", isDir)
                    .put("size_str", sz),
            )
        }
        return arr
    }

    fun restoreFromTrash(storage: File, ids: List<String>): List<String> {
        val dir = trashRoot(storage)
        val meta = loadTrashMeta(storage)
        val restored = mutableListOf<String>()
        for (rawId in ids) {
            val tid = File(rawId.replace("\u0000", "")).name
            val entry = meta.optJSONObject(tid) ?: continue
            val src = File(dir, tid)
            if (!src.exists()) {
                meta.remove(tid)
                continue
            }
            val origRel = cleanRel(entry.optString("orig_rel", entry.optString("name", tid)))
            val parentRel = File(origRel).parent
            var targetDir = if (!parentRel.isNullOrBlank()) File(storage, parentRel) else storage
            if (!SecurityManager.isWithinStorage(storage, targetDir)) targetDir = storage
            if (!targetDir.exists()) targetDir.mkdirs()
            val destName = File(origRel).name.ifBlank { entry.optString("name", tid) }
            val dest = SecurityManager.reserveUniqueFile(targetDir, destName)
            dest.delete()
            val ok = src.renameTo(dest) || run {
                try {
                    src.copyRecursively(dest, overwrite = true)
                    src.deleteRecursively()
                    true
                } catch (_: Exception) {
                    false
                }
            }
            if (ok) {
                meta.remove(tid)
                restored.add(origRel)
            }
        }
        saveTrashMeta(storage, meta)
        return restored
    }

    fun purgeFromTrash(storage: File, ids: List<String>): Int {
        val dir = trashRoot(storage)
        val meta = loadTrashMeta(storage)
        var count = 0
        for (rawId in ids) {
            val tid = File(rawId.replace("\u0000", "")).name
            val src = File(dir, tid)
            if (src.exists()) {
                if (src.deleteRecursively()) count++
            }
            meta.remove(tid)
        }
        saveTrashMeta(storage, meta)
        return count
    }

    fun emptyTrash(storage: File): Int {
        val dir = trashRoot(storage)
        if (!dir.isDirectory) return 0
        var count = 0
        dir.listFiles()?.forEach { child ->
            if (child.name != ".nomedia") {
                if (child.deleteRecursively()) count++
            }
        }
        saveTrashMeta(storage, JSONObject())
        return count
    }

    fun renameItem(storage: File, relPath: String, newName: String): Pair<Boolean, String> {
        val rel = cleanRel(relPath)
        val cleanNew = File(newName.replace("\u0000", "").trim()).name
        if (rel.isEmpty() || cleanNew.isEmpty() || cleanNew in setOf(".", "..") || isInternalHidden(cleanNew)) {
            return false to "Invalid name"
        }
        val src = File(storage, rel)
        if (!SecurityManager.isWithinStorage(storage, src) || src.canonicalPath == storage.canonicalPath || !src.exists()) {
            return false to "Not found"
        }
        val dest = File(src.parentFile ?: storage, cleanNew)
        if (!SecurityManager.isWithinStorage(storage, dest)) return false to "Forbidden"
        if (dest.exists()) return false to "Already exists"
        return if (src.renameTo(dest)) true to cleanNew else false to "Rename failed"
    }

    fun moveOrCopyItems(
        storage: File,
        relPaths: List<String>,
        destRelDir: String,
        copyMode: Boolean,
    ): Pair<Boolean, List<String>> {
        val cleanDest = cleanRel(destRelDir)
        val destDir = if (cleanDest.isEmpty()) storage else File(storage, cleanDest)
        if (!SecurityManager.isWithinStorage(storage, destDir) || !destDir.isDirectory) {
            return false to emptyList()
        }
        val done = mutableListOf<String>()
        for (raw in relPaths) {
            val rel = cleanRel(raw)
            if (rel.isEmpty()) continue
            val src = File(storage, rel)
            if (!SecurityManager.isWithinStorage(storage, src) || src.canonicalPath == storage.canonicalPath || !src.exists()) continue
            if (src.isDirectory && (destDir.canonicalPath == src.canonicalPath || destDir.canonicalPath.startsWith(src.canonicalPath + File.separator))) {
                continue
            }
            val target = SecurityManager.reserveUniqueFile(destDir, src.name)
            target.delete()
            val ok = try {
                if (copyMode) {
                    src.copyRecursively(target, overwrite = true)
                    true
                } else {
                    src.renameTo(target) || run {
                        src.copyRecursively(target, overwrite = true)
                        src.deleteRecursively()
                        true
                    }
                }
            } catch (_: Exception) {
                false
            }
            if (ok) done.add(rel)
        }
        return done.isNotEmpty() to done
    }

    fun createFolder(storage: File, relParent: String, folderName: String): Pair<Boolean, String> {
        val parentRel = cleanRel(relParent)
        val cleanName = File(folderName.replace("\u0000", "").trim()).name
        if (cleanName.isEmpty() || cleanName in setOf(".", "..") || isInternalHidden(cleanName)) {
            return false to "Invalid folder name"
        }
        val parentDir = if (parentRel.isEmpty()) storage else File(storage, parentRel)
        if (!SecurityManager.isWithinStorage(storage, parentDir) || !parentDir.isDirectory) {
            return false to "Invalid parent"
        }
        val target = File(parentDir, cleanName)
        if (!SecurityManager.isWithinStorage(storage, target)) return false to "Forbidden"
        if (target.exists()) return false to "Already exists"
        return if (target.mkdir()) true to cleanName else false to "Cannot create folder"
    }

    fun listSubfoldersForPicker(storage: File, hiddenItems: Set<String>): JSONArray {
        val result = JSONArray()
        result.put(JSONObject().put("rel", "").put("label", "/ (Root)"))
        fun walk(dir: File, relPrefix: String, depth: Int) {
            if (depth > 2 || result.length() >= 120) return
            val children = dir.listFiles()?.filter { it.isDirectory && !it.name.startsWith(".") && !isInternalHidden(it.name) }
                ?.sortedBy { it.name.lowercase(Locale.ROOT) } ?: return
            for (c in children) {
                val rel = if (relPrefix.isEmpty()) c.name else "$relPrefix/${c.name}"
                if (c.name in hiddenItems || rel in hiddenItems) continue
                result.put(JSONObject().put("rel", rel).put("label", "/$rel"))
                walk(c, rel, depth + 1)
            }
        }
        walk(storage, "", 0)
        return result
    }
    @Volatile private var recentCacheKey: String = ""; @Volatile private var recentCacheMs: Long = 0L; @Volatile private var recentCacheJson: String? = null; fun invalidateRecentCache() { recentCacheJson = null; recentCacheMs = 0L }
    fun scanRecentFiles(storage: File, hiddenItems: Set<String>, limit: Int = 100): JSONArray {
        val cacheKey = "${storage.absolutePath}|${hiddenItems.hashCode()}|$limit"; val now = System.currentTimeMillis(); val cached = recentCacheJson; if (cached != null && cacheKey == recentCacheKey && now - recentCacheMs < 15_000L) return JSONArray(cached); data class Entry(val name: String, val rel: String, val size: Long, val mtime: Long, val kind: String)
        val list = mutableListOf<Entry>()
        val skip = setOf(".thumbnails", ".trash", ".Trashes", TRASH_DIR_NAME, "Android")
        fun walk(dir: File, relPrefix: String, depth: Int) {
            if (depth > 4 || list.size >= 1500) return
            val files = dir.listFiles() ?: return
            for (f in files) {
                val n = f.name
                if (n.startsWith(".") || isInternalHidden(n) || n in skip) continue
                val rel = if (relPrefix.isEmpty()) n else "$relPrefix/$n"
                if (n in hiddenItems || rel in hiddenItems) continue
                if (f.isDirectory) {
                    walk(f, rel, depth + 1)
                } else if (f.isFile) {
                    val dot = n.lastIndexOf('.')
                    val ext = if (dot >= 0) n.substring(dot).lowercase(Locale.ROOT) else ""
                    val kind = when {
                        ext in SecurityManager.IMAGE_EXTS -> "image"
                        ext in SecurityManager.VIDEO_EXTS -> "video"
                        else -> "file"
                    }
                    list.add(Entry(n, rel, f.length(), f.lastModified(), kind))
                }
            }
        }
        walk(storage, "", 0)
        list.sortByDescending { it.mtime }
        val arr = JSONArray()
        for (e in list.take(limit)) {
            arr.put(
                JSONObject()
                    .put("name", e.name)
                    .put("rel_path", e.rel)
                    .put("size_str", SettingsStore.formatSize(e.size))
                    .put("kind", e.kind),
            )
        }
        recentCacheKey = cacheKey; recentCacheJson = arr.toString(); recentCacheMs = System.currentTimeMillis(); return arr
    }

    fun searchStorage(storage: File, query: String, folderLabel: String): JSONArray {
        val tokens = query.trim().lowercase(Locale.ROOT).split(Regex("\\s+")).filter { it.isNotEmpty() }
        val arr = JSONArray()
        if (tokens.isEmpty()) return arr
        val skip = setOf(".thumbnails", ".trash", ".Trashes", TRASH_DIR_NAME)
        fun walk(dir: File, relPrefix: String, depth: Int) {
            if (depth > 8 || arr.length() >= 200) return
            val files = dir.listFiles() ?: return
            for (f in files) {
                if (arr.length() >= 200) return
                val n = f.name
                if (isInternalHidden(n) || n in skip) continue
                if (relPrefix == "Android" && (n == "data" || n == "obb")) continue
                val rel = if (relPrefix.isEmpty()) n else "$relPrefix/$n"
                val low = n.lowercase(Locale.ROOT)
                if (tokens.all { low.contains(it) }) {
                    val isDir = f.isDirectory
                    val dot = n.lastIndexOf('.')
                    val ext = if (dot >= 0) n.substring(dot).lowercase(Locale.ROOT) else ""
                    val kind = when {
                        isDir -> "folder"
                        ext in SecurityManager.IMAGE_EXTS -> "image"
                        ext in SecurityManager.VIDEO_EXTS -> "video"
                        else -> "file"
                    }
                    arr.put(
                        JSONObject()
                            .put("name", n)
                            .put("rel_path", rel)
                            .put("is_dir", isDir)
                            .put("size_str", if (isDir) folderLabel else SettingsStore.formatSize(f.length()))
                            .put("kind", kind),
                    )
                }
                if (f.isDirectory) walk(f, rel, depth + 1)
            }
        }
        walk(storage, "", 0)
        return arr
    }
}

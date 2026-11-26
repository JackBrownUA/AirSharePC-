package com.airshare.airshare.server

import android.content.ContentUris
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.util.Size
import com.airshare.airshare.SettingsStore
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class MediaItem(
    val id: Long,
    val name: String,
    val absPath: String,
    val relPath: String,
    val album: String,
    val sizeBytes: Long,
    val dateModifiedSec: Long,
    val kind: String,
)

class MediaLibrary(private val context: Context, private val store: SettingsStore) {
    private val cacheLock = Any()
    private var cachedAtMs = 0L
    private var cachedItems: List<MediaItem> = emptyList()
    private val thumbDir = File(context.cacheDir, "airshare_thumbs").apply { mkdirs() }

    fun invalidateCache() = synchronized(cacheLock) {
        cachedAtMs = 0L
        cachedItems = emptyList()
    }

    private fun queryAllMedia(): List<MediaItem> {
        val now = System.currentTimeMillis()
        synchronized(cacheLock) {
            if (cachedItems.isNotEmpty() && (now - cachedAtMs) < 30_000L) {
                return cachedItems
            }
        }
        val rootDir = store.getRootStorageDir()
        val rootPath = try { rootDir.canonicalPath } catch (_: Exception) { rootDir.absolutePath }
        val result = ArrayList<MediaItem>(2048)

        val projection = arrayOf(
            MediaStore.MediaColumns._ID,
            MediaStore.MediaColumns.DATA,
            MediaStore.MediaColumns.DISPLAY_NAME,
            MediaStore.MediaColumns.DATE_MODIFIED,
            MediaStore.MediaColumns.SIZE,
            MediaStore.MediaColumns.BUCKET_DISPLAY_NAME,
        )

        fun scanUri(uri: Uri, kind: String) {
            try {
                context.contentResolver.query(
                    uri,
                    projection,
                    null,
                    null,
                    "${MediaStore.MediaColumns.DATE_MODIFIED} DESC",
                )?.use { c ->
                    val idxId = c.getColumnIndex(MediaStore.MediaColumns._ID)
                    val idxData = c.getColumnIndex(MediaStore.MediaColumns.DATA)
                    val idxName = c.getColumnIndex(MediaStore.MediaColumns.DISPLAY_NAME)
                    val idxDate = c.getColumnIndex(MediaStore.MediaColumns.DATE_MODIFIED)
                    val idxSize = c.getColumnIndex(MediaStore.MediaColumns.SIZE)
                    val idxBucket = c.getColumnIndex(MediaStore.MediaColumns.BUCKET_DISPLAY_NAME)

                    while (c.moveToNext()) {
                        val absPath = if (idxData >= 0) c.getString(idxData) else null
                        if (absPath.isNullOrBlank()) continue
                        if (absPath.contains("/.airshare_trash/") || absPath.contains("/.thumbnails/")) continue
                        if (!absPath.startsWith(rootPath)) continue
                        val rel = absPath.removePrefix(rootPath).trimStart('/')
                        if (rel.isEmpty() || rel.startsWith(".") || rel.contains("/.")) continue
                        val id = if (idxId >= 0) c.getLong(idxId) else 0L
                        val name = (if (idxName >= 0) c.getString(idxName) else null) ?: File(absPath).name
                        val dateSec = if (idxDate >= 0) c.getLong(idxDate) else 0L
                        val size = if (idxSize >= 0) c.getLong(idxSize) else 0L
                        val bucket = (if (idxBucket >= 0) c.getString(idxBucket) else null)
                            ?.takeIf { it.isNotBlank() }
                            ?: File(absPath).parentFile?.name
                            ?: "Phone"
                        result.add(MediaItem(id, name, absPath, rel, bucket, size, dateSec, kind))
                    }
                }
            } catch (_: Exception) {}
        }

        scanUri(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, "image")
        scanUri(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, "video")
        result.sortByDescending { it.dateModifiedSec }

        synchronized(cacheLock) {
            cachedItems = result
            cachedAtMs = System.currentTimeMillis()
        }
        return result
    }

    fun getGalleryPage(
        album: String,
        offset: Int,
        limit: Int,
        showHidden: Boolean,
    ): JSONObject {
        val all = queryAllMedia()
        val hiddenAlbums = store.hiddenAlbums.toSet()
        val hiddenFolders = store.hiddenItems.toSet()

        val albumCounts = LinkedHashMap<String, Int>()
        val filtered = ArrayList<MediaItem>(all.size)

        for (item in all) {
            val parts = item.relPath.split("/")
            if (!showHidden && parts.dropLast(1).any { it in hiddenFolders }) continue
            albumCounts[item.album] = (albumCounts[item.album] ?: 0) + 1
            if (!showHidden && item.album in hiddenAlbums) continue
            if (album.isNotEmpty() && album != "__all__" && item.album != album) continue
            filtered.add(item)
        }

        val albumsArr = JSONArray()
        albumCounts.entries
            .sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key.lowercase(Locale.ROOT) })
            .forEach { (name, cnt) ->
                if (showHidden || name !in hiddenAlbums) {
                    albumsArr.put(
                        JSONObject()
                            .put("name", name)
                            .put("count", cnt)
                            .put("hidden", name in hiddenAlbums),
                    )
                }
            }

        val safeOff = offset.coerceAtLeast(0)
        val safeLim = limit.coerceIn(1, 300)
        val total = filtered.size
        val slice = if (safeOff < total) filtered.subList(safeOff, (safeOff + safeLim).coerceAtMost(total)) else emptyList()

        val sdf = SimpleDateFormat("yyyy-MM-dd", Locale.US)
        val grouped = LinkedHashMap<String, JSONArray>()
        for (item in slice) {
            val dateStr = sdf.format(Date(item.dateModifiedSec * 1000L))
            val list = grouped.getOrPut(dateStr) { JSONArray() }
            list.put(
                JSONObject()
                    .put("id", item.id)
                    .put("name", item.name)
                    .put("rel_path", item.relPath)
                    .put("album", item.album)
                    .put("size_str", SettingsStore.formatSize(item.sizeBytes))
                    .put("kind", item.kind),
            )
        }

        val groupsArr = JSONArray()
        for ((dateStr, itemsArr) in grouped) {
            groupsArr.put(JSONObject().put("date", dateStr).put("items", itemsArr))
        }

        return JSONObject()
            .put("groups", groupsArr)
            .put("albums", albumsArr)
            .put("total", total)
            .put("all_total", all.size)
            .put("offset", safeOff)
            .put("has_more", (safeOff + safeLim) < total)
    }

    fun getOrCreateThumbnail(file: File, mediaId: Long = 0L): ByteArray? {
        if (!file.isFile) return null
        val keyRaw = "${file.canonicalPath}:${file.lastModified()}:${file.length()}"
        val key = MessageDigest.getInstance("SHA-1").digest(keyRaw.toByteArray()).joinToString("") { "%02x".format(it) }
        val cacheFile = File(thumbDir, "$key.jpg")
        if (cacheFile.isFile) {
            return try { cacheFile.readBytes() } catch (_: Exception) { null }
        }

        val ext = file.extension.lowercase(Locale.ROOT).let { if (it.isEmpty()) "" else ".$it" }
        var bmp: Bitmap? = null
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && mediaId > 0L) {
                val baseUri = if (ext in SecurityManager.VIDEO_EXTS) {
                    MediaStore.Video.Media.EXTERNAL_CONTENT_URI
                } else {
                    MediaStore.Images.Media.EXTERNAL_CONTENT_URI
                }
                val uri = ContentUris.withAppendedId(baseUri, mediaId)
                bmp = try {
                    context.contentResolver.loadThumbnail(uri, Size(320, 320), null)
                } catch (_: Exception) {
                    null
                }
            }
            if (bmp == null && ext in SecurityManager.VIDEO_EXTS) {
                val mmr = MediaMetadataRetriever()
                try {
                    mmr.setDataSource(file.absolutePath)
                    val frame = mmr.getFrameAtTime(-1)
                    if (frame != null) {
                        val scale = (320f / maxOf(frame.width, frame.height).coerceAtLeast(1)).coerceAtMost(1f)
                        bmp = if (scale < 1f) {
                            Bitmap.createScaledBitmap(
                                frame,
                                (frame.width * scale).toInt().coerceAtLeast(1),
                                (frame.height * scale).toInt().coerceAtLeast(1),
                                true,
                            ).also { frame.recycle() }
                        } else {
                            frame
                        }
                    }
                } finally {
                    try { mmr.release() } catch (_: Exception) {}
                }
            }
            if (bmp == null && ext in SecurityManager.IMAGE_EXTS) {
                val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeFile(file.absolutePath, opts)
                var sample = 1
                while ((opts.outWidth / sample) > 640 && (opts.outHeight / sample) > 640) sample *= 2
                val opts2 = BitmapFactory.Options().apply { inSampleSize = sample }
                bmp = BitmapFactory.decodeFile(file.absolutePath, opts2)
            }
            if (bmp != null) {
                val baos = ByteArrayOutputStream()
                bmp.compress(Bitmap.CompressFormat.JPEG, 78, baos)
                val bytes = baos.toByteArray()
                bmp.recycle()
                if (bytes.isNotEmpty()) {
                    try { cacheFile.writeBytes(bytes) } catch (_: Exception) {}
                    return bytes
                }
            }
        } catch (_: Exception) {
            try { bmp?.recycle() } catch (_: Exception) {}
        }
        return null
    }
}

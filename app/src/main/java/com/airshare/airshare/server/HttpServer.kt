package com.airshare.airshare.server

import android.content.Context
import android.webkit.MimeTypeMap
import com.airshare.airshare.AppI18n
import com.airshare.airshare.AppState
import com.airshare.airshare.SettingsStore
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.io.RandomAccessFile
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URLDecoder
import java.security.MessageDigest
import java.util.Locale
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class HttpServer(
    private val context: Context,
    private val store: SettingsStore,
    private val mediaLibrary: MediaLibrary,
    private val onChallengeCreated: (AuthChallenge) -> Unit,
    private val onLockoutAlert: (String, Int) -> Unit,
    private val onFolderChanged: (String) -> Unit,
    private val onTransferCompleted: () -> Unit,
) {
    @Volatile
    private var running = false
    private var serverSocket: ServerSocket? = null
    private var acceptThread: Thread? = null
    private var pool: ExecutorService? = null
    private val lastActivityMs = AtomicLong(System.currentTimeMillis())

    companion object {
        private const val MAX_UPLOAD_BYTES = 4L * 1024L * 1024L * 1024L
        private const val STREAM_BUF = 256 * 1024
        private const val ITEMS_PER_PAGE = 300
    }

    fun touchActivity() {
        lastActivityMs.set(System.currentTimeMillis())
    }

    fun getIdleSeconds(): Long =
        ((System.currentTimeMillis() - lastActivityMs.get()) / 1000L).coerceAtLeast(0L)

    fun start(bindIp: String?, port: Int): Boolean {
        stop()
        touchActivity()
        return try {
            val ss = try {
                if (!bindIp.isNullOrBlank()) {
                    ServerSocket(port, 64, InetAddress.getByName(bindIp))
                } else {
                    ServerSocket(port, 64)
                }
            } catch (_: Exception) {
                ServerSocket(port, 64)
            }
            ss.reuseAddress = true
            serverSocket = ss
            running = true
            pool = Executors.newFixedThreadPool(24)
            acceptThread = Thread({
                while (running) {
                    try {
                        val sock = ss.accept()
                        sock.tcpNoDelay = true
                        sock.soTimeout = 30_000
                        pool?.execute { handleClient(sock) }
                    } catch (_: Exception) {
                        if (!running) break
                    }
                }
            }, "AirShare-Accept").apply {
                isDaemon = true
                start()
            }
            true
        } catch (_: Exception) {
            stop()
            false
        }
    }

    fun stop() {
        running = false
        try { serverSocket?.close() } catch (_: Exception) {}
        serverSocket = null
        try { pool?.shutdownNow() } catch (_: Exception) {}
        pool = null
        acceptThread = null
    }

    private fun readLine(ins: InputStream): String? {
        val baos = ByteArrayOutputStream(128)
        var b = ins.read()
        if (b == -1) return null
        while (b != -1) {
            if (b == '\n'.code) break
            if (b != '\r'.code) baos.write(b)
            if (baos.size() > 16384) break
            b = ins.read()
        }
        return baos.toString("UTF-8")
    }

    private fun parseQuery(qs: String?): Map<String, List<String>> {
        if (qs.isNullOrBlank()) return emptyMap()
        val map = LinkedHashMap<String, MutableList<String>>()
        for (part in qs.split("&")) {
            if (part.isEmpty()) continue
            val eq = part.indexOf('=')
            val k = urlDecode(if (eq >= 0) part.substring(0, eq) else part)
            val v = urlDecode(if (eq >= 0) part.substring(eq + 1) else "")
            map.getOrPut(k) { mutableListOf() }.add(v)
        }
        return map
    }

    private fun urlDecode(s: String): String =
        try { URLDecoder.decode(s.replace("+", "%2B"), "UTF-8") } catch (_: Exception) { s }

    private fun parseCookies(header: String?): Map<String, String> {
        if (header.isNullOrBlank()) return emptyMap()
        val res = HashMap<String, String>()
        for (part in header.split(";")) {
            val eq = part.indexOf('=')
            if (eq > 0) {
                res[part.substring(0, eq).trim()] = part.substring(eq + 1).trim()
            }
        }
        return res
    }

    private fun readBodyBytes(ins: InputStream, headers: Map<String, String>, maxBytes: Int = 2 * 1024 * 1024): ByteArray {
        val len = headers["content-length"]?.toIntOrNull()?.coerceIn(0, maxBytes) ?: 0
        if (len <= 0) return ByteArray(0)
        val out = ByteArray(len)
        var off = 0
        while (off < len) {
            val r = ins.read(out, off, len - off)
            if (r <= 0) break
            off += r
        }
        return if (off == len) out else out.copyOf(off)
    }

    private fun handleClient(sock: Socket) {
        try {
            val ins = BufferedInputStream(sock.getInputStream(), 65536)
            val out = BufferedOutputStream(sock.getOutputStream(), 65536)
            val ip = sock.inetAddress?.hostAddress?.substringBefore("%") ?: "unknown"

            val reqLine = readLine(ins) ?: return
            val parts = reqLine.split(" ")
            if (parts.size < 2) return
            val method = parts[0].uppercase(Locale.ROOT)
            val rawTarget = parts[1]

            val headers = HashMap<String, String>()
            while (true) {
                val line = readLine(ins) ?: break
                if (line.isEmpty()) break
                val colon = line.indexOf(':')
                if (colon > 0) {
                    headers[line.substring(0, colon).trim().lowercase(Locale.ROOT)] =
                        line.substring(colon + 1).trim()
                }
            }

            if (!SettingsStore.isPrivateLanIp(ip) && ip != "127.0.0.1" && ip != "::1") {
                sendText(out, 403, "Forbidden", "Local network only")
                return
            }

            val qIdx = rawTarget.indexOf('?')
            val path = (if (qIdx >= 0) rawTarget.substring(0, qIdx) else rawTarget).replace("\u0000", "")
            val query = parseQuery(if (qIdx >= 0) rawTarget.substring(qIdx + 1) else null)
            val cookies = parseCookies(headers["cookie"])
            val lang = resolveLang(query, cookies, headers["accept-language"])

            if (method == "GET" && path.startsWith("/assets/")) {
                serveAsset(out, path.removePrefix("/assets/"))
                return
            }

            if (method == "GET" && path == "/auth/status") {
                val cid = query["cid"]?.firstOrNull() ?: ""
                val st = SecurityManager.getChallengeStatus(cid, ip)
                sendJson(out, 200, JSONObject().put("status", st))
                return
            }

            if (method == "POST" && path == "/auth/start") {
                handleAuthStart(ins, out, ip, headers, lang)
                return
            }
            if (method == "POST" && path == "/auth/claim") {
                handleAuthClaim(ins, out, ip, headers)
                return
            }
            if (method == "POST" && path == "/login") {
                handlePinLogin(ins, out, ip, headers, lang)
                return
            }

            if (SecurityManager.isIpDisconnected(ip)) {
                if (path.startsWith("/api/")) {
                    sendJson(out, 403, JSONObject().put("error", AppI18n.tr(context, "web_dev_blocked", lang)))
                } else {
                    serveHtmlAsset(out, 403, "web/login.html", lang)
                }
                return
            }

            val (rateOk, retrySec) = SecurityManager.checkRateLimit(ip)
            if (!rateOk) {
                val msg = AppI18n.tr(context, "web_rate_limit", lang, "sec" to retrySec)
                if (path.startsWith("/api/")) {
                    sendJson(out, 429, JSONObject().put("error", msg).put("retry_after", retrySec))
                } else {
                    serveHtmlAsset(out, 429, "web/login.html", lang)
                }
                return
            }

            val session = SecurityManager.getSession(cookies["airshare_auth"], ip, store.password)
            if (session == null) {
                if (path.startsWith("/api/") || path == "/upload") {
                    sendJson(out, 401, JSONObject().put("error", "Unauthorized"))
                } else {
                    serveHtmlAsset(out, 200, "web/login.html", lang)
                }
                return
            }

            touchActivity()
            notifyClientIfNew(ip, headers["user-agent"] ?: "")

            when {
                method == "GET" && (path == "/" || path == "/index.html") -> {
                    serveHtmlAsset(out, 200, "web/index.html", lang)
                }
                method == "GET" && path == "/api/list" -> {
                    handleApiList(out, query, session.trusted, lang)
                }
                method == "GET" && path == "/api/gallery" -> {
                    val album = query["album"]?.firstOrNull() ?: ""
                    val offset = query["offset"]?.firstOrNull()?.toIntOrNull() ?: 0
                    val limit = query["limit"]?.firstOrNull()?.toIntOrNull() ?: 120
                    val showHid = session.trusted && store.showHidden
                    sendJson(out, 200, mediaLibrary.getGalleryPage(album, offset, limit, showHid))
                }
                method == "GET" && path == "/api/recent" -> {
                    val storage = activeStorage()
                    val hid = if (session.trusted && store.showHidden) emptySet() else store.hiddenItems.toSet()
                    val items = FileOps.scanRecentFiles(storage, hid, 120)
                    sendJson(out, 200, JSONObject().put("results", items))
                }
                method == "GET" && path == "/api/trash" -> {
                    if (!session.trusted) {
                        sendJson(out, 403, JSONObject().put("error", "Trusted device required"))
                        return
                    }
                    val storage = activeStorage()
                    sendJson(
                        out,
                        200,
                        JSONObject()
                            .put("items", FileOps.listTrashItems(storage))
                            .put("trash_path", File(storage, FileOps.TRASH_DIR_NAME).absolutePath),
                    )
                }
               method == "GET" && path == "/api/status" -> { sendJson(out, 200, JSONObject().put("trusted", session.trusted).put("active_folder", store.activeFolderKey).put("show_hidden", session.trusted && store.showHidden).put("lang", lang)) }
                method == "POST" && path == "/api/role" -> { val raw = readBodyBytes(ins, headers, 4096).toString(Charsets.UTF_8); val obj = try { JSONObject(raw.ifBlank { "{}" }) } catch (_: Exception) { JSONObject() }; if (obj.optBoolean("trusted", false)) { sendJson(out, 403, JSONObject().put("error", "Trusted device required")) } else { SecurityManager.setIpTrusted(ip, false); AppState.bumpDevices(); val tok = SecurityManager.createSessionToken(ip, store.password, trusted = false); sendJson(out, 200, JSONObject().put("ok", true).put("trusted", false), extraHeaders = mapOf("Set-Cookie" to "airshare_auth=$tok; HttpOnly; Path=/; SameSite=Lax")) } }
                method == "GET" && path == "/api/folders" -> {
                    if (!session.trusted) {
                        sendJson(out, 403, JSONObject().put("error", "Trusted device required"))
                        return
                    }
                    val storage = activeStorage()
                    val hid = if (store.showHidden) emptySet() else store.hiddenItems.toSet()
                    sendJson(out, 200, JSONObject().put("folders", FileOps.listSubfoldersForPicker(storage, hid)))
                }
                method == "GET" && path == "/api/search" -> {
                    val q = query["q"]?.firstOrNull() ?: ""
                    val fl = AppI18n.tr(context, "web_folder", lang)
                    sendJson(out, 200, JSONObject().put("results", FileOps.searchStorage(activeStorage(), q, fl)))
                }
                method == "GET" && path == "/api/hash" -> {
                    val rel = (query["path"]?.firstOrNull() ?: "").replace("\u0000", "").trimStart('/')
                    val f = File(activeStorage(), rel)
                    if (!SecurityManager.isWithinStorage(activeStorage(), f) || !f.isFile) {
                        sendJson(out, 404, JSONObject().put("error", "Not found"))
                    } else {
                        val sha = SecurityManager.computeCachedSha256(f)
                        sendJson(out, 200, JSONObject().put("name", f.name).put("sha256", sha))
                    }
                }
                (method == "GET" || method == "HEAD") && path.startsWith("/file/") -> {
                    val rel = urlDecode(path.removePrefix("/file/")).replace("\u0000", "").trimStart('/')
                    val f = File(activeStorage(), rel)
                    val asAttach = query["download"]?.firstOrNull() == "1"
                    val isThumb = query["thumb"]?.firstOrNull() == "1"
                    streamFile(out, activeStorage(), f, headers, asAttach, isThumb, 0L, method == "HEAD")
                }
                (method == "GET" || method == "HEAD") && path.startsWith("/media/") -> {
                    val sub = path.removePrefix("/media/")
                    val (cleanSub, pathThumb) = when {
                        sub.startsWith("thumb/") -> sub.removePrefix("thumb/") to true
                        sub.startsWith("raw/") -> sub.removePrefix("raw/") to false
                        else -> sub to false
                    }
                    val rel = urlDecode(cleanSub).replace("\u0000", "").trimStart('/')
                    val root = store.getRootStorageDir()
                    val f = File(root, rel)
                    val asAttach = query["download"]?.firstOrNull() == "1"
                    val isThumb = pathThumb || query["thumb"]?.firstOrNull() == "1"
                    val mid = (query["mid"]?.firstOrNull() ?: query["id"]?.firstOrNull())?.toLongOrNull() ?: 0L
                    streamFile(out, root, f, headers, asAttach, isThumb, mid, method == "HEAD")
                }
                method == "GET" && path == "/zip" -> {
                    val rel = (query["dir"]?.firstOrNull() ?: query["path"]?.firstOrNull() ?: "").replace("\u0000", "").trimStart('/')
                    streamFolderZip(out, File(activeStorage(), rel))
                }
                method == "GET" && path == "/download_selected" -> {
                    val files = (query["files"] ?: emptyList()) + (query["p"] ?: emptyList())
                    streamSelectedZip(out, files)
                }
                method == "POST" && path == "/upload" -> {
                    if (!session.trusted) {
                        sendText(out, 403, "Forbidden", "Trusted device required")
                        return
                    }
                    handleUpload(ins, out, query, headers)
                }
                method == "POST" && path == "/api/op" -> {
                    if (!session.trusted) {
                        sendJson(out, 403, JSONObject().put("error", "Trusted device required"))
                        return
                    }
                    handleApiOp(ins, out, query, headers)
                }
                else -> sendText(out, 404, "Not Found", "Not Found")
            }
        } catch (_: Exception) {
        } finally {
            try { sock.close() } catch (_: Exception) {}
        }
    }

    private fun activeStorage(): File = store.resolveFolder(store.activeFolderKey)

    private fun resolveLang(query: Map<String, List<String>>, cookies: Map<String, String>, acceptLang: String?): String {
        query["lang"]?.firstOrNull()?.lowercase(Locale.ROOT)?.let { if (it in SettingsStore.SUPPORTED_CODES) return it }
        cookies["airshare_lang"]?.lowercase(Locale.ROOT)?.let { if (it in SettingsStore.SUPPORTED_CODES) return it }
       
        return store.language
    }
    private fun detectDeviceLabel(ua: String?): String {
        val s = ua ?: ""
        return when {
            "Windows" in s -> "Windows PC"
            "Macintosh" in s || "Mac OS" in s -> "Mac"
            "Android" in s -> "Android"
            "iPhone" in s || "iPad" in s -> "iOS"
            "Linux" in s -> "Linux PC"
            else -> "PC"
        }
    }
    
    private fun notifyClientIfNew(ip: String, ua: String) {
        if (!SecurityManager.markIpNotified(ip)) return
            val osName = detectDeviceLabel(ua)
        store.addRecentIp("$osName • $ip")
        AppState.bumpDevices()
        AppState.showToast(AppI18n.tr(context, "toast_connected", store.language, "dev" to osName, "ip" to ip))
    }

    private fun handleAuthStart(ins: InputStream, out: OutputStream, ip: String, headers: Map<String, String>, lang: String) {
        val (rateOk, retrySec) = SecurityManager.checkRateLimit(ip)
        if (!rateOk) {
            sendJson(out, 429, JSONObject().put("error", AppI18n.tr(context, "web_rate_limit", lang, "sec" to retrySec)).put("retry_after", retrySec))
            return
        }
        val raw = readBodyBytes(ins, headers, 8192).toString(Charsets.UTF_8)
        val obj = try { JSONObject(raw.ifBlank { "{}" }) } catch (_: Exception) { JSONObject() }
        val mode = obj.optString("mode", "biometric")
        val action = obj.optString("action", "login")
        val folderKey = obj.optString("folder_key", "")
        val ch = SecurityManager.createChallenge(
            ip = ip,
            device = detectDeviceLabel(headers["user-agent"]),
            mode = mode,
            action = action,
            targetFolderKey = folderKey,
        )
        onChallengeCreated(ch)
        sendJson(
            out,
            200,
            JSONObject()
                .put("cid", ch.id)
                .put("mode", ch.mode)
                .put("target", ch.target)
                .put("pairs", JSONArray(ch.pairs)),
        )
    }

    private fun handleAuthClaim(ins: InputStream, out: OutputStream, ip: String, headers: Map<String, String>) {
        val raw = readBodyBytes(ins, headers, 8192).toString(Charsets.UTF_8)
        val obj = try { JSONObject(raw.ifBlank { "{}" }) } catch (_: Exception) { JSONObject() }
        val cid = obj.optString("cid", "")
        val ch = SecurityManager.claimApprovedChallenge(cid, ip)
        if (ch == null) {
            sendJson(out, 401, JSONObject().put("error", "Not approved"))
            return
        }
        SecurityManager.clearAuthFailures(ip)
        if (ch.action == "access_change" && ch.targetFolderKey.isNotBlank()) {
            store.activeFolderKey = ch.targetFolderKey
            AppState.setActiveFolder(ch.targetFolderKey)
            onFolderChanged(ch.targetFolderKey)
            sendJson(out, 200, JSONObject().put("ok", true).put("folder_key", ch.targetFolderKey))
            return
        }
        val tok = SecurityManager.createSessionToken(ip, store.password, ch.trusted)
        sendJson(
            out,
            200,
            JSONObject().put("ok", true).put("trusted", ch.trusted),
            extraHeaders = mapOf("Set-Cookie" to "airshare_auth=$tok; HttpOnly; Path=/; SameSite=Lax"),
        )
    }

    private fun handlePinLogin(ins: InputStream, out: OutputStream, ip: String, headers: Map<String, String>, lang: String) {
        val (rateOk, retrySec) = SecurityManager.checkRateLimit(ip)
        if (!rateOk) {
            sendJson(out, 429, JSONObject().put("error", AppI18n.tr(context, "web_rate_limit", lang, "sec" to retrySec)))
            return
        }
        val raw = readBodyBytes(ins, headers, 8192).toString(Charsets.UTF_8)
        val obj = try { JSONObject(raw.ifBlank { "{}" }) } catch (_: Exception) { JSONObject() }
        val provided = obj.optString("pin", "").trim()
        val action = obj.optString("action", "login")
        val folderKey = obj.optString("folder_key", "")

        if (SecurityManager.constantTimeEquals(provided, store.password)) {
            SecurityManager.clearAuthFailures(ip)
            if (action == "access_change" && folderKey.isNotBlank()) {
                store.activeFolderKey = folderKey
                AppState.setActiveFolder(folderKey)
                onFolderChanged(folderKey)
                sendJson(out, 200, JSONObject().put("ok", true).put("folder_key", folderKey))
                return
            }
            val isFirstConnect = store.recentIps.none { it.substringAfterLast("•").trim() == ip }; val startTrusted = !isFirstConnect; if (isFirstConnect) { val ch = SecurityManager.createChallenge(ip = ip, device = detectDeviceLabel(headers["user-agent"]), mode = "biometric", action = "role_select", targetFolderKey = store.activeFolderKey); AppState.setPendingChallenge(ch) }
            val tok = SecurityManager.createSessionToken(ip, store.password, trusted = startTrusted)
            sendJson(
                out,
                200,
                JSONObject().put("ok", true).put("trusted", startTrusted),
                extraHeaders = mapOf("Set-Cookie" to "airshare_auth=$tok; HttpOnly; Path=/; SameSite=Lax"),
            )
            return
        }

        val (count, locked) = SecurityManager.registerAuthFailure(ip)
        AppState.showToast(AppI18n.tr(context, "toast_bad_pin", store.language, "ip" to ip), "error")
        if (locked) onLockoutAlert(ip, count)
        val code = if (locked) 429 else 401
        val err = if (locked) AppI18n.tr(context, "web_rate_limit", lang, "sec" to 300) else AppI18n.tr(context, "pin_hint", lang)
        sendJson(out, code, JSONObject().put("error", err))
    }

    private fun handleApiList(out: OutputStream, query: Map<String, List<String>>, trusted: Boolean, lang: String) {
        val storage = activeStorage()
        val relDir = (query["path"]?.firstOrNull() ?: query["dir"]?.firstOrNull() ?: "").replace("\u0000", "").replace("\\", "/").trim('/')
        val dir = if (relDir.isEmpty()) storage else File(storage, relDir)
        if (!SecurityManager.isWithinStorage(storage, dir) || !dir.isDirectory) {
            sendJson(out, 404, JSONObject().put("error", "Directory not found"))
            return
        }

        val favorites = store.favorites
        val hiddenSet = store.hiddenItems.toSet()
        val showHidden = trusted && store.showHidden

        val rawFiles = dir.listFiles()?.filter { f ->
            val n = f.name
            if (FileOps.isInternalHidden(n)) || n.startsWith(".") return@filter false
            val relItem = if (relDir.isEmpty()) n else "$relDir/$n"
            if (!showHidden && (n in hiddenSet || relItem in hiddenSet)) return@filter false
            true
        } ?: emptyList()

        val sorted = rawFiles.sortedWith(
            compareBy<File>(
                { f ->
                    val relItem = if (relDir.isEmpty()) f.name else "$relDir/${f.name}"
                    !(f.name in favorites || relItem in favorites)
                },
                { !it.isDirectory },
                { it.name.lowercase(Locale.ROOT) },
            ),
        )

        val total = sorted.size
        val totalPages = ((total + ITEMS_PER_PAGE - 1) / ITEMS_PER_PAGE).coerceAtLeast(1)
        val page = (query["page"]?.firstOrNull()?.toIntOrNull() ?: 1).coerceIn(1, totalPages)
        val start = (page - 1) * ITEMS_PER_PAGE
        val pageSlice = if (start < total) sorted.subList(start, (start + ITEMS_PER_PAGE).coerceAtMost(total)) else emptyList()

        val itemsArr = JSONArray()
        for (f in pageSlice) {
            val relItem = if (relDir.isEmpty()) f.name else "$relDir/${f.name}"
            val isDir = f.isDirectory
            val dot = f.name.lastIndexOf('.')
            val ext = if (!isDir && dot >= 0) f.name.substring(dot).lowercase(Locale.ROOT) else ""
            val kind = when {
                isDir -> "folder"
                ext in SecurityManager.IMAGE_EXTS -> "image"
                ext in SecurityManager.VIDEO_EXTS -> "video"
                else -> "file"
            }
            itemsArr.put(
                JSONObject()
                    .put("name", f.name)
                    .put("rel_path", relItem)
                    .put("is_dir", isDir)
                    .put("size_str", if (isDir) AppI18n.tr(context, "web_folder", lang) else SettingsStore.formatSize(f.length()))
                    .put("kind", kind)
                    .put("fav", f.name in favorites || relItem in favorites),
            )
        }

        val favArr = JSONArray()
        for (fav in favorites) {
            val ff = File(storage, fav)
            if (SecurityManager.isWithinStorage(storage, ff) && ff.isDirectory) {
                favArr.put(fav)
            }
        }

        val uploadDest = "/" + if (relDir.isNotEmpty()) relDir else store.activeFolderKey
        sendJson(
            out,
            200,
            JSONObject()
                .put("rel_dir", relDir)
                .put("trusted", trusted)
                .put("show_hidden", showHidden)
                .put("active_folder", store.activeFolderKey)
                .put("upload_dest", uploadDest)
                .put("trash_path", File(storage, FileOps.TRASH_DIR_NAME).absolutePath)
                .put("favorites", favArr)
                .put("page", page)
                .put("total_pages", totalPages)
                .put("total_items", total)
                .put("items", itemsArr),
        )
    }

    private fun handleApiOp(ins: InputStream, out: OutputStream, query: Map<String, List<String>>, headers: Map<String, String>) {
        val op = query["op"]?.firstOrNull() ?: ""
        val raw = readBodyBytes(ins, headers, 1048576).toString(Charsets.UTF_8)
        val obj = try { JSONObject(raw.ifBlank { "{}" }) } catch (_: Exception) { JSONObject() }
        val storage = activeStorage()

        fun jsonStringList(key: String): List<String> {
            val a = obj.optJSONArray(key) ?: return emptyList()
            return (0 until a.length()).mapNotNull { a.optString(it)?.takeIf { s -> s.isNotBlank() } }
        }

        when (op) {
            "rename" -> {
                val (ok, msg) = FileOps.renameItem(storage, obj.optString("path"), obj.optString("new_name"))
                if (ok) FileOps.invalidateRecentCache(); sendJson(out, if (ok) 200 else 400, JSONObject().put("ok", ok).put("msg", msg))
            }
            "move", "copy" -> {
                val (ok, done) = FileOps.moveOrCopyItems(storage, jsonStringList("paths"), obj.optString("dest_dir"), op == "copy")
                if (ok) FileOps.invalidateRecentCache(); sendJson(out, if (ok) 200 else 400, JSONObject().put("ok", ok).put("done", JSONArray(done)))
            }
            "mkdir" -> {
                val (ok, msg) = FileOps.createFolder(storage, obj.optString("dir"), obj.optString("name"))
                sendJson(out, if (ok) 200 else 400, JSONObject().put("ok", ok).put("msg", msg))
            }
            "delete" -> {
                val moved = FileOps.moveToTrash(storage, jsonStringList("paths"))
                mediaLibrary.invalidateCache(); FileOps.invalidateRecentCache()
                sendJson(out, if (moved.isNotEmpty()) 200 else 400, JSONObject().put("ok", moved.isNotEmpty()).put("moved", JSONArray(moved)))
            }
            "restore" -> {
                val restored = FileOps.restoreFromTrash(storage, jsonStringList("ids"))
                mediaLibrary.invalidateCache(); FileOps.invalidateRecentCache()
                sendJson(out, if (restored.isNotEmpty()) 200 else 400, JSONObject().put("ok", restored.isNotEmpty()))
            }
            "purge" -> {
                val cnt = FileOps.purgeFromTrash(storage, jsonStringList("ids"))
                sendJson(out, 200, JSONObject().put("ok", true).put("purged", cnt))
            }
            "empty_trash" -> {
                val cnt = FileOps.emptyTrash(storage)
                sendJson(out, 200, JSONObject().put("ok", true).put("purged", cnt))
            }
            "fav" -> {
                val rel = obj.optString("rel_path").trim('/')
                val list = store.favorites.toMutableList()
                if (rel in list) list.remove(rel) else if (rel.isNotEmpty()) list.add(rel)
                store.favorites = list
                sendJson(out, 200, JSONObject().put("ok", true))
            }
            "hide" -> {
                val rel = obj.optString("rel_path").trim('/')
                val list = store.hiddenItems.toMutableList()
                if (rel in list) list.remove(rel) else if (rel.isNotEmpty()) list.add(rel)
                store.hiddenItems = list
                sendJson(out, 200, JSONObject().put("ok", true))
            }
            "show_hidden", "toggle_hidden" -> {
                store.showHidden = !store.showHidden
                sendJson(out, 200, JSONObject().put("ok", true).put("show_hidden", store.showHidden))
            }
            "hide_album", "toggle_album" -> {
                val alb = obj.optString("album").trim()
                val list = store.hiddenAlbums.toMutableList()
                if (alb in list) list.remove(alb) else if (alb.isNotEmpty()) list.add(alb)
                store.hiddenAlbums = list
                sendJson(out, 200, JSONObject().put("ok", true))
            }
            else -> sendJson(out, 400, JSONObject().put("error", "Unknown op"))
        }
    }

    private fun handleUpload(ins: InputStream, out: OutputStream, query: Map<String, List<String>>, headers: Map<String, String>) {
        val rawName = query["name"]?.firstOrNull()
            ?: headers["x-file-name"]?.let { urlDecode(it) }
            ?: ""
        val filename = File(rawName.replace("\u0000", "").trim()).name
        if (filename.isEmpty() || filename in setOf(".", "..")) {
            sendText(out, 400, "Bad Request", "Invalid filename")
            return
        }
        val storage = activeStorage()
        val relDir = (query["dir"]?.firstOrNull() ?: "").replace("\u0000", "").trim('/')
        var targetDir = if (relDir.isEmpty()) storage else File(storage, relDir)
        if (!SecurityManager.isWithinStorage(storage, targetDir) || !targetDir.isDirectory) {
            sendText(out, 403, "Forbidden", "Forbidden target directory")
            return
        }
        if (targetDir.canonicalPath == store.getRootStorageDir().canonicalPath && !targetDir.canWrite()) {
            val dl = File(store.getRootStorageDir(), "Download")
            if (dl.isDirectory) targetDir = dl
        }

        val length = headers["content-length"]?.toLongOrNull() ?: -1L
        if (length < 0L) {
            sendText(out, 411, "Length Required", "Content-Length required")
            return
        }
        if (length > MAX_UPLOAD_BYTES) {
            sendText(out, 413, "Payload Too Large", "File too large")
            return
        }
        val expectedSha = (headers["x-content-sha256"] ?: headers["x-airshare-sha256"])?.trim()?.lowercase(Locale.ROOT) ?: ""
        if (expectedSha.isNotEmpty() && !SecurityManager.isValidSha256Hex(expectedSha)) {
            sendText(out, 400, "Bad Request", "Invalid X-Content-SHA256")
            return
        }

        val tmpFile = File(targetDir, ".airshare_${Thread.currentThread().id}_${SecurityManager.randomHex(4)}.part")
        val md = MessageDigest.getInstance("SHA-256")
        try {
            var remaining = length
            var received = 0L
            var lastProg = 0L
            val buf = ByteArray(STREAM_BUF)
            FileOutputStream(tmpFile).use { fos ->
                while (remaining > 0L) {
                    val toRead = minOf(remaining, buf.size.toLong()).toInt()
                    val r = ins.read(buf, 0, toRead)
                    if (r <= 0) break
                    fos.write(buf, 0, r)
                    md.update(buf, 0, r)
                    remaining -= r
                    received += r
                    val now = System.currentTimeMillis()
                    if (now - lastProg >= 150L || remaining == 0L) {
                        lastProg = now
                        AppState.updateTransferProgress(filename, received, length, "upload")
                    }
                }
            }
            if (remaining != 0L) {
                tmpFile.delete()
                sendText(out, 400, "Bad Request", "Incomplete upload")
                return
            }
            val actualSha = md.digest().joinToString("") { "%02x".format(it) }
            if (expectedSha.isNotEmpty() && !SecurityManager.constantTimeEquals(actualSha, expectedSha)) {
                tmpFile.delete()
                sendText(out, 422, "Unprocessable Entity", "SHA-256 mismatch")
                return
            }
            val dest = SecurityManager.reserveUniqueFile(targetDir, filename)
            dest.delete()
            if (!tmpFile.renameTo(dest)) {
                tmpFile.copyTo(dest, overwrite = true)
                tmpFile.delete()
            }
            mediaLibrary.invalidateCache(); FileOps.invalidateRecentCache()
            val lbl = AppI18n.tr(context, "uploaded", store.language)
            AppState.recordTransfer("${dest.name} ($lbl • ${SettingsStore.formatSize(received)})", "upload")
            onTransferCompleted()
            sendText(out, 200, "OK", "OK", extraHeaders = mapOf("X-Verified-SHA256" to actualSha))
        } catch (_: Exception) {
            tmpFile.delete()
            sendText(out, 500, "Internal Server Error", "Upload error")
        }
    }

    private fun streamFile(
        out: OutputStream,
        root: File,
        file: File,
        headers: Map<String, String>,
        asAttachment: Boolean,
        isThumb: Boolean,
        mediaId: Long,
        headOnly: Boolean,
    ) {
        if (!SecurityManager.isWithinStorage(root, file) || !file.isFile || FileOps.isInternalHidden(file.name)) {
            sendText(out, 404, "Not Found", "File not found")
            return
        }
        if (isThumb && !asAttachment && !headOnly) {
            val jpeg = mediaLibrary.getOrCreateThumbnail(file, mediaId)
            if (jpeg != null) {
                val isWebp = jpeg.size >= 4 && jpeg[0] == 'R'.code.toByte() && jpeg[1] == 'I'.code.toByte(); writeHeaders(
                    out,
                    200,
                    "OK",
                    if (isWebp) "image/webp" else "image/jpeg",
                    jpeg.size.toLong(),
                    mapOf("Cache-Control" to "private, max-age=3600"),
                )
                out.write(jpeg)
                out.flush()
                return
            }
        }

        val size = file.length()
        val ext = file.extension.lowercase(Locale.ROOT)
        val mime = when (ext) { "mp4", "m4v" -> "video/mp4"; "webm" -> "video/webm"; "mkv" -> "video/x-matroska"; "mov" -> "video/quicktime"; "avi" -> "video/x-msvideo"; "mp3" -> "audio/mpeg"; "m4a" -> "audio/mp4"; "ogg" -> "audio/ogg"; "wav" -> "audio/wav"; "flac" -> "audio/flac"; "jpg", "jpeg" -> "image/jpeg"; "png" -> "image/png"; "webp" -> "image/webp"; "gif" -> "image/gif"; else -> MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: "application/octet-stream" }
        val sandboxed = ".$ext" in SecurityManager.SANDBOX_EXTS
        val forceAttach = asAttachment || sandboxed

        val extra = LinkedHashMap<String, String>()
        extra["Accept-Ranges"] = "bytes"
        extra["Cache-Control"] = if (mime.startsWith("video/") || mime.startsWith("audio/")) "private, max-age=300" else "no-store"
        if (sandboxed) extra["Content-Security-Policy"] = "sandbox"
        if (forceAttach) extra["Content-Disposition"] = SecurityManager.makeContentDisposition(file.name, "attachment")

        var start = 0L
        var end = (size - 1L).coerceAtLeast(0L)
        val rangeHdr = headers["range"]
        var isPartial = false
        if (!rangeHdr.isNullOrBlank() && rangeHdr.startsWith("bytes=") && size > 0L) {
            val spec = rangeHdr.removePrefix("bytes=").substringBefore(",").trim()
            val dash = spec.indexOf('-')
            if (dash >= 0) {
                val sStr = spec.substring(0, dash).trim()
                val eStr = spec.substring(dash + 1).trim()
                if (sStr.isEmpty()) {
                    val suf = eStr.toLongOrNull() ?: 0L
                    if (suf > 0L) {
                        start = (size - suf).coerceAtLeast(0L)
                        end = size - 1L
                        isPartial = true
                    }
                } else {
                    val sVal = sStr.toLongOrNull()
                    val eVal = if (eStr.isEmpty()) size - 1L else eStr.toLongOrNull()
                    if (sVal == null || eVal == null || sVal < 0L || sVal >= size || eVal < sVal) {
                        writeHeaders(out, 416, "Range Not Satisfiable", "text/plain", 0L, mapOf("Content-Range" to "bytes */$size"))
                        out.flush()
                        return
                    }
                    start = sVal
                    end = eVal.coerceAtMost(size - 1L)
                    isPartial = true
                }
            }
        }

        val contentLen = if (size == 0L) 0L else (end - start + 1L)
        if (isPartial) {
            extra["Content-Range"] = "bytes $start-$end/$size"
            writeHeaders(out, 206, "Partial Content", mime, contentLen, extra)
        } else {
            writeHeaders(out, 200, "OK", mime, contentLen, extra)
        }
        out.flush()
        if (headOnly || contentLen == 0L) return

        val buf = ByteArray(STREAM_BUF)
        var left = contentLen
        var done = start
        var lastProg = 0L
        RandomAccessFile(file, "r").use { raf ->
            raf.seek(start)
            while (left > 0L) {
                val r = raf.read(buf, 0, minOf(left, buf.size.toLong()).toInt())
                if (r <= 0) break
                out.write(buf, 0, r); if (mime.startsWith("video/") || mime.startsWith("audio/")) out.flush()
                left -= r
                done += r
                if (forceAttach || (!isThumb && size >= 65536L)) {
                    val now = System.currentTimeMillis()
                    if (now - lastProg >= 150L || left == 0L) {
                        lastProg = now
                        AppState.updateTransferProgress(file.name, done, size, "download")
                    }
                }
            }
        }
        out.flush()
        if (!isThumb && size > 0L && start == 0L && (forceAttach || left == 0L)) {
            val lbl = AppI18n.tr(context, "downloaded", store.language)
            AppState.recordTransfer("${file.name} ($lbl • ${SettingsStore.formatSize(size)})", "download")
            onTransferCompleted()
        }
    }

    private fun streamFolderZip(out: OutputStream, folder: File) {
        val storage = activeStorage()
        if (!SecurityManager.isWithinStorage(storage, folder) || !folder.isDirectory) {
            sendText(out, 404, "Not Found", "Directory not found")
            return
        }
        val entries = mutableListOf<Pair<File, String>>()
        val parentPath = folder.parentFile?.canonicalPath ?: storage.canonicalPath
        folder.walkTopDown().forEach { f ->
            if (f.isFile && !FileOps.isInternalHidden(f.name) && SecurityManager.isWithinStorage(storage, f)) {
                val arc = f.canonicalPath.removePrefix(parentPath).trimStart(File.separatorChar).replace("\\", "/")
                entries.add(f to arc)
            }
        }
        streamZipEntries(out, "${folder.name.ifBlank { "archive" }}.zip", entries)
    }

    private fun streamSelectedZip(out: OutputStream, relPaths: List<String>) {
        val storage = activeStorage()
        val entries = mutableListOf<Pair<File, String>>()
        val seen = HashSet<String>()
        val rootCanon = storage.canonicalPath
        for (raw in relPaths) {
            val clean = raw.replace("\u0000", "").replace("\\", "/").trimStart('/')
            if (clean.isEmpty()) continue
            val cand = File(storage, clean)
            if (!SecurityManager.isWithinStorage(storage, cand) || !cand.exists()) continue
            if (cand.isFile && !FileOps.isInternalHidden(cand.name)) {
                val arc = cand.canonicalPath.removePrefix(rootCanon).trimStart(File.separatorChar).replace("\\", "/")
                if (seen.add(arc)) entries.add(cand to arc)
            } else if (cand.isDirectory) {
                cand.walkTopDown().forEach { f ->
                    if (f.isFile && !FileOps.isInternalHidden(f.name) && SecurityManager.isWithinStorage(storage, f)) {
                        val arc = f.canonicalPath.removePrefix(rootCanon).trimStart(File.separatorChar).replace("\\", "/")
                        if (seen.add(arc)) entries.add(f to arc)
                    }
                }
            }
        }
        if (entries.isEmpty()) {
            sendText(out, 404, "Not Found", "No valid files selected")
            return
        }
        streamZipEntries(out, "selected_files.zip", entries)
    }

    private fun streamZipEntries(out: OutputStream, zipName: String, entries: List<Pair<File, String>>) {
        val sb = StringBuilder()
        sb.append("HTTP/1.1 200 OK\r\n")
        sb.append("Content-Type: application/zip\r\n")
        sb.append("Content-Disposition: ").append(SecurityManager.makeContentDisposition(zipName)).append("\r\n")
        sb.append("X-Content-Type-Options: nosniff\r\n")
        sb.append("Connection: close\r\n\r\n")
        out.write(sb.toString().toByteArray(Charsets.UTF_8))
        out.flush()

        var totalBytes = 0L
        val buf = ByteArray(STREAM_BUF)
        ZipOutputStream(out).use { zos ->
            zos.setLevel(0)
            for ((file, arcName) in entries) {
                try {
                    val crc = CRC32()
                    FileInputStream(file).use { fis ->
                        while (true) {
                            val r = fis.read(buf)
                            if (r <= 0) break
                            crc.update(buf, 0, r)
                        }
                    }
                    val entry = ZipEntry(arcName).apply {
                        method = ZipEntry.STORED
                        size = file.length()
                        compressedSize = file.length()
                        this.crc = crc.value
                    }
                    zos.putNextEntry(entry)
                    FileInputStream(file).use { fis ->
                        while (true) {
                            val r = fis.read(buf)
                            if (r <= 0) break
                            zos.write(buf, 0, r)
                            totalBytes += r
                        }
                    }
                    zos.closeEntry()
                } catch (_: Exception) {}
            }
        }
        val lbl = AppI18n.tr(context, "downloaded", store.language)
        AppState.recordTransfer("$zipName ($lbl • ${SettingsStore.formatSize(totalBytes)})", "download")
        onTransferCompleted()
    }

    private fun serveAsset(out: OutputStream, rel: String) {
        val clean = rel.replace("..", "").trimStart('/')
        val ctype = when {
            clean.endsWith(".css") -> "text/css; charset=utf-8"
            clean.endsWith(".js") -> "application/javascript; charset=utf-8"
            clean.endsWith(".json") -> "application/json; charset=utf-8"
            clean.endsWith(".html") -> "text/html; charset=utf-8"
            else -> "application/octet-stream"
        }
        try {
            val bytes = context.assets.open("web/$clean").use { it.readBytes() }
            writeHeaders(out, 200, "OK", ctype, bytes.size.toLong(), mapOf("Cache-Control" to "private, max-age=3600"))
            out.write(bytes)
            out.flush()
        } catch (_: Exception) {
            sendText(out, 404, "Not Found", "Asset not found")
        }
    }

    private fun serveHtmlAsset(out: OutputStream, code: Int, assetPath: String, lang: String) {
        try {
            val raw = context.assets.open(assetPath).bufferedReader(Charsets.UTF_8).use { it.readText() }
            val i18nJson = AppI18n.rawJson(context, lang)
            val theme = if (store.themeMode == "light") "light" else "dark"
            val rendered = raw
                .replace("__INIT_LANG__", lang)
                .replace("__INIT_THEME__", theme)
                .replace("__INIT_I18N__", i18nJson)
            val bytes = rendered.toByteArray(Charsets.UTF_8)
            writeHeaders(out, code, if (code == 200) "OK" else "Error", "text/html; charset=utf-8", bytes.size.toLong(), mapOf("Cache-Control" to "no-store"))
            out.write(bytes)
            out.flush()
        } catch (_: Exception) {
            sendText(out, 500, "Error", "UI asset missing")
        }
    }

    private fun sendJson(out: OutputStream, code: Int, obj: JSONObject, extraHeaders: Map<String, String> = emptyMap()) {
        val bytes = obj.toString().toByteArray(Charsets.UTF_8)
        val hdrs = LinkedHashMap<String, String>()
        hdrs["Cache-Control"] = "no-store"
        hdrs.putAll(extraHeaders)
        writeHeaders(out, code, if (code in 200..299) "OK" else "Error", "application/json; charset=utf-8", bytes.size.toLong(), hdrs)
        out.write(bytes)
        out.flush()
    }

    private fun sendText(out: OutputStream, code: Int, reason: String, text: String, extraHeaders: Map<String, String> = emptyMap()) {
        val bytes = text.toByteArray(Charsets.UTF_8)
        val hdrs = LinkedHashMap<String, String>()
        hdrs["Cache-Control"] = "no-store"
        hdrs.putAll(extraHeaders)
        writeHeaders(out, code, reason, "text/plain; charset=utf-8", bytes.size.toLong(), hdrs)
        out.write(bytes)
        out.flush()
    }

    private fun writeHeaders(
        out: OutputStream,
        code: Int,
        reason: String,
        contentType: String,
        contentLength: Long,
        extra: Map<String, String> = emptyMap(),
    ) {
        val sb = StringBuilder()
        sb.append("HTTP/1.1 ").append(code).append(" ").append(reason).append("\r\n")
        sb.append("Content-Type: ").append(contentType).append("\r\n")
        sb.append("Content-Length: ").append(contentLength).append("\r\n")
        sb.append("X-Content-Type-Options: nosniff\r\n")
        sb.append("X-Frame-Options: SAMEORIGIN\r\n")
        sb.append("Referrer-Policy: no-referrer\r\n")
        for ((k, v) in extra) {
            sb.append(k).append(": ").append(v).append("\r\n")
        }
        sb.append("Connection: close\r\n\r\n")
        out.write(sb.toString().toByteArray(Charsets.UTF_8))
    }
}

package com.airshare.airshare

import android.content.Context
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.provider.Settings
import org.json.JSONArray
import java.io.File
import java.net.Inet4Address
import java.net.NetworkInterface
import java.security.SecureRandom
import java.util.Locale

data class StorageStats(
    val usedGb: Double,
    val totalGb: Double,
    val percent: Float,
)

class SettingsStore(private val context: Context) {
    private val prefs = context.getSharedPreferences("airshare_prefs_v2", Context.MODE_PRIVATE)
    private val rng = SecureRandom()

    companion object {
        val SUPPORTED_LANGUAGES = listOf(
            "en" to "English",
            "es" to "Español",
            "de" to "Deutsch",
            "lt" to "Lietuvių",
            "ru" to "Русский",
            "uk" to "Українська",
        )
        val SUPPORTED_CODES = SUPPORTED_LANGUAGES.map { it.first }.toSet()
        val DEFAULT_FAVORITES = listOf("Download", "DCIM")
        val DEFAULT_HIDDEN_ITEMS = listOf("Android", "Alarms", "Audiobooks", "Backups")
        private val WEAK_SEQ = "01234567890123456789 98765432109876543210"
        private val PRIMARY_PREFIXES = listOf("wlan", "swlan", "wifi", "eth", "en", "wl")
        private val SECONDARY_PREFIXES = listOf("ap", "softap", "rndis", "p2p")

        fun isPrivateLanIp(ip: String?): Boolean {
            if (ip.isNullOrBlank()) return false
            val parts = ip.trim().split(".")
            if (parts.size != 4) return false
            val nums = parts.map { it.toIntOrNull() ?: return false }
            if (nums.any { it !in 0..255 }) return false
            return nums[0] == 10 ||
                (nums[0] == 172 && nums[1] in 16..31) ||
                (nums[0] == 192 && nums[1] == 168)
        }

        fun formatSize(bytes: Long): String {
            var v = bytes.toDouble().coerceAtLeast(0.0)
            if (v < 1024.0) return "${v.toLong()} B"
            val units = arrayOf("KB", "MB", "GB", "TB", "PB")
            var idx = 0
            v /= 1024.0
            while (v >= 1024.0 && idx < units.lastIndex) {
                v /= 1024.0
                idx++
            }
            return String.format(Locale.US, "%.1f %s", v, units[idx])
        }
    }

    fun isWeakPin(pin: String): Boolean {
        val v = pin.trim()
        if (v.length < 6) return true
        if (v == "06102000") return true
        if (v.toSet().size <= 1) return true
        if (v.all { it.isDigit() } && WEAK_SEQ.contains(v)) return true
        return false
    }

    fun generatePin(): String {
        repeat(32) {
            val pin = String.format(Locale.US, "%06d", rng.nextInt(1_000_000))
            if (!isWeakPin(pin)) return pin
        }
        return (100000 + rng.nextInt(900000)).toString()
    }

    var password: String
        get() {
            val saved = prefs.getString("password", "") ?: ""
            if (saved.isBlank() || isWeakPin(saved)) {
                val fresh = generatePin()
                prefs.edit().putString("password", fresh).apply()
                return fresh
            }
            return saved
        }
        set(value) {
            val clean = if (isWeakPin(value)) generatePin() else value.trim()
            prefs.edit().putString("password", clean).apply()
        }

    var port: Int
        get() = prefs.getInt("port", 8080).coerceIn(1024, 65535)
        set(value) {
            if (value in 1024..65535) prefs.edit().putInt("port", value).apply()
        }

    var themeMode: String
        get() = prefs.getString("theme_mode", "dark") ?: "dark"
        set(value) {
            if (value in setOf("dark", "light", "system")) {
                prefs.edit().putString("theme_mode", value).apply()
            }
        }

    var language: String
        get() {
            val saved = prefs.getString("language", null)
            if (saved != null && saved in SUPPORTED_CODES) return saved
            val sys = Locale.getDefault().language.lowercase(Locale.ROOT).take(2)
            val resolved = if (sys in SUPPORTED_CODES) sys else "en"
            prefs.edit().putString("language", resolved).apply()
            return resolved
        }
        set(value) {
            val clean = value.lowercase(Locale.ROOT)
            if (clean in SUPPORTED_CODES) prefs.edit().putString("language", clean).apply()
        }

    var autoOffMinutes: Int
        get() = prefs.getInt("auto_off_minutes", 0).let { if (it in setOf(0, 15, 30, 60)) it else 0 }
        set(value) {
            if (value in setOf(0, 15, 30, 60)) prefs.edit().putInt("auto_off_minutes", value).apply()
        }

    var activeFolderKey: String
        get() = prefs.getString("active_folder_key", "downloads") ?: "downloads"
        set(value) {
            prefs.edit().putString("active_folder_key", value).apply()
        }

    var showHidden: Boolean
        get() = prefs.getBoolean("show_hidden", false)
        set(value) {
            prefs.edit().putBoolean("show_hidden", value).apply()
        }

    var recentIps: List<String>
        get() = readStringList("recent_ips", emptyList())
        set(value) = writeStringList("recent_ips", value.distinct().take(10))

    fun addRecentIp(ip: String) {
        val clean = ip.trim()
        if (clean.isEmpty()) return
        val cur = recentIps.toMutableList()
        cur.remove(clean)
        cur.add(0, clean)
        recentIps = cur.take(10)
    }

    var favorites: List<String>
        get() = readStringList("favorites", DEFAULT_FAVORITES)
        set(value) = writeStringList("favorites", value.distinct().take(50))

    var hiddenItems: List<String>
        get() = readStringList("hidden_items", DEFAULT_HIDDEN_ITEMS)
        set(value) = writeStringList("hidden_items", value.distinct().take(100))

    var hiddenAlbums: List<String>
        get() = readStringList("hidden_albums", emptyList())
        set(value) = writeStringList("hidden_albums", value.distinct().take(100))

    private fun readStringList(key: String, default: List<String>): List<String> {
        val raw = prefs.getString(key, null) ?: return default
        return try {
            val arr = JSONArray(raw)
            (0 until arr.length()).mapNotNull { i -> arr.optString(i)?.takeIf { it.isNotBlank() } }
        } catch (_: Exception) {
            default
        }
    }

    private fun writeStringList(key: String, list: List<String>) {
        val arr = JSONArray()
        list.forEach { arr.put(it) }
        prefs.edit().putString(key, arr.toString()).apply()
    }

    fun getRootStorageDir(): File = Environment.getExternalStorageDirectory()

    fun resolveFolder(key: String): File {
        val root = getRootStorageDir()
        val target = when (key) {
            "all", "All Storage" -> root
            "camera", "Camera Roll" -> File(root, "DCIM")
            "documents", "Documents" -> File(root, "Documents")
            else -> File(root, "Download")
        }
        if (!target.exists()) target.mkdirs()
        return if (target.isDirectory) target else root
    }

    fun getWifiIp(): String? {
        return try {
            val ifaces = NetworkInterface.getNetworkInterfaces() ?: return null
            var fallback: String? = null
            while (ifaces.hasMoreElements()) {
                val nif = ifaces.nextElement() ?: continue
                if (!nif.isUp || nif.isLoopback) continue
                val name = nif.name.lowercase(Locale.ROOT)
                val isPrimary = PRIMARY_PREFIXES.any { name.startsWith(it) }
                val isSecondary = SECONDARY_PREFIXES.any { name.startsWith(it) }
                if (!isPrimary && !isSecondary) continue
                val addrs = nif.inetAddresses
                while (addrs.hasMoreElements()) {
                    val addr = addrs.nextElement()
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        val host = addr.hostAddress ?: continue
                        if (isPrivateLanIp(host)) {
                            if (isPrimary) return host
                            if (fallback == null) fallback = host
                        }
                    }
                }
            }
            fallback
        } catch (_: Exception) {
            null
        }
    }

    fun getDeviceName(): String {
        try {
            val n = Settings.Global.getString(context.contentResolver, "device_name")
            if (!n.isNullOrBlank()) return n.trim()
        } catch (_: Exception) {}
        val model = (Build.MODEL ?: "").trim()
        val mfg = (Build.MANUFACTURER ?: "").trim().replaceFirstChar { it.uppercaseChar() }
        return when {
            model.startsWith(mfg, ignoreCase = true) && model.isNotBlank() -> model
            "$mfg $model".isNotBlank() -> "$mfg $model".trim()
            else -> "Android Device"
        }
    }

    fun getStorageStats(): StorageStats {
        return try {
            val sf = StatFs(getRootStorageDir().absolutePath)
            val total = sf.totalBytes.toDouble().coerceAtLeast(1.0)
            val free = sf.availableBytes.toDouble().coerceAtLeast(0.0)
            val used = (total - free).coerceAtLeast(0.0)
            val gb = 1024.0 * 1024.0 * 1024.0
            StorageStats(
                usedGb = used / gb,
                totalGb = total / gb,
                percent = (used / total).toFloat().coerceIn(0f, 1f),
            )
        } catch (_: Exception) {
            StorageStats(0.0, 0.0, 0f)
        }
    }

    fun hasFullStoragePermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            true
        }
    }
}

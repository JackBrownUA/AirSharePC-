package com.airshare.airshare.server

import java.io.File
import java.io.FileInputStream
import java.net.URLEncoder
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.concurrent.ConcurrentHashMap
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

data class DeviceSession(
    val token: String,
    val ip: String,
    val pwd: String,
    @Volatile var trusted: Boolean,
    val createdMs: Long,
)

data class AuthChallenge(
    val id: String,
    val ip: String,
    val device: String,
    val mode: String, // "biometric" or "pairs"
    val action: String = "login", // "login" or "access_change"
    val targetFolderKey: String = "",
    val pairs: List<String>,
    val target: String,
    @Volatile var status: String = "pending", // pending, approved, denied, cancelled, expired
    @Volatile var trusted: Boolean = false,
    val createdMs: Long = System.currentTimeMillis(),
)

data class FailureState(
    val count: Int,
    val blockedUntilMs: Long,
)

object SecurityManager {
    const val RATE_LIMIT_MAX_ATTEMPTS = 5
    const val RATE_LIMIT_BLOCK_MS = 300_000L
    const val SESSION_TTL_MS = 12 * 3600 * 1000L
    const val CHALLENGE_TTL_MS = 180_000L

    val SANDBOX_EXTS = setOf(".html", ".htm", ".svg", ".xhtml", ".js", ".mjs", ".xml")
    val IMAGE_EXTS = setOf(".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".heic")
    val VIDEO_EXTS = setOf(".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".3gp")
    private val SHA_REGEX = Regex("^[0-9a-fA-F]{64}$")

    private val rng = SecureRandom()
    private val lock = Any()
    private var sessionSecret = randomHex(16)
    private val sessions = LinkedHashMap<String, DeviceSession>()
    private val challenges = LinkedHashMap<String, AuthChallenge>()
    private val failures = HashMap<String, FailureState>()
    private val disconnectedIps = HashSet<String>()
    private val notifiedIps = HashSet<String>()
    private val hashCache = ConcurrentHashMap<String, String>()

    fun randomHex(bytes: Int): String {
        val arr = ByteArray(bytes)
        rng.nextBytes(arr)
        return arr.joinToString("") { "%02x".format(it) }
    }

    fun isTempPartFile(name: String): Boolean =
        name.startsWith(".airshare_") && name.endsWith(".part")

    fun isValidSha256Hex(v: String?): Boolean =
        !v.isNullOrBlank() && SHA_REGEX.matches(v.trim())

    fun constantTimeEquals(a: String, b: String): Boolean =
        MessageDigest.isEqual(a.toByteArray(Charsets.UTF_8), b.toByteArray(Charsets.UTF_8))

    fun isWithinStorage(root: File, candidate: File): Boolean {
        return try {
            val realRoot = root.canonicalPath
            val realCand = candidate.canonicalPath
            realCand == realRoot || realCand.startsWith(realRoot + File.separator)
        } catch (_: Exception) {
            false
        }
    }

    fun makeContentDisposition(filename: String, disposition: String = "attachment"): String {
        val clean = File(filename).name.replace("\"", "_").replace("\r", "").replace("\n", "")
        val ascii = clean.filter { it.code in 32..126 }.trim().let {
            if (it.isEmpty() || it.startsWith(".")) {
                val dot = clean.lastIndexOf('.')
                val ext = if (dot >= 0) clean.substring(dot) else ""
                "download$ext"
            } else it
        }
        val utf8 = URLEncoder.encode(clean, "UTF-8").replace("+", "%20")
        return "$disposition; filename=\"$ascii\"; filename*=UTF-8''$utf8"
    }

    fun reserveUniqueFile(dir: File, filename: String): File {
        val dot = filename.lastIndexOf('.')
        val stem = if (dot > 0) filename.substring(0, dot) else filename
        val ext = if (dot > 0) filename.substring(dot) else ""
        var counter = 0
        while (true) {
            val name = if (counter == 0) filename else "$stem ($counter)$ext"
            val cand = File(dir, name)
            try {
                if (cand.createNewFile()) return cand
            } catch (_: Exception) {}
            counter++
        }
    }

    fun computeCachedSha256(file: File): String {
        val key = "${file.canonicalPath}:${file.lastModified()}:${file.length()}"
        hashCache[key]?.let { return it }
        val md = MessageDigest.getInstance("SHA-256")
        val buf = ByteArray(1024 * 1024)
        FileInputStream(file).use { fis ->
            while (true) {
                val r = fis.read(buf)
                if (r <= 0) break
                md.update(buf, 0, r)
            }
        }
        val hex = md.digest().joinToString("") { "%02x".format(it) }
        if (hashCache.size > 512) hashCache.clear()
        hashCache[key] = hex
        return hex
    }

    fun resetAll() = synchronized(lock) {
        sessionSecret = randomHex(16)
        sessions.clear()
        challenges.clear()
        failures.clear()
        notifiedIps.clear()
    }

    fun resetRateLimits() = synchronized(lock) {
        failures.clear()
        sessions.clear()
        challenges.clear()
        sessionSecret = randomHex(16)
    }

    fun setIpDisconnected(ip: String, disconnected: Boolean) = synchronized(lock) {
        if (disconnected) {
            disconnectedIps.add(ip)
            notifiedIps.remove(ip)
            sessions.entries.removeIf { it.value.ip == ip }
        } else {
            disconnectedIps.remove(ip)
        }
    }

    fun isIpDisconnected(ip: String): Boolean = synchronized(lock) { ip in disconnectedIps }

    fun markIpNotified(ip: String): Boolean = synchronized(lock) { notifiedIps.add(ip) }

    fun setIpTrusted(ip: String, trusted: Boolean) = synchronized(lock) {
        sessions.values.filter { it.ip == ip }.forEach { it.trusted = trusted }
    }

    fun isIpTrusted(ip: String): Boolean = synchronized(lock) {
        sessions.values.any { it.ip == ip && it.trusted }
    }

    fun checkRateLimit(ip: String): Pair<Boolean, Int> = synchronized(lock) {
        val now = System.currentTimeMillis()
        val rec = failures[ip] ?: return true to 0
        if (rec.blockedUntilMs > now) {
            val sec = ((rec.blockedUntilMs - now) / 1000L).toInt() + 1
            return false to sec
        }
        if (rec.blockedUntilMs > 0L) failures.remove(ip)
        true to 0
    }

    fun registerAuthFailure(ip: String): Pair<Int, Boolean> = synchronized(lock) {
        val now = System.currentTimeMillis()
        val prev = failures[ip]
        val baseCount = if (prev != null && (prev.blockedUntilMs == 0L || prev.blockedUntilMs > now)) prev.count else 0
        val nextCount = baseCount + 1
        val blockedUntil = if (nextCount >= RATE_LIMIT_MAX_ATTEMPTS) now + RATE_LIMIT_BLOCK_MS else 0L
        failures[ip] = FailureState(nextCount, blockedUntil)
        nextCount to (blockedUntil > now)
    }

    fun clearAuthFailures(ip: String) = synchronized(lock) {
        failures.remove(ip)
    }

    fun createSessionToken(ip: String, pwd: String, trusted: Boolean): String = synchronized(lock) {
        val nonce = randomHex(16)
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(sessionSecret.toByteArray(Charsets.UTF_8), "HmacSHA256"))
        val tok = mac.doFinal("$ip:$pwd:$nonce".toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
        if (sessions.size >= 256) {
            sessions.keys.firstOrNull()?.let { sessions.remove(it) }
        }
        sessions[tok] = DeviceSession(tok, ip, pwd, trusted, System.currentTimeMillis())
        tok
    }

    fun getSession(token: String?, ip: String, expectedPwd: String): DeviceSession? = synchronized(lock) {
        if (token.isNullOrBlank()) return null
        val s = sessions[token] ?: return null
        if (System.currentTimeMillis() - s.createdMs > SESSION_TTL_MS) {
            sessions.remove(token)
            return null
        }
        if (s.ip == ip && constantTimeEquals(s.pwd, expectedPwd)) return s
        null
    }

    fun createChallenge(
        ip: String,
        device: String,
        mode: String = "biometric",
        action: String = "login",
        targetFolderKey: String = "",
    ): AuthChallenge = synchronized(lock) {
        val pool = LinkedHashSet<String>()
        while (pool.size < 3) {
            pool.add((10 + rng.nextInt(90)).toString())
        }
        val list = pool.toList()
        val target = list[rng.nextInt(3)]
        val now = System.currentTimeMillis()
        challenges.entries.removeIf { (_, v) ->
            (now - v.createdMs) > CHALLENGE_TTL_MS || (v.ip == ip && v.status == "pending")
        }
        if (challenges.size >= 32) {
            challenges.keys.firstOrNull()?.let { challenges.remove(it) }
        }
        val ch = AuthChallenge(
            id = randomHex(12),
            ip = ip,
            device = device.take(64),
            mode = if (mode == "pairs") "pairs" else "biometric",
            action = action,
            targetFolderKey = targetFolderKey,
            pairs = list,
            target = target,
            createdMs = now,
        )
        challenges[ch.id] = ch
        ch
    }

    fun getChallengeStatus(cid: String, ip: String): String = synchronized(lock) {
        val ch = challenges[cid] ?: return "expired"
        if (ch.ip != ip || (System.currentTimeMillis() - ch.createdMs) > CHALLENGE_TTL_MS) {
            challenges.remove(cid)
            return "expired"
        }
        ch.status
    }

    fun resolveChallenge(
        cid: String,
        selectedPair: String = "",
        approve: Boolean = true,
        trusted: Boolean = false,
        biometricOk: Boolean = false,
        cancelled: Boolean = false,
    ): Pair<Boolean, String> = synchronized(lock) {
        val ch = challenges[cid] ?: return false to "expired"
        if ((System.currentTimeMillis() - ch.createdMs) > CHALLENGE_TTL_MS) {
            challenges.remove(cid)
            return false to "expired"
        }
        if (ch.status != "pending") return false to ch.status
        if (cancelled) {
            ch.status = "cancelled"
            return true to "cancelled"
        }
        if (!approve) {
            ch.status = "denied"
            return true to "denied"
        }
        val pairOk = selectedPair.isNotBlank() && constantTimeEquals(selectedPair.trim(), ch.target)
        if (biometricOk || pairOk) {
            ch.status = "approved"
            ch.trusted = trusted
            return true to "approved"
        }
        ch.status = "denied"
        false to "mismatch"
    }

    fun claimApprovedChallenge(cid: String, ip: String): AuthChallenge? = synchronized(lock) {
        val ch = challenges[cid] ?: return null
        if (ch.ip != ip || ch.status != "approved") return null
        challenges.remove(cid)
        ch
    }
}

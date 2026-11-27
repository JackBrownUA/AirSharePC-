package com.airshare.airshare.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import com.airshare.airshare.AppI18n
import com.airshare.airshare.AppState
import com.airshare.airshare.MainActivity
import com.airshare.airshare.R
import com.airshare.airshare.SettingsStore
import com.airshare.airshare.server.AuthChallenge
import com.airshare.airshare.server.HttpServer
import com.airshare.airshare.server.MediaLibrary
import com.airshare.airshare.server.SecurityManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class AirShareForegroundService : Service() {
    companion object {
        const val ACTION_START = "com.airshare.airshare.START"
        const val ACTION_STOP = "com.airshare.airshare.STOP"
        const val ACTION_REFRESH_NOTIF = "com.airshare.airshare.REFRESH"

        private const val CH_FG = "airshare_fg_channel"
        private const val CH_ALERTS = "airshare_alerts_channel"
        private const val NOTIF_FG_ID = 1001
        private const val NOTIF_AUTH_ID = 2001
        private const val NOTIF_LOCKOUT_ID = 2002

        fun start(context: Context) {
            val intent = Intent(context, AirShareForegroundService::class.java).setAction(ACTION_START)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            val intent = Intent(context, AirShareForegroundService::class.java).setAction(ACTION_STOP)
            context.startService(intent)
        }
    }

    private lateinit var store: SettingsStore
    private lateinit var mediaLibrary: MediaLibrary
    private var httpServer: HttpServer? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var autoOffJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        store = SettingsStore(applicationContext)
        mediaLibrary = MediaLibrary(applicationContext, store)
        ensureChannels()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopServerAndSelf()
                return START_NOT_STICKY
            }
            ACTION_REFRESH_NOTIF -> {
                if (AppState.serverRunning.value) updateForegroundNotification()
                return START_STICKY
            }
            else -> startServer()
        }
        return START_STICKY
    }

    private fun startServer() {
        acquireLocks()
        val ip = store.getWifiIp()
        val port = store.port
        val srv = HttpServer(
            context = applicationContext,
            store = store,
            mediaLibrary = mediaLibrary,
            onChallengeCreated = { ch -> handleIncomingChallenge(ch) },
            onLockoutAlert = { ipAddr, attempts -> sendLockoutNotification(ipAddr, attempts) },
            onFolderChanged = { updateForegroundNotification() },
            onTransferCompleted = { updateForegroundNotification() },
        )
        val ok = srv.start(ip, port)
        if (!ok) {
            AppState.setServerRunning(false)
            AppState.showToast("Failed to start server on port $port", "error")
            stopServerAndSelf()
            return
        }
        httpServer = srv
        val url = "http://${ip ?: "127.0.0.1"}:$port"
        AppState.setActiveFolder(store.activeFolderKey)
        AppState.setServerRunning(true, url)
        val notif = buildForegroundNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_FG_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIF_FG_ID, notif)
        }
        startAutoOffWatcher()
    }

    private fun startAutoOffWatcher() {
        autoOffJob?.cancel()
        autoOffJob = serviceScope.launch {
            while (isActive && AppState.serverRunning.value) {
                delay(10_000L)
                val mins = store.autoOffMinutes
                val srv = httpServer
                if (mins > 0 && srv != null && srv.getIdleSeconds() >= mins * 60L) {
                    stopServerAndSelf()
                    break
                }
            }
        }
    }

    private fun handleIncomingChallenge(ch: AuthChallenge) {
        AppState.setPendingChallenge(ch)
        if (!AppState.isActivityInForeground) {
            val lang = store.language
            val titleKey = if (ch.action == "access_change") "notif_access_title" else "notif_auth_title"
            val bodyKey = if (ch.action == "access_change") "notif_access_body" else "notif_auth_body"
            val title = AppI18n.tr(this, titleKey, lang)
            val body = AppI18n.tr(this, bodyKey, lang, "ip" to ch.ip, "folder" to ch.targetFolderKey)
            sendAlertNotification(NOTIF_AUTH_ID, title, body)
        }
    }

    private fun sendLockoutNotification(ip: String, attempts: Int) {
        val lang = store.language
        val title = AppI18n.tr(this, "notif_lockout_title", lang)
        val body = AppI18n.tr(this, "notif_lockout_body", lang, "count" to attempts, "ip" to ip, "sec" to 300)
        sendAlertNotification(NOTIF_LOCKOUT_ID, title, body)
    }

    private fun sendAlertNotification(id: Int, title: String, body: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pi = PendingIntent.getActivity(
            this,
            id,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notif = NotificationCompat.Builder(this, CH_ALERTS)
            .setSmallIcon(R.drawable.ic_stat_airshare)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pi)
            .build()
        nm.notify(id, notif)
    }

    private fun ensureChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return
            val fgCh = NotificationChannel(CH_FG, "AirShare PC Server", NotificationManager.IMPORTANCE_LOW).apply {
                setShowBadge(false)
            }
            val alertCh = NotificationChannel(CH_ALERTS, "AirShare PC Security Alerts", NotificationManager.IMPORTANCE_HIGH)
            nm.createNotificationChannel(fgCh)
            nm.createNotificationChannel(alertCh)
        }
    }

    private fun buildForegroundNotification(): Notification {
        val lang = store.language
        val title = "AirShare PC — ${AppI18n.tr(this, "server_active", lang)}"
        val stats = AppI18n.tr(
            this,
            "notif_stats_fmt",
            lang,
            "sent" to AppState.sentCount.value,
            "received" to AppState.receivedCount.value,
        )
        val url = AppState.serverUrl.value
        val bigText = if (url.isNotBlank()) "$stats\n$url" else stats

        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openPi = PendingIntent.getActivity(this, 0, openIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

        val stopIntent = Intent(this, AirShareForegroundService::class.java).setAction(ACTION_STOP)
        val stopPi = PendingIntent.getService(this, 1, stopIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

        return NotificationCompat.Builder(this, CH_FG)
            .setSmallIcon(R.drawable.ic_stat_airshare)
            .setContentTitle(title)
            .setContentText(stats)
            .setStyle(NotificationCompat.BigTextStyle().bigText(bigText))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(openPi)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, AppI18n.tr(this, "disconnect", lang), stopPi)
            .build()
    }

    private fun updateForegroundNotification() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return
        nm.notify(NOTIF_FG_ID, buildForegroundNotification())
    }

    private fun acquireLocks() {
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as? PowerManager
            if (pm != null && (wakeLock == null || wakeLock?.isHeld == false)) {
                wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AirSharePC::WakeLock").apply {
                    setReferenceCounted(false)
                    acquire(6 * 60 * 60 * 1000L)
                }
            }
            val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            if (wm != null && (wifiLock == null || wifiLock?.isHeld == false)) {
                val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    WifiManager.WIFI_MODE_FULL_LOW_LATENCY
                } else {
                    @Suppress("DEPRECATION")
                    WifiManager.WIFI_MODE_FULL_HIGH_PERF
                }
                wifiLock = wm.createWifiLock(mode, "AirSharePC::WifiLock").apply {
                    setReferenceCounted(false)
                    acquire()
                }
            }
        } catch (_: Exception) {}
    }

    private fun releaseLocks() {
        try { if (wakeLock?.isHeld == true) wakeLock?.release() } catch (_: Exception) {}
        try { if (wifiLock?.isHeld == true) wifiLock?.release() } catch (_: Exception) {}
    }

    private fun stopServerAndSelf() {
        autoOffJob?.cancel()
        httpServer?.stop()
        httpServer = null
        SecurityManager.resetAll()
        AppState.setServerRunning(false)
        releaseLocks()
        try { stopForeground(STOP_FOREGROUND_REMOVE) } catch (_: Exception) {}
        stopSelf()
    }

    override fun onTimeout(startId: Int) {
        stopServerAndSelf()
    }

    override fun onDestroy() {
        autoOffJob?.cancel()
        httpServer?.stop()
        releaseLocks()
        serviceScope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}

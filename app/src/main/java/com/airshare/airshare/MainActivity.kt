package com.airshare.airshare

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import com.airshare.airshare.server.AuthChallenge
import com.airshare.airshare.server.SecurityManager
import com.airshare.airshare.service.AirShareForegroundService
import com.airshare.airshare.ui.AirSharePalettes
import com.airshare.airshare.ui.AirShareTheme
import com.airshare.airshare.ui.AuthChallengeModal
import com.airshare.airshare.ui.DrawerMenuRowItem
import com.airshare.airshare.ui.OriginalBottomNav
import com.airshare.airshare.ui.OriginalHeader
import com.airshare.airshare.ui.OriginalModalDialog
import com.airshare.airshare.ui.RadarHeroCard
import com.airshare.airshare.ui.RecentTransfersCard
import kotlinx.coroutines.launch
import java.util.Locale

class MainActivity : FragmentActivity() {

    private lateinit var store: SettingsStore
    private val resumeTick = mutableIntStateOf(0)
    
    private val permLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = SettingsStore(this)
        AppState.setActiveFolder(store.activeFolderKey)
        requestRuntimePermissions()

        setContent {
            AirShareRootScreen()
        }
    }

    override fun onResume() {
        super.onResume()
        AppState.isActivityInForeground = true
            resumeTick.intValue++
    }

    override fun onPause() {
        super.onPause()
        AppState.isActivityInForeground = false
    }

    private fun requestRuntimePermissions() {
        val perms = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= 33) {
            perms.add(Manifest.permission.POST_NOTIFICATIONS)
            perms.add(Manifest.permission.READ_MEDIA_IMAGES)
            perms.add(Manifest.permission.READ_MEDIA_VIDEO)
        } else {
            perms.add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
        if (perms.isNotEmpty()) {
            permLauncher.launch(perms.toTypedArray())
        }
    }

    private fun openAllFilesPermissionSettings() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try {
                val intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
                    data = Uri.parse("package:$packageName")
                }
                startActivity(intent)
            } catch (_: Exception) {
                startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
            }
        }
    }

    private fun canUseBiometrics(): Boolean {
        val bm = BiometricManager.from(this)
        val auth = BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.BIOMETRIC_WEAK
        return bm.canAuthenticate(auth) == BiometricManager.BIOMETRIC_SUCCESS
    }

    private fun launchBiometricPrompt(
        challenge: AuthChallenge,
        lang: String,
        trusted: Boolean,
    ) {
        val executor = ContextCompat.getMainExecutor(this)
        val prompt = BiometricPrompt(
            this,
            executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    SecurityManager.resolveChallenge(
                        cid = challenge.id,
                        approve = true,
                        trusted = trusted,
                        biometricOk = true,
                    )
                    AppState.setPendingChallenge(null)
                    AppState.bumpDevices()
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    SecurityManager.resolveChallenge(
                        cid = challenge.id,
                        approve = false,
                        cancelled = true,
                    )
                    AppState.setPendingChallenge(null)
                }

                override fun onAuthenticationFailed() {}
            },
        )

        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle(AppI18n.tr(this, "bio_prompt_title", lang))
            .setSubtitle(AppI18n.tr(this, "bio_prompt_sub", lang, "ip" to challenge.ip))
            .setNegativeButtonText(AppI18n.tr(this, "cancel", lang))
            .setAllowedAuthenticators(
                BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.BIOMETRIC_WEAK
            )
            .build()

        prompt.authenticate(info)
    }

    private fun copyToClipboard(label: String, text: String, toastMsg: String) {
        val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText(label, text))
        AppState.showToast(toastMsg)
    }

    @Composable
    private fun AirShareRootScreen() {
        var lang by remember { mutableStateOf(store.language) }
        var darkTheme by remember { mutableStateOf(store.themeMode != "light") }
        var currentPin by remember { mutableStateOf(store.password) }
        var currentPort by remember { mutableIntStateOf(store.port) }
        var autoOffMin by remember { mutableIntStateOf(store.autoOffMinutes) }
        var wifiIp by remember { mutableStateOf(store.getWifiIp()) }

        var showFilesModal by remember { mutableStateOf(false) }
        var showDevicesModal by remember { mutableStateOf(false) }
        var showTransfersModal by remember { mutableStateOf(false) }
        var showAutoOffModal by remember { mutableStateOf(false) }
        var showLanguageModal by remember { mutableStateOf(false) }
        var showSecurityModal by remember { mutableStateOf(false) }
        var showPortModal by remember { mutableStateOf(false) }
        var showHelpModal by remember { mutableStateOf(false) }
        var showAllStorageWarn by remember { mutableStateOf(false) }
        var showWifiModal by remember { mutableStateOf(false) }

        val serverRunning by AppState.serverRunning.collectAsState()
        val serverUrl by AppState.serverUrl.collectAsState()
        val activeFolder by AppState.activeFolderKey.collectAsState()
        val transferProgress by AppState.currentTransfer.collectAsState()
        val history by AppState.transferHistory.collectAsState()
        val pendingChallenge by AppState.pendingChallenge.collectAsState()
        val toastEvent by AppState.toast.collectAsState()
        val devicesVer by AppState.devicesVersion.collectAsState()

        val drawerState = rememberDrawerState(DrawerValue.Closed)
        val scope = rememberCoroutineScope()
        val snackbar = remember { SnackbarHostState() }
        val palette = if (darkTheme) AirSharePalettes.Dark else AirSharePalettes.Light

        fun t(key: String, vararg args: Pair<String, Any>): String =
            AppI18n.tr(this@MainActivity, key, lang, *args)

        fun folderTitle(key: String): String = when (key) {
            "camera", "Camera Roll" -> t("folder_cam_title")
            "documents", "Documents" -> t("folder_doc_title")
            "all", "All Storage" -> t("folder_all_title")
            else -> t("folder_dl_title")
        }

        fun langFlag(code: String): String = when (code) {
            "en" -> "\uD83C\uDDEC\uD83C\uDDE7"
            "es" -> "\uD83C\uDDEA\uD83C\uDDF8"
            "de" -> "\uD83C\uDDE9\uD83C\uDDEA"
            "lt" -> "\uD83C\uDDF1\uD83C\uDDF9"
            "ru" -> "\uD83C\uDDF7\uD83C\uDDFA"
            "uk" -> "\uD83C\uDDFA\uD83C\uDDE6"
            else -> "\uD83C\uDF10"
        }

        LaunchedEffect(toastEvent?.id) {
            val ev = toastEvent ?: return@LaunchedEffect
            snackbar.showSnackbar(ev.message)
            AppState.clearToast()
        }

        val storageStats = remember(serverRunning, history.size) { store.getStorageStats() }
        val devName = remember { store.getDeviceName() }
        var hasFullPerm by remember { mutableStateOf(store.hasFullStoragePermission()) }
        val rTick by resumeTick
        LaunchedEffect(rTick) {
            hasFullPerm = store.hasFullStoragePermission()
            wifiIp = store.getWifiIp()
        }
        
        AirShareTheme(darkTheme = darkTheme) {
            ModalNavigationDrawer(
                drawerState = drawerState,
                drawerContent = {
                    ModalDrawerSheet(
                        modifier = Modifier
                            .width(292.dp)
                            .fillMaxHeight()
                            .padding(start = 12.dp, top = 28.dp, bottom = 22.dp),
                        drawerShape = RoundedCornerShape(26.dp),
                        drawerContainerColor = palette.drawerBg,
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(horizontal = 18.dp, vertical = 18.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            Text(
                                text = "AirShare PC",
                                color = palette.text,
                                fontSize = 22.sp,
                                fontWeight = FontWeight.Bold,
                            )

                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    imageVector = Icons.Default.PhoneAndroid,
                                    contentDescription = null,
                                    tint = palette.subtext,
                                    modifier = Modifier.size(18.dp),
                                )
                                Spacer(Modifier.width(8.dp))
                                Text(
                                    text = devName,
                                    color = palette.text,
                                    fontSize = 14.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }

                            Surface(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(15.dp))
                                    .clickable {
                                        showFilesModal = true
                                        scope.launch { drawerState.close() }
                                    },
                                shape = RoundedCornerShape(15.dp),
                                color = palette.drawerCard,
                                border = BorderStroke(
                                    1.dp,
                                    Brush.verticalGradient(listOf(palette.highlightBorder, palette.drawerBorder)),
                                ),
                                shadowElevation = 6.dp,
                            ) {
                                Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        Text(
                                            text = String.format(Locale.US, "%.1f / %.1f GB", storageStats.usedGb, storageStats.totalGb),
                                            color = palette.text,
                                            fontSize = 12.5.sp,
                                            fontWeight = FontWeight.SemiBold,
                                        )
                                        Spacer(Modifier.width(10.dp))
                                        Text(
                                            text = folderTitle(activeFolder),
                                            color = palette.subtext,
                                            fontSize = 11.sp,
                                            textAlign = TextAlign.End,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                            modifier = Modifier.weight(1f),
                                        )
                                    }
                                    Spacer(Modifier.height(7.dp))
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .height(5.dp)
                                            .clip(RoundedCornerShape(99.dp))
                                            .background(palette.pillBg),
                                    ) {
                                        Box(
                                            modifier = Modifier
                                                .fillMaxWidth(storageStats.percent.coerceIn(0f, 1f))
                                                .fillMaxHeight()
                                                .clip(RoundedCornerShape(99.dp))
                                                .background(palette.text),
                                        )
                                    }
                                }
                            }

                            Surface(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(15.dp))
                                    .clickable {
                                        wifiIp = store.getWifiIp()
                                        if (!serverRunning && wifiIp == null) showWifiModal = true
                                        else if (serverRunning) AirShareForegroundService.stop(this@MainActivity)
                                        else AirShareForegroundService.start(this@MainActivity)
                                    },
                                shape = RoundedCornerShape(15.dp),
                                color = palette.drawerCard,
                                border = BorderStroke(
                                    1.dp,
                                    Brush.verticalGradient(listOf(palette.highlightBorder, palette.drawerBorder)),
                                ),
                                shadowElevation = 6.dp,
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 11.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Computer,
                                        contentDescription = null,
                                        tint = if (serverRunning) palette.green else palette.text,
                                        modifier = Modifier.size(26.dp),
                                    )
                                    Spacer(Modifier.width(12.dp))
                                    Column {
                                        Text(
                                            text = if (serverRunning) t("server_active") else t("server_stopped"),
                                            color = palette.text,
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.SemiBold,
                                        )
                                        Text(
                                            text = "Port $currentPort • PIN $currentPin",
                                            color = palette.subtext,
                                            fontSize = 11.5.sp,
                                        )
                                    }
                                }
                            }

                            Spacer(Modifier.weight(1f))

                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .verticalScroll(rememberScrollState()),
                            ) {
                                DrawerMenuRowItem(Icons.Default.Timer, t("menu_auto_off"), palette) {
                                    showAutoOffModal = true
                                    scope.launch { drawerState.close() }
                                }
                                DrawerMenuRowItem(Icons.Default.Language, t("menu_language"), palette) {
                                    showLanguageModal = true
                                    scope.launch { drawerState.close() }
                                }
                                DrawerMenuRowItem(Icons.Default.Lock, t("menu_security"), palette) {
                                    showSecurityModal = true
                                    scope.launch { drawerState.close() }
                                }
                                DrawerMenuRowItem(Icons.Default.Tune, t("menu_port"), palette) {
                                    showPortModal = true
                                    scope.launch { drawerState.close() }
                                }
                                DrawerMenuRowItem(Icons.Default.HelpOutline, t("menu_help"), palette) {
                                    showHelpModal = true
                                    scope.launch { drawerState.close() }
                                }
                            }

                            Surface(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(40.dp),
                                shape = RoundedCornerShape(16.dp),
                                color = palette.drawerCard,
                                border = BorderStroke(1.dp, palette.drawerBorder),
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .padding(4.dp),
                                ) {
                                    Surface(
                                        modifier = Modifier
                                            .weight(1f)
                                            .fillMaxHeight()
                                            .clip(RoundedCornerShape(12.dp))
                                            .clickable {
                                                darkTheme = true
                                                store.themeMode = "dark"
                                            },
                                        shape = RoundedCornerShape(12.dp),
                                        color = if (darkTheme) palette.pillActive else Color.Transparent,
                                    ) {
                                        Box(contentAlignment = Alignment.Center) {
                                            Text(t("theme_dark"), color = palette.text, fontSize = 12.5.sp, fontWeight = FontWeight.SemiBold)
                                        }
                                    }
                                    Surface(
                                        modifier = Modifier
                                            .weight(1f)
                                            .fillMaxHeight()
                                            .clip(RoundedCornerShape(12.dp))
                                            .clickable {
                                                darkTheme = false
                                                store.themeMode = "light"
                                            },
                                        shape = RoundedCornerShape(12.dp),
                                        color = if (!darkTheme) palette.pillActive else Color.Transparent,
                                    ) {
                                        Box(contentAlignment = Alignment.Center) {
                                            Text(t("theme_light"), color = palette.text, fontSize = 12.5.sp, fontWeight = FontWeight.SemiBold)
                                        }
                                    }
                                }
                            }

                            Text(
                                text = t("footer_credit"),
                                color = palette.subtext,
                                fontSize = 10.5.sp,
                                textAlign = TextAlign.Center,
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                    }
                },
            ) {
                Scaffold(
                    snackbarHost = { SnackbarHost(snackbar) },
                    containerColor = palette.bg,
                ) { padding ->
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(palette.bg)
                            .statusBarsPadding()
                            .navigationBarsPadding()
                            .padding(padding)
                            .padding(horizontal = 18.dp, vertical = 14.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        OriginalHeader(
                            deviceName = devName,
                            serverRunning = serverRunning,
                            wifiOnline = wifiIp != null,
                            wifiLabel = if (wifiIp != null) t("wifi_online") else t("no_wifi"),
                            palette = palette,
                            onWifiClick = {
                                wifiIp = store.getWifiIp()
                                if (wifiIp == null) showWifiModal = true
                            },
                        )

                        if (!hasFullPerm) {
                            Surface(
                                shape = RoundedCornerShape(14.dp),
                                color = palette.amber.copy(alpha = 0.16f),
                                border = BorderStroke(1.dp, palette.amber.copy(alpha = 0.45f)),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { openAllFilesPermissionSettings() },
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Icon(Icons.Default.Warning, contentDescription = null, tint = palette.amber, modifier = Modifier.size(18.dp))
                                    Spacer(Modifier.width(8.dp))
                                    Text(t("perm_needed"), color = palette.text, fontSize = 11.5.sp, modifier = Modifier.weight(1f))
                                    Spacer(Modifier.width(6.dp))
                                    Text(t("perm_grant"), color = palette.amber, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                }
                            }
                        }

                        RadarHeroCard(
                            modifier = Modifier.weight(0.50f),
                            palette = palette,
                            serverRunning = serverRunning,
                            buttonLabel = if (serverRunning) t("disconnect") else t("connect"),
                            addressText = if (serverRunning && serverUrl.isNotBlank()) serverUrl else t("tap_to_start_port", "port" to currentPort),
                            httpWarnText = t("http_warn"),
                            onToggleServer = {
                                wifiIp = store.getWifiIp()
                                if (!serverRunning && wifiIp == null) {
                                    showWifiModal = true
                                } else if (serverRunning) {
                                    AirShareForegroundService.stop(this@MainActivity)
                                } else {
                                    AirShareForegroundService.start(this@MainActivity)
                                }
                            },
                            onCopyAddress = {
                                if (serverRunning && serverUrl.isNotBlank()) {
                                    copyToClipboard("AirShare URL", serverUrl, t("copied_clipboard"))
                                }
                            },
                        )

                        Text(
                            text = t("recent_transfers"),
                            color = palette.text,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                        )

                        RecentTransfersCard(
                            modifier = Modifier.weight(0.32f),
                            palette = palette,
                            progress = transferProgress,
                            history = history,
                            noActiveText = t("no_active_transfers"),
                            waitingText = t("waiting_pc"),
                            onClick = { showTransfersModal = true },
                        )

                        OriginalBottomNav(
                            palette = palette,
                            transferLabel = t("nav_transfer"),
                            filesLabel = t("nav_files"),
                            devicesLabel = t("nav_devices"),
                            settingsLabel = t("nav_settings"),
                            onTransfer = { },
                            onFiles = { showFilesModal = true },
                            onDevices = { showDevicesModal = true },
                            onSettings = { scope.launch { drawerState.open() } },
                        )
                    }
                }
            }

            pendingChallenge?.let { ch ->
                AuthChallengeModal(
                    challenge = ch,
                    palette = palette,
                    tr = { k, a -> AppI18n.tr(this@MainActivity, k, lang, *a) },
                    folderName = folderTitle(ch.targetFolderKey),
                    canUseBiometrics = canUseBiometrics(),
                    onBiometricClick = { trusted -> launchBiometricPrompt(ch, lang, trusted) },
                    onPairClick = { code, trusted ->
                        val (ok, status) = SecurityManager.resolveChallenge(
                            cid = ch.id,
                            selectedPair = code,
                            approve = true,
                            trusted = trusted,
                        )
                        AppState.setPendingChallenge(null)
                        if (!ok && status == "mismatch") SecurityManager.registerAuthFailure(ch.ip)
                        AppState.bumpDevices()
                    },
                    onDirectApprove = { trusted ->
                        SecurityManager.resolveChallenge(cid = ch.id, approve = true, trusted = trusted, biometricOk = true)
                        AppState.setPendingChallenge(null)
                        AppState.bumpDevices()
                    },
                    onDeny = {
                        SecurityManager.resolveChallenge(cid = ch.id, approve = false)
                        AppState.setPendingChallenge(null)
                    },
                    onCancel = {
                        SecurityManager.resolveChallenge(cid = ch.id, approve = false, cancelled = true)
                        AppState.setPendingChallenge(null)
                    },
                )
            }

            if (showFilesModal) {
                OriginalModalDialog(
                    palette = palette,
                    title = t("folders_title"),
                    onDismiss = { showFilesModal = false },
                    buttons = { TextButton(onClick = { showFilesModal = false }) { Text(t("close"), color = palette.blue) } },
                ) {
                    Text(t("folders_subtitle"), fontSize = 12.5.sp, color = palette.subtext)
                    listOf(
                        Triple("downloads", t("folder_dl_title"), t("folder_dl_desc")),
                        Triple("camera", t("folder_cam_title"), t("folder_cam_desc")),
                        Triple("documents", t("folder_doc_title"), t("folder_doc_desc")),
                        Triple("all", t("folder_all_title"), t("folder_all_desc")),
                    ).forEach { (key, title, desc) ->
                        val selected = activeFolder == key
                        Surface(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(13.dp))
                                .clickable {
                                    if (key == "all" && activeFolder != "all") {
                                        showFilesModal = false
                                        showAllStorageWarn = true
                                    } else {
                                        store.activeFolderKey = key
                                        AppState.setActiveFolder(key)
                                        showFilesModal = false
                                    }
                                },
                            shape = RoundedCornerShape(13.dp),
                            color = if (selected) palette.pillActive else palette.drawerCard,
                            border = BorderStroke(1.dp, if (selected) palette.green else palette.cardBorder),
                            shadowElevation = if (selected) 6.dp else 2.dp,
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 11.dp, vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(
                                    Icons.Default.Folder,
                                    contentDescription = null,
                                    tint = if (selected) palette.green else palette.subtext,
                                    modifier = Modifier.size(19.dp),
                                )
                                Spacer(Modifier.width(10.dp))
                                Column {
                                    Text(title, color = palette.text, fontWeight = FontWeight.SemiBold, fontSize = 13.5.sp)
                                    Text(desc, color = palette.subtext, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                }
                            }
                        }
                    }
                }
            }

            if (showDevicesModal) {
                val ver = devicesVer; val ips = remember(ver, showDevicesModal) { store.recentIps }
                OriginalModalDialog(
                    palette = palette,
                    title = t("devices_title"),
                    onDismiss = { showDevicesModal = false },
                    buttons = { TextButton(onClick = { showDevicesModal = false }) { Text(t("close"), color = palette.blue) } },
                ) {
                    Text(t("devices_subtitle"), fontSize = 12.5.sp, color = palette.subtext)
                    if (ips.isEmpty()) {
                        Text(t("no_devices_yet"), fontSize = 12.5.sp, color = palette.subtext)
                    } else {
                        ips.forEach { entry -> val cleanIp = entry.substringAfterLast("•").trim()
                            val isTrusted = remember(ver, cleanIp) { SecurityManager.isIpTrusted(cleanIp) }
                            val isDisc = remember(ver, cleanIp) { SecurityManager.isIpDisconnected(cleanIp) }
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = palette.drawerCard,
                                border = BorderStroke(1.dp, palette.cardBorder),
                                shadowElevation = 4.dp,
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Column(Modifier.padding(10.dp)) {
                                    Text(entry, color = palette.text, fontWeight = FontWeight.Bold, fontSize = 13.5.sp)
                                    Spacer(Modifier.height(5.dp))
                                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        FilterChip(
                                            selected = isTrusted,
                                            onClick = {
                                                SecurityManager.setIpTrusted(cleanIp, !isTrusted)
                                                AppState.bumpDevices()
                                            },
                                            label = { Text(if (isTrusted) t("btn_trust") else t("btn_guest"), fontSize = 11.sp) },
                                        )
                                        OutlinedButton(
                                            onClick = {
                                                SecurityManager.setIpDisconnected(cleanIp, !isDisc)
                                                AppState.bumpDevices()
                                            },
                                        ) {
                                            Text(if (isDisc) t("btn_allow_dev") else t("btn_disconnect_dev"), fontSize = 11.sp)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            if (showTransfersModal) {
                OriginalModalDialog(
                    palette = palette,
                    title = t("recent_transfers"),
                    onDismiss = { showTransfersModal = false },
                    buttons = { TextButton(onClick = { showTransfersModal = false }) { Text(t("close"), color = palette.blue) } },
                ) {
                    if (history.isEmpty()) {
                        Text(t("no_transfers_yet"), fontSize = 12.5.sp, color = palette.subtext)
                    } else {
                        history.take(15).forEach { entry ->
                            Text("• $entry", fontSize = 12.sp, color = palette.text)
                        }
                    }
                }
            }

            if (showAutoOffModal) {
                OriginalModalDialog(
                    palette = palette,
                    title = t("menu_auto_off"),
                    compact = true,
                    onDismiss = { showAutoOffModal = false },
                    buttons = { TextButton(onClick = { showAutoOffModal = false }) { Text(t("close"), color = palette.blue) } },
                ) {
                    listOf(0, 15, 30, 60).forEach { mins ->
                        val selected = autoOffMin == mins
                        val label = if (mins == 0) t("auto_off_never") else t("auto_off_min", "m" to mins)
                        Surface(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .clickable {
                                    store.autoOffMinutes = mins
                                    autoOffMin = mins
                                    showAutoOffModal = false
                                },
                            shape = RoundedCornerShape(12.dp),
                            color = if (selected) palette.pillActive else palette.drawerCard,
                            border = BorderStroke(1.dp, if (selected) palette.green else palette.cardBorder),
                        ) {
                            Text(label, color = palette.text, fontSize = 13.5.sp, modifier = Modifier.padding(horizontal = 12.dp, vertical = 9.dp))
                        }
                    }
                }
            }

            if (showLanguageModal) {
                OriginalModalDialog(
                    palette = palette,
                    title = t("lang_title"),
                    compact = true,
                    onDismiss = { showLanguageModal = false },
                    buttons = { TextButton(onClick = { showLanguageModal = false }) { Text(t("close"), color = palette.blue) } },
                ) {
                    Text(t("lang_subtitle"), fontSize = 12.sp, color = palette.subtext)
                    SettingsStore.SUPPORTED_LANGUAGES.forEach { (code, name) ->
                        val selected = lang == code
                        Surface(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .clickable {
                                    store.language = code
                                    lang = code
                                    showLanguageModal = false
                                },
                            shape = RoundedCornerShape(12.dp),
                            color = if (selected) palette.pillActive else palette.drawerCard,
                            border = BorderStroke(1.dp, if (selected) palette.green else palette.cardBorder),
                            shadowElevation = if (selected) 4.dp else 1.dp,
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Text(langFlag(code), fontSize = 16.sp)
                                Spacer(Modifier.width(10.dp))
                                Text(
                                    text = name,
                                    color = palette.text,
                                    fontSize = 13.5.sp,
                                    fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                                )
                            }
                        }
                    }
                }
            }

            if (showSecurityModal) {
                var pinInput by remember { mutableStateOf(currentPin) }
                OriginalModalDialog(
                    palette = palette,
                    title = t("pin_title"),
                    compact = true,
                    onDismiss = { showSecurityModal = false },
                    buttons = {
                        TextButton(onClick = { showSecurityModal = false }) { Text(t("cancel"), color = palette.subtext) }
                        Button(
                            onClick = {
                                if (!store.isWeakPin(pinInput)) {
                                    store.password = pinInput.trim()
                                    currentPin = store.password
                                }
                                showSecurityModal = false
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = palette.green, contentColor = Color.White),
                        ) { Text(t("pin_save")) }
                    },
                ) {
                    Text(t("pin_subtitle"), fontSize = 12.5.sp, color = palette.subtext)
                    OutlinedTextField(
                        value = pinInput,
                        onValueChange = { pinInput = it.filter(Char::isDigit).take(12) },
                        singleLine = true,
                        label = { Text(t("pin_new")) },
                    )
                    TextButton(onClick = {
                        val fresh = store.generatePin()
                        pinInput = fresh
                        store.password = fresh
                        currentPin = fresh
                        copyToClipboard("AirShare PIN", fresh, t("copied_clipboard"))
                    }) {
                        Text(t("copy_url").replace("URL", "PIN"), color = palette.blue)
                    }
                }
            }

            if (showPortModal) {
                var portInput by remember { mutableStateOf(currentPort.toString()) }
                OriginalModalDialog(
                    palette = palette,
                    title = t("port_title"),
                    compact = true,
                    onDismiss = { showPortModal = false },
                    buttons = {
                        TextButton(onClick = { showPortModal = false }) { Text(t("cancel"), color = palette.subtext) }
                        Button(
                            onClick = {
                                val p = portInput.toIntOrNull()
                                if (p != null && p in 1024..65535) {
                                    store.port = p
                                    currentPort = p
                                }
                                showPortModal = false
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = palette.green, contentColor = Color.White),
                        ) { Text(t("port_save")) }
                    },
                ) {
                    Text(t("port_subtitle"), fontSize = 12.5.sp, color = palette.subtext)
                    OutlinedTextField(
                        value = portInput,
                        onValueChange = { portInput = it.filter(Char::isDigit).take(5) },
                        singleLine = true,
                    )
                }
            }

            if (showAllStorageWarn) {
                OriginalModalDialog(
                    palette = palette,
                    title = t("all_storage_warn_title"),
                    compact = true,
                    onDismiss = { showAllStorageWarn = false },
                    buttons = {
                        TextButton(onClick = { showAllStorageWarn = false }) { Text(t("cancel"), color = palette.subtext) }
                        Button(
                            onClick = {
                                store.activeFolderKey = "all"
                                AppState.setActiveFolder("all")
                                showAllStorageWarn = false
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = palette.green, contentColor = Color.White),
                        ) { Text(t("confirm_allow")) }
                    },
                ) {
                    Text(t("all_storage_warn_body"), fontSize = 12.5.sp, color = palette.subtext)
                }
            }

            if (showWifiModal) {
                OriginalModalDialog(
                    palette = palette,
                    title = t("no_wifi_title"),
                    compact = true,
                    onDismiss = { showWifiModal = false },
                    buttons = { TextButton(onClick = { showWifiModal = false }) { Text(t("ok_understand"), color = palette.blue) } },
                ) {
                    Text(t("no_wifi_body"), fontSize = 12.5.sp, color = palette.subtext)
                }
            }

            if (showHelpModal) {
                OriginalModalDialog(
                    palette = palette,
                    title = t("help_title"),
                    onDismiss = { showHelpModal = false },
                    buttons = { TextButton(onClick = { showHelpModal = false }) { Text(t("close"), color = palette.blue) } },
                ) {
                    Text(t("help_body"), fontSize = 12.5.sp, color = palette.subtext)
                }
            }
        }
    }
}

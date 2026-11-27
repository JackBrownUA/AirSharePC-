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
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.Key
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
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
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import com.airshare.airshare.server.AuthChallenge
import com.airshare.airshare.server.SecurityManager
import com.airshare.airshare.service.AirShareForegroundService
import com.airshare.airshare.ui.AirShareColors
import com.airshare.airshare.ui.AirShareTheme
import com.airshare.airshare.ui.AuthChallengeModal
import com.airshare.airshare.ui.DrawerNavRow
import com.airshare.airshare.ui.DrawerSectionTitle
import com.airshare.airshare.ui.GlassCard
import com.airshare.airshare.ui.PowerHeroButton
import com.airshare.airshare.ui.StorageCard
import com.airshare.airshare.ui.TransferBanner
import kotlinx.coroutines.launch

class MainActivity : FragmentActivity() {

    private lateinit var store: SettingsStore

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
            .setSubtitle(AppI18n.tr(this, "bio_prompt_sub", lang))
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

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    private fun AirShareRootScreen() {
        var lang by remember { mutableStateOf(store.language) }
        var darkTheme by remember { mutableStateOf(store.themeMode != "light") }
        var currentPin by remember { mutableStateOf(store.password) }
        var currentPort by remember { mutableIntStateOf(store.port) }
        var autoOffMin by remember { mutableIntStateOf(store.autoOffMinutes) }
        var showHelp by remember { mutableStateOf(false) }
        var showDevices by remember { mutableStateOf(false) }
        var showPortDialog by remember { mutableStateOf(false) }
        var showAllStorageWarn by remember { mutableStateOf(false) }

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

        fun t(key: String, vararg args: Pair<String, Any>): String =
            AppI18n.tr(this@MainActivity, key, lang, *args)

        fun folderTitle(key: String): String = when (key) {
            "camera", "Camera Roll" -> t("folder_cam_title")
            "documents", "Documents" -> t("folder_doc_title")
            "all", "All Storage" -> t("folder_all_title")
            else -> t("folder_dl_title")
        }

        LaunchedEffect(toastEvent?.id) {
            val ev = toastEvent ?: return@LaunchedEffect
            snackbar.showSnackbar(ev.message)
            AppState.clearToast()
        }

        val storageStats = remember(serverRunning, history.size) { store.getStorageStats() }
        val hasFullPerm = store.hasFullStoragePermission()

        AirShareTheme(darkTheme = darkTheme) {
            ModalNavigationDrawer(
                drawerState = drawerState,
                drawerContent = {
                    ModalDrawerSheet(
                        modifier = Modifier
                            .width(305.dp)
                            .fillMaxHeight(),
                        drawerContainerColor = MaterialTheme.colorScheme.surface,
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .verticalScroll(rememberScrollState())
                                .padding(horizontal = 16.dp, vertical = 20.dp),
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Image(
                                    painter = painterResource(id = R.drawable.app_logo),
                                    contentDescription = "AirShare PC",
                                    modifier = Modifier
                                        .size(42.dp)
                                        .clip(RoundedCornerShape(11.dp)),
                                )
                                Spacer(Modifier.width(12.dp))
                                Column {
                                    Text("AirShare PC", fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
                                    Text(t("version_label"), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }

                            DrawerSectionTitle(t("folders_title"))
                            listOf(
                                Triple("downloads", t("folder_dl_title"), t("folder_dl_desc")),
                                Triple("camera", t("folder_cam_title"), t("folder_cam_desc")),
                                Triple("documents", t("folder_doc_title"), t("folder_doc_desc")),
                                Triple("all", t("folder_all_title"), t("folder_all_desc")),
                            ).forEach { (key, title, desc) ->
                                DrawerNavRow(
                                    icon = Icons.Default.Folder,
                                    title = title,
                                    subtitle = desc,
                                    selected = activeFolder == key,
                                    onClick = {
                                        if (key == "all" && activeFolder != "all") {
                                            showAllStorageWarn = true
                                        } else {
                                            store.activeFolderKey = key
                                            AppState.setActiveFolder(key)
                                        }
                                        scope.launch { drawerState.close() }
                                    },
                                )
                            }

                            DrawerSectionTitle(t("devices_title"))
                            DrawerNavRow(
                                icon = Icons.Default.Devices,
                                title = t("devices_title"),
                                subtitle = "${store.recentIps.size} IP",
                                onClick = {
                                    showDevices = true
                                    scope.launch { drawerState.close() }
                                },
                            )

                            DrawerSectionTitle("PIN & Port")
                            DrawerNavRow(
                                icon = Icons.Default.Key,
                                title = "PIN: $currentPin",
                                subtitle = t("pin_hint"),
                                onClick = {
                                    val fresh = store.generatePin()
                                    store.password = fresh
                                    currentPin = fresh
                                    copyToClipboard("AirShare PIN", fresh, t("copied_clipboard"))
                                },
                            )
                            DrawerNavRow(
                                icon = Icons.Default.Refresh,
                                title = "Port: $currentPort",
                                onClick = {
                                    showPortDialog = true
                                    scope.launch { drawerState.close() }
                                },
                            )

                            DrawerSectionTitle(t("auto_off_min").ifBlank { "Auto-off" })
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                            ) {
                                listOf(0, 15, 30, 60).forEach { mins ->
                                    FilterChip(
                                        selected = autoOffMin == mins,
                                        onClick = {
                                            store.autoOffMinutes = mins
                                            autoOffMin = mins
                                        },
                                        label = {
                                            Text(
                                                text = if (mins == 0) t("auto_off_never") else "${mins}m",
                                                fontSize = 11.sp,
                                            )
                                        },
                                    )
                                }
                            }

                            DrawerSectionTitle("Language")
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                            ) {
                                SettingsStore.SUPPORTED_LANGUAGES.take(3).forEach { (code, _) ->
                                    FilterChip(
                                        selected = lang == code,
                                        onClick = {
                                            store.language = code
                                            lang = code
                                        },
                                        label = { Text(code.uppercase(), fontSize = 11.sp) },
                                    )
                                }
                            }
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                            ) {
                                SettingsStore.SUPPORTED_LANGUAGES.drop(3).forEach { (code, _) ->
                                    FilterChip(
                                        selected = lang == code,
                                        onClick = {
                                            store.language = code
                                            lang = code
                                        },
                                        label = { Text(code.uppercase(), fontSize = 11.sp) },
                                    )
                                }
                            }

                            Spacer(Modifier.weight(1f))
                            Spacer(Modifier.height(18.dp))
                            Text(
                                text = t("footer_credit"),
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                textAlign = TextAlign.Center,
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                    }
                },
            ) {
                Scaffold(
                    snackbarHost = { SnackbarHost(snackbar) },
                    containerColor = MaterialTheme.colorScheme.background,
                    topBar = {
                        TopAppBar(
                            title = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text("AirShare PC", fontWeight = FontWeight.ExtraBold, fontSize = 19.sp)
                                    Spacer(Modifier.width(8.dp))
                                    Surface(
                                        shape = RoundedCornerShape(99.dp),
                                        color = AirShareColors.Accent.copy(alpha = 0.16f),
                                    ) {
                                        Text(
                                            text = t("version_label"),
                                            fontSize = 11.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = AirShareColors.Accent,
                                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                                        )
                                    }
                                }
                            },
                            navigationIcon = {
                                IconButton(onClick = { scope.launch { drawerState.open() } }) {
                                    Icon(Icons.Default.Menu, contentDescription = "Menu")
                                }
                            },
                            actions = {
                                IconButton(onClick = {
                                    darkTheme = !darkTheme
                                    store.themeMode = if (darkTheme) "dark" else "light"
                                }) {
                                    Icon(
                                        imageVector = if (darkTheme) Icons.Default.LightMode else Icons.Default.DarkMode,
                                        contentDescription = "Theme",
                                    )
                                }
                                IconButton(onClick = { showHelp = true }) {
                                    Icon(Icons.Default.HelpOutline, contentDescription = "Help")
                                }
                            },
                            colors = TopAppBarDefaults.topAppBarColors(
                                containerColor = MaterialTheme.colorScheme.background,
                            ),
                        )
                    },
                ) { padding ->
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding)
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = 18.dp, vertical = 10.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp),
                    ) {
                        if (!hasFullPerm) {
                            Surface(
                                shape = RoundedCornerShape(16.dp),
                                color = AirShareColors.Amber.copy(alpha = 0.16f),
                                border = BorderStroke(1.dp, AirShareColors.Amber.copy(alpha = 0.45f)),
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Row(
                                    modifier = Modifier.padding(14.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Icon(Icons.Default.Warning, contentDescription = null, tint = AirShareColors.Amber)
                                    Spacer(Modifier.width(10.dp))
                                    Text(
                                        text = t("perm_needed"),
                                        fontSize = 12.sp,
                                        modifier = Modifier.weight(1f),
                                    )
                                    TextButton(onClick = { openAllFilesPermissionSettings() }) {
                                        Text(t("perm_grant"), fontWeight = FontWeight.Bold)
                                    }
                                }
                            }
                        }

                        GlassCard {
                            Column(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalAlignment = Alignment.CenterHorizontally,
                            ) {
                                PowerHeroButton(
                                    running = serverRunning,
                                    label = if (serverRunning) t("disconnect") else t("connect"),
                                    onClick = {
                                        if (serverRunning) {
                                            AirShareForegroundService.stop(this@MainActivity)
                                        } else {
                                            AirShareForegroundService.start(this@MainActivity)
                                        }
                                    },
                                )

                                Spacer(Modifier.height(14.dp))

                                if (serverRunning && serverUrl.isNotBlank()) {
                                    Surface(
                                        shape = RoundedCornerShape(12.dp),
                                        color = AirShareColors.Accent.copy(alpha = 0.14f),
                                        border = BorderStroke(1.dp, AirShareColors.Accent.copy(alpha = 0.35f)),
                                        modifier = Modifier.fillMaxWidth(),
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                        ) {
                                            Text(
                                                text = serverUrl,
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 15.sp,
                                                color = AirShareColors.Accent,
                                            )
                                            IconButton(
                                                onClick = { copyToClipboard("AirShare URL", serverUrl, t("copied_clipboard")) },
                                                modifier = Modifier.size(32.dp),
                                            ) {
                                                Icon(Icons.Default.ContentCopy, contentDescription = t("copy_url"), tint = AirShareColors.Accent)
                                            }
                                        }
                                    }
                                    Spacer(Modifier.height(8.dp))
                                    Text(
                                        text = "PIN: $currentPin • ${folderTitle(activeFolder)}",
                                        fontSize = 12.sp,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    Spacer(Modifier.height(4.dp))
                                    Text(
                                        text = t("http_warn"),
                                        fontSize = 11.sp,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        textAlign = TextAlign.Center,
                                    )
                                } else {
                                    Text(
                                        text = "${folderTitle(activeFolder)} • Port $currentPort",
                                        fontSize = 13.sp,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }

                        TransferBanner(progress = transferProgress)

                        StorageCard(
                            title = store.getDeviceName(),
                            stats = storageStats,
                        )

                        if (history.isNotEmpty()) {
                            GlassCard {
                                Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text(
                                        text = t("web_tab_recent"),
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 14.sp,
                                    )
                                    history.take(8).forEach { entry ->
                                        Text(
                                            text = entry,
                                            fontSize = 12.sp,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                            }
                        }

                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = t("footer_credit"),
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }

            pendingChallenge?.let { ch ->
                AuthChallengeModal(
                    challenge = ch,
                    tr = { k, a -> AppI18n.tr(this@MainActivity, k, lang, *a) },
                    folderName = folderTitle(ch.targetFolderKey),
                    canUseBiometrics = canUseBiometrics(),
                    onBiometricClick = { trusted ->
                        launchBiometricPrompt(ch, lang, trusted)
                    },
                    onPairClick = { code, trusted ->
                        val (ok, status) = SecurityManager.resolveChallenge(
                            cid = ch.id,
                            selectedPair = code,
                            approve = true,
                            trusted = trusted,
                        )
                        AppState.setPendingChallenge(null)
                        if (!ok && status == "mismatch") {
                            SecurityManager.registerAuthFailure(ch.ip)
                        }
                        AppState.bumpDevices()
                    },
                    onDirectApprove = { trusted ->
                        SecurityManager.resolveChallenge(
                            cid = ch.id,
                            approve = true,
                            trusted = trusted,
                            biometricOk = true,
                        )
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

            if (showDevices) {
                val ips = remember(devicesVer, showDevices) { store.recentIps }
                AlertDialog(
                    onDismissRequest = { showDevices = false },
                    title = { Text(t("devices_title"), fontWeight = FontWeight.Bold) },
                    text = {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(t("devices_subtitle"), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            if (ips.isEmpty()) {
                                Text("—", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            } else {
                                ips.forEach { ip ->
                                    val isTrusted = SecurityManager.isIpTrusted(ip)
                                    val isDisc = SecurityManager.isIpDisconnected(ip)
                                    Surface(
                                        shape = RoundedCornerShape(12.dp),
                                        color = MaterialTheme.colorScheme.surfaceVariant,
                                        modifier = Modifier.fillMaxWidth(),
                                    ) {
                                        Column(Modifier.padding(10.dp)) {
                                            Text(ip, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                                            Spacer(Modifier.height(6.dp))
                                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                                FilterChip(
                                                    selected = isTrusted,
                                                    onClick = {
                                                        SecurityManager.setIpTrusted(ip, !isTrusted)
                                                        AppState.bumpDevices()
                                                    },
                                                    label = { Text(if (isTrusted) t("btn_trust") else t("btn_guest"), fontSize = 11.sp) },
                                                )
                                                OutlinedButton(
                                                    onClick = {
                                                        SecurityManager.setIpDisconnected(ip, !isDisc)
                                                        AppState.bumpDevices()
                                                    },
                                                ) {
                                                    Text(
                                                        text = if (isDisc) t("btn_allow_dev") else t("btn_disconnect_dev"),
                                                        fontSize = 11.sp,
                                                    )
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    confirmButton = {
                        TextButton(onClick = { showDevices = false }) { Text(t("close")) }
                    },
                )
            }

            if (showPortDialog) {
                var portInput by remember { mutableStateOf(currentPort.toString()) }
                AlertDialog(
                    onDismissRequest = { showPortDialog = false },
                    title = { Text("HTTP Port") },
                    text = {
                        OutlinedTextField(
                            value = portInput,
                            onValueChange = { portInput = it.filter(Char::isDigit).take(5) },
                            singleLine = true,
                        )
                    },
                    confirmButton = {
                        Button(onClick = {
                            val p = portInput.toIntOrNull()
                            if (p != null && p in 1024..65535) {
                                store.port = p
                                currentPort = p
                            }
                            showPortDialog = false
                        }) { Text("OK") }
                    },
                    dismissButton = {
                        TextButton(onClick = { showPortDialog = false }) { Text(t("cancel")) }
                    },
                )
            }

            if (showAllStorageWarn) {
                AlertDialog(
                    onDismissRequest = { showAllStorageWarn = false },
                    title = { Text(t("all_storage_warn_title"), fontWeight = FontWeight.Bold) },
                    text = { Text(t("all_storage_warn_body"), fontSize = 13.sp) },
                    confirmButton = {
                        Button(onClick = {
                            store.activeFolderKey = "all"
                            AppState.setActiveFolder("all")
                            showAllStorageWarn = false
                        }) { Text(t("confirm_allow")) }
                    },
                    dismissButton = {
                        TextButton(onClick = { showAllStorageWarn = false }) { Text(t("cancel")) }
                    },
                )
            }

            if (showHelp) {
                AlertDialog(
                    onDismissRequest = { showHelp = false },
                    title = { Text(t("help_title"), fontWeight = FontWeight.Bold) },
                    text = { Text(t("help_body"), fontSize = 13.sp) },
                    confirmButton = {
                        TextButton(onClick = { showHelp = false }) { Text(t("close")) }
                    },
                )
            }
        }
    }
}

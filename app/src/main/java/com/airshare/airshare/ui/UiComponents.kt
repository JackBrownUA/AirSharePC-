package com.airshare.airshare.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SwapVert
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.airshare.airshare.SettingsStore
import com.airshare.airshare.TransferProgress
import com.airshare.airshare.server.AuthChallenge

@Composable
fun OriginalHeader(
    deviceName: String,
    serverRunning: Boolean,
    wifiOnline: Boolean,
    wifiLabel: String,
    palette: AirSharePalette,
    onWifiClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(44.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Row(
            modifier = Modifier.weight(1f),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(14.dp)
                    .clip(CircleShape)
                    .background(if (serverRunning) palette.green else palette.red),
            )
            Spacer(Modifier.width(10.dp))
            Text(
                text = deviceName,
                color = palette.text,
                fontSize = if (deviceName.length <= 14) 20.sp else 17.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Spacer(Modifier.width(8.dp))
        Surface(
            modifier = Modifier
                .height(34.dp)
                .clip(RoundedCornerShape(17.dp))
                .clickable { onWifiClick() },
            shape = RoundedCornerShape(17.dp),
            color = palette.pillBg,
            border = BorderStroke(1.dp, palette.cardBorder),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    imageVector = if (wifiOnline) Icons.Default.Wifi else Icons.Default.WifiOff,
                    contentDescription = null,
                    tint = if (wifiOnline) palette.green else palette.red,
                    modifier = Modifier.size(16.dp),
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    text = wifiLabel,
                    color = palette.text,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                )
            }
        }
    }
}

@Composable
fun RadarHeroCard(
    modifier: Modifier = Modifier,
    palette: AirSharePalette,
    serverRunning: Boolean,
    buttonLabel: String,
    addressText: String,
    httpWarnText: String,
    onToggleServer: () -> Unit,
    onCopyAddress: () -> Unit,
) {
    val transition = rememberInfiniteTransition(label = "radar")
    val pulse by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 2800, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "pulse",
    )

    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        color = palette.radarBg,
        border = BorderStroke(1.dp, palette.cardBorder),
    ) {
        Box(modifier = Modifier.fillMaxSize()) {
            Canvas(modifier = Modifier.fillMaxSize()) {
                val center = Offset(size.width / 2f, size.height * 0.28f)
                val maxR = size.minDimension * 0.44f
                if (serverRunning) {
                    for (i in 0..2) {
                        val phase = (pulse + i / 3f) % 1f
                        val r = maxR * (0.28f + 0.72f * phase)
                        val alpha = (1f - phase) * 0.35f
                        drawCircle(
                            color = palette.green.copy(alpha = alpha),
                            radius = r,
                            center = center,
                            style = Stroke(width = 2.dp.toPx()),
                        )
                    }
                } else {
                    for (f in listOf(0.45f, 0.72f, 0.98f)) {
                        drawCircle(
                            color = palette.radarRing,
                            radius = maxR * f,
                            center = center,
                            style = Stroke(width = 1.2.dp.toPx()),
                        )
                    }
                }
                drawCircle(
                    color = palette.radarGlow,
                    radius = maxR * 0.42f,
                    center = center,
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp, vertical = 16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                Box(
                    modifier = Modifier
                        .weight(0.40f)
                        .fillMaxWidth(),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = Icons.Default.Computer,
                        contentDescription = "PC",
                        tint = if (serverRunning) palette.green else palette.text,
                        modifier = Modifier.size(56.dp),
                    )
                }

                Box(
                    modifier = Modifier
                        .weight(0.26f)
                        .fillMaxWidth(),
                    contentAlignment = Alignment.Center,
                ) {
                    Button(
                        onClick = onToggleServer,
                        shape = RoundedCornerShape(23.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (serverRunning) palette.red else palette.green,
                            contentColor = Color.White,
                        ),
                        border = BorderStroke(1.dp, Color.White.copy(alpha = 0.18f)),
                        modifier = Modifier
                            .width(204.dp)
                            .height(46.dp),
                    ) {
                        Text(
                            text = buttonLabel,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }

                Row(
                    modifier = Modifier
                        .weight(0.22f)
                        .fillMaxWidth(0.96f),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Surface(
                        modifier = Modifier
                            .weight(1f)
                            .height(38.dp)
                            .clip(RoundedCornerShape(16.dp))
                            .clickable { onCopyAddress() },
                        shape = RoundedCornerShape(16.dp),
                        color = palette.pillBg,
                        border = BorderStroke(1.dp, palette.cardBorder),
                    ) {
                        Box(
                            modifier = Modifier.padding(horizontal = 12.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                text = addressText,
                                color = if (serverRunning) palette.blue else palette.subtext,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Medium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }

                    Surface(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .clickable { onCopyAddress() },
                        shape = RoundedCornerShape(14.dp),
                        color = palette.pillBg,
                        border = BorderStroke(1.dp, palette.cardBorder),
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = Icons.Default.ContentCopy,
                                contentDescription = "Copy",
                                tint = palette.text,
                                modifier = Modifier.size(18.dp),
                            )
                        }
                    }
                }

                Text(
                    text = httpWarnText,
                    color = palette.subtext,
                    fontSize = 10.5.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
fun RecentTransfersCard(
    modifier: Modifier = Modifier,
    palette: AirSharePalette,
    progress: TransferProgress,
    history: List<String>,
    noActiveText: String,
    waitingText: String,
    onClick: () -> Unit,
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .clickable { onClick() },
        shape = RoundedCornerShape(18.dp),
        color = palette.cardBg,
        border = BorderStroke(1.dp, palette.cardBorder),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.SpaceEvenly,
        ) {
            val row1Title = when {
                progress.active -> progress.filename
                history.isNotEmpty() -> history[0]
                else -> noActiveText
            }
            val row1Ratio = when {
                progress.active && progress.totalBytes > 0L ->
                    (progress.transferredBytes.toFloat() / progress.totalBytes.toFloat()).coerceIn(0f, 1f)
                history.isNotEmpty() -> 1f
                else -> 0f
            }
            val row1Pct = when {
                progress.active -> "${(row1Ratio * 100).toInt()}%"
                history.isNotEmpty() -> "100%"
                else -> "—"
            }
            val row1Sub = when {
                progress.active -> "${SettingsStore.formatSize(progress.transferredBytes)} / ${SettingsStore.formatSize(progress.totalBytes)}"
                history.isNotEmpty() -> history[0]
                else -> waitingText
            }

            TransferBadgeRow(
                badgeText = if (progress.active && progress.direction == "upload") "UP" else "ZIP",
                badgeColor = palette.amber,
                title = row1Title,
                pctText = row1Pct,
                subText = row1Sub,
                ratio = row1Ratio,
                palette = palette,
            )

            if (history.size > 1) {
                val second = history[1]
                TransferBadgeRow(
                    badgeText = "FILE",
                    badgeColor = palette.blue,
                    title = second,
                    pctText = "100%",
                    subText = second,
                    ratio = 1f,
                    palette = palette,
                )
            }
        }
    }
}

@Composable
private fun TransferBadgeRow(
    badgeText: String,
    badgeColor: Color,
    title: String,
    pctText: String,
    subText: String,
    ratio: Float,
    palette: AirSharePalette,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            modifier = Modifier.size(40.dp),
            shape = RoundedCornerShape(11.dp),
            color = badgeColor.copy(alpha = 0.18f),
            border = BorderStroke(1.dp, badgeColor.copy(alpha = 0.45f)),
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = badgeText,
                    color = badgeColor,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.ExtraBold,
                )
            }
        }
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = title,
                    color = palette.text,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = pctText,
                    color = palette.subtext,
                    fontSize = 12.sp,
                )
            }
            Spacer(Modifier.height(5.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(4.dp)
                    .clip(RoundedCornerShape(99.dp))
                    .background(palette.track),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(ratio.coerceIn(0f, 1f))
                        .fillMaxHeight()
                        .clip(RoundedCornerShape(99.dp))
                        .background(badgeColor),
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(
                text = subText,
                color = palette.subtext,
                fontSize = 11.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
fun OriginalBottomNav(
    palette: AirSharePalette,
    transferLabel: String,
    filesLabel: String,
    devicesLabel: String,
    settingsLabel: String,
    onTransfer: () -> Unit,
    onFiles: () -> Unit,
    onDevices: () -> Unit,
    onSettings: () -> Unit,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .height(64.dp),
        shape = RoundedCornerShape(26.dp),
        color = palette.cardBg,
        border = BorderStroke(1.dp, palette.cardBorder),
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 8.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            NavTabPill(
                icon = Icons.Default.SwapVert,
                label = transferLabel,
                active = true,
                palette = palette,
                modifier = Modifier.weight(1f),
                onClick = onTransfer,
            )
            NavTabPill(
                icon = Icons.Default.Folder,
                label = filesLabel,
                active = false,
                palette = palette,
                modifier = Modifier.weight(1f),
                onClick = onFiles,
            )
            NavTabPill(
                icon = Icons.Default.Devices,
                label = devicesLabel,
                active = false,
                palette = palette,
                modifier = Modifier.weight(1f),
                onClick = onDevices,
            )
            NavTabPill(
                icon = Icons.Default.Settings,
                label = settingsLabel,
                active = false,
                palette = palette,
                modifier = Modifier.weight(1f),
                onClick = onSettings,
            )
        }
    }
}

@Composable
private fun NavTabPill(
    icon: ImageVector,
    label: String,
    active: Boolean,
    palette: AirSharePalette,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Surface(
        modifier = modifier
            .fillMaxHeight()
            .clip(RoundedCornerShape(20.dp))
            .clickable { onClick() },
        shape = RoundedCornerShape(20.dp),
        color = if (active) palette.pillActive else Color.Transparent,
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Icon(
                imageVector = icon,
                contentDescription = label,
                tint = if (active) palette.text else palette.subtext,
                modifier = Modifier.size(20.dp),
            )
            Spacer(Modifier.height(2.dp))
            Text(
                text = label,
                color = if (active) palette.text else palette.subtext,
                fontSize = 10.5.sp,
                fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
fun DrawerMenuRowItem(
    icon: ImageVector,
    label: String,
    palette: AirSharePalette,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(44.dp)
            .clip(RoundedCornerShape(12.dp))
            .clickable { onClick() }
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = palette.subtext,
            modifier = Modifier.size(20.dp),
        )
        Spacer(Modifier.width(14.dp))
        Text(
            text = label,
            color = palette.text,
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
fun OriginalModalDialog(
    palette: AirSharePalette,
    title: String,
    onDismiss: () -> Unit,
    buttons: @Composable () -> Unit,
    content: @Composable ColumnScope.() -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = palette.modalBg,
        titleContentColor = palette.text,
        textContentColor = palette.subtext,
        title = { Text(title, fontWeight = FontWeight.Bold, fontSize = 18.sp) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(10.dp), content = content) },
        confirmButton = buttons,
    )
}

@Composable
fun AuthChallengeModal(
    challenge: AuthChallenge,
    palette: AirSharePalette,
    tr: (String, Array<out Pair<String, Any>>) -> String,
    folderName: String,
    canUseBiometrics: Boolean,
    onBiometricClick: (trusted: Boolean) -> Unit,
    onPairClick: (pair: String, trusted: Boolean) -> Unit,
    onDirectApprove: (trusted: Boolean) -> Unit,
    onDeny: () -> Unit,
    onCancel: () -> Unit,
) {
    var trustedChoice by remember(challenge.id) { mutableStateOf(true) }
    val isAccessChange = challenge.action == "access_change"

    AlertDialog(
        onDismissRequest = onCancel,
        containerColor = palette.modalBg,
        titleContentColor = palette.text,
        textContentColor = palette.subtext,
        icon = {
            Icon(
                imageVector = if (isAccessChange) Icons.Default.Folder else Icons.Default.Lock,
                contentDescription = null,
                tint = palette.blue,
                modifier = Modifier.size(32.dp),
            )
        },
        title = {
            Text(
                text = if (isAccessChange) tr("auth_access_title", emptyArray()) else tr("auth_req_title", emptyArray()),
                fontWeight = FontWeight.Bold,
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    text = if (isAccessChange) {
                        tr("auth_access_sub", arrayOf("ip" to challenge.ip, "folder" to folderName))
                    } else {
                        "${challenge.device} (${challenge.ip})\n${tr("auth_req_sub", arrayOf("ip" to challenge.ip))}"
                    },
                    fontSize = 13.sp,
                    color = palette.subtext,
                )

                if (!isAccessChange) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(
                            selected = trustedChoice,
                            onClick = { trustedChoice = true },
                            label = { Text(tr("auth_trust_full", emptyArray()), fontSize = 12.sp) },
                        )
                        FilterChip(
                            selected = !trustedChoice,
                            onClick = { trustedChoice = false },
                            label = { Text(tr("auth_trust_guest", emptyArray()), fontSize = 12.sp) },
                        )
                    }
                }

                if (challenge.mode == "pairs") {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        challenge.pairs.forEach { code ->
                            Button(
                                onClick = { onPairClick(code, trustedChoice) },
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = palette.blue, contentColor = Color.White),
                            ) {
                                Text(code, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
                            }
                        }
                    }
                } else {
                    if (canUseBiometrics) {
                        Button(
                            onClick = { onBiometricClick(trustedChoice) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = palette.green, contentColor = Color.White),
                        ) {
                            Icon(Icons.Default.Fingerprint, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text(tr("auth_btn_bio", emptyArray()))
                        }
                    } else {
                        Text(tr("bio_unavailable", emptyArray()), fontSize = 12.sp, color = palette.amber)
                        Button(
                            onClick = { onDirectApprove(trustedChoice) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = palette.green, contentColor = Color.White),
                        ) {
                            Text(tr("auth_btn_allow", emptyArray()))
                        }
                    }
                }
            }
        },
        confirmButton = {
            OutlinedButton(
                onClick = onDeny,
                colors = ButtonDefaults.outlinedButtonColors(contentColor = palette.red),
            ) {
                Text(tr("auth_deny", emptyArray()))
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel) {
                Text(tr("cancel", emptyArray()))
            }
        },
    )
}

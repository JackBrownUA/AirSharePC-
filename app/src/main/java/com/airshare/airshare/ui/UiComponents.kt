package com.airshare.airshare.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.airshare.airshare.SettingsStore
import com.airshare.airshare.StorageStats
import com.airshare.airshare.TransferProgress
import com.airshare.airshare.server.AuthChallenge
import java.util.Locale

@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    val cardModifier = if (onClick != null) modifier.clickable { onClick() } else modifier
    Card(
        modifier = cardModifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Box(modifier = Modifier.padding(16.dp)) {
            content()
        }
    }
}

@Composable
fun PowerHeroButton(
    running: Boolean,
    label: String,
    onClick: () -> Unit,
) {
    val brush = if (running) {
        Brush.linearGradient(listOf(AirShareColors.Green, Color(0xFF16A34A)))
    } else {
        Brush.linearGradient(listOf(AirShareColors.Accent, AirShareColors.AccentDark))
    }
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            modifier = Modifier
                .size(116.dp)
                .clip(CircleShape)
                .background(brush)
                .clickable { onClick() },
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.Default.PowerSettingsNew,
                contentDescription = label,
                tint = Color.White,
                modifier = Modifier.size(50.dp),
            )
        }
        Spacer(Modifier.height(10.dp))
        Text(
            text = label,
            fontSize = 15.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground,
        )
    }
}

@Composable
fun StorageCard(
    title: String,
    stats: StorageStats,
) {
    GlassCard {
        Column(Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(title, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                Text(
                    text = String.format(Locale.US, "%.1f / %.1f GB", stats.usedGb, stats.totalGb),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 12.sp,
                )
            }
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { stats.percent.coerceIn(0f, 1f) },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(RoundedCornerShape(99.dp)),
                color = if (stats.percent > 0.88f) AirShareColors.Red else AirShareColors.Accent,
                trackColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.25f),
            )
        }
    }
}

@Composable
fun TransferBanner(progress: TransferProgress) {
    if (!progress.active) return
    val ratio = if (progress.totalBytes > 0) {
        (progress.transferredBytes.toFloat() / progress.totalBytes.toFloat()).coerceIn(0f, 1f)
    } else 0f
    GlassCard {
        Column(Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = (if (progress.direction == "upload") "⬇ " else "⬆ ") + progress.filename,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 13.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = "${SettingsStore.formatSize(progress.transferredBytes)} / ${SettingsStore.formatSize(progress.totalBytes)}",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(6.dp))
            LinearProgressIndicator(
                progress = { ratio },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(6.dp)
                    .clip(RoundedCornerShape(99.dp)),
                color = AirShareColors.Green,
            )
        }
    }
}

@Composable
fun DrawerSectionTitle(text: String) {
    Text(
        text = text.uppercase(Locale.ROOT),
        fontSize = 11.sp,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 14.dp, bottom = 6.dp, start = 4.dp),
    )
}

@Composable
fun DrawerNavRow(
    icon: ImageVector,
    title: String,
    subtitle: String? = null,
    selected: Boolean = false,
    onClick: () -> Unit,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp)
            .clip(RoundedCornerShape(12.dp))
            .clickable { onClick() },
        color = if (selected) AirShareColors.Accent.copy(alpha = 0.16f) else Color.Transparent,
        shape = RoundedCornerShape(12.dp),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = if (selected) AirShareColors.Accent else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(20.dp),
            )
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    text = title,
                    fontSize = 14.sp,
                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                    color = if (selected) AirShareColors.Accent else MaterialTheme.colorScheme.onSurface,
                )
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        text = subtitle,
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            if (selected) {
                Icon(
                    imageVector = Icons.Default.CheckCircle,
                    contentDescription = null,
                    tint = AirShareColors.Accent,
                    modifier = Modifier.size(18.dp),
                )
            }
        }
    }
}

@Composable
fun AuthChallengeModal(
    challenge: AuthChallenge,
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
        icon = {
            Icon(
                imageVector = if (isAccessChange) Icons.Default.Folder else Icons.Default.Lock,
                contentDescription = null,
                tint = AirShareColors.Accent,
                modifier = Modifier.size(32.dp),
            )
        },
        title = {
            Text(
                text = if (isAccessChange) {
                    tr("auth_access_title", emptyArray())
                } else {
                    tr("auth_req_title", emptyArray())
                },
                fontWeight = FontWeight.Bold,
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    text = if (isAccessChange) {
                        tr("auth_access_sub", arrayOf("ip" to challenge.ip, "folder" to folderName))
                    } else {
                        "${challenge.device} (${challenge.ip})\n${tr("auth_req_sub", emptyArray())}"
                    },
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
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
                        ) {
                            Icon(Icons.Default.Fingerprint, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text(tr("auth_btn_bio", emptyArray()))
                        }
                    } else {
                        Text(
                            text = tr("bio_unavailable", emptyArray()),
                            fontSize = 12.sp,
                            color = AirShareColors.Amber,
                        )
                        Button(
                            onClick = { onDirectApprove(trustedChoice) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
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
                colors = ButtonDefaults.outlinedButtonColors(contentColor = AirShareColors.Red),
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

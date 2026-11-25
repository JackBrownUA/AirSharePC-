package com.airshare.airshare.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

object AirShareColors {
    val DarkBg = Color(0xFF080D1A)
    val DarkSurface = Color(0xFF111A2E)
    val DarkCard = Color(0xFF16223C)
    val DarkBorder = Color(0xFF243456)
    val DarkText = Color(0xFFF1F5F9)
    val DarkMuted = Color(0xFF94A3B8)

    val LightBg = Color(0xFFEFF6FF)
    val LightSurface = Color(0xFFFFFFFF)
    val LightCard = Color(0xFFFFFFFF)
    val LightBorder = Color(0xFFCBD5E1)
    val LightText = Color(0xFF0F172A)
    val LightMuted = Color(0xFF475569)

    val Accent = Color(0xFF3B82F6)
    val AccentDark = Color(0xFF2563EB)
    val Green = Color(0xFF22C55E)
    val Amber = Color(0xFFF59E0B)
    val Red = Color(0xFFEF4444)
    val Purple = Color(0xFF8B5CF6)
}

private val DarkColors = darkColorScheme(
    primary = AirShareColors.Accent,
    onPrimary = Color.White,
    secondary = AirShareColors.Purple,
    background = AirShareColors.DarkBg,
    onBackground = AirShareColors.DarkText,
    surface = AirShareColors.DarkSurface,
    onSurface = AirShareColors.DarkText,
    surfaceVariant = AirShareColors.DarkCard,
    onSurfaceVariant = AirShareColors.DarkMuted,
    outline = AirShareColors.DarkBorder,
    error = AirShareColors.Red,
)

private val LightColors = lightColorScheme(
    primary = AirShareColors.AccentDark,
    onPrimary = Color.White,
    secondary = AirShareColors.Purple,
    background = AirShareColors.LightBg,
    onBackground = AirShareColors.LightText,
    surface = AirShareColors.LightSurface,
    onSurface = AirShareColors.LightText,
    surfaceVariant = AirShareColors.LightCard,
    onSurfaceVariant = AirShareColors.LightMuted,
    outline = AirShareColors.LightBorder,
    error = AirShareColors.Red,
)

@Composable
fun AirShareTheme(
    darkTheme: Boolean,
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}

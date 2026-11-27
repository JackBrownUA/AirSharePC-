package com.airshare.airshare.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

data class AirSharePalette(
    val bg: Color,
    val radarBg: Color,
    val radarGlow: Color,
    val radarRing: Color,
    val cardBg: Color,
    val cardBorder: Color,
    val drawerBg: Color,
    val drawerCard: Color,
    val drawerBorder: Color,
    val modalBg: Color,
    val text: Color,
    val subtext: Color,
    val pillBg: Color,
    val pillActive: Color,
    val amber: Color,
    val blue: Color,
    val green: Color,
    val red: Color,
    val yellow: Color,
    val track: Color,
)

object AirSharePalettes {
    val Dark = AirSharePalette(
        bg = Color(0xFF181A1D),
        radarBg = Color(0xFF2E3136),
        radarGlow = Color(0x2E525C70),
        radarRing = Color(0x38A3B8D6),
        cardBg = Color(0xFF25272C),
        cardBorder = Color(0xD9454A52),
        drawerBg = Color(0xEB262A2F),
        drawerCard = Color(0xC7383D45),
        drawerBorder = Color(0x9E666E7A),
        modalBg = Color(0xF5272B30),
        text = Color(0xFFF5F7FA),
        subtext = Color(0xFF9EA6B3),
        pillBg = Color(0xFF383D45),
        pillActive = Color(0xFF4A525C),
        amber = Color(0xFFE09C38),
        blue = Color(0xFF61B8FA),
        green = Color(0xFF33C775),
        red = Color(0xFFE0474D),
        yellow = Color(0xFFF5C72E),
        track = Color(0xFF383C42),
    )

    val Light = AirSharePalette(
        bg = Color(0xFFEDEFF5),
        radarBg = Color(0xFFDBE0EA),
        radarGlow = Color(0x59FFFFFF),
        radarRing = Color(0x33526685),
        cardBg = Color(0xFFFCFCFF),
        cardBorder = Color(0xFFCCD1DB),
        drawerBg = Color(0xE6F2F5FA),
        drawerCard = Color(0xD1E3E8F2),
        drawerBorder = Color(0xBFBDC4D1),
        modalBg = Color(0xFAF5F7FC),
        text = Color(0xFF1C1F24),
        subtext = Color(0xFF707887),
        pillBg = Color(0xFFD4D9E3),
        pillActive = Color(0xFFB8C2D1),
        amber = Color(0xFFD68A24),
        blue = Color(0xFF3D9EF0),
        green = Color(0xFF29B86B),
        red = Color(0xFFD63D42),
        yellow = Color(0xFFE6AD1F),
        track = Color(0xFFCCD1DB),
    )
}

private val DarkColors = darkColorScheme(
    primary = AirSharePalettes.Dark.green,
    onPrimary = Color.White,
    secondary = AirSharePalettes.Dark.blue,
    background = AirSharePalettes.Dark.bg,
    onBackground = AirSharePalettes.Dark.text,
    surface = AirSharePalettes.Dark.cardBg,
    onSurface = AirSharePalettes.Dark.text,
    surfaceVariant = AirSharePalettes.Dark.radarBg,
    onSurfaceVariant = AirSharePalettes.Dark.subtext,
    outline = AirSharePalettes.Dark.cardBorder,
    error = AirSharePalettes.Dark.red,
)

private val LightColors = lightColorScheme(
    primary = AirSharePalettes.Light.green,
    onPrimary = Color.White,
    secondary = AirSharePalettes.Light.blue,
    background = AirSharePalettes.Light.bg,
    onBackground = AirSharePalettes.Light.text,
    surface = AirSharePalettes.Light.cardBg,
    onSurface = AirSharePalettes.Light.text,
    surfaceVariant = AirSharePalettes.Light.radarBg,
    onSurfaceVariant = AirSharePalettes.Light.subtext,
    outline = AirSharePalettes.Light.cardBorder,
    error = AirSharePalettes.Light.red,
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

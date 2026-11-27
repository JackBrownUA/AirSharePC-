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
    val highlightBorder: Color,
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
        bg = Color(0xFF16181B),
        radarBg = Color(0xDE2A2D33),
        radarGlow = Color(0x28525C70),
        radarRing = Color(0x3AA3B8D6),
        cardBg = Color(0xDE24272C),
        cardBorder = Color(0xB84A5059),
        highlightBorder = Color(0x33FFFFFF),
        drawerBg = Color(0xE023272C),
        drawerCard = Color(0xBF353A42),
        drawerBorder = Color(0x94666E7A),
        modalBg = Color(0xE625292E),
        text = Color(0xFFF5F7FA),
        subtext = Color(0xFF9EA6B3),
        pillBg = Color(0xD9363B43),
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
        radarBg = Color(0xE6DBE0EA),
        radarGlow = Color(0x59FFFFFF),
        radarRing = Color(0x36526685),
        cardBg = Color(0xE8FCFCFF),
        cardBorder = Color(0xC8C4CAD6),
        highlightBorder = Color(0x99FFFFFF),
        drawerBg = Color(0xE0F2F5FA),
        drawerCard = Color(0xCCE3E8F2),
        drawerBorder = Color(0xB8BDC4D1),
        modalBg = Color(0xEBF5F7FC),
        text = Color(0xFF1C1F24),
        subtext = Color(0xFF6C7482),
        pillBg = Color(0xDED4D9E3),
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

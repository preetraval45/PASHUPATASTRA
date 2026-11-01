package app.pashupatastra

import android.graphics.Color

/**
 * The site's colours (apps/web/app/globals.css, :root and [data-theme="light"]),
 * so the native bars and the page beneath them read as one surface. The app
 * follows the site's theme, not the phone's: the site defaults to dark because
 * it is an operations console, and the choice is one setting for both.
 */
class Palette(
    val dark: Boolean,
    val ground: Int,
    val panel: Int,
    val raised: Int,
    val edge: Int,
    val ink: Int,
    val muted: Int,
    val faint: Int,
    val astra: Int,
    val crit: Int,
    val high: Int,
    val warn: Int,
    val ok: Int,
) {
    companion object {
        val DARK = Palette(
            dark = true,
            ground = Color.rgb(11, 13, 17),
            panel = Color.rgb(17, 20, 26),
            raised = Color.rgb(23, 27, 34),
            edge = Color.rgb(33, 39, 48),
            ink = Color.rgb(233, 237, 243),
            muted = Color.rgb(141, 151, 166),
            faint = Color.rgb(126, 136, 149),
            astra = Color.rgb(47, 163, 160),
            crit = Color.rgb(251, 113, 133),
            high = Color.rgb(251, 146, 60),
            warn = Color.rgb(251, 191, 36),
            ok = Color.rgb(52, 211, 153),
        )
        val LIGHT = Palette(
            dark = false,
            ground = Color.rgb(247, 247, 245),
            panel = Color.rgb(255, 255, 255),
            raised = Color.rgb(240, 240, 238),
            edge = Color.rgb(223, 224, 221),
            ink = Color.rgb(24, 27, 32),
            muted = Color.rgb(92, 100, 112),
            faint = Color.rgb(100, 108, 120),
            astra = Color.rgb(17, 116, 114),
            crit = Color.rgb(190, 18, 60),
            high = Color.rgb(154, 52, 18),
            warn = Color.rgb(145, 86, 5),
            ok = Color.rgb(4, 120, 87),
        )
    }
}

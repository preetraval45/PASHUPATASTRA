package app.pashupatastra

import android.content.res.ColorStateList
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.View
import android.view.ViewGroup
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.graphics.ColorUtils
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.material.button.MaterialButton

/**
 * The first launch: three short screens before the app, then never again.
 *
 * What the product does, what Sati is (the first mention says what it is,
 * BRAND.md), and alerts, offered with the reason before Android's permission
 * dialog appears, rather than a bare system prompt on an unexplained screen.
 * Plain claims only; no promise the product does not keep.
 */
class Onboarding(
    private val activity: MainActivity,
    private val host: ViewGroup,
    private val onAlerts: (Boolean) -> Unit,
) {
    private class Page(val icon: Int, val title: String, val body: String)

    private val pages = listOf(
        Page(
            R.drawable.ic_shield, "Four alerts are one intrusion",
            "Pashupatastra assembles scattered signals into one incident with its causal chain, and scores a response before anyone runs it.",
        ),
        Page(
            R.drawable.ic_chat, "Ask Sati AI",
            "Sati, the investigation agent, and nine specialist models answer questions about attacks, techniques and defences. Every claim is cited; Sati can propose but never act.",
        ),
        Page(
            R.drawable.ic_alert, "Know when you're needed",
            "Get an alert when an incident awaits your approval or a critical one opens. The phone checks the public API; nothing is sent from it.",
        ),
    )

    private val p get() = activity.palette
    private fun dp(v: Int) = activity.dp(v)

    private val root = FrameLayout(activity)
    private var index = 0

    fun show() {
        root.isClickable = true
        // Drawn edge to edge over the app, so it pads itself clear of the status and navigation bars.
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        host.addView(root, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        // Before Android 11 a sibling that consumed the insets keeps them from this view; read them directly too.
        ViewCompat.getRootWindowInsets(host)?.let { insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            root.setPadding(bars.left, bars.top, bars.right, bars.bottom)
        }
        ViewCompat.requestApplyInsets(root)
        render()
    }

    private fun render() {
        root.removeAllViews()
        root.setBackgroundColor(p.ground)
        val page = pages[index]
        val last = index == pages.lastIndex

        val column = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(32), dp(48), dp(32), dp(32))
        }
        column.addView(View(activity), LinearLayout.LayoutParams(1, 0, 1f))

        column.addView(FrameLayout(activity).apply {
            background = GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                intArrayOf(ColorUtils.setAlphaComponent(p.astra, 90), ColorUtils.setAlphaComponent(p.astra, 25)),
            ).apply { cornerRadius = dp(32).toFloat() }
            addView(ImageView(activity).apply {
                setImageResource(page.icon)
                imageTintList = ColorStateList.valueOf(p.astra)
            }, FrameLayout.LayoutParams(dp(44), dp(44), Gravity.CENTER))
        }, LinearLayout.LayoutParams(dp(96), dp(96)))

        column.addView(TextView(activity).apply {
            text = page.title
            textSize = 26f
            gravity = Gravity.CENTER
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            setTextColor(p.ink)
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(32) })
        column.addView(TextView(activity).apply {
            text = page.body
            textSize = 16f
            gravity = Gravity.CENTER
            setLineSpacing(0f, 1.3f)
            setTextColor(p.muted)
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(12) })

        column.addView(View(activity), LinearLayout.LayoutParams(1, 0, 1f))

        // Where the reader is: one dot per screen.
        column.addView(LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            pages.indices.forEach { i ->
                addView(View(activity).apply {
                    background = GradientDrawable().apply {
                        cornerRadius = dp(4).toFloat()
                        setColor(if (i == index) p.astra else p.edge)
                    }
                }, LinearLayout.LayoutParams(if (i == index) dp(22) else dp(8), dp(8)).apply { if (i > 0) marginStart = dp(6) })
            }
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { bottomMargin = dp(24) })

        column.addView(button(if (last) "Turn on alerts" else "Next", primary = true) {
            if (last) finish(alerts = true) else next()
        }, LinearLayout.LayoutParams(MATCH_PARENT, dp(52)))
        column.addView(button(if (last) "Not now" else "Skip", primary = false) {
            finish(alerts = !last)
        }, LinearLayout.LayoutParams(MATCH_PARENT, dp(52)).apply { topMargin = dp(8) })

        column.alpha = 0f
        column.translationX = dp(24).toFloat()
        column.animate().alpha(1f).translationX(0f).setDuration(220).start()
        root.addView(column, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
    }

    private fun button(label: String, primary: Boolean, onClick: () -> Unit) = MaterialButton(activity).apply {
        text = label
        textSize = 16f
        isAllCaps = false
        cornerRadius = dp(26)
        insetTop = 0
        insetBottom = 0
        if (primary) {
            backgroundTintList = ColorStateList.valueOf(p.astra)
            setTextColor(p.ground)
        } else {
            backgroundTintList = ColorStateList.valueOf(android.graphics.Color.TRANSPARENT)
            setTextColor(p.muted)
        }
        setOnClickListener {
            it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
            onClick()
        }
    }

    private fun next() {
        index++
        render()
    }

    /** Skip keeps alerts on by default (the switch in More turns them off); "Not now" turns them off. */
    private fun finish(alerts: Boolean) {
        root.animate().alpha(0f).setDuration(200).withEndAction { host.removeView(root) }.start()
        onAlerts(alerts)
    }
}

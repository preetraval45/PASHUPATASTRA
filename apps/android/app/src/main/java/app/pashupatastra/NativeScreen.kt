package app.pashupatastra

import android.content.res.ColorStateList
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.text.TextUtils
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.graphics.ColorUtils
import java.util.Locale

/**
 * What the app's native screens share: the site's palette, its rounded panels,
 * and cards that respond to a press as native cards do (a ripple, a slight
 * press-in, a haptic tick). Each screen draws itself from these in code, so
 * a theme change is a redraw.
 */
abstract class NativeScreen(protected val activity: MainActivity) {

    /** The screen's root view, placed in the tab area by MainActivity. */
    abstract val view: View

    /** Called when the tab is shown again: reload if what is shown is old. */
    abstract fun refreshIfStale()

    /** Re-tapping the tab: to the top, or reload if already there. */
    abstract fun toTop()

    /** The theme changed: redraw in the new palette. */
    abstract fun applyPalette()

    /** Back, handled inside the screen (a detail open above its list); false when there is nothing to close. */
    open fun onBack(): Boolean = false

    /** The top bar's title while the screen shows its own page; null for the tab's name. */
    open val title: String? get() = null

    protected val p get() = activity.palette

    /** The app's own words, in the phone's language (res/values, values-hi, values-es). */
    protected fun s(id: Int, vararg args: Any): String = activity.getString(id, *args)

    /** A count with its noun, by the language's own plural rules ("1 incident", "3 incidents"). */
    protected fun q(id: Int, count: Int): String = activity.resources.getQuantityString(id, count, count)

    /** A kind's name, matching the site's labels (apps/web/lib/incidentkinds.ts). */
    protected fun kindLabel(kind: String?): String = when (kind) {
        "KEV" -> s(R.string.kind_kev)
        "NVD" -> s(R.string.kind_nvd)
        "C2" -> s(R.string.kind_c2)
        "RW" -> s(R.string.kind_rw)
        "BREACH" -> s(R.string.kind_breach)
        "CAMPAIGN" -> s(R.string.kind_campaign)
        "PKG" -> s(R.string.kind_pkg)
        else -> kind.orEmpty()
    }

    protected fun sevLabel(severity: String): String = when (severity) {
        "critical" -> s(R.string.stat_critical)
        "high" -> s(R.string.sev_high)
        "medium" -> s(R.string.sev_medium)
        "low" -> s(R.string.sev_low)
        else -> severity
    }
    protected fun dp(v: Int) = activity.dp(v)

    protected fun incidentCard(incident: Api.Incident): View {
        val tone = severityTone(incident.severity)
        return LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = ripple(rounded(p.panel, 18, p.edge))
            pressable { activity.open("/incidents/" + incident.id) }
            // One sentence for TalkBack instead of five fragments.
            contentDescription = s(R.string.incident_desc, sevLabel(incident.severity), incident.id, incident.statement, Api.stateLabel(activity, incident.state))
            addView(LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                addView(text(sevLabel(incident.severity).uppercase(Locale.getDefault()), 11f, tone, bold = true).apply {
                    letterSpacing = 0.06f
                    setPadding(dp(8), dp(3), dp(8), dp(3))
                    background = rounded(ColorUtils.setAlphaComponent(tone, 40), 10)
                })
                addView(text(incident.id, 12f, p.muted).apply { typeface = Typeface.MONOSPACE }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { marginStart = dp(10) })
                addView(text(Api.ago(activity, incident.openedAt), 12f, p.faint))
            })
            addView(text(incident.statement.ifBlank { s(R.string.incident_no_hypothesis) }, 15f, p.ink).apply {
                maxLines = 3
                ellipsize = TextUtils.TruncateAt.END
                setLineSpacing(0f, 1.15f)
            }, lp(top = 10))
            val detail = buildList {
                // A real incident says what kind it is; it has no services or users to count, so none are shown.
                kindOf(incident.id)?.let { add(kindLabel(it)) }
                if (incident.services.isNotEmpty()) add(incident.services.take(3).joinToString(", "))
                if (incident.simulated) add("simulation")
            }.joinToString(" · ")
            addView(LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                addView(text(Api.stateLabel(activity, incident.state), 12f, if (incident.state == "awaiting_approval") p.warn else p.muted, bold = true))
                if (detail.isNotEmpty()) {
                    addView(text(detail, 12f, p.faint).apply {
                        maxLines = 1
                        ellipsize = TextUtils.TruncateAt.END
                    }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { marginStart = dp(10) })
                }
            }, lp(top = 8))
        }
    }


    protected fun text(value: String, size: Float, color: Int, bold: Boolean = false) = TextView(activity).apply {
        text = value
        textSize = size
        setTextColor(color)
        if (bold) typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    }

    protected fun icon(res: Int, color: Int, size: Int) = ImageView(activity).apply {
        setImageResource(res)
        imageTintList = ColorStateList.valueOf(color)
        layoutParams = LinearLayout.LayoutParams(dp(size), dp(size))
    }

    protected fun rounded(color: Int, radius: Int, stroke: Int? = null) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radius).toFloat()
        if (stroke != null) setStroke(dp(1), stroke)
    }

    protected fun ripple(shape: GradientDrawable) =
        RippleDrawable(ColorStateList.valueOf(ColorUtils.setAlphaComponent(p.astra, 50)), shape, null)

    /** Tappable, with a light press-in and a haptic tick, as native cards respond. */
    protected fun View.pressable(onClick: () -> Unit) {
        isClickable = true
        isFocusable = true
        setOnClickListener {
            it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
            onClick()
        }
        setOnTouchListener { v, event ->
            when (event.actionMasked) {
                android.view.MotionEvent.ACTION_DOWN -> v.animate().scaleX(0.98f).scaleY(0.98f).setDuration(90).start()
                android.view.MotionEvent.ACTION_UP, android.view.MotionEvent.ACTION_CANCEL ->
                    v.animate().scaleX(1f).scaleY(1f).setDuration(120).start()
            }
            false
        }
    }

    /**
     * Placeholder cards while the API answers: grey blocks in the shape of the cards
     * to come, pulsing gently, so the screen has its layout before it has its data.
     */
    protected fun skeleton(cards: Int): View = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        repeat(cards) { i ->
            addView(LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(16), dp(16), dp(16), dp(16))
                background = rounded(p.panel, 18, p.edge)
                addView(View(activity).apply { background = rounded(p.raised, 6) }, LinearLayout.LayoutParams(dp(110), dp(12)))
                addView(View(activity).apply { background = rounded(p.raised, 6) }, LinearLayout.LayoutParams(MATCH_PARENT, dp(14)).apply { topMargin = dp(14) })
                addView(View(activity).apply { background = rounded(p.raised, 6) }, LinearLayout.LayoutParams(dp(200), dp(14)).apply { topMargin = dp(8) })
            }, lp(top = if (i == 0) 0 else 10))
        }
        alpha = 0.5f
        animate().alpha(1f).setDuration(700).withEndAction(object : Runnable {
            override fun run() {
                if (!isAttachedToWindow) return
                animate().alpha(if (alpha > 0.75f) 0.5f else 1f).setDuration(700).withEndAction(this).start()
            }
        }).start()
    }

    protected fun lp(top: Int = 0) = LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(top) }

    protected fun weighted(start: Int) = LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { marginStart = dp(start) }

    protected fun severityTone(severity: String) = when (severity) {
        "critical" -> p.crit
        "high" -> p.high
        "medium" -> p.warn
        else -> p.ok
    }
}

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
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.graphics.ColorUtils
import androidx.core.widget.NestedScrollView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.Executors

/**
 * The app's Home tab, drawn natively from the live API rather than loaded as a page.
 *
 * The website's home pitches the product; the app's home is for someone who
 * already chose it: ask Sati, see what needs them, and go. Every number on it
 * is read from the same public API the site reads (`/incidents`, `/health`),
 * and nothing is shown that the API did not return: while loading the counts
 * say "–", and when the API cannot be reached the screen says so.
 */
class HomeScreen(private val activity: MainActivity) {

    class Incident(
        val id: String,
        val state: String,
        val severity: String,
        val openedAt: String,
        val statement: String,
    )

    class Snapshot(val incidents: List<Incident>?, val health: JSONObject?)

    val view = FrameLayout(activity)
    private val refresh = SwipeRefreshLayout(activity)
    private val scroll = NestedScrollView(activity)
    private val column = LinearLayout(activity)
    private var snapshot: Snapshot? = null
    private var loading = false
    private var loadedAt = 0L

    private val p get() = activity.palette
    private fun dp(v: Int) = activity.dp(v)

    init {
        column.orientation = LinearLayout.VERTICAL
        column.setPadding(dp(16), dp(12), dp(16), dp(24))
        scroll.isVerticalScrollBarEnabled = false
        scroll.overScrollMode = View.OVER_SCROLL_NEVER
        scroll.addView(column, FrameLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        refresh.addView(scroll, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        refresh.setOnRefreshListener { load() }
        view.addView(refresh, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        render()
        load()
    }

    /** Reloads if what is shown is more than a minute old: called when the tab is shown again. */
    fun refreshIfStale() {
        if (System.currentTimeMillis() - loadedAt > 60_000) load()
    }

    fun toTop() {
        if (scroll.scrollY > 0) scroll.smoothScrollTo(0, 0) else { refresh.isRefreshing = true; load() }
    }

    fun applyPalette() = render()

    private fun load() {
        if (loading) return
        loading = true
        IO.execute {
            val incidents = runCatching { parseIncidents(JSONArray(get("/incidents"))) }.getOrNull()
            val health = runCatching { JSONObject(get("/health")) }.getOrNull()
            activity.runOnUiThread {
                loading = false
                refresh.isRefreshing = false
                if (activity.isDestroyed) return@runOnUiThread
                snapshot = Snapshot(incidents, health)
                loadedAt = System.currentTimeMillis()
                render()
            }
        }
    }

    // --- the screen -------------------------------------------------------------

    private fun render() {
        view.setBackgroundColor(p.ground)
        refresh.setColorSchemeColors(p.astra)
        refresh.setProgressBackgroundColorSchemeColor(p.raised)
        column.removeAllViews()

        column.addView(text(greeting(), 14f, p.muted))
        column.addView(text("What do you want to do?", 24f, p.ink, bold = true), lp(top = 2))

        column.addView(askCard(), lp(top = 18))

        val all = snapshot?.incidents
        val live = all?.filter { it.state != "resolved" && it.state != "rolled_back" }
        val awaiting = live?.filter { it.state == "awaiting_approval" }
        val critical = live?.count { it.severity == "critical" }

        val stats = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL }
        stats.addView(stat(live?.size, "Open", p.astra) { activity.open("/incidents") }, weighted(0))
        stats.addView(stat(awaiting?.size, "Need you", p.warn) { activity.open("/incidents") }, weighted(10))
        stats.addView(stat(critical, "Critical", p.crit) { activity.open("/incidents?severity=critical") }, weighted(10))
        column.addView(stats, lp(top = 14))

        if (live != null) {
            val needs = awaiting.orEmpty()
            val shown = (if (needs.isNotEmpty()) needs else live).sortedBy { rank(it.severity) }.take(3)
            if (shown.isNotEmpty()) {
                column.addView(heading(if (needs.isNotEmpty()) "Needs your approval" else "Open incidents", "See all") {
                    activity.open("/incidents")
                }, lp(top = 24))
                shown.forEach { column.addView(incidentCard(it), lp(top = 10)) }
            }
        } else if (snapshot != null) {
            column.addView(notice("The API could not be reached. Pull down to try again."), lp(top = 18))
        }

        column.addView(heading("Explore", null, null), lp(top = 24))
        val explore = listOf(
            Triple("/observatory", "Live attacks", R.drawable.ic_radar) to "polled hourly",
            Triple("/models", "Sati models", R.drawable.ic_cube) to "nine, live",
            Triple("/training", "Training", R.drawable.ic_cap) to "nine levels and labs",
            Triple("/findings", "Findings", R.drawable.ic_news) to "what we measured",
        )
        val tones = listOf(p.warn, p.astra, p.ok, p.high)
        explore.chunked(2).forEachIndexed { row, pair ->
            val line = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL }
            pair.forEachIndexed { i, (dest, note) ->
                line.addView(tile(dest.second, note, dest.third, tones[row * 2 + i]) { activity.open(dest.first) }, weighted(if (i == 0) 0 else 10))
            }
            column.addView(line, lp(top = 10))
        }

        column.addView(status(), lp(top = 22))
    }

    private fun askCard(): View {
        val shape = GradientDrawable(
            GradientDrawable.Orientation.TL_BR,
            intArrayOf(ColorUtils.setAlphaComponent(p.astra, 70), p.panel, p.panel),
        ).apply {
            cornerRadius = dp(24).toFloat()
            setStroke(dp(1), ColorUtils.setAlphaComponent(p.astra, 100))
        }
        return LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(18), dp(20), dp(18))
            background = ripple(shape)
            pressable { activity.open("/ask") }
            addView(LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                addView(icon(R.drawable.ic_chat, p.astra, 18))
                addView(text("Sati AI", 13f, p.astra, bold = true), LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { marginStart = dp(8) })
            })
            addView(text("Ask about an attack, a technique or a defence", 18f, p.ink, bold = true), lp(top = 10))
            addView(text("Sati, the investigation agent, and its nine specialist models answer with sources.", 14f, p.muted), lp(top = 4))
            addView(LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(16), dp(6), dp(6), dp(6))
                background = rounded(ColorUtils.setAlphaComponent(p.ground, 200), 18, p.edge)
                addView(text("Ask Sati anything…", 14f, p.faint), LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
                addView(FrameLayout(activity).apply {
                    background = rounded(p.astra, 14)
                    addView(icon(R.drawable.ic_back, p.ground, 18).apply { rotation = 90f }, FrameLayout.LayoutParams(dp(18), dp(18), Gravity.CENTER))
                }, LinearLayout.LayoutParams(dp(36), dp(36)))
            }, lp(top = 16))
        }
    }

    private fun stat(value: Int?, label: String, tone: Int, onClick: () -> Unit): View = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(14), dp(12), dp(14), dp(12))
        background = ripple(rounded(p.panel, 18, p.edge))
        pressable(onClick)
        addView(text(value?.toString() ?: "–", 26f, if (value != null && value > 0) tone else p.ink, bold = true))
        addView(text(label, 12f, p.muted), lp(top = 2))
    }

    private fun incidentCard(incident: Incident): View {
        val tone = severityTone(incident.severity)
        return LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = ripple(rounded(p.panel, 18, p.edge))
            pressable { activity.open("/incidents/" + incident.id) }
            addView(LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                addView(text(incident.severity.uppercase(Locale.ROOT), 11f, tone, bold = true).apply {
                    letterSpacing = 0.06f
                    setPadding(dp(8), dp(3), dp(8), dp(3))
                    background = rounded(ColorUtils.setAlphaComponent(tone, 40), 10)
                })
                addView(text(incident.id, 12f, p.muted).apply { typeface = Typeface.MONOSPACE }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { marginStart = dp(10) })
                addView(text(ago(incident.openedAt), 12f, p.faint))
            })
            addView(text(incident.statement.ifBlank { "No hypothesis yet" }, 15f, p.ink).apply {
                maxLines = 3
                ellipsize = TextUtils.TruncateAt.END
                setLineSpacing(0f, 1.15f)
            }, lp(top = 10))
            addView(text(stateLabel(incident.state), 12f, if (incident.state == "awaiting_approval") p.warn else p.muted, bold = true), lp(top = 8))
        }
    }

    private fun tile(title: String, note: String, iconRes: Int, tone: Int, onClick: () -> Unit): View = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        minimumHeight = dp(116)
        setPadding(dp(16), dp(16), dp(16), dp(14))
        background = ripple(rounded(p.panel, 20, p.edge))
        pressable(onClick)
        addView(FrameLayout(activity).apply {
            background = rounded(ColorUtils.setAlphaComponent(tone, 38), 12)
            addView(icon(iconRes, tone, 22), FrameLayout.LayoutParams(dp(22), dp(22), Gravity.CENTER))
        }, LinearLayout.LayoutParams(dp(42), dp(42)))
        addView(View(activity), LinearLayout.LayoutParams(1, 0, 1f))
        addView(text(title, 15f, p.ink, bold = true), lp(top = 14))
        addView(text(note, 12f, p.muted), lp(top = 1))
    }

    private fun heading(title: String, action: String?, onAction: (() -> Unit)?): View = LinearLayout(activity).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        addView(text(title, 17f, p.ink, bold = true), LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        if (action != null && onAction != null) {
            addView(text(action, 14f, p.astra, bold = true).apply {
                setPadding(dp(8), dp(4), dp(4), dp(4))
                setOnClickListener { onAction() }
            })
        }
    }

    private fun notice(message: String): View = text(message, 14f, p.warn).apply {
        setPadding(dp(16), dp(14), dp(16), dp(14))
        background = rounded(ColorUtils.setAlphaComponent(p.warn, 30), 16, ColorUtils.setAlphaComponent(p.warn, 90))
    }

    /** One line on the system: the API's own health answer, and whether actions really run. */
    private fun status(): View {
        val health = snapshot?.health
        val (dot, line) = when {
            snapshot == null -> p.faint to "Checking the system…"
            health == null -> p.warn to "API unreachable"
            else -> {
                val dry = health.optBoolean("dry_run", true)
                val audit = health.optInt("audit_records", -1)
                (if (dry) p.ok else p.crit) to buildString {
                    append("System ok · ")
                    append(if (dry) "dry run, nothing executes" else "LIVE EXECUTION")
                    if (audit >= 0) append(" · $audit audit records")
                }
            }
        }
        return LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            addView(View(activity).apply { background = rounded(dot, 4) }, LinearLayout.LayoutParams(dp(8), dp(8)))
            addView(text(line, 12f, p.faint), LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { marginStart = dp(8) })
        }
    }

    // --- pieces -----------------------------------------------------------------

    private fun text(value: String, size: Float, color: Int, bold: Boolean = false) = TextView(activity).apply {
        text = value
        textSize = size
        setTextColor(color)
        if (bold) typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    }

    private fun icon(res: Int, color: Int, size: Int) = ImageView(activity).apply {
        setImageResource(res)
        imageTintList = ColorStateList.valueOf(color)
        layoutParams = LinearLayout.LayoutParams(dp(size), dp(size))
    }

    private fun rounded(color: Int, radius: Int, stroke: Int? = null) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radius).toFloat()
        if (stroke != null) setStroke(dp(1), stroke)
    }

    private fun ripple(shape: GradientDrawable) =
        RippleDrawable(ColorStateList.valueOf(ColorUtils.setAlphaComponent(p.astra, 50)), shape, null)

    /** Tappable, with a light press-in and a haptic tick, as native cards respond. */
    private fun View.pressable(onClick: () -> Unit) {
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

    private fun lp(top: Int = 0) = LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(top) }

    private fun weighted(start: Int) = LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { marginStart = dp(start) }

    private fun severityTone(severity: String) = when (severity) {
        "critical" -> p.crit
        "high" -> p.high
        "medium" -> p.warn
        else -> p.ok
    }

    private companion object {
        val IO = Executors.newSingleThreadExecutor()

        fun get(path: String): String {
            val connection = URL(BuildConfig.API_URL.trimEnd('/') + path).openConnection() as HttpURLConnection
            connection.connectTimeout = 10_000
            connection.readTimeout = 20_000
            connection.setRequestProperty("Accept", "application/json")
            try {
                if (connection.responseCode !in 200..299) error("HTTP ${connection.responseCode}")
                return connection.inputStream.bufferedReader().use { it.readText() }
            } finally {
                connection.disconnect()
            }
        }

        fun parseIncidents(array: JSONArray): List<Incident> = (0 until array.length()).map { i ->
            val o = array.getJSONObject(i)
            val hypotheses = o.optJSONArray("hypotheses")
            Incident(
                id = o.optString("id"),
                state = o.optString("state"),
                severity = o.optString("severity", "low"),
                openedAt = o.optString("opened_at"),
                statement = hypotheses?.optJSONObject(0)?.optString("statement").orEmpty(),
            )
        }

        fun rank(severity: String) = when (severity) {
            "critical" -> 0
            "high" -> 1
            "medium" -> 2
            else -> 3
        }

        fun stateLabel(state: String) = when (state) {
            "awaiting_approval" -> "Awaiting your approval"
            else -> state.replace('_', ' ').replaceFirstChar { it.uppercase() }
        }

        fun greeting(): String {
            val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
            return when {
                hour < 5 -> "Working late"
                hour < 12 -> "Good morning"
                hour < 18 -> "Good afternoon"
                else -> "Good evening"
            }
        }

        /** "3 h ago" from the API's UTC timestamp; java.time needs API 26, so SimpleDateFormat. */
        fun ago(iso: String): String {
            val at = runCatching {
                SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.ROOT).apply { timeZone = TimeZone.getTimeZone("UTC") }
                    .parse(iso.take(19))?.time
            }.getOrNull() ?: return ""
            val minutes = (System.currentTimeMillis() - at) / 60_000
            return when {
                minutes < 1 -> "just now"
                minutes < 60 -> "$minutes min ago"
                minutes < 60 * 24 -> "${minutes / 60} h ago"
                else -> "${minutes / (60 * 24)} d ago"
            }
        }
    }
}

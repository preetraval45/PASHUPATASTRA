package app.pashupatastra

import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.FrameLayout
import android.widget.LinearLayout
import androidx.core.graphics.ColorUtils
import androidx.core.widget.NestedScrollView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar

/**
 * The app's Home tab, drawn natively from the live API rather than loaded as a page.
 *
 * The website's home pitches the product; the app's home is for someone who
 * already chose it: ask Sati, see what needs them, and go. Every number on it
 * is read from the same public API the site reads (`/incidents`, `/health`),
 * and nothing is shown that the API did not return: while loading the counts
 * say "–", and when the API cannot be reached the screen says so.
 */
class HomeScreen(activity: MainActivity) : NativeScreen(activity) {

    class Snapshot(val incidents: List<Api.Incident>?, val health: JSONObject?)

    override val view = FrameLayout(activity)
    private val refresh = SwipeRefreshLayout(activity)
    private val scroll = NestedScrollView(activity)
    private val column = LinearLayout(activity)
    private var snapshot: Snapshot? = null
    private var loading = false
    private var loadedAt = 0L


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
    override fun refreshIfStale() {
        if (System.currentTimeMillis() - loadedAt > 60_000) load()
    }

    override fun toTop() {
        if (scroll.scrollY > 0) scroll.smoothScrollTo(0, 0) else { refresh.isRefreshing = true; load() }
    }

    override fun applyPalette() = render()

    private fun load() {
        if (loading) return
        loading = true
        Api.IO.execute {
            val incidents = runCatching { Api.parseIncidents(JSONArray(Api.get("/incidents"))) }.getOrNull()
            val health = runCatching { JSONObject(Api.get("/health")) }.getOrNull()
            if (incidents != null) IncidentsWidget.update(activity, incidents)
            activity.runOnUiThread {
                loading = false
                refresh.isRefreshing = false
                if (activity.isDestroyed) return@runOnUiThread
                snapshot = Snapshot(incidents, health)
                if (incidents != null) activity.setNeedYou(incidents.count { it.state == "awaiting_approval" })
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
            val shown = (if (needs.isNotEmpty()) needs else live).sortedBy { Api.rank(it.severity) }.take(3)
            if (shown.isNotEmpty()) {
                column.addView(heading(if (needs.isNotEmpty()) "Needs your approval" else "Open incidents", "See all") {
                    activity.open("/incidents")
                }, lp(top = 24))
                shown.forEach { column.addView(incidentCard(it), lp(top = 10)) }
            }
        } else if (snapshot == null) {
            column.addView(skeleton(2), lp(top = 24))
        } else {
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
        contentDescription = if (value == null) "$label: loading" else "$value $label"
        addView(text(value?.toString() ?: "–", 26f, if (value != null && value > 0) tone else p.ink, bold = true))
        addView(text(label, 12f, p.muted), lp(top = 2))
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

    private fun greeting(): String {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return when {
            hour < 5 -> "Working late"
            hour < 12 -> "Good morning"
            hour < 18 -> "Good afternoon"
            else -> "Good evening"
        }
    }
}

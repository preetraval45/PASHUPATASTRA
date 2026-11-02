package app.pashupatastra

import android.net.Uri
import android.text.TextUtils
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import androidx.core.graphics.ColorUtils
import androidx.core.widget.NestedScrollView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import org.json.JSONObject

/**
 * Live attacks, native: what the public feeds reported in the last hours, read
 * from the API's `/intel` (the same data as the site's Observatory). Each card
 * names its source and how far it is verified, and tapping it opens the
 * source's own record: an item a reader cannot trace is not shown as fact.
 */
class FeedScreen(activity: MainActivity) : NativeScreen(activity) {

    class Report(
        val source: String,
        val severity: String,
        val verification: String,
        val title: String,
        val summary: String,
        val url: String?,
        val at: String,
        val reports: Int,
    )

    override val view = FrameLayout(activity)
    private val refresh = SwipeRefreshLayout(activity)
    private val scroll = NestedScrollView(activity)
    private val column = ReadableColumn(activity, activity.dp(720))
    private var reports: List<Report>? = null
    private var windowHours = 0
    private var failed = false
    private var staleAt: Long? = null
    private var loading = false
    private var loadedAt = 0L
    private var source = "all"

    init {
        column.orientation = LinearLayout.VERTICAL
        column.setPadding(0, dp(12), 0, dp(24))
        scroll.isVerticalScrollBarEnabled = false
        scroll.overScrollMode = View.OVER_SCROLL_NEVER
        scroll.addView(column, FrameLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT, android.view.Gravity.CENTER_HORIZONTAL))
        refresh.addView(scroll, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        refresh.setOnRefreshListener { load() }
        view.addView(refresh, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        render()
        load()
    }

    override fun refreshIfStale() {
        if (System.currentTimeMillis() - loadedAt > 5 * 60_000) load()
    }

    override fun toTop() {
        if (scroll.scrollY > 0) scroll.smoothScrollTo(0, 0) else { refresh.isRefreshing = true; load() }
    }

    override fun applyPalette() = render()

    private fun load() {
        if (loading) return
        loading = true
        Api.IO.execute {
            val fetched = Api.fetch(activity, "/intel?limit=80")
            val body = fetched?.let { runCatching { JSONObject(it.body) }.getOrNull() }
            val parsed = body?.let { runCatching { parse(it) }.getOrNull() }
            activity.runOnUiThread {
                loading = false
                refresh.isRefreshing = false
                if (activity.isDestroyed) return@runOnUiThread
                failed = fetched?.fresh != true
                staleAt = fetched?.takeIf { !it.fresh }?.at
                if (parsed != null) {
                    reports = parsed
                    windowHours = body?.optInt("window_hours", 0) ?: 0
                    loadedAt = System.currentTimeMillis()
                }
                render()
            }
        }
    }

    private fun render() {
        view.setBackgroundColor(p.ground)
        refresh.setColorSchemeColors(p.astra)
        refresh.setProgressBackgroundColorSchemeColor(p.raised)
        column.removeAllViews()

        val all = reports
        val list = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), 0, dp(16), 0)
        }
        if (all == null) {
            column.addView(list)
            list.addView(
                if (failed) notice(s(R.string.feed_failed))
                else skeleton(5),
                lp(top = 10),
            )
            return
        }

        val sources = listOf("all") + all.map { it.source }.distinct().sortedBy { label(it) }
        if (source !in sources) source = "all"
        column.addView(chips(sources, all), LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        column.addView(list, lp(top = 6))
        if (failed) {
            val at = staleAt
            list.addView(notice(
                if (at != null) s(R.string.feed_offline, Api.clock(at))
                else s(R.string.feed_stale),
            ), lp(top = 10))
        }

        val shown = if (source == "all") all else all.filter { it.source == source }
        val counted = q(R.plurals.reports_count, shown.size)
        list.addView(text(if (windowHours > 0) s(R.string.feed_window, counted, windowHours) else counted, 13f, p.muted), lp(top = 8))
        shown.forEach { list.addView(card(it), lp(top = 10)) }
        list.addView(text(s(R.string.feed_footer), 12f, p.faint).apply {
            gravity = Gravity.CENTER
        }, lp(top = 18))
    }

    private fun chips(sources: List<String>, all: List<Report>): View {
        val row = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(16), dp(2), dp(16), dp(2))
        }
        sources.forEachIndexed { i, key ->
            val active = key == source
            val count = if (key == "all") all.size else all.count { it.source == key }
            val chip = text("${label(key)}  $count", 13f, if (active) p.ground else p.muted, bold = active).apply {
                gravity = Gravity.CENTER
                minHeight = dp(36)
                setPadding(dp(14), 0, dp(14), 0)
                background = ripple(if (active) rounded(p.astra, 18) else rounded(p.panel, 18, p.edge))
                isClickable = true
                setOnClickListener {
                    it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                    source = key
                    render()
                }
            }
            row.addView(chip, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { if (i > 0) marginStart = dp(8) })
        }
        return HorizontalScrollView(activity).apply {
            isHorizontalScrollBarEnabled = false
            overScrollMode = View.OVER_SCROLL_NEVER
            addView(row)
        }
    }

    private fun card(report: Report): View {
        val tone = when (report.severity) {
            "critical" -> p.crit
            "warning" -> p.warn
            else -> p.astra
        }
        return LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = ripple(rounded(p.panel, 18, p.edge))
            val url = report.url
            if (url != null) pressable { activity.openOutside(Uri.parse(url)) }
            contentDescription = s(R.string.feed_desc, label(report.source), verification(report.verification), report.title) +
                if (url != null) " " + s(R.string.feed_opens_source) else ""
            addView(LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                addView(text(label(report.source), 11f, tone, bold = true).apply {
                    setPadding(dp(8), dp(3), dp(8), dp(3))
                    background = rounded(ColorUtils.setAlphaComponent(tone, 40), 10)
                })
                addView(text(verification(report.verification), 12f, p.muted), LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { marginStart = dp(10) })
                addView(text(Api.ago(activity, report.at), 12f, p.faint))
            })
            addView(text(report.title, 15f, p.ink, bold = true).apply {
                maxLines = 2
                ellipsize = TextUtils.TruncateAt.END
            }, lp(top = 10))
            if (report.summary.isNotBlank() && report.summary != report.title) {
                addView(text(report.summary, 13f, p.muted).apply {
                    maxLines = 3
                    ellipsize = TextUtils.TruncateAt.END
                    setLineSpacing(0f, 1.15f)
                }, lp(top = 4))
            }
            val footer = buildList {
                if (report.reports > 1) add(q(R.plurals.reports_count, report.reports))
                if (url != null) add(s(R.string.feed_source_record))
            }.joinToString(" · ")
            if (footer.isNotEmpty()) addView(text(footer, 12f, p.astra, bold = true), lp(top = 8))
        }
    }

    /** The feeds by what they report, not by their product names. */
    private fun label(source: String): String = when (source) {
        "all" -> s(R.string.src_all)
        "cisa-kev" -> s(R.string.src_kev)
        "nvd" -> s(R.string.src_nvd)
        "feodo-tracker" -> s(R.string.src_feodo)
        "ransomware-live" -> s(R.string.src_ransomware)
        "threatfox" -> s(R.string.src_threatfox)
        "urlhaus" -> s(R.string.src_urlhaus)
        "hibp" -> s(R.string.src_hibp)
        else -> source
    }

    private fun verification(level: String): String = when (level) {
        "reported" -> s(R.string.ver_reported)
        "corroborated" -> s(R.string.ver_corroborated)
        "confirmed" -> s(R.string.ver_confirmed)
        else -> level
    }

    private fun notice(message: String): View = text(message, 14f, p.warn).apply {
        setPadding(dp(16), dp(14), dp(16), dp(14))
        background = rounded(ColorUtils.setAlphaComponent(p.warn, 30), 16, ColorUtils.setAlphaComponent(p.warn, 90))
    }

    private companion object {
        fun parse(body: JSONObject): List<Report> {
            val groups = body.optJSONArray("groups") ?: return emptyList()
            return (0 until groups.length()).map { i ->
                val g = groups.getJSONObject(i)
                val url = g.optJSONObject("provenance")?.optString("url")?.takeIf { it.startsWith("https://") }
                Report(
                    source = g.optString("source"),
                    severity = g.optString("severity"),
                    verification = g.optString("verification"),
                    title = g.optString("title"),
                    summary = g.optString("summary"),
                    url = url,
                    at = g.optString("last_at"),
                    reports = g.optInt("reports", 1),
                )
            }
        }
    }
}

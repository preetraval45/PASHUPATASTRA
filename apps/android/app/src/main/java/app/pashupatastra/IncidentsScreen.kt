package app.pashupatastra

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
import org.json.JSONArray

/**
 * The Incidents tab's list, native: filter chips a thumb can flick through and
 * a card per incident, read from the API's `/incidents`. Tapping a card opens
 * that incident's full page (the causal chain, plan and approval live there)
 * above the list; back returns to the list where it was.
 */
class IncidentsScreen(activity: MainActivity) : NativeScreen(activity) {

    private class Filter(val key: String, val label: String, val test: (Api.Incident) -> Boolean)

    private val filters = listOf(
        Filter("open", "Open") { it.state != "resolved" && it.state != "rolled_back" },
        Filter("approval", "Need you") { it.state == "awaiting_approval" },
        Filter("critical", "Critical") { it.severity == "critical" },
        Filter("high", "High") { it.severity == "high" },
        Filter("medium", "Medium") { it.severity == "medium" },
        Filter("low", "Low") { it.severity == "low" },
        Filter("closed", "Closed") { it.state == "resolved" || it.state == "rolled_back" },
        Filter("all", "All") { true },
    )

    override val view = FrameLayout(activity)
    private val refresh = SwipeRefreshLayout(activity)
    private val scroll = NestedScrollView(activity)
    private val column = LinearLayout(activity)
    private var incidents: List<Api.Incident>? = null
    private var failed = false
    private var loading = false
    private var loadedAt = 0L
    private var filter = "open"

    init {
        column.orientation = LinearLayout.VERTICAL
        column.setPadding(0, dp(12), 0, dp(24))
        scroll.isVerticalScrollBarEnabled = false
        scroll.overScrollMode = View.OVER_SCROLL_NEVER
        scroll.addView(column, FrameLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        refresh.addView(scroll, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        refresh.setOnRefreshListener { load() }
        view.addView(refresh, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        render()
        load()
    }

    override fun refreshIfStale() {
        if (System.currentTimeMillis() - loadedAt > 60_000) load()
    }

    override fun toTop() {
        if (scroll.scrollY > 0) scroll.smoothScrollTo(0, 0) else { refresh.isRefreshing = true; load() }
    }

    override fun applyPalette() = render()

    /** Shows one filter, by the site's own names ("critical", "high", …), e.g. from Home's Critical count. */
    fun show(key: String) {
        val known = filters.firstOrNull { it.key == key } ?: return
        filter = known.key
        render()
        scroll.scrollTo(0, 0)
    }

    private fun load() {
        if (loading) return
        loading = true
        Api.IO.execute {
            val result = runCatching { Api.parseIncidents(JSONArray(Api.get("/incidents"))) }.getOrNull()
            activity.runOnUiThread {
                loading = false
                refresh.isRefreshing = false
                if (activity.isDestroyed) return@runOnUiThread
                failed = result == null
                if (result != null) {
                    incidents = result
                    activity.setNeedYou(result.count { it.state == "awaiting_approval" })
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

        val all = incidents
        column.addView(chips(all), LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))

        val list = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), 0, dp(16), 0)
        }
        column.addView(list, lp(top = 6))

        if (all == null) {
            list.addView(
                if (failed) notice("The incidents could not be loaded. Pull down to try again.")
                else skeleton(4),
                lp(top = 10),
            )
            return
        }
        if (failed) list.addView(notice("Showing the last list loaded: the API did not answer just now."), lp(top = 10))

        val chosen = filters.first { it.key == filter }
        val shown = all.filter(chosen.test).sortedWith(compareBy({ Api.rank(it.severity) }, { it.state != "awaiting_approval" }))
        list.addView(text(
            "${shown.size} ${if (shown.size == 1) "incident" else "incidents"}" + if (chosen.key == "all") "" else " · ${chosen.label.lowercase()}",
            13f, p.muted,
        ), lp(top = 8))
        if (shown.isEmpty()) {
            list.addView(empty(), lp(top = 10))
        } else {
            shown.forEach { list.addView(incidentCard(it), lp(top = 10)) }
        }
    }

    private fun chips(all: List<Api.Incident>?): View {
        val row = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(16), dp(2), dp(16), dp(2))
        }
        filters.forEachIndexed { i, f ->
            val active = f.key == filter
            val count = all?.count(f.test)
            val chip = text(if (count == null) f.label else "${f.label}  $count", 13f, if (active) p.ground else p.muted, bold = active).apply {
                gravity = Gravity.CENTER
                minHeight = dp(36)
                setPadding(dp(14), 0, dp(14), 0)
                background = ripple(
                    if (active) rounded(p.astra, 18) else rounded(p.panel, 18, p.edge),
                )
                isClickable = true
                setOnClickListener {
                    it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                    filter = f.key
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

    private fun empty(): View = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        setPadding(dp(24), dp(36), dp(24), dp(36))
        background = rounded(p.panel, 20, p.edge)
        addView(icon(R.drawable.ic_check, p.ok, 36))
        addView(text("Nothing here", 16f, p.ink, bold = true), LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(12) })
        addView(text("No incident matches this filter.", 14f, p.muted), LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(4) })
    }

    private fun notice(message: String): View = text(message, 14f, p.warn).apply {
        setPadding(dp(16), dp(14), dp(16), dp(14))
        background = rounded(ColorUtils.setAlphaComponent(p.warn, 30), 16, ColorUtils.setAlphaComponent(p.warn, 90))
    }
}

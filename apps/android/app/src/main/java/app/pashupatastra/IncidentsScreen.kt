package app.pashupatastra

import android.text.InputType
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import androidx.core.graphics.ColorUtils
import androidx.core.widget.NestedScrollView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder

/**
 * The Incidents tab, native, over the real incidents the API builds (as of b7cbc33 it serves no scenarios):
 *
 * - **Live**: what the feeds show now (`/incidents`, ids `LIVE-<KIND>-…`), with a chip per kind.
 * - **From the record**: past incidents built from CISA KEV, NVD and Have I Been Pwned
 *   (`/incidents/past`, about 5,300), searchable and paged.
 *
 * The kind comes from the id (KEV, NVD, C2, RW, BREACH), as the site reads it (apps/web/lib/incidentkinds.ts),
 * so a label cannot disagree with the rule that built the incident. Written drills (INC-…) are not listed.
 * A card opens the incident's full page above the list; back returns here.
 */
class IncidentsScreen(activity: MainActivity) : NativeScreen(activity) {

    override val view = FrameLayout(activity)
    private val refresh = SwipeRefreshLayout(activity)
    private val scroll = NestedScrollView(activity)
    private val column = ReadableColumn(activity, activity.dp(720))

    private var tab = "live"

    // Live
    private var incidents: List<Api.Incident>? = null
    private var failed = false
    private var staleAt: Long? = null
    private var loading = false
    private var loadedAt = 0L
    private var kind = "ALL"
    private var livePages = 1

    // From the record
    private val past = mutableListOf<Api.Incident>()
    private var pastTotal: Int? = null
    private var pastKind = "ALL"
    private var pastQuery = ""
    private var pastLoading = false
    private var pastFailed = false
    private val search = EditText(activity)

    init {
        column.setPadding(0, dp(12), 0, dp(24))
        scroll.isVerticalScrollBarEnabled = false
        scroll.overScrollMode = View.OVER_SCROLL_NEVER
        scroll.addView(column, FrameLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT, Gravity.CENTER_HORIZONTAL))
        refresh.addView(scroll, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        refresh.setOnRefreshListener { if (tab == "live") load() else loadPast(reset = true) }
        view.addView(refresh, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        search.apply {
            hint = s(R.string.past_search_hint)
            textSize = 15f
            isSingleLine = true
            inputType = InputType.TYPE_CLASS_TEXT
            imeOptions = EditorInfo.IME_ACTION_SEARCH
            setPadding(dp(16), dp(12), dp(16), dp(12))
            setOnEditorActionListener { v, action, _ ->
                if (action != EditorInfo.IME_ACTION_SEARCH) return@setOnEditorActionListener false
                pastQuery = text.toString().trim()
                (activity.getSystemService(android.content.Context.INPUT_METHOD_SERVICE) as InputMethodManager)
                    .hideSoftInputFromWindow(v.windowToken, 0)
                loadPast(reset = true)
                true
            }
        }
        render()
        load()
        loadPast(reset = true)
    }

    override fun refreshIfStale() {
        if (System.currentTimeMillis() - loadedAt > 60_000) load()
    }

    override fun toTop() {
        if (scroll.scrollY > 0) scroll.smoothScrollTo(0, 0) else {
            refresh.isRefreshing = true
            if (tab == "live") load() else loadPast(reset = true)
        }
    }

    override fun applyPalette() = render()

    /** From Home: the live list, on a kind if one is named; a severity is not a kind, so it shows all. */
    fun show(key: String) {
        tab = "live"
        kind = KINDS.firstOrNull { it.equals(key, ignoreCase = true) } ?: "ALL"
        render()
        scroll.scrollTo(0, 0)
    }

    /** From Home's "From the record" count. */
    fun showPast() {
        tab = "past"
        render()
        scroll.scrollTo(0, 0)
    }

    private fun load() {
        if (loading) return
        loading = true
        Api.IO.execute {
            val fetched = Api.fetch(activity, "/incidents")
            val result = fetched?.let { runCatching { Api.parseIncidents(JSONArray(it.body)) }.getOrNull() }
                ?.filter { it.id.startsWith("LIVE-") }
            activity.runOnUiThread {
                loading = false
                refresh.isRefreshing = false
                if (activity.isDestroyed) return@runOnUiThread
                failed = fetched?.fresh != true
                staleAt = fetched?.takeIf { !it.fresh }?.at
                if (result != null) {
                    incidents = result
                    activity.setNeedYou(result.count { it.state == "awaiting_approval" })
                    loadedAt = System.currentTimeMillis()
                }
                render()
            }
        }
    }

    private fun loadPast(reset: Boolean) {
        if (pastLoading) return
        pastLoading = true
        if (reset) {
            past.clear()
            pastTotal = null
        }
        val offset = past.size
        val path = buildString {
            append("/incidents/past?limit=25&offset=").append(offset)
            if (pastKind != "ALL") append("&kind=").append(pastKind.lowercase())
            if (pastQuery.isNotEmpty()) append("&q=").append(URLEncoder.encode(pastQuery, "UTF-8"))
        }
        if (tab == "past") render()
        Api.IO.execute {
            val body = runCatching { JSONObject(Api.get(path)) }.getOrNull()
            val items = body?.optJSONArray("items")?.let { runCatching { Api.parseIncidents(it) }.getOrNull() }
            val total = body?.optInt("total", -1) ?: -1
            activity.runOnUiThread {
                pastLoading = false
                refresh.isRefreshing = false
                if (activity.isDestroyed) return@runOnUiThread
                pastFailed = items == null
                if (items != null) {
                    past.addAll(items)
                    pastTotal = if (total >= 0) total else past.size
                }
                render()
            }
        }
    }

    // --- the screen -------------------------------------------------------------------------

    private fun render() {
        view.setBackgroundColor(p.ground)
        refresh.setColorSchemeColors(p.astra)
        refresh.setProgressBackgroundColorSchemeColor(p.raised)
        column.removeAllViews()
        column.addView(tabs(), LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply {
            marginStart = dp(16)
            marginEnd = dp(16)
        })
        if (tab == "live") renderLive() else renderPast()
    }

    /** Live | From the record, with how many each holds. */
    private fun tabs(): View = LinearLayout(activity).apply {
        orientation = LinearLayout.HORIZONTAL
        setPadding(dp(4), dp(4), dp(4), dp(4))
        background = rounded(p.panel, 22, p.edge)
        val live = incidents?.size
        listOf(
            "live" to (s(R.string.inc_tab_live) + (live?.let { "  $it" } ?: "")),
            "past" to (s(R.string.inc_tab_past) + (pastTotal?.let { "  $it" } ?: "")),
        ).forEachIndexed { i, (key, label) ->
            val active = key == tab
            addView(text(label, 14f, if (active) p.ground else p.muted, bold = true).apply {
                gravity = Gravity.CENTER
                minHeight = dp(40)
                background = if (active) rounded(p.astra, 18) else null
                isClickable = true
                setOnClickListener {
                    it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                    tab = key
                    render()
                }
            }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { if (i > 0) marginStart = dp(4) })
        }
    }

    private fun renderLive() {
        val all = incidents
        val list = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), 0, dp(16), 0)
        }
        if (all == null) {
            column.addView(list, lp(top = 10))
            list.addView(if (failed) notice(s(R.string.incidents_failed)) else skeleton(4), lp(top = 10))
            return
        }
        val present = listOf("ALL") + KINDS.filter { k -> all.any { kindOf(it.id) == k } }
        if (kind !in present) kind = "ALL"
        column.addView(chips(present, kind, { k -> if (k == "ALL") all.size else all.count { kindOf(it.id) == k } }) {
            kind = it
            livePages = 1
            render()
        }, lp(top = 12))
        column.addView(list, lp(top = 2))
        if (failed) {
            val at = staleAt
            list.addView(notice(if (at != null) s(R.string.home_offline, Api.clock(at)) else s(R.string.incidents_stale)), lp(top = 10))
        }
        val shown = all.filter { kind == "ALL" || kindOf(it.id) == kind }
            .sortedWith(compareBy({ Api.rank(it.severity) }, { it.state != "awaiting_approval" }))
        list.addView(text(q(R.plurals.incidents_count, shown.size) + " · " + s(R.string.inc_live_note), 13f, p.muted), lp(top = 8))
        if (shown.isEmpty()) list.addView(empty(s(R.string.empty_body)), lp(top = 10))
        // A long live list draws more only on demand: each card is a view, and hundreds at once are slow.
        shown.take(LIVE_PAGE * livePages).forEach { list.addView(incidentCard(it), lp(top = 10)) }
        if (shown.size > LIVE_PAGE * livePages) list.addView(more { livePages++; render() }, lp(top = 14))
    }

    private fun renderPast() {
        (search.parent as? android.view.ViewGroup)?.removeView(search)
        search.setTextColor(p.ink)
        search.setHintTextColor(p.faint)
        search.background = rounded(p.panel, 18, p.edge)
        column.addView(search, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply {
            topMargin = dp(12)
            marginStart = dp(16)
            marginEnd = dp(16)
        })
        column.addView(chips(PAST_KINDS, pastKind, null) {
            pastKind = it
            loadPast(reset = true)
        }, lp(top = 10))
        val list = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), 0, dp(16), 0)
        }
        column.addView(list, lp(top = 2))
        val total = pastTotal
        if (total == null) {
            list.addView(if (pastFailed) notice(s(R.string.past_failed)) else skeleton(4), lp(top = 10))
            return
        }
        list.addView(text(s(R.string.past_count, past.size, total) + " · " + s(R.string.inc_past_note), 13f, p.muted), lp(top = 8))
        if (past.isEmpty()) list.addView(empty(s(R.string.past_empty)), lp(top = 10))
        past.forEach { list.addView(incidentCard(it), lp(top = 10)) }
        if (past.size < total) list.addView(more { loadPast(reset = false) }, lp(top = 14))
        if (pastFailed && past.isNotEmpty()) list.addView(notice(s(R.string.past_failed)), lp(top = 10))
    }

    // --- pieces ----------------------------------------------------------------------------

    private fun chips(keys: List<String>, active: String, count: ((String) -> Int)?, onPick: (String) -> Unit): View {
        val row = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(16), dp(2), dp(16), dp(2))
        }
        keys.forEachIndexed { i, key ->
            val on = key == active
            val label = (if (key == "ALL") s(R.string.filter_all) else kindLabel(key)) + (count?.let { "  ${it(key)}" } ?: "")
            row.addView(text(label, 13f, if (on) p.ground else p.muted, bold = on).apply {
                gravity = Gravity.CENTER
                minHeight = dp(36)
                setPadding(dp(14), 0, dp(14), 0)
                background = ripple(if (on) rounded(p.astra, 18) else rounded(p.panel, 18, p.edge))
                isClickable = true
                setOnClickListener {
                    it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                    onPick(key)
                }
            }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { if (i > 0) marginStart = dp(8) })
        }
        return HorizontalScrollView(activity).apply {
            isHorizontalScrollBarEnabled = false
            overScrollMode = View.OVER_SCROLL_NEVER
            addView(row)
        }
    }

    private fun more(onClick: () -> Unit): View = text(s(R.string.past_more), 14f, p.astra, bold = true).apply {
        gravity = Gravity.CENTER
        minHeight = dp(48)
        background = ripple(rounded(p.panel, 18, p.edge))
        isClickable = true
        setOnClickListener {
            it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
            onClick()
        }
    }

    private fun empty(message: String): View = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        setPadding(dp(24), dp(36), dp(24), dp(36))
        background = rounded(p.panel, 20, p.edge)
        addView(icon(R.drawable.ic_check, p.ok, 36))
        addView(text(s(R.string.empty_title), 16f, p.ink, bold = true), LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(12) })
        addView(text(message, 14f, p.muted).apply { gravity = Gravity.CENTER },
            LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(4) })
    }

    private fun notice(message: String): View = text(message, 14f, p.warn).apply {
        setPadding(dp(16), dp(14), dp(16), dp(14))
        background = rounded(ColorUtils.setAlphaComponent(p.warn, 30), 16, ColorUtils.setAlphaComponent(p.warn, 90))
    }

    private companion object {
        const val LIVE_PAGE = 40
        val PAST_KINDS = listOf("ALL", "KEV", "NVD", "BREACH", "RW", "CAMPAIGN")
    }
}

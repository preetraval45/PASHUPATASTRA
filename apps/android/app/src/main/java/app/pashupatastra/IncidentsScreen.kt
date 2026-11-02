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

    // A real incident opened from a card, shown in place of the list; back returns to the list where it was.
    private var detailId: String? = null
    private var detail: JSONObject? = null
    private var detailFailed = false
    private var listScroll = 0

    override val title: String? get() = detailId

    override fun onBack(): Boolean {
        if (detailId == null) return false
        detailId = null
        detail = null
        render()
        scroll.post { scroll.scrollTo(0, listScroll) }
        return true
    }

    /** Opens one real incident natively (`/incidents/{id}`): its claim, how it unfolded, and its sources. */
    fun openDetail(id: String) {
        if (detailId == null) listScroll = scroll.scrollY
        detailId = id
        detail = null
        detailFailed = false
        render()
        scroll.scrollTo(0, 0)
        activity.refreshChrome()
        Api.IO.execute {
            val body = runCatching { JSONObject(Api.get("/incidents/" + java.net.URLEncoder.encode(id, "UTF-8"))) }.getOrNull()
            activity.runOnUiThread {
                if (activity.isDestroyed || detailId != id) return@runOnUiThread
                refresh.isRefreshing = false
                detail = body
                detailFailed = body == null
                render()
            }
        }
    }

    init {
        column.setPadding(0, dp(12), 0, dp(24))
        scroll.isVerticalScrollBarEnabled = false
        scroll.overScrollMode = View.OVER_SCROLL_NEVER
        scroll.addView(column, FrameLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT, Gravity.CENTER_HORIZONTAL))
        refresh.addView(scroll, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        refresh.setOnRefreshListener {
            val open = detailId
            when {
                open != null -> openDetail(open)
                tab == "live" -> load()
                else -> loadPast(reset = true)
            }
        }
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
        if (detailId != null) {
            renderDetail()
            return
        }
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

    /**
     * One incident: kind, severity and age; the claim as the rule that built it states it; each step of the
     * causal chain with its ATT&CK technique when it has one; and the publishers' records it rests on. Every
     * line is the API's; nothing is summarised here. The site's page (plan, timeline, evidence) is a tap away.
     */
    private fun renderDetail() {
        val id = detailId ?: return
        val body = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), 0, dp(16), 0)
        }
        column.addView(body)
        val d = detail
        if (d == null) {
            body.addView(if (detailFailed) notice(s(R.string.detail_failed)) else skeleton(3), lp(top = 4))
            return
        }
        val severity = d.optString("severity")
        val tone = when (severity) {
            "critical" -> p.crit
            "high" -> p.high
            "medium" -> p.warn
            else -> p.ok
        }
        val hypothesis = d.optJSONArray("hypotheses")?.optJSONObject(0)

        // Kind, severity, age, state.
        body.addView(LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(text(sevLabel(severity).uppercase(java.util.Locale.getDefault()), 11f, tone, bold = true).apply {
                setPadding(dp(8), dp(3), dp(8), dp(3))
                background = rounded(ColorUtils.setAlphaComponent(tone, 40), 10)
            })
            kindOf(id)?.let {
                addView(text(kindLabel(it), 13f, p.muted, bold = true), LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { marginStart = dp(10) })
            }
        }, lp(top = 4))
        body.addView(text(
            s(R.string.detail_opened, Api.ago(activity, d.optString("opened_at"))) + " · " + Api.stateLabel(activity, d.optString("state")),
            12f, p.faint,
        ), lp(top = 8))

        // The claim.
        body.addView(text(hypothesis?.optString("statement").orEmpty().ifBlank { s(R.string.incident_no_hypothesis) }, 17f, p.ink).apply {
            setLineSpacing(0f, 1.25f)
            setTextIsSelectable(true)
        }, lp(top = 12))
        hypothesis?.optDouble("confidence")?.takeIf { !it.isNaN() }?.let {
            body.addView(text(s(R.string.detail_confidence, (it * 100).toInt()), 12f, p.muted), lp(top = 8))
        }

        // How it unfolded.
        val chain = d.optJSONArray("causal_chain")
        if (chain != null && chain.length() > 0) {
            body.addView(text(s(R.string.detail_what), 16f, p.ink, bold = true), lp(top = 22))
            for (i in 0 until chain.length()) {
                val step = chain.optJSONObject(i) ?: continue
                val entity = step.optJSONObject("entity")
                val name = entity?.optString("name").orEmpty().ifBlank { entity?.optString("id").orEmpty() }
                val technique = step.optString("attack_technique").takeIf { it.isNotBlank() && it != "null" }
                body.addView(LinearLayout(activity).apply {
                    orientation = LinearLayout.HORIZONTAL
                    setPadding(dp(14), dp(12), dp(14), dp(12))
                    background = rounded(p.panel, 16, p.edge)
                    addView(text("${i + 1}", 13f, p.astra, bold = true).apply {
                        gravity = Gravity.CENTER
                        background = rounded(ColorUtils.setAlphaComponent(p.astra, 36), 12)
                    }, LinearLayout.LayoutParams(dp(26), dp(26)))
                    addView(LinearLayout(activity).apply {
                        orientation = LinearLayout.VERTICAL
                        addView(text(name, 14f, p.ink, bold = true))
                        addView(text(step.optString("transition"), 13f, p.muted), lp(top = 2))
                        if (technique != null) {
                            addView(text("ATT&CK $technique ↗", 12f, p.astra, bold = true).apply {
                                setPadding(0, dp(4), 0, 0)
                                isClickable = true
                                setOnClickListener {
                                    val path = technique.replace('.', '/')
                                    activity.openOutside(android.net.Uri.parse("https://attack.mitre.org/techniques/$path/"))
                                }
                            })
                        }
                    }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { marginStart = dp(12) })
                }, lp(top = 8))
            }
        }

        // The records it rests on.
        val sources = d.optJSONArray("sources")
        if (sources != null && sources.length() > 0) {
            body.addView(text(s(R.string.detail_sources), 16f, p.ink, bold = true), lp(top = 22))
            for (i in 0 until sources.length()) {
                val source = sources.optJSONObject(i) ?: continue
                val url = source.optString("url").takeIf { it.startsWith("https://") }
                body.addView(LinearLayout(activity).apply {
                    orientation = LinearLayout.VERTICAL
                    setPadding(dp(14), dp(12), dp(14), dp(12))
                    background = ripple(rounded(p.panel, 16, p.edge))
                    if (url != null) pressable { activity.openOutside(android.net.Uri.parse(url)) }
                    addView(text(source.optString("title") + if (url != null) "  ↗" else "", 14f, if (url != null) p.astra else p.ink, bold = true))
                    source.optString("publisher").takeIf { it.isNotBlank() }?.let { addView(text(it, 12f, p.muted), lp(top = 2)) }
                }, lp(top = 8))
            }
        }

        // The evidence ids the claim cites.
        val evidence = hypothesis?.optJSONArray("evidence")
        if (evidence != null && evidence.length() > 0) {
            body.addView(text(s(R.string.detail_evidence), 16f, p.ink, bold = true), lp(top = 22))
            body.addView(text((0 until evidence.length()).joinToString("\n") { evidence.optString(it) }, 12f, p.muted).apply {
                typeface = android.graphics.Typeface.MONOSPACE
                setTextIsSelectable(true)
            }, lp(top = 6))
        }

        // Everything else, on the site.
        body.addView(LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = ripple(rounded(p.ground, 18, p.edge))
            pressable { activity.openWebPage("/incidents/$id") }
            addView(text(s(R.string.detail_full) + "  ↗", 15f, p.ink, bold = true))
            addView(text(s(R.string.detail_full_body), 12f, p.muted), lp(top = 2))
        }, lp(top = 22))
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
        val PAST_KINDS = listOf("ALL", "KEV", "NVD", "BREACH", "RW", "CAMPAIGN", "PKG")
    }
}

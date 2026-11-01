package app.pashupatastra

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Typeface
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.TextUtils
import android.text.method.LinkMovementMethod
import android.text.style.LeadingMarginSpan
import android.text.style.StyleSpan
import android.text.style.URLSpan
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.inputmethod.EditorInfo
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.Toast
import androidx.core.graphics.ColorUtils
import androidx.core.widget.NestedScrollView
import org.json.JSONArray
import org.json.JSONObject

/**
 * Sati AI, native: a phone chat over the API's `/agent/ask`.
 *
 * The website's /ask page is the full console (the nine specialists, live model runs,
 * drawn verdicts) and it is heavy for a phone: slow to open, and on the CI emulator the
 * memory it took coincided with Play services dying and the app going with it (runs
 * 41328701921, 41329886458). The app's tab is this instead: opens at once, asks Sati,
 * which routes the question to its own models (no outside model), and renders the answer
 * with every ID and source as a link. The full console is one tap away.
 */
class AskScreen(activity: MainActivity) : NativeScreen(activity) {

    private class Turn(val question: String, var answer: String? = null, var area: String = "", var error: String? = null)

    override val view = FrameLayout(activity)
    private val root = LinearLayout(activity)
    private val scroll = NestedScrollView(activity)
    private val column = LinearLayout(activity)
    private val composer = LinearLayout(activity)
    private val input = EditText(activity)
    private val send = FrameLayout(activity)
    private val note = text("", 11f, 0)
    private val turns = mutableListOf<Turn>()
    private var busy = false

    init {
        root.orientation = LinearLayout.VERTICAL
        column.orientation = LinearLayout.VERTICAL
        column.setPadding(dp(16), dp(12), dp(16), dp(16))
        scroll.isVerticalScrollBarEnabled = false
        scroll.overScrollMode = View.OVER_SCROLL_NEVER
        scroll.addView(column, FrameLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        root.addView(scroll, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))

        input.apply {
            hint = "Ask about an attack, a technique, a defence or a CVE…"
            textSize = 15f
            maxLines = 5
            minHeight = dp(48)
            background = null
            setPadding(dp(16), dp(10), dp(8), dp(10))
            imeOptions = EditorInfo.IME_ACTION_SEND
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES or
                android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE
            setOnEditorActionListener { _, action, _ ->
                if (action == EditorInfo.IME_ACTION_SEND) { submit(); true } else false
            }
        }
        send.apply {
            contentDescription = "Send"
            isClickable = true
            setOnClickListener { submit() }
            addView(icon(R.drawable.ic_back, 0, 18).apply { rotation = 90f }, FrameLayout.LayoutParams(dp(18), dp(18), Gravity.CENTER))
        }
        composer.apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(4), dp(4), dp(6), dp(4))
            addView(input, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
            addView(send, LinearLayout.LayoutParams(dp(40), dp(40)))
        }
        val bottom = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(8), dp(12), dp(8))
            addView(composer, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
            note.text = "Questions are kept in the public audit trail, so leave out personal details. Sati cannot act."
            addView(note, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(6); marginStart = dp(4) })
        }
        root.addView(bottom, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        view.addView(root, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        applyPalette()
    }

    override fun refreshIfStale() = Unit

    override fun toTop() {
        if (scroll.scrollY > 0) scroll.smoothScrollTo(0, 0) else input.requestFocus()
    }

    override fun applyPalette() {
        view.setBackgroundColor(p.ground)
        composer.background = rounded(p.panel, 24, p.edge)
        input.setTextColor(p.ink)
        input.setHintTextColor(p.faint)
        send.background = rounded(p.astra, 20)
        (send.getChildAt(0) as? android.widget.ImageView)?.imageTintList = android.content.res.ColorStateList.valueOf(p.ground)
        note.setTextColor(p.faint)
        render()
    }

    // --- the conversation -----------------------------------------------------

    private fun render() {
        column.removeAllViews()
        if (turns.isEmpty()) {
            welcome()
        } else {
            column.addView(LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.END
                addView(link("New chat") { turns.clear(); render() })
            }, lp())
            turns.forEach { turn ->
                column.addView(userBubble(turn.question), lp(top = 10))
                column.addView(replyBubble(turn), lp(top = 8))
            }
        }
        scroll.post { if (turns.isNotEmpty()) scroll.fullScroll(View.FOCUS_DOWN) }
    }

    private fun welcome() {
        column.addView(LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(18), dp(20), dp(18))
            background = android.graphics.drawable.GradientDrawable(
                android.graphics.drawable.GradientDrawable.Orientation.TL_BR,
                intArrayOf(ColorUtils.setAlphaComponent(p.astra, 60), p.panel, p.panel),
            ).apply {
                cornerRadius = dp(24).toFloat()
                setStroke(dp(1), ColorUtils.setAlphaComponent(p.astra, 90))
            }
            addView(LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                addView(icon(R.drawable.ic_chat, p.astra, 20))
                addView(text("Sati AI", 15f, p.astra, bold = true), LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { marginStart = dp(8) })
            })
            addView(text("Ask Sati, the investigation agent", 19f, p.ink, bold = true), lp(top = 10))
            addView(text(
                "About an attack, a technique, a defence or a CVE. Sati routes your question to its own specialist models and every answer cites its sources. It can propose, never act.",
                14f, p.muted,
            ).apply { setLineSpacing(0f, 1.2f) }, lp(top = 4))
        }, lp())

        column.addView(text("Try one", 13f, p.faint, bold = true).apply { setPadding(dp(4), 0, 0, 0) }, lp(top = 20))
        SUGGESTIONS.forEach { (question, hint) ->
            column.addView(LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(16), dp(14), dp(14), dp(14))
                background = ripple(rounded(p.panel, 18, p.edge))
                pressable { ask(question) }
                contentDescription = question
                addView(LinearLayout(activity).apply {
                    orientation = LinearLayout.VERTICAL
                    addView(text(question, 15f, p.ink, bold = true))
                    addView(text(hint, 12f, p.muted), lp(top = 2))
                }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
                addView(text("→", 16f, p.faint), LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { marginStart = dp(8) })
            }, lp(top = 8))
        }

        // The full console: the nine specialists, live runs on held-out data, drawn verdicts.
        column.addView(LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(14), dp(14), dp(14))
            background = ripple(rounded(p.ground, 18, p.edge))
            pressable { activity.open("/ask?full=1") }
            addView(icon(R.drawable.ic_cube, p.astra, 22))
            addView(LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                addView(text("Open the full Sati AI", 15f, p.ink, bold = true))
                addView(text("All nine specialists, live model runs and drawn verdicts", 12f, p.muted), lp(top = 2))
            }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { marginStart = dp(12) })
            addView(text("↗", 16f, p.faint))
        }, lp(top = 20))
    }

    private fun userBubble(question: String): View = LinearLayout(activity).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.END
        addView(text(question, 15f, p.ink).apply {
            setPadding(dp(14), dp(10), dp(14), dp(10))
            background = rounded(ColorUtils.setAlphaComponent(p.astra, 46), 18)
            maxWidth = (activity.resources.displayMetrics.widthPixels * 0.8).toInt()
        })
    }

    private fun replyBubble(turn: Turn): View = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(16), dp(12), dp(16), dp(12))
        background = rounded(p.panel, 18, p.edge)
        addView(LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(text("S", 11f, p.ground, bold = true).apply {
                gravity = Gravity.CENTER
                background = rounded(p.astra, 10)
            }, LinearLayout.LayoutParams(dp(20), dp(20)))
            addView(text(byline(turn), 12f, p.muted, bold = true), LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { marginStart = dp(8) })
        })
        val answer = turn.answer
        val error = turn.error
        when {
            error != null -> {
                addView(text(error, 14f, p.warn), lp(top = 8))
                addView(link("Try again") { turns.remove(turn); ask(turn.question) }, lp(top = 8))
            }
            answer == null -> addView(typing(), lp(top = 10))
            else -> {
                addView(text("", 15f, p.ink).apply {
                    text = format(answer)
                    setLineSpacing(0f, 1.2f)
                    setLinkTextColor(p.astra)
                    movementMethod = LinkMovementMethod.getInstance()
                }, lp(top = 8))
                addView(LinearLayout(activity).apply {
                    orientation = LinearLayout.HORIZONTAL
                    addView(link("Copy") {
                        val clip = activity.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        clip.setPrimaryClip(ClipData.newPlainText("Sati AI", answer))
                        Toast.makeText(activity, "Copied", Toast.LENGTH_SHORT).show()
                    })
                    addView(link("Share") { activity.share("Sati AI: " + turn.question, turn.question + "\n\n" + answer) },
                        LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { marginStart = dp(16) })
                }, lp(top = 10))
            }
        }
    }

    /** Three dots that pulse while Sati answers. */
    private fun typing(): View = LinearLayout(activity).apply {
        orientation = LinearLayout.HORIZONTAL
        contentDescription = "Sati is answering"
        repeat(3) { i ->
            addView(View(activity).apply {
                background = rounded(p.faint, 4)
                alpha = 0.3f
                animate().alpha(1f).setStartDelay(i * 180L).setDuration(450).withEndAction(object : Runnable {
                    override fun run() {
                        if (!isAttachedToWindow) return
                        animate().alpha(if (alpha > 0.6f) 0.3f else 1f).setStartDelay(0).setDuration(450).withEndAction(this).start()
                    }
                }).start()
            }, LinearLayout.LayoutParams(dp(8), dp(8)).apply { if (i > 0) marginStart = dp(6) })
        }
    }

    private fun link(label: String, onClick: () -> Unit) = text(label, 13f, p.astra, bold = true).apply {
        setPadding(0, dp(4), 0, dp(4))
        isClickable = true
        setOnClickListener {
            it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
            onClick()
        }
    }

    /** The answer's byline, job first (adr/Navadurga): what answered, then which model. */
    private fun byline(turn: Turn): String {
        val job = when (turn.area) {
            "brahmacharini" -> "Technique match"
            "skandamata" -> "Defences"
            "kushmanda" -> "Explanation"
            "katyayani" -> "Root cause"
            else -> null
        }
        val model = turn.area.replaceFirstChar { it.uppercase() }
        return when {
            turn.answer == null && turn.error == null -> "Sati is answering"
            job != null -> "Sati · $job · $model"
            turn.area.isNotBlank() -> "Sati · $model"
            else -> "Sati"
        }
    }

    // --- asking -------------------------------------------------------------------

    private fun submit() {
        val question = input.text.toString().trim()
        if (question.isEmpty()) return
        input.setText("")
        ask(question)
    }

    fun ask(question: String) {
        if (busy) return
        busy = true
        val history = JSONArray().apply {
            turns.filter { it.answer != null }.takeLast(6).forEach {
                put(JSONObject().put("question", it.question).put("answer", it.answer))
            }
        }
        val turn = Turn(question)
        turns.add(turn)
        render()
        val body = JSONObject().put("message", question).put("history", history).toString()
        Api.CHAT.execute {
            val (status, text) = runCatching { Api.post("/agent/ask", body) }.getOrElse { 0 to "" }
            activity.runOnUiThread {
                busy = false
                if (activity.isDestroyed) return@runOnUiThread
                val json = runCatching { JSONObject(text) }.getOrNull()
                when {
                    status in 200..299 && json != null -> {
                        turn.answer = json.optString("answer").ifBlank { "Sati had no answer to that." }
                        turn.area = json.optString("area")
                    }
                    status == 0 -> turn.error = "Could not reach Sati. Check the connection and try again."
                    status == 429 -> turn.error = json?.optString("detail")?.ifBlank { null } ?: "Too many questions this minute. Try again shortly."
                    else -> turn.error = json?.optString("detail")?.ifBlank { null } ?: "Sati is unavailable right now."
                }
                render()
            }
        }
    }

    // --- the answer, formatted ------------------------------------------------------

    /**
     * The answer's light markdown (bold, bullets) as text styles, and every source and
     * identifier as a link: URLs, CVE ids to NVD, CAPEC ids to CAPEC, ATT&CK technique
     * ids to ATT&CK (as the site does, lib/answerlinks.ts).
     */
    private fun format(answer: String): CharSequence {
        val out = SpannableStringBuilder()
        val lines = answer.trim().lines()
        lines.forEachIndexed { index, raw ->
            val bullet = raw.startsWith("- ") || raw.startsWith("* ")
            var rest = if (bullet) raw.drop(2) else raw
            val start = out.length
            if (bullet) out.append("•  ")
            while (true) {
                val open = rest.indexOf("**")
                val close = if (open < 0) -1 else rest.indexOf("**", open + 2)
                if (open < 0 || close < 0) break
                out.append(rest.substring(0, open))
                val boldStart = out.length
                out.append(rest.substring(open + 2, close))
                out.setSpan(StyleSpan(Typeface.BOLD), boldStart, out.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                rest = rest.substring(close + 2)
            }
            out.append(rest)
            if (bullet) out.setSpan(LeadingMarginSpan.Standard(0, dp(18)), start, out.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            if (index < lines.lastIndex) out.append('\n')
        }
        fun linkAll(pattern: Regex, url: (MatchResult) -> String) {
            pattern.findAll(out.toString()).forEach { m ->
                val s = m.range.first
                val e = m.range.last + 1
                if (out.getSpans(s, e, URLSpan::class.java).isEmpty()) {
                    out.setSpan(URLSpan(url(m)), s, e, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                }
            }
        }
        linkAll(Regex("https://[^\\s·]+[^\\s·.,;)]")) { it.value }
        linkAll(Regex("\\bCVE-\\d{4}-\\d{4,}\\b")) { "https://nvd.nist.gov/vuln/detail/${it.value}" }
        linkAll(Regex("\\bCAPEC-(\\d+)\\b")) { "https://capec.mitre.org/data/definitions/${it.groupValues[1]}.html" }
        linkAll(Regex("\\bT(\\d{4})(?:\\.(\\d{3}))?\\b")) {
            val sub = it.groupValues[2]
            "https://attack.mitre.org/techniques/T${it.groupValues[1]}/" + if (sub.isNotEmpty()) "$sub/" else ""
        }
        return out
    }

    private companion object {
        /** The same openers as the site's /ask, each with what it shows. */
        val SUGGESTIONS = listOf(
            "What is SQL injection?" to "The attack, and the fixes that stop it",
            "How do we defend against ransomware?" to "Defences, most relevant first",
            "What should we do about Log4Shell?" to "CISA's required action, cited",
            "How do we defend against phishing emails?" to "Training first, then the controls",
            "Which ATT&CK technique is a scheduled task that runs malware at every logon?" to "Names the technique",
        )
    }
}

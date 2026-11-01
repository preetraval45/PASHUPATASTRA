package app.pashupatastra

import android.content.Context
import org.json.JSONArray
import java.text.DateFormat
import java.util.Date
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.Executors

/**
 * The public API, as the native screens read it: the same endpoints the site
 * reads (apps/web/lib/api.ts), from BuildConfig.API_URL. Read-only; nothing
 * here can act, so nothing here bypasses Dharma.
 */
object Api {

    class Incident(
        val id: String,
        val state: String,
        val severity: String,
        val openedAt: String,
        val statement: String,
        val services: List<String> = emptyList(),
        val simulated: Boolean = false,
    )

    val IO = Executors.newSingleThreadExecutor()

    /** A response, and whether it came from the network now (`fresh`) or from the phone's copy. */
    class Fetched(val body: String, val at: Long, val fresh: Boolean)

    /**
     * Reads `path`, keeping the answer on the phone. When the network fails, the last
     * answer comes back marked not fresh, with its time, so a screen can show it and
     * say how old it is rather than show nothing. Nothing is invented: no copy, null.
     */
    fun fetch(context: Context, path: String): Fetched? {
        val prefs = context.getSharedPreferences(CACHE, Context.MODE_PRIVATE)
        return try {
            val body = get(path)
            val now = System.currentTimeMillis()
            prefs.edit().putString(path, body).putLong("$path@", now).apply()
            Fetched(body, now, fresh = true)
        } catch (error: Exception) {
            recall(context, path)
        }
    }

    /** The phone's copy of `path`, without asking the network: for the first paint. */
    fun recall(context: Context, path: String): Fetched? {
        val prefs = context.getSharedPreferences(CACHE, Context.MODE_PRIVATE)
        val body = prefs.getString(path, null) ?: return null
        return Fetched(body, prefs.getLong("$path@", 0L), fresh = false)
    }

    /** "3:41 PM", in the phone's own format. */
    fun clock(at: Long): String = DateFormat.getTimeInstance(DateFormat.SHORT).format(Date(at))

    private const val CACHE = "api-cache"

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
            services = o.optJSONObject("impact")?.optJSONArray("affected_services")?.let { a ->
                (0 until a.length()).map { a.optString(it) }
            }.orEmpty(),
            simulated = !o.isNull("simulation_of") && o.optString("simulation_of").isNotBlank(),
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

package app.pashupatastra

import android.content.Context
import org.json.JSONObject

/**
 * Who is signed in, as the site's account system says (services/api/app/accounts.py).
 *
 * Signing in, signing up and signing out happen on the site's own pages inside the app
 * (/login, /signup, /account), which keep the session token in the WebView's storage
 * (`pashu.session`, apps/web/lib/account.ts). The app reads it from there after each page
 * load (MainActivity.syncFromPage) and keeps a copy in its private storage, so the native
 * screens can greet the person and show their company before any page has loaded.
 */
object Session {

    class Org(
        val id: String,
        val name: String,
        val role: String,
        val required: List<String>,
        val due: String?,
        val requiredPassed: Int,
        var policiesToRead: Int? = null,
    )

    class Me(val name: String, val email: String?, val guest: Boolean, val org: Org?, val platformAdmin: Boolean)

    private const val PREFS = "app"
    private const val KEY = "session.token"

    fun token(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)

    /** Stores the page's token; true when it changed (signed in, out, or as someone else). */
    fun set(context: Context, token: String?): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY, null) == token) return false
        prefs.edit().apply { if (token == null) remove(KEY) else putString(KEY, token) }.apply()
        return true
    }

    /**
     * The account and its first company, from `/me`, with how many of the company's
     * policies are still unacknowledged. Null when signed out; a revoked token is forgotten.
     * Runs on a background thread.
     */
    fun load(context: Context): Me? {
        val token = token(context) ?: return null
        val me = try {
            JSONObject(Api.get("/me", token))
        } catch (expired: Api.Unauthorized) {
            set(context, null)
            return null
        } catch (other: Exception) {
            return null
        }
        val user = me.optJSONObject("user") ?: return null
        val training = me.optJSONObject("training")
        val passed = mutableSetOf<String>()
        training?.keys()?.forEach { slug -> if (training.optJSONObject(slug)?.optBoolean("passed") == true) passed.add(slug) }
        val org = me.optJSONArray("orgs")?.optJSONObject(0)?.let { o ->
            val settings = o.optJSONObject("settings")
            val required = settings?.optJSONArray("required")?.let { a -> (0 until a.length()).map { a.optString(it) } }.orEmpty()
            Org(
                id = o.optString("id"),
                name = o.optString("name"),
                role = o.optString("role"),
                required = required,
                due = settings?.optString("due")?.takeIf { it.isNotBlank() && it != "null" },
                requiredPassed = required.count { it in passed },
            )
        }
        if (org != null) {
            org.policiesToRead = runCatching {
                val list = JSONObject(Api.get("/orgs/${org.id}/policies", token)).optJSONArray("policies")
                (0 until (list?.length() ?: 0)).count { list!!.optJSONObject(it).isNull("acknowledged") }
            }.getOrNull()
        }
        return Me(
            name = user.optString("name").ifBlank { "there" },
            email = user.optString("email").takeIf { it.isNotBlank() && it != "null" },
            guest = user.optString("provider") == "guest",
            org = org,
            platformAdmin = me.optBoolean("platform_admin"),
        )
    }
}

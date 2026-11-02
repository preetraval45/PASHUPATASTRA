package app.pashupatastra

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.webkit.WebView
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.graphics.ColorUtils
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.google.android.material.bottomsheet.BottomSheetBehavior
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.materialswitch.MaterialSwitch

/**
 * The Pashupatastra app: native bars around the live site.
 *
 * The pages come from the deployed site, so whatever ships to main shows up in
 * the app with no rebuild. The frame is native, so it behaves as a phone app
 * rather than a website saved to the home screen: a Material top bar with the
 * page's name, back arrow, search and share; a bottom tab bar whose tabs each
 * keep their own page and history; every other section in a native sheet;
 * edge-to-edge drawing; and native loading and offline states. The site hides
 * its own header and tab bar when the user agent says PashupatastraNative.
 *
 * Links that leave the site open in the phone's browser, so the app never
 * becomes a browser for someone else's pages.
 */
class MainActivity : AppCompatActivity() {

    private val site: Uri = Uri.parse(BuildConfig.SITE_URL)

    private lateinit var root: LinearLayout
    private lateinit var appBar: LinearLayout
    private lateinit var toolbar: MaterialToolbar
    private lateinit var progress: ProgressBar
    private lateinit var content: FrameLayout
    private lateinit var nav: BottomNavigationView
    private lateinit var topLine: View
    private lateinit var bottomLine: View
    private lateinit var lock: AppLock

    private val tabs = LinkedHashMap<Int, WebTab>()
    private var current: WebTab? = null
    /** Tabs whose first screen is native, drawn from the API; their pages open above them. */
    private val natives = HashMap<Int, NativeScreen>()

    /** Live attacks (FeedScreen): a native screen reached from More, so the tab bar marks More. */
    private val feed = View.generateViewId()
    private var shown: View? = null
    private var currentId = 0

    var palette: Palette = Palette.DARK
        private set

    /** The signed-in account, as Home last loaded it (Session.load); null when signed out or not yet known. */
    var me: Session.Me? = null

    private val notifyPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (!granted) {
            prefs().edit().putBoolean(IncidentWatch.ENABLED, false).apply()
        }
    }

    /** A place in the site, as the website's rail lists it (apps/web/components/sidebar.tsx). */
    private class Dest(val path: String, val label: String, val icon: Int)

    private val sections: List<Pair<String, List<Dest>>> by lazy {
        listOf(
            "Start" to listOf(
                Dest("/", "Home", R.drawable.ic_home),
                Dest("/how-it-works", "How it works", R.drawable.ic_book),
            ),
            "Operate" to listOf(
                Dest("/overview", "Overview", R.drawable.ic_grid),
                Dest("/incidents", "Incidents", R.drawable.ic_alert),
                Dest("/ask", "Sati AI", R.drawable.ic_chat),
                Dest("/observatory", "Observatory", R.drawable.ic_radar),
            ),
            "Analyze" to listOf(
                Dest("/analytics", "Analytics", R.drawable.ic_chart),
                Dest("/world", "World threats", R.drawable.ic_globe),
                Dest("/models", "Sati models", R.drawable.ic_cube),
            ),
            "Respond" to listOf(
                Dest("/actions", "Actions", R.drawable.ic_bolt),
                Dest("/detections", "Detections", R.drawable.ic_shield),
                Dest("/attack", "ATT&CK coverage", R.drawable.ic_matrix),
            ),
            "Learn" to listOf(
                Dest("/training", "Training", R.drawable.ic_cap),
                Dest("/findings", "Findings", R.drawable.ic_news),
                Dest("/evaluation", "Evaluation", R.drawable.ic_check),
            ),
            "More" to listOf(
                Dest("/impact", "Impact", R.drawable.ic_pulse),
                Dest("/press", "Press", R.drawable.ic_news),
                Dest("/search", "Search", R.drawable.ic_search),
                Dest("/privacy", "Privacy", R.drawable.ic_shield),
            ),
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        if (Build.VERSION.SDK_INT >= 29) window.isNavigationBarContrastEnforced = false
        setContentView(R.layout.activity_main)

        root = findViewById(R.id.root)
        appBar = findViewById(R.id.appbar)
        toolbar = findViewById(R.id.toolbar)
        progress = findViewById(R.id.progress)
        content = findViewById(R.id.content)
        nav = findViewById(R.id.nav)
        topLine = findViewById(R.id.topline)
        bottomLine = findViewById(R.id.bottomline)
        currentId = R.id.tab_home
        lock = AppLock(this, findViewById(android.R.id.content))
        applySecure()

        palette = if (prefs().getString(THEME, "dark") == "light") Palette.LIGHT else Palette.DARK

        toolbar.inflateMenu(R.menu.toolbar)
        toolbar.setNavigationContentDescription(R.string.action_back)
        toolbar.setNavigationOnClickListener { onBackPressedDispatcher.onBackPressed() }
        toolbar.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.action_search -> { open("/search"); true }
                R.id.action_share -> {
                    val tab = current
                    if (tab != null) share(titleOf(tab), tab.web.url ?: site.toString())
                    else share(getString(R.string.app_name), site.toString())
                    true
                }
                else -> false
            }
        }

        nav.setOnItemSelectedListener { item ->
            nav.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
            if (item.itemId == R.id.tab_more) {
                showMore()
                false
            } else {
                show(item.itemId)
                true
            }
        }
        nav.setOnItemReselectedListener { item ->
            nav.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
            val id = item.itemId
            when {
                id == R.id.tab_more -> showMore()
                hasNative(id) && tabs[id] != null -> closePage(id)
                hasNative(id) -> native(id)?.toTop()
                else -> tabs[id]?.toRoot()
            }
        }

        // Edge to edge: the bars sit under the status and navigation bars, padded clear of them.
        // While the keyboard is up the tab bar steps aside and the page ends at the keyboard,
        // so Sati AI's input stays visible as it is typed in.
        ViewCompat.setOnApplyWindowInsetsListener(root) { _, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            val typing = insets.isVisible(WindowInsetsCompat.Type.ime())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            appBar.setPadding(bars.left, bars.top, bars.right, 0)
            nav.setPadding(bars.left, 0, bars.right, bars.bottom)
            nav.visibility = if (typing) View.GONE else View.VISIBLE
            bottomLine.visibility = nav.visibility
            root.setPadding(0, 0, 0, if (typing) ime.bottom else 0)
            WindowInsetsCompat.CONSUMED
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val tab = current
                when {
                    tab != null && tab.web.canGoBack() -> tab.web.goBack()
                    tab != null && hasNative(currentId) -> closePage(currentId)
                    currentId != R.id.tab_home -> select(R.id.tab_home)
                    else -> moveTaskToBack(true)
                }
            }
        })

        applyPalette()
        route(intent)

        // Alerts are on unless turned off; the first launch asks for permission once, after the app has drawn.
        val alerts = prefs().getBoolean(IncidentWatch.ENABLED, true)
        IncidentWatch.schedule(this)
        if (!prefs().getBoolean(ONBOARDED, false)) {
            // First launch: three short screens, ending with alerts offered and explained.
            prefs().edit().putBoolean(ONBOARDED, true).putBoolean(ASKED, true).apply()
            Onboarding(this, findViewById(android.R.id.content)) { on ->
                prefs().edit().putBoolean(IncidentWatch.ENABLED, on).apply()
                if (on) askForAlerts()
            }.show()
        } else if (alerts && !prefs().getBoolean(ASKED, false)) {
            prefs().edit().putBoolean(ASKED, true).apply()
            root.postDelayed({ askForAlerts() }, 1500)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        route(intent)
    }

    override fun onStart() {
        super.onStart()
        lock.onStart()
    }

    override fun onStop() {
        lock.onStop()
        super.onStop()
    }

    /** With the app lock on, the window is secure: no screenshots, and a blank recent-apps preview. */
    private fun applySecure() {
        if (lock.enabled) window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        else window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
    }

    override fun onResume() {
        super.onResume()
        if (current == null) native(currentId)?.refreshIfStale()
    }

    /**
     * Android is short of memory: let go of every page that is not on screen. Each is a
     * whole browser renderer; a tab whose page was dropped loads its first page again when
     * it is next opened. Heavy pages held in hidden tabs were what the emulator runs were
     * short of when Play services died and Android closed the app with it.
     */
    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        if (level < android.content.ComponentCallbacks2.TRIM_MEMORY_RUNNING_LOW) return
        tabs.entries.filter { it.value !== current }.map { it.key }.forEach { dropPage(it) }
    }

    override fun onDestroy() {
        tabs.values.forEach { it.web.destroy() }
        super.onDestroy()
    }

    // --- tabs ---------------------------------------------------------------

    private fun rootPath(id: Int): String = when (id) {
        feed -> "/observatory"
        R.id.tab_incidents -> "/incidents"
        R.id.tab_ask -> "/ask"
        R.id.tab_learn -> "/training"
        else -> "/"
    }

    /** Which tab a path belongs to; anything not under the four tabs opens in More's own stack. */
    private fun tabFor(path: String): Int = when {
        path == "/observatory" -> feed
        path == "" || path == "/" -> R.id.tab_home
        path.startsWith("/incidents") -> R.id.tab_incidents
        path.startsWith("/ask") -> R.id.tab_ask
        path.startsWith("/training") || path.startsWith("/blue-team") -> R.id.tab_learn
        else -> R.id.tab_more
    }

    private fun url(path: String): String = BuildConfig.SITE_URL.trimEnd('/') + path

    private fun tab(id: Int): WebTab = tabs.getOrPut(id) {
        WebTab(this).also {
            it.view.visibility = View.GONE
            content.addView(it.view, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        }
    }

    /** Selects a tab from code, which moves the tab bar's highlight too. */
    private fun select(id: Int, url: String? = null) {
        show(id, url)
        nav.menu.findItem(if (id == feed) R.id.tab_more else id)?.isChecked = true
    }

    private fun hasNative(id: Int) = id == R.id.tab_home || id == R.id.tab_incidents || id == R.id.tab_ask || id == feed

    /** The tab's native first screen, made on first use. */
    private fun native(id: Int): NativeScreen? {
        if (!hasNative(id)) return null
        return natives.getOrPut(id) {
            val screen = when (id) {
                R.id.tab_home -> HomeScreen(this)
                feed -> FeedScreen(this)
                R.id.tab_ask -> AskScreen(this)
                else -> IncidentsScreen(this)
            }
            screen.view.visibility = View.GONE
            content.addView(screen.view, 0, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
            screen
        }
    }

    /** Removes the page open above a native screen at once (a new page replaces it). */
    private fun dropPage(id: Int) {
        val tab = tabs.remove(id) ?: return
        if (current === tab) current = null
        if (shown === tab.view) shown = null
        content.removeView(tab.view)
        tab.web.destroy()
    }

    /** Back from a page to the native list beneath it: the page slides away, the list is where it was. */
    private fun closePage(id: Int) {
        val screen = native(id) ?: return
        val tab = tabs.remove(id)
        current = null
        currentId = id
        screen.view.animate().cancel()
        screen.view.alpha = 1f
        screen.view.translationY = 0f
        screen.view.visibility = View.VISIBLE
        if (shown !== screen.view && shown !== tab?.view) shown?.visibility = View.GONE
        shown = screen.view
        updateChrome()
        if (tab != null) {
            tab.view.animate().translationX(tab.view.width.toFloat()).setDuration(200).withEndAction {
                content.removeView(tab.view)
                tab.web.destroy()
            }.start()
        }
    }

    /**
     * Shows a tab, loading `url` in it if given, or its first page if it has none yet.
     * Home and Incidents start native (HomeScreen, IncidentsScreen); a page opened from
     * them slides in above, as a native detail screen does. The other tabs are pages.
     */
    private fun show(id: Int, url: String? = null) {
        val next: View
        val screen = native(id)
        if (screen != null && url == null && tabs[id] == null) {
            if (shown !== screen.view) screen.refreshIfStale()
            current = null
            next = screen.view
        } else if (screen != null && url != null) {
            // A fresh page above the list, so back always returns to the list.
            dropPage(id)
            val tab = tab(id)
            tab.load(url)
            if (shown != null && shown !== screen.view) shown?.visibility = View.GONE
            screen.view.visibility = View.VISIBLE
            tab.view.visibility = View.VISIBLE
            tab.view.translationX = content.width.toFloat()
            tab.view.animate().translationX(0f).setDuration(220).withEndAction {
                if (shown === tab.view) screen.view.visibility = View.GONE
            }.start()
            current = tab
            shown = tab.view
            currentId = id
            tabs.values.forEach { if (it === current) it.web.onResume() else it.web.onPause() }
            updateChrome()
            return
        } else {
            val tab = tab(id)
            when {
                url != null -> tab.load(url)
                tab.isEmpty -> tab.load(url(rootPath(id)))
            }
            current = tab
            next = tab.view
        }
        // Only the page on screen runs: hidden tabs' scripts, timers and animations pause.
        tabs.values.forEach { if (it === current) it.web.onResume() else it.web.onPause() }
        if (shown !== next) {
            shown?.visibility = View.GONE
            // A list left visible under a page still sliding in must not show through another tab.
            natives.values.forEach { if (it.view !== next) it.view.visibility = View.GONE }
            next.alpha = 0f
            next.translationY = dp(8).toFloat()
            next.visibility = View.VISIBLE
            next.animate().alpha(1f).translationY(0f).setDuration(180).start()
            shown = next
        }
        currentId = id
        updateChrome()
    }

    /**
     * A place in the site, opened where it belongs: its tab if it has one, More's stack if not.
     * A tab's own first page just selects the tab, so it keeps where the user was in it.
     */
    fun open(path: String) {
        if (path.startsWith("/incidents?severity=")) {
            dropPage(R.id.tab_incidents)
            select(R.id.tab_incidents)
            (native(R.id.tab_incidents) as? IncidentsScreen)?.show(path.substringAfter("="))
            return
        }
        val id = tabFor(path)
        if (id == R.id.tab_more || (id != R.id.tab_home && path != rootPath(id))) select(id, url(path)) else select(id)
    }

    /** A link to the site opens that page in its tab; a launch with no link resumes where the app was. */
    private fun route(intent: Intent?) {
        val link = intent?.data?.takeIf { isSite(it) }
        if (link == null) {
            select(currentId)
            return
        }
        val path = link.path.orEmpty()
        // "/ask?q=…" asks Sati straight away, in the native chat (shortcuts, shared links, CI).
        val question = if (path.trimEnd('/') == "/ask") link.getQueryParameter("q")?.trim()?.takeIf { it.isNotEmpty() } else null
        if (question != null) {
            dropPage(R.id.tab_ask)
            select(R.id.tab_ask)
            (native(R.id.tab_ask) as? AskScreen)?.ask(question.take(500))
            return
        }
        val id = tabFor(path)
        val atRoot = path.trimEnd('/') == rootPath(id).trimEnd('/')
        if (atRoot && id != R.id.tab_more) select(id) else select(id, link.toString())
    }

    /** The Incidents tab's badge: how many incidents await the owner's approval; hidden at zero. */
    fun setNeedYou(count: Int) {
        if (count > 0) {
            nav.getOrCreateBadge(R.id.tab_incidents).apply {
                number = count
                backgroundColor = palette.warn
                badgeTextColor = palette.ground
            }
        } else {
            nav.removeBadge(R.id.tab_incidents)
        }
    }

    fun onTabChanged(tab: WebTab) {
        if (tab === current) updateChrome()
    }

    private fun updateChrome() {
        val tab = current
        if (tab == null) {
            toolbar.title = when (currentId) {
                R.id.tab_home -> getString(R.string.app_name)
                feed -> getString(R.string.feed_title)
                else -> nav.menu.findItem(currentId)?.title
            }
            toolbar.navigationIcon = null
            progress.visibility = View.INVISIBLE
            return
        }
        toolbar.title = titleOf(tab)
        toolbar.navigationIcon = if (tab.web.canGoBack() || hasNative(currentId)) tinted(R.drawable.ic_back, palette.ink) else null
        if (tab.progress in 1..99) {
            progress.visibility = View.VISIBLE
            progress.progress = tab.progress
        } else {
            progress.visibility = View.INVISIBLE
        }
    }

    /** The page's name, as the site titles it ("Incidents · Pashupatastra"), without the suffix. */
    private fun titleOf(tab: WebTab): String {
        val path = Uri.parse(tab.web.url ?: "").path.orEmpty()
        if (path == "" || path == "/") return getString(R.string.app_name)
        val title = tab.pageTitle.substringBefore(" · ").trim()
        if (title.isNotEmpty() && !title.startsWith("http") && !title.contains(".vercel.app")) return title
        return sections.flatMap { it.second }.firstOrNull { it.path != "/" && path.startsWith(it.path) }?.label
            ?: getString(R.string.app_name)
    }

    fun isSite(uri: Uri): Boolean = uri.scheme == "https" && uri.host == site.host

    fun openOutside(uri: Uri) {
        runCatching { startActivity(Intent(Intent.ACTION_VIEW, uri)) }
    }

    fun share(title: String, url: String) {
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, title.take(200))
            putExtra(Intent.EXTRA_TEXT, url.take(2000))
        }
        startActivity(Intent.createChooser(send, getString(R.string.action_share)))
    }

    // --- More: every section, as a native sheet ------------------------------

    private fun showMore() {
        val p = palette
        val dialog = BottomSheetDialog(this)
        val here = current?.web?.url?.let { Uri.parse(it).path.orEmpty() } ?: rootPath(currentId)

        val list = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(10), dp(16), dp(20))
        }
        list.addView(View(this).apply {
            background = rounded(p.edge, dp(2).toFloat())
        }, LinearLayout.LayoutParams(dp(36), dp(4)).apply { gravity = Gravity.CENTER_HORIZONTAL; bottomMargin = dp(12) })

        // Who is signed in, or the way to sign in (the site's own pages; Session reads the result).
        val account = me
        val signedIn = Session.token(this) != null
        list.addView(LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(12))
            background = RippleDrawable(ColorStateList.valueOf(ColorUtils.setAlphaComponent(p.astra, 60)), rounded(p.ground, dp(18).toFloat(), p.edge), null)
            isClickable = true
            setOnClickListener {
                dialog.dismiss()
                open(if (signedIn) "/account" else "/login")
            }
            val name = account?.name ?: if (signedIn) "Your account" else "Not signed in"
            val detail = when {
                account == null && !signedIn -> "Save your training and join your company"
                account == null -> "Open your account"
                account.guest -> "Guest" + (account.org?.let { " · ${it.name}" } ?: "")
                else -> listOfNotNull(account.email, account.org?.let { "${it.name} · ${it.role}" }).joinToString(" · ")
            }
            contentDescription = "$name. $detail"
            val avatar: View = if (account == null) {
                FrameLayout(this@MainActivity).apply {
                    addView(ImageView(this@MainActivity).apply {
                        setImageResource(R.drawable.ic_user)
                        imageTintList = ColorStateList.valueOf(p.astra)
                    }, FrameLayout.LayoutParams(dp(22), dp(22), Gravity.CENTER))
                }
            } else {
                TextView(this@MainActivity).apply {
                    text = account.name.split(' ').filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }
                    textSize = 15f
                    gravity = Gravity.CENTER
                    typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
                    setTextColor(p.astra)
                }
            }
            avatar.background = rounded(ColorUtils.setAlphaComponent(p.astra, 40), dp(22).toFloat())
            addView(avatar, LinearLayout.LayoutParams(dp(44), dp(44)))
            addView(LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.VERTICAL
                addView(TextView(this@MainActivity).apply {
                    text = name
                    textSize = 16f
                    typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
                    setTextColor(p.ink)
                })
                addView(TextView(this@MainActivity).apply {
                    text = detail
                    textSize = 12f
                    maxLines = 1
                    ellipsize = android.text.TextUtils.TruncateAt.END
                    setTextColor(p.muted)
                })
            }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f).apply { marginStart = dp(12) })
            addView(TextView(this@MainActivity).apply {
                text = if (signedIn) "→" else "Sign in"
                textSize = 14f
                typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
                setTextColor(p.astra)
            })
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { bottomMargin = dp(4) })

        // The workspace (RP-101, RP-106): what this account's role opens, ahead of the product's sections.
        val workspace = buildList {
            add(Dest("/apps", "All apps", R.drawable.ic_grid))
            account?.org?.let { org ->
                add(Dest("/company/${org.id}", org.name, R.drawable.ic_company))
                if (org.role == "owner" || org.role == "admin") add(Dest("/team", "Team", R.drawable.ic_team))
            }
            if (account?.platformAdmin == true) add(Dest("/admin", "Admin", R.drawable.ic_shield))
            if (signedIn) add(Dest("/account", "Account", R.drawable.ic_user))
        }

        for ((title, dests) in listOf("Workspace" to workspace) + sections) {
            list.addView(TextView(this).apply {
                text = title.uppercase()
                textSize = 11f
                letterSpacing = 0.08f
                typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
                setTextColor(p.faint)
                setPadding(dp(4), dp(10), 0, dp(8))
            })
            dests.chunked(3).forEach { row ->
                val line = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
                for (i in 0 until 3) {
                    val params = LinearLayout.LayoutParams(0, dp(84), 1f).apply {
                        if (i > 0) marginStart = dp(8)
                    }
                    val dest = row.getOrNull(i)
                    if (dest == null) {
                        line.addView(View(this), params)
                        continue
                    }
                    val active = if (dest.path == "/") here == "" || here == "/" else here.startsWith(dest.path)
                    line.addView(tile(dest, active) {
                        dialog.dismiss()
                        open(dest.path)
                    }, params)
                }
                list.addView(line, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { bottomMargin = dp(8) })
            }
        }

        // The theme, for the app and the site together.
        list.addView(switchRow(R.drawable.ic_moon, getString(R.string.sheet_dark), p.dark) { dark ->
            useTheme(light = !dark)
            dialog.dismiss()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(12) })
        // Alerts on the phone when an incident needs its owner (IncidentWatch).
        list.addView(switchRow(R.drawable.ic_alert, getString(R.string.sheet_alerts), prefs().getBoolean(IncidentWatch.ENABLED, true)) { on ->
            prefs().edit().putBoolean(IncidentWatch.ENABLED, on).apply()
            if (on) askForAlerts()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(8) })
        // The app lock (AppLock): fingerprint, face or the phone's screen lock.
        list.addView(switchRow(R.drawable.ic_shield, getString(R.string.sheet_lock), lock.enabled) { on ->
            lock.setEnabled(on) {
                applySecure()
                dialog.dismiss()
            }
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(8) })

        // Help (RP-107): a problem report with the facts a fix needs, and email when a support address is set.
        list.addView(actionRow(R.drawable.ic_alert, getString(R.string.sheet_report)) {
            dialog.dismiss()
            reportProblem()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(8) })
        if (BuildConfig.SUPPORT_EMAIL.isNotBlank()) {
            list.addView(actionRow(R.drawable.ic_chat, getString(R.string.sheet_contact)) {
                dialog.dismiss()
                val mail = Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:" + BuildConfig.SUPPORT_EMAIL))
                    .putExtra(Intent.EXTRA_SUBJECT, "Pashupatastra app " + BuildConfig.VERSION_NAME)
                runCatching { startActivity(mail) }
            }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(8) })
        }

        list.addView(TextView(this).apply {
            text = getString(R.string.sheet_build, BuildConfig.VERSION_NAME)
            textSize = 12f
            gravity = Gravity.CENTER
            setTextColor(p.faint)
            setPadding(0, dp(16), 0, 0)
        })

        val scroll = ScrollView(this).apply {
            isVerticalScrollBarEnabled = false
            background = GradientDrawable().apply {
                setColor(p.panel)
                val r = dp(28).toFloat()
                cornerRadii = floatArrayOf(r, r, r, r, 0f, 0f, 0f, 0f)
            }
            addView(list)
        }
        dialog.setContentView(scroll)
        dialog.setOnShowListener {
            dialog.findViewById<View>(com.google.android.material.R.id.design_bottom_sheet)
                ?.background = ColorDrawable(Color.TRANSPARENT)
            dialog.behavior.skipCollapsed = true
            dialog.behavior.state = BottomSheetBehavior.STATE_EXPANDED
        }
        dialog.show()
    }

    /** A tappable row in the More sheet, shaped like the switch rows. */
    private fun actionRow(iconRes: Int, label: String, onClick: () -> Unit): View {
        val p = palette
        return LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = RippleDrawable(ColorStateList.valueOf(ColorUtils.setAlphaComponent(p.astra, 60)), rounded(p.ground, dp(16).toFloat(), p.edge), null)
            isClickable = true
            contentDescription = label
            setOnClickListener {
                it.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                onClick()
            }
            addView(ImageView(this@MainActivity).apply {
                setImageResource(iconRes)
                imageTintList = ColorStateList.valueOf(p.muted)
            }, LinearLayout.LayoutParams(dp(22), dp(22)))
            addView(TextView(this@MainActivity).apply {
                text = label
                textSize = 15f
                setTextColor(p.ink)
                setPadding(dp(14), 0, dp(8), 0)
            }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
            addView(TextView(this@MainActivity).apply {
                text = "↗"
                textSize = 15f
                setTextColor(p.faint)
            })
        }
    }

    /**
     * A problem report as a new issue on the project's tracker, with what a fix needs already filled in:
     * the app's build, Android's version, the phone model and the screen. Nothing personal: no account,
     * no email, no location. The person reads it before sending and can change anything.
     */
    private fun reportProblem() {
        val screen = current?.web?.url?.let { Uri.parse(it).path } ?: rootPath(currentId)
        val body = buildString {
            appendLine("What happened, and what did you expect?")
            appendLine()
            appendLine()
            appendLine("---")
            appendLine("App build: ${BuildConfig.VERSION_NAME}")
            appendLine("Android: ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")
            appendLine("Phone: ${Build.MANUFACTURER} ${Build.MODEL}")
            appendLine("Screen: $screen")
        }
        val issue = Uri.parse("https://github.com/preetraval45/PASHUPATASTRA/issues/new").buildUpon()
            .appendQueryParameter("title", "App: ")
            .appendQueryParameter("labels", "android")
            .appendQueryParameter("body", body)
            .build()
        openOutside(issue)
    }

    private fun switchRow(iconRes: Int, label: String, checked: Boolean, onChange: (Boolean) -> Unit): View {
        val p = palette
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(6), dp(8), dp(6))
            background = rounded(p.ground, dp(16).toFloat(), p.edge)
        }
        row.addView(ImageView(this).apply {
            setImageResource(iconRes)
            imageTintList = ColorStateList.valueOf(p.muted)
        }, LinearLayout.LayoutParams(dp(22), dp(22)))
        row.addView(TextView(this).apply {
            text = label
            textSize = 15f
            setTextColor(p.ink)
            setPadding(dp(14), 0, dp(8), 0)
        }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        row.addView(MaterialSwitch(this).apply {
            isChecked = checked
            val states = arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf())
            thumbTintList = ColorStateList(states, intArrayOf(p.ground, p.faint))
            trackTintList = ColorStateList(states, intArrayOf(p.astra, p.raised))
            setOnCheckedChangeListener { view, on ->
                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                onChange(on)
            }
        })
        return row
    }

    /** Android 13+ asks before an app may notify; asked when alerts are wanted, not before. */
    private fun askForAlerts() {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notifyPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private fun tile(dest: Dest, active: Boolean, onClick: () -> Unit): View {
        val p = palette
        val ground = if (active) ColorUtils.setAlphaComponent(p.astra, 36) else p.ground
        val stroke = if (active) ColorUtils.setAlphaComponent(p.astra, 150) else p.edge
        val shape = rounded(ground, dp(18).toFloat(), stroke)
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(6), dp(8), dp(6), dp(8))
            background = RippleDrawable(ColorStateList.valueOf(ColorUtils.setAlphaComponent(p.astra, 60)), shape, null)
            isClickable = true
            isFocusable = true
            contentDescription = dest.label
            setOnClickListener { onClick() }
            addView(ImageView(context).apply {
                setImageResource(dest.icon)
                imageTintList = ColorStateList.valueOf(if (active) p.astra else p.muted)
            }, LinearLayout.LayoutParams(dp(24), dp(24)))
            addView(TextView(context).apply {
                text = dest.label
                textSize = 12f
                gravity = Gravity.CENTER
                maxLines = 2
                setTextColor(if (active) p.ink else p.muted)
                if (active) typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(6) })
        }
    }

    // --- theme ----------------------------------------------------------------

    private fun prefs() = getSharedPreferences("app", MODE_PRIVATE)

    /** Switches app and site together: the site keeps its theme in localStorage, shared by every tab. */
    private fun useTheme(light: Boolean) {
        val name = if (light) "light" else "dark"
        prefs().edit().putString(THEME, name).apply()
        palette = if (light) Palette.LIGHT else Palette.DARK
        applyPalette()
        val script = "try{localStorage.setItem('theme','$name')}catch(e){};document.documentElement.setAttribute('data-theme','$name')"
        tabs.values.forEach { it.web.evaluateJavascript(script, null) }
    }

    /** The site's stored theme wins over the app's, so a choice made on a page before this build still holds. */
    /**
     * After each page load: the site's theme and its session, read from the page's storage.
     * The site's stored theme wins over the app's, so a choice made on a page still holds; a
     * sign-in, sign-out or account switch on a page reaches the native screens (Session).
     */
    fun syncFromPage(web: WebView) {
        val script = "(function(){try{return JSON.stringify([localStorage.getItem('theme'),localStorage.getItem('pashu.session')])}catch(e){return null}})()"
        web.evaluateJavascript(script) { value ->
            // evaluateJavascript hands back a JSON value: here a string holding the JSON array.
            val pair = runCatching { org.json.JSONArray(org.json.JSONTokener(value).nextValue() as String) }.getOrNull() ?: return@evaluateJavascript
            val light = pair.optString(0) == "light"
            if (light != !palette.dark) {
                prefs().edit().putString(THEME, if (light) "light" else "dark").apply()
                palette = if (light) Palette.LIGHT else Palette.DARK
                applyPalette()
            }
            val token = if (pair.isNull(1)) null else pair.optString(1).takeIf { it.isNotBlank() }
            if (Session.set(this, token)) {
                me = null
                natives[R.id.tab_home]?.let { (it as? HomeScreen)?.reload() }
            }
        }
    }

    private fun applyPalette() {
        val p = palette
        root.setBackgroundColor(p.ground)
        appBar.setBackgroundColor(p.ground)
        toolbar.setBackgroundColor(p.ground)
        toolbar.setTitleTextColor(p.ink)
        toolbar.menu.findItem(R.id.action_search)?.icon = tinted(R.drawable.ic_search, p.muted)
        toolbar.menu.findItem(R.id.action_share)?.icon = tinted(R.drawable.ic_share, p.muted)
        progress.progressTintList = ColorStateList.valueOf(p.astra)
        progress.progressBackgroundTintList = ColorStateList.valueOf(Color.TRANSPARENT)
        topLine.setBackgroundColor(p.edge)
        bottomLine.setBackgroundColor(p.edge)

        val states = arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf())
        nav.setBackgroundColor(p.panel)
        nav.itemIconTintList = ColorStateList(states, intArrayOf(p.astra, p.faint))
        nav.itemTextColor = ColorStateList(states, intArrayOf(p.ink, p.faint))
        nav.itemActiveIndicatorColor = ColorStateList.valueOf(ColorUtils.setAlphaComponent(p.astra, 46))
        nav.itemRippleColor = ColorStateList.valueOf(ColorUtils.setAlphaComponent(p.astra, 30))

        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !p.dark
            isAppearanceLightNavigationBars = !p.dark
        }
        tabs.values.forEach { it.applyPalette(p) }
        natives.values.forEach { it.applyPalette() }
        updateChrome()
    }

    // --- helpers --------------------------------------------------------------

    fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun tinted(res: Int, color: Int) = ContextCompat.getDrawable(this, res)?.mutate()?.apply { setTint(color) }

    private fun rounded(color: Int, radius: Float, stroke: Int? = null) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = radius
        if (stroke != null) setStroke(dp(1), stroke)
    }

    private companion object {
        const val THEME = "theme"
        const val ASKED = "alerts.asked"
        const val ONBOARDED = "onboarded"
    }
}

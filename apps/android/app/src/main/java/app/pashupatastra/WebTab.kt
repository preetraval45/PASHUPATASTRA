package app.pashupatastra

import android.annotation.SuppressLint
import android.content.res.ColorStateList
import android.graphics.Bitmap
import android.graphics.Typeface
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.google.android.material.button.MaterialButton

/**
 * One tab of the app: its own WebView with its own history, as a native app's
 * tabs keep their own stack. Switching tabs and back returns to the same page
 * at the same scroll position, instead of reloading it.
 *
 * Over the page it draws native states rather than web ones: a spinner until
 * the first page arrives, and an offline screen instead of Chrome's error page.
 */
@SuppressLint("SetJavaScriptEnabled")
class WebTab(private val activity: MainActivity) {

    val view = FrameLayout(activity)
    val web = WebView(activity)
    private val refresh = SwipeRefreshLayout(activity)
    private val loading = ProgressBar(activity)
    private val offline = LinearLayout(activity)
    private val offlineIcon = ImageView(activity)
    private val offlineTitle = TextView(activity)
    private val offlineBody = TextView(activity)
    private val retry = MaterialButton(activity)

    /** Set by the page (AppBridge.atTop): the site scrolls inside a panel, so the WebView's own scrollY stays 0. */
    @Volatile
    var pageAtTop = true

    var progress = 100
        private set
    var pageTitle = ""
        private set

    /** Nothing loaded yet: the tab was created but never shown. */
    var isEmpty = true
        private set

    private var failed = false

    init {
        web.apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.mediaPlaybackRequiresUserGesture = true
            settings.allowFileAccess = false
            settings.setSupportZoom(false)
            settings.builtInZoomControls = false
            // The site can tell it is inside the app ("PashupatastraApp"), and that this build
            // draws its own bars ("PashupatastraNative"), so the page hides its web ones.
            settings.userAgentString = settings.userAgentString +
                " PashupatastraApp/" + BuildConfig.VERSION_NAME + " PashupatastraNative/1"
            overScrollMode = View.OVER_SCROLL_NEVER
            isVerticalScrollBarEnabled = false
            isHorizontalScrollBarEnabled = false
            addJavascriptInterface(AppBridge(activity, this@WebTab), "PashupatastraApp")
            webViewClient = Client()
            webChromeClient = Chrome()
        }
        refresh.apply {
            addView(web, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
            setOnRefreshListener { web.reload() }
            // Only pull-to-refresh at the very top of a page, so scrolling inside panels still works.
            setOnChildScrollUpCallback { _, _ -> !pageAtTop || web.scrollY > 0 }
        }
        view.addView(refresh, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        view.addView(loading, FrameLayout.LayoutParams(activity.dp(40), activity.dp(40), Gravity.CENTER))
        buildOffline()
        view.addView(offline, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        applyPalette(activity.palette)
    }

    private fun buildOffline() {
        offline.apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(activity.dp(32), 0, activity.dp(32), activity.dp(32))
            visibility = View.GONE
            isClickable = true
        }
        offlineIcon.setImageResource(R.drawable.ic_offline)
        offline.addView(offlineIcon, LinearLayout.LayoutParams(activity.dp(56), activity.dp(56)))
        offlineTitle.apply {
            setText(R.string.offline_title)
            textSize = 20f
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            gravity = Gravity.CENTER
        }
        offline.addView(offlineTitle, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = activity.dp(20) })
        offlineBody.apply {
            setText(R.string.offline_body)
            textSize = 15f
            gravity = Gravity.CENTER
            setLineSpacing(0f, 1.25f)
        }
        offline.addView(offlineBody, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = activity.dp(8) })
        retry.apply {
            setText(R.string.offline_retry)
            cornerRadius = activity.dp(24)
            minHeight = activity.dp(48)
            setPadding(activity.dp(28), 0, activity.dp(28), 0)
            setOnClickListener {
                offline.visibility = View.GONE
                loading.visibility = View.VISIBLE
                web.reload()
            }
        }
        offline.addView(retry, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = activity.dp(24) })
    }

    fun applyPalette(p: Palette) {
        view.setBackgroundColor(p.ground)
        web.setBackgroundColor(p.ground)
        refresh.setColorSchemeColors(p.astra)
        refresh.setProgressBackgroundColorSchemeColor(p.raised)
        loading.indeterminateTintList = ColorStateList.valueOf(p.astra)
        offline.setBackgroundColor(p.ground)
        offlineIcon.imageTintList = ColorStateList.valueOf(p.faint)
        offlineTitle.setTextColor(p.ink)
        offlineBody.setTextColor(p.muted)
        retry.backgroundTintList = ColorStateList.valueOf(p.astra)
        retry.setTextColor(p.ground)
    }

    fun load(url: String) {
        isEmpty = false
        web.loadUrl(url)
    }

    /** Re-tapping the current tab, as in any app: back to its first page, or to the top if already there. */
    fun toRoot() {
        val history = web.copyBackForwardList()
        if (history.currentIndex > 0) {
            web.goBackOrForward(-history.currentIndex)
        } else {
            web.evaluateJavascript(
                "document.querySelectorAll('.overflow-y-auto,main').forEach(function(e){e.scrollTo({top:0,behavior:'smooth'})});window.scrollTo({top:0,behavior:'smooth'})",
                null,
            )
        }
    }

    private inner class Client : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val uri = request.url
            if (activity.isSite(uri)) return false
            // Everything else (other sites, mailto:, tel:) goes to the app that handles it.
            activity.openOutside(uri)
            return true
        }

        override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
            pageAtTop = true
            failed = false
        }

        override fun onPageFinished(view: WebView, url: String) {
            refresh.isRefreshing = false
            loading.visibility = View.GONE
            if (!failed) offline.visibility = View.GONE
            activity.syncThemeFrom(web)
            activity.onTabChanged(this@WebTab)
        }

        override fun doUpdateVisitedHistory(view: WebView, url: String, isReload: Boolean) {
            // Fires on the site's client-side navigations too, which onPageStarted does not.
            activity.onTabChanged(this@WebTab)
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            // Only a failed page, not a failed image or API call inside a page that loaded.
            if (request.isForMainFrame) {
                failed = true
                refresh.isRefreshing = false
                loading.visibility = View.GONE
                offline.visibility = View.VISIBLE
            }
        }
    }

    private inner class Chrome : WebChromeClient() {
        override fun onProgressChanged(view: WebView, newProgress: Int) {
            progress = newProgress
            activity.onTabChanged(this@WebTab)
        }

        override fun onReceivedTitle(view: WebView, title: String?) {
            pageTitle = title.orEmpty()
            activity.onTabChanged(this@WebTab)
        }
    }
}

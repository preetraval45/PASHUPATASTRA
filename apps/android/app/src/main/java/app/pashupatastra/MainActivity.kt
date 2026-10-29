package app.pashupatastra

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.ProgressBar
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout

/**
 * The Pashupatastra app: the live website in a full-screen WebView.
 *
 * Every page comes from the deployed site, so whatever ships to main shows up
 * in the app with no rebuild. The app adds what a browser tab does not: its
 * own icon and splash, pull to refresh, the back button walking back through
 * pages, a native share sheet, and an offline page instead of a browser error.
 * Links that leave the site open in the phone's browser, so the app never
 * becomes a browser for someone else's pages.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var refresh: SwipeRefreshLayout
    private lateinit var progress: ProgressBar
    private val site: Uri = Uri.parse(BuildConfig.SITE_URL)

    /** Set by the page (AppBridge.atTop): the site scrolls inside a panel, so the WebView's own scrollY stays 0. */
    @Volatile
    var pageAtTop = true

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)

        web = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#0b0d11"))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.mediaPlaybackRequiresUserGesture = true
            settings.allowFileAccess = false
            // The site can tell it is inside the app, e.g. to hide an "install the app" prompt.
            settings.userAgentString = settings.userAgentString + " PashupatastraApp/" + BuildConfig.VERSION_NAME
            addJavascriptInterface(AppBridge(this@MainActivity), "PashupatastraApp")
            webViewClient = Client()
            webChromeClient = object : WebChromeClient() {
                override fun onProgressChanged(view: WebView, newProgress: Int) {
                    progress.progress = newProgress
                    progress.visibility = if (newProgress < 100) View.VISIBLE else View.GONE
                }
            }
        }
        refresh = SwipeRefreshLayout(this).apply {
            setColorSchemeColors(Color.parseColor("#2fa3a0"))
            setProgressBackgroundColorSchemeColor(Color.parseColor("#161a21"))
            addView(web, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            setOnRefreshListener { web.reload() }
            // Only pull-to-refresh at the very top of a page, so scrolling inside panels still works.
            setOnChildScrollUpCallback { _, _ -> !pageAtTop || web.scrollY > 0 }
        }
        progress = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100
            progressTintList = android.content.res.ColorStateList.valueOf(Color.parseColor("#2fa3a0"))
        }
        setContentView(FrameLayout(this).apply {
            setBackgroundColor(Color.parseColor("#0b0d11"))
            addView(refresh, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
            addView(progress, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, 6))
        })

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (web.canGoBack()) web.goBack() else finish()
            }
        })

        if (savedInstanceState != null) web.restoreState(savedInstanceState) else web.loadUrl(startUrl(intent))
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        web.loadUrl(startUrl(intent))
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    /** A link to the site opens that page; anything else opens the home page. */
    private fun startUrl(intent: Intent?): String {
        val link = intent?.data
        return if (link != null && isSite(link)) link.toString() else site.toString()
    }

    private fun isSite(uri: Uri): Boolean = uri.scheme == "https" && uri.host == site.host

    private inner class Client : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val uri = request.url
            if (isSite(uri)) return false
            // Everything else (other sites, mailto:, tel:) goes to the app that handles it.
            runCatching { startActivity(Intent(Intent.ACTION_VIEW, uri)) }
            return true
        }

        override fun onPageStarted(view: WebView, url: String, favicon: android.graphics.Bitmap?) {
            pageAtTop = true
        }

        override fun onPageFinished(view: WebView, url: String) {
            refresh.isRefreshing = false
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            // Only a failed page, not a failed image or API call inside a page that loaded.
            if (request.isForMainFrame) {
                refresh.isRefreshing = false
                view.loadUrl("file:///android_asset/offline.html")
            }
        }
    }

    /** Called from the offline page's "Try again" button. */
    fun retry() {
        runOnUiThread { web.loadUrl(site.toString()) }
    }
}

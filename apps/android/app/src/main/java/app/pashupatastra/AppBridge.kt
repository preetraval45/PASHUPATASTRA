package app.pashupatastra

import android.content.Intent
import android.webkit.JavascriptInterface

/**
 * The only things a page may ask of the app, as `window.PashupatastraApp.<method>()`.
 *
 * Kept to a few harmless calls on purpose: the WebView only ever shows this
 * site (other links leave for the browser), but whatever is exposed here is
 * callable by any script on it, so nothing here reads data or acts on the
 * phone's behalf. One bridge per tab, because each tab scrolls on its own.
 */
class AppBridge(private val activity: MainActivity, private val tab: WebTab) {

    /** Opens Android's share sheet with a page's title and link. */
    @JavascriptInterface
    fun share(title: String, url: String) {
        activity.runOnUiThread { activity.share(title, url) }
    }

    /** The page reports whether what the user is scrolling is at its top, so pull-to-refresh only fires there. */
    @JavascriptInterface
    fun atTop(top: Boolean) {
        tab.pageAtTop = top
    }
}

package app.pashupatastra

import android.content.Intent
import android.webkit.JavascriptInterface

/**
 * The only things the page may ask of the app, as `window.PashupatastraApp.<method>()`.
 *
 * Kept to a few harmless calls on purpose: the WebView only ever shows this
 * site (other links leave for the browser), but whatever is exposed here is
 * callable by any script on it, so nothing here reads data or acts on the
 * phone's behalf.
 */
class AppBridge(private val activity: MainActivity) {

    /** Opens Android's share sheet with a page's title and link. */
    @JavascriptInterface
    fun share(title: String, url: String) {
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, title.take(200))
            putExtra(Intent.EXTRA_TEXT, url.take(2000))
        }
        activity.runOnUiThread { activity.startActivity(Intent.createChooser(send, "Share")) }
    }

    /** The page reports whether what the user is scrolling is at its top, so pull-to-refresh only fires there. */
    @JavascriptInterface
    fun atTop(top: Boolean) {
        activity.pageAtTop = top
    }

    /** Reloads the site; the offline page's "Try again" button calls it. */
    @JavascriptInterface
    fun retry() = activity.retry()
}

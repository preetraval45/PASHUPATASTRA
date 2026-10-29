# The page talks to the app only through AppBridge's @JavascriptInterface methods; keep them.
-keepclassmembers class app.pashupatastra.AppBridge {
    @android.webkit.JavascriptInterface <methods>;
}

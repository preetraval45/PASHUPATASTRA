package app.pashupatastra

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.widget.Toast

/**
 * Updates for copies installed from the APK (a copy from Google Play is updated by Play, and Play does not
 * allow an app to update itself, so none of this shows there: Api.newerBuild answers null for it).
 *
 * The owner could not download updates (2 Nov): the banner handed the APK's link to the browser, which on
 * many phones fails quietly or is blocked. Android's own download manager fetches it instead, with a
 * progress notification; tapping "Download complete" opens the system installer, which asks once for
 * permission to install from this source. Nothing is installed without the person confirming it.
 */
object Updater {

    fun download(context: Context, build: Int?) {
        val name = "Pashupatastra-" + (build?.toString() ?: "latest") + ".apk"
        val request = DownloadManager.Request(Uri.parse(Api.APK))
            .setTitle(context.getString(R.string.update_title))
            .setDescription(name)
            .setMimeType("application/vnd.android.package-archive")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            // The app's own download folder: no storage permission needed on any Android version.
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, name)
        val started = runCatching {
            (context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
        }.isSuccess
        Toast.makeText(
            context,
            context.getString(if (started) R.string.update_downloading else R.string.update_failed),
            Toast.LENGTH_LONG,
        ).show()
    }
}

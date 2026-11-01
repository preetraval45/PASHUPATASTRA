package app.pashupatastra

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONArray
import java.util.concurrent.TimeUnit

/**
 * Tells the phone when an incident needs its owner, without the app open.
 *
 * Every 15 minutes (Android's shortest period for background work, and only
 * with a network) it reads the public `/incidents` and notifies once for each
 * incident that newly awaits approval or newly opens as critical. No push
 * service or account is involved: the phone asks, the API answers, nothing is
 * sent from the phone. The first run only records what is already open, so
 * turning alerts on does not replay every existing incident.
 */
class IncidentWatch(context: Context, params: WorkerParameters) : Worker(context, params) {

    override fun doWork(): Result {
        val incidents = runCatching { Api.parseIncidents(JSONArray(Api.get("/incidents"))) }
            .getOrElse { return Result.retry() }
        val prefs = applicationContext.getSharedPreferences("app", Context.MODE_PRIVATE)
        val alerting = incidents.filter {
            it.state == "awaiting_approval" ||
                (it.severity == "critical" && it.state != "resolved" && it.state != "rolled_back")
        }
        val keys = alerting.map { key(it) }.toSet()
        val seen = prefs.getStringSet(SEEN, null)
        if (seen != null) alerting.filter { key(it) !in seen }.forEach { notify(it) }
        prefs.edit().putStringSet(SEEN, keys).apply()
        return Result.success()
    }

    private fun key(incident: Api.Incident) = incident.id + ":" + incident.state + ":" + incident.severity

    private fun notify(incident: Api.Incident) {
        val context = applicationContext
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        channel(context)
        val open = Intent(Intent.ACTION_VIEW, Uri.parse(BuildConfig.SITE_URL.trimEnd('/') + "/incidents/" + incident.id))
            .setClass(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val tap = PendingIntent.getActivity(
            context, incident.id.hashCode(), open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val title = if (incident.state == "awaiting_approval") {
            "${incident.id} needs your approval"
        } else {
            "Critical incident: ${incident.id}"
        }
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_alert)
            .setColor(Palette.DARK.astra)
            .setContentTitle(title)
            .setContentText(incident.statement.ifBlank { Api.stateLabel(incident.state) })
            .setStyle(NotificationCompat.BigTextStyle().bigText(incident.statement.ifBlank { Api.stateLabel(incident.state) }))
            .setSubText(incident.severity.replaceFirstChar { it.uppercase() })
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .setContentIntent(tap)
            .setAutoCancel(true)
            .build()
        runCatching { NotificationManagerCompat.from(context).notify(incident.id.hashCode(), notification) }
    }

    companion object {
        private const val CHANNEL = "incidents"
        private const val SEEN = "alerts.seen"
        private const val WORK = "incident-watch"
        const val ENABLED = "alerts.enabled"

        fun channel(context: Context) {
            if (Build.VERSION.SDK_INT < 26) return
            val manager = context.getSystemService(NotificationManager::class.java)
            if (manager.getNotificationChannel(CHANNEL) != null) return
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL, "Incidents that need you", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "An incident awaits approval, or a critical incident opens."
                },
            )
        }

        /** Starts or stops the watch, as the user's switch in More says. */
        fun schedule(context: Context, enabled: Boolean) {
            val work = WorkManager.getInstance(context)
            if (!enabled) {
                work.cancelUniqueWork(WORK)
                return
            }
            val request = PeriodicWorkRequestBuilder<IncidentWatch>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            work.enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.KEEP, request)
        }
    }
}

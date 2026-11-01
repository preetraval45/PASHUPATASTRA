package app.pashupatastra

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.RemoteViews
import java.text.DateFormat
import java.util.Date

/**
 * The home-screen widget: how many incidents are open, how many await the
 * owner's approval, how many are critical. IncidentWatch refreshes it with
 * every check; until the first check has answered it shows "–", never a
 * guess. Tapping it opens the Incidents tab.
 */
class IncidentsWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        render(context, manager, ids)
        IncidentWatch.checkNow(context)
    }

    companion object {
        private const val OPEN = "widget.open"
        private const val NEED = "widget.need"
        private const val CRITICAL = "widget.critical"
        private const val AT = "widget.at"

        /** Stores the latest counts and redraws every placed widget. */
        fun update(context: Context, incidents: List<Api.Incident>) {
            val live = incidents.filter { it.state != "resolved" && it.state != "rolled_back" }
            context.getSharedPreferences("app", Context.MODE_PRIVATE).edit()
                .putInt(OPEN, live.size)
                .putInt(NEED, live.count { it.state == "awaiting_approval" })
                .putInt(CRITICAL, live.count { it.severity == "critical" })
                .putLong(AT, System.currentTimeMillis())
                .apply()
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, IncidentsWidget::class.java))
            if (ids.isNotEmpty()) render(context, manager, ids)
        }

        private fun render(context: Context, manager: AppWidgetManager, ids: IntArray) {
            val prefs = context.getSharedPreferences("app", Context.MODE_PRIVATE)
            val at = prefs.getLong(AT, 0L)
            val views = RemoteViews(context.packageName, R.layout.widget_incidents)
            fun count(id: Int, key: String, tone: Int) {
                if (at == 0L) return
                val value = prefs.getInt(key, 0)
                views.setTextViewText(id, value.toString())
                views.setTextColor(id, if (value > 0) tone else Palette.DARK.ink)
            }
            count(R.id.widget_open, OPEN, Palette.DARK.astra)
            count(R.id.widget_need, NEED, Palette.DARK.warn)
            count(R.id.widget_critical, CRITICAL, Palette.DARK.crit)
            views.setTextViewText(R.id.widget_updated, if (at == 0L) "" else DateFormat.getTimeInstance(DateFormat.SHORT).format(Date(at)))
            val open = Intent(Intent.ACTION_VIEW, Uri.parse(BuildConfig.SITE_URL.trimEnd('/') + "/incidents"))
                .setClass(context, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            views.setOnClickPendingIntent(
                R.id.widget_root,
                PendingIntent.getActivity(context, 7, open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE),
            )
            manager.updateAppWidget(ids, views)
        }
    }
}

package app.pashupatastra

import android.content.res.ColorStateList
import android.graphics.Typeface
import android.os.Build
import android.os.SystemClock
import android.view.Gravity
import android.view.ViewGroup
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_WEAK
import androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.material.button.MaterialButton

/**
 * An optional lock on the app: fingerprint, face, or the phone's own PIN, pattern or
 * password. Off by default; a switch under More turns it on.
 *
 * When on, the app is covered on open and on return after 30 seconds away, and the
 * window is marked secure (MainActivity.applySecure), so the recent-apps preview and
 * screenshots show nothing of the incidents behind it. Android does the checking; the app only
 * learns whether it passed, and stores nothing about the person.
 */
class AppLock(private val activity: MainActivity, private val host: ViewGroup) {

    private val prefs = activity.getSharedPreferences("app", android.content.Context.MODE_PRIVATE)
    private var cover: FrameLayout? = null
    private var leftAt = 0L

    val enabled get() = prefs.getBoolean(ENABLED, false)

    /** Whether this phone can lock the app at all: a screen lock or a biometric is set up. */
    fun available(): Boolean {
        if (BiometricManager.from(activity).canAuthenticate(authenticators()) == BiometricManager.BIOMETRIC_SUCCESS) return true
        // Before Android 11 a PIN-only phone reports no biometric; its screen lock still counts.
        val keyguard = activity.getSystemService(android.app.KeyguardManager::class.java)
        return Build.VERSION.SDK_INT < 30 && keyguard?.isDeviceSecure == true
    }

    /** From the More switch: turning it on needs one successful check first, so nobody locks themselves out. */
    fun setEnabled(on: Boolean, done: (Boolean) -> Unit) {
        if (!on) {
            prefs.edit().putBoolean(ENABLED, false).apply()
            done(false)
            return
        }
        if (!available()) {
            Toast.makeText(activity, "Set up a screen lock on this phone first.", Toast.LENGTH_LONG).show()
            done(false)
            return
        }
        prompt("Turn on the app lock") { passed ->
            if (passed) prefs.edit().putBoolean(ENABLED, true).apply()
            done(passed)
        }
    }

    fun onStart() {
        if (!enabled) return
        if (cover == null && (leftAt == 0L || SystemClock.elapsedRealtime() - leftAt > GRACE_MS)) lock()
    }

    fun onStop() {
        leftAt = SystemClock.elapsedRealtime()
    }

    private fun lock() {
        val p = activity.palette
        val dp = { v: Int -> activity.dp(v) }
        val layer = FrameLayout(activity).apply {
            setBackgroundColor(p.ground)
            isClickable = true
            isFocusable = true
        }
        val column = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(32), 0, dp(32), 0)
        }
        column.addView(ImageView(activity).apply {
            setImageResource(R.drawable.ic_shield)
            imageTintList = ColorStateList.valueOf(p.astra)
        }, LinearLayout.LayoutParams(dp(56), dp(56)))
        column.addView(TextView(activity).apply {
            text = "Pashupatastra is locked"
            textSize = 22f
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            setTextColor(p.ink)
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(20) })
        column.addView(TextView(activity).apply {
            text = "Unlock with your fingerprint, face or screen lock."
            textSize = 15f
            setTextColor(p.muted)
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(8) })
        column.addView(MaterialButton(activity).apply {
            text = "Unlock"
            isAllCaps = false
            textSize = 16f
            cornerRadius = dp(26)
            backgroundTintList = ColorStateList.valueOf(p.astra)
            setTextColor(p.ground)
            setOnClickListener { ask() }
        }, LinearLayout.LayoutParams(dp(220), dp(52)).apply { topMargin = dp(28) })
        layer.addView(column, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        ViewCompat.setOnApplyWindowInsetsListener(layer) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        host.addView(layer, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        cover = layer
        layer.post { ask() }
    }

    private fun ask() {
        prompt("Unlock Pashupatastra") { passed ->
            if (passed) {
                cover?.let { layer -> layer.animate().alpha(0f).setDuration(180).withEndAction { host.removeView(layer) }.start() }
                cover = null
            }
        }
    }

    private fun prompt(title: String, result: (Boolean) -> Unit) {
        val callback = object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(outcome: BiometricPrompt.AuthenticationResult) = result(true)
            override fun onAuthenticationError(code: Int, message: CharSequence) = result(false)
        }
        val builder = BiometricPrompt.PromptInfo.Builder().setTitle(title)
        if (Build.VERSION.SDK_INT >= 30) {
            builder.setAllowedAuthenticators(authenticators())
        } else {
            // Before Android 11 the phone's PIN is offered through the older switch.
            @Suppress("DEPRECATION")
            builder.setDeviceCredentialAllowed(true)
        }
        BiometricPrompt(activity, ContextCompat.getMainExecutor(activity), callback).authenticate(builder.build())
    }

    private fun authenticators() = if (Build.VERSION.SDK_INT >= 30) BIOMETRIC_WEAK or DEVICE_CREDENTIAL else BIOMETRIC_WEAK

    private companion object {
        const val ENABLED = "lock.enabled"
        const val GRACE_MS = 30_000L
    }
}

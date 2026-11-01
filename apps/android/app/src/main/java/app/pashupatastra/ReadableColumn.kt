package app.pashupatastra

import android.content.Context
import android.view.View.MeasureSpec
import android.widget.LinearLayout

/**
 * A vertical column that never grows wider than a comfortable reading width.
 *
 * On a phone it is the full width; on a tablet, a foldable or in landscape it stops at
 * `maxWidthPx` and its parent centres it, so cards and lines of text keep a readable
 * length instead of stretching across the whole screen. Measured, not fixed at
 * creation, so it follows rotation (the activity handles configuration changes itself).
 */
class ReadableColumn(context: Context, private val maxWidthPx: Int) : LinearLayout(context) {

    init {
        orientation = VERTICAL
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val available = MeasureSpec.getSize(widthMeasureSpec)
        val spec = if (MeasureSpec.getMode(widthMeasureSpec) != MeasureSpec.UNSPECIFIED && available > maxWidthPx) {
            MeasureSpec.makeMeasureSpec(maxWidthPx, MeasureSpec.EXACTLY)
        } else {
            widthMeasureSpec
        }
        super.onMeasure(spec, heightMeasureSpec)
    }
}

#!/usr/bin/env python3
"""v19: conditional IME layout recovery, never modify CarPlay transport or VD flags."""
from pathlib import Path
root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p=root/"ui/aa/split/SplitImeController.kt"
s=p.read_text()
anchor="    private val pollRunnable = object : Runnable {"
assert anchor in s
patch='''
    // v19: blind typing means the IME can receive input while its surface is
    // absent from the rendered pane. Request a WM layout pass only when a
    // visible IME window reports an empty frame. No IME app restart, no focus
    // switching, and no virtual-display/transport modifications.
    private val lastLayoutRecoveryMs = mutableMapOf<Int, Long>()
    private fun recoverZeroFrameIme(displayId: Int) {
        try {
            ensureResolved()
            val dc = displayContent(displayId) ?: return
            val walk = forAllWindows ?: return
            var emptyFrame = false
            var nonemptyFrame = false
            val visitor = Consumer<Any> { w ->
                if (!isInputMethodWindow(w) || !isWindowVisible(w)) return@Consumer
                val frame = fieldValue(w, "mFrame") as? android.graphics.Rect
                if (frame == null) {
                    android.util.Log.i("AAD_IME19", "display=$displayId visible IME frame unknown")
                } else {
                    val bad = frame.width() <= 0 || frame.height() <= 0
                    if (bad) emptyFrame = true else nonemptyFrame = true
                    android.util.Log.i("AAD_IME19",
                        "display=$displayId frame=$frame empty=$bad densityDpi=${c.mDensityDpi}")
                }
            }
            walk.invoke(dc, visitor, java.lang.Boolean.TRUE)
            if (!emptyFrame || nonemptyFrame) return
            val now = android.os.SystemClock.uptimeMillis()
            if (now - (lastLayoutRecoveryMs[displayId] ?: 0L) < 10000L) return
            lastLayoutRecoveryMs[displayId] = now
            // A layout traversal is less invasive than hiding/showing the IME
            // (which loses the active editor and may break blind input).
            val wm = wms ?: return
            val placer = fieldValue(wm, "mWindowPlacerLocked")
                ?: fieldValue(fieldValue(wm, "mService") ?: wm, "mWindowPlacerLocked")
            val request = placer?.javaClass?.methods?.firstOrNull {
                it.name == "requestTraversal" && it.parameterTypes.isEmpty()
            }
            if (request != null) {
                request.invoke(placer)
                android.util.Log.i("AAD_IME19", "requested IME layout traversal display=$displayId")
            } else {
                android.util.Log.i("AAD_IME19", "IME traversal API unavailable display=$displayId")
            }
        } catch (t: Throwable) {
            android.util.Log.w("AAD_IME19", "IME layout check failed display=$displayId", t)
        }
    }

'''
s=s.replace(anchor,patch+anchor,1)
anchor2='''                logImeGeometry(displayId)'''
assert anchor2 in s
s=s.replace(anchor2,anchor2+'''
                c.mHandler.postDelayed({
                    if (!c.mIsDestroying && c.isAaVirtualDisplay(displayId)) {
                        recoverZeroFrameIme(displayId)
                    }
                }, 350L)''',1)
p.write_text(s)
gradle=Path("aa-display/build.gradle.kts")
v=gradle.read_text()
assert 'versionCode = 3118' in v and 'versionName = "0.3#17.8-v18"' in v
v=v.replace('versionCode = 3118','versionCode = 3119',1).replace('versionName = "0.3#17.8-v18"','versionName = "0.3#17.8-v19"',1)
gradle.write_text(v)
print("v19 conditional IME zero-frame recovery applied")

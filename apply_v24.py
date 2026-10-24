#!/usr/bin/env python3
"""v24: IME-only hard-keyboard setting verification and zero-height diagnostics.
Run after v23. Preserve transport, display geometry, and original IME routing.
"""
from pathlib import Path
root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p=root/"xposed/hook/VdImeDisplayPin.kt"
s=p.read_text()
old='''            Settings.Secure.putInt(cr, SHOW_IME_WITH_HARD_KEYBOARD, 1)
            softImeSettingOwned = true
            log(TAG, "enabled show_ime_with_hard_keyboard for AA session (BT hard kb)")'''
new='''            val wrote = Settings.Secure.putInt(cr, SHOW_IME_WITH_HARD_KEYBOARD, 1)
            val actual = Settings.Secure.getInt(cr, SHOW_IME_WITH_HARD_KEYBOARD, 0)
            softImeSettingOwned = wrote && actual == 1
            log(TAG, "v24 hard-keyboard IME requested=1 wrote=$wrote actual=$actual owned=$softImeSettingOwned")
            if (!softImeSettingOwned) softImeSettingPrevious = null'''
assert s.count(old)==1
s=s.replace(old,new,1)
old='''            if (current != 0) return'''
new='''            if (current != 0) {
                log(TAG, "v24 hard-keyboard IME already enabled value=$current")
                return
            }'''
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)
p=root/"ui/aa/split/SplitImeController.kt"
s=p.read_text()
anchor='''    private val pollRunnable = object : Runnable {'''
assert s.count(anchor)==1
addition='''    // v24: read-only diagnostic. A visible IME token with a zero-height
    // frame is NOT a usable keyboard. Do not inject BACK or force a show.
    private var v24LastImeSampleMs = 0L
    private fun v24SampleIme() {
        val now = android.os.SystemClock.uptimeMillis()
        if (now - v24LastImeSampleMs < 2000L) return
        v24LastImeSampleMs = now
        try {
            ensureResolved()
            val ids = intArrayOf(c.primaryDisplayId, c.secondaryDisplayId)
            for (id in ids) {
                if (id == Display.INVALID_DISPLAY || !c.isAaVirtualDisplay(id)) continue
                val dc = displayContent(id) ?: continue
                val walk = forAllWindows ?: continue
                var count = 0
                val visitor = Consumer<Any> { w ->
                    if (!isInputMethodWindow(w)) return@Consumer
                    count++
                    val frame = fieldValue(w, "mFrame") as? android.graphics.Rect
                    val visibleNow = isWindowVisible(w)
                    log(SplitDisplayController.TAG,
                        "v24 IME display=$id visible=$visibleNow frame=$frame " +
                        "zeroFrame=${frame != null && (frame.width() <= 0 || frame.height() <= 0)}")
                }
                walk.invoke(dc, visitor, java.lang.Boolean.TRUE)
                if (count == 0) {
                    logDebug(SplitDisplayController.TAG, "v24 IME display=$id no-window")
                }
            }
        } catch (t: Throwable) {
            logDebug(SplitDisplayController.TAG, "v24 IME sample failed: ${t.message}")
        }
    }

'''
s=s.replace(anchor,addition+anchor,1)
needle='''            refreshAndNotify()
            val delay = if (visible) POLL_VISIBLE_MS else POLL_HIDDEN_MS'''
assert s.count(needle)==1
s=s.replace(needle,'''            refreshAndNotify()
            v24SampleIme()
            val delay = if (visible) POLL_VISIBLE_MS else POLL_HIDDEN_MS''',1)
p.write_text(s)
g=Path("aa-display/build.gradle.kts")
v=g.read_text()
assert 'versionCode = 3123' in v and 'versionName = "0.3#17.8-v23"' in v
g.write_text(v.replace('versionCode = 3123','versionCode = 3124',1).replace('versionName = "0.3#17.8-v23"','versionName = "0.3#17.8-v24"',1))
print("v24 IME-only verification and diagnostics applied")

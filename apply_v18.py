#!/usr/bin/env python3
"""v18: IME window geometry diagnostics only; preserve all transport paths."""
from pathlib import Path
root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p=root/"ui/aa/split/SplitImeController.kt"
s=p.read_text()
anchor="    private val pollRunnable = object : Runnable {"
assert anchor in s
addition='''
    // v18: sample actual WindowManager IME geometry on the pane that was
    // touched. A visible window can still have a zero-sized source frame.
    // Read-only diagnostics; never force layout or modify display flags.
    private var lastGeometryLogMs = 0L
    private fun logImeGeometry(displayId: Int) {
        val now = android.os.SystemClock.uptimeMillis()
        if (now - lastGeometryLogMs < 1500L) return
        lastGeometryLogMs = now
        try {
            ensureResolved()
            val dc = displayContent(displayId)
            val walk = forAllWindows
            if (dc == null || walk == null) {
                log(SplitDisplayController.TAG,
                    "v18 IME geometry unavailable display=$displayId dc=${dc != null} walk=${walk != null}")
                return
            }
            var count = 0
            val visitor = Consumer<Any> { window ->
                if (!isInputMethodWindow(window)) return@Consumer
                count++
                val attrs = windowAttrs(window)
                val frame = fieldValue(window, "mFrame")
                val visibleNow = isWindowVisible(window)
                log(SplitDisplayController.TAG,
                    "v18 IME geometry display=$displayId visible=$visibleNow " +
                    "frame=$frame attrsWidth=${attrs?.width} attrsHeight=${attrs?.height} " +
                    "gravity=${attrs?.gravity} flags=${attrs?.flags}")
            }
            walk.invoke(dc, visitor, java.lang.Boolean.TRUE)
            if (count == 0) {
                log(SplitDisplayController.TAG, "v18 IME no window display=$displayId")
            }
        } catch (e: Throwable) {
            log(SplitDisplayController.TAG, "v18 IME geometry failed display=$displayId", e)
        }
    }

'''
s=s.replace(anchor,addition+anchor,1)
anchor2='''                log(SplitDisplayController.TAG, "v17 IME policy LOCAL reassert display=$displayId")'''
assert anchor2 in s
s=s.replace(anchor2,anchor2+'''
                logImeGeometry(displayId)''',1)
p.write_text(s)
gradle=Path("aa-display/build.gradle.kts")
v=gradle.read_text()
assert 'versionCode = 3117' in v and 'versionName = "0.3#17.8-v17"' in v
v=v.replace('versionCode = 3117','versionCode = 3118',1).replace('versionName = "0.3#17.8-v17"','versionName = "0.3#17.8-v18"',1)
gradle.write_text(v)
print("v18 IME-only geometry diagnostics applied")

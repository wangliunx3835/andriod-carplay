#!/usr/bin/env python3
"""v17 IME-only experimental policy reassertion and window diagnostics."""
from pathlib import Path
root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p=root/"ui/aa/split/SplitImeController.kt"
s=p.read_text()
anchor="    private var immHide: Method? = null"
assert anchor in s
s=s.replace(anchor,anchor+'''
    // v17: never touch transport or media. Recover the local IME policy only
    // after a pane interaction; throttle to avoid binder churn on touch moves.
    private val lastPolicyRefresh = mutableMapOf<Int, Long>()
    fun onPaneTouch(displayId: Int) {
        if (c.mIsDestroying || !c.isAaVirtualDisplay(displayId)) return
        val now = android.os.SystemClock.uptimeMillis()
        if (now - (lastPolicyRefresh[displayId] ?: 0L) < 4000L) return
        lastPolicyRefresh[displayId] = now
        c.mHandler.post {
            if (c.mIsDestroying || !c.isAaVirtualDisplay(displayId)) return@post
            runCatching {
                io.github.nitsuya.aa.display.xposed.util.Instances.iWindowManager
                    .setDisplayImePolicy(displayId, 0)
                log(SplitDisplayController.TAG, "v17 IME policy LOCAL reassert display=$displayId")
            }.onFailure {
                log(SplitDisplayController.TAG, "v17 IME policy reassert failed display=$displayId", it)
            }
        }
    }
''',1)
anchor2="        if (shown == visible && (!shown || pane == imePane)) return"
assert anchor2 in s
s=s.replace(anchor2,'''        // v17: emit transitions only; an IME token without a drawn window is
        // intentionally not reported as visible.
        if (shown != visible) {
            log(SplitDisplayController.TAG,
                "v17 IME transition shown=$shown pane=$pane primary=${c.primaryDisplayId} secondary=${c.secondaryDisplayId}")
        }
'''+anchor2,1)
p.write_text(s)
p=root/"ui/aa/split/SplitDisplayController.kt"
s=p.read_text()
anchor="    fun onTouchPane("
assert anchor in s
# Keep transport and injection untouched: call recovery at input injection boundary.
p2=root/"ui/aa/split/SplitInputRecents.kt"
s2=p2.read_text()
needle="            val injected = Instances.iInputManager.injectInputEvent(event, 0)"
assert needle in s2
s2=s2.replace(needle,'''            if (event is android.view.MotionEvent &&
                event.actionMasked == android.view.MotionEvent.ACTION_DOWN) {
                c.ime.onPaneTouch(displayId)
            }
'''+needle,1)
p2.write_text(s2)
gradle=Path("aa-display/build.gradle.kts")
v=gradle.read_text()
assert 'versionCode = 3116' in v and 'versionName = "0.3#17.8-v16"' in v
v=v.replace('versionCode = 3116','versionCode = 3117',1).replace('versionName = "0.3#17.8-v16"','versionName = "0.3#17.8-v17"',1)
gradle.write_text(v)
print("v17 IME-only patch applied")

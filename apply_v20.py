#!/usr/bin/env python3
"""v20: periodic multi-display IME focus diagnostics and cautious policy repair.
Only touches IME controller and build metadata; transport and VD flags unchanged.
"""
from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/ui/aa/split/SplitImeController.kt")
s=p.read_text()
needle="    private val pollRunnable = object : Runnable {"
assert needle in s
addition='''
    // v20: independent of onPaneTouch and independent of v17 policy success.
    // Record transitions from system_server every 4 seconds, including when
    // there is no IME window at all. Never log editor text or keystrokes.
    private var lastV20SampleMs = 0L
    private val v20Previous = mutableMapOf<Int, String>()
    private fun v20Sample() {
        val now = android.os.SystemClock.uptimeMillis()
        if (now - lastV20SampleMs < 4000L) return
        lastV20SampleMs = now
        for (id in intArrayOf(c.primaryDisplayId, c.secondaryDisplayId)) {
            if (id == Display.INVALID_DISPLAY || !c.isAaVirtualDisplay(id)) continue
            try {
                ensureResolved()
                val dc = displayContent(id)
                val focus = dc?.let { fieldValue(it, "mCurrentFocus") }
                val imeWindow = dc?.let {
                    fieldValue(it, "mInputMethodWindow")
                        ?: fieldValue(it, "mImeWindow")
                }
                val target = dc?.let {
                    fieldValue(it, "mInputMethodTarget")
                        ?: fieldValue(it, "mImeInputTarget")
                }
                val imeVisible = isImeWindowVisible(id)
                val policy = runCatching {
                    io.github.nitsuya.aa.display.xposed.util.Instances.iWindowManager
                        .getDisplayImePolicy(id)
                }.getOrNull()
                val state = "focus=${focus != null} ime=${imeWindow != null} " +
                    "visible=$imeVisible target=${target != null} policy=$policy"
                val previous = v20Previous.put(id, state)
                if (previous != state) {
                    android.util.Log.i("AAD_IME20", "display=$id $state")
                }
                // Only repair a policy that actually drifted from LOCAL.
                // Do not synthesize focus, restart IME or change display flags.
                if (policy != null && policy != 0 && focus != null) {
                    runCatching {
                        io.github.nitsuya.aa.display.xposed.util.Instances.iWindowManager
                            .setDisplayImePolicy(id, 0)
                    }.onSuccess {
                        android.util.Log.i("AAD_IME20",
                            "display=$id repaired policy=$policy -> LOCAL")
                    }.onFailure {
                        android.util.Log.w("AAD_IME20",
                            "display=$id policy repair failed", it)
                    }
                }
            } catch (t: Throwable) {
                android.util.Log.w("AAD_IME20", "display=$id sampling failed", t)
            }
        }
    }

'''
s=s.replace(needle,addition+needle,1)
needle2="            refreshAndNotify()"
assert needle2 in s
s=s.replace(needle2,"            v20Sample()\n"+needle2,1)
p.write_text(s)
g=Path("aa-display/build.gradle.kts")
v=g.read_text()
assert 'versionCode = 3119' in v
v=v.replace('versionCode = 3119','versionCode = 3120',1).replace('versionName = "0.3#17.8-v19"','versionName = "0.3#17.8-v20"',1)
g.write_text(v)
print("v20 periodic IME diagnostics and policy drift repair applied")

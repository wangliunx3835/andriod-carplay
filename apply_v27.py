#!/usr/bin/env python3
"""v27: user-triggered, IME-synchronized GPU diagnostics after v26.

Run strictly after apply_v26.py. Adds a one-shot file trigger checked by the
compositor (every >=350 ms) without touching IME policy, VirtualDisplay setup,
networking, streaming transport, or v23 gateway readiness.

Trigger, from a rooted phone shell:
    touch /data/user/0/io.github.nitsuya.aa.display/files/CarPlayV26/v27_capture.trigger
Screenshots are saved in the same app-private CarPlayV26 directory with v27_N_ prefixes.
"""
from pathlib import Path

source = Path('aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlayGlCompositor.kt')
s = source.read_text(encoding='utf-8')


def change_once(old: str, new: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise AssertionError(f'v27 source mismatch: expected 1, got {count}: {old[:150]!r}')
    s = s.replace(old, new, 1)


change_once('''    private var v26Captured = false''', '''    private var v26Captured = false
    private var v27LastTriggerCheckMs = 0L
    private var v27CaptureSequence = 0

    /** Diagnostics only: root can request captures after the IME is already visible.
     * This does not change IME state and does not execute shell commands.
     */
    private fun v27ConsumeTrigger(): Boolean {
        val now = SystemClock.uptimeMillis()
        if (now - v27LastTriggerCheckMs < 350L) return false
        v27LastTriggerCheckMs = now
        return try {
            val pkg = Application.getProcessName().substringBefore(':')
            val file = File("/data/user/0/$pkg/files/CarPlayV26/v27_capture.trigger")
            if (!file.exists()) false
            else if (file.delete()) {
                Log.i(CarPlayConsts.TAG, "v27 manual GPU capture requested")
                true
            } else {
                Log.w(CarPlayConsts.TAG, "v27 trigger exists but could not be removed")
                false
            }
        } catch (t: Throwable) {
            Log.e(CarPlayConsts.TAG, "v27 trigger poll failed", t)
            false
        }
    }''')

change_once('''        val v26Capture = !v26Captured && SystemClock.uptimeMillis() >= v26CaptureAtMs
        if (v26Capture) {
            v26Captured = true''', '''        val v26Capture = !v26Captured && SystemClock.uptimeMillis() >= v26CaptureAtMs
        val v27ManualCapture = v27ConsumeTrigger()
        val v27Prefix = if (v27ManualCapture) "v27_${++v27CaptureSequence}_" else ""
        if (v26Capture || v27ManualCapture) {
            if (v26Capture) v26Captured = true''')
change_once('''                v26SaveFrame("raw_pane_${pane}", encodeWidth, encodeHeight)''', '''                v26SaveFrame("${v27Prefix}raw_pane_${pane}", encodeWidth, encodeHeight)''')
change_once('''        if (v26Capture) v26SaveFrame("encoder_before_swap", encodeWidth, encodeHeight)''', '''        if (v26Capture || v27ManualCapture) {
            v26SaveFrame("${v27Prefix}encoder_before_swap", encodeWidth, encodeHeight)
        }''')

build = Path('aa-display/build.gradle.kts')
g = build.read_text(encoding='utf-8')
assert g.count('versionCode = 3126') == 1, 'v27 must run after v26 (versionCode)'
assert g.count('versionName = "0.3#17.8-v26"') == 1, 'v27 must run after v26 (versionName)'
g = g.replace('versionCode = 3126', 'versionCode = 3127', 1)
g = g.replace('versionName = "0.3#17.8-v26"', 'versionName = "0.3#17.8-v27"', 1)
source.write_text(s, encoding='utf-8')
build.write_text(g, encoding='utf-8')
print('v27: manual synchronized GPU capture enabled (preserves v23)')

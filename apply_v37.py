#!/usr/bin/env python3
"""v37: independent opt-in DiPlay protocol-state A/B tests.

Do not change default RTSP, video, audio or iAP2 sequences. Based on documented
sender/receiver differences in CarPToCarL, CatPlay and OpenXPlay.
Apply strictly after apply_v36.py.
"""
from pathlib import Path
base=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")
def once(s,a,b,label):
    n=s.count(a)
    if n != 1:
        raise AssertionError(f"v37 {label}: expected 1 anchor, found {n}: {a[:115]!r}")
    return s.replace(a,b,1)

p=base/"CarPlayV37Options.kt"
if p.exists(): raise AssertionError("v37 options already exist")
p.write_text('''package io.github.nitsuya.aa.display.carplay

/** Controlled source-side protocol A/B tests. Both OFF by default. */
internal object CarPlayV37Options {
    private fun enabled(name: String): Boolean = runCatching {
        val cls = Class.forName("android.os.SystemProperties")
        val get = cls.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, name, "0") as? String) == "1"
    }.getOrDefault(false)

    /** POST modesChanged screen + main audio claim before type-110 screen SETUP. */
    fun claimBeforeScreen() = enabled("debug.carplay.v37_claim_before_screen")

    /** Move initial RECORD after type-110 SETUP and video dataPort TCP connect. */
    fun recordAfterScreen() = enabled("debug.carplay.v37_record_after_screen")
}
''',encoding="utf-8")

p=base/"CarPlayRtspSession.kt"
s=p.read_text(encoding="utf-8")
s=once(s,
'''        val v35PostAudioRecord = !mib3 && CarPlayV35Options.postAudioRecord()
''',
'''        val v35PostAudioRecord = !mib3 && CarPlayV35Options.postAudioRecord()
        val v37ClaimBeforeScreen = !mib3 && CarPlayV37Options.claimBeforeScreen()
        val v37RecordAfterScreen = !mib3 && CarPlayV37Options.recordAfterScreen()
        CarPlayV33Diag.stage("v37-options",
            "claimBeforeScreen=$v37ClaimBeforeScreen recordAfterScreen=$v37RecordAfterScreen")
        if (v37ClaimBeforeScreen && v37RecordAfterScreen) {
            Log.e(CarPlayConsts.TAG, "v37 experiments are mutually exclusive; disable one")
            return false
        }
''',"new opt-in snapshots")
s=once(s,
'''        } else {
            if (!sendRecord()) return false
            val screen = sendScreenSetup(listOf(screenStream), "diplay") ?: return false
''',
'''        } else {
            // Default remains v36: RECORD before screen stream SETUP.
            if (!v37RecordAfterScreen && !sendRecord()) return false
            if (v37ClaimBeforeScreen) {
                CarPlayV33Diag.stage("v37-modes-before-screen", "sending")
                val ok = announcePhoneModesChanged()
                CarPlayV33Diag.stage("v37-modes-before-screen", "success=$ok")
                // A failed claim is not an informative test of media startup.
                if (!ok) return false
            }
            val screen = sendScreenSetup(listOf(screenStream), "diplay") ?: return false
''',"DiPlay protocol branch")
s=once(s,
'''        screenEgress.getAndSet(egress)?.close()
        // Shared A/V timeline — must start before encoder + audio pumps.
''',
'''        screenEgress.getAndSet(egress)?.close()
        if (v37RecordAfterScreen) {
            // CarPToCarL-compatible A/B: the receiver has already accepted
            // type-110 SETUP and its dataPort TCP connection, but no AVC
            // media/encoder frame has been sent yet.
            CarPlayV33Diag.stage("v37-record-after-screen", "sending after video TCP")
            val ok = sendRecord()
            CarPlayV33Diag.stage("v37-record-after-screen", "success=$ok")
            if (!ok) {
                screenEgress.compareAndSet(egress, null)
                egress.close()
                return false
            }
        }
        // Shared A/V timeline — must start before encoder + audio pumps.
''',"move RECORD only in experimental branch")
p.write_text(s,encoding="utf-8")

p=Path("aa-display/build.gradle.kts")
s=p.read_text(encoding="utf-8")
s=once(s,"versionCode = 3136","versionCode = 3137","version code")
s=once(s,'versionName = "0.3#17.8-v36"','versionName = "0.3#17.8-v37"',"version name")
p.write_text(s,encoding="utf-8")
print("v37 applied: default unchanged; DiPlay modesChanged or delayed first RECORD opt-in, mutually exclusive")

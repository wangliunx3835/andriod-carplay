#!/usr/bin/env python3
"""v36 lean baseline and opt-in Bonjour readiness experiment.
Apply after v35. All previous patches stay in source control for rollback.
Default 0: no intentional control/Wi-Fi/RTSP timing change.
"""
from pathlib import Path
base=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")
def once(s,a,b,tag):
    n=s.count(a)
    if n!=1: raise AssertionError(f"v36 {tag}: expected 1 anchor found {n}: {a[:110]!r}")
    return s.replace(a,b,1)

p=base/"CarPlayV36Options.kt"
if p.exists(): raise AssertionError("v36 already applied")
p.write_text('''package io.github.nitsuya.aa.display.carplay

/** Read only on new dial / in diagnostics; all experiments off by default. */
internal object CarPlayV36Options {
    private fun read(key: String): Int = runCatching {
        val cls = Class.forName("android.os.SystemProperties")
        val getter = cls.getMethod("get", String::class.java, String::class.java)
        val value = getter.invoke(null, key, "0") as? String ?: "0"
        value.toIntOrNull() ?: 0
    }.getOrDefault(0)
    fun ctrlQuietMs(): Int = read("debug.carplay.v36_ctrl_quiet_ms").coerceIn(0, 1200)
    fun verboseVideo(): Boolean = read("debug.carplay.v36_verbose_video") == 1
    fun verboseFeedback(): Boolean = read("debug.carplay.v36_verbose_feedback") == 1
}
''',encoding="utf-8")

# Remove per-connection high-detail video dumps from the default path, keeping
# stage timings and the existing normal first-IDR/screen CONFIG logs intact.
p=base/"CarPlayV33Diag.kt";s=p.read_text(encoding="utf-8")
s=once(s,'''    private val videoN = AtomicInteger()
''','''    private val videoN = AtomicInteger()
    @Volatile private var v36VerboseVideoEnabled = false
''',"per-session cached video toggle")
s=once(s,'''        videoN.set(0)
''','''        videoN.set(0)
        v36VerboseVideoEnabled = CarPlayV36Options.verboseVideo()
''',"read verbose toggle once")
s=once(s,'''    fun video(bytes: ByteArray, ptsUs: Long, key: Boolean, config: Boolean, sent: Int) {
        val n = videoN.getAndIncrement()
''','''    fun video(bytes: ByteArray, ptsUs: Long, key: Boolean, config: Boolean, sent: Int) {
        if (!v36VerboseVideoEnabled) return
        val n = videoN.getAndIncrement()
''',"reduce verbose first-frames")
p.write_text(s,encoding="utf-8")

# Keep early playback feedback for the first 2 seconds; sample steady-state
# once every 30 feedbacks, instead of logging the first 12 and then 1/20.
# An explicit verbose switch retains the full old behavior for diagnosis.
p=base/"CarPlayRtspSession.kt";s=p.read_text(encoding="utf-8")
s=once(s,'''            if (v35FeedbackCount > 12 && v35FeedbackCount % 20 != 0) return
''','''            val v36Verbose = CarPlayV36Options.verboseFeedback()
            if (v36Verbose) {
                if (v35FeedbackCount > 12 && v35FeedbackCount % 20 != 0) return
            } else {
                if (v35FeedbackCount > 2 && v35FeedbackCount % 30 != 0) return
            }
''',"sample feedback")
p.write_text(s,encoding="utf-8")

# NsdManager registerService(...) is async. The first connection's 0x4301
# may race registration (seen in v35 logs); expose a wait for a real
# onServiceRegistered callback and a bounded quiet period.
p=base/"CarPlayBonjour.kt";s=p.read_text(encoding="utf-8")
s=once(s,'''import java.util.concurrent.atomic.AtomicBoolean
''','''import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
''',"Bonjour generation import")
s=once(s,'''    private var registeredAtMs = 0L
''','''    private var registeredAtMs = 0L
    /** Prevent a late callback for an old registration satisfying the gate. */
    private val v36CtrlGeneration = AtomicInteger(0)
    @Volatile private var v36CtrlReadyAtMs = 0L

    /** Optional, bounded wait; never hold a Wi-Fi or UI callback thread. */
    fun awaitV36CtrlQuiet(quietMs: Int, maxWaitMs: Long = 2_000L): String {
        if (quietMs <= 0) return "disabled"
        val started = SystemClock.uptimeMillis()
        val deadline = started + maxWaitMs
        while (SystemClock.uptimeMillis() < deadline) {
            val readyAt = v36CtrlReadyAtMs
            val now = SystemClock.uptimeMillis()
            if (readyAt > 0L && now - readyAt >= quietMs) {
                return "ready waited=${now-started}ms"
            }
            try {
                Thread.sleep(40L)
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
                return "interrupted"
            }
        }
        return "timeout waited=${SystemClock.uptimeMillis()-started}ms"
    }
''',"Bonjour ack state")
s=once(s,'''        if (registered.get()) {
            unregisterQuietly()
''','''        val v36Generation = v36CtrlGeneration.incrementAndGet()
        v36CtrlReadyAtMs = 0L
        if (registered.get()) {
            unregisterQuietly()
''',"new registration generation")
s=once(s,'''                registered.set(true)
                registeredAtMs = SystemClock.uptimeMillis()
            }

            override fun onServiceUnregistered''','''                registered.set(true)
                registeredAtMs = SystemClock.uptimeMillis()
                if (v36CtrlGeneration.get() == v36Generation) {
                    v36CtrlReadyAtMs = registeredAtMs
                }
            }

            override fun onServiceUnregistered''',"Bonjour callback ack")
s=once(s,'''        unregisterQuietly()
        airplayEndpoint.set(null)
''','''        unregisterQuietly()
        v36CtrlReadyAtMs = 0L
        airplayEndpoint.set(null)
''',"reset on stop")
p.write_text(s,encoding="utf-8")

# Only optional first dial delay, AFTER IPv4 has passed the real TCP reachability
# probe. Does not slow the v23 quick gateway / association code, and never blocks
# Bluetooth 0x4301 or Wi-Fi callbacks. If Bonjour never confirms, proceed after
# 2 seconds instead of deadlocking.
p=base/"CarPlaySourceSession.kt";s=p.read_text(encoding="utf-8")
s=once(s,'''                    prepareMediaPipeline("airplay-dial")
''','''                    // v36 A/B: avoid starting the first RTSP/media session
                    // while forced _carplay-ctrl re-registration is still
                    // awaiting NsdManager acknowledgement on the new Wi-Fi.
                    if (!wired && attempt == 1) {
                        val quietMs = CarPlayV36Options.ctrlQuietMs()
                        if (quietMs > 0) {
                            val outcome = bonjour?.awaitV36CtrlQuiet(quietMs)
                                ?: "bonjour-not-started"
                            Log.i(CarPlayConsts.TAG,
                                "v36 ctrl-settle quietMs=$quietMs $outcome")
                        }
                    }
                    prepareMediaPipeline("airplay-dial")
''',"gate RTSP dial after probe")
p.write_text(s,encoding="utf-8")

p=Path("aa-display/build.gradle.kts");s=p.read_text(encoding="utf-8")
s=once(s,"versionCode = 3135","versionCode = 3136","version code")
s=once(s,'versionName = "0.3#17.8-v35"','versionName = "0.3#17.8-v36"',"version name")
p.write_text(s,encoding="utf-8")
print("v36 applied: lean per-session diagnostics; opt-in Bonjour ack/quiet gate, no default RTSP timing changes")

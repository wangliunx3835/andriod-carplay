#!/usr/bin/env python3
"""v40: reduce confirmed useless runtime observations without touching wire protocol.

Apply strictly after apply_v39.py. Retain successful v39 first-connect fix,
v23 IPv4 readiness, normal RTSP feedback packets, iAP2, codec, rendering and
touch/IME logic. Changes:
  - rate-limit absent NowPlaying artwork Binder fetch/thread to 20s per revision;
  - disable legacy manual GPU capture *file polling* unless expressly opted in;
  - stop default 1Hz feedback plist parsing and steady-state diagnostic logs.
"""
from pathlib import Path

base = Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")

def once(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise AssertionError(f"v40 {label}: expected 1 anchor, got {n}: {old[:120]!r}")
    return s.replace(old, new, 1)

options = base / "CarPlayV40Options.kt"
if options.exists():
    raise AssertionError("v40 options already exist")
options.write_text('''package io.github.nitsuya.aa.display.carplay

/** Optional diagnostics; defaults avoid polling/logging during normal playback. */
internal object CarPlayV40Options {
    private fun enabled(key: String): Boolean = runCatching {
        val cls = Class.forName("android.os.SystemProperties")
        val get = cls.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, key, "0") as? String) == "1"
    }.getOrDefault(false)

    /** Read once at compositor creation; restart app after changing. */
    fun manualCapture(): Boolean = enabled("debug.carplay.v40_manual_gpu_capture")

    /** Read once at AirPlay RTSP session object creation. */
    fun verboseControl(): Boolean = enabled("debug.carplay.v40_verbose_control")
}
''', encoding="utf-8")

# v40: no available JPEG used to launch a new thread and query CoreApi Binder
# every second, then warn on every miss. Revision change still retries at once.
p = base / "CarPlayNowPlaying.kt"
s = p.read_text(encoding="utf-8")
s = once(s,
'''    private val artLock = Any()
''',
'''    private val artLock = Any()
    // Prevent a missing album cover from causing 1 thread + 1 Binder IPC / sec.
    // A different art revision always bypasses the 20s absent-art cooldown.
    private val v40ArtFetchRunning = AtomicBoolean(false)
    private var v40LastArtAttemptRevision = Long.MIN_VALUE
    private var v40NextArtAttemptAtMs = 0L
''', "artwork throttle state")
s = once(s,
'''        pushedArtRevision = -1L
        boundArtTransferId = null
''',
'''        pushedArtRevision = -1L
        v40LastArtAttemptRevision = Long.MIN_VALUE
        v40NextArtAttemptAtMs = 0L
        boundArtTransferId = null
''', "reset artwork cooldown on transport change")
s = once(s,
'''    private fun maybeTransferArtwork(revision: Long, trackId: String?) {
        Thread(
            {
                val e = egress
''',
'''    private fun maybeTransferArtwork(revision: Long, trackId: String?) {
        val now = android.os.SystemClock.uptimeMillis()
        if (v40LastArtAttemptRevision == revision && now < v40NextArtAttemptAtMs) return
        if (!v40ArtFetchRunning.compareAndSet(false, true)) return
        v40LastArtAttemptRevision = revision
        v40NextArtAttemptAtMs = now + 20_000L
        Thread(
            {
                try {
                val e = egress
''', "throttle absent-art worker")
s = once(s,
'''                if (e == null || jpeg == null || jpeg.isEmpty()) {
                    Log.w(TAG, "artwork skip — jpeg=${jpeg?.size ?: -1}B egress=${e != null}")
                    return@Thread
                }
''',
'''                if (e == null || jpeg == null || jpeg.isEmpty()) {
                    // No artwork yet: wait for a new revision or the next
                    // 20s retry window. Avoid per-second warnings/IPC.
                    return@Thread
                }
''', "no-art warning and fast retry removal")
s = once(s,
'''                Log.i(TAG, "artwork transfer started id=$id size=${jpeg.size}B track=${trackId?.take(24)}")
            },
            "cp-nowplaying-art",
''',
'''                Log.i(TAG, "artwork transfer started id=$id size=${jpeg.size}B track=${trackId?.take(24)}")
                } finally {
                    v40ArtFetchRunning.set(false)
                }
            },
            "cp-nowplaying-art",
''', "always release artwork worker lock")
p.write_text(s, encoding="utf-8")

# v40: manual GPU readback remains available, but default rendering
# no longer checks a trigger file every second.
p = base / "CarPlayGlCompositor.kt"
s = p.read_text(encoding="utf-8")
s = once(s,
'''    private var v27CaptureSequence = 0
''',
'''    private var v27CaptureSequence = 0
    private val v40ManualCaptureEnabled = CarPlayV40Options.manualCapture()
''', "cached opt-in manual GPU capture state")
s = once(s,
'''        val v27ManualCapture = v27ConsumeTrigger()
''',
'''        val v27ManualCapture = if (v40ManualCaptureEnabled) v27ConsumeTrigger() else false
''', "skip default GPU capture file poll")
p.write_text(s, encoding="utf-8")

# v40: RTSP feedback is REQUIRED and continues unchanged every ~1s.
# Disable only unnecessary normal-mode decode and logs.
p = base / "CarPlayRtspSession.kt"
s = p.read_text(encoding="utf-8")
s = once(s,
'''    private val controlPumpLive = AtomicBoolean(false)
''',
'''    private val controlPumpLive = AtomicBoolean(false)
    private val v40VerboseControlLog = CarPlayV40Options.verboseControl()
''', "one-time control diagnostic option")
s = once(s,
'''        var v35FeedbackCount = 0
''',
'''        val v40VerboseFeedback = CarPlayV36Options.verboseFeedback()
        var v40FeedbackAckLogged = false
        var v35FeedbackCount = 0
''', "per-session feedback diagnostic switches")
s = once(s,
'''            inspectV35Feedback(msg)
            if (!deliverControlResponse(msg)) {
                Log.i(
                    CarPlayConsts.TAG,
                    "AirPlay enc ← ${msg.firstLine} body=${msg.body.size}B (orphan cseq=${msg.cSeq})",
                )
            }
''',
'''            if (v40VerboseFeedback) inspectV35Feedback(msg)
            if (!deliverControlResponse(msg)) {
                // POST /feedback is intentionally write-only, and its 200 is
                // not a protocol error. Log first ack only, or in verbose mode.
                val feedbackAck = msg.cSeq >= 900_000 && msg.firstLine.startsWith("RTSP/")
                if (!feedbackAck || v40VerboseFeedback || !v40FeedbackAckLogged) {
                    Log.i(
                        CarPlayConsts.TAG,
                        "AirPlay enc ← ${msg.firstLine} body=${msg.body.size}B (orphan cseq=${msg.cSeq})",
                    )
                }
                if (feedbackAck) v40FeedbackAckLogged = true
            }
''', "stop default parse and 1Hz orphan-ack logs")
s = once(s,
'''        Log.d(CarPlayConsts.TAG, "control feedback → cseq=$seq")
''',
'''        if (v40VerboseControlLog) {
            Log.d(CarPlayConsts.TAG, "control feedback → cseq=$seq")
        }
''', "stop 1Hz request debug log")
p.write_text(s, encoding="utf-8")

p = Path("aa-display/build.gradle.kts")
s = p.read_text(encoding="utf-8")
s = once(s, "versionCode = 3139", "versionCode = 3140", "version code")
s = once(s, 'versionName = "0.3#17.8-v39"',
            'versionName = "0.3#17.8-v40"', "version name")
p.write_text(s, encoding="utf-8")

print("v40 applied: no 1Hz absent-art workers, default GPU file poll OFF, feedback diagnostics lean; wire unchanged")

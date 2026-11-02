#!/usr/bin/env python3
"""v51: proven reverse default ON; disconnect cleanup; orphan mute release;
opt-in MediaProjection isolation A/B. Apply after v50."""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise AssertionError(f"v51 {label}: {n} matches")
    return s.replace(a,b,1)
def change(path,updates):
    p=R/path; s=p.read_text(encoding="utf-8")
    for a,b,label in updates: s=one(s,a,b,label)
    p.write_text(s,encoding="utf-8")
change("carplay/CarPlayV50Options.kt",[
('    fun reverseGate() = enabled("debug.carplay.v50_reverse_video_gate")',
'''    // v51: verified reverse priority is ON by default, but property 0 opts out.
    fun reverseGate(): Boolean = runCatching {
        val p = Class.forName("android.os.SystemProperties")
        val get = p.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, "debug.carplay.v50_reverse_video_gate", "1") as String) != "0"
    }.getOrDefault(true)''',"reverse default")
])
change("carplay/CarPlayHostActivity.kt",[
('''        /** Best-effort Activity launch; always also arms [CarPlayHostRuntime]. */
        fun launch(context: Context) {
            CarPlayHostRuntime.ensureStarted(context)''',
'''        /** BAL trampoline only; real HU SETUP boots Host/VDs. */
        fun launch(context: Context) {''',"no premature host launch"),
('''        // Sync boot so SETUP in the same tick sees a live compositor.
        CarPlayHostRuntime.ensureStartedSync(this, timeoutMs = 5_000L)
        CarPlayProjectionService.start(this)''',
'''        // Never preboot VDs before actual receiver connection.
        CarPlayProjectionService.start(this)''',"no premature host onCreate")
])
change("carplay/CarPlayProjectionService.kt",[
('''        fun isSessionArmed(): Boolean = sessionRef.get() != null''',
'''        fun isSessionArmed(): Boolean = sessionRef.get() != null
        fun isScreenStreaming(): Boolean = sessionRef.get()?.isScreenStreaming() == true''',"stream state"),
('''        session?.stop()
        session = null
        sessionRef.set(null)
        CarPlayHostRuntime.stop(reason)
        reportLive(false)
        stopForeground(STOP_FOREGROUND_REMOVE)''',
'''        try {
            runCatching { session?.stop() }
                .onFailure { Log.e(CarPlayConsts.TAG, "v51 session stop failed", it) }
            session = null
            sessionRef.set(null)
            runCatching { CarPlayHostRuntime.stop(reason) }
                .onFailure { Log.e(CarPlayConsts.TAG, "v51 Host stop failed", it) }
        } finally {
            // system_server owns phone mute; always release, even after local crash
            reportLive(false)
            stopForeground(STOP_FOREGROUND_REMOVE)
        }''',"guaranteed service cleanup")
])
change("carplay/CarPlayStatusUi.kt",[
('''        val armed = CarPlayProjectionService.isSessionArmed()
        val hostUp = CarPlayHostRuntime.isRunning()''',
'''        val armed = CarPlayProjectionService.isSessionArmed()
        val streaming = CarPlayProjectionService.isScreenStreaming()
        val hostUp = CarPlayHostRuntime.isRunning()''',"real streaming status"),
('''            live && hostUp -> Triple(''',
'''            live && streaming && hostUp -> Triple(''',"true output status"),
('''            live -> Triple(
                "正在准备画面…",''',
'''            streaming -> Triple(
                "正在准备画面…",''',"no false preparing")
])
change("carplay/CarPlaySourceSession.kt",[
('''    fun start() {
        if (!running.compareAndSet(false, true)) return''',
'''    fun isScreenStreaming(): Boolean = rtsp?.isStreaming() == true

    fun start() {
        if (!running.compareAndSet(false, true)) return''',"source state"),
('''    private val releasePhoneAudio = Runnable {
        if (!running.get()) return@Runnable
        if (rtsp?.isStreaming() == true) {
            Log.i(CarPlayConsts.TAG, "skip phone audio release — streaming again")
            return@Runnable
        }
        val reason = pendingAudioReleaseReason
        Log.i(CarPlayConsts.TAG, "CarPlay HU gone ($reason) — restore phone volume")
        ProjectionSessionGate.setCarPlayLive(false)
        try {
            CoreApi.reportCarPlaySessionLive(false)
        } catch (e: Throwable) {
            Log.e(CarPlayConsts.TAG, "reportCarPlaySessionLive(false) failed", e)
        }
    }''',
'''    private val releasePhoneAudio = Runnable {
        if (!running.get()) return@Runnable
        if (rtsp?.isStreaming() == true) {
            Log.i(CarPlayConsts.TAG, "skip phone audio release — streaming again")
            return@Runnable
        }
        val reason = pendingAudioReleaseReason
        Log.i(CarPlayConsts.TAG, "v51 HU media ended ($reason) — restore phone volume/VDs")
        ProjectionSessionGate.setCarPlayLive(false)
        try {
            CoreApi.reportCarPlaySessionLive(false)
        } catch (e: Throwable) {
            Log.e(CarPlayConsts.TAG, "reportCarPlaySessionLive(false) failed", e)
        }
        runCatching { CoreApi.setCarPlayAudioEgressEnabled(false) }
            .onFailure { Log.w(CarPlayConsts.TAG, "v51 audio disarm fallback failed", it) }
        if (rtsp?.isStreaming() == true) return@Runnable
        cancelGlRebindRetry()
        glCompositor?.onRateReport = null
        runCatching { glCompositor?.detachEncoder() }
        tee.stop()
        encoder.stop()
        CarPlayNowPlaying.stop()
        mediaPrepared.set(false)
        runCatching { CarPlayHostRuntime.stop("v51-hu-ended:$reason") }
            .onFailure { Log.e(CarPlayConsts.TAG, "v51 Host cleanup failed", it) }
        glCompositor = null
        Log.i(CarPlayConsts.TAG, "v51 HU idle cleanup finished; listeners kept")
    }''',"HU disconnect cleanup")
])
change("xposed/carplay/CarPlayAudioCapture.kt",[
('''    private const val PULL_TIMEOUT_MS = 5 * 60_000L''',
'''    private const val PULL_TIMEOUT_MS = 5 * 60_000L
    // Recover if AADisplay process died and could not send live=false.
    private const val V51_ORPHAN_NO_PULL_MS = 90_000L''',"orphan safety"),
('''                proj = obtainMediaProjection(ctx)
                if (proj != null) {''',
'''                proj = if (v51NoMediaProjection()) {
                    log(TAG, "v51 projection isolation: MediaProjection bypassed")
                    null
                } else obtainMediaProjection(ctx)
                if (proj != null) {''',"isolate audio projection"),
('''                    runCatching {
                        proj.registerCallback(
                            object : MediaProjection.Callback() {
                                override fun onStop() {
                                    if (ignoringProjectionStop) return''',
'''                    val registeredProjection = proj
                    runCatching {
                        proj.registerCallback(
                            object : MediaProjection.Callback() {
                                override fun onStop() {
                                    if (ignoringProjectionStop ||
                                        mediaProjection !== registeredProjection) return''',"guard late callback"),
('''                if (mediaRec == null) {
                    mediaRec = openRemoteSubmixRecord(MEDIA_SAMPLE_RATE, MEDIA_CHANNEL_MASK)
                    mMode = "remote-submix"
                }''',
'''                if (mediaRec == null) {
                    // Failed playback capture must not keep a screen-capture
                    // projection when falling back to REMOTE_SUBMIX.
                    if (proj != null) {
                        ignoringProjectionStop = true
                        try {
                            runCatching { proj.stop() }
                                .onFailure { log(TAG, "v51 unused projection stop failed", it) }
                        } finally {
                            proj = null
                            ignoringProjectionStop = false
                        }
                    }
                    mediaRec = openRemoteSubmixRecord(MEDIA_SAMPLE_RATE, MEDIA_CHANNEL_MASK)
                    mMode = "remote-submix"
                }''',"stop unused projection"),
('''    private fun scheduleWatchdog(handler: Handler) {''',
'''    private fun v51NoMediaProjection(): Boolean = runCatching {
        val c = Class.forName("android.os.SystemProperties")
        val m = c.getMethod("getBoolean", String::class.java, Boolean::class.javaPrimitiveType)
        m.invoke(null, "debug.carplay.v51_no_media_projection", false) == true
    }.getOrDefault(false)

    private fun scheduleWatchdog(handler: Handler) {''',"opt-in option"),
('''                if (System.currentTimeMillis() - lastPullMs.get() > PULL_TIMEOUT_MS) {''',
'''                val noPullMs = System.currentTimeMillis() - lastPullMs.get()
                if (noPullMs > V51_ORPHAN_NO_PULL_MS) {
                    log(TAG, "v51 no audio pulls for " + (noPullMs / 1000) +
                        "s; release orphan capture and restore phone volumes")
                    setEnabled(false)
                    return@postDelayed
                }
                if (noPullMs > PULL_TIMEOUT_MS) {''',"watchdog stops orphan")
])
p=Path("aa-display/build.gradle.kts")
s=p.read_text(encoding="utf-8")
s=one(s,"versionCode = 3150","versionCode = 3151","version code")
s=one(s,'versionName = "0.3#17.8-v50"','versionName = "0.3#17.8-v51"',"version name")
p.write_text(s,encoding="utf-8")
print("v51 applied: reverse default, disconnect cleanup, orphan recovery, projection A/B")

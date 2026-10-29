#!/usr/bin/env python3
"""v33 diagnostic + two opt-in A/V experiments. Apply after v32."""
from pathlib import Path
base=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")
def once(s,a,b,tag):
 n=s.count(a)
 if n!=1: raise AssertionError(f"v33 {tag}: {n} matches for {a[:90]!r}")
 return s.replace(a,b,1)
d=base/"CarPlayV33Diag.kt"
if d.exists(): raise AssertionError("v33 exists")
d.write_text('''package io.github.nitsuya.aa.display.carplay

import android.os.SystemClock
import android.util.Log
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong

/** Monotonic first-connect and fallback diagnostics. No secret keys logged. */
internal object CarPlayV33Diag {
    private val session = AtomicInteger()
    private val startedAt = AtomicLong()
    private val videoN = AtomicInteger()
    private val audioN = AtomicInteger()
    private val lastPts = AtomicLong(-1)
    private fun prop(name: String): Int = runCatching {
        val cls = Class.forName("android.os.SystemProperties")
        val text = cls.getMethod("get", String::class.java, String::class.java)
            .invoke(null, name, "0") as? String ?: "0"
        text.toIntOrNull() ?: 0
    }.getOrDefault(0)
    fun fps(): Int = if (prop("debug.carplay.v33_video_fps") == 30) 30 else 0
    fun delayMs(): Int = prop("debug.carplay.v33_audio_delay_ms").coerceIn(0, 1500)
    fun begin(route: String, hu: String, target: String) {
        session.incrementAndGet()
        startedAt.set(SystemClock.elapsedRealtime())
        videoN.set(0)
        audioN.set(0)
        lastPts.set(-1)
        stage("begin", "route=$route hu=$hu target=$target fpsOverride=${fps()} audioDelayMs=${delayMs()}")
    }
    fun stage(name: String, details: String = "") {
        val start = startedAt.get()
        val elapsed = if (start > 0L) SystemClock.elapsedRealtime() - start else -1L
        Log.i(CarPlayConsts.TAG, "v33 session=${session.get()} +${elapsed}ms $name $details")
    }
    fun video(bytes: ByteArray, ptsUs: Long, key: Boolean, config: Boolean, sent: Int) {
        val n = videoN.getAndIncrement()
        if (n >= 6) return
        val prev = lastPts.getAndSet(ptsUs)
        val delta = if (prev < 0L) 0L else ptsUs - prev
        val head = bytes.take(12).joinToString("") { "%02x".format(it.toInt() and 255) }
        stage("video#$n", "size=${bytes.size} ptsUs=$ptsUs deltaUs=$delta key=$key config=$config sent=$sent head=$head")
    }
    fun audioFirst(type: String, bytes: Int, pts: Long) {
        if (audioN.getAndIncrement() == 0) stage("audio-first", "type=$type bytes=$bytes rtpTs=$pts")
    }
}
''')
p=base/"CarPlaySourceSession.kt";s=p.read_text()
s=once(s,'''        supplyFps = CarPlayConsts.DEFAULT_VIDEO_FPS
        badRateWindows = 0
''','''        supplyFps = CarPlayV33Diag.fps().takeIf { it > 0 }
            ?: CarPlayConsts.DEFAULT_VIDEO_FPS
        Log.i(CarPlayConsts.TAG, "v33 supplyFps=$supplyFps")
        badRateWindows = 0
''',"fps selection")
s=once(s,'''    private fun onRateReport(targetFps: Int, actualFps: Float) {
        if (!running.get() || encoder.currentFps() == 0) return
''','''    private fun onRateReport(targetFps: Int, actualFps: Float) {
        if (CarPlayV33Diag.fps() == 30) return // fixed 30fps test, no adaptive recovery
        if (!running.get() || encoder.currentFps() == 0) return
''',"fps lock")
s=once(s,'''    private val encoder = CarPlayVideoEncoder { bytes, ptsUs, key, config ->
        val written = rtsp?.sendVideoAccessUnit(bytes, ptsUs, key, config) ?: 0
''','''    private val encoder = CarPlayVideoEncoder { bytes, ptsUs, key, config ->
        val written = rtsp?.sendVideoAccessUnit(bytes, ptsUs, key, config) ?: 0
        CarPlayV33Diag.video(bytes, ptsUs, key, config, written)
''',"video trace")
p.write_text(s)
p=base/"CarPlayRtspSession.kt";s=p.read_text()
s=once(s,'''            try {
                val mib3 = huProfile.usesMib3WirelessPath
''','''            try {
                CarPlayV33Diag.begin(
                    if (deviceId == null) "fallback" else "start-session",
                    huProfile.id, "${host.hostAddress}:$port")
                val mib3 = huProfile.usesMib3WirelessPath
''',"route")
s=once(s,'''                controlWriteKey.set(verify.writeKey)
                controlReadKey.set(verify.readKey)
''','''                CarPlayV33Diag.stage("pair-verify-success")
                controlWriteKey.set(verify.writeKey)
                controlReadKey.set(verify.readKey)
''',"pairing")
s=once(s,'''                val ok = runEncryptedSetupRecord(
                    peerHost = host,
''','''                CarPlayV33Diag.stage("setup-start")
                val ok = runEncryptedSetupRecord(
                    peerHost = host,
''',"setup started")
s=once(s,'''                if (!ok) {
                    Log.e(CarPlayConsts.TAG, "encrypted SETUP/RECORD / screen open failed")
''','''                CarPlayV33Diag.stage("setup-finished", "success=$ok")
                if (!ok) {
                    Log.e(CarPlayConsts.TAG, "encrypted SETUP/RECORD / screen open failed")
''',"setup ended")
s=once(s,'''                // Keep encrypted control alive (feedback); video is on dataPort.
''','''                CarPlayV33Diag.stage("control-pump-enter")
                // Keep encrypted control alive (feedback); video is on dataPort.
''',"control start")
s=once(s,'''            } catch (e: Throwable) {
                Log.e(CarPlayConsts.TAG, "AirPlay source dial failed", e)
            } finally {
                controlPumpLive.set(false)
''','''            } catch (e: Throwable) {
                CarPlayV33Diag.stage("dial-exception", e.javaClass.simpleName)
                Log.e(CarPlayConsts.TAG, "AirPlay source dial failed", e)
            } finally {
                CarPlayV33Diag.stage("control-worker-exit")
                controlPumpLive.set(false)
''',"control exit")
s=once(s,'''                "fps" to CarPlayConsts.DEFAULT_VIDEO_FPS.toLong(),
                "usingScreen" to true,
''','''                "fps" to (CarPlayV33Diag.fps().takeIf { it > 0 }
                    ?: CarPlayConsts.DEFAULT_VIDEO_FPS).toLong(),
                "usingScreen" to true,
''',"screen fps advertisement")
s=once(s,'''        // Audio: Audi MIB3 needs type-102 AAC-LC (CSM path). DiPlay keeps type-100 PCM.
''','''        CarPlayV33Diag.stage("audio-setup-begin", "mib3=$mib3")
        // Audio: Audi MIB3 needs type-102 AAC-LC (CSM path). DiPlay keeps type-100 PCM.
''',"audio start")
s=once(s,'''        onSessionReady()
        Log.i(CarPlayConsts.TAG, "screen egress armed — AVC frames → dataPort=$dataPort")
''','''        CarPlayV33Diag.stage("audio-setup-finished")
        onSessionReady()
        CarPlayV33Diag.stage("screen-egress-armed", "dataPort=$dataPort")
        Log.i(CarPlayConsts.TAG, "screen egress armed — AVC frames → dataPort=$dataPort")
''',"screen ready")
p.write_text(s)
p=base/"CarPlayAudioEgress.kt";s=p.read_text()
s=once(s,'''        flushPreTxBacklog(profile)
        // Absolute cadence: at most one packet per interval.
''','''        flushPreTxBacklog(profile)
        // Opt-in: delay only first media RTP, not RTSP SETUP or AAC/PCM format.
        val v33ExtraDelay =
            if (profile.audioType == "media") CarPlayV33Diag.delayMs() else 0
        if (v33ExtraDelay > 0) {
            CarPlayV33Diag.stage("audio-delay-start", "ms=$v33ExtraDelay")
            val stopAt = android.os.SystemClock.elapsedRealtime() + v33ExtraDelay
            while (running.get() && android.os.SystemClock.elapsedRealtime() < stopAt) {
                try { Thread.sleep(20L) } catch (_: InterruptedException) { break }
            }
            if (!running.get()) return
            flushPreTxBacklog(profile)
            rtpTimestamp = CarPlayMediaClock.rtpTimestamp(profile.sampleRate)
            CarPlayV33Diag.stage("audio-delay-finished")
        }
        // Absolute cadence: at most one packet per interval.
''',"audio delay")
s=once(s,'''                packets++
                if (packets <= 3 || packets % 500 == 0) {
''','''                packets++
                if (packets == 1) {
                    CarPlayV33Diag.audioFirst(profile.audioType, datagram.size, timestamp.toLong())
                }
                if (packets <= 3 || packets % 500 == 0) {
''',"first rtp")
p.write_text(s)
p=Path("aa-display/build.gradle.kts");s=p.read_text()
s=once(s,"versionCode = 3132","versionCode = 3133","version code")
s=once(s,'versionName = "0.3#17.8-v32"','versionName = "0.3#17.8-v33"',"version name")
p.write_text(s)
print("v33 applied: v32 defaults, monotonic timeline, optional 30fps screen+codec, optional media RTP delay")

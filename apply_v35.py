#!/usr/bin/env python3
"""v35: parse AirPlay /feedback, opt-in Screen KeepAlive + post-audio RECORD.

Run after apply_v34.py; preserve all earlier patches. Only feedback diagnostics
change in default mode. Set experimental props before force-stop/restart:
 debug.carplay.v35_screen_ka=1
 debug.carplay.v35_post_audio_record=1
Run experiments separately; DiPlay/generic only, Audi MIB3 untouched.
"""
from pathlib import Path
base=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")
def once(s,a,b,tag):
    n=s.count(a)
    if n!=1: raise AssertionError(f"v35 {tag}: expected one anchor found {n}: {a[:100]!r}")
    return s.replace(a,b,1)

p=base/"CarPlayV35Options.kt"
if p.exists(): raise AssertionError("v35 options already present")
p.write_text('''package io.github.nitsuya.aa.display.carplay

/** Experimental options sampled once per new AirPlay connection. */
internal object CarPlayV35Options {
    private fun enabled(key: String): Boolean = runCatching {
        val cls = Class.forName("android.os.SystemProperties")
        val getter = cls.getMethod("get", String::class.java, String::class.java)
        (getter.invoke(null, key, "0") as? String) == "1"
    }.getOrDefault(false)
    fun screenKeepAlive() = enabled("debug.carplay.v35_screen_ka")
    fun postAudioRecord() = enabled("debug.carplay.v35_post_audio_record")
}
''', encoding="utf-8")

p=base/"protocol/ScreenStreamEgress.kt";s=p.read_text(encoding="utf-8")
s=once(s,
'''import java.util.concurrent.atomic.AtomicLong
''',
'''import java.util.concurrent.atomic.AtomicLong
import kotlin.concurrent.thread
''',"thread import")
s=once(s,
'''    private val firstIdrSent = AtomicBoolean(false)
    private var loggedWaitingForIdr = false
''',
'''    private val firstIdrSent = AtomicBoolean(false)
    private var loggedWaitingForIdr = false
    private val v35KeepAliveStarted = AtomicBoolean(false)
''',"keepalive lifecycle")
s=once(s,
'''    private fun writeFrame(header: ByteArray, payload: ByteArray): Boolean {
''',
'''    /**
     * v35 opt-in: Screen KeepAlive is an independent unencrypted 128-byte
     * frame (opcode=2). It does not advance the ChaCha frame nonce. It uses
     * exactly the video OutputStream monitor so headers never interleave with
     * an encrypted video write. Start only after the first IDR is delivered.
     */
    fun startV35ScreenKeepAlive() {
        if (closed.get() || !v35KeepAliveStarted.compareAndSet(false, true)) return
        Log.i(CarPlayConsts.TAG, "v35 screen KA armed interval=1000ms opcode=2 (after IDR)")
        thread(name = "carplay-v35-screen-keepalive", isDaemon = true) {
            var sent = 0L
            var lastAt = android.os.SystemClock.elapsedRealtime()
            while (!closed.get()) {
                try {
                    Thread.sleep(200L)
                } catch (_: InterruptedException) {
                    break
                }
                if (closed.get() || !firstIdrSent.get()) continue
                val now = android.os.SystemClock.elapsedRealtime()
                if (now - lastAt < 1_000L) continue
                val header = ByteArray(HEADER_LEN)
                header[4] = OPCODE_KEEPALIVE
                try {
                    synchronized(out) {
                        if (closed.get()) return@thread
                        out.write(header)
                        out.flush()
                    }
                    lastAt = now
                    sent++
                    if (sent <= 5 || sent % 30L == 0L) {
                        Log.i(CarPlayConsts.TAG, "v35 screen KA sent #$sent opcode=2 bytes=128")
                    }
                } catch (e: Throwable) {
                    if (!closed.get()) Log.w(CarPlayConsts.TAG, "v35 screen KA write failed", e)
                    close()
                    break
                }
            }
        }
    }

    private fun writeFrame(header: ByteArray, payload: ByteArray): Boolean {
''',"screen keepalive sender")
s=once(s,
'''        private const val OPCODE_CONFIG: Byte = 0x01
''',
'''        private const val OPCODE_CONFIG: Byte = 0x01
        private const val OPCODE_KEEPALIVE: Byte = 0x02
''',"screen KA opcode")
p.write_text(s,encoding="utf-8")

p=base/"CarPlayRtspSession.kt";s=p.read_text(encoding="utf-8")
# All 3 features are evaluated on a fresh AirPlay session only.
s=once(s,
'''        val v34Enabled = !mib3 && CarPlayV34Options.mediaBarrier()
''',
'''        val v34Enabled = !mib3 && CarPlayV34Options.mediaBarrier()
        val v35ScreenKa = !mib3 && CarPlayV35Options.screenKeepAlive()
        val v35PostAudioRecord = !mib3 && CarPlayV35Options.postAudioRecord()
        CarPlayV33Diag.stage("v35-options",
            "screenKA=$v35ScreenKa postAudioRecord=$v35PostAudioRecord mediaBarrier=$v34Enabled mib3=$mib3")
''',"option snapshot")
# Feedback responses are handled by the existing single control reader.
s=once(s,
'''        controlOnMessage.set { msg ->
            if (handleControlRequest(msg)) {
''',
'''        var v35FeedbackCount = 0
        fun inspectV35Feedback(msg: RtspMessage) {
            if (msg.cSeq < 900_000 || !msg.firstLine.startsWith("RTSP/") ||
                msg.body.isEmpty()) return
            v35FeedbackCount++
            // Diagnose first-connect reset: always dump first 12, then one in
            // 20. No raw body logged and no impact on RTSP response demux.
            if (v35FeedbackCount > 12 && v35FeedbackCount % 20 != 0) return
            try {
                val root = BinaryPlist.asDict(BinaryPlist.decode(msg.body))
                val streams = root?.get("streams") as? List<*>
                val summary = streams?.mapIndexed { index, item ->
                    val d = BinaryPlist.asDict(item)
                    "[$index type=${d?.get("type")} id=${d?.get("streamConnectionID")} " +
                        "sampleTime=${d?.get("sampleTime")} sr=${d?.get("sr")} " +
                        "ts=${d?.get("timestamp")}]"
                }?.joinToString(" ")?.take(680)
                CarPlayV33Diag.stage("v35-feedback",
                    "n=$v35FeedbackCount cseq=${msg.cSeq} " +
                    "streams=${streams?.size ?: 0} $summary " +
                    "keys=${root?.keys?.joinToString(",")?.take(140)}")
            } catch (e: Throwable) {
                CarPlayV33Diag.stage("v35-feedback-parse-failed",
                    "n=$v35FeedbackCount body=${msg.body.size} err=${e.javaClass.simpleName}")
            }
        }
        controlOnMessage.set { msg ->
            if (handleControlRequest(msg)) {
''',"feedback parser")
s=once(s,
'''            if (!deliverControlResponse(msg)) {
                Log.i(
''',
'''            inspectV35Feedback(msg)
            if (!deliverControlResponse(msg)) {
                Log.i(
''',"feedback observation")
s=once(s,
'''        CarPlayV33Diag.stage("audio-setup-finished")
        onSessionReady()
''',
'''        CarPlayV33Diag.stage("audio-setup-finished")
        if (v35PostAudioRecord) {
            CarPlayV33Diag.stage("v35-post-audio-record", "start")
            val recordOk = sendRecord()
            CarPlayV33Diag.stage("v35-post-audio-record", "success=$recordOk")
            if (!recordOk) return false
        }
        onSessionReady()
''',"optional second RECORD")
s=once(s,
'''        CarPlayV33Diag.stage("screen-egress-armed", "dataPort=$dataPort")
        Log.i(CarPlayConsts.TAG, "screen egress armed — AVC frames → dataPort=$dataPort")
''',
'''        CarPlayV33Diag.stage("screen-egress-armed", "dataPort=$dataPort")
        if (v35ScreenKa) egress.startV35ScreenKeepAlive()
        Log.i(CarPlayConsts.TAG, "screen egress armed — AVC frames → dataPort=$dataPort")
''',"start optional screen KA")
p.write_text(s,encoding="utf-8")
p=Path("aa-display/build.gradle.kts");s=p.read_text(encoding="utf-8")
s=once(s,"versionCode = 3134","versionCode = 3135","version code")
s=once(s,'versionName = "0.3#17.8-v34"','versionName = "0.3#17.8-v35"',"version name")
p.write_text(s,encoding="utf-8")
print("v35 applied: feedback decode + opt-in DiPlay screen keepalive and post-audio RECORD")

#!/usr/bin/env python3
"""v34: optional DiPlay media-start barrier + persistent StartSession history.
Apply strictly after v33. Default property 0 preserves v33 media behavior.
Enable on new connection: setprop debug.carplay.v34_media_barrier 1.
"""
from pathlib import Path
base=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")
def once(s,a,b,tag):
 n=s.count(a)
 if n!=1: raise AssertionError(f"v34 {tag}: required 1 anchor, found {n}: {a[:110]!r}")
 return s.replace(a,b,1)
p=base/"CarPlayV34Options.kt"
if p.exists(): raise AssertionError("v34 options already exists")
p.write_text('''package io.github.nitsuya.aa.display.carplay

/** Per-AirPlay media gate, disabled unless user explicitly enables it. */
internal object CarPlayV34Options {
    fun mediaBarrier(): Boolean = runCatching {
        val cls = Class.forName("android.os.SystemProperties")
        val text = cls.getMethod("get", String::class.java, String::class.java)
            .invoke(null, "debug.carplay.v34_media_barrier", "0") as? String ?: "0"
        text == "1"
    }.getOrDefault(false)
}
''',encoding="utf-8")

p=base/"CarPlayRtspSession.kt";s=p.read_text(encoding="utf-8")
s=once(s,'''    private val screenEgress = AtomicReference<ScreenStreamEgress?>(null)
''','''    private val screenEgress = AtomicReference<ScreenStreamEgress?>(null)
    private val v34MediaBarrier = AtomicBoolean(false)
    private val v34MediaReady = AtomicBoolean(true)
    private val v34SkippedFrames = AtomicInteger(0)
''',"gate state")
s=once(s,'''    fun releaseMediaStreams(reason: String) {
        streaming.set(false)
''','''    fun releaseMediaStreams(reason: String) {
        v34MediaReady.set(false)
        streaming.set(false)
''',"gate on teardown")
start=s.index("    private fun runEncryptedSetupRecord(")
anchor="        val mib3 = huProfile.usesMib3WirelessPath\n"
idx=s.index(anchor,start)
if idx-start>3000: raise AssertionError("v34 RTSP function anchor out of bounds")
s=s[:idx]+'''        val mib3 = huProfile.usesMib3WirelessPath
        val v34Enabled = !mib3 && CarPlayV34Options.mediaBarrier()
        v34MediaBarrier.set(v34Enabled)
        v34MediaReady.set(!v34Enabled)
        v34SkippedFrames.set(0)
        CarPlayV33Diag.stage("v34-setup-gate", "enabled=$v34Enabled mib3=$mib3")
'''+s[idx+len(anchor):]
s=once(s,'''        streaming.set(true)
        onForceKeyFrame()

        CarPlayV33Diag.stage("audio-setup-begin", "mib3=$mib3")
''','''        streaming.set(true)
        if (!v34Enabled) {
            onForceKeyFrame()
        } else {
            CarPlayV33Diag.stage("v34-video-held", "await audio SETUP")
        }

        CarPlayV33Diag.stage("audio-setup-begin", "mib3=$mib3")
''',"defer initial keyframe")
s=once(s,'''        onSessionReady()
        CarPlayV33Diag.stage("screen-egress-armed", "dataPort=$dataPort")
''','''        onSessionReady()
        if (v34Enabled && running.get() && screenEgress.get() === egress) {
            v34MediaReady.set(true)
            CarPlayV33Diag.stage("v34-gate-open",
                "audioMedia=${mediaAudioEgress.get()!=null} " +
                "audioSpeech=${speechAudioEgress.get()!=null} " +
                "earlyVideoDrops=${v34SkippedFrames.get()}")
            mediaAudioEgress.get()?.start()
            speechAudioEgress.get()?.start()
            onForceKeyFrame()
        }
        CarPlayV33Diag.stage("screen-egress-armed", "dataPort=$dataPort")
''',"open after setup")
s=once(s,'''            slot.getAndSet(egress)?.stop()
            egress?.start()
        } catch (e: Throwable) {
''','''            slot.getAndSet(egress)?.stop()
            if (v34MediaBarrier.get()) {
                CarPlayV33Diag.stage("v34-audio-held", "type=${profile.audioType}")
            } else {
                egress?.start()
            }
        } catch (e: Throwable) {
''',"delay PCM TX start until gate open")
s=once(s,'''    ): Int {
        if (isCodecConfig) {
            lastCodecConfig.set(au)
''','''    ): Int {
        if (v34MediaBarrier.get() && !v34MediaReady.get()) {
            if (isCodecConfig) lastCodecConfig.set(au)
            val count = v34SkippedFrames.incrementAndGet()
            if (count <= 2) {
                CarPlayV33Diag.stage("v34-early-video-held",
                    "config=$isCodecConfig key=$isKey count=$count")
            }
            return 0
        }
        if (isCodecConfig) {
            lastCodecConfig.set(au)
''',"gate CONFIG and all screen bytes")
p.write_text(s,encoding="utf-8")

p=base/"CarPlaySourceSession.kt";s=p.read_text(encoding="utf-8")
s=once(s,'''    private val v32RecoveryQueued = AtomicBoolean(false)
''','''    private val v32RecoveryQueued = AtomicBoolean(false)
    /** Independent of iAP2 state that resets on RFCOMM teardown. */
    private val v34StartSeenInAuthRound = AtomicBoolean(false)
''',"independent StartSession history")
s=once(s,'''        v31WifiHandoffPending.set(false)
        v31AcceptedLinkSync.set(null)
        mediaPrepared.set(false)
''','''        v31WifiHandoffPending.set(false)
        v31AcceptedLinkSync.set(null)
        v34StartSeenInAuthRound.set(false)
        mediaPrepared.set(false)
''',"initialize history")
s=once(s,'''            onAuthComplete = {
                Log.i(CarPlayConsts.TAG, "iAP auth done → WiFi / CarPlayStartSession")
            },
''','''            onAuthComplete = {
                v34StartSeenInAuthRound.set(false)
                mainHandler.removeCallbacks(v14Recovery)
                v32RecoveryQueued.set(false)
                Log.i(CarPlayConsts.TAG,
                    "v34 fresh iAP2 auth: 0x4301 history reset; stale recovery cancelled")
                Log.i(CarPlayConsts.TAG, "iAP auth done → WiFi / CarPlayStartSession")
            },
''',"reset on new auth")
s=once(s,'''            onCarPlayStart = { start ->
                v31WifiHandoffPending.set(true)
''','''            onCarPlayStart = { start ->
                v34StartSeenInAuthRound.set(true)
                Log.i(CarPlayConsts.TAG, "v34 0x4301 received; history retained after RFCOMM close")
                v31WifiHandoffPending.set(true)
''',"remember 0x4301")
s=once(s,'''            if (iap2?.hasSeenStartSession() == true) return@Thread
''','''            if (v34StartSeenInAuthRound.get() ||
                iap2?.hasSeenStartSession() == true) return@Thread
''',"guard wifi fallback")
s=once(s,'''        if (iap2?.hasSeenStartSession() == true) return
''','''        if (v34StartSeenInAuthRound.get() ||
            iap2?.hasSeenStartSession() == true) {
            Log.i(CarPlayConsts.TAG,
                "v34 ignore no-0x4301 fallback: previously received 0x4301")
            return
        }
''',"guard fallback")
s=once(s,'''    private val v14Recovery = Runnable {
        v32RecoveryQueued.set(false)
''','''    private val v14Recovery = Runnable {
        v32RecoveryQueued.set(false)
        if (v34StartSeenInAuthRound.get()) {
            Log.i(CarPlayConsts.TAG,
                "v34 prevent no-StartSession recovery after verified 0x4301")
            return@Runnable
        }
''',"guard v14 recovery")
s=once(s,'''        v31AcceptedLinkSync.set(null)
        v15ReleaseLocks()
''','''        v31AcceptedLinkSync.set(null)
        v34StartSeenInAuthRound.set(false)
        v15ReleaseLocks()
''',"clear full stop")
p.write_text(s,encoding="utf-8")

p=Path("aa-display/build.gradle.kts");s=p.read_text(encoding="utf-8")
s=once(s,"versionCode = 3133","versionCode = 3134","version code")
s=once(s,'versionName = "0.3#17.8-v33"','versionName = "0.3#17.8-v34"',"version name")
p.write_text(s,encoding="utf-8")
print("v34 applied: optional RTSP A/V start gate + 0x4301 recovery history preservation")

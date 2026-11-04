#!/usr/bin/env python3
"""v58: recover long reverse black screen without stopping audio/control session.

After v57. A/B flag debug.carplay.v58_video_recover=0 (new RTSP object).
No periodic poll, no reconnect during BORROW, no midstream codec reset.
"""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(path,old,new,label):
    p=R/path
    s=p.read_text(encoding="utf-8")
    n=s.count(old)
    if n!=1: raise AssertionError("v58 "+label+" count="+str(n))
    p.write_text(s.replace(old,new,1),encoding="utf-8")

# Queue no longer accepts any new compressed video while the HU owns the screen.
one("carplay/CarPlayV57VideoQueue.kt",
'''    fun close() {
        synchronized(lock) {''',
'''    fun dropUntilIdr(reason: String) {
        synchronized(lock) {
            generation++
            val removed = pending.size
            pending.clear()
            dropped += removed.toLong()
            awaitingIdr = true
            lock.notifyAll()
            Log.i(CarPlayConsts.TAG, "v58 queue flushed reason=" + reason +
                " removed=" + removed + " totalDropped=" + dropped)
        }
    }

    fun blockedForMs(): Long = synchronized(lock) {
        if (inFlightAt == 0L) 0L
        else (SystemClock.elapsedRealtime() - inFlightAt).coerceAtLeast(0L)
    }

    fun close() {
        synchronized(lock) {''',"queue drain monitor")

# In requestUI the HU may already believe controller owns the screen. Still
# signal a video recovery probe without re-posting modesChanged / audio claims.
one("carplay/protocol/CarPlayEventChannel.kt",
'''    private val onModesRestoredToPhone: () -> Unit,
) {''',
'''    private val onModesRestoredToPhone: () -> Unit,
    private val onPhoneScreenRequested: () -> Unit,
) {''',"event ctor")
one("carplay/protocol/CarPlayEventChannel.kt",
'''                onForceKeyFrame()
            }
            else -> Log.i(CarPlayConsts.TAG, "event command type=''' ,
'''                onForceKeyFrame()
                runCatching { onPhoneScreenRequested() }
                    .onFailure { Log.w(CarPlayConsts.TAG, "v58 requestUI callback error", it) }
            }
            else -> Log.i(CarPlayConsts.TAG, "event command type=''' ,"event requestUI")
one("carplay/protocol/CarPlayEventChannel.kt",
'''            onModesRestoredToPhone: () -> Unit = {},
        ): CarPlayEventChannel? {''',
'''            onModesRestoredToPhone: () -> Unit = {},
            onPhoneScreenRequested: () -> Unit = {},
        ): CarPlayEventChannel? {''',"event factory")
one("carplay/protocol/CarPlayEventChannel.kt",
'''                    onModesRestoredToPhone = onModesRestoredToPhone,
                )''',
'''                    onModesRestoredToPhone = onModesRestoredToPhone,
                    onPhoneScreenRequested = onPhoneScreenRequested,
                )''',"event object")

one("carplay/CarPlayRtspSession.kt",
'''    private val v57ModeLogged = AtomicBoolean(false)''',
'''    private val v57ModeLogged = AtomicBoolean(false)
    private val v58Enabled = runCatching {
        val c = Class.forName("android.os.SystemProperties")
        val m = c.getMethod("get", String::class.java, String::class.java)
        (m.invoke(null, "debug.carplay.v58_video_recover", "1") as String) != "0"
    }.getOrDefault(true)
    private val v58ReopenScreen = AtomicReference<(() -> Boolean)?>(null)
    private val v58Busy = AtomicBoolean(false)
    private val v58Suspended = AtomicBoolean(false)
    private val v58VideoUnusable = AtomicBoolean(false)
    private val v58LastAttempt = AtomicLong(0)

    /** Triggered only on user request/restore or by encoder while phone owns screen. */
    private fun v58TryRecovery(reason: String) {
        if (!v58Enabled || !running.get() || !streaming.get()) return
        if (eventChannel.get()?.isPhoneOwningMainScreen() == false) return
        val stall = v57VideoQueue.blockedForMs()
        val closed = screenEgress.get()?.isClosed() == true
        if (stall < 2500L && !closed && !v58VideoUnusable.get()) return
        if (!v58Busy.compareAndSet(false,true)) return
        val now = android.os.SystemClock.elapsedRealtime()
        val last = v58LastAttempt.get()
        if (now-last < 12000L) {
            v58Busy.set(false)
            return
        }
        v58LastAttempt.set(now)
        thread(name="carplay-v58-screen-only",isDaemon=true) {
            try {
                if (!running.get() || !streaming.get() ||
                    eventChannel.get()?.isPhoneOwningMainScreen() == false) return@thread
                val reopen = v58ReopenScreen.get() ?: return@thread
                Log.w(CarPlayConsts.TAG,"v58 video-only recovery start reason=" +
                    reason + " blockedMs=" + stall + " socketClosed=" + closed)
                v58VideoUnusable.set(true)
                v57VideoQueue.dropUntilIdr("v58-start")
                // The old blocking TCP write cannot be cancelled by queue.clear().
                // Close ONLY the screen dataPort; RTSP control and AAC stay alive.
                screenEgress.getAndSet(null)?.close()
                val ok = runCatching { reopen() }
                    .onFailure { Log.e(CarPlayConsts.TAG,"v58 screen-only SETUP failed",it) }
                    .getOrDefault(false)
                if (ok) {
                    v57VideoQueue.dropUntilIdr("v58-success")
                    v58VideoUnusable.set(false)
                    onForceKeyFrame()
                }
                Log.i(CarPlayConsts.TAG,"v58 video-only recovery result=" + ok)
            } finally {
                v58Busy.set(false)
            }
        }
    }''',"v58 fields and recovery")

one("carplay/CarPlayRtspSession.kt",
'''        return if (v57AsyncEnabled) {
            v57VideoQueue.offer(au, ptsUs, isKey, isCodecConfig)
        } else {''',
'''        if (v58Enabled) {
            // v50's reverse gate is inside TCP send. A stuck sender never
            // reaches it, so move HU ownership gating to the codec entrance.
            if (eventChannel.get()?.isPhoneOwningMainScreen() == false) {
                if (v58Suspended.compareAndSet(false,true)) {
                    v57VideoQueue.dropUntilIdr("HU-owned MainScreen")
                    Log.i(CarPlayConsts.TAG,"v58 video enqueue paused while HU owns screen")
                }
                return false
            }
            if (v58Suspended.compareAndSet(true,false)) {
                v57VideoQueue.dropUntilIdr("MainScreen returned")
                onForceKeyFrame()
            }
            if (v58VideoUnusable.get() ||
                v57VideoQueue.blockedForMs() > 2500L) {
                v58TryRecovery("encoder-output")
                return false
            }
        }
        return if (v57AsyncEnabled) {
            v57VideoQueue.offer(au, ptsUs, isKey, isCodecConfig)
        } else {''',"upstream enqueue gate")

one("carplay/CarPlayRtspSession.kt",
'''        if (isCodecConfig) {
            lastCodecConfig.set(au)''',
'''        if (v58Enabled && v58VideoUnusable.get()) return 0
        if (isCodecConfig) {
            lastCodecConfig.set(au)''',"suppress RTP fallback")

one("carplay/CarPlayRtspSession.kt",
'''                onIapMessage = { frame -> wifi?.onInbound(frame) },
                onModesRestoredToPhone = {''',
'''                onIapMessage = { frame -> wifi?.onInbound(frame) },
                onPhoneScreenRequested = { v58TryRecovery("requestUI") },
                onModesRestoredToPhone = {''',"user reentry callback")
one("carplay/CarPlayRtspSession.kt",
'''                        modesRestored.get()?.invoke()
                    }
                },''',
'''                        modesRestored.get()?.invoke()
                        v58TryRecovery("MainScreen restored")
                    }
                },''',"UNBORROW callback")

# Recovery uses the authenticated AirPlay control channel and only SETUP
# stream type 110 with a new connection ID. It does not touch AAC SETUP/teardown.
one("carplay/CarPlayRtspSession.kt",
'''        streaming.set(true)
        onForceKeyFrame()

        // Audio:''',
'''        streaming.set(true)
        v58VideoUnusable.set(false)
        v58ReopenScreen.set {
            if (!v58Enabled || !controlPumpLive.get() ||
                !running.get() || !streaming.get() ||
                eventChannel.get()?.isPhoneOwningMainScreen() == false) {
                false
            } else {
                val id = if(mib3) newStreamConnectionId64() else newStreamConnectionId()
                val spec = LinkedHashMap<String,Any?>(screenStream)
                spec["streamConnectionID"] = id
                val reply = sendScreenSetup(listOf(spec),"v58-screen-resume")
                val dict = reply?.body?.let { BinaryPlist.asDict(BinaryPlist.decode(it)) }
                val streams = dict?.get("streams") as? List<*>
                val info = streams?.firstNotNullOfOrNull { entry ->
                    val item = BinaryPlist.asDict(entry) ?: return@firstNotNullOfOrNull null
                    if (BinaryPlist.intOf(item["type"])?.toInt() == 110) item else null
                } ?: BinaryPlist.asDict(streams?.firstOrNull())
                val port = BinaryPlist.intOf(info?.get("dataPort"))?.toInt()?.and(0xffff)
                if (reply?.firstLine?.contains("200") != true || port == null || port<=0) {
                    Log.w(CarPlayConsts.TAG,"v58 SETUP rejected response=" +
                        reply?.firstLine + " dataPort=" + port)
                    false
                } else {
                    val fresh = ScreenStreamEgress.open(
                        host=peerHost, dataPort=port, sessionKey=sharedSecret,
                        streamConnectionId=id, width=screenW, height=screenH,
                        displayWidth=screenW, displayHeight=screenH,
                        wrapAvccFourcc=!mib3,
                    )
                    if (fresh == null) false
                    else {
                        screenEgress.getAndSet(fresh)?.close()
                        Log.i(CarPlayConsts.TAG,"v58 new screen dataPort=" + port +
                            " id=" + id + " cachedCsd=" +
                            (lastCodecConfig.get()?.size ?: 0))
                        true
                    }
                }
            }
        }
        onForceKeyFrame()

        // Audio:''',"screen-only SETUP")

one("carplay/CarPlayRtspSession.kt",
'''    fun releaseMediaStreams(reason: String) {
        v57VideoQueue.reset("release:" + reason)''',
'''    fun releaseMediaStreams(reason: String) {
        v58ReopenScreen.set(null)
        v58VideoUnusable.set(false)
        v58Suspended.set(false)
        v57VideoQueue.reset("release:" + reason)''',"cleanup")
one("carplay/CarPlayRtspSession.kt",
'''        v57VideoQueue.reset("screen-setup")
        onVideoSetup(screenW, screenH)''',
'''        v57VideoQueue.reset("screen-setup")
        v58VideoUnusable.set(false)
        v58Suspended.set(false)
        onVideoSetup(screenW, screenH)''',"new session")

g=Path("aa-display/build.gradle.kts")
s=g.read_text(encoding="utf-8")
if s.count("versionCode = 3157")!=1 or s.count('versionName = "0.3#17.8-v57"')!=1:
    raise AssertionError("v58 requires exact v57")
g.write_text(s.replace("versionCode = 3157","versionCode = 3158")
    .replace('versionName = "0.3#17.8-v57"',
             'versionName = "0.3#17.8-v58"'),encoding="utf-8")
print("v58 gated video-queue pause and video-only reSETUP on return applied")

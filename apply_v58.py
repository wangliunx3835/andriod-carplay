#!/usr/bin/env python3
"""v58: avoid queuing video during HU reverse borrow and repair a blocked video-only DataStream.

Base: v57. Critical user log: TCP sender blocked >32s, 6375 dropped
while CarPlay control/audio survive. Avoid whole-session restart, midstream
MediaCodec recycle, crypto reuse, or screen reclaim during active camera.
"""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def sub(path,old,new,label):
    p=R/path
    s=p.read_text(encoding="utf-8")
    n=s.count(old)
    if n!=1:raise AssertionError("v58 "+label+" anchor count="+str(n))
    p.write_text(s.replace(old,new,1),encoding="utf-8")

# v57 sender could remain in one blocked socket.write forever. The recovery
# replaces the worker epoch as well as the negotiated video dataPort; old
# worker is retired, and cannot consume new-epoch packets.
sub("carplay/CarPlayV57VideoQueue.kt",
'''    init {
        thread(name = "carplay-v57-video-tx", isDaemon = true) { senderLoop() }
    }''',
'''    private var senderEpoch = 1L
    init {
        thread(name = "carplay-v57-video-tx", isDaemon = true) { senderLoop(1L) }
    }

    fun blockedMs(): Long = synchronized(lock) {
        if (inFlightAt == 0L) 0L
        else (SystemClock.elapsedRealtime() - inFlightAt).coerceAtLeast(0L)
    }

    /** Only use after closing/replacing the old dataPort Socket. */
    fun replaceSenderForNewStream(reason: String) {
        val epoch: Long
        synchronized(lock) {
            senderEpoch++
            epoch = senderEpoch
            generation++
            pending.clear()
            awaitingIdr = true
            inFlightAt = 0L
            lock.notifyAll()
        }
        Log.w(CarPlayConsts.TAG, "v58 sender replace epoch=" + epoch +
            " reason=" + reason)
        thread(name = "carplay-v58-video-tx", isDaemon = true) {
            senderLoop(epoch)
        }
    }''',"worker epoch and stall monitor")
sub("carplay/CarPlayV57VideoQueue.kt",
'''    private fun take(): Frame? {''',
'''    private fun take(epoch: Long): Frame? {''',"epoch-aware take")
sub("carplay/CarPlayV57VideoQueue.kt",
'''            while (alive && pending.isEmpty()) {''',
'''            while (alive && epoch == senderEpoch && pending.isEmpty()) {''',"epoch wait")
sub("carplay/CarPlayV57VideoQueue.kt",
'''            if (!alive) return null
            val frame = pending.removeFirst()''',
'''            if (!alive || epoch != senderEpoch) return null
            val frame = pending.removeFirst()''',"old take retire")
sub("carplay/CarPlayV57VideoQueue.kt",
'''    private fun senderLoop() {
        while (true) {
            val item = take() ?: return
            if (synchronized(lock) { item.generation != generation }) {''',
'''    private fun senderLoop(epoch: Long) {
        while (true) {
            val item = take(epoch) ?: return
            if (synchronized(lock) {
                    epoch != senderEpoch || item.generation != generation
                }) {''',"retire old sender after blocked send ends")
sub("carplay/CarPlayV57VideoQueue.kt",
'''            synchronized(lock) {
                inFlightAt = 0L
                if (written > 0 && item.generation == generation) sent++
            }''',
'''            synchronized(lock) {
                if (epoch == senderEpoch) inFlightAt = 0L
                if (written > 0 && item.generation == generation &&
                    epoch == senderEpoch) sent++
            }''',"avoid retired thread clobbering new stall timer")

# A blocked writer may hold the BufferedOutputStream's monitor, so do not
# call out.close() from the recovery controller. Closing Socket unblocks write
# without waiting for the BufferedOutputStream lock.
sub("carplay/protocol/ScreenStreamEgress.kt",
'''    fun close() {
        if (!closed.compareAndSet(false, true)) return''',
'''    /** v58: abort the old stuck video dataPort without taking the writer lock. */
    fun abortForVideoRepair() {
        if (!closed.compareAndSet(false, true)) return
        runCatching { socket.close() }
            .onFailure { Log.w(CarPlayConsts.TAG, "v58 video Socket abort failed", it) }
        Log.w(CarPlayConsts.TAG, "v58 aborted stuck screen dataPort")
    }

    fun close() {
        if (!closed.compareAndSet(false, true)) return''',"socket-only abort")

# Session state and one-time opt-out per connection.
sub("carplay/CarPlayRtspSession.kt",
'''    private val v57ModeLogged = AtomicBoolean(false)''',
'''    private val v57ModeLogged = AtomicBoolean(false)
    private val v58VideoRepairEnabled = runCatching {
        val p = Class.forName("android.os.SystemProperties")
        val get = p.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, "debug.carplay.v58_video_repair", "1") as String) != "0"
    }.getOrDefault(true)
    private val v58ReopenVideo = AtomicReference<(() -> Boolean)?>(null)
    private val v58Recovering = AtomicBoolean(false)
    private val v58RepairCount = AtomicInteger(0)
    private val v58LastRepair = AtomicLong(0L)
    private val v58HuBorrowed = AtomicBoolean(false)
    private val v58EncodeEvents = AtomicLong(0L)

    /**
     * Repair video type-110 only, on a separate control worker after HU gives
     * MainScreen back. Never touch audio streams or screen ownership.
     */
    private fun v58MaybeRepair(reason: String) {
        if (!v58VideoRepairEnabled || !v57AsyncEnabled ||
            !running.get() || !streaming.get() || !controlPumpLive.get()) return
        val ev = eventChannel.get() ?: return
        if (!ev.isPhoneOwningMainScreen()) return
        val stalled = v57VideoQueue.blockedMs()
        if (stalled < 4_500L) return
        val callback = v58ReopenVideo.get() ?: return
        if (v58RepairCount.get() >= 2) return
        val now = android.os.SystemClock.elapsedRealtime()
        if (now - v58LastRepair.get() < 25_000L) return
        if (!v58Recovering.compareAndSet(false, true)) return
        v58LastRepair.set(now)
        v58RepairCount.incrementAndGet()
        thread(name = "carplay-v58-screen-repair", isDaemon = true) {
            try {
                if (!running.get() || !streaming.get() ||
                    eventChannel.get()?.isPhoneOwningMainScreen() != true) {
                    return@thread
                }
                Log.w(CarPlayConsts.TAG,
                    "v58 repairing video only cause=" + reason +
                    " blockedMs=" + stalled + " attempt=" + v58RepairCount.get())
                val ok = callback()
                Log.w(CarPlayConsts.TAG,
                    "v58 video-only screen SETUP result=" + ok +
                    " attempt=" + v58RepairCount.get())
            } catch (e: Throwable) {
                Log.e(CarPlayConsts.TAG, "v58 video repair failed", e)
            } finally {
                v58Recovering.set(false)
            }
        }
    }''',"video recovery session state")

sub("carplay/CarPlayRtspSession.kt",
'''        return if (v57AsyncEnabled) {
            v57VideoQueue.offer(au, ptsUs, isKey, isCodecConfig)
        } else {''',
'''        return if (v57AsyncEnabled) {
            // The old v50 owner gate was checked only by the network worker.
            // Keep the codec thread from queuing stale video throughout reverse.
            val huOwns = v50ReverseGate &&
                eventChannel.get()?.isPhoneOwningMainScreen() == false
            if (huOwns) {
                if (v58HuBorrowed.compareAndSet(false, true)) {
                    v57VideoQueue.reset("hu-holds-main-screen")
                    Log.i(CarPlayConsts.TAG, "v58 suppress enqueue while HU owns screen")
                }
                false
            } else {
                if (v58HuBorrowed.compareAndSet(true, false)) {
                    v57VideoQueue.reset("hu-returned-main-screen")
                    onForceKeyFrame()
                    Log.i(CarPlayConsts.TAG, "v58 screen returned: fresh IDR requested")
                }
                if (v58EncodeEvents.incrementAndGet() % 120L == 0L) {
                    v58MaybeRepair("fresh-encoder-events")
                }
                v57VideoQueue.offer(au, ptsUs, isKey, isCodecConfig)
            }
        } else {''',"suppress stale frames before queue")
sub("carplay/CarPlayRtspSession.kt",
'''        v57VideoQueue.reset("release:" + reason)''',
'''        v58ReopenVideo.set(null)
        v58HuBorrowed.set(false)
        v57VideoQueue.reset("release:" + reason)''',"release recovery callback")
sub("carplay/CarPlayRtspSession.kt",
'''                onForceKeyFrame = onForceKeyFrame,
                onTouch = onTouchEvent,''',
'''                onForceKeyFrame = {
                    onForceKeyFrame()
                    v58MaybeRepair("HU-event-requestUI-or-IDR")
                },
                onTouch = onTouchEvent,''',"repair on requestUI or keyframe")
sub("carplay/CarPlayRtspSession.kt",
'''                        modesRestored.get()?.invoke()
                    }
                },''',
'''                        modesRestored.get()?.invoke()
                        v58MaybeRepair("MainScreen-restored")
                    }
                },''',"repair on resource returned")

# Capture the existing authenticated encrypted control request/response closure,
# session URL, HU identity and screen codec configuration from this exact SETUP.
# New screen stream: fresh streamConnectionID -> fresh per-stream ChaCha key.
# No audio SETUP/teardown, no pairing reset, no MediaCodec recycle.
sub("carplay/CarPlayRtspSession.kt",
'''        v57VideoQueue.reset("screen-setup")
        onVideoSetup(screenW, screenH)
        streaming.set(true)''',
'''        v57VideoQueue.reset("screen-setup")
        onVideoSetup(screenW, screenH)

        v58ReopenVideo.set {
            // Suspend video only. Audio RTP/AAC and encrypted control stay live.
            streaming.set(false)
            val prior = screenEgress.getAndSet(null)
            prior?.abortForVideoRepair()
            v57VideoQueue.replaceSenderForNewStream("video-only-SETUP")
            val newId = if (mib3) newStreamConnectionId64()
                else newStreamConnectionId()
            val newStream = linkedMapOf<String, Any?>()
            newStream.putAll(screenStream)
            newStream["streamConnectionID"] = newId
            val response = sendScreenSetup(listOf(newStream), "v58-video-repair")
            val ok = response?.firstLine?.contains("200") == true
            if (!ok) {
                Log.e(CarPlayConsts.TAG,
                    "v58 screen SETUP refused=" + response?.firstLine)
                false
            } else {
                val decoded = response?.body?.let { BinaryPlist.asDict(BinaryPlist.decode(it)) }
                val returned = decoded?.get("streams") as? List<*>
                val selected = returned?.firstNotNullOfOrNull { value ->
                    val d = BinaryPlist.asDict(value)
                    if (BinaryPlist.intOf(d?.get("type"))?.toInt() == 110) d
                    else null
                } ?: BinaryPlist.asDict(returned?.firstOrNull())
                val port = BinaryPlist.intOf(selected?.get("dataPort"))
                    ?.toInt()?.and(0xffff) ?: 0
                if (port <= 0) {
                    Log.e(CarPlayConsts.TAG, "v58 screen SETUP no dataPort")
                    false
                } else {
                    val fresh = ScreenStreamEgress.open(
                        host = peerHost,
                        dataPort = port,
                        sessionKey = sharedSecret,
                        streamConnectionId = newId,
                        width = screenW, height = screenH,
                        displayWidth = screenW, displayHeight = screenH,
                        wrapAvccFourcc = !mib3,
                    )
                    if (fresh == null) {
                        Log.e(CarPlayConsts.TAG, "v58 screen dataPort open failed")
                        false
                    } else {
                        screenEgress.set(fresh)
                        streaming.set(true)
                        onForceKeyFrame()
                        Log.i(CarPlayConsts.TAG,
                            "v58 video-only screen rearmed dataPort=" + port +
                            " newStreamId=" + newId)
                        true
                    }
                }
            }
        }
        streaming.set(true)''',"install video-only reSETUP closure")

g=Path("aa-display/build.gradle.kts")
s=g.read_text(encoding="utf-8")
if s.count("versionCode = 3157")!=1 or s.count('versionName = "0.3#17.8-v57"')!=1:
    raise AssertionError("v58 requires exact v57 build")
g.write_text(s.replace("versionCode = 3157","versionCode = 3158")
    .replace('versionName = "0.3#17.8-v57"','versionName = "0.3#17.8-v58"'),
    encoding="utf-8")
print("v58: suppression before queue + bounded video-only RTSP reSETUP repair applied")

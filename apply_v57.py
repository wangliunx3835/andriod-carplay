#!/usr/bin/env python3
"""v57: decouple MediaCodec drain from blocking HU TCP, retain v56 features."""
from pathlib import Path
root = Path("aa-display/src/main/java/io/github/nitsuya/aa/display")

def sub(path, old, new, label):
    p=root/path
    s=p.read_text(encoding="utf-8")
    n=s.count(old)
    if n!=1:raise AssertionError("v57 "+label+" count="+str(n))
    p.write_text(s.replace(old,new,1),encoding="utf-8")

sub("carplay/CarPlaySourceSession.kt",
    'val written = rtsp?.sendVideoAccessUnit(bytes, ptsUs, key, config) ?: 0',
    'val queued = rtsp?.enqueueEncodedVideo(bytes, ptsUs, key, config) == true',
    "source queue")
sub("carplay/CarPlaySourceSession.kt",
    'packets=$written streaming=',
    'queueAccepted=$queued streaming=',
    "source log")

sub("carplay/CarPlayRtspSession.kt",
    '    private val screenEgress = AtomicReference<ScreenStreamEgress?>(null)',
    '''    private val screenEgress = AtomicReference<ScreenStreamEgress?>(null)
    // v57: one ordered sender instead of writing TCP from MediaCodec drain.
    // 0 opts out for A/B; evaluated once per new RTSP object.
    private val v57AsyncEnabled = runCatching {
        val c = Class.forName("android.os.SystemProperties")
        val get = c.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, "debug.carplay.v57_async_video", "1") as String) != "0"
    }.getOrDefault(true)
    private val v57VideoQueue = CarPlayV57VideoQueue(
        send = { au, pts, key, config -> sendVideoAccessUnit(au, pts, key, config) },
        requestIdr = onForceKeyFrame,
    )
    private val v57ModeLogged = AtomicBoolean(false)''',
    "sender field")

sub("carplay/CarPlayRtspSession.kt",
    '    fun isStreaming(): Boolean = streaming.get()',
    '''    fun isStreaming(): Boolean = streaming.get()

    /** Async by default; debug property 0 restores old synchronous path. */
    fun enqueueEncodedVideo(
        au: ByteArray, ptsUs: Long, isKey: Boolean, isCodecConfig: Boolean
    ): Boolean {
        if (v57ModeLogged.compareAndSet(false, true)) {
            Log.i(CarPlayConsts.TAG, "v57 async video enabled=" + v57AsyncEnabled)
        }
        return if (v57AsyncEnabled) {
            v57VideoQueue.offer(au, ptsUs, isKey, isCodecConfig)
        } else {
            sendVideoAccessUnit(au, ptsUs, isKey, isCodecConfig) > 0
        }
    }''',
    "queue API")

sub("carplay/CarPlayRtspSession.kt",
    '''    fun releaseMediaStreams(reason: String) {
        streaming.set(false)''',
    '''    fun releaseMediaStreams(reason: String) {
        v57VideoQueue.reset("release:" + reason)
        streaming.set(false)''',
    "media release")

sub("carplay/CarPlayRtspSession.kt",
    '''        lastCodecConfig.set(null)
        onVideoSetup(screenW, screenH)
        streaming.set(true)''',
    '''        lastCodecConfig.set(null)
        v57VideoQueue.reset("screen-setup")
        onVideoSetup(screenW, screenH)
        streaming.set(true)''',
    "screen setup")

sub("carplay/CarPlayRtspSession.kt",
    '''        running.set(false)
        releaseMediaStreams("rtsp-stop")
        peer?.closeQuietly()''',
    '''        running.set(false)
        releaseMediaStreams("rtsp-stop")
        v57VideoQueue.close()
        peer?.closeQuietly()''',
    "rtsp stop")

sub("carplay/protocol/ScreenStreamEgress.kt",
    '''    fun close() {
        if (!closed.compareAndSet(false, true)) return
        try {
            out.close()
        } catch (_: Throwable) {
        }
        try {
            socket.close()
        } catch (_: Throwable) {
        }''',
    '''    fun close() {
        if (!closed.compareAndSet(false, true)) return
        // v57: unblock any outstanding Socket write before closing/flushing
        // BufferedOutputStream; HU may stop reading while showing native UI.
        try {
            socket.close()
        } catch (_: Throwable) {
        }
        try {
            out.close()
        } catch (_: Throwable) {
        }''',
    "close TCP first")

queue="package io.github.nitsuya.aa.display.carplay\n\nimport android.os.SystemClock\nimport android.util.Log\nimport java.util.ArrayDeque\nimport kotlin.concurrent.thread\n\n/**\n * v57: prevent HU TCP backpressure from stalling MediaCodec's output-drain thread.\n * CONFIG, IDR and P frames are sent by a single consumer in original order.\n * Overflow drops a whole pending GOP and waits for a new IDR.\n */\ninternal class CarPlayV57VideoQueue(\n    private val send: (ByteArray, Long, Boolean, Boolean) -> Int,\n    private val requestIdr: () -> Unit,\n) {\n    private data class Frame(\n        val bytes: ByteArray, val ptsUs: Long,\n        val key: Boolean, val config: Boolean, val generation: Long,\n    )\n    private val lock = Object()\n    private val pending = ArrayDeque<Frame>()\n    private var alive = true\n    private var generation = 1L\n    private var awaitingIdr = false\n    private var lastIdrRequestAt = 0L\n    private var lastWarningAt = 0L\n    private var inFlightAt = 0L\n    private var dropped = 0L\n    private var sent = 0L\n\n    init {\n        thread(name = \"carplay-v57-video-tx\", isDaemon = true) { senderLoop() }\n    }\n\n    /** Called on hardware codec output thread; never waits for a socket. */\n    fun offer(bytes: ByteArray, ptsUs: Long, key: Boolean, config: Boolean): Boolean {\n        var askForIdr = false\n        var accepted = false\n        val now = SystemClock.elapsedRealtime()\n        synchronized(lock) {\n            if (!alive) return false\n            if (pending.size >= MAX_PENDING) {\n                val configToPreserve = pending.lastOrNull { it.config }\n                val skipped = pending.size\n                pending.clear()\n                if (configToPreserve != null) pending.addLast(configToPreserve)\n                dropped += skipped.toLong()\n                awaitingIdr = true\n                if (now - lastIdrRequestAt >= IDR_REQUEST_GAP_MS) {\n                    lastIdrRequestAt = now\n                    askForIdr = true\n                }\n                if (now - lastWarningAt >= WARNING_GAP_MS) {\n                    lastWarningAt = now\n                    Log.w(CarPlayConsts.TAG, \"v57 video queue overflow dropped=\" +\n                        dropped + \" pending=\" + pending.size + \" awaitingIdr=\" + awaitingIdr)\n                }\n            }\n            if (config || !awaitingIdr || key) {\n                pending.addLast(Frame(bytes, ptsUs, key, config, generation))\n                if (key) awaitingIdr = false\n                accepted = true\n                lock.notifyAll()\n            } else {\n                dropped++\n            }\n            val stalledFor = if (inFlightAt != 0L) now - inFlightAt else 0L\n            if (stalledFor > 2000L && now - lastWarningAt >= WARNING_GAP_MS) {\n                lastWarningAt = now\n                Log.w(CarPlayConsts.TAG,\n                    \"v57 video TCP sender potentially blocked for \" + stalledFor +\n                    \"ms pending=\" + pending.size + \" dropped=\" + dropped)\n            }\n        }\n        if (askForIdr) {\n            runCatching { requestIdr() }\n                .onFailure { Log.w(CarPlayConsts.TAG, \"v57 IDR request failed\", it) }\n        }\n        return accepted\n    }\n\n    /** Remove the previous session's encoded buffers on screen re-SETUP. */\n    fun reset(reason: String) {\n        synchronized(lock) {\n            generation++\n            val removed = pending.size\n            pending.clear()\n            awaitingIdr = false\n            lock.notifyAll()\n            Log.i(CarPlayConsts.TAG, \"v57 video queue reset reason=\" + reason +\n                \" removed=\" + removed + \" generation=\" + generation)\n        }\n    }\n\n    fun close() {\n        synchronized(lock) {\n            alive = false\n            pending.clear()\n            lock.notifyAll()\n        }\n    }\n\n    private fun take(): Frame? {\n        synchronized(lock) {\n            while (alive && pending.isEmpty()) {\n                try {\n                    lock.wait(1000L)\n                } catch (_: InterruptedException) {\n                    if (!alive) return null\n                }\n            }\n            if (!alive) return null\n            val frame = pending.removeFirst()\n            inFlightAt = SystemClock.elapsedRealtime()\n            return frame\n        }\n    }\n\n    private fun senderLoop() {\n        while (true) {\n            val item = take() ?: return\n            if (synchronized(lock) { item.generation != generation }) {\n                synchronized(lock) { inFlightAt = 0L }\n                continue\n            }\n            val started = SystemClock.elapsedRealtime()\n            val written = runCatching {\n                send(item.bytes, item.ptsUs, item.key, item.config)\n            }.onFailure {\n                Log.e(CarPlayConsts.TAG, \"v57 video network send threw\", it)\n            }.getOrDefault(0)\n            val elapsed = SystemClock.elapsedRealtime() - started\n            synchronized(lock) {\n                inFlightAt = 0L\n                if (written > 0 && item.generation == generation) sent++\n            }\n            if (elapsed > 800L) {\n                Log.w(CarPlayConsts.TAG, \"v57 slow video TCP send duration=\" +\n                    elapsed + \"ms written=\" + written +\n                    \" config=\" + item.config + \" key=\" + item.key)\n            }\n        }\n    }\n    companion object {\n        private const val MAX_PENDING = 32\n        private const val IDR_REQUEST_GAP_MS = 1500L\n        private const val WARNING_GAP_MS = 2000L\n    }\n}\n"
p=root/"carplay/CarPlayV57VideoQueue.kt"
if p.exists():raise AssertionError("v57 duplicate queue")
p.write_text(queue,encoding="utf-8")

g=Path("aa-display/build.gradle.kts")
s=g.read_text(encoding="utf-8")
if s.count("versionCode = 3156")!=1 or s.count('versionName = "0.3#17.8-v56"')!=1:
    raise AssertionError("v57 expected v56 version baseline")
g.write_text(s.replace("versionCode = 3156","versionCode = 3157")
   .replace('versionName = "0.3#17.8-v56"','versionName = "0.3#17.8-v57"'),
    encoding="utf-8")
print("v57 queue + bounded GOP dropping + TCP close ordering applied")

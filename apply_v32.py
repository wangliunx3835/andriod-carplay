#!/usr/bin/env python3
"""v32: MediaCodec worker generation isolation, inbound probe lifecycle and recovery."""
from pathlib import Path
base=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")
def one(s,a,b,tag):
    n=s.count(a)
    if n!=1: raise AssertionError(f"v32 {tag}: anchor count {n}: {a[:110]!r}")
    return s.replace(a,b,1)

p=base/"CarPlayVideoEncoder.kt"
s=p.read_text()
s=one(s,"    private val drainFailLogged = AtomicBoolean(false)\n",
"""    private val drainFailLogged = AtomicBoolean(false)
    private val v32CodecLock = Any()
    private val v32Generation = AtomicLong(0L)
    private var v32DrainThread: Thread? = null
""","encoder state")
s=one(s,"    fun start(width: Int, height: Int, fps: Int = CarPlayConsts.DEFAULT_VIDEO_FPS) {\n",
"""    @Synchronized
    fun start(width: Int, height: Int, fps: Int = CarPlayConsts.DEFAULT_VIDEO_FPS) {
""","serialized start")
s=one(s,"        codec = encoder\n        inputSurface = surface\n        running.set(true)\n",
"""        codec = encoder
        inputSurface = surface
        val token = v32Generation.incrementAndGet()
        running.set(true)
""","new generation")
s=one(s,'''            converterThread = thread(name = "carplay-avc-convert", isDaemon = true) { converterLoop(encoder) }
        }
        thread(name = "carplay-avc-drain", isDaemon = true) { drainLoop(encoder) }
''','''            converterThread = thread(name = "carplay-avc-convert", isDaemon = true) {
                converterLoop(encoder, token)
            }
        }
        v32DrainThread = thread(name = "carplay-avc-drain", isDaemon = true) {
            drainLoop(encoder, token)
        }
''',"token worker launch")
s=one(s,"    private fun converterLoop(encoder: MediaCodec) {\n",
"    private fun converterLoop(encoder: MediaCodec, token: Long) {\n","converter token")
s=one(s,"        while (running.get() || !converterQueue.isEmpty()) {\n",
"        while (running.get() && v32Generation.get() == token) {\n","converter loop generation")
s=one(s,'''            val inIndex = try {
                encoder.dequeueInputBuffer(10_000)
            } catch (_: Throwable) {
                continue
            }
''','''            val inIndex = synchronized(v32CodecLock) {
                if (!running.get() || v32Generation.get() != token) -1 else {
                    try { encoder.dequeueInputBuffer(10_000) } catch (_: Throwable) { -1 }
                }
            }
''',"converter input dequeue guard")
s=one(s,'''            if (inIndex < 0) continue
            try {
                val input: ByteBuffer = encoder.getInputBuffer(inIndex) ?: continue
                val nv12 = nv12Slots[slotIndex]
                input.clear()
                input.put(nv12)
                CarPlayMediaClock.ensureRunning()
                val pts = CarPlayMediaClock.videoTimestampNs() / 1_000L
                frameIndex++
                encoder.queueInputBuffer(inIndex, 0, nv12.size, pts, 0)
            } catch (e: Throwable) {
                Log.e(CarPlayConsts.TAG, "queueInputBuffer failed", e)
            }
''','''            if (inIndex < 0) continue
            synchronized(v32CodecLock) {
                if (running.get() && v32Generation.get() == token) {
                    try {
                        val input: ByteBuffer = encoder.getInputBuffer(inIndex)
                            ?: return@synchronized
                        val nv12 = nv12Slots[slotIndex]
                        input.clear()
                        input.put(nv12)
                        CarPlayMediaClock.ensureRunning()
                        val pts = CarPlayMediaClock.videoTimestampNs() / 1_000L
                        frameIndex++
                        encoder.queueInputBuffer(inIndex, 0, nv12.size, pts, 0)
                    } catch (e: Throwable) {
                        Log.e(CarPlayConsts.TAG, "queueInputBuffer failed", e)
                    }
                }
            }
''',"converter input buffer guard")
a=s.index("    private fun drainLoop(encoder: MediaCodec) {")
b=s.index("    fun stop() {",a)
new='''    private fun drainLoop(encoder: MediaCodec, token: Long) {
        val info = MediaCodec.BufferInfo()
        while (running.get() && v32Generation.get() == token) {
            try {
                drainOnce(encoder, info, token)
            } catch (e: Throwable) {
                if (running.get() && v32Generation.get() == token &&
                    drainFailLogged.compareAndSet(false, true)) {
                    Log.w(CarPlayConsts.TAG, "v32 AVC drain unexpected failure", e)
                }
                break
            }
        }
        Log.i(CarPlayConsts.TAG, "v32 AVC drain retired token=$token")
    }

    private fun drainOnce(encoder: MediaCodec, info: MediaCodec.BufferInfo, token: Long) {
        // Copy and release codec output while stop() is excluded; deliver to
        // network outside the lock, avoiding a network-blocked codec teardown.
        val frame: Triple<ByteArray, Long, Int>? = synchronized(v32CodecLock) {
            if (!running.get() || v32Generation.get() != token) {
                return@synchronized null
            }
            val index = try {
                encoder.dequeueOutputBuffer(info, 10_000)
            } catch (_: Throwable) {
                return@synchronized null
            }
            when {
                index == MediaCodec.INFO_TRY_AGAIN_LATER -> null
                index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                    runCatching {
                        Log.i(CarPlayConsts.TAG, "AVC output format ${encoder.outputFormat}")
                    }
                    null
                }
                index >= 0 -> {
                    try {
                        val buf = encoder.getOutputBuffer(index)
                        if (buf != null && info.size > 0) {
                            val bytes = ByteArray(info.size)
                            buf.position(info.offset)
                            buf.limit(info.offset + info.size)
                            buf.get(bytes)
                            Triple(bytes, info.presentationTimeUs, info.flags)
                        } else null
                    } catch (e: Throwable) {
                        if (running.get() && v32Generation.get() == token) {
                            Log.w(CarPlayConsts.TAG, "v32 AVC output buffer failure", e)
                        }
                        null
                    } finally {
                        runCatching { encoder.releaseOutputBuffer(index, false) }
                    }
                }
                else -> null
            }
        }
        if (frame != null && running.get() && v32Generation.get() == token) {
            val (bytes, pts, flags) = frame
            val key = (flags and MediaCodec.BUFFER_FLAG_KEY_FRAME) != 0
            val config = (flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0
            onEncodedAccessUnit(bytes, pts, key, config)
        }
    }

    @Synchronized
'''
s=s[:a]+new+s[b:]
s=one(s,'''    fun stop() {
        running.set(false)
        try {
            codec?.stop()
        } catch (_: Throwable) {
        }
        try {
            codec?.release()
        } catch (_: Throwable) {
        }
        codec = null
''','''    fun stop() {
        running.set(false)
        val retired = v32Generation.incrementAndGet()
        converterQueue.clear()
        converterThread?.interrupt()
        v32DrainThread?.interrupt()
        val worker = v32DrainThread
        if (worker != null && Thread.currentThread() !== worker) {
            runCatching { worker.join(350L) }
        }
        val converter = converterThread
        if (converter != null && Thread.currentThread() !== converter) {
            runCatching { converter.join(350L) }
        }
        v32DrainThread = null
        synchronized(v32CodecLock) {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            codec = null
        }
        Log.d(CarPlayConsts.TAG, "v32 MediaCodec retired generation=$retired")
''',"safe stop")
s=one(s,'''        converterThread?.interrupt()
        converterThread = null
''','''        converterThread = null
''',"remove duplicate interrupt")
p.write_text(s)

p=base/"CarPlayRtspSession.kt";s=p.read_text()
s=one(s,'''        val headerBuf = ByteArrayOutputLimited(64 * 1024)
        while (running.get() && !socket.isClosed) {
''','''        val headerBuf = ByteArrayOutputLimited(64 * 1024)
        var v32InboundMediaSeen = false
        while (running.get() && !socket.isClosed) {
''',"track real inbound media")
s=one(s,'''            val msg = provisional.copy(body = body)
            Log.i(CarPlayConsts.TAG, "RTSP ${msg.firstLine} cSeq=${msg.cSeq} body=${body.size}")
''','''            val msg = provisional.copy(body = body)
            if (msg.method in setOf("SETUP", "RECORD", "ANNOUNCE")) {
                v32InboundMediaSeen = true
            }
            Log.i(CarPlayConsts.TAG, "RTSP ${msg.firstLine} cSeq=${msg.cSeq} body=${body.size}")
            if (!v32InboundMediaSeen && msg.method == "TEARDOWN") {
                Log.i(CarPlayConsts.TAG, "v32 ignore probe TEARDOWN before media SETUP")
                reply(out, RtspMessage.ok(msg.cSeq.coerceAtLeast(0)))
                continue
            }
''',"request-based inbound probe classification")
s=one(s,'''        if (ownsSession) {
            // Old inbound/Bonjour socket EOF cannot tear down the
''','''        if (ownsSession && !v32InboundMediaSeen) {
            // A /ctrl-int/1/connect or /info probe is not a media session.
            // No releaseMediaStreams or v14Recovery on its EOF.
            if (peer === socket) {
                peer = null
                output = null
            }
            Log.i(CarPlayConsts.TAG, "v32 probe peer closed (no media SETUP), keep AirPlay")
        } else if (ownsSession) {
            // Old inbound/Bonjour socket EOF cannot tear down the
''',"do not release on non-media EOF")
p.write_text(s)

p=base/"CarPlaySourceSession.kt";s=p.read_text()
s=one(s,"    private val v14Recovery = Runnable {\n",
'''    private val v32RecoveryQueued = AtomicBoolean(false)
    private val v14Recovery = Runnable {
        v32RecoveryQueued.set(false)
''',"recovery dedup state")
s=one(s,'''                    airplayDialed.set(false)
                    mainHandler.removeCallbacks(v14Recovery)
                    mainHandler.postDelayed(v14Recovery, 2_500L)
                    Log.w(CarPlayConsts.TAG, "v14 RTSP ended; recovery scheduled")
''','''                    airplayDialed.set(false)
                    if (v32RecoveryQueued.compareAndSet(false, true)) {
                        mainHandler.postDelayed(v14Recovery, 2_500L)
                        Log.w(CarPlayConsts.TAG, "v32 RTSP ended; single recovery queued")
                    } else {
                        Log.i(CarPlayConsts.TAG, "v32 duplicate recovery suppressed ($reason)")
                    }
''',"deduplicate callbacks")
s=one(s,'''        mainHandler.removeCallbacks(v14Recovery)
        Log.i(CarPlayConsts.TAG, "v15 StartSession primary dial; cancelled fallback")
''','''        mainHandler.removeCallbacks(v14Recovery)
        v32RecoveryQueued.set(false)
        Log.i(CarPlayConsts.TAG, "v15 StartSession primary dial; cancelled fallback")
''',"primary cancels queued recovery")
s=one(s,'''    private fun cancelPhoneAudioRelease() {
        mainHandler.removeCallbacks(v14Recovery)
''','''    private fun cancelPhoneAudioRelease() {
        v32RecoveryQueued.set(false)
        mainHandler.removeCallbacks(v14Recovery)
''',"cancel queued recovery")
p.write_text(s)

p=Path("aa-display/build.gradle.kts");s=p.read_text()
s=one(s,"versionCode = 3131","versionCode = 3132","version code")
s=one(s,'versionName = "0.3#17.8-v31"','versionName = "0.3#17.8-v32"',"version name")
p.write_text(s)
print("v32 applied: codec generation-safe teardown, probe-only EOF ignored, recovery single-flight")

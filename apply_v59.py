#!/usr/bin/env python3
"""v59: bound video TCP backpressure and probe after MainScreen returns.

Apply after v58. Only video dataPort/queue are modified; audio, control,
pairing, virtual displays, reverse ownership and stable v23/v39 fixes remain.
"""
from pathlib import Path

R = Path("aa-display/src/main/java/io/github/nitsuya/aa/display")

def one(path, old, new, label):
    p = R / path
    data = p.read_text(encoding="utf-8")
    count = data.count(old)
    if count != 1:
        raise AssertionError(f"v59 {label}: expected 1 anchor, got {count}")
    p.write_text(data.replace(old, new, 1), encoding="utf-8")

# In v58, an unresponsive HU can keep ACKs stationary while the Android
# kernel happily accepts a large amount of video data. Reduce ONLY the video
# socket's send buffer to make lost receiver progress observable via the
# existing v57 ordered worker, rather than touching AAC/RTSP sockets.
# SO_SNDBUF is a kernel hint: log the actual value. Property 0 disables.
one("carplay/protocol/ScreenStreamEgress.kt",
    """                socket.tcpNoDelay = true
                socket.connect(InetSocketAddress(host, dataPort), 10_000)""",
    """                socket.tcpNoDelay = true
                val v59BufferKb = runCatching {
                    val cls = Class.forName("android.os.SystemProperties")
                    val get = cls.getMethod("get", String::class.java, String::class.java)
                    (get.invoke(null, "debug.carplay.v59_video_sockbuf_kb", "128")
                        as String).toInt()
                }.getOrDefault(128)
                if (v59BufferKb in 32..1024) {
                    runCatching { socket.sendBufferSize = v59BufferKb * 1024 }
                        .onFailure { Log.w(CarPlayConsts.TAG,
                            "v59 SO_SNDBUF request failed", it) }
                }
                Log.i(CarPlayConsts.TAG, "v59 video SO_SNDBUF requestedKB=" +
                    v59BufferKb + " actualKB=" +
                    runCatching { socket.sendBufferSize / 1024 }.getOrDefault(-1))
                socket.connect(InetSocketAddress(host, dataPort), 10_000)""",
    "video socket buffer")

# The v58 stalledForMs() checks only an in-flight Socket.write. A queued
# backlog without successful network sends must also be observable. Idle
# streams (empty queue) never trigger this condition.
one("carplay/CarPlayV57VideoQueue.kt",
    """    private var lastWarningAt = 0L
    private var inFlightAt = 0L""",
    """    private var lastWarningAt = 0L
    private var lastSendProgressAt = SystemClock.elapsedRealtime()
    private var inFlightAt = 0L""",
    "queue progress field")

one("carplay/CarPlayV57VideoQueue.kt",
    """            pending.clear()
            awaitingIdr = false
            lock.notifyAll()
            Log.i(CarPlayConsts.TAG, "v57 video queue reset""",
    """            pending.clear()
            awaitingIdr = false
            lastSendProgressAt = SystemClock.elapsedRealtime()
            lock.notifyAll()
            Log.i(CarPlayConsts.TAG, "v57 video queue reset""",
    "queue reset progress")

one("carplay/CarPlayV57VideoQueue.kt",
    """            dropped += removed.toLong()
            awaitingIdr = true
            lock.notifyAll()
            Log.i(CarPlayConsts.TAG, "v58 queue flushed""",
    """            dropped += removed.toLong()
            awaitingIdr = true
            lastSendProgressAt = SystemClock.elapsedRealtime()
            lock.notifyAll()
            Log.i(CarPlayConsts.TAG, "v58 queue flushed""",
    "queue flush progress")

one("carplay/CarPlayV57VideoQueue.kt",
    """    fun blockedForMs(): Long = synchronized(lock) {""",
    """    // Detect worker starvation/backpressure even between Socket.write calls.
    // No active pending AU means no stall: static/idle screen is safe.
    fun queuedWithoutProgressMs(): Long = synchronized(lock) {
        if (pending.isEmpty()) 0L
        else (SystemClock.elapsedRealtime() - lastSendProgressAt)
            .coerceAtLeast(0L)
    }

    fun blockedForMs(): Long = synchronized(lock) {""",
    "queue no-progress API")

one("carplay/CarPlayV57VideoQueue.kt",
    """                if (written > 0 && item.generation == generation) sent++""",
    """                if (written > 0 && item.generation == generation) {
                    sent++
                    lastSendProgressAt = SystemClock.elapsedRealtime()
                }""",
    "queue progress successful send")

# On receiving explicit requestUI/UNBORROW, v58 only checks once, often
# BEFORE the now-released sender has had 2.5 seconds to stall. A bounded
# one-shot probe rechecks at ~4 seconds. No permanent poll, and never while
# backup camera owns MainScreen.
one("carplay/CarPlayRtspSession.kt",
    """    private val v58LastAttempt = AtomicLong(0)

    /** Triggered only on user request/restore or by encoder while phone owns screen. */""",
    """    private val v58LastAttempt = AtomicLong(0)
    private val v59ProbeRunning = AtomicBoolean(false)
    private val v59LastProbeAt = AtomicLong(0L)
    private val v59ProbeEnabled = runCatching {
        val c = Class.forName("android.os.SystemProperties")
        val m = c.getMethod("get", String::class.java, String::class.java)
        (m.invoke(null, "debug.carplay.v59_video_probe", "1") as String) != "0"
    }.getOrDefault(true)

    private fun v59ArmReturnProbe(reason: String) {
        if (!v59ProbeEnabled || !v58Enabled ||
            !running.get() || !streaming.get() ||
            eventChannel.get()?.isPhoneOwningMainScreen() == false) return
        if (!v59ProbeRunning.compareAndSet(false, true)) return
        val now = android.os.SystemClock.elapsedRealtime()
        if (now - v59LastProbeAt.get() < 8_000L) {
            v59ProbeRunning.set(false)
            return
        }
        v59LastProbeAt.set(now)
        thread(name = "carplay-v59-return-probe", isDaemon = true) {
            try {
                Thread.sleep(4_000L)
                if (running.get() && streaming.get() &&
                    eventChannel.get()?.isPhoneOwningMainScreen() != false) {
                    val stall = maxOf(v57VideoQueue.blockedForMs(),
                        v57VideoQueue.queuedWithoutProgressMs())
                    Log.i(CarPlayConsts.TAG, "v59 return probe reason=" + reason +
                        " stalledMs=" + stall + " egressClosed=" +
                        (screenEgress.get()?.isClosed() == true))
                    v58TryRecovery("v59-return:" + reason)
                }
            } catch (_: InterruptedException) {
                // Shutdown/interrupt: no recovery.
            } finally {
                v59ProbeRunning.set(false)
            }
        }
    }

    /** Triggered only on user request/restore or by encoder while phone owns screen. */""",
    "return probe")

one("carplay/CarPlayRtspSession.kt",
    """        val stall = v57VideoQueue.blockedForMs()
        val closed = screenEgress.get()?.isClosed() == true""",
    """        val stall = maxOf(v57VideoQueue.blockedForMs(),
            v57VideoQueue.queuedWithoutProgressMs())
        val closed = screenEgress.get()?.isClosed() == true""",
    "v58 recovery queue starvation")

one("carplay/CarPlayRtspSession.kt",
    """                v57VideoQueue.dropUntilIdr("MainScreen returned")
                onForceKeyFrame()
            }
            if (v58VideoUnusable.get() ||
                v57VideoQueue.blockedForMs() > 2500L) {""",
    """                v57VideoQueue.dropUntilIdr("MainScreen returned")
                onForceKeyFrame()
                v59ArmReturnProbe("encoder-resume")
            }
            if (v58VideoUnusable.get() ||
                v57VideoQueue.blockedForMs() > 2500L ||
                v57VideoQueue.queuedWithoutProgressMs() > 3500L) {""",
    "encoder return probe & queue starvation")

one("carplay/CarPlayRtspSession.kt",
    """                onPhoneScreenRequested = { v58TryRecovery("requestUI") },""",
    """                onPhoneScreenRequested = {
                    v58TryRecovery("requestUI")
                    v59ArmReturnProbe("requestUI")
                },""",
    "explicit requestUI probe")

one("carplay/CarPlayRtspSession.kt",
    """                        v58TryRecovery("MainScreen restored")
                    }
                },""",
    """                        v58TryRecovery("MainScreen restored")
                        v59ArmReturnProbe("MainScreen restored")
                    }
                },""",
    "UNBORROW return probe")

g = Path("aa-display/build.gradle.kts")
s = g.read_text(encoding="utf-8")
if s.count("versionCode = 3158") != 1 or s.count('versionName = "0.3#17.8-v58"') != 1:
    raise AssertionError("v59 requires exact v58 baseline")
g.write_text(s.replace("versionCode = 3158", "versionCode = 3159")
    .replace('versionName = "0.3#17.8-v58"',
             'versionName = "0.3#17.8-v59"'), encoding="utf-8")
print("v59 bounded video TCP SO_SNDBUF + no-progress detection + one-shot return probe")

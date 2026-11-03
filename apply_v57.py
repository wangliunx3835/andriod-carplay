#!/usr/bin/env python3
"""v57: MediaCodec output-buffer lifecycle must not wait for HU video TCP writes.

Based on user 2026-11-03 black-screen capture: v55 screen ownership restored,
AAC stable, MTK AVC 1D output stash rose 11->16 then encode=0/DQout=0.
The existing codec drain synchronous callback writes to TCP and flushes before
releaseOutputBuffer. Isolate that callback in one bounded ordered sender.
"""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def replace(path, edits):
    p=R/path
    s=p.read_text(encoding="utf-8")
    for old,new,label in edits:
        c=s.count(old)
        if c!=1:raise AssertionError("v57 "+str(path)+" "+label+" count="+str(c))
        s=s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")

replace("carplay/CarPlayVideoEncoder.kt",[
('''import java.nio.ByteBuffer
import java.util.concurrent.LinkedBlockingQueue''',
 '''import java.nio.ByteBuffer
import java.util.ArrayDeque
import java.util.concurrent.LinkedBlockingQueue''',"import"),
('''    private val droppedFrames = AtomicLong(0)

    /** Frames dropped''',
 '''    private val droppedFrames = AtomicLong(0)

    // v57: the CarPlay video TCP Socket may block when HU switches to HOME or
    // reverse. Never hold a MediaCodec output buffer while writing the Socket.
    // Only one socket-writing worker; sequential frames, original per-frame
    // flush and cryptographic nonce sequence remain in ScreenStreamEgress.
    private data class V57Au(
        val bytes: ByteArray, val ptsUs: Long,
        val key: Boolean, val config: Boolean, val epoch: Long
    )
    private val v57Lock = Object()
    private val v57Pending = ArrayDeque<V57Au>()
    private val v57Epoch = AtomicLong(0L)
    private val v57WorkerStarted = AtomicBoolean(false)
    private var v57AwaitIdr = true
    private var v57Dropped = 0L
    private var v57LastWarnMs = 0L
    private var v57HighWater = 0

    private fun v57StartSender() {
        if (!v57WorkerStarted.compareAndSet(false, true)) return
        thread(name = "carplay-avc-socket-v57", isDaemon = true) {
            while (true) {
                val frame = synchronized(v57Lock) {
                    while (v57Pending.isEmpty()) {
                        try { v57Lock.wait() }
                        catch (_: InterruptedException) { return@thread }
                    }
                    v57Pending.removeFirst()
                }
                if (frame.epoch != v57Epoch.get()) continue
                val started = android.os.SystemClock.uptimeMillis()
                try {
                    // The only caller of ScreenStreamEgress / ChaCha writer;
                    // dataPort frames stay ordered with per-frame flush.
                    onEncodedAccessUnit(frame.bytes,frame.ptsUs,frame.key,frame.config)
                } catch (e: Throwable) {
                    Log.e(CarPlayConsts.TAG,"v57 socket sender callback failed",e)
                }
                val elapsed = android.os.SystemClock.uptimeMillis()-started
                if (elapsed >= 500L) {
                    Log.w(CarPlayConsts.TAG,
                        "v57 video socket write delayMs=" + elapsed +
                        " queued=" + synchronized(v57Lock){v57Pending.size} +
                        " dropped=" + v57Dropped)
                }
            }
        }
    }

    private fun v57QueueEncoded(
        bytes: ByteArray, ptsUs: Long, key: Boolean, config: Boolean
    ) {
        val epoch=v57Epoch.get()
        synchronized(v57Lock) {
            if (v57Pending.size>=8) {
                // Preserve codec CONFIG and discard an obsolete partial GOP;
                // resume only at a fresh IDR, never send P without its refs.
                val iter=v57Pending.iterator()
                while (iter.hasNext()) {
                    if (!iter.next().config) {
                        iter.remove()
                        v57Dropped++
                    }
                }
                v57AwaitIdr=true
                val now=android.os.SystemClock.uptimeMillis()
                if(now-v57LastWarnMs>4000L){
                    v57LastWarnMs=now
                    Log.w(CarPlayConsts.TAG,
                        "v57 AVC drain protected: network backpressure " +
                        "dropped="+v57Dropped+" queueHigh="+v57HighWater)
                }
            }
            if (!config && v57AwaitIdr && !key) {
                v57Dropped++
                return
            }
            if (!config && key) v57AwaitIdr=false
            v57Pending.addLast(V57Au(bytes,ptsUs,key,config,epoch))
            if(v57Pending.size>v57HighWater)v57HighWater=v57Pending.size
            v57Lock.notifyAll()
        }
    }

    /** Frames dropped''',"fields & sender"),
('''        stop()
        // CSM ScreenH264Encoder''',
 '''        stop()
        v57StartSender()
        // CSM ScreenH264Encoder''',"start worker"),
('''                            onEncodedAccessUnit(bytes, pts, key, config)''',
 '''            // v32 has already released the output buffer; do not block the
            // next drain iteration waiting for the HU TCP sink.
            v57QueueEncoded(bytes, pts, key, config)''',"drain offload"),
('''    fun stop() {
        running.set(false)''',
 '''    fun stop() {
        running.set(false)
        v57Epoch.incrementAndGet()
        synchronized(v57Lock) {
            v57Pending.clear()
            v57AwaitIdr=true
            v57Lock.notifyAll()
        }''',"stop queue")
])

replace("carplay/protocol/ScreenStreamEgress.kt",[
('''        if (!closed.compareAndSet(false, true)) return
        try {
            out.close()
        } catch (_: Throwable) {
        }
        try {
            socket.close()
        } catch (_: Throwable) {
        }
        Log.i(''',
 '''        if (!closed.compareAndSet(false, true)) return
        // v57: socket FIRST; BufferedOutputStream.close() can block waiting
        // for a synchronized write/flush in progress.
        try {
            socket.close()
        } catch (_: Throwable) {
        }
        try {
            out.close()
        } catch (_: Throwable) {
        }
        Log.i(''',"unblock old sender")
])

g=Path("aa-display/build.gradle.kts")
s=g.read_text(encoding="utf-8")
if s.count("versionCode = 3156")!=1 or s.count('versionName = "0.3#17.8-v56"')!=1:
    raise AssertionError("expected v56 build baseline")
g.write_text(s.replace("versionCode = 3156","versionCode = 3157")
  .replace('versionName = "0.3#17.8-v56"',
           'versionName = "0.3#17.8-v57"'),encoding="utf-8")
print("v57 applied: nonblocking AVC drain + bounded single TCP sender + safe socket close")

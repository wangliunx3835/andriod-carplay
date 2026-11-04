#!/usr/bin/env python3
"""v60: protect reverse camera, stage recovery after receiver reentry, reduce idle work.

Apply ONLY after v59. Video-only code. Keep VDs/IME, AAC, pairing, CarPlay
control, network fast-start and original frame bytes unchanged.
"""
from pathlib import Path

R = Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(path, old, new, label):
    p=R/path
    s=p.read_text(encoding="utf-8")
    n=s.count(old)
    if n != 1: raise AssertionError(f"v60 {label}: expected 1, got {n}")
    p.write_text(s.replace(old,new,1),encoding="utf-8")

# One cross-component, lock-free state holder. No watcher/timer/thread.
state=R/"carplay/CarPlayV60VideoPolicy.kt"
if state.exists(): raise AssertionError("v60 state already exists")
state.write_text("""package io.github.nitsuya.aa.display.carplay

import android.os.SystemClock
import android.util.Log

/** Published by authenticated MainScreen backupCamera BORROW/UNBORROW events. */
internal object CarPlayV60VideoPolicy {
    @Volatile private var cameraBorrowed = false
    @Volatile private var lastReturnMs = 0L
    private val reverseLowFps = runCatching {
        val c = Class.forName("android.os.SystemProperties")
        val m = c.getMethod("get", String::class.java, String::class.java)
        (m.invoke(null, "debug.carplay.v60_reverse_lowfps", "1") as String) != "0"
    }.getOrDefault(true)

    fun setCameraBorrowed(borrowed: Boolean) {
        if (cameraBorrowed == borrowed) return
        // Release timestamp is published before cameraBorrowed=false.
        if (!borrowed) lastReturnMs = SystemClock.elapsedRealtime()
        cameraBorrowed = borrowed
        Log.i(CarPlayConsts.TAG,
            "v60 backupCamera borrowed=" + borrowed +
                " GL10fps=" + reverseLowFps)
    }

    fun isCameraBorrowed(): Boolean = cameraBorrowed

    /** Receiver may still be transitioning immediately after UNBORROW. */
    fun mayReSetupVideo(): Boolean {
        if (cameraBorrowed) return false
        val returned = lastReturnMs
        return returned == 0L ||
            SystemClock.elapsedRealtime() - returned >= 5_500L
    }

    fun renderIntervalMs(normal: Long): Long =
        if (reverseLowFps && cameraBorrowed) maxOf(normal, 100L) else normal

    fun suppressRateAdaptation(): Boolean = reverseLowFps && cameraBorrowed

    fun resetSession() {
        cameraBorrowed = false
        lastReturnMs = 0L
    }
}
""",encoding="utf-8")

# Event channel is the authoritative source of camera ownership. Do not
# infer camera-active from an arbitrary HU home screen.
one("carplay/protocol/CarPlayEventChannel.kt",
    "import io.github.nitsuya.aa.display.carplay.CarPlayConsts",
    "import io.github.nitsuya.aa.display.carplay.CarPlayConsts\nimport io.github.nitsuya.aa.display.carplay.CarPlayV60VideoPolicy",
    "event import")

one("carplay/protocol/CarPlayEventChannel.kt",
    """                                    v55BackupCameraBorrowed = true
                                }
                            }""",
    """                                    v55BackupCameraBorrowed = true
                                    CarPlayV60VideoPolicy.setCameraBorrowed(true)
                                }
                            }""",
    "camera borrow signal")

one("carplay/protocol/CarPlayEventChannel.kt",
    """                                    v55BackupCameraBorrowed = false
                                }
                            }""",
    """                                    v55BackupCameraBorrowed = false
                                    CarPlayV60VideoPolicy.setCameraBorrowed(false)
                                }
                            }""",
    "camera return signal")

one("carplay/protocol/CarPlayEventChannel.kt",
    """                onForceKeyFrame()
                runCatching { onPhoneScreenRequested() }""",
    """                // Do not stimulate the video path during backup camera.
                if (!v55BackupCameraBorrowed) onForceKeyFrame()
                runCatching { onPhoneScreenRequested() }""",
    "requestUI while camera borrowed")

one("carplay/protocol/CarPlayEventChannel.kt",
    """        Log.i(CarPlayConsts.TAG, "event channel closed")""",
    """        CarPlayV60VideoPolicy.resetSession()
        Log.i(CarPlayConsts.TAG, "event channel closed")""",
    "event teardown state")

# Preserve 60fps on CarPlay; during active camera BORROW use 10fps video GL
# composition (without stopping MediaCodec or touching the accessory display).
# v58 already drops these encoded video AUs at enqueue. Avoid degrading the
# adaptive supply FPS because 10fps is intentional during camera ownership.
one("carplay/CarPlayGlCompositor.kt",
    """            val nextAt = tickStart + frameIntervalMs
            val delay = (nextAt - SystemClock.uptimeMillis()).coerceAtLeast(1L)""",
    """            val nextAt = tickStart +
                CarPlayV60VideoPolicy.renderIntervalMs(frameIntervalMs)
            val delay = (nextAt - SystemClock.uptimeMillis()).coerceAtLeast(1L)""",
    "GL camera frame pacing")

one("carplay/CarPlayGlCompositor.kt",
    """    private fun evaluateRate() {
        if (!encoderAttached.get()) return
        val now = SystemClock.uptimeMillis()""",
    """    private fun evaluateRate() {
        if (!encoderAttached.get()) return
        if (CarPlayV60VideoPolicy.suppressRateAdaptation()) {
            deliveredFrames.set(0)
            windowStart = SystemClock.uptimeMillis()
            return
        }
        val now = SystemClock.uptimeMillis()""",
    "avoid false FPS degrade")

# Queue sender is event-driven. No need to wake it every 1s when empty.
# offer/reset/drop/close already notify the same monitor.
one("carplay/CarPlayV57VideoQueue.kt",
    """                    lock.wait(1000L)""",
    """                    lock.wait() // v60: no idle 1Hz wakeup""",
    "queue idle wait")

# Early SETUP returns HTTP-like RTSP 400 while HU is still releasing its
# receiver after backupCamera UNBORROW. Guard both encoder and callback paths
# from video-only setup for 5.5 seconds after a known camera return.
one("carplay/CarPlayRtspSession.kt",
    """    private val v58LastAttempt = AtomicLong(0)
    private val v59ProbeRunning""",
    """    private val v58LastAttempt = AtomicLong(0)
    private val v60RecoverFailures = AtomicInteger(0)
    private val v59ProbeRunning""",
    "recovery failures field")

one("carplay/CarPlayRtspSession.kt",
    """        if (eventChannel.get()?.isPhoneOwningMainScreen() == false) return
        val stall = maxOf(v57VideoQueue.blockedForMs(),""",
    """        if (eventChannel.get()?.isPhoneOwningMainScreen() == false) return
        if (!CarPlayV60VideoPolicy.mayReSetupVideo()) return
        val stall = maxOf(v57VideoQueue.blockedForMs(),""",
    "camera settle guard")

one("carplay/CarPlayRtspSession.kt",
    """        if (now-last < 12000L) {""",
    """        // 400 Bad Request: retry sooner, but exponential backoff limits
        // repeated video SETUP attempts and avoids a busy/reconnect loop.
        val cooldown = when(v60RecoverFailures.get()) {
            0 -> 12_000L
            1 -> 4_000L
            2 -> 8_000L
            else -> 16_000L
        }
        if (now-last < cooldown) {""",
    "adaptive cooldown")

one("carplay/CarPlayRtspSession.kt",
    """                Log.i(CarPlayConsts.TAG,"v58 video-only recovery result=" + ok)""",
    """                if (ok) v60RecoverFailures.set(0)
                else v60RecoverFailures.updateAndGet { (it + 1).coerceAtMost(3) }
                Log.i(CarPlayConsts.TAG,"v58 video-only recovery result=" + ok +
                    " failureCount=" + v60RecoverFailures.get())""",
    "failure cooldown bookkeeping")

one("carplay/CarPlayRtspSession.kt",
    """                Thread.sleep(4_000L)""",
    """                Thread.sleep(6_000L) // v60: wait for receiver camera exit settle""",
    "delay one-shot probe")

one("carplay/CarPlayRtspSession.kt",
    """        v58ReopenScreen.set(null)
        v58VideoUnusable.set(false)""",
    """        v58ReopenScreen.set(null)
        v60RecoverFailures.set(0)
        v58VideoUnusable.set(false)""",
    "RTSP cleanup")

# Reduce repetitive protocol INFORMATION logs; do not change iAP2 framing
# or timing. HU periodic detect markers still parsed and answered as before.
one("carplay/protocol/WifiIap2Link.kt",
    """    private var detectArmed = false
    private var detectSent = false""",
    """    private var detectArmed = false
    private var v60DetectLogShown = false
    private var v60DeferLogShown = false
    private var detectSent = false""",
    "iAP marker logger state")

one("carplay/protocol/WifiIap2Link.kt",
    """        Log.i(CarPlayConsts.TAG, "Wi-Fi iAP2 marker")
        if (mib3Style) {""",
    """        if (!v60DetectLogShown) {
            v60DetectLogShown = true
            Log.i(CarPlayConsts.TAG, "Wi-Fi iAP2 first detect marker")
        }
        if (mib3Style) {""",
    "iAP marker dedup")

one("carplay/protocol/WifiIap2Link.kt",
    """            else Log.i(CarPlayConsts.TAG, "Wi-Fi iAP2 detect deferred until screen SETUP")""",
    """            else if (!v60DeferLogShown) {
                v60DeferLogShown = true
                Log.i(CarPlayConsts.TAG, "Wi-Fi iAP2 detect deferred until screen SETUP")
            }""",
    "iAP deferred dedup")

g=Path("aa-display/build.gradle.kts")
v=g.read_text(encoding="utf-8")
if v.count("versionCode = 3159")!=1 or v.count('versionName = "0.3#17.8-v59"')!=1:
    raise AssertionError("v60 requires v59 exact baseline")
g.write_text(v.replace("versionCode = 3159","versionCode = 3160")
    .replace('versionName = "0.3#17.8-v59"',
             'versionName = "0.3#17.8-v60"'),encoding="utf-8")
print("v60 camera ownership guard + 10fps reverse GL + sender wait + targeted log quiet + safe retry")

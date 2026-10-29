#!/usr/bin/env python3
"""v29: AirPlay single-owner startup & resource-lifetime fixes, applied after v28.
Preserves pinned upstream, v23 IPv4 readiness, v28 lean runtime, VD/IME/media."""
from pathlib import Path

root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")
rtsp=root/"CarPlayRtspSession.kt"
source=root/"CarPlaySourceSession.kt"
gradle=Path("aa-display/build.gradle.kts")

def replace_once(src, old, new, label):
    count=src.count(old)
    if count != 1:
        raise AssertionError(f"v29 {label}: expected 1, got {count}, anchor={old[:110]!r}")
    return src.replace(old,new,1)

r=rtsp.read_text(encoding="utf-8")
r=replace_once(r,'''    private val onHuMediaEnded: (reason: String) -> Unit = {},
''','''    private val onHuMediaEnded: (reason: String) -> Unit = {},
    /** Runs AFTER source control ownership and media are fully released. */
    private val onSourceDialEnded: () -> Unit = {},
''',"release callback")
r=replace_once(r,'''    fun isStreaming(): Boolean = streaming.get()
''','''    fun isStreaming(): Boolean = streaming.get()
    /** Includes pairing/SETUP, not only the later streaming state. */
    fun isAirPlaySourceActive(): Boolean = airplaySourceActive.get()
''',"busy query")
r=replace_once(r,'''        wifiMac: String? = null,
    ) {
        thread(name = "carplay-airplay-source", isDaemon = true) {
            if (!running.get()) running.set(true)
            airplaySourceActive.set(true)
            try {
''','''        wifiMac: String? = null,
    ): Boolean {
        // Own the RTSP source BEFORE launching its worker. All racing
        // 0x4301/fallback entrants must be rejected without touching media.
        if (streaming.get()) {
            Log.i(CarPlayConsts.TAG, "v29 reject source dial: already streaming")
            return false
        }
        if (!airplaySourceActive.compareAndSet(false, true)) {
            Log.i(CarPlayConsts.TAG, "v29 reject source dial: pairing/SETUP active")
            return false
        }
        Log.i(CarPlayConsts.TAG, "v29 AirPlay owner acquired host=$host port=$port")
        thread(name = "carplay-airplay-source", isDaemon = true) {
            if (!running.get()) running.set(true)
            var ownedSocket: Socket? = null
            try {
''',"atomic ownership")
r=replace_once(r,'''                var socket = CarPlayAccessoryNet.openTcp(allowUnbound = loopback)
                socket.connect''','''                var socket = CarPlayAccessoryNet.openTcp(allowUnbound = loopback)
                ownedSocket = socket
                socket.connect''',"initial socket")
r=replace_once(r,'''                    socket = CarPlayAccessoryNet.openTcp(allowUnbound = loopback)
                    socket.connect''','''                    socket = CarPlayAccessoryNet.openTcp(allowUnbound = loopback)
                    ownedSocket = socket
                    socket.connect''',"verify reconnect socket")
r=replace_once(r,'''                airplaySourceActive.set(false)
                // DiPlay resets control → must stop UDP audio / screen TCP or reconnect
                // Auth dies under zombie streams ("连接中断" loop).
                releaseMediaStreams("airplay-control-ended")
            }
        }
    }

    /** 4-byte UDP ping every 10s.''','''                runCatching { ownedSocket?.close() }
                if (peer === ownedSocket) {
                    peer = null
                    output = null
                }
                // Keep the ownership gate closed during teardown, then
                // notify the primary 0x4301 queue that it can safely dial.
                try {
                    releaseMediaStreams("airplay-control-ended")
                } finally {
                    airplaySourceActive.set(false)
                    Log.i(CarPlayConsts.TAG, "v29 AirPlay owner fully released")
                    runCatching { onSourceDialEnded() }
                        .onFailure { Log.w(CarPlayConsts.TAG, "v29 dial-end callback error", it) }
                }
            }
        }
        return true
    }

    /** 4-byte UDP ping every 10s.''',"atomic ownership end")
r=replace_once(r,'''        if (ownsSession) {
            output = null
            releaseMediaStreams("rtsp-peer-closed")
            Log.i(
                CarPlayConsts.TAG,
                "RTSP peer closed rtpSent=${rtpSent.get()} rtpBytes=${rtpBytes.get()}",
            )
        } else {
''','''        if (ownsSession) {
            // Old inbound/Bonjour socket EOF cannot tear down the
            // source session which superseded it.
            if (peer === socket && !airplaySourceActive.get()) {
                peer = null
                output = null
                releaseMediaStreams("rtsp-peer-closed")
                Log.i(CarPlayConsts.TAG, "RTSP inbound owner closed")
            } else {
                Log.i(CarPlayConsts.TAG, "v29 stale inbound peer EOF ignored")
            }
        } else {
''',"inbound stale EOF")
r=replace_once(r,"if (now - lastFeedbackAt >= 2_000L) {","if (now - lastFeedbackAt >= 1_000L) {","feedback period")
r=replace_once(r,'''                    Thread.sleep(10_000)
                } catch (_: InterruptedException) {
                    break
                }
            }
        }
        Log.i(CarPlayConsts.TAG, "keepAlive → $peer:$port")''','''                    Thread.sleep(5_000)
                } catch (_: InterruptedException) {
                    break
                }
            }
        }
        Log.i(CarPlayConsts.TAG, "keepAlive → $peer:$port")''',"udp heartbeat period")
rtsp.write_text(r,encoding="utf-8")

s=source.read_text(encoding="utf-8")
s=replace_once(s,'''import java.util.concurrent.atomic.AtomicLong
''','''import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference
''',"atomic import")
s=replace_once(s,'''    private val airplayDialed = AtomicBoolean(false)
''','''    private val airplayDialed = AtomicBoolean(false)
    // 0x4301 received while a fallback source is still pairing/setting up.
    private val v29DeferredPrimary = AtomicReference<Iap2Csm.CarPlayStart?>(null)

    private fun v29DeferPrimary(start: Iap2Csm.CarPlayStart, reason: String) {
        if (!running.get()) return
        v29DeferredPrimary.set(start)
        Log.i(CarPlayConsts.TAG, "v29 deferred 0x4301: $reason")
        // Race guard: if owner just completed, there will be no further
        // onSourceDialEnded callback; explicitly queue a one-shot drain.
        if (rtsp?.isAirPlaySourceActive() != true) {
            mainHandler.post { v29ResumeDeferredPrimary() }
        }
    }

    private fun v29ResumeDeferredPrimary() {
        if (!running.get()) {
            v29DeferredPrimary.set(null)
            return
        }
        val session = rtsp ?: return
        if (session.isAirPlaySourceActive()) return
        if (session.isStreaming()) {
            v29DeferredPrimary.set(null)
            Log.i(CarPlayConsts.TAG, "v29 pending 0x4301 ignored: already streaming")
            return
        }
        val pending = v29DeferredPrimary.getAndSet(null) ?: return
        Log.i(CarPlayConsts.TAG, "v29 resume deferred 0x4301 on released control")
        dialCarPlayControl(pending)
    }
''',"deferred StartSession")
s=replace_once(s,'''        airplayDialed.set(false)
        mediaPrepared.set(false)
''','''        airplayDialed.set(false)
        v29DeferredPrimary.set(null)
        mediaPrepared.set(false)
''',"reset pending on start")
s=replace_once(s,'''            onTouchEvent = { x, y, action -> CarPlayInputBridge.injectNormalized(x, y, action) },
''','''            onSourceDialEnded = { mainHandler.post { v29ResumeDeferredPrimary() } },
            onTouchEvent = { x, y, action -> CarPlayInputBridge.injectNormalized(x, y, action) },
''',"callback hookup")
s=replace_once(s,'''                if (rtsp?.isStreaming() == true) {
                    Log.w(CarPlayConsts.TAG,
                        "v7 RFCOMM closed while RTSP streaming: preserve media; " +
''','''                if (rtsp?.isStreaming() == true || rtsp?.isAirPlaySourceActive() == true) {
                    Log.w(CarPlayConsts.TAG,
                        "v29 RFCOMM closed while AirPlay pairing/streaming: preserve media; " +
''',"RFCOMM active preservation")
s=replace_once(s,'''    private fun dialAirPlayHost(host: InetAddress?, port: Int, reason: String) {
        if (host == null || port <= 0 || port > 65535) return
''','''    private fun dialAirPlayHost(host: InetAddress?, port: Int, reason: String) {
        if (host == null || port <= 0 || port > 65535) return
        if (rtsp?.isAirPlaySourceActive() == true || rtsp?.isStreaming() == true) {
            Log.i(CarPlayConsts.TAG, "v29 skip fallback: another source owner active")
            return
        }
''',"fallback busy guard")
s=replace_once(s,'''        if (airplayDialed.get() && rtsp?.isStreaming() == true) {
            Log.i(CarPlayConsts.TAG, "StartSession after fallback already streaming — keep")
            return
        }
''','''        if (rtsp?.isStreaming() == true) {
            Log.i(CarPlayConsts.TAG, "v29 0x4301 ignored: streaming healthy")
            return
        }
        if (rtsp?.isAirPlaySourceActive() == true) {
            v29DeferPrimary(start, "pairing or setup in progress")
            return
        }
''',"defer when fallback in flight")
s=replace_once(s,'''                    rtsp?.connectAsAirPlaySource(
                        host = addr,
                        port = port,
                        deviceId = start.deviceId,
''','''                    val claimed = rtsp?.connectAsAirPlaySource(
                        host = addr,
                        port = port,
                        deviceId = start.deviceId,
''',"observe source owner claim")
s=replace_once(s,'''                        wifiMac = if (wired) null else wifiHandoff?.staMacForAnnounce(),
                    )
                    return@Thread
''','''                        wifiMac = if (wired) null else wifiHandoff?.staMacForAnnounce(),
                    ) == true
                    if (!claimed && running.get() && rtsp?.isStreaming() != true) {
                        v29DeferPrimary(start, "source owner claim rejected")
                    }
                    return@Thread
''',"publish rejected 0x4301")
s=replace_once(s,'''        cancelPhoneAudioRelease()
        v15ReleaseLocks()
''','''        cancelPhoneAudioRelease()
        v29DeferredPrimary.set(null)
        v15ReleaseLocks()
''',"clear pending on stop")
source.write_text(s,encoding="utf-8")
g=gradle.read_text(encoding="utf-8")
g=replace_once(g,"versionCode = 3128","versionCode = 3129","versionCode")
g=replace_once(g,'versionName = "0.3#17.8-v28"','versionName = "0.3#17.8-v29"',"versionName")
gradle.write_text(g,encoding="utf-8")
print("v29: single owner + deferred 0x4301 + stale EOF guard + pairing BT preservation + heartbeat cadence")

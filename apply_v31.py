#!/usr/bin/env python3
"""v31: fix RTSP event response-echo, BT->Wi-Fi handoff and isolate IME experiments.

Apply after v30. Keeps v23 IPv4 fast readiness, v29 atomic AirPlay control
ownership and v30 reverse-camera MainScreen BORROW handling.
Build-only test branch: no Release publishing.
"""
from pathlib import Path

root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
event=root/"carplay/protocol/CarPlayEventChannel.kt"
source=root/"carplay/CarPlaySourceSession.kt"
vd=root/"ui/aa/split/SplitVdLifecycle.kt"
hook=root/"xposed/hook/VdImeDisplayPin.kt"
gradle=Path("aa-display/build.gradle.kts")

def once(s, old, new, label):
    n=s.count(old)
    if n != 1:
        raise AssertionError(f"v31 {label}: expected exactly one anchor, got {n}: {old[:125]!r}")
    return s.replace(old,new,1)

# I. Fix a verified protocol defect seen in v30 logs:
# response to our outgoing /command -> 'RTSP/1.0 200 OK' was incorrectly
# treated as a new accessory request and replied to repeatedly.
s=event.read_text(encoding="utf-8")
s=once(s,
'''    private val closed = AtomicBoolean(false)
''',
'''    private val closed = AtomicBoolean(false)
    private val v31IgnoredEventResponseLogged = AtomicBoolean(false)
''',"one-shot event diagnostic")
s=once(s,
'''    private fun handle(msg: RtspMessage) {
        val path = msg.firstLine.substringAfter(' ', "").substringBefore(' ')
        Log.i(
            CarPlayConsts.TAG,
            "event ← ${msg.firstLine} body=${msg.body.size}B",
        )
        // iPhone: changeModes gets a plist 200 (status+params ~220B), not empty.
''',
'''    private fun handle(msg: RtspMessage) {
        // RTSP/HTTP status lines are replies to our outgoing event commands.
        // Never reply to a reply: the old implementation caused a 200/200
        // feedback loop on DiPlay, wasting the encrypted event channel.
        val first = msg.firstLine
        if (first.startsWith("RTSP/", ignoreCase = true) ||
            first.startsWith("HTTP/", ignoreCase = true)) {
            if (v31IgnoredEventResponseLogged.compareAndSet(false, true)) {
                Log.i(CarPlayConsts.TAG,
                    "v31 event response demux active; incoming 200 OK ignored")
            }
            return
        }
        val path = first.substringAfter(' ', "").substringBefore(' ')
        if (!path.startsWith("/") || msg.method !in setOf(
            "POST", "GET", "PUT", "DELETE", "OPTIONS", "SETUP", "TEARDOWN"
        )) {
            Log.w(CarPlayConsts.TAG, "v31 ignore malformed event request: $first")
            return
        }
        Log.i(CarPlayConsts.TAG,
            "event ← ${msg.firstLine} body=${msg.body.size}B")
        // iPhone: changeModes gets a plist 200 (status+params ~220B), not empty.
''', "prevent event response ping-pong")
event.write_text(s,encoding="utf-8")

# II. There is a legitimate BT->Wi-Fi handoff window when the accessory closes
# RFCOMM before the RTSP worker owns its connection. v29 previously returned
# "without active RTSP" and tore down shared resources in this window.
s=source.read_text(encoding="utf-8")
s=once(s,
'''    private val airplayDialed = AtomicBoolean(false)
''',
'''    private val airplayDialed = AtomicBoolean(false)
    /** True after Wi-Fi credentials or StartSession until screen SETUP completes. */
    private val v31WifiHandoffPending = AtomicBoolean(false)
    /** Persist negotiated LinkSync across iAP2 reset on RFCOMM teardown. */
    private val v31AcceptedLinkSync = java.util.concurrent.atomic.AtomicReference<ByteArray?>(null)

    private fun v31RememberLinkSync(reason: String) {
        val lsp = iap2?.acceptedLinkSync()
        if (lsp != null && lsp.isNotEmpty()) {
            v31AcceptedLinkSync.set(lsp.copyOf())
            Log.i(CarPlayConsts.TAG, "v31 cached iAP2 LinkSync=${lsp.size}B ($reason)")
        }
    }
''', "handoff and LinkSync state")
s=once(s,
'''        airplayDialed.set(false)
        v29DeferredPrimary.set(null)
        mediaPrepared.set(false)
''',
'''        airplayDialed.set(false)
        v29DeferredPrimary.set(null)
        v31WifiHandoffPending.set(false)
        v31AcceptedLinkSync.set(null)
        mediaPrepared.set(false)
''',"initialize v31 handoff state")
s=once(s,
'''            onSessionReady = {
                // Do not ensureEncoder here — a second bindGl/forceFreshSurface mid-stream
''',
'''            onSessionReady = {
                v31WifiHandoffPending.set(false)
                Log.i(CarPlayConsts.TAG, "v31 Wi-Fi handoff completed: screen SETUP ready")
                // Do not ensureEncoder here — a second bindGl/forceFreshSurface mid-stream
''',"complete handoff on video start")
s=once(s,
'''            linkSyncBytes = { iap2?.acceptedLinkSync() },
''',
'''            linkSyncBytes = {
                iap2?.acceptedLinkSync() ?: v31AcceptedLinkSync.get()?.copyOf()
            },
''',"cached accepted LinkSync")
s=once(s,
'''            onConnected = { iap2?.onTransportConnected() },
''',
'''            onConnected = {
                if (rtsp?.isStreaming() != true &&
                    rtsp?.isAirPlaySourceActive() != true) {
                    v31WifiHandoffPending.set(false)
                    v31AcceptedLinkSync.set(null)
                }
                iap2?.onTransportConnected()
            },
''',"reset handoff on new transport")
s=once(s,
'''                if (rtsp?.mib3NowPlayingEgress() != null) {
                    Log.i(CarPlayConsts.TAG, "iAP RFCOMM closed — keep media/NowPlaying (Wi-Fi iAP)")
                    return@disconnect
                }
                rtsp?.releaseMediaStreams("iap-rfcomm-closed")
''',
'''                if (rtsp?.mib3NowPlayingEgress() != null) {
                    Log.i(CarPlayConsts.TAG, "iAP RFCOMM closed — keep media/NowPlaying (Wi-Fi iAP)")
                    return@disconnect
                }
                // RFCOMM can be intentionally retired after the accessory has
                // supplied Wi-Fi credentials / StartSession. Before AirPlay
                // claims its RTSP socket, "not streaming" is NOT disconnected.
                // Do not release media or launch v14 fallback in this window.
                if (v31WifiHandoffPending.get() ||
                    rtsp?.isAirPlaySourceActive() == true ||
                    rtsp?.isStreaming() == true) {
                    Log.i(CarPlayConsts.TAG,
                        "v31 RFCOMM closed during handoff/RTSP: preserve session " +
                            "pending=${v31WifiHandoffPending.get()} " +
                            "rtspBusy=${rtsp?.isAirPlaySourceActive()}")
                    return@disconnect
                }
                rtsp?.releaseMediaStreams("iap-rfcomm-closed")
''',"protect pre-RTSP handoff")
s=once(s,
'''            onWifiConfig = { wifi ->
                lastWifiSsid = wifi.ssid
''',
'''            onWifiConfig = { wifi ->
                v31WifiHandoffPending.set(true)
                v31RememberLinkSync("wifi-config")
                lastWifiSsid = wifi.ssid
''',"begin handoff at Wi-Fi credentials")
s=once(s,
'''            onCarPlayStart = { start ->
                val handoff = wifiHandoff
''',
'''            onCarPlayStart = { start ->
                v31WifiHandoffPending.set(true)
                v31RememberLinkSync("0x4301")
                val handoff = wifiHandoff
''',"begin handoff at 0x4301")
s=once(s,
'''        cancelPhoneAudioRelease()
        v29DeferredPrimary.set(null)
        v15ReleaseLocks()
''',
'''        cancelPhoneAudioRelease()
        v29DeferredPrimary.set(null)
        v31WifiHandoffPending.set(false)
        v31AcceptedLinkSync.set(null)
        v15ReleaseLocks()
''',"clear v31 state on stop")
source.write_text(s,encoding="utf-8")

# III. Revert v30's unproven default: SECURE flag stays enabled unless user
# deliberately opts into the separate non-SECURE IME experiment.
s=vd.read_text(encoding="utf-8")
s=once(s,
'''            ).invoke(null, "debug.carplay.v30_ime_secure", false) == true
        }.getOrDefault(false)
''',
'''            ).invoke(null, "debug.carplay.v30_ime_secure", true) == true
        }.getOrDefault(true)
''',"restore v29 secure VD default")
s=once(s,
'''        // Default OFF for SECURE; setprop debug.carplay.v30_ime_secure 1
        // then recreate displays to restore the previous v29 behavior.
''',
'''        // Default ON for SECURE (v29 stable behavior); only setprop
        // debug.carplay.v30_ime_secure 0 for isolated IME display experiments.
''',"document secure default")
vd.write_text(s, encoding="utf-8")

# IV. One-shot IME hook health log at VD activation. The known failing case
# has the IME Surface attached/drawn but omitted from SF Output Layers;
# do not pretend that PUBLIC, LOCAL or SECURE alone fixed that vendor issue.
s=hook.read_text(encoding="utf-8")
s=once(s,
'''    fun onAaDisplaysActive(context: Context) {
        ensureHooked()
        if (softImeSettingOwned) return
''',
'''    fun onAaDisplaysActive(context: Context) {
        ensureHooked()
        log(TAG, "v31 IME hook-health basic=$hooked " +
            "attempted=$installAttempted v28ParentHook=${v28ImeParentHook != null}; " +
            "HyperOS Output Layers requires device validation")
        if (softImeSettingOwned) return
''',"IME state diagnosis on VD activation")
hook.write_text(s,encoding="utf-8")

g=gradle.read_text(encoding="utf-8")
g=once(g,"versionCode = 3130","versionCode = 3131","versionCode")
g=once(g,'versionName = "0.3#17.8-v30"','versionName = "0.3#17.8-v31"',"versionName")
gradle.write_text(g,encoding="utf-8")
print("v31 applied: event-response demux, BT/Wi-Fi handoff guard, LSP cache, SECURE default restore, IME hook health")

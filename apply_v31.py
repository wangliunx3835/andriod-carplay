#!/usr/bin/env python3
"""v31 test APK: ignore RTSP replies on event socket; preserve Bluetooth→Wi-Fi handoff.

Applied after v30, without modifying v23 IPv4 gateway, v29 source single-owner,
v30 reverse-camera BORROW protection, render timing, frame/feedback cadence.
Restore SECURE virtual-display flag as DEFAULT after the v30 nonsecure experiment
failed on HyperOS. Use debug.carplay.v30_ime_secure=0 only for explicit A/B tests.
"""
from pathlib import Path

root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
source=root/"carplay/CarPlaySourceSession.kt"
event=root/"carplay/protocol/CarPlayEventChannel.kt"
vd=root/"ui/aa/split/SplitVdLifecycle.kt"
gradle=Path("aa-display/build.gradle.kts")

def once(s, old, new, label):
    count=s.count(old)
    if count != 1:
        raise AssertionError(f"v31 {label}: expected one anchor, found {count}: {old[:140]!r}")
    return s.replace(old,new,1)

# /command request and RTSP response share the encrypted event connection.
# CarDeck tests show that replying to a response causes a 200/200 feedback loop.
s=event.read_text(encoding="utf-8")
s=once(s,
    '''    private fun handle(msg: RtspMessage) {
        val path = msg.firstLine.substringAfter(' ', "").substringBefore(' ')
        Log.i(
            CarPlayConsts.TAG,
            "event ← ${msg.firstLine} body=${msg.body.size}B",
        )
''',
    '''    private fun handle(msg: RtspMessage) {
        val line = msg.firstLine
        // RTSP/HTTP status lines are responses to our outgoing /command.
        // NEVER reply to an RTSP response (would loop 200↔200 and flood HU).
        if (line.startsWith("RTSP/", ignoreCase = true) ||
            line.startsWith("HTTP/", ignoreCase = true)) {
            // Keep a bounded first-response breadcrumb for field verification.
            if (v31StatusResponses.getAndIncrement() < 2) {
                Log.i(CarPlayConsts.TAG, "v31 event response consumed; no reply: $line")
            }
            return
        }
        val parts = line.split(' ', limit = 3)
        if (parts.size < 3 || !parts[1].startsWith("/") ||
            !(parts[2].startsWith("RTSP/", ignoreCase = true) ||
                parts[2].startsWith("HTTP/", ignoreCase = true))) {
            Log.w(CarPlayConsts.TAG, "v31 event invalid request ignored: $line")
            return
        }
        val path = parts[1]
        Log.i(CarPlayConsts.TAG, "event ← $line body=${msg.body.size}B")
''', "event valid-request gating")
s=once(s,
    '''    private val outboundCseq = AtomicInteger(1)
''',
    '''    private val outboundCseq = AtomicInteger(1)
    private val v31StatusResponses = AtomicInteger(0)
''', "bounded response diagnostic")
event.write_text(s, encoding="utf-8")

s=source.read_text(encoding="utf-8")
s=once(s,
    '''    private val airplayDialed = AtomicBoolean(false)
''',
    '''    private val airplayDialed = AtomicBoolean(false)
    /**
     * Cache the agreed iAP2 LSP before an expected Bluetooth RFCOMM close.
     * Iap2Session.onTransportClosed() resets linkReady, which previously made
     * RTSP SETUP skip the Wi-Fi iAP2 link even after successful BT negotiation.
     * Cache is per CarPlaySourceSession start, not global / across new sessions.
     */
    private val v31WirelessLsp = java.util.concurrent.atomic.AtomicReference<ByteArray?>(null)

    private fun v31RememberLsp(label: String) {
        val agreed = iap2?.acceptedLinkSync()
        if (agreed != null && agreed.isNotEmpty()) {
            v31WirelessLsp.set(agreed.copyOf())
            Log.i(CarPlayConsts.TAG, "v31 LSP cached at $label len=${agreed.size}")
        }
    }
''', "cache per-session BT negotiated LSP")
s=once(s,
    '''        airplayDialed.set(false)
        v29DeferredPrimary.set(null)
        mediaPrepared.set(false)
''',
    '''        airplayDialed.set(false)
        v29DeferredPrimary.set(null)
        v31WirelessLsp.set(null)
        lastWifiSsid = null
        mediaPrepared.set(false)
''', "clear cached LSP on new session")
s=once(s,
    '''            linkSyncBytes = { iap2?.acceptedLinkSync() },
''',
    '''            linkSyncBytes = {
                iap2?.acceptedLinkSync() ?: v31WirelessLsp.get()?.copyOf()
            },
''', "source WiFi iAP2 can consume stored BT LSP")
s=once(s,
    '''            onDisconnected = disconnect@{
                if (iap2?.onTransportClosed() == false) return@disconnect
                // MIB3 NowPlaying rides Wi‑Fi iAP2 after handoff — RFCOMM drop must not
''',
    '''            onDisconnected = disconnect@{
                // Save state BEFORE calling onTransportClosed(), which resets the
                // iAP2 negotiation and StartSessionSeen fields.
                val v31HandoffExpected = !lastWifiSsid.isNullOrBlank() ||
                    iap2?.hasSeenStartSession() == true
                v31RememberLsp("rfcomm-close")
                if (iap2?.onTransportClosed() == false) return@disconnect
                if (v31HandoffExpected || rtsp?.isAirPlaySourceActive() == true ||
                    rtsp?.isStreaming() == true) {
                    Log.i(CarPlayConsts.TAG,
                        "v31 RFCOMM closed during Wi-Fi handoff/source: " +
                            "preserve pipeline (waiting for AirPlay / RTSP)")
                    return@disconnect
                }
                // MIB3 NowPlaying rides Wi‑Fi iAP2 after handoff — RFCOMM drop must not
''', "pre-handoff RFCOMM closure")
s=once(s,
    '''            onWifiConfig = { wifi ->
                lastWifiSsid = wifi.ssid
''',
    '''            onWifiConfig = { wifi ->
                v31RememberLsp("wifi-credentials")
                lastWifiSsid = wifi.ssid
''', "store LSP when handoff is announced")
s=once(s,
    '''            onCarPlayStart = { start ->
                val handoff = wifiHandoff
''',
    '''            onCarPlayStart = { start ->
                v31RememberLsp("0x4301")
                val handoff = wifiHandoff
''', "store LSP on primary dial")
s=once(s,
    '''        cancelPhoneAudioRelease()
        v29DeferredPrimary.set(null)
        v15ReleaseLocks()
''',
    '''        cancelPhoneAudioRelease()
        v29DeferredPrimary.set(null)
        v31WirelessLsp.set(null)
        lastWifiSsid = null
        v15ReleaseLocks()
''', "clear handoff cache on service stop")
# v14 legacy fallback must never pre-empt an in-flight v29 dial.
s=once(s,
    '''            rtsp?.isStreaming() != true &&
            CarPlayAccessoryNet.hasNetwork() &&
''',
    '''            rtsp?.isStreaming() != true &&
            rtsp?.isAirPlaySourceActive() != true &&
            CarPlayAccessoryNet.hasNetwork() &&
''', "guard fallback recovery during active RTSP handshake")
source.write_text(s, encoding="utf-8")

# The v30 SECURE=false experiment did not make IME visible; restore v29
# virtual-display behavior by default. Users can explicitly A/B test false.
s=vd.read_text(encoding="utf-8")
s=once(s,
    '''.invoke(null, "debug.carplay.v30_ime_secure", false) == true
        }.getOrDefault(false)''',
    '''.invoke(null, "debug.carplay.v30_ime_secure", true) == true
        }.getOrDefault(true)''', "restore v29 SECURE default")
s=once(s,
    '''"v30 IME VD flags SECURE=$keepSecure PUBLIC=true TRUSTED=true " +''',
    '''"v31 IME VD flags SECURE=$keepSecure PUBLIC=true TRUSTED=true " +''', "v31 IME flag log")
vd.write_text(s, encoding="utf-8")

g=gradle.read_text(encoding="utf-8")
g=once(g,"versionCode = 3130","versionCode = 3131","code")
g=once(g,'versionName = "0.3#17.8-v30"','versionName = "0.3#17.8-v31"',"name")
gradle.write_text(g, encoding="utf-8")
print("v31: RTSP response de-loop, RFCOMM handoff preserved, negotiated LSP cached, v14 fallback gated, SECURE restored")

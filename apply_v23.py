#!/usr/bin/env python3
"""v23-A: bounded IPv4 gateway readiness check for wireless fe80 StartSession.
No RTSP/IME/video/recovery changes. Run strictly after apply_v22.py.
"""
from pathlib import Path
p = Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlaySourceSession.kt")
s = p.read_text()
def replace_once(a, b):
    global s
    assert s.count(a) == 1, (a[:100], s.count(a))
    s = s.replace(a, b, 1)

replace_once(
    '        val gateway = if (!wired) wifiHandoff?.accessoryIpv4Hint(start.ssid) else null',
    '        var gateway = if (!wired) wifiHandoff?.accessoryIpv4Hint(start.ssid) else null',
)
replace_once(
    '        val preferGateway = !wired && advertisedIsLinkLocal &&',
    '        var preferGateway = !wired && advertisedIsLinkLocal &&',
)
replace_once(
    '        val host = if (preferGateway) gateway else advertised ?: gateway',
    '        var host = if (preferGateway) gateway else advertised ?: gateway',
)
needle = '''        Thread({
            fun scopedAddress(candidate: String): InetAddress {'''
insert = '''        Thread({
            // v23-A: only on wireless StartSession with fe80 and no IPv4 hint.
            // Poll on the existing dial worker, never block the iAP2 callback.
            // All successful IPv4, global IPv6, USB and loopback paths are untouched.
            if (!wired && advertisedIsLinkLocal && !preferGateway) {
                val startWait = android.os.SystemClock.elapsedRealtime()
                val deadline = startWait + 1_500L
                while (running.get() && !usbMode.get() &&
                    android.os.SystemClock.elapsedRealtime() < deadline) {
                    val hint = wifiHandoff?.accessoryIpv4Hint(start.ssid)
                    if (!hint.isNullOrBlank() &&
                        runCatching {
                            java.net.InetAddress.getByName(hint) is java.net.Inet4Address
                        }.getOrDefault(false)) {
                        gateway = hint
                        preferGateway = true
                        host = hint
                        break
                    }
                    try {
                        Thread.sleep(150L)
                    } catch (_: InterruptedException) {
                        return@Thread
                    }
                }
                Log.i(CarPlayConsts.TAG,
                    "v23-A gateway readiness waited=" +
                        (android.os.SystemClock.elapsedRealtime() - startWait) +
                        "ms ipv4Ready=$preferGateway selected=$host")
            }
            fun scopedAddress(candidate: String): InetAddress {'''
replace_once(needle,insert)
p.write_text(s)
g = Path("aa-display/build.gradle.kts")
v = g.read_text()
assert 'versionCode = 3122' in v and 'versionName = "0.3#17.8-v22"' in v
g.write_text(v.replace('versionCode = 3122', 'versionCode = 3123', 1)
              .replace('versionName = "0.3#17.8-v22"', 'versionName = "0.3#17.8-v23"', 1))
print("v23-A: bounded wireless IPv4 readiness check applied")

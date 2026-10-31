#!/usr/bin/env python3
"""v39: eliminate the standalone wireless RTSP/TCP reachability probe.

Apply after v38 on the pinned upstream commit. The original preflight connected
to the head unit's AirPlay port 7000 and immediately closed it before the real
RTSP handshake. DiPlay incorrectly scheduled a whole-session reconnect on that
empty probe's EOF (2/4/8/16-second backoff), even after the real session became
active. Rely on the real RTSP connect as the wireless reachability check.

Preserve loopback and wired preflight behavior; opt-in property
debug.carplay.v39_legacy_tcp_probe=1 restores the old wireless preflight for A/B.
Do not alter v23 fast IPv4 gateway readiness or any session/media protocol.
"""
from pathlib import Path

base = Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")

def once(src, old, new, label):
    count = src.count(old)
    if count != 1:
        raise AssertionError(f"v39 {label}: expected 1 anchor, found {count}: {old[:115]!r}")
    return src.replace(old, new, 1)

opts = base / "CarPlayV39Options.kt"
if opts.exists():
    raise AssertionError("v39 options already exist")
opts.write_text('''package io.github.nitsuya.aa.display.carplay

/** Reproduce v38's pre-RTSP TCP probe only for controlled comparison. */
internal object CarPlayV39Options {
    fun legacyTcpProbe(): Boolean = runCatching {
        val cls = Class.forName("android.os.SystemProperties")
        val get = cls.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, "debug.carplay.v39_legacy_tcp_probe", "0") as? String) == "1"
    }.getOrDefault(false)
}
''', encoding="utf-8")

p = base / "CarPlaySourceSession.kt"
s = p.read_text(encoding="utf-8")
# Two unique v6 log lines bound the original TCP probe. Match the
# structure by markers, not an exact multi-line blob: intermediate patches
# can add harmless comments/logs between these statements.
begin = '                    Log.i(CarPlayConsts.TAG, "v6 TCP probe begin $addr:$port")'
finish = '                    Log.i(CarPlayConsts.TAG, "v6 TCP probe SUCCESS $addr:$port")'
if s.count(begin) != 1 or s.count(finish) != 1:
    raise AssertionError("v39 expected one v6 preflight begin and finish marker")
i = s.index(begin)
j = s.index(finish, i) + len(finish)
old = s[i:j]
if (old.count("probe.connect(") != 2 or
        "java.net.Socket().use { probe ->" not in old or
        "CarPlayAccessoryNet.openTcp().use { probe ->" not in old):
    raise AssertionError("v39 preflight body no longer matches known socket behavior")
replacement = '''                    // v39: an empty pre-RTSP TCP probe reaches DiPlay and
                    // immediately emits EOF. DiPlay can schedule a stale
                    // reconnect that later destroys the actual media session.
                    // Real encrypted RTSP dial handles TCP reachability itself.
                    val v39Preflight = wired || loopback || CarPlayV39Options.legacyTcpProbe()
                    if (v39Preflight) {
                        Log.i(CarPlayConsts.TAG,
                            "v39 legacy TCP preflight begin $addr:$port wired=$wired loopback=$loopback")
                        if (loopback) {
                            java.net.Socket().use { probe ->
                                probe.connect(java.net.InetSocketAddress(addr, port), 2_500)
                            }
                        } else {
                            CarPlayAccessoryNet.openTcp().use { probe ->
                                probe.connect(java.net.InetSocketAddress(addr, port), 2_500)
                            }
                        }
                        Log.i(CarPlayConsts.TAG, "v39 legacy TCP preflight success $addr:$port")
                    } else {
                        Log.i(CarPlayConsts.TAG,
                            "v39 skip standalone TCP probe wireless $addr:$port; real RTSP dial only")
                    }'''
s = s[:i] + replacement + s[j:]
p.write_text(s, encoding="utf-8")

p = Path("aa-display/build.gradle.kts")
s = p.read_text(encoding="utf-8")
s = once(s, "versionCode = 3138", "versionCode = 3139", "version code")
s = once(s, 'versionName = "0.3#17.8-v38"',
            'versionName = "0.3#17.8-v39"', "version name")
p.write_text(s, encoding="utf-8")

print("v39 applied: wireless standalone TCP probe OFF, real RTSP dial retained")

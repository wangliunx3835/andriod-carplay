#!/usr/bin/env python3
"""v38: isolate the already-observed 1.2-second first-audio RTP hole.

Apply strictly after apply_v37.py. Default: continuous 20-ms PCM RTP cadence
from packet #1; all wire formats, RTP timestamps, RTSP, iAP2 and video unchanged.
Opt-in debug.carplay.v38_legacy_audio_pause=1 restores v37's 1200-ms gap
followed by the 22-ms/packet soft pace, for a controlled within-APK A/B test.
"""
from pathlib import Path

base = Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")

def once(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise AssertionError(f"v38 {label}: expected one anchor, got {n}: {old[:100]!r}")
    return s.replace(old, new, 1)

p = base / "CarPlayV38Options.kt"
if p.exists():
    raise AssertionError("v38 options already exist")
p.write_text('''package io.github.nitsuya.aa.display.carplay

/** A/B control: restores legacy first-media-audio gap only when explicitly enabled. */
internal object CarPlayV38Options {
    fun legacyAudioPause(): Boolean = runCatching {
        val cls = Class.forName("android.os.SystemProperties")
        val get = cls.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, "debug.carplay.v38_legacy_audio_pause", "0") as? String) == "1"
    }.getOrDefault(false)
}
''', encoding="utf-8")

p = base / "CarPlayAudioEgress.kt"
s = p.read_text(encoding="utf-8")
s = once(s,
'''        val paceHuStartup = profile.audioType == "media"
        var huSettlePending = paceHuStartup
''',
'''        // v38: first PCM RTP must be followed by uninterrupted real-time RTP.
        // v37 deliberately sent a single packet, then went silent for 1200 ms
        // and under-sent at 22 ms for 8 s. Restore that only for A/B control.
        val paceHuStartup = profile.audioType == "media" &&
            CarPlayV38Options.legacyAudioPause()
        Log.i(CarPlayConsts.TAG,
            "v38 audio cadence profile=" + profile.label +
                " mode=" + (if (paceHuStartup) "legacy-pause-1200ms-soft-22ms"
                           else "continuous-20ms"))
        var huSettlePending = paceHuStartup
''', "audio-pump cadence switch")
p.write_text(s, encoding="utf-8")

p = Path("aa-display/build.gradle.kts")
s = p.read_text(encoding="utf-8")
s = once(s, "versionCode = 3137", "versionCode = 3138", "version code")
s = once(s, 'versionName = "0.3#17.8-v37"',
            'versionName = "0.3#17.8-v38"', "version name")
p.write_text(s, encoding="utf-8")

print("v38 applied: default media RTP 20ms continuous; legacy 1200ms gap opt-in")

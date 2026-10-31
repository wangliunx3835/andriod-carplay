#!/usr/bin/env python3
"""v40: reduce unnecessary steady-state logging and redundant artwork threads.

Apply after v39. Preserve all CarPlay wire messages, feedback *transmissions*,
audio cadence, video encoding and Bluetooth/Wi-Fi lifecycle. The only new
runtime work change is caching a per-revision artwork fetch attempt; an absent
cover no longer spins up a new thread every second forever. The normal RTSP
feedback response is expected and only logged with an explicit verbose flag.
"""
from pathlib import Path

base=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay")

def once(src,old,new,label):
    count=src.count(old)
    if count!=1:
        raise AssertionError(f"v40 {label}: expected 1 anchor, got {count}: {old[:110]!r}")
    return src.replace(old,new,1)

p=base/"CarPlayV40Options.kt"
if p.exists():
    raise AssertionError("v40 options already exist")
p.write_text('''package io.github.nitsuya.aa.display.carplay

/** Only additional logging is opt-in; network feedback itself is unchanged. */
internal object CarPlayV40Options {
    val verboseControl: Boolean by lazy {
        runCatching {
            val cls = Class.forName("android.os.SystemProperties")
            val get = cls.getMethod("get", String::class.java, String::class.java)
            (get.invoke(null, "debug.carplay.v40_verbose_control", "0") as? String) == "1"
        }.getOrDefault(false)
    }
}
''',encoding="utf-8")

# Original code reads a Settings Global artwork revision every second. When
# art does not exist, the background thread exits without recording that the
# revision was attempted, causing an unbounded 1-thread-per-second retry.
# The art-revision counter changes on each new artwork/track update.
p=base/"CarPlayNowPlaying.kt"
s=p.read_text(encoding="utf-8")
s=once(s,
'''    private fun maybeTransferArtwork(revision: Long, trackId: String?) {
        Thread(
''',
'''    private fun maybeTransferArtwork(revision: Long, trackId: String?) {
        // v40: the egress must exist before committing an attempted revision.
        // Cache even a null/empty JPEG result, so a missing cover cannot
        // create one Binder fetch + new Java Thread on every elapsed tick.
        // A changed art revision, new track or egress rebind re-enables it.
        if (egress == null) return
        pushedArtRevision = revision
        Thread(
''',"one artwork fetch per revision")
p.write_text(s,encoding="utf-8")

p=base/"CarPlayRtspSession.kt"
s=p.read_text(encoding="utf-8")
s=once(s,
'''        Log.d(CarPlayConsts.TAG, "control feedback → cseq=$seq")
''',
'''        // v40: keep sending every feedback packet, omit 1/s log churn.
        if (CarPlayV40Options.verboseControl) {
            Log.d(CarPlayConsts.TAG, "control feedback → cseq=$seq")
        }
''',"feedback send log")
s=once(s,
'''            if (!deliverControlResponse(msg)) {
                Log.i(
                    CarPlayConsts.TAG,
                    "AirPlay enc ← ${msg.firstLine} body=${msg.body.size}B (orphan cseq=${msg.cSeq})",
                )
            }
''',
'''            if (!deliverControlResponse(msg)) {
                // 900000+ is the normal, write-only /feedback response,
                // not an orphan failure. Retain anomalous responses and
                // allow opt-in verbose logging for all responses.
                if (msg.cSeq < 900_000 || CarPlayV40Options.verboseControl) {
                    Log.i(
                        CarPlayConsts.TAG,
                        "AirPlay enc ← ${msg.firstLine} body=${msg.body.size}B (orphan cseq=${msg.cSeq})",
                    )
                }
            }
''',"suppress normal feedback response log")
p.write_text(s,encoding="utf-8")

p=Path("aa-display/build.gradle.kts")
s=p.read_text(encoding="utf-8")
s=once(s,"versionCode = 3139","versionCode = 3140","version code")
s=once(s,'versionName = "0.3#17.8-v39"',
         'versionName = "0.3#17.8-v40"',"version name")
p.write_text(s,encoding="utf-8")
print("v40 applied: missing-artwork thread storm fixed; routine RTSP feedback logs opt-in")

#!/usr/bin/env python3
"""v57r1: retire sender with final CarPlay session, not every codec re-SETUP."""
from pathlib import Path

r=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(path,a,b,label):
    p=r/path
    s=p.read_text(encoding="utf-8")
    n=s.count(a)
    if n!=1:raise AssertionError("v57r1 "+label+" matches="+str(n))
    p.write_text(s.replace(a,b,1),encoding="utf-8")

one("carplay/CarPlayVideoEncoder.kt",
    "    private var v57AwaitIdr = true\n    private var v57Dropped = 0L",
    "    private var v57AwaitIdr = true\n    private var v57Shutdown = false\n    private var v57Dropped = 0L",
    "sender shutdown flag")
one("carplay/CarPlayVideoEncoder.kt",
    "while (v57Pending.isEmpty()) {",
    "while (v57Pending.isEmpty() && !v57Shutdown) {",
    "wait exit predicate")
one("carplay/CarPlayVideoEncoder.kt",
    "                    v57Pending.removeFirst()\n                }\n                if (frame.epoch",
    "                    if (v57Shutdown) return@thread\n                    v57Pending.removeFirst()\n                }\n                if (frame.epoch",
    "exit sender")
one("carplay/CarPlayVideoEncoder.kt",
    "    /** Frames dropped for back-pressure",
    """    /** Only for final CarPlay session teardown, not a soft codec restart. */
    fun shutdown() {
        stop()
        synchronized(v57Lock) {
            v57Shutdown=true
            v57Pending.clear()
            v57Lock.notifyAll()
        }
    }

    /** Frames dropped for back-pressure""",
    "sender shutdown method")
one("carplay/CarPlaySourceSession.kt",
    "        tee.setGlExclusive(false)\n        tee.stop()\n        encoder.stop()\n        supplyFps =",
    "        tee.setGlExclusive(false)\n        tee.stop()\n        encoder.shutdown()\n        supplyFps =",
    "only final SourceSession.stop()")
g=Path("aa-display/build.gradle.kts")
s=g.read_text(encoding="utf-8")
assert s.count("versionCode = 3157")==1 and s.count('versionName = "0.3#17.8-v57"')==1
g.write_text(s.replace("versionCode = 3157","versionCode = 3158")
    .replace('versionName = "0.3#17.8-v57"',
             'versionName = "0.3#17.8-v57r1"'),encoding="utf-8")
print("v57r1 send worker lifetime fixed; no orphan idle threads")

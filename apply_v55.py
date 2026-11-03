#!/usr/bin/env python3
from pathlib import Path
r=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p=r/"carplay/protocol/CarPlayEventChannel.kt"
s=p.read_text()
def sub(a,b,label):
 global s
 n=s.count(a)
 if n!=1:raise AssertionError(label+" count="+str(n))
 s=s.replace(a,b,1)
sub("    @Volatile private var screenPermanent = ENTITY_PHONE\n    @Volatile private var audioEntity = ENTITY_PHONE",
"""    @Volatile private var screenPermanent = ENTITY_PHONE
    private var v55BackupCameraBorrowed = false
    @Volatile private var audioEntity = ENTITY_PHONE""","screen vars")
sub('            "requestUI" -> {\n                Log.i(CarPlayConsts.TAG, "event requestUI keys='+chr(36)+'{dict.keys}")\n                onForceKeyFrame()\n            }',
'''            "requestUI" -> {
                // Reclaim only in response to an explicit head-unit UI request,
                // NEVER during an active backup-camera screen borrow.
                val reclaimed = synchronized(modesLock) {
                    val eligible = !v55BackupCameraBorrowed &&
                        screenEntity == ENTITY_ACCESSORY &&
                        screenPermanent == ENTITY_ACCESSORY &&
                        v55RequestUiReclaimEnabled()
                    if (eligible) {
                        screenEntity = ENTITY_PHONE
                        screenPermanent = ENTITY_PHONE
                    }
                    Log.i(CarPlayConsts.TAG,
                        "v55 requestUI screen=" + screenEntity + "/" + screenPermanent +
                        " cameraBorrow=" + v55BackupCameraBorrowed +
                        " reclaimed=" + eligible)
                    eligible
                }
                if (reclaimed) {
                    runCatching { onModesRestoredToPhone() }
                        .onFailure { Log.w(CarPlayConsts.TAG, "v55 UI reclaim callback failed", it) }
                }
                onForceKeyFrame()
            }''',"requestUI")
sub("""                            TRANSFER_BORROW -> screenEntity = ENTITY_ACCESSORY
                            TRANSFER_UNBORROW -> screenEntity = screenPermanent""",
'''                            TRANSFER_BORROW -> {
                                screenEntity = ENTITY_ACCESSORY
                                if (r["borrowID"]?.toString() == "backupCamera") {
                                    v55BackupCameraBorrowed = true
                                }
                            }
                            TRANSFER_UNBORROW -> {
                                screenEntity = screenPermanent
                                if (r["borrowID"]?.toString() == "backupCamera") {
                                    v55BackupCameraBorrowed = false
                                }
                            }''',"camera borrow")
sub("    /** Current MainScreen+MainAudio ownership snapshot (Audi volume / mixer). */",
'''    /** Disable v55 in live process: setprop debug.carplay.v55_requestui_reclaim 0. */
    private fun v55RequestUiReclaimEnabled(): Boolean = runCatching {
        val cls = Class.forName("android.os.SystemProperties")
        val get = cls.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, "debug.carplay.v55_requestui_reclaim", "1") as String) != "0"
    }.getOrDefault(true)

    /** Current MainScreen+MainAudio ownership snapshot (Audi volume / mixer). */''',"opt-out")
p.write_text(s)
g=Path("aa-display/build.gradle.kts");v=g.read_text()
assert v.count("versionCode = 3154")==1 and v.count('versionName = "0.3#17.8-v54"')==1
g.write_text(v.replace("versionCode = 3154","versionCode = 3155").replace('versionName = "0.3#17.8-v54"','versionName = "0.3#17.8-v55"'))
print("v55 guarded requestUI MainScreen takeover applied")

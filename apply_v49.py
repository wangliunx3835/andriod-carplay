#!/usr/bin/env python3
"""v49: read-only, opt-in IME decision entry trace. Apply after v48."""
from pathlib import Path
def one(src, old, new, label):
    n=src.count(old)
    if n!=1: raise AssertionError(f"v49 {label}: expected 1, got {n}")
    return src.replace(old,new,1)
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/xposed/hook/VdImeDisplayPin.kt")
s=p.read_text(encoding="utf-8")
s=one(s,'    @Volatile private var v48AttachCalls = 0',
      '    @Volatile private var v48AttachCalls = 0\n    @Volatile private var v49AttachEntryCalls = 0',"counter")
s=one(s,
'''                    val diag = v41Enabled("debug.carplay.v48_ime_diag")
                    val repair = v41Enabled("debug.carplay.v48_ime_display_area")''',
'''                    val diag = v41Enabled("debug.carplay.v48_ime_diag")
                    // Read-only, sampled BEFORE v48's early return conditions.
                    if (v41Enabled("debug.carplay.v49_ime_trace")) {
                        v49AttachEntryCalls++
                        if (v49AttachEntryCalls <= 20 || v49AttachEntryCalls % 50 == 0) {
                            val dc49 = param.thisObject
                            val id49 = runCatching { displayIdOfDisplayContent(dc49) }.getOrNull()
                            val isAA49 = runCatching {
                                id49?.let { CoreManagerService.isAaVirtualDisplay(it) }
                            }.getOrNull()
                            val container49 = runCatching {
                                findField(dc49.javaClass, "mImeWindowsContainer")?.get(dc49)
                            }.getOrNull()
                            val organized49 = runCatching {
                                container49?.let { v41Call(it, "isOrganized") }
                            }.getOrNull()
                            log(TAG, "v49 attachEntry id=$id49 aa=$isAA49 " +
                                "original=" + param.result +
                                " live=" + CoreManagerService.hasAaVirtualDisplays() +
                                " container=" + (container49 != null) +
                                " organized=$organized49 count=$v49AttachEntryCalls")
                        }
                    }
                    val repair = v41Enabled("debug.carplay.v48_ime_display_area")''',
"hook body")
s=one(s,'            "updates=$v48UpdateCalls leashEvents=$v48LeashCalls")',
      '            "updates=$v48UpdateCalls leashEvents=$v48LeashCalls" +\n' +
      '            " v49EntryCalls=$v49AttachEntryCalls")',"status")
p.write_text(s,encoding="utf-8")
g=Path("aa-display/build.gradle.kts")
t=g.read_text(encoding="utf-8")
t=one(t,"versionCode = 3148","versionCode = 3149","version code")
t=one(t,'versionName = "0.3#17.8-v48"','versionName = "0.3#17.8-v49"',"version name")
g.write_text(t,encoding="utf-8")
print("v49 opt-in read-only IME entry trace installed; default OFF")

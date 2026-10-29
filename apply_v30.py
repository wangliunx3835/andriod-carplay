#!/usr/bin/env python3
"""v30: respect reversing-camera MainScreen BORROW and trial HyperOS IME fix.
Applies after v29. Never change video/control stream liveness during reverse.
Only CarPlay-created VDs use SECURE-off trial; AA VDs remain unchanged.
"""
from pathlib import Path
root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
event=root/"carplay/protocol/CarPlayEventChannel.kt"
rtsp=root/"carplay/CarPlayRtspSession.kt"
vd=root/"ui/aa/split/SplitVdLifecycle.kt"
gradle=Path("aa-display/build.gradle.kts")

def one(src,old,new,label):
    n=src.count(old)
    if n!=1:
        raise AssertionError(f"v30 {label}: {n} matches, anchor {old[:100]!r}")
    return src.replace(old,new,1)

s=event.read_text()
s=one(s,
'''    fun isPhoneOwningMainAudio(): Boolean = audioEntity == ENTITY_PHONE
''',
'''    fun isPhoneOwningMainAudio(): Boolean = audioEntity == ENTITY_PHONE

    /** Accessory temporarily owns MainScreen during BORROW/TAKE (reverse camera). */
    fun isPhoneOwningMainScreen(): Boolean = screenEntity == ENTITY_PHONE
''',"screen ownership query")
s=one(s,
'''    private fun currentModesParams(): Map<String, Any?> = synchronized(modesLock) {
''',
'''    /** Preserve HU ownership and permanence when composing an outbound modesChanged. */
    fun currentModesParams(): Map<String, Any?> = synchronized(modesLock) {
''',"mode snapshot access")
event.write_text(s)

s=rtsp.read_text()
start=s.index('        fun announcePhoneModesChanged(): Boolean = postControlCommand(')
end=s.index('\n        modesRestored.set { announcePhoneModesChanged() }', start)
old=s[start:end]
assert old.count('"resourceID" to 1')==1 and old.count('"resourceID" to 2')==1
new='''        fun announcePhoneModesChanged(): Boolean {
            val ev = eventChannel.get()
            // HU BORROW/TAKE for backup camera has precedence. Never send the
            // old hardcoded "phone owns MainScreen" claim during that window.
            if (ev != null && !ev.isPhoneOwningMainScreen()) {
                Log.i(CarPlayConsts.TAG, "v30 skip modesChanged: HU owns MainScreen (reverse/native)")
                return false
            }
            // Use the actual response snapshot (including HU-owned resources)
            // instead of unconditionally assigning both resources to phone.
            val actualModes = ev?.currentModesParams() ?: linkedMapOf(
                "resources" to listOf(
                    linkedMapOf("resourceID" to 1, "entity" to 1, "permanentEntity" to 1),
                    linkedMapOf("resourceID" to 2, "entity" to 1, "permanentEntity" to 1),
                ),
                "appStates" to listOf(
                    linkedMapOf("appStateID" to 2, "entity" to 0),
                    linkedMapOf("appStateID" to 3, "entity" to 0),
                    linkedMapOf("appStateID" to 1, "entity" to 0, "speechMode" to -1),
                ),
            )
            if (ev != null && !ev.isPhoneOwningMainScreen()) {
                Log.i(CarPlayConsts.TAG, "v30 cancel modesChanged: HU borrowed screen during snapshot")
                return false
            }
            return postControlCommand(
                linkedMapOf("type" to "modesChanged", "params" to actualModes),
                "v30 resource-aware modesChanged",
            )
        }
'''
s=s[:start]+new+s[end:]
s=one(s,
'''        if (ev != null && !ev.isPhoneOwningMainAudio()) {
            Log.i(CarPlayConsts.TAG, "modesChanged skip ($reason) — HU owns MainAudio")
            return
        }
''',
'''        if (ev != null && !ev.isPhoneOwningMainAudio()) {
            Log.i(CarPlayConsts.TAG, "modesChanged skip ($reason) — HU owns MainAudio")
            return
        }
        if (ev != null && !ev.isPhoneOwningMainScreen()) {
            Log.i(CarPlayConsts.TAG, "v30 skip modes reclaim ($reason): HU owns MainScreen")
            return
        }
''',"skip periodic reclaim when HU owns reverse screen")
rtsp.write_text(s)

s=vd.read_text()
s=one(s,
'''import io.github.nitsuya.aa.display.xposed.hook.PaneDisplayGroupForce
''',
'''import io.github.nitsuya.aa.display.xposed.hook.PaneDisplayGroupForce
import io.github.nitsuya.aa.display.xposed.CoreManagerService
''',"CarPlay live flag import")
s=one(s,
'''    fun vdFlags(): Int {
''',
'''    fun vdFlags(): Int {
        // HyperOS trial: IME has a drawn buffer but is absent from virtual
        // Output Layers. Remove SECURE only on CarPlay VDs; regular AA is kept
        // unchanged. Restore with root property then recreate the two VDs:
        // setprop debug.carplay.v30_keep_secure_vd 1
        val carPlayLive = CoreManagerService.isCarPlaySessionLive()
        val keepSecureForCarPlay = runCatching {
            val sp = Class.forName("android.os.SystemProperties")
            sp.getMethod(
                "getBoolean", String::class.java, Boolean::class.javaPrimitiveType,
            ).invoke(null, "debug.carplay.v30_keep_secure_vd", false) == true
        }.getOrDefault(false)
        val secureFlag = if (carPlayLive && !keepSecureForCarPlay) {
            0
        } else {
            DisplayManager.VIRTUAL_DISPLAY_FLAG_SECURE
        }
        log(SplitDisplayController.TAG,
            "v30 VD flags carPlayLive=" + carPlayLive +
                " SECURE=" + (secureFlag != 0) +
                " keepSecureOverride=" + keepSecureForCarPlay)
''',"CarPlay-only SECURE trial")
s=one(s,
'''            DisplayManager.VIRTUAL_DISPLAY_FLAG_SECURE or
''',
'''            secureFlag or
''',"conditional secure bit")
s=one(s,
'''        val imePolicy = 0 // DISPLAY_IME_POLICY_LOCAL
''',
'''        val imePolicy = runCatching {
            Class.forName("android.view.WindowManager")
                .getField("DISPLAY_IME_POLICY_LOCAL").getInt(null)
        }.getOrDefault(0) // AOSP LOCAL policy
''',"runtime LOCAL policy constant")
s=one(s,
'''                runCatching { iwm.setDisplayImePolicy(displayId, imePolicy) }
                    .onFailure {
                        logDebug(SplitDisplayController.TAG, "setDisplayImePolicy: ${it.message}")
                    }
''',
'''                runCatching {
                    iwm.setDisplayImePolicy(displayId, imePolicy)
                    if (!resizeHotPath) {
                        val readBack = runCatching {
                            iwm.javaClass.getMethod(
                                "getDisplayImePolicy", Int::class.javaPrimitiveType,
                            ).invoke(iwm, displayId)
                        }.getOrElse { "unavailable: " + it.javaClass.simpleName }
                        log(SplitDisplayController.TAG,
                            "v30 IME policy display=" + displayId +
                                " LOCAL=" + imePolicy + " actual=" + readBack)
                    }
                }.onFailure {
                    log(SplitDisplayController.TAG,
                        "v30 setDisplayImePolicy failed display=" + displayId +
                            " policy=" + imePolicy, it)
                }
''',"verify IME policy")
vd.write_text(s)

s=gradle.read_text()
s=one(s,"versionCode = 3129","versionCode = 3130","versionCode")
s=one(s,'versionName = "0.3#17.8-v29"','versionName = "0.3#17.8-v30"',"versionName")
gradle.write_text(s)
print("v30: reverse-screen borrowing guarded, CarPlay-only non-SECURE trial, IME LOCAL readback")

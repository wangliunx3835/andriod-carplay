#!/usr/bin/env python3
"""v30 non-release test: rear-camera resource arbitration + HyperOS IME VD options.

Apply after v29. Preserve v23 IPv4 fast readiness, v29 AirPlay single-owner,
dual VDs, frame/feedback keepalives, and v28 performance cleanup.
To restore the original SECURE virtual-display flag, run as root before reconnect:
    setprop debug.carplay.v30_ime_secure 1
"""
from pathlib import Path

root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
event=root/"carplay/protocol/CarPlayEventChannel.kt"
rtsp=root/"carplay/CarPlayRtspSession.kt"
vd=root/"ui/aa/split/SplitVdLifecycle.kt"
gradle=Path("aa-display/build.gradle.kts")

def once(s, old, new, label):
    n=s.count(old)
    if n != 1:
        raise AssertionError(f"v30 {label}: anchor count={n} != 1: {old[:120]!r}")
    return s.replace(old,new,1)

s=event.read_text(encoding="utf-8")
s=once(s,
    '''    fun isPhoneOwningMainAudio(): Boolean = audioEntity == ENTITY_PHONE
''',
    '''    fun isPhoneOwningMainAudio(): Boolean = audioEntity == ENTITY_PHONE

    /** MainScreen borrowed by HU (for example a reverse camera) is NOT phone-owned. */
    fun isPhoneOwningMainScreen(): Boolean = screenEntity == ENTITY_PHONE
''', "screen ownership accessor")
s=once(s,
    '''                if (restored) {
                    try {
                        onModesRestoredToPhone()
''',
    '''                if (restored) {
                    Log.i(CarPlayConsts.TAG,
                        "v30 changeModes resources returned: screenPhone=" +
                            isPhoneOwningMainScreen() + " audioPhone=" + isPhoneOwningMainAudio())
                    try {
                        onModesRestoredToPhone()
''', "restore audit")
event.write_text(s, encoding="utf-8")

s=rtsp.read_text(encoding="utf-8")
s=once(s,
    '''        if (ev != null && !ev.isPhoneOwningMainAudio()) {
            Log.i(CarPlayConsts.TAG, "modesChanged skip ($reason) — HU owns MainAudio")
            return
        }
''',
    '''        if (ev != null &&
            (!ev.isPhoneOwningMainScreen() || !ev.isPhoneOwningMainAudio())) {
            Log.i(CarPlayConsts.TAG,
                "v30 modesChanged skip ($reason): HU owns " +
                    "MainScreen=${!ev.isPhoneOwningMainScreen()} " +
                    "MainAudio=${!ev.isPhoneOwningMainAudio()}")
            return
        }
''', "guard both resource owners in periodic reclaim")
s=once(s,
    '''        fun announcePhoneModesChanged(): Boolean = postControlCommand(
            linkedMapOf(
''',
    '''        fun announcePhoneModesChanged(): Boolean {
            // While HU owns MainScreen, never reassert phone screen during reverse.
            // Keep video TCP active: some receivers tear down after a stream silence.
            val current = eventChannel.get()
            if (current != null &&
                (!current.isPhoneOwningMainScreen() || !current.isPhoneOwningMainAudio())) {
                Log.i(CarPlayConsts.TAG,
                    "v30 suppress screen reclaim: " +
                        "screenPhone=${current.isPhoneOwningMainScreen()} " +
                        "audioPhone=${current.isPhoneOwningMainAudio()}")
                return false
            }
            return postControlCommand(
                linkedMapOf(
''', "guard all direct phone-owned modes announcements")
s=once(s,
    '''            "modesChanged phone-owns-screen+audio",
        )
        modesRestored.set { announcePhoneModesChanged() }
''',
    '''                "modesChanged phone-owns-screen+audio",
            )
        }
        modesRestored.set { announcePhoneModesChanged() }
''', "finish guarded modes announcement")
rtsp.write_text(s, encoding="utf-8")

s=vd.read_text(encoding="utf-8")
s=once(s,
    '''        return DisplayManager.VIRTUAL_DISPLAY_FLAG_PUBLIC or
            DisplayManager.VIRTUAL_DISPLAY_FLAG_SECURE or
''',
    '''        // Cardeck's known-good app VDs use PUBLIC/TRUSTED/OWN_CONTENT_ONLY
        // without SECURE. Test this vendor output-path difference on HyperOS.
        // Default OFF for SECURE; setprop debug.carplay.v30_ime_secure 1
        // then recreate displays to restore the previous v29 behavior.
        val keepSecure = runCatching {
            val props = Class.forName("android.os.SystemProperties")
            props.getMethod(
                "getBoolean", String::class.java, Boolean::class.javaPrimitiveType,
            ).invoke(null, "debug.carplay.v30_ime_secure", false) == true
        }.getOrDefault(false)
        log(SplitDisplayController.TAG,
            "v30 IME VD flags SECURE=$keepSecure PUBLIC=true TRUSTED=true " +
                "(restore using debug.carplay.v30_ime_secure=1 then reconnect)")
        return DisplayManager.VIRTUAL_DISPLAY_FLAG_PUBLIC or
            (if (keepSecure) DisplayManager.VIRTUAL_DISPLAY_FLAG_SECURE else 0) or
''', "try nonsecure app-VD compatibility")
s=once(s,
    '''        val imePolicy = 0 // DISPLAY_IME_POLICY_LOCAL
''',
    '''        val imePolicy = runCatching {
            Class.forName("android.view.WindowManager")
                .getField("DISPLAY_IME_POLICY_LOCAL")
                .getInt(null)
        }.getOrElse {
            log(SplitDisplayController.TAG,
                "v30 LOCAL IME reflection unavailable; use AOSP 0", it)
            0
        }
''', "read ROM-specific IME local policy")
s=once(s,
    '''                runCatching { iwm.setDisplayImePolicy(displayId, imePolicy) }
                    .onFailure {
                        logDebug(SplitDisplayController.TAG, "setDisplayImePolicy: ${it.message}")
                    }
''',
    '''                runCatching { iwm.setDisplayImePolicy(displayId, imePolicy) }
                    .onFailure {
                        log(SplitDisplayController.TAG,
                            "v30 setDisplayImePolicy failed display=$displayId", it)
                    }
                // Read back once per VD creation or policy reapply; no GPU capture.
                if (!resizeHotPath) {
                    val actual = runCatching {
                        iwm.javaClass.getMethod(
                            "getDisplayImePolicy", Int::class.javaPrimitiveType,
                        ).invoke(iwm, displayId)
                    }.getOrElse { "unsupported: ${it.javaClass.simpleName}" }
                    log(SplitDisplayController.TAG,
                        "v30 display=$displayId IME LOCAL=$imePolicy readBack=$actual reason=$reason")
                }
''', "verify per-display local IME policy")
vd.write_text(s, encoding="utf-8")

g=gradle.read_text(encoding="utf-8")
g=once(g,"versionCode = 3129","versionCode = 3130","version code")
g=once(g,'versionName = "0.3#17.8-v29"','versionName = "0.3#17.8-v30"',"version name")
gradle.write_text(g, encoding="utf-8")
print("v30 applied: MainScreen BORROW guard, Cardeck-aligned non-SECURE VD experiment, IME policy readback")

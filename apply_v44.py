#!/usr/bin/env python3
"""v44: Opt-in WindowManager IME parent-choice repair on CarPlay pane VDs.

Correct computeImeParent() BEFORE WindowManager's synchronized reparent and
relative layer assignment, rather than mutating surfaces afterwards.
The v43 Gboard-specific OEM allowlist experiment is retired in v44.
"""
from pathlib import Path
ROOT = Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def once(src, old, new, title):
    count = src.count(old)
    if count != 1:
        raise AssertionError(f"v44 {title}: expected one match, found {count}")
    return src.replace(old, new, 1)

p = ROOT / "xposed/hook/VdImeDisplayPin.kt"
s = p.read_text(encoding="utf-8")
s = once(s, '    private var v41ImeTargetHook: XC_MethodHook.Unhook? = null',
'''    private var v41ImeTargetHook: XC_MethodHook.Unhook? = null
    private var v44ImeParentHook: XC_MethodHook.Unhook? = null
    @Volatile private var v44HookStatus = "not-attempted"
    @Volatile private var v44LastDiagnostic = ""
    @Volatile private var v44LastDiagnosticMs = 0L
    @Volatile private var v44LastRepairMs = 0L
    @Volatile private var v44LastRuntimeMs = 0L''', "state")
s = once(s,
'''        runCatching { hookV41ImeSurfacePlacement() }
            .onFailure { log(TAG, "v41 IME surface placement hook install failed", it) }''',
'''        runCatching { hookV41ImeSurfacePlacement() }
            .onFailure { log(TAG, "v41 IME surface placement hook install failed", it) }
        runCatching { v44HookImeParentChoice() }
            .onFailure {
                v44HookStatus = "install-failed:" + it.javaClass.simpleName
                log(TAG, "v44 parent hook install failed", it)
            }''', "install")
s = once(s,
'        val repair = v41Enabled("debug.carplay.v41_ime_reparent")',
'''        val repair = v41Enabled("debug.carplay.v41_ime_reparent") &&
            !v41Enabled("debug.carplay.v44_ime_parent_policy")''', "legacy conflict")

anchor = '    private fun v28SurfaceOf(container: Any): SurfaceControl? {'
addition = r'''    /**
     * AOSP updateImeParent() uses computeImeParent() result for an atomic
     * reparent and relative-layer assignment. HyperOS SF captures show the
     * true InputMethod layer missing from VD output when attached under an
     * app ActivityRecord, while a temporary IME screenshot is present.
     * Opt-in: replace ONLY the computed parent for our AA pane display with
     * the declared IME display-area parent; leave WindowManager's own
     * transaction/layer machinery intact.
     *
     * DO NOT touch Display 0, organized IME containers or hidden/no-window IMEs.
     * No global OEM policy, package whitelist, polling or screen wakeup.
     */
    private fun v44HookImeParentChoice() {
        val method = AndroidHook.findSystemMethod(
            "com.android.server.wm.DisplayContent", findSuper = true,
        ) {
            name == "computeImeParent" && parameterTypes.isEmpty() &&
                SurfaceControl::class.java.isAssignableFrom(returnType)
        }
        if (method == null) {
            v44HookStatus = "computeImeParent-missing"
            log(TAG, "v44 computeImeParent unavailable; no repair possible")
            return
        }
        v44ImeParentHook = method.hookAfter { param ->
            try {
                if (!CoreManagerService.hasAaVirtualDisplays()) return@hookAfter
                val dc = param.thisObject
                val id = displayIdOfDisplayContent(dc) ?: return@hookAfter
                if (!CoreManagerService.isAaVirtualDisplay(id)) return@hookAfter
                val observe = v41Enabled("debug.carplay.v44_ime_diag")
                val repair = v41Enabled("debug.carplay.v44_ime_parent_policy")
                if (!observe && !repair) return@hookAfter

                val container = findField(dc.javaClass, "mImeWindowsContainer")
                    ?.get(dc) ?: return@hookAfter
                val parent = v41Call(container, "getParent")
                val expected = parent?.let { v28SurfaceOf(it) }
                val selected = param.result as? SurfaceControl
                val imeWindow = findField(dc.javaClass, "mInputMethodWindow")?.get(dc)
                val organized = v41Call(container, "isOrganized") == true
                val canRepair = imeWindow != null && !organized &&
                    selected?.isValid == true && expected?.isValid == true &&
                    selected !== expected

                val summary = "display=$id hasWindow=${imeWindow != null} " +
                    "organized=$organized originalValid=${selected?.isValid == true} " +
                    "displayAreaValid=${expected?.isValid == true} " +
                    "parent=${parent?.javaClass?.simpleName} different=${selected !== expected}"
                val now = android.os.SystemClock.uptimeMillis()
                if (summary != v44LastDiagnostic || now - v44LastDiagnosticMs >= 5_000L) {
                    v44LastDiagnostic = summary
                    v44LastDiagnosticMs = now
                    log(TAG, "v44 IME parent decision $summary " +
                        "mode=${if (repair) "REPAIR" else "OBSERVE"}")
                }
                if (repair && canRepair) {
                    param.result = expected
                    if (now - v44LastRepairMs >= 2_000L) {
                        v44LastRepairMs = now
                        log(TAG, "v44 selected display-area IME parent for VD=$id; " +
                            "WindowManager owns transaction and relative layering")
                    }
                }
            } catch (t: Throwable) {
                log(TAG, "v44 parent decision callback error", t)
            }
        }
        v44HookStatus = "hooked"
        log(TAG, "v44 IME parent choice installed (experiment OFF by default)")
    }

    fun v44ReportState(source: String) {
        val diag = v41Enabled("debug.carplay.v44_ime_diag")
        val repair = v41Enabled("debug.carplay.v44_ime_parent_policy")
        if (!diag && !repair) return
        val now = android.os.SystemClock.uptimeMillis()
        if (now - v44LastRuntimeMs < 8_000L) return
        v44LastRuntimeMs = now
        log(TAG, "v44 runtime source=$source hookStatus=$v44HookStatus " +
            "hooked=${v44ImeParentHook != null} diag=$diag repair=$repair " +
            "legacyRepair=${v41Enabled("debug.carplay.v41_ime_reparent")}")
    }

'''
s = once(s, anchor, addition + anchor, "parent hook code")
p.write_text(s, encoding="utf-8")

core = ROOT / "xposed/CoreManagerService.kt"
t = core.read_text(encoding="utf-8")
t = once(t, 'import io.github.nitsuya.aa.display.xposed.hook.V43ImeFreezeGuard\n', '', "old import")
t = once(t,
'''        // v43 opt-in, CarPlay-session-only Xiaomi Greezer IME workaround.
        // On false, restore any OEM list entry added by this guard.
        runCatching { V43ImeFreezeGuard.onCarPlaySession(systemContext, live) }
            .onFailure { log(TAG, "v43 IME freezer guard dispatch failed", it) }''',
'''        // v44 retires hard-coded Gboard OEM exemption.
        // IME parent experiment runs only in WM callback on our pane VDs.
        runCatching { VdImeDisplayPin.v44ReportState("CarPlay-live=$live") }
            .onFailure { log(TAG, "v44 IME status report failed", it) }''',
"remove fixed Gboard guard")
core.write_text(t, encoding="utf-8")

gradle = Path("aa-display/build.gradle.kts")
v = gradle.read_text(encoding="utf-8")
v = once(v, "versionCode = 3143", "versionCode = 3144", "versionCode")
v = once(v, 'versionName = "0.3#17.8-v43"', 'versionName = "0.3#17.8-v44"', "versionName")
gradle.write_text(v, encoding="utf-8")
print("v44: optional IME parent choice fix; v43 fixed Gboard guard retired")

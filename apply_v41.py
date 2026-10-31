#!/usr/bin/env python3
"""v41: HyperOS IME Surface parent instrumentation + gated placement experiment.

Apply AFTER v40. No CarPlay networking/codec/display-create flags change.
The two pane VirtualDisplays remain the only allowed targets. Default OFF.
System-server Xposed code requires a DEVICE REBOOT after an APK upgrade.
"""
from pathlib import Path

base = Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p = base / "xposed/hook/VdImeDisplayPin.kt"
s = p.read_text(encoding="utf-8")

def once(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise AssertionError(f"v41 {label}: expected 1 match, got {n}: {old[:140]!r}")
    return src.replace(old, new, 1)

s = once(s,
'''    private var v28ImeParentHook: XC_MethodHook.Unhook? = null''',
'''    private var v28ImeParentHook: XC_MethodHook.Unhook? = null
    private var v41ImeParentHook: XC_MethodHook.Unhook? = null
    private var v41ImeTargetHook: XC_MethodHook.Unhook? = null
    @Volatile private var v41LastDiagnostic = ""
    @Volatile private var v41LastDiagnosticMs = 0L
    @Volatile private var v41LastRepairMs = 0L''',
"v41 hook state")

s = once(s,
'''        runCatching { hookV28ImeParentExperiment() }
            .onFailure { log(TAG, "v28 IME parent experiment hook failed", it) }''',
'''        runCatching { hookV28ImeParentExperiment() }
            .onFailure { log(TAG, "v28 IME parent experiment hook failed", it) }
        runCatching { hookV41ImeSurfacePlacement() }
            .onFailure { log(TAG, "v41 IME surface placement hook install failed", it) }''',
"hook install call")

needle = '''    private fun v28SurfaceOf(container: Any): SurfaceControl? {'''
addition = '''    /**
     * v41: two separate, opt-in paths, both scoped strictly to our AA VDs:
     *   debug.carplay.v41_ime_diag=1   records sparse WM IME parent decisions
     *   debug.carplay.v41_ime_reparent=1   experimental placement repair
     *
     * v28 instead reparents to DisplayContent's top surface. Here we reparent
     * to the IME container's OWN WindowContainer parent (ImePlaceholder / the
     * designated IME DisplayArea). This avoids an app-bounds/clipping parent
     * while preserving that display's logical IME hierarchy.
     *
     * Hook the WM event rather than polling an app or encoder thread.
     * The feature is OFF by default. Only an explicit root setting enables
     * actual reparent, and there is no instrumentation on every video frame.
     */
    private fun hookV41ImeSurfacePlacement() {
        val parentMethod = AndroidHook.findSystemMethod(
            "com.android.server.wm.DisplayContent", findSuper = true,
        ) { name == "updateImeParent" && parameterTypes.isEmpty() }
        if (parentMethod == null) {
            log(TAG, "v41 updateImeParent absent; repair unavailable")
            return
        }
        v41ImeParentHook = parentMethod.hookAfter { param ->
            runCatching { v41ObserveImeParent(param.thisObject, "updateImeParent") }
                .onFailure { log(TAG, "v41 updateImeParent callback failed", it) }
        }
        // Some HyperOS builds choose the target before updateImeParent.
        // Observe the decision here too; repair runs only if an IME window is
        // already visible and belongs to an AADisplay virtual display.
        val targetMethod = AndroidHook.findSystemMethod(
            "com.android.server.wm.DisplayContent", findSuper = true,
        ) { name == "setImeLayeringTarget" && parameterTypes.size == 1 }
        if (targetMethod != null) {
            v41ImeTargetHook = targetMethod.hookAfter { param ->
                runCatching { v41ObserveImeParent(param.thisObject, "setImeLayeringTarget") }
                    .onFailure { log(TAG, "v41 target callback failed", it) }
            }
        }
        log(TAG,
            "v41 installed system_server IME hooks parent=${v41ImeParentHook != null} " +
                "target=${v41ImeTargetHook != null} (diagnostics and repair default OFF)")
    }

    private fun v41Enabled(key: String): Boolean = runCatching {
        val prop = Class.forName("android.os.SystemProperties")
        val get = prop.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, key, "0") as? String) == "1"
    }.getOrDefault(false)

    private fun v41Call(target: Any, name: String): Any? {
        var cls: Class<*>? = target.javaClass
        while (cls != null && cls != Any::class.java) {
            val method = cls.declaredMethods.firstOrNull {
                it.name == name && it.parameterTypes.isEmpty()
            }
            if (method != null) {
                return runCatching {
                    method.isAccessible = true
                    method.invoke(target)
                }.getOrNull()
            }
            cls = cls.superclass
        }
        return null
    }

    private fun v41ImeVisible(window: Any): Boolean {
        for (name in arrayOf("isVisible", "isOnScreen")) {
            val result = v41Call(window, name)
            if (result is Boolean) return result
        }
        return false // never reparent an unknown/hidden IME window
    }

    private fun v41ObserveImeParent(dc: Any, event: String) {
        val displayId = displayIdOfDisplayContent(dc) ?: return
        if (!CoreManagerService.isAaVirtualDisplay(displayId)) return
        val diag = v41Enabled("debug.carplay.v41_ime_diag")
        val repair = v41Enabled("debug.carplay.v41_ime_reparent")
        if (!diag && !repair) return

        val container = findField(dc.javaClass, "mImeWindowsContainer")
            ?.get(dc) ?: return
        val window = findField(dc.javaClass, "mInputMethodWindow")
            ?.get(dc)
        val visible = window != null && v41ImeVisible(window)
        val nativeParent = v41Call(container, "getParent")
        val imeSurface = v28SurfaceOf(container)
        val placeholderSurface = nativeParent?.let { v28SurfaceOf(it) }
        val valid = imeSurface?.isValid == true && placeholderSurface?.isValid == true
        val now = android.os.SystemClock.uptimeMillis()

        if (diag) {
            val key = "display=$displayId visible=$visible valid=$valid nativeParent=${nativeParent?.javaClass?.simpleName}"
            if (key != v41LastDiagnostic || now - v41LastDiagnosticMs >= 5_000L) {
                v41LastDiagnostic = key
                v41LastDiagnosticMs = now
                log(TAG, "v41 ime state event=$event $key")
            }
        }

        if (!repair || !visible || !valid) return
        // Avoid repeated transactions when WM fires several callbacks within
        // one frame. A later IME-target transition can still retry.
        if (now - v41LastRepairMs < 300L) return
        v41LastRepairMs = now
        val ime = imeSurface ?: return
        val placeholder = placeholderSurface ?: return
        if (ime === placeholder) return

        // Restore only the IME container surface to the placeholder on its
        // same virtual display, never manipulate the physical display 0,
        // the keyboard app process, or any other WindowContainer.
        SurfaceControl.Transaction().use { tx ->
            tx.reparent(ime, placeholder)
            tx.setLayer(ime, 1_000_000)
            tx.apply()
        }
        log(TAG, "v41 IME surface reparent applied display=$displayId event=$event " +
            "target=${nativeParent?.javaClass?.simpleName}")
    }

'''
s = once(s, needle, addition + needle, "v41 WM hook implementation")
p.write_text(s, encoding="utf-8")

p = Path("aa-display/build.gradle.kts")
v = p.read_text(encoding="utf-8")
v = once(v, "versionCode = 3140", "versionCode = 3141", "version code")
v = once(v, 'versionName = "0.3#17.8-v40"',
         'versionName = "0.3#17.8-v41"', "version name")
p.write_text(v, encoding="utf-8")

print("v41 applied: opt-in HyperOS virtual-IME placement diagnostics and gated repair; v39/v40 unchanged")

#!/usr/bin/env python3
"""v28: remove obsolete always-on diagnostics; optional AA-only IME z-parent experiment.

Apply strictly after v27. Runtime is lean by default. The experimental IME root
parent fix is OFF by default and must be opted in using root:
    su -c 'setprop debug.carplay.v28_ime_root 1'
Reconnect CarPlay after switching the flag, and disable with setprop ... 0.
The hook is limited to the two AADisplay virtual displays, never Display 0.
No changes to v23 networking/RTSP/audio/touch or VD flags.
"""
from pathlib import Path

ROOT = Path('aa-display/src/main/java/io/github/nitsuya/aa/display')
ime = ROOT / 'ui/aa/split/SplitImeController.kt'
gl = ROOT / 'carplay/CarPlayGlCompositor.kt'
hook = ROOT / 'xposed/hook/VdImeDisplayPin.kt'
gradle = Path('aa-display/build.gradle.kts')


def one(s: str, old: str, new: str, label: str) -> str:
    count = s.count(old)
    if count != 1:
        raise AssertionError(f'v28 {label}: expected 1 match, got {count}; {old[:100]!r}')
    return s.replace(old, new, 1)

# Preserve the controller's 200/400ms poll: it powers the hide-keyboard chip.
# v21 already restored the upstream controller, removing v18-v20 probes.
# Suppress only the remaining v24 geometry sampler.
s = ime.read_text(encoding='utf-8')
s = one(s, '            v24SampleIme()\n', '', 'v24 periodic geometry scan')
ime.write_text(s, encoding='utf-8')

s = gl.read_text(encoding='utf-8')
start = '        // v25: small GL readback from the exact encoder framebuffer, once every 5s.'
end = '        // Shared media clock'
a, b = s.find(start), s.find(end)
assert a >= 0 and b > a and s.count(start) == 1 and s.count(end) == 1, 'v25 GL probe boundaries'
s = s[:a] + s[b:]
s = one(s, '''    private val v25Received = longArrayOf(0L, 0L)
    private val v25Consumed = longArrayOf(0L, 0L)
    private var v25LastReportMs = 0L
''', '', 'v25 counters fields')
s = one(s, '''                    frameAvailable[i] = true
                    v25Received[i]++
''', '''                    frameAvailable[i] = true
''', 'v25 frame callback counter')
s = one(s, '''                    surfaceTextures[i]?.updateTexImage()
                    v25Consumed[i]++
''', '''                    surfaceTextures[i]?.updateTexImage()
''', 'v25 consumed counter')
# Avoid three full-resolution readbacks + PNG compression 15s after every attach.
s = one(s, '''        val v26Capture = !v26Captured && SystemClock.uptimeMillis() >= v26CaptureAtMs''',
        '''        val v26Capture = false // v28: disable automatic timed screenshots''', 'v26 timed readback')
s = one(s, '                v26CaptureAtMs = windowStart + 15000L\n', '', 'v26 capture scheduling')
s = one(s, '    private var v26CaptureAtMs = 0L\n', '', 'v26 capture timer state')
# Keep manual one-shot GPU captures, but only check for a root-requested trigger ~1/s.
s = one(s, 'now - v27LastTriggerCheckMs < 350L',
        'now - v27LastTriggerCheckMs < 1_000L', 'v27 manual trigger frequency')
gl.write_text(s, encoding='utf-8')

# This is an *opt-in*, reversible experiment for the SF virtual-output omission:
# an IME Surface attached relative to Via's window is moved to the same VD
# DisplayContent root, with a high z-order. No per-frame work, no security flags
# are cleared, and no phone physical display is touched. Results are unproven.
s = hook.read_text(encoding='utf-8')
s = one(s, 'import android.view.Display\n',
        'import android.view.Display\nimport android.view.SurfaceControl\n', 'SurfaceControl import')
s = one(s, '''    private var displayImePolicyHook: XC_MethodHook.Unhook? = null''',
        '''    private var displayImePolicyHook: XC_MethodHook.Unhook? = null
    private var v28ImeParentHook: XC_MethodHook.Unhook? = null''', 'v28 hook state')
s = one(s, '''        runCatching { hookDisplayImePolicy() }
            .onFailure { log(TAG, "displayImePolicy install failed", it) }''',
        '''        runCatching { hookDisplayImePolicy() }
            .onFailure { log(TAG, "displayImePolicy install failed", it) }
        runCatching { hookV28ImeParentExperiment() }
            .onFailure { log(TAG, "v28 IME parent experiment hook failed", it) }''',
        'v28 hook registration')
needle = '    private fun displayIdOfDisplayContent(dc: Any): Int? {'
addition = '''    /**
     * v28 opt-in experiment: on AA virtual displays only, detach the IME
     * container from its relative-app parent and attach it directly under the
     * same DisplayContent root. It can be turned on with:
     *   su -c 'setprop debug.carplay.v28_ime_root 1'
     * Default OFF, since the exact HyperOS SurfaceFlinger exclusion rule has
     * not been identified. Reconnect the session to reset the hierarchy.
     * Runs only on IME parent updates, never in the render/poll loop.
     */
    private fun hookV28ImeParentExperiment() {
        val method = AndroidHook.findSystemMethod(
            "com.android.server.wm.DisplayContent", findSuper = true,
        ) { name == "updateImeParent" && parameterTypes.isEmpty() }
        if (method == null) {
            log(TAG, "v28 updateImeParent unavailable: experiment inactive")
            return
        }
        v28ImeParentHook = method.hookAfter { param ->
            try {
                val dc = param.thisObject
                val id = displayIdOfDisplayContent(dc) ?: return@hookAfter
                if (!CoreManagerService.isAaVirtualDisplay(id)) return@hookAfter
                val property = Class.forName("android.os.SystemProperties")
                val enabled = property.getMethod(
                    "getBoolean", String::class.java, Boolean::class.javaPrimitiveType,
                ).invoke(null, "debug.carplay.v28_ime_root", false) == true
                if (!enabled) return@hookAfter
                val imeContainer = findField(dc.javaClass, "mImeWindowsContainer")
                    ?.get(dc) ?: return@hookAfter
                val imeSurface = v28SurfaceOf(imeContainer) ?: return@hookAfter
                val rootSurface = v28SurfaceOf(dc) ?: return@hookAfter
                if (!imeSurface.isValid || !rootSurface.isValid) return@hookAfter
                SurfaceControl.Transaction().use { tx ->
                    tx.reparent(imeSurface, rootSurface)
                    tx.setLayer(imeSurface, 1_000_000)
                    tx.apply()
                }
                log(TAG, "v28 experimental IME root parent attached display=$id")
            } catch (t: Throwable) {
                log(TAG, "v28 experimental IME parent failed", t)
            }
        }
        log(TAG, "v28 opt-in IME root parent hook installed (default OFF)")
    }

    private fun v28SurfaceOf(container: Any): SurfaceControl? {
        var cls: Class<*>? = container.javaClass
        while (cls != null && cls != Any::class.java) {
            val method = cls.declaredMethods.firstOrNull {
                it.name == "getSurfaceControl" && it.parameterTypes.isEmpty()
            }
            if (method != null) {
                method.isAccessible = true
                return method.invoke(container) as? SurfaceControl
            }
            cls = cls.superclass
        }
        return null
    }

'''
s = one(s, needle, addition + needle, 'v28 experiment implementation')
hook.write_text(s, encoding='utf-8')

v = gradle.read_text(encoding='utf-8')
v = one(v, 'versionCode = 3127', 'versionCode = 3128', 'versionCode')
v = one(v, 'versionName = "0.3#17.8-v27"', 'versionName = "0.3#17.8-v28"', 'versionName')
gradle.write_text(v, encoding='utf-8')
print('v28 applied: disabled remaining v24/v25/v26 diagnostics; kept manual captures; optional experimental IME parent')

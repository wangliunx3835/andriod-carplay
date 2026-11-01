#!/usr/bin/env python3
"""v45: Android16 WindowContainer computeImeParent() compatibility and opt-in IME area policy.
Apply after v44; no package-name allowlists or global freezes.
"""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def once(s,a,b,label):
    n=s.count(a)
    if n!=1: raise AssertionError(f"v45 {label}: expected 1 match; got {n}")
    return s.replace(a,b,1)

p=R/"xposed/hook/VdImeDisplayPin.kt"
s=p.read_text(encoding="utf-8")
s=once(s, "    private var v44ImeParentHook: XC_MethodHook.Unhook? = null",
'''    private var v44ImeParentHook: XC_MethodHook.Unhook? = null
    private var v45AttachHook: XC_MethodHook.Unhook? = null
    @Volatile private var v45AttachCount = 0
    @Volatile private var v45ParentCount = 0''',"new state")
s=once(s,"runCatching { v44HookImeParentChoice() }","runCatching { v45HookImeParentChoice() }","call")
s=once(s,"private fun v44HookImeParentChoice()","private fun v45HookImeParentChoice()","declaration")
s=once(s,
'''name == "computeImeParent" && parameterTypes.isEmpty() &&
                SurfaceControl::class.java.isAssignableFrom(returnType)''',
'''name == "computeImeParent" && parameterTypes.isEmpty()''',"signature")
s=once(s,
'v44HookStatus = "computeImeParent-missing"',
'v44HookStatus = "v45-computeImeParent-missing"',"status")
s=once(s,
'log(TAG, "v44 computeImeParent unavailable; no repair possible")',
'log(TAG, "v45 computeImeParent unavailable; no repair possible")',"no method log")
s=once(s,
'''        v44ImeParentHook = method.hookAfter { param ->''',
'''        // Android16: disable app-attached IME in AA pane only, allowing WM's
        // regular updateImeParent + relative-layer transactions to place it.
        val attachMethod = AndroidHook.findSystemMethod(
            "com.android.server.wm.DisplayContent", findSuper = true,
        ) {
            name == "shouldImeAttachedToApp" && parameterTypes.isEmpty() &&
                returnType == Boolean::class.javaPrimitiveType
        }
        attachMethod?.let { methodAttach ->
            v45AttachHook = methodAttach.hookAfter { param ->
                try {
                    if (!v41Enabled("debug.carplay.v45_ime_parent_policy")) return@hookAfter
                    if (param.result != true) return@hookAfter
                    if (!CoreManagerService.hasAaVirtualDisplays()) return@hookAfter
                    val dc = param.thisObject
                    val id = displayIdOfDisplayContent(dc) ?: return@hookAfter
                    if (!CoreManagerService.isAaVirtualDisplay(id)) return@hookAfter
                    val container = findField(dc.javaClass, "mImeWindowsContainer")
                        ?.get(dc) ?: return@hookAfter
                    if (v41Call(container, "isOrganized") != false) return@hookAfter
                    if (findField(dc.javaClass, "mInputMethodWindow")?.get(dc) == null)
                        return@hookAfter
                    param.result = false
                    v45AttachCount++
                    if (v45AttachCount == 1 || v45AttachCount % 30 == 0)
                        log(TAG, "v45 app-attached IME disabled VD=" + id +
                            " count=" + v45AttachCount)
                } catch (t: Throwable) {
                    log(TAG, "v45 app attach callback error", t)
                }
            }
        }
        log(TAG, "v45 discovered computeImeParent(): " +
            method.returnType.name + " attachHook=" + (v45AttachHook != null))
        v44ImeParentHook = method.hookAfter { param ->''',"attachment hook")
s=once(s,'val observe = v41Enabled("debug.carplay.v44_ime_diag")','val observe = v41Enabled("debug.carplay.v45_ime_diag")',"diag option callback")
s=once(s,
'''                val repair = v41Enabled("debug.carplay.v44_ime_parent_policy")
                if (!observe && !repair) return@hookAfter''',
'''                val repair = v41Enabled("debug.carplay.v45_ime_parent_policy")
                if (!observe && !repair) return@hookAfter''',"policy option callback")
s=once(s,
'''                val selected = param.result as? SurfaceControl''',
'''                val selected = param.result
                val selectedSurface = if (selected is SurfaceControl) selected
                    else selected?.let { v28SurfaceOf(it) }
                val isSurfaceReturn =
                    SurfaceControl::class.java.isAssignableFrom(method.returnType)
                val replacement: Any? = if (isSurfaceReturn) expected
                    else if (parent != null && method.returnType.isInstance(parent)) parent
                    else null
                val appAttached = if (isSurfaceReturn)
                    selectedSurface !== expected
                    else selected?.javaClass?.name?.contains("ActivityRecord") == true''',
"return-aware parent")
s=once(s,
'''                val canRepair = imeWindow != null && !organized &&
                    selected?.isValid == true && expected?.isValid == true &&
                    selected !== expected''',
'''                val canRepair = imeWindow != null && !organized &&
                    selectedSurface?.isValid == true && expected?.isValid == true &&
                    appAttached && replacement != null && selected !== replacement''',
"safe validation")
start=s.index('                val summary = "display=$id hasWindow=')
end=s.index('                val now = android.os.SystemClock.uptimeMillis()',start)
s=s[:start]+'''                val summary = "display=" + id +
                    " returnType=" + method.returnType.simpleName +
                    " originalType=" + selected?.javaClass?.simpleName +
                    " nativeParent=" + parent?.javaClass?.simpleName +
                    " organized=" + organized + " appAttached=" + appAttached +
                    " hasIme=" + (imeWindow != null) + " canRepair=" + canRepair
'''+s[end:]
s=once(s,'log(TAG, "v44 IME parent decision $summary " +','log(TAG, "v45 IME parent decision $summary " +',"decision tag")
s=once(s,'param.result = expected','param.result = replacement\n                    v45ParentCount++',"correct parent typed")
s=once(s,'log(TAG, "v44 selected display-area IME parent for VD=$id; " +',
       'log(TAG, "v45 selected display-area IME parent for VD=$id; " +',"correction log")
s=once(s,
'''        v44HookStatus = "hooked"
        log(TAG, "v44 IME parent choice installed (experiment OFF by default)")''',
'''        v44HookStatus = "v45 parentReturn=" + method.returnType.name +
            " parentHook=true attachHook=" + (v45AttachHook != null)
        log(TAG, "v45 IME parent choice installed " + v44HookStatus +
            " (experiment OFF by default)")''',"installed log")
s=once(s,'fun v44ReportState(source: String)','fun v45ReportState(source: String)',"report function")
s=once(s,
'''        val diag = v41Enabled("debug.carplay.v44_ime_diag")
        val repair = v41Enabled("debug.carplay.v44_ime_parent_policy")''',
'''        val diag = v41Enabled("debug.carplay.v45_ime_diag")
        val repair = v41Enabled("debug.carplay.v45_ime_parent_policy")''',"report options")
s=once(s,'log(TAG, "v44 runtime source=$source hookStatus=$v44HookStatus " +',
       'log(TAG, "v45 runtime source=$source hookStatus=$v44HookStatus " +',"runtime tag")
s=once(s,
'''            "legacyRepair=''', 
'''            "attachBlocked=" + v45AttachCount + " parentCorrected=" +
                v45ParentCount + " legacyRepair=''', "counters")
s=once(s,
'''        val repair = v41Enabled("debug.carplay.v41_ime_reparent") &&
            !v41Enabled("debug.carplay.v44_ime_parent_policy")''',
'''        val repair = v41Enabled("debug.carplay.v41_ime_reparent") &&
            !v41Enabled("debug.carplay.v44_ime_parent_policy") &&
            !v41Enabled("debug.carplay.v45_ime_parent_policy")''',"older reparent conflict")
core=R/"xposed/CoreManagerService.kt"
t=core.read_text(encoding="utf-8")
t=once(t,'VdImeDisplayPin.v44ReportState("CarPlay-live=$live")',
       'VdImeDisplayPin.v45ReportState("CarPlay-live=$live")',"session trace")
t=once(t,'"v44 IME status report failed"','"v45 IME status report failed"',"session log")
core.write_text(t,encoding="utf-8")
p.write_text(s,encoding="utf-8")
gradle=Path("aa-display/build.gradle.kts")
v=gradle.read_text(encoding="utf-8")
v=once(v,"versionCode = 3144","versionCode = 3145","code")
v=once(v,'versionName = "0.3#17.8-v44"','versionName = "0.3#17.8-v45"',"name")
gradle.write_text(v,encoding="utf-8")
print("v45: A13/A16 compatible IME parent + app-attached decision, default OFF")

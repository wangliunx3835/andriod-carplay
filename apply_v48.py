#!/usr/bin/env python3
"""v48 after v47: scoped native IME parent timing repair, read-only leash audit."""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(s,a,b,tag):
    n=s.count(a)
    if n!=1: raise AssertionError("v48 "+tag+" count "+str(n))
    return s.replace(a,b,1)
f=R/"xposed/hook/VdImeDisplayPin.kt"
s=f.read_text(encoding="utf-8")
s=one(s,"    @Volatile private var v45ParentCount = 0",
"""    @Volatile private var v45ParentCount = 0
    private var v48UpdateHook: XC_MethodHook.Unhook? = null
    private var v48LeashHook: XC_MethodHook.Unhook? = null
    @Volatile private var v48AttachCalls = 0
    @Volatile private var v48Changed = 0
    @Volatile private var v48UpdateCalls = 0
    @Volatile private var v48LeashCalls = 0
    @Volatile private var v48LastStatusMs = 0L
    @Volatile private var v48Status = "not-attempted" ""","state")
start=s.index('                    if (!v41Enabled("debug.carplay.v45_ime_parent_policy")) return@hookAfter')
end=s.index('                } catch (t: Throwable) {',start)
old=s[start:end]
assert "v45AttachCount++" in old
new=r'''                    val diag = v41Enabled("debug.carplay.v48_ime_diag")
                    val repair = v41Enabled("debug.carplay.v48_ime_display_area")
                    val oldRepair = v41Enabled("debug.carplay.v45_ime_parent_policy") && !repair
                    if (!diag && !repair && !oldRepair) return@hookAfter
                    if (!CoreManagerService.hasAaVirtualDisplays()) return@hookAfter
                    val dc = param.thisObject
                    val id = displayIdOfDisplayContent(dc) ?: return@hookAfter
                    if (!CoreManagerService.isAaVirtualDisplay(id)) return@hookAfter
                    val container = findField(dc.javaClass, "mImeWindowsContainer")
                        ?.get(dc) ?: return@hookAfter
                    val organized = v41Call(container, "isOrganized")
                    val imeExists = findField(dc.javaClass, "mInputMethodWindow")?.get(dc) != null
                    val wasAttached = param.result
                    v48AttachCalls++
                    if (diag && (v48AttachCalls <= 20 || v48AttachCalls % 40 == 0))
                        log(TAG, "v48 attachDecision display=$id original=$wasAttached " +
                            "organized=$organized imeExists=$imeExists " +
                            "calls=$v48AttachCalls changed=$v48Changed")
                    if (wasAttached != true || organized != false) return@hookAfter
                    // No mInputMethodWindow gate for v48: WM can choose its
                    // parent before the IME window has been created.
                    if (repair) {
                        param.result = false
                        v48Changed++
                        if (v48Changed <= 20 || v48Changed % 40 == 0)
                            log(TAG, "v48 display-area decision display=$id " +
                                "imeExists=$imeExists changed=$v48Changed")
                    } else if (oldRepair && imeExists) {
                        param.result = false
                        v45AttachCount++
                    }
'''
s=s[:start]+new+s[end:]
anchor="    private fun v45HookImeParentChoice() {"
addition=r'''    private fun v48InstallDiagnostics() {
        val update = AndroidHook.findSystemMethod(
            "com.android.server.wm.DisplayContent", findSuper = true
        ) { name == "updateImeParent" && parameterTypes.isEmpty() }
        if (update != null) {
            v48UpdateHook = update.hookAfter { param ->
                try {
                    if (!v41Enabled("debug.carplay.v48_ime_diag") &&
                        !v41Enabled("debug.carplay.v48_ime_display_area")) return@hookAfter
                    val dc = param.thisObject
                    val id = displayIdOfDisplayContent(dc) ?: return@hookAfter
                    if (!CoreManagerService.isAaVirtualDisplay(id)) return@hookAfter
                    v48UpdateCalls++
                    if (v48UpdateCalls > 20 && v48UpdateCalls % 50 != 0) return@hookAfter
                    val parent = findField(dc.javaClass,
                        "mInputMethodSurfaceParentWindow")?.get(dc)
                    val container = findField(dc.javaClass, "mImeWindowsContainer")?.get(dc)
                    val organized = container?.let { v41Call(it, "isOrganized") }
                    log(TAG, "v48 nativeUpdate display=$id " +
                        "parent=" + (parent?.javaClass?.simpleName ?: "null") +
                        " organized=$organized calls=$v48UpdateCalls")
                } catch (t: Throwable) {
                    log(TAG, "v48 update diagnostic failed", t)
                }
            }
        }
        val post = AndroidHook.findSystemMethod(
            "com.android.server.wm.ImeInsetsSourceProvider", findSuper = true
        ) { name == "onPostLayout" && parameterTypes.isEmpty() }
        if (post != null) {
            v48LeashHook = post.hookAfter { param ->
                try {
                    if (!v41Enabled("debug.carplay.v48_leash_diag")) return@hookAfter
                    val provider = param.thisObject
                    val dc = findField(provider.javaClass, "mDisplayContent")
                        ?.get(provider) ?: return@hookAfter
                    val id = displayIdOfDisplayContent(dc) ?: return@hookAfter
                    if (!CoreManagerService.isAaVirtualDisplay(id)) return@hookAfter
                    v48LeashCalls++
                    if (v48LeashCalls > 12 && v48LeashCalls % 80 != 0) return@hookAfter
                    val ready = findField(provider.javaClass, "mGivenInsetsReady")
                        ?.get(provider)
                    val control = v41Call(provider, "getControl")
                    log(TAG, "v48 leash display=$id ready=$ready " +
                        "controlFound=" + (control != null) +
                        " calls=$v48LeashCalls")
                } catch (t: Throwable) {
                    log(TAG, "v48 leash diagnostic failed", t)
                }
            }
        }
        v48Status = "update=" + (v48UpdateHook != null) +
            " provider=" + (v48LeashHook != null)
        log(TAG, "v48 diagnostic hook installed $v48Status (default OFF)")
    }

    fun v48ReportState(source: String) {
        if (!v41Enabled("debug.carplay.v48_ime_diag") &&
            !v41Enabled("debug.carplay.v48_ime_display_area") &&
            !v41Enabled("debug.carplay.v48_leash_diag")) return
        val now = android.os.SystemClock.uptimeMillis()
        if (now - v48LastStatusMs < 7000L) return
        v48LastStatusMs = now
        log(TAG, "v48 runtime source=$source status=$v48Status " +
            "attachHook=" + (v45AttachHook != null) +
            " attachCalls=$v48AttachCalls changed=$v48Changed " +
            "updates=$v48UpdateCalls leashEvents=$v48LeashCalls")
    }

'''
s=one(s,anchor,addition+anchor,"code")
s=one(s,'''        runCatching { v47HookImeNoFullscreen() }''',
'''        runCatching { v48InstallDiagnostics() }
            .onFailure { log(TAG, "v48 diagnostic install failed", it) }
        runCatching { v47HookImeNoFullscreen() }''',"install")
f.write_text(s,encoding="utf-8")
c=R/"xposed/CoreManagerService.kt"
t=c.read_text(encoding="utf-8")
a='''        runCatching { VdImeDisplayPin.v45ReportState("CarPlay-live=$live") }
            .onFailure { log(TAG, "v45 IME status report failed", it) }'''
t=one(t,a,a+'''
        runCatching { VdImeDisplayPin.v48ReportState("CarPlay-live=$live") }
            .onFailure { log(TAG, "v48 IME status report failed", it) }''',"report")
c.write_text(t,encoding="utf-8")
g=Path("aa-display/build.gradle.kts")
v=g.read_text(encoding="utf-8")
v=one(v,"versionCode = 3147","versionCode = 3148","code")
v=one(v,'versionName = "0.3#17.8-v47"','versionName = "0.3#17.8-v48"',"name")
g.write_text(v,encoding="utf-8")
print("v48: native IME area-parent timing test and leash diagnostics, default OFF")

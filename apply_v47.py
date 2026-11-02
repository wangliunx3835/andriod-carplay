#!/usr/bin/env python3
"""v47: no v46 single-VD patch; opt-in NO_FULLSCREEN for AA pane input clients.
Apply DIRECTLY AFTER v45. Avoids global IME properties, Greezer and Surfaces.
"""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(s,a,b,tag):
    n=s.count(a)
    if n!=1: raise AssertionError(f"v47 {tag}: expected one match, got {n}")
    return s.replace(a,b,1)

p=R/"xposed/hook/VdImeDisplayPin.kt"
s=p.read_text(encoding="utf-8")
s=one(s,"import android.view.Display","import android.view.Display\nimport android.view.inputmethod.EditorInfo","EditorInfo import")
s=one(s,"import com.github.kyuubiran.ezxhelper.utils.hookAfter",
"import com.github.kyuubiran.ezxhelper.utils.hookAfter\nimport com.github.kyuubiran.ezxhelper.utils.hookBefore","hookBefore import")
s=one(s,"    private var v45AttachHook: XC_MethodHook.Unhook? = null",
'''    private var v45AttachHook: XC_MethodHook.Unhook? = null
    private var v47InputFlagHook: XC_MethodHook.Unhook? = null
    @Volatile private var v47FlagCalls = 0
    @Volatile private var v47FlagChanges = 0
    @Volatile private var v47Status = "not-installed"''',"state")
s=one(s,"        runCatching { v45HookImeParentChoice() }",
'''        runCatching { v47HookImeNoFullscreen() }
            .onFailure {
                v47Status = "install-failed:" + it.javaClass.simpleName
                log(TAG, "v47 hook installation failed", it)
            }
        runCatching { v45HookImeParentChoice() }''',"install")

logic=r'''    /**
     * AOSP InputMethodService.onComputeInsets() intentionally sets
     * contentTopInsets to decorHeight when fullscreen, producing zero-height
     * InsetsSource. This is not by itself a clipping defect.
     *
     * Change only the EditorInfo delivered for a live AA pane VD client:
     * IME_FLAG_NO_FULLSCREEN requests non-extract mode from a compliant IME.
     * Preserve normal physical display 0 and non-AA external display input.
     * OFF by default and no additional Gboard LSPosed scope needed.
     */
    private fun v47HookImeNoFullscreen() {
        val method = AndroidHook.findSystemMethod(IMMS, findSuper = true) {
            name == "startInputUncheckedLocked" &&
                parameterTypes.any { EditorInfo::class.java.isAssignableFrom(it) } &&
                parameterTypes.any { it.simpleName == "ClientState" ||
                    it.name.endsWith("$" + "ClientState") }
        }
        if (method == null) {
            v47Status = "startInputUncheckedLocked-not-found"
            log(TAG, "v47 input flag method missing; no modification possible")
            return
        }
        val editorIndex = method.parameterTypes.indexOfFirst {
            EditorInfo::class.java.isAssignableFrom(it)
        }
        val clientIndex = method.parameterTypes.indexOfFirst {
            it.simpleName == "ClientState" || it.name.endsWith("$" + "ClientState")
        }
        if (editorIndex < 0 || clientIndex < 0) {
            v47Status = "argument-index-invalid"
            log(TAG, "v47 signature missing required arguments")
            return
        }
        v47InputFlagHook = method.hookBefore { param ->
            try {
                if (!CoreManagerService.hasAaVirtualDisplays()) return@hookBefore
                val observe = v41Enabled("debug.carplay.v47_ime_diag")
                val repair = v41Enabled("debug.carplay.v47_ime_no_fullscreen")
                if (!observe && !repair) return@hookBefore
                val client = param.args.getOrNull(clientIndex) ?: return@hookBefore
                val id = runCatching {
                    findField(client.javaClass, "mSelfReportedDisplayId")?.getInt(client)
                }.getOrNull()
                if (id == null) {
                    log(TAG, "v47 client display unavailable; no modification")
                    return@hookBefore
                }
                if (!CoreManagerService.isAaVirtualDisplay(id)) return@hookBefore
                val editor = param.args.getOrNull(editorIndex) as? EditorInfo
                    ?: return@hookBefore
                val before = editor.imeOptions
                v47FlagCalls++
                if (repair && before and EditorInfo.IME_FLAG_NO_FULLSCREEN == 0) {
                    editor.imeOptions = before or EditorInfo.IME_FLAG_NO_FULLSCREEN
                    v47FlagChanges++
                }
                if (v47FlagCalls <= 10 || v47FlagCalls % 40 == 0) {
                    log(TAG, "v47 startInput display=" + id +
                        " mode=" + (if (repair) "REPAIR" else "OBSERVE") +
                        " before=0x" + Integer.toHexString(before) +
                        " after=0x" + Integer.toHexString(editor.imeOptions) +
                        " calls=" + v47FlagCalls +
                        " changes=" + v47FlagChanges)
                }
            } catch (t: Throwable) {
                log(TAG, "v47 input flag callback error", t)
            }
        }
        v47Status = "hooked startInputUncheckedLocked editorIndex=" + editorIndex +
            " clientIndex=" + clientIndex
        log(TAG, "v47 IME flag hook installed: " + v47Status +
            " (OFF by default)")
    }

'''
s=one(s,"    private fun v45HookImeParentChoice() {",
    logic+"    private fun v45HookImeParentChoice() {","IME flag hook")
p.write_text(s,encoding="utf-8")

g=Path("aa-display/build.gradle.kts")
v=g.read_text(encoding="utf-8")
v=one(v,"versionCode = 3145","versionCode = 3147","versionCode")
v=one(v,'versionName = "0.3#17.8-v45"','versionName = "0.3#17.8-v47"',"versionName")
g.write_text(v,encoding="utf-8")
print("v47: dual-VD v45 baseline restored; opt-in NO_FULLSCREEN for AA client")

#!/usr/bin/env python3
"""v50: opt-in live IME mirror + HU MainScreen conditional video gate; after v49."""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise AssertionError(f"v50 {label}: {n} matches")
    return s.replace(a,b,1)

p=R/"xposed/hook/VdImeDisplayPin.kt"
s=p.read_text(encoding="utf-8")
s=one(s,'    @Volatile private var v49AttachEntryCalls = 0',
'''    @Volatile private var v49AttachEntryCalls = 0
    private val v50MirrorLock = Any()
    private val v50MirrorByDisplay = mutableMapOf<Int, Pair<SurfaceControl, SurfaceControl>>()
    private var v50MirrorUpdateHook: XC_MethodHook.Unhook? = null
    private var v50MirrorTargetHook: XC_MethodHook.Unhook? = null''',"state")
code=r'''    /** Reuse screenshot's activity parent, without moving original IME. Default OFF. */
    private fun v50RemoveMirrorLocked(id: Int, why: String) {
        val old = v50MirrorByDisplay.remove(id) ?: return
        runCatching {
            SurfaceControl.Transaction().use { tx ->
                tx.remove(old.second)
                tx.apply()
            }
        }.onFailure { log(TAG, "v50 mirror remove failed display=$id", it) }
        runCatching { old.second.release() }
        log(TAG, "v50 mirror removed display=$id reason=$why")
    }

    private fun v50ClearMirrors(why: String) {
        synchronized(v50MirrorLock) {
            v50MirrorByDisplay.keys.toList().forEach { v50RemoveMirrorLocked(it, why) }
        }
    }

    private fun v50SyncMirror(dc: Any, event: String) {
        val id = displayIdOfDisplayContent(dc) ?: return
        if (!CoreManagerService.isAaVirtualDisplay(id)) return
        synchronized(v50MirrorLock) {
            if (!v41Enabled("debug.carplay.v50_ime_mirror")) {
                v50RemoveMirrorLocked(id, "disabled")
                return
            }
            val ime = findField(dc.javaClass, "mInputMethodWindow")?.get(dc)
            if (ime == null || !v41ImeVisible(ime)) {
                v50RemoveMirrorLocked(id, "ime-hidden")
                return
            }
            val target = findField(dc.javaClass, "mImeLayeringTarget")?.get(dc)
            if (target == null) {
                v50RemoveMirrorLocked(id, "target-absent")
                return
            }
            val activity = findField(target.javaClass, "mActivityRecord")?.get(target)
            if (activity == null) {
                v50RemoveMirrorLocked(id, "activity-absent")
                return
            }
            val attrs = findField(ime.javaClass, "mAttrs")?.get(ime)
                as? android.view.WindowManager.LayoutParams
            val targetAttrs = findField(target.javaClass, "mAttrs")?.get(target)
                as? android.view.WindowManager.LayoutParams
            if (attrs == null || targetAttrs == null ||
                attrs.flags and android.view.WindowManager.LayoutParams.FLAG_SECURE != 0 ||
                targetAttrs.flags and android.view.WindowManager.LayoutParams.FLAG_SECURE != 0) {
                v50RemoveMirrorLocked(id, "secure-or-unknown")
                return
            }
            val source = v28SurfaceOf(ime)
            val parent = v28SurfaceOf(activity)
            if (source?.isValid != true || parent?.isValid != true) return
            val prev = v50MirrorByDisplay[id]
            if (prev?.first === source && prev?.second?.isValid == true) return
            v50RemoveMirrorLocked(id, "source-changed")
            var mirror: SurfaceControl? = null
            try {
                mirror = SurfaceControl.mirrorSurface(source)
                if (mirror.isValid != true) {
                    mirror?.release()
                    return
                }
                SurfaceControl.Transaction().use { tx ->
                    tx.reparent(mirror, parent)
                    tx.setLayer(mirror, 1)
                    val frame = v41Call(ime, "getFrame") as? android.graphics.Rect
                    if (frame != null) {
                        tx.setPosition(mirror, frame.left.toFloat(), frame.top.toFloat())
                    }
                    tx.show(mirror)
                    tx.apply()
                }
                v50MirrorByDisplay[id] = Pair(source, mirror)
                log(TAG, "v50 mirror created display=$id event=$event parent=ActivityRecord")
            } catch (t: Throwable) {
                runCatching { mirror?.release() }
                log(TAG, "v50 mirror failed display=$id event=$event", t)
            }
        }
    }

    private fun v50InstallMirrorHooks() {
        val update = AndroidHook.findSystemMethod(
            "com.android.server.wm.DisplayContent", findSuper = true
        ) { name == "updateImeParent" && parameterTypes.isEmpty() }
        if (update != null) {
            v50MirrorUpdateHook = update.hookAfter { param ->
                runCatching { v50SyncMirror(param.thisObject, "updateImeParent") }
                    .onFailure { log(TAG, "v50 mirror update callback failed", it) }
            }
        }
        val target = AndroidHook.findSystemMethod(
            "com.android.server.wm.DisplayContent", findSuper = true
        ) { name == "setImeLayeringTarget" && parameterTypes.size == 1 }
        if (target != null) {
            v50MirrorTargetHook = target.hookAfter { param ->
                runCatching { v50SyncMirror(param.thisObject, "setImeLayeringTarget") }
                    .onFailure { log(TAG, "v50 mirror target callback failed", it) }
            }
        }
        log(TAG, "v50 mirror hooks update=" + (v50MirrorUpdateHook != null) +
            " target=" + (v50MirrorTargetHook != null) + " (default OFF)")
    }

'''
s=one(s,'    private fun v48InstallDiagnostics() {',code+'    private fun v48InstallDiagnostics() {',"mirror body")
s=one(s,'        runCatching { v48InstallDiagnostics() }',
'''        runCatching { v50InstallMirrorHooks() }
            .onFailure { log(TAG, "v50 mirror hook install failed", it) }
        runCatching { v48InstallDiagnostics() }''',"install")
s=one(s,'    fun onAaDisplaysInactive(context: Context) {',
'''    fun onAaDisplaysInactive(context: Context) {
        v50ClearMirrors("displays-inactive")''',"cleanup")
p.write_text(s,encoding="utf-8")

p=R/"carplay/CarPlayRtspSession.kt"
s=p.read_text(encoding="utf-8")
s=one(s,'    private val screenEgress = AtomicReference<ScreenStreamEgress?>(null)',
'''    private val screenEgress = AtomicReference<ScreenStreamEgress?>(null)
    private val v50ReverseGate = CarPlayV50Options.reverseGate()
    private val v50ReverseTrace = CarPlayV50Options.reverseTrace()
    private var v50BorrowedLast = false
    private var v50SkippedFrames = 0L
    private var v50ReverseReadyLogged = false''',"screen state")
s=one(s,'''        if (!streaming.get()) return 0
        val screen = screenEgress.get()
''',
'''        if (!streaming.get()) return 0
        // Honor HU's authenticated MainScreen BORROW/TAKE; audio/RTSP unaffected.
        // Default OFF because some HU receivers reset silent video TCP.
        val huOwnsMainScreen = eventChannel.get()?.isPhoneOwningMainScreen() == false
        if (!v50ReverseReadyLogged && v50ReverseTrace) {
            v50ReverseReadyLogged = true
            Log.i(CarPlayConsts.TAG, "v50 reverse monitor gate=$v50ReverseGate " +
                "hasEventChannel=" + (eventChannel.get() != null))
        }
        if (huOwnsMainScreen != v50BorrowedLast) {
            Log.i(CarPlayConsts.TAG, "v50 MainScreen owner changed hu=$huOwnsMainScreen " +
                "gate=$v50ReverseGate skipped=$v50SkippedFrames")
            v50BorrowedLast = huOwnsMainScreen
            if (!huOwnsMainScreen && v50ReverseGate) onForceKeyFrame()
        }
        if (v50ReverseGate && huOwnsMainScreen) {
            v50SkippedFrames++
            if (v50SkippedFrames == 1L || v50SkippedFrames % 300L == 0L) {
                Log.i(CarPlayConsts.TAG,
                    "v50 video suppressed while HU owns MainScreen total=$v50SkippedFrames")
            }
            return 0
        }
        val screen = screenEgress.get()
''',"send gate")
p.write_text(s,encoding="utf-8")
opt=R/"carplay/CarPlayV50Options.kt"
if opt.exists(): raise AssertionError("v50 options already exist")
opt.write_text('''package io.github.nitsuya.aa.display.carplay

/** Read once per RTSP object creation; defaults OFF to protect v39 session. */
internal object CarPlayV50Options {
    private fun enabled(key: String): Boolean = runCatching {
        val p = Class.forName("android.os.SystemProperties")
        p.getMethod("getBoolean", String::class.java, Boolean::class.javaPrimitiveType)
            .invoke(null, key, false) == true
    }.getOrDefault(false)
    fun reverseGate() = enabled("debug.carplay.v50_reverse_video_gate")
    fun reverseTrace() = enabled("debug.carplay.v50_reverse_trace")
}
''',encoding="utf-8")
g=Path("aa-display/build.gradle.kts");v=g.read_text(encoding="utf-8")
v=one(v,"versionCode = 3149","versionCode = 3150","versionCode")
v=one(v,'versionName = "0.3#17.8-v49"','versionName = "0.3#17.8-v50"',"versionName")
g.write_text(v,encoding="utf-8")
print("v50: opt-in live IME mirror and HU MainScreen conditional video suppression")

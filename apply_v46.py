#!/usr/bin/env python3
"""v46 A/B: real single VirtualDisplay and optional original 0x0 window.
Run after v45. Off by default; preserves CarPlay networking and all v45 code.
"""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(s,a,b,tag):
    n=s.count(a)
    if n!=1: raise AssertionError(f"v46 {tag} expected 1 got {n} needle={a[:90]!r}")
    return s.replace(a,b,1)
def edit(p,items):
    f=R/p
    s=f.read_text(encoding="utf-8")
    for tag,a,b in items: s=one(s,a,b,tag)
    f.write_text(s,encoding="utf-8")

f=R/"util/V46Mode.kt"
if f.exists(): raise AssertionError("v46 mode already exists")
f.write_text(r'''package io.github.nitsuya.aa.display.util

/** Per-process session snapshot. Set flags BEFORE CarPlay starts. */
object V46Mode {
    @Volatile var single: Boolean = false
        private set
    @Volatile var anchor: Boolean = false
        private set

    fun refresh() {
        fun read(key: String): Boolean = runCatching {
            val c = Class.forName("android.os.SystemProperties")
            val m = c.getMethod("get", String::class.java, String::class.java)
            m.invoke(null, key, "0") == "1"
        }.getOrDefault(false)
        single = read("debug.carplay.v46_single_vd")
        anchor = single && read("debug.carplay.v46_anchor_window")
        android.util.Log.i("AAD_V46Mode", "single=" + single +
            " anchor=" + anchor + " pid=" + android.os.Process.myPid())
    }
}
''',encoding="utf-8")

edit("ui/aa/split/SplitVdLifecycle.kt",[
("import",'import android.content.Context','import android.content.Context\nimport io.github.nitsuya.aa.display.util.V46Mode'),
("null-secondary",'''        val primary = c.mPrimary ?: return
        val secondary = c.mSecondary ?: return
        val sizes = computePaneSizes()''','''        val primary = c.mPrimary ?: return
        val secondary = c.mSecondary
        if (secondary == null && !V46Mode.single) return
        val sizes = computePaneSizes()'''),
("optional-secondary-resize",'''            if (secondaryChanged || reason == "reconnect") {
                secondary.resize(sizes.secondaryW, sizes.secondaryH, c.mDensityDpi)''','''            if (secondary != null && (secondaryChanged || reason == "reconnect")) {
                secondary.resize(sizes.secondaryW, sizes.secondaryH, c.mDensityDpi)''')
])

anchor=r'''    // Optional original-Nitsuya-style 0x0 transparent, non-focusable window.
    private var v46WindowManager: android.view.WindowManager? = null
    private var v46WindowView: android.view.View? = null

    private fun v46InstallAnchor() {
        if (!V46Mode.single || !V46Mode.anchor || v46WindowView != null) return
        val display = mPrimary?.display ?: return
        try {
            val ctx = context.createDisplayContext(display).createWindowContext(
                display, android.view.WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, null
            )
            val wm = ctx.getSystemService(android.view.WindowManager::class.java)
                ?: throw IllegalStateException("window service unavailable")
            val view = android.view.View(ctx)
            val flags = android.view.WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                android.view.WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
            val lp = android.view.WindowManager.LayoutParams(0, 0,
                android.view.WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                flags, android.graphics.PixelFormat.TRANSPARENT).apply {
                gravity = android.view.Gravity.TOP or android.view.Gravity.LEFT
                screenOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
                alpha = 0f
            }
            wm.addView(view, lp)
            v46WindowManager = wm
            v46WindowView = view
            log(TAG, "v46 original 0x0 anchor installed display=" + display.displayId)
        } catch (t: Throwable) {
            log(TAG, "v46 optional original anchor failed", t)
        }
    }

    private fun v46RemoveAnchor() {
        val view = v46WindowView
        val wm = v46WindowManager
        v46WindowView = null
        v46WindowManager = null
        if (view != null && wm != null) {
            try { wm.removeViewImmediate(view) }
            catch (t: Throwable) { log(TAG, "v46 anchor cleanup", t) }
        }
    }

'''
edit("ui/aa/split/SplitDisplayController.kt",[
("import","import android.hardware.display.VirtualDisplay","import android.hardware.display.VirtualDisplay\nimport io.github.nitsuya.aa.display.util.V46Mode"),
("anchor helper","    internal var mPrimary: VirtualDisplay? = null",anchor+"    internal var mPrimary: VirtualDisplay? = null"),
("startup mode",'''        mRatio = SplitPane.clampRatio(ratio)
        mFullscreenPane = SplitPane.FULLSCREEN_NONE''','''        V46Mode.refresh()
        mRatio = SplitPane.clampRatio(ratio)
        mFullscreenPane = if (V46Mode.single) SplitPane.PRIMARY else SplitPane.FULLSCREEN_NONE
        if (V46Mode.single) mFocusedPane = SplitPane.PRIMARY'''),
("second VD",'''            mSecondary = Instances.displayManager.createVirtualDisplay(
                "AADisplay-S-${System.currentTimeMillis()}",
                sizes.secondaryW, sizes.secondaryH, mDensityDpi,
                secondarySurface, flags
            )
            mCachedSecondaryDisplayId =
                mSecondary?.display?.displayId ?: Display.INVALID_DISPLAY''','''            if (V46Mode.single) {
                mSecondary = null
                mCachedSecondaryDisplayId = Display.INVALID_DISPLAY
            } else {
                mSecondary = Instances.displayManager.createVirtualDisplay(
                    "AADisplay-S-${System.currentTimeMillis()}",
                    sizes.secondaryW, sizes.secondaryH, mDensityDpi,
                    secondarySurface, flags
                )
                mCachedSecondaryDisplayId =
                    mSecondary?.display?.displayId ?: Display.INVALID_DISPLAY
            }'''),
("topology trace",'''        try {
            Instances.iActivityTaskManager.registerTaskStackListener(mTaskStackListener)''','''        log(TAG, "v46 topology realSingle=" + V46Mode.single +
            " primaryId=" + primaryDisplayId +
            " secondaryId=" + secondaryDisplayId +
            " primarySize=" + sizes.primaryW + "x" + sizes.primaryH)
        try {
            Instances.iActivityTaskManager.registerTaskStackListener(mTaskStackListener)'''),
("IME setup",'''            vd.applyPolicies(SplitPane.PRIMARY, "connect")
            vd.applyPolicies(SplitPane.SECONDARY, "connect")
            ime.start()''','''            vd.applyPolicies(SplitPane.PRIMARY, "connect")
            if (!V46Mode.single) vd.applyPolicies(SplitPane.SECONDARY, "connect")
            v46InstallAnchor()
            ime.start()'''),
("no restore",'''        if (launch.shouldRestoreLastSplitOnConnect()) {''','''        if (!V46Mode.single && launch.shouldRestoreLastSplitOnConnect()) {'''),
("no reconnect dual restore",'''        if (launch.shouldRestoreLastSplitOnConnect() && launch.bothPanesVacantOnDisplays()) {''','''        if (!V46Mode.single && launch.shouldRestoreLastSplitOnConnect() && launch.bothPanesVacantOnDisplays()) {'''),
("no resize ratio",'''    fun setSplitRatio(ratio: Float) {
        val clamped''','''    fun setSplitRatio(ratio: Float) {
        if (V46Mode.single) return
        val clamped'''),
("fixed fullscreen",'''    fun setSplitFullscreen(pane: Int) {
        if (pane != SplitPane.FULLSCREEN_NONE''','''    fun setSplitFullscreen(pane: Int) {
        if (V46Mode.single) return
        if (pane != SplitPane.FULLSCREEN_NONE'''),
("no secondary app",'''    fun startActivityOnPane(packageName: String, userId: Int, pane: Int): Boolean {
        // Same queue''','''    fun startActivityOnPane(packageName: String, userId: Int, pane: Int): Boolean {
        if (V46Mode.single && pane != SplitPane.PRIMARY) return false
        // Same queue'''),
("no secondary picker",'''    fun startActivityOnPaneForUser(packageName: String, userId: Int, pane: Int): Boolean {
        cancelBackgroundSettleForUserAction()''','''    fun startActivityOnPaneForUser(packageName: String, userId: Int, pane: Int): Boolean {
        if (V46Mode.single && pane != SplitPane.PRIMARY) return false
        cancelBackgroundSettleForUserAction()'''),
("cleanup anchor",'''        tryOrNull { mPrimary?.release() }''','''        v46RemoveAnchor()
        tryOrNull { mPrimary?.release() }''')
])

edit("ui/aa/split/SplitLaunchRestore.kt",[
("import",'import io.github.nitsuya.aa.display.util.LastSplitStore','import io.github.nitsuya.aa.display.util.LastSplitStore\nimport io.github.nitsuya.aa.display.util.V46Mode'),
("skip-dual-restore",'''    fun shouldRestoreLastSplitOnConnect(): Boolean {
        // Always on''','''    fun shouldRestoreLastSplitOnConnect(): Boolean {
        if (V46Mode.single) return false
        // Always on'''),
("skip-dual-backfill",'''    private fun backfillVacantPanesFromSnapshot(reason: String) {
        val snap''','''    private fun backfillVacantPanesFromSnapshot(reason: String) {
        if (V46Mode.single) return
        val snap'''),
("preserve-ratio",'''    fun persistRatioNow() {
        val ratio''','''    fun persistRatioNow() {
        if (V46Mode.single) return
        val ratio'''),
("preserve-dual-snapshot",'''    fun persistSnapshot(force: Boolean, logSettingsFailures: Boolean) {
        // On destroy''','''    fun persistSnapshot(force: Boolean, logSettingsFailures: Boolean) {
        if (V46Mode.single) return
        // On destroy''')
])

edit("carplay/CarPlayInputBridge.kt",[
("import",'import io.github.nitsuya.aa.display.ui.aa.split.SplitPane','import io.github.nitsuya.aa.display.ui.aa.split.SplitPane\nimport io.github.nitsuya.aa.display.util.V46Mode'),
("no-dividers",'''    private fun handleChrome(x: Float, y: Float, action: Int): Boolean {
        val fs''','''    private fun handleChrome(x: Float, y: Float, action: Int): Boolean {
        if (V46Mode.single) return false
        val fs'''),
("touch primary full",'''        val (pane, xPane, paneWidth) = if (SplitPane.isFullscreenPane(fs)) {''','''        val (pane, xPane, paneWidth) = if (V46Mode.single) {
            Triple(SplitPane.PRIMARY, xNorm.coerceIn(0f, 1f), w)
        } else if (SplitPane.isFullscreenPane(fs)) {''')
])
edit("carplay/CarPlayGlCompositor.kt",[
("import",'import android.graphics.SurfaceTexture','import android.graphics.SurfaceTexture\nimport io.github.nitsuya.aa.display.util.V46Mode'),
("full primary",'''        if (SplitPane.isFullscreenPane(fs) && CarPlayInputBridge.peelPreviewActive) {''','''        if (V46Mode.single) {
            applyPaneBufferSize(0, encodeWidth, encodeHeight)
            drawPane(0, 0, 0, encodeWidth, encodeHeight)
            seamX = -1
            chromeFullscreen = true
        } else if (SplitPane.isFullscreenPane(fs) && CarPlayInputBridge.peelPreviewActive) {'''),
("skip compositor chrome",'''        drawChromeLayer(seamX, chromeFullscreen)''','''        if (!V46Mode.single) drawChromeLayer(seamX, chromeFullscreen)''')
])
edit("carplay/CarPlayHostRuntime.kt",[
("import",'import io.github.nitsuya.aa.display.util.LastSplitStore','import io.github.nitsuya.aa.display.util.LastSplitStore\nimport io.github.nitsuya.aa.display.util.V46Mode'),
("host boot",'''            val dpi = resolveEncodeDpi()
            val paneW = (w / 2).coerceAtLeast(16)''','''            val dpi = resolveEncodeDpi()
            V46Mode.refresh()
            val paneW = (if (V46Mode.single) w else w / 2).coerceAtLeast(16)
            CarPlayInputBridge.fullscreenPane =
                if (V46Mode.single) SplitPane.PRIMARY else SplitPane.FULLSCREEN_NONE
            CarPlayInputBridge.peelPreviewActive = false'''),
("only primary app",'''            val snap = runCatching { LastSplitStore.load(ctx.contentResolver) }.getOrNull()
            snap?.primaryRatio?.let { r ->''','''            val snap = runCatching { LastSplitStore.load(ctx.contentResolver) }.getOrNull()
            if (V46Mode.single) {
                CarPlayInputBridge.fullscreenPane = SplitPane.PRIMARY
                val pkg = snap?.primaryPackage?.takeIf { it.isNotBlank() }
                    ?: "com.android.chrome"
                try {
                    if (CoreApi.getPanePackage(SplitPane.PRIMARY).isNullOrBlank()) {
                        CoreApi.startActivityOnPane(pkg, 0, SplitPane.PRIMARY)
                        Log.i(CarPlayConsts.TAG, "v46 single primary app=" + pkg)
                    }
                } catch (e: Throwable) {
                    Log.w(CarPlayConsts.TAG, "v46 single app launch failed", e)
                }
                return@postDelayed
            }
            snap?.primaryRatio?.let { r ->'''),
("full buffer",'''        gl.syncPaneBuffers(left, right, height)''','''        if (V46Mode.single) gl.syncPaneBuffers(width, width, height)
        else gl.syncPaneBuffers(left, right, height)''')
])
g=Path("aa-display/build.gradle.kts")
s=g.read_text(encoding="utf-8")
s=one(s,"versionCode = 3145","versionCode = 3146","versionCode")
s=one(s,'versionName = "0.3#17.8-v45"','versionName = "0.3#17.8-v46"',"versionName")
g.write_text(s,encoding="utf-8")
print("v46 applied: real single VD and optional Nitsuya 0x0 anchor; dual unchanged")

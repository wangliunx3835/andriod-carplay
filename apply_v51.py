#!/usr/bin/env python3
"""v51: default-on proven backup camera gate; app-death cleanup; audio recovery.
Apply after v50 on pinned upstream. Preserve v23/v39 and dual VDs.
"""
from pathlib import Path
ROOT=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(s,a,b,tag):
    n=s.count(a)
    if n!=1: raise AssertionError(f"v51 {tag}: expected 1 anchor, got {n}")
    return s.replace(a,b,1)
def edit(file,a,b,tag):
    src=file.read_text(encoding="utf-8")
    file.write_text(one(src,a,b,tag),encoding="utf-8")

# Make verified BORROW/UNBORROW video gate the DEFAULT, opt-out via prop 0.
f=ROOT/"carplay/CarPlayV50Options.kt"
edit(f,'    fun reverseGate() = enabled("debug.carplay.v50_reverse_video_gate")',
'''    // v51: stationary reverse tests verified proper MainScreen BORROW/UNBORROW.
    // Default active, debug.carplay.v50_reverse_video_gate=0 rolls back.
    fun reverseGate(): Boolean = runCatching {
        val props = Class.forName("android.os.SystemProperties")
        val get = props.getMethod("get", String::class.java, String::class.java)
        (get.invoke(null, "debug.carplay.v50_reverse_video_gate", "1") as? String) != "0"
    }.getOrDefault(true)''',"reverse default")

# App owner exists in the app process, so system_server is notified on process death.
aidl=Path("aa-display/src/main/aidl/io/github/nitsuya/aa/display/xposed/ICoreManager.aidl")
edit(aidl,'    void preferCellularOverUnvalidatedWifi();\n}',
'''    void preferCellularOverUnvalidatedWifi();

    /** v51: process-local Binder token; lets system_server restore mute on app death. */
    void registerCarPlayOwner(IVirtualDisplayCreatedListener owner);
}''',"AIDL append owner token")

mgr=ROOT/"xposed/CoreManager.kt"
edit(mgr,'    override fun reportCarPlaySessionLive(live: Boolean) {',
'''    override fun registerCarPlayOwner(owner: IVirtualDisplayCreatedListener) {
        try {
            getService()?.registerCarPlayOwner(owner)
        } catch (t: Throwable) {
            Log.e(TAG, "v51 registerCarPlayOwner failed", t)
        }
    }

    override fun reportCarPlaySessionLive(live: Boolean) {''',"CoreManager owner forwarding")

service=ROOT/"xposed/CoreManagerService.kt"
s=service.read_text(encoding="utf-8")
s=one(s,'    private var coolwalkReconnectEpochMs = 0L',
'''    private var coolwalkReconnectEpochMs = 0L
    private val v51OwnerLock = Any()
    private var v51OwnerBinder: android.os.IBinder? = null
    private var v51OwnerDeath: android.os.IBinder.DeathRecipient? = null

    override fun registerCarPlayOwner(owner: IVirtualDisplayCreatedListener) {
        val token = owner.asBinder()
        synchronized(v51OwnerLock) {
            if (v51OwnerBinder === token) return
            v51ClearOwnerLocked()
            val death = object : android.os.IBinder.DeathRecipient {
                override fun binderDied() {
                    // Death callback comes on a Binder pool thread. Clear only
                    // if this is still the active owner (new connection may exist).
                    runMain {
                        synchronized(v51OwnerLock) {
                            if (v51OwnerBinder !== token) return@runMain
                            v51OwnerBinder = null
                            v51OwnerDeath = null
                        }
                        log(TAG, "v51 CarPlay app binder died: restore audio and VDs")
                        reportCarPlaySessionLive(false)
                        // No 180 s Delay Destroy for crashed clients.
                        runCatching { mSessionPolicy?.onDestroyPromptly() }
                            .onFailure { log(TAG, "v51 policy death cleanup failed", it) }
                        runCatching { mSplitController?.onDestroy() }
                            .onFailure { log(TAG, "v51 VD death cleanup failed", it) }
                        mSplitController = null
                        mSessionPolicy = null
                        mDisplayCreateInProgress = false
                        clearDisplayProfileLock()
                        if (hasSystemContext) {
                            runCatching { VdImeDisplayPin.onAaDisplaysInactive(systemContext) }
                        }
                    }
                }
            }
            try {
                token.linkToDeath(death, 0)
                v51OwnerBinder = token
                v51OwnerDeath = death
                log(TAG, "v51 registered CarPlay process death recipient")
            } catch (t: Throwable) {
                log(TAG, "v51 owner already dead", t)
                runMain { reportCarPlaySessionLive(false) }
            }
        }
    }

    private fun v51ClearOwnerLocked() {
        val old = v51OwnerBinder
        val death = v51OwnerDeath
        v51OwnerBinder = null
        v51OwnerDeath = null
        if (old != null && death != null) {
            runCatching { old.unlinkToDeath(death, 0) }
        }
    }
''',"service death registration")
s=one(s,'''    override fun reportCarPlaySessionLive(live: Boolean) {
        carPlaySessionLive = live''',
'''    override fun reportCarPlaySessionLive(live: Boolean) {
        if (!live) synchronized(v51OwnerLock) { v51ClearOwnerLocked() }
        carPlaySessionLive = live''',"clear owner on release")
service.write_text(s,encoding="utf-8")

source=ROOT/"carplay/CarPlaySourceSession.kt"
s=source.read_text(encoding="utf-8")
s=one(s,'''    private val running = AtomicBoolean(false)''',
'''    // Remote Binder token held for this session's full lifetime.
    private val v51OwnerToken = object :
        io.github.nitsuya.aa.display.xposed.IVirtualDisplayCreatedListener.Stub() {
        override fun onAvailableDisplay(displayId: Int, create: Boolean) {}
    }
    private val running = AtomicBoolean(false)''',"owner token")
s=one(s,'''        ProjectionSessionGate.setCarPlayLive(true)
        try {
            // Before Host onCreateSplitDisplay''',
'''        ProjectionSessionGate.setCarPlayLive(true)
        // register FIRST: if the app crashes during setup, system_server can
        // restore phone mute even without a service onDestroy callback.
        runCatching { CoreApi.registerCarPlayOwner(v51OwnerToken) }
            .onFailure { Log.e(CarPlayConsts.TAG, "v51 owner registration failed", it) }
        try {
            // Before Host onCreateSplitDisplay''',"register before live")
s=one(s,'''        mediaPrepared.set(false)
        ProjectionSessionGate.setCarPlayLive(false)
    }''',
'''        mediaPrepared.set(false)
        ProjectionSessionGate.setCarPlayLive(false)
        // Do not rely solely on Service.tearDown: early stop/crash paths can
        // otherwise leave system_server's audio capture and device mute armed.
        runCatching { CoreApi.reportCarPlaySessionLive(false) }
            .onFailure { Log.e(CarPlayConsts.TAG, "v51 restore audio failed", it) }
    }''',"explicit source stop")
source.write_text(s,encoding="utf-8")

audio=ROOT/"xposed/carplay/CarPlayAudioCapture.kt"
s=audio.read_text(encoding="utf-8")
s=one(s,'''    fun setEnabled(enabled: Boolean) {
        var reassertMute = false''',
'''    fun setEnabled(enabled: Boolean) {
        if (!enabled) {
            // v51: even if armed=false, a failed/rearming tap may retain a
            // MediaProjection, system stream mute or device-volume overrides.
            synchronized(opLock) {
                desired.set(false)
                val identity = Binder.clearCallingIdentity()
                try {
                    if (armed.get() || mediaProjection != null ||
                        mediaRecord != null || speechRecord != null ||
                        phoneMuted || speakerDeviceMuted) {
                        disableLocked(restoreAudio = true)
                    }
                } finally {
                    Binder.restoreCallingIdentity(identity)
                }
            }
            return
        }
        var reassertMute = false''',"hard disarm on false")
s=one(s,'''                proj = obtainMediaProjection(ctx)
                if (proj != null) {''',
'''                val v51SkipProjection = runCatching {
                    val p = Class.forName("android.os.SystemProperties")
                    p.getMethod("getBoolean", String::class.java,
                        Boolean::class.javaPrimitiveType)
                        .invoke(null, "debug.carplay.v51_skip_media_projection", false) == true
                }.getOrDefault(false)
                if (v51SkipProjection) {
                    log(TAG, "v51 MediaProjection A/B disabled by opt-in property")
                }
                proj = if (v51SkipProjection) null else obtainMediaProjection(ctx)
                if (proj != null) {''',"optional isolated no-projection")
s=one(s,'''                if (mediaRec == null) {
                    mediaRec = openRemoteSubmixRecord(MEDIA_SAMPLE_RATE, MEDIA_CHANNEL_MASK)''',
'''                if (mediaRec == null) {
                    // Do not hold a screen-capture session after playback
                    // capture failed and we switched to REMOTE_SUBMIX.
                    if (proj != null) {
                        ignoringProjectionStop = true
                        runCatching { proj.stop() }
                            .onFailure { log(TAG, "v51 unused projection stop failed", it) }
                        ignoringProjectionStop = false
                        proj = null
                    }
                    mediaRec = openRemoteSubmixRecord(MEDIA_SAMPLE_RATE, MEDIA_CHANNEL_MASK)''',"release unused projection")
audio.write_text(s,encoding="utf-8")

svc=ROOT/"carplay/CarPlayProjectionService.kt"
s=svc.read_text(encoding="utf-8")
s=one(s,'        private const val EXTRA_LAUNCH_HOST_TRAMPOLINE = "launchHostTrampoline"',
'''        private const val EXTRA_LAUNCH_HOST_TRAMPOLINE = "launchHostTrampoline"
        private const val EXTRA_FORCE_RESTART = "v51ForceRestart"

        /** Explicit button-only reset; AutoArm continues using listen-only start(). */
        fun reconnect(context: Context) {
            val i = Intent(context, CarPlayProjectionService::class.java)
                .setAction(CarPlayConsts.ACTION_CONNECT)
                .putExtra(EXTRA_LAUNCH_HOST_TRAMPOLINE, false)
                .putExtra(EXTRA_FORCE_RESTART, true)
            context.startForegroundService(i)
        }''',"explicit reconnect")
s=one(s,'''                ensureForeground()
                val launchHost = intent.getBooleanExtra''',
'''                if (intent.getBooleanExtra(EXTRA_FORCE_RESTART, false)) {
                    Log.i(CarPlayConsts.TAG, "v51 explicit reconnect: restart stale listen")
                    tearDown("v51-explicit-reconnect")
                }
                ensureForeground()
                val launchHost = intent.getBooleanExtra''',"reconnect command")
s=one(s,'''        session?.stop()
        session = null
        sessionRef.set(null)
        CarPlayHostRuntime.stop(reason)
        reportLive(false)
        stopForeground(STOP_FOREGROUND_REMOVE)''',
'''        try {
            runCatching { session?.stop() }
                .onFailure { Log.e(CarPlayConsts.TAG, "v51 session stop failed", it) }
            session = null
            sessionRef.set(null)
            runCatching { CarPlayHostRuntime.stop(reason) }
                .onFailure { Log.e(CarPlayConsts.TAG, "v51 host stop failed", it) }
        } finally {
            // Always tell system_server to drop mute/projection/live state.
            reportLive(false)
            stopForeground(STOP_FOREGROUND_REMOVE)
        }''',"tearDown finally")
svc.write_text(s,encoding="utf-8")

status=ROOT/"carplay/CarPlayStatusUi.kt"
s=status.read_text(encoding="utf-8")
s=one(s,'''        binding.btnCarplayHost.setOnClickListener {
            applyChannel(activity, binding, CarPlayChannel.CHANNEL_CARPLAY)
            // Re-prompt discoverable''',
'''        binding.btnCarplayHost.setOnClickListener {
            applyChannel(activity, binding, CarPlayChannel.CHANNEL_CARPLAY)
            if (CarPlayChannel.useCarPlayEgress(activity) &&
                CarPlayRuntimePerms.ensureWireless(activity)) {
                CarPlayProjectionService.reconnect(activity)
            }
            // Re-prompt discoverable''',"manual reconnect button")
status.write_text(s,encoding="utf-8")
gradle=Path("aa-display/build.gradle.kts")
t=gradle.read_text(encoding="utf-8")
t=one(t,"versionCode = 3150","versionCode = 3151","version code")
t=one(t,'versionName = "0.3#17.8-v50"','versionName = "0.3#17.8-v51"',"version name")
gradle.write_text(t,encoding="utf-8")
print("v51: default reverse gate; binder death recovery; idempotent audio teardown; real reconnect")

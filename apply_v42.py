#!/usr/bin/env python3
"""v42: runtime IME hook version/status & compatible overloads; low-frequency safe mute.

Apply AFTER v41; keeps all v23/v39/v40 connection behavior and v41 default-off repair.
"""
from pathlib import Path

ROOT = Path("aa-display/src/main/java/io/github/nitsuya/aa/display")

def replace_once(text, old, new, label):
    found = text.count(old)
    assert found == 1, f"v42 {label}: expected 1 occurrence, got {found}: {old[:120]!r}"
    return text.replace(old, new, 1)

# 1. Runtime status, independent of boot logs and IME event callbacks.
hook = ROOT / "xposed/hook/VdImeDisplayPin.kt"
s = hook.read_text(encoding="utf-8")
s = replace_once(s,
    '''    private var v41ImeTargetHook: XC_MethodHook.Unhook? = null''',
    '''    private var v41ImeTargetHook: XC_MethodHook.Unhook? = null
    private val v42CompatImeHooks = ArrayList<XC_MethodHook.Unhook>()
    @Volatile private var v42CompatStatus = "not-attempted"
    @Volatile private var v42LastReportMs = 0L''',
    "state fields")

s = replace_once(s,
    '''        runCatching { hookV41ImeSurfacePlacement() }
            .onFailure { log(TAG, "v41 IME surface placement hook install failed", it) }''',
    '''        runCatching { hookV41ImeSurfacePlacement() }
            .onFailure { log(TAG, "v41 IME surface placement hook install failed", it) }
        runCatching { v42InstallImeCompatHooks() }
            .onFailure {
                v42CompatStatus = "error:${it.javaClass.simpleName}:${it.message}"
                log(TAG, "v42 IME compat install failed", it)
            }''',
    "compat install")

anchor = '''    private fun v28SurfaceOf(container: Any): SurfaceControl? {'''
addition = '''    /**
     * v42 runtime diagnostic, called by the real CoreManagerService on EVERY AA
     * display-create request (max 1 log / 10 sec). This proves the bytecode
     * running in system_server is v42 regardless of logcat -c at boot.
     *
     * Only invoked when debug.carplay.v41_ime_diag=1. No background polling.
     */
    fun v42ReportState(source: String) {
        if (!v41Enabled("debug.carplay.v41_ime_diag")) return
        ensureHooked()
        val now = android.os.SystemClock.uptimeMillis()
        if (now - v42LastReportMs < 10_000L) return
        v42LastReportMs = now
        log(TAG,
            "v42 runtime source=$source ready=${AndroidHook.isReadyForSystemHooks()} " +
                "installAttempted=$installAttempted baseHooked=$hooked " +
                "v41Parent=${v41ImeParentHook != null} v41Target=${v41ImeTargetHook != null} " +
                "v42Compat=${v42CompatImeHooks.size} status=$v42CompatStatus " +
                "diag=${v41Enabled("debug.carplay.v41_ime_diag")} " +
                "repair=${v41Enabled("debug.carplay.v41_ime_reparent")}")
    }

    /**
     * HyperOS may change method signatures between A16 vendor builds. Enumerate
     * only the DisplayContent methods that already exist and hook exact overloads.
     * Never guess a vendor private class name; the status lists discovered names.
     * v41 hooks remain primary, so avoid hooking their identical overloads twice.
     */
    private fun v42InstallImeCompatHooks() {
        val cls = AndroidHook.loadSystemClass("com.android.server.wm.DisplayContent")
        if (cls == null) {
            v42CompatStatus = "DisplayContent-not-loaded"
            log(TAG, "v42 compat: DisplayContent class unavailable")
            return
        }
        val methods = cls.declaredMethods.filter {
            it.name in arrayOf("updateImeParent", "setImeLayeringTarget",
                "updateImeLayeringTarget", "computeImeTarget")
        }.sortedWith(compareBy({ it.name }, { it.parameterTypes.size }))
        val signatures = methods.map { m ->
            m.name + "(" + m.parameterTypes.joinToString(",") { it.simpleName } + ")"
        }
        var failures = 0
        for (m in methods) {
            // Already handled in v41 by the same method and same signature.
            if (m.name == "updateImeParent" && m.parameterTypes.isEmpty() &&
                v41ImeParentHook != null) continue
            if (m.name == "setImeLayeringTarget" && m.parameterTypes.size == 1 &&
                v41ImeTargetHook != null) continue
            // Method belongs to DisplayContent; its receiver MUST be DisplayContent.
            // computeImeTarget can be invoked frequently: only observe when explicitly
            // in diagnostic mode, and existing v41 logging is state-throttled.
            if (v42CompatImeHooks.size >= 8) break
            try {
                m.isAccessible = true
                v42CompatImeHooks.add(m.hookAfter { param ->
                    runCatching {
                        if (v41Enabled("debug.carplay.v41_ime_diag") ||
                            v41Enabled("debug.carplay.v41_ime_reparent")) {
                            v41ObserveImeParent(param.thisObject, "v42:${m.name}")
                        }
                    }.onFailure { log(TAG, "v42 IME callback failed", it) }
                })
            } catch (t: Throwable) {
                failures++
                log(TAG, "v42 could not hook ${m.name}/${m.parameterTypes.size}: ${t.message}")
            }
        }
        v42CompatStatus = "methods=${signatures.joinToString(";")} failures=$failures"
        log(TAG, "v42 IME compat discovered=$v42CompatStatus hooked=${v42CompatImeHooks.size}")
    }

'''
s = replace_once(s, anchor, addition + anchor, "v42 IME diagnostic/compat methods")
hook.write_text(s, encoding="utf-8")

core = ROOT / "xposed/CoreManagerService.kt"
s = core.read_text(encoding="utf-8")
s = replace_once(s,
    '''            if (!hasSystemContext) {
                log(TAG, "onCreateSplitDisplay aborted: systemContext not initialized")
                return@runMain
            }''',
    '''            // v42: event-driven proof that the NEW system_server Xposed class is
            // active. Not dependent on boot logs or input-method callback firing.
            runCatching { VdImeDisplayPin.v42ReportState("onCreateSplitDisplay") }
                .onFailure { log(TAG, "v42 runtime status report failed", it) }
            if (!hasSystemContext) {
                log(TAG, "onCreateSplitDisplay aborted: systemContext not initialized")
                return@runMain
            }''',
    "connected service runtime report")
core.write_text(s, encoding="utf-8")

# 2. Audio guard: avoid 250ms multistream Binder + AudioSystem resets forever.
audio = ROOT / "xposed/carplay/CarPlayAudioCapture.kt"
s = audio.read_text(encoding="utf-8")
s = replace_once(s,
    '''    /** CSM re-enforces local mute every 250ms — some OEMs restore MUSIC when apps start. */
    private const val MUTE_ENFORCE_MS = 250L''',
    '''    /** v42: 2s safety watchdog; volume-change receiver still triggers prompt repair. */
    private const val MUTE_ENFORCE_MS = 2_000L
    private const val MUTE_CORRECTION_LOG_MS = 15_000L
    private const val MUTE_DEVICE_RECHECK_MS = 15_000L
    private const val MUTE_EVENT_MIN_GAP_MS = 500L''',
    "mute period")

s = replace_once(s,
    '''    private val muteEnforceActive = AtomicBoolean(false)''',
    '''    private val muteEnforceActive = AtomicBoolean(false)
    /** Prevent concurrent poll / broadcast receiver AudioManager writes. */
    private val v42MuteCheckRunning = AtomicBoolean(false)
    private val v42LastMuteLogMs = AtomicLong(0L)
    private val v42SuppressedMuteLogs = AtomicInteger(0)
    private val v42LastDeviceZeroMs = AtomicLong(0L)
    private val v42LastVolumeEventMs = AtomicLong(0L)''',
    "mute guard state")

s = replace_once(s,
    '''    private fun enforcePhoneMute(am: AudioManager?) {
        if (am == null) return
        // Hold mute across rearm windows (desired + phoneMuted) even while briefly unarmed.''',
    '''    private fun enforcePhoneMute(am: AudioManager?) {
        if (am == null) return
        // A volume-changed broadcast can be raised synchronously by our own write.
        // Do not let it concurrently/reentrantly trigger another multi-stream pass.
        if (!v42MuteCheckRunning.compareAndSet(false, true)) return
        try {
        // Hold mute across rearm windows (desired + phoneMuted) even while briefly unarmed.''',
    "mute check reentrancy")

s = replace_once(s,
    '''        if (speakerDeviceMuted || phoneMuted) {
            // Re-zero local OUT devices without rewriting savedSpeakerVolumes.
            rezeroLocalPlaybackDevices()
        }
        if (touched) {
            log(
                TAG,
                "phone mute re-enforced streams=$streams" +
                    (restoredVol?.let { " musicWas=$it" } ?: ""),
            )
        }
    }

    /** Best-effort OEM fine / sem volume → 0 (no-op when APIs are absent). */''',
    '''        val now = android.os.SystemClock.uptimeMillis()
        if (speakerDeviceMuted || phoneMuted) {
            // Avoid reflection and resets of all output-device volume indices on
            // every watchdog pass. Repair promptly if ANY base stream changed,
            // otherwise periodically reassert physical-device safety.
            if (touched || now - v42LastDeviceZeroMs.get() >= MUTE_DEVICE_RECHECK_MS) {
                rezeroLocalPlaybackDevices()
                v42LastDeviceZeroMs.set(now)
            }
        }
        if (touched) {
            // LSPosed log() writes TWO expensive lines into system_server. Keep one
            // summary per 15 s rather than ~4/sec when an OEM stream ignores mute.
            val last = v42LastMuteLogMs.get()
            if (now - last >= MUTE_CORRECTION_LOG_MS &&
                v42LastMuteLogMs.compareAndSet(last, now)) {
                log(
                    TAG,
                    "v42 phone mute corrected streams=$streams " +
                        "suppressed=${v42SuppressedMuteLogs.getAndSet(0)}" +
                        (restoredVol?.let { " musicWas=$it" } ?: ""),
                )
            } else {
                v42SuppressedMuteLogs.incrementAndGet()
            }
        }
        } finally {
            v42MuteCheckRunning.set(false)
        }
    }

    /** Best-effort OEM fine / sem volume → 0 (no-op when APIs are absent). */''',
    "mute device & log throttle")

s = replace_once(s,
    '''                // No opLock here — see enforcePhoneMute. Snapshot gates only.
                if ((armed.get() && mediaMode == "playback-capture") ||
                    (desired.get() && phoneMuted)
                ) {
                    enforcePhoneMute(audioManager)
                }''',
    '''                // No opLock here — see enforcePhoneMute. Snapshot gates only.
                // Ignore self-generated AudioManager volume broadcasts for 500ms.
                val now = android.os.SystemClock.uptimeMillis()
                val last = v42LastVolumeEventMs.get()
                if (now - last < MUTE_EVENT_MIN_GAP_MS ||
                    !v42LastVolumeEventMs.compareAndSet(last, now)) return
                if ((armed.get() && mediaMode == "playback-capture") ||
                    (desired.get() && phoneMuted)
                ) {
                    enforcePhoneMute(audioManager)
                }''',
    "mute receiver event debounce")

audio.write_text(s, encoding="utf-8")

gradle = Path("aa-display/build.gradle.kts")
v = gradle.read_text(encoding="utf-8")
v = replace_once(v, "versionCode = 3141", "versionCode = 3142", "version code")
v = replace_once(v, 'versionName = "0.3#17.8-v41"',
                 'versionName = "0.3#17.8-v42"', "version name")
gradle.write_text(v, encoding="utf-8")

print("v42: runtime hook status/compat + 2s mute check + 15s device zero + debounced volume events")

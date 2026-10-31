# AADisplay CarPlay v42 — Runtime IME Hook Verification + Quiet Phone Mute

## Scope, safety, baseline

Based on the successful v41 CI branch. All v2–v41 patches remain, including:
- **v23** IPv4 gateway fast readiness.
- **v39** fix for first-connect disconnect from standalone RTSP preflight TCP.
- **v40** low-overhead compositor/control logs, original cadence, continuous audio.
- **v41** optional IME diagnostics and optional parent experiment; **repair OFF by default**.

Version: `3142`, `0.3#17.8-v42`.

## 1. IME diagnostic improvements

Prior v41 boot log `v41 installed system_server IME hooks` vanished after
`logcat -c`, while `v41 ime state` did not run. The connected Android
system_server definitely executes other AADisplay Xposed hooks, but that alone
cannot prove v41's IME event hooks are installed.

v42 introduces a definitive **runtime fingerprint** in the already functioning
`CoreManagerService.onCreateSplitDisplay` callback. On a new CarPlay session,
if `debug.carplay.v41_ime_diag=1`, the system server logs:

```
AAD_VdImeDisplayPin: v42 runtime source=onCreateSplitDisplay
  ready=... installAttempted=... baseHooked=...
  v41Parent=... v41Target=... v42Compat=...
  status=methods=... failures=... diag=true repair=false
```

It also enumerates actual `DisplayContent` IME method signatures and, where
v41 did not already install a hook, hooks selected compatible overloads:
`updateImeParent`, `setImeLayeringTarget`, `updateImeLayeringTarget`,
`computeImeTarget`. The names and parameter types are reported so we can
verify HyperOS behavior without guessing a vendor private class name.

No unconditional polling. Runtime log at most once per 10s, and only with
diagnostic property ON. **No v42 forced input-method reparent is enabled by
default.** v41's reparent experiment remains independently opt-in.

**Important:** APK Xposed code is loaded into `system_server`. Reboot
the Android source device after upgrading to v42, and ensure LSPosed framework
scope for the module is enabled.

### Capture the useful logs

After reboot, root terminal:

```sh
su -c 'setprop debug.carplay.v28_ime_root 0; setprop debug.carplay.v41_ime_diag 1; setprop debug.carplay.v41_ime_reparent 0; setprop debug.carplay.v39_legacy_tcp_probe 0'
```

Do not run `logcat -c` after enabling diagnostics unless necessary.
Connect to DiPlay and focus Gboard in Via or MT Manager, then:

```sh
su -c '(
  date
  getprop debug.carplay.v41_ime_diag
  logcat -b main -b system -d -v time | grep -iE "v42 runtime|v42 IME compat|v41 ime state|v41 updateImeParent|AAD_VdImeDisplayPin" | tail -90
) > /sdcard/Download/v42_ime_runtime.txt 2>&1'
```

If the runtime line is absent but AADisplay's regular session log says new
virtual displays were created, verify that the device was rebooted **after**
the v42 APK was installed, and inspect raw system_server logs.

### Optional A/B repair (do not enable until runtime diagnostic is seen)

```sh
su -c 'setprop debug.carplay.v41_ime_reparent 1'
```

Hide/show Gboard once, observe screen and system-server log. Disable with:

```sh
su -c 'setprop debug.carplay.v41_ime_reparent 0'
```

If the IME is stuck, reconnect or reboot to restore system-owned layer
placement. `setprop` test switches are not persistent through reboot.

## 2. Repeated phone mute optimization

Previous `CarPlayAudioCapture` checked eight phone stream types and reset
local audio device indices **every 250 ms**, plus LSPosed duplicated its
`phone mute re-enforced` log. The v41 trace showed this repeated many times.

v42:
- Replaces 250ms mute polling with **2-second safety checks**.
- Keeps the volume-change broadcast receiver for prompt correction, with a
  **500ms event debounce** to avoid self-triggered cascades.
- Adds an atomic guard against concurrent/reentrant mute operations.
- Re-zeros all local device indices only when a stream actually changed or at
  least every **15s** while a mute is held.
- Limits costly duplicated LSPosed `phone mute re-enforced` event logs to one
  summary per **15s**, counting suppressed repetitions.
- Does not change the first-arm saved stream/device volumes, original restore,
  audio sample format, 20ms PCM stream timing, RTSP heartbeat, or session policy.
- The mute guard is **not disabled**; an OEM may still restore MUSIC, so
  2s watchdog plus event-driven corrections preserve the protection.

Compare by checking both the system-server AudioManager load and whether
the phone speaker remains silent during actual media playback. If the latter
regresses on a device that silently restores volume without broadcasting,
record that behavior and we can tune the periodic fallback.

## Release validation

The GitHub Actions workflow applies v42 *after* v41, compiles
`:aa-display:assembleDebug`, verifies the APK zip structure, emits a
SHA-256 checksum, and publishes the APK plus checksum to a GitHub Release.

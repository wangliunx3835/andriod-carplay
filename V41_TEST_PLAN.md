# AADisplay CarPlay v41 — HyperOS IME Surface parent A/B

## Baseline preserved
Start with the known working **v40-lean-runtime** branch. Apply all patches
in order through `apply_v41.py`. The v23 IPv4 gateway fast readiness, v39
removal of the standalone TCP probe (first-connect stability), v40 runtime
throttles, RTSP/audio/video protocols and VirtualDisplay creation flags all
remain unchanged.

**No new behavior is enabled by default.** This build adds two separate
root-controllable system_server Xposed features specifically for the *two
AADisplay pane VirtualDisplays*:

| Property | Default | Meaning |
|---|---|---|
| `debug.carplay.v41_ime_diag` | 0 | Sparse event-driven WM IME parent diagnostic |
| `debug.carplay.v41_ime_reparent` | 0 | Experimental reparent of the IME container Surface to its own virtual display's IME placeholder |
| `debug.carplay.v28_ime_root` | 0 | Previous independent experiment; leave OFF when testing v41 |

v41 hooks `DisplayContent.updateImeParent()` and, where available,
`setImeLayeringTarget(...)`. It validates that `displayId` belongs to the
actual AA pane VDs, that an InputMethod window is visible, and the source and
destination SurfaceControls are valid before attempting an explicit
`SurfaceControl.Transaction.reparent`. It never targets Display 0.
The target is `mImeWindowsContainer.getParent().getSurfaceControl()`, rather
than v28's DisplayContent root: the IME's own designated container placement
may avoid inheriting an app's input-inset or dialog crop. Reparenting is
throttled across duplicate WM events, and it never runs on the encoder thread.

This is an **experimental hypothesis**, not a proven fix. The vendor
`MiuiMirrorInputMethodImpl` logs
`shouldUpdateImeParent:false` during changes involving pane Displays 2/3,
including cases with parent mismatch. Neither that log nor AOSP's
`updateImeParent` model proves that parent attachment is the sole cause.

## Must reboot once after APK installation
The hooks are in **system_server under LSPosed**. App force-stop alone will
not reload the Xposed module classes already loaded into system_server.
After installing the v41 APK, verify LSPosed framework scope is enabled,
then **reboot the Android device** once before testing.

## Step A: diagnostic-only capture (first, safest)
Root shell after reboot:

```sh
su -c 'setprop debug.carplay.v28_ime_root 0; setprop debug.carplay.v39_legacy_tcp_probe 0; setprop debug.carplay.v41_ime_diag 1; setprop debug.carplay.v41_ime_reparent 0'
su -c 'logcat -c'
```

Connect DiPlay, tap a text field in Via or MT Manager on one of the pane
displays, then run a delayed root capture (so Terminal focus doesn't disturb
the keyboard):

```sh
su -c '(
  sleep 12
  date > /sdcard/Download/v41_ime_time.txt
  dumpsys input_method > /sdcard/Download/v41_ime.txt
  dumpsys window windows > /sdcard/Download/v41_window.txt
  dumpsys SurfaceFlinger --list > /sdcard/Download/v41_sf.txt
  logcat -b all -d -v threadtime | grep -iE "AAD_VdImeDisplayPin|v41 ime|v41 installed|MiuiMirrorInputMethodImpl" | tail -120 > /sdcard/Download/v41_hook.txt
) >/sdcard/Download/v41_capture_error.txt 2>&1 &'
```

Within 12 seconds return to DiPlay and hold the keyboard in the
should-be-visible state. In the resulting log, check for
`v41 installed system_server IME hooks parent=true` (may be in the
earlier Xposed log buffer) and `v41 ime state event=...`.

If no v41 diagnostic events appear, do not infer that the repair is invalid;
instead inspect module scope, system_server injection, method availability,
and whether v41 was loaded at boot.

## Step B: opt-in experimental repair
Only after the diagnostic confirms the hook is actually running:

```sh
su -c 'setprop debug.carplay.v41_ime_reparent 1'
```

Hide and re-open the keyboard in the virtual screen. A successful attempt
should emit:

`v41 IME surface reparent applied display=2 event=updateImeParent target=...`

The display can instead be 3. Observe whether keys become visible in DiPlay,
and collect another pane GPU capture if not. A successful method call alone
does not prove SurfaceFlinger presented those pixels.

**Immediate rollback** (no APK downgrade required):

```sh
su -c 'setprop debug.carplay.v41_ime_reparent 0; setprop debug.carplay.v41_ime_diag 0; setprop debug.carplay.v28_ime_root 0'
```

If the IME surface is visually stuck or the keyboard animates incorrectly,
hide/show it, reconnect the session, or reboot to restore system-owned
Surface hierarchy. The test changes neither APK preferences nor device
partition files.

## Interpreting outcomes
- No `v41 installed`: verify LSPosed system framework injection and reboot;
  logs may be rotated, so check v41 event lines as well.
- Installed but no `v41 ime state`: trigger a fresh IME focus transition;
  investigate OEM method mismatch or early return. No reason to repeat v28.
- Diagnostic lines appear, but no `v41 IME surface reparent applied`: possible
  hidden window, wrong display, invalid surfaces, or no parent method.
- Applied and keyboard appears in raw pane: WM parent/clipping issue strongly
  supported.
- Applied but raw pane still excludes keyboard: move investigation to
  SurfaceFlinger relative layering, effective crop/visibility, and vendor
  composition security before attempting further blind changes.

## Performance
The new hooks run only on WM IME update/target events and are disabled by
default. No polling, auto screenshots, extra audio/video packets or socket
probes are added. No quantitative performance change is claimed.

Build: `versionCode=3141`, `versionName=0.3#17.8-v41`.

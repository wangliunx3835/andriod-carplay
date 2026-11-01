# AADisplay CarPlay v44 — IME display-area parent A/B experiment

Version: `versionCode=3144`, `versionName=0.3#17.8-v44`.
Pinned upstream: `lagXkjy/AADisplay` commit `494dcc4909e8765e8798be4e7b8031fefd90a4eb`, then apply patches v2 through v44.

## Evidence and why this differs from v28/v41

The valid locked/unlocked comparison from 2026-11-01 found both snapshots reporting the same active Gboard IME on Display 2: `mInputShown=true`, `mImeShowing=true`, and a real `VRI-InputMethod` surface. Yet the real IME was absent from the per-display SurfaceFlinger **output layer** listing in both states. A temporary `IME-screenshot-surface` appeared in output on the locked side and disappeared after unlock. This suggests an IME composition/parent/layering issue. The snapshot does *not* prove which exact clipping/ordering issue is responsible.

Earlier v28 and v41 experiments forcibly reparented the IME SurfaceControl after WindowManager's normal work; no confirmed fix followed. v44 instead hooks `DisplayContent.computeImeParent()` **before** `updateImeParent()` uses the computed SurfaceControl. When explicitly enabled and the current display belongs to AADisplay's pane VDs, it selects the IME container's declared display-area parent rather than its app ActivityRecord parent. WindowManager then owns the synchronized reparent and relative IME z-order. The hook checks for a real IME window, valid existing/target surfaces, and no organized IME container. The physical display and IME policy are untouched.

**Important:** This is a guarded repair *experiment*, not a verified fix. A different HyperOS implementation may lack `computeImeParent`, use an organized IME container, or require other composition policy changes.

## Behavioral scope

- v44 does not add per-app allowlists. It **retires the v43 hard-coded Gboard OEM guard dispatch**. The v43 source is retained only for patch reproducibility; no Gboard exemption is applied from the v44 session lifecycle.
- No global Greezer exemption, no forced process `top-app`, no blanket keep-alive. Any application in the background follows existing Android/HyperOS policy. Dynamic foreground-only Greezer protection is a separate, still-unverified task.
- Existing v23 IPv4 gateway optimization, v39 session stability, v40 lean performance, and v42 low-overhead mute logic are preserved.
- The new parent-choice repair is **OFF by default**, even if the v43 diagnostic guard property is still set.

## Installation

1. Install v44 over v43. **Reboot Android** so LSPosed reloads the system-server code.
2. Reconnect CarPlay and keep the phone, pane application, and selected input method the same during A/B.
3. Ensure older surface experiments are off:

```sh
su -c 'setprop debug.carplay.v28_ime_root 0; setprop debug.carplay.v41_ime_reparent 0; setprop debug.carplay.v43_ime_freeze_guard 0'
```

## A/B comparison

**A — baseline/observe:** enable sparse v44 diagnostics, leave repair off; reconnect and show the keyboard (lock/unlock sequence):

```sh
su -c 'setprop debug.carplay.v44_ime_diag 1; setprop debug.carplay.v44_ime_parent_policy 0'
```

**B — parent repair:** switch on and dismiss/reopen the keyboard to trigger a new computeImeParent decision:

```sh
su -c 'setprop debug.carplay.v44_ime_parent_policy 1'
```

Capture for either state after IME is visibly shown (or when it should be):

```sh
su -c '(
  OUT=/sdcard/Download/v44_ime
  mkdir -p "$OUT"
  date > "$OUT/date.txt"
  getprop debug.carplay.v44_ime_parent_policy > "$OUT/mode.txt"
  dumpsys window displays > "$OUT/window_displays.txt"
  dumpsys input_method > "$OUT/input_method.txt"
  dumpsys input > "$OUT/input.txt"
  dumpsys SurfaceFlinger --layers > "$OUT/sf_layers.txt"
  logcat -b main -b system -d -v threadtime |
     grep -iE "AAD_VdImeDisplayPin|v44 IME|MiuiMirrorInputMethod|InputDispatcher|ActionExecute|freezeUid|reportCarPlaySessionLive" |
     tail -400 > "$OUT/events.txt"
  tar -czf /sdcard/Download/v44_ime.tar.gz -C /sdcard/Download v44_ime
)'
```

Save the output as `v44_ime_A.tar.gz` and `v44_ime_B.tar.gz` respectively before repeating. For each, report (1) whether the keyboard is actually visible in the car, (2) whether it responds to touch, (3) whether the phone was locked or unlocked. Compare SurfaceFlinger **Output Layer** membership of the real `VRI-InputMethod`, not merely `visible reason` under a Layer.

Look for:

```text
AAD_VdImeDisplayPin: v44 runtime ... hooked=true
AAD_VdImeDisplayPin: v44 IME parent decision ... mode=OBSERVE/REPAIR
AAD_VdImeDisplayPin: v44 selected display-area IME parent ...
```

No selected-parent log could mean the selection is already correct, no IME was shown, an organized container, an absent hook, or another vendor decision path.

## Immediate rollback

```sh
su -c 'setprop debug.carplay.v44_ime_parent_policy 0'
```

Changing the property prevents future overrides; **dismiss and reopen the IME** so WindowManager re-evaluates parent choice. If the experiment causes persistent display problems, reboot the device with the property off. There is no persistent v44 setting to restore.

## Source reference

AOSP Android 16 DisplayContent: `updateImeParent()` calls `computeImeParent()` and uses the selected SurfaceControl for reparent and relative-layer ordering; app-attached IME is an intentional Android mode. v44 changes the choice only for our virtual displays, and needs real-device A/B confirmation:
https://android.googlesource.com/platform/frameworks/base/+/android16-qpr2-release/services/core/java/com/android/server/wm/DisplayContent.java

# v49 — HyperOS IME final Output Layer comparison

**Base:** v48 commit `d8bd223678120a155c2e9bd1ea958a16c78316ad`, pinned `lagXkjy/AADisplay` commit `494dcc4909e8765e8798be4e7b8031fefd90a4eb`. Build applies all prior patches v2–v45, v47, v48, then v49; v46 single-VD experiment stays excluded.

## Why v49 is different

- Real Gboard IME is drawn with buffers on Display 2 but absent from SurfaceFlinger Output Layers. This is not proven to be caused by WindowManager parent; ActivityRecord is a legitimate app-attached IME parent.
- User previously observed keyboard **visible but untouchable when locked**, versus **invisible but touchable when unlocked**. The goal is a matched SF/WM comparison of both conditions.
- v48 hook diagnostics showed `attachHook=true attachCalls=0 changed=0` while nativeUpdate count increased. v49 logs entry to existing `shouldImeAttachedToApp` hook **before** its filters. This is read-only and sampled.
- No direct SurfaceControl reparent, no new IME route changes, no speculative Xiaomi private flag mutations, no default diagnostics.

## Changes

- New `apply_v49.py` adds opt-in `debug.carplay.v49_ime_trace`, default OFF; read-only sampled entry log and v49EntryCalls field in v48 runtime report.
- New `tools/v49_capture.sh` takes two SF --layers snapshots (2s apart) plus input_method/window/display/filtered logcat. Only runs on command; archives to Download.
- App version `0.3#17.8-v49` (3149). No changes whatsoever to CarPlay Wi-Fi/BT, v23 IPv4 gateway readiness, v29 single session, v31 Event path, v38–v40 network stability, VD flags, GL/MediaCodec or virtual-pane count.

## Install and prepare

Install the v49 APK and **reboot Android to reload LSPosed/system_server**. In your rooted Android phone terminal run:

```sh
su -c 'setprop debug.carplay.v28_ime_root 0; setprop debug.carplay.v41_ime_reparent 0; setprop debug.carplay.v44_ime_parent_policy 0; setprop debug.carplay.v45_ime_parent_policy 0; setprop debug.carplay.v47_ime_no_fullscreen 0; setprop debug.carplay.v48_ime_display_area 0; setprop debug.carplay.v48_ime_diag 1; setprop debug.carplay.v48_leash_diag 0; setprop debug.carplay.v45_ime_diag 1; setprop debug.carplay.v49_ime_trace 1'
```

Copy `v49_capture.sh` from release to `/sdcard/Download/v49_capture.sh`. Don't type sensitive data while collecting logs.

### Unlocked: IME invisible but blind touches work

Connect CarPlay. In the same Via/MT Manager text field, show the soft keyboard. Start:

```sh
su -c 'sh /sdcard/Download/v49_capture.sh unlocked 15'
```

Return focus to the car, keep the IME open for 20+ seconds. File: `v49_unlocked_YYYYMMDD_HHMMSS.tar.gz`.

### Locked: IME previously visible but untouchable

Start the next command while still able to reach the Android terminal:

```sh
su -c 'sh /sdcard/Download/v49_capture.sh locked 15'
```

Immediately reproduce the lock-screen state **without entering a PIN**. If keyboard is not visible during lock, note this; do not label it as a positive lock case. File: `v49_locked_YYYYMMDD_HHMMSS.tar.gz`.

Upload both archives plus a short note: visible on unlocked? visible on locked? If script cannot run after the screen locks, start it first; its delay is intended for that.

## How to decide next actual fix

1. **IME joins SF Output Layers only when locked:** compare layer stack, display inclusion, crop, transforms, z-order and visible/draw regions. Fix only the first proven difference.
2. **IME excluded in both:** verify IME remained present and the earlier lock observation can be reproduced; do not assume vendor bug.
3. **IME included in both but still unseen when unlocked:** inspect GLES pane transform, SurfaceTexture, encoder content rather than WindowManager.
4. **v49EntryCalls > 0 but v48AttachCalls = 0:** inspect hook entry id/aa/container; earlier v48 filters blocked updates.
5. **v49EntryCalls = 0:** the old hook is not executed on this path; do not force native parent based on an unhit hook.
6. **Active Layers visible, Output Layers absent:** investigate AOSP Output::includesLayer, clip/drawRegion/occlusion and HyperOS-specific composition with a grounded comparison.

Independent scrcpy-style minimal trusted virtual display remains a **separate follow-up test, not shipped in this v49 APK**. Don't confuse that with this lock-state comparison.

Cleanup: `su -c 'setprop debug.carplay.v49_ime_trace 0; setprop debug.carplay.v48_ime_diag 0; setprop debug.carplay.v45_ime_diag 0'`

v49 is a **diagnostic build**, not an already validated visibility repair.

# AADisplay CarPlay v47 — NO_FULLSCREEN IME A/B + v46 cleanup

Version `0.3#17.8-v47`, versionCode `3147`. Fixed upstream `lagXkjy/AADisplay` commit `494dcc4909e8765e8798be4e7b8031fefd90a4eb`.

## Important v46 cleanup

The workflow applies v2–v45 and **v47**, **not** v46. `apply_v46.py` and `V46_TEST_PLAN.md` are removed in v47; there is no single-VD, no transparent 0×0 anchor/window, no single-only touch routing and no single-only GL compositor path. Normal two-VD CarPlay returns. IPv4 fast readiness from v23 and existing CarPlay connection/runtime optimizations are preserved.

The user captured a true single VD but still found real Gboard `VRI-InputMethod` outside the display's final Output Layer list, while IMMS reported the IME on that VD, visible and drawn. User also observed an IME InsetsSource of zero height and `mInFullscreenMode=true`.

**Caution:** AOSP InputMethodService.onComputeInsets() deliberately uses decor height as `contentTopInsets` in fullscreen mode. Zero-height InsetsSource is therefore **not proof of a broken Surface**. This experiment tests whether removing *landscape fullscreen/extract mode* changes the result, rather than forcing any Insets or Surface transforms.

## What v47 does

An opt-in, signature-sensitive Xposed hook in `system_server` intercepts `InputMethodManagerService.startInputUncheckedLocked(ClientState, ..., EditorInfo, ...)`. It requires a valid `mSelfReportedDisplayId` that matches a live AADisplay virtual display. When enabled, it ORs **`EditorInfo.IME_FLAG_NO_FULLSCREEN`** into the *per-request* `EditorInfo.imeOptions`. The flag is the AOSP-supported way to request non-fullscreen IME; some IMEs might ignore it.

No Gboard or Doubao whitelist, extra LSPosed app scope, persistent settings change, process freezing changes, physical Display 0 changes, Surface reparent or layer mutation.

**Default OFF** — install and reboot loads the hook but does not modify editor options until you enable the property.

## Test

1. Install v47 and reboot Android to reload `system_server`.
2. Disable prior unverified IME experiments and any leftover v46 properties:

```sh
su -c 'setprop debug.carplay.v28_ime_root 0; setprop debug.carplay.v41_ime_reparent 0; setprop debug.carplay.v44_ime_parent_policy 0; setprop debug.carplay.v45_ime_parent_policy 0; setprop debug.carplay.v46_single_vd 0; setprop debug.carplay.v46_anchor_window 0'
```

3. Connect CarPlay and use the same input app and input field for both A/B. Verify **two** AADisplay virtual displays exist.
4. A (diagnostic, no mutation):

```sh
su -c 'setprop debug.carplay.v47_ime_diag 1; setprop debug.carplay.v47_ime_no_fullscreen 0'
```

Dismiss/reopen keyboard. Capture as A.

5. B (experiment on):

```sh
su -c 'setprop debug.carplay.v47_ime_no_fullscreen 1'
```

Dismiss/reopen keyboard to force a new start-input and trigger the method. Test locked vs unlocked and keyboard touch. Capture as B.

### Capture (no download script needed)

Replace `M=A` with `M=B` for the second capture.

```sh
su -c '(
  M=A
  D=/sdcard/Download/v47_$M
  mkdir -p "$D"
  date > "$D/date.txt"
  getprop debug.carplay.v47_ime_diag > "$D/diag.txt"
  getprop debug.carplay.v47_ime_no_fullscreen > "$D/repair.txt"
  dumpsys input_method > "$D/ime.txt" 2>&1
  dumpsys window displays > "$D/window.txt" 2>&1
  dumpsys SurfaceFlinger --layers > "$D/sf_layers.txt" 2>&1
  dumpsys display > "$D/displays.txt" 2>&1
  logcat -b all -d -v threadtime |
    grep -iE "v47 |AAD_VdImeDisplayPin|MiuiMirrorInputMethodImpl|mInFullscreenMode" |
    tail -500 > "$D/events.txt"
  tar -czf /sdcard/Download/v47_$M.tar.gz -C /sdcard/Download v47_$M
  ls -lh /sdcard/Download/v47_$M.tar.gz
)'
```

Upload `v47_A.tar.gz` and `v47_B.tar.gz`; specify Gboard visible/hidden and touch works/fails.

### What counts as meaningful evidence

- Hook installation: `v47 IME flag hook installed`.
- Runtime: `v47 startInput display=2 ... mode=OBSERVE/REPAIR before=0x... after=0x... changes=N`.
- Actual mode: `mInFullscreenMode=false` in input method dump, and IME InsetsSource frame has non-zero height; compare across A/B.
- Final outcome: the **real** `VRI-InputMethod` appears in that VD's SurfaceFlinger Output Layer and keyboard is visible/touchable.

If the hook reports `method missing` or `client display unavailable`, **do not call the experiment successful**. If `changes>0` and fullscreen remains true, compliant IME behavior might differ or the editor was restarted before consumption. If fullscreen becomes false but output stays missing, fullscreen is not the main blocker; investigate SurfaceFlinger/HyperOS IME composition filters.

## Rollback

```sh
su -c 'setprop debug.carplay.v47_ime_no_fullscreen 0'
```

Dismiss/reopen keyboard. The v47 property does not persist through most reboots.

## AOSP reference

https://developer.android.com/reference/android/inputmethodservice/InputMethodService#onComputeInsets(android.inputmethodservice.InputMethodService.Insets)

https://developer.android.com/reference/android/view/inputmethod/EditorInfo#IME_FLAG_NO_FULLSCREEN

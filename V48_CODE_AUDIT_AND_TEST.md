# v48: comprehensive code review and HyperOS IME validation

**Build baseline:** pinned `lagXkjy/AADisplay` commit `494dcc4909e8765e8798be4e7b8031fefd90a4eb` + sequential v2–v45, v47 and v48 patches. v46 one-VD/anchor experiments are removed and **not applied**. Version `0.3#17.8-v48` / versionCode `3148`.

## Sources and checks

1. Nitsuya original [AaVirtualDisplayAdapter.kt](https://github.com/Nitsuya/AADisplay/blob/main/aa-display/src/main/java/io/github/nitsuya/aa/display/ui/aa/AaVirtualDisplayAdapter.kt): one virtual display, AA's TextureView as its Surface, default `DISPLAY_IME_POLICY_FALLBACK_DISPLAY` (1). This is NOT evidence the real IME rendered on the VD under Android 17.
2. Pinned dual-VD [SplitVdLifecycle.kt](https://github.com/lagXkjy/AADisplay/blob/494dcc4909e8765e8798be4e7b8031fefd90a4eb/aa-display/src/main/java/io/github/nitsuya/aa/display/ui/aa/split/SplitVdLifecycle.kt): PUBLIC/SECURE/TRUSTED/OWN_CONTENT_ONLY/OWN_DISPLAY_GROUP/ALWAYS_UNLOCKED/SUPPORTS_TOUCH; LOCAL IME policy; orientation lock; two separate VD buffers.
3. [CarPlayGlCompositor.kt](https://github.com/lagXkjy/AADisplay/blob/494dcc4909e8765e8798be4e7b8031fefd90a4eb/aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlayGlCompositor.kt): VD SurfaceTexture buffers -> GLES panes -> MediaCodec surface; no separate keyboard overlay in this path. If real InputMethod is absent from the VD Output Layers already, later encoding cannot restore it.
4. [VdImeDisplayPin.kt](https://github.com/lagXkjy/AADisplay/blob/494dcc4909e8765e8798be4e7b8031fefd90a4eb/aa-display/src/main/java/io/github/nitsuya/aa/display/xposed/hook/VdImeDisplayPin.kt): original branch correctly pins IMMS show target / LOCAL policy to the AA display. The earlier blind-click evidence and dumpsys confirm the IME token is on Display 2, not absent from WindowManager.
5. [Android 16 DisplayContent.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/services/core/java/com/android/server/wm/DisplayContent.java): `shouldImeAttachedToApp()` chooses attaching to `ActivityRecord` vs IME DisplayArea; `computeImeParent()` returns `WindowContainer`. `updateImeParent()` performs native synchronized reparent and relative layer assignment. Do not perform a separate Surface transaction in v48.
6. [Android 16 ImeInsetsSourceProvider.java](https://android.googlesource.com/platform/frameworks/base/+/android16-qpr2-release/services/core/java/com/android/server/wm/ImeInsetsSourceProvider.java): leash delivery requires source visibility, drawn window and given Insets readiness. A 10-second ImeTracker timeout alone does not prove missing leash.
7. [AOSP multi-display IME documentation](https://source.android.com/docs/core/display/multi_display/ime-support): single IME instance follows focus, and only authorized/system-owned VDs may host IME. Avoid assuming every virtual display is equivalent. This app creates VDs in privileged system_server.
8. [CarDeck/AGENTS.md](https://github.com/shaonialife/cardeck/blob/main/AGENTS.md): records an independently tested PUBLIC + LOCAL path. Both already exist in this AADisplay split baseline, so replaying those fixes without evidence is unnecessary.

## Evidence read from v47_B_delayed.tar.gz

Captured around 2026-11-02 13:39:38 and 13:39:52 on user's device (HyperOS Android 17). The client is `bin.mt.plus` on Display 2. `mCurDisplayId=2`, IME `mInputShown=true`, `mImeWindowVis=3`, `mInFullscreenMode=false`, `mImeShowing=true`, `mLastDrawn=true`. `InsetsSource frame=[0,454][1280,720]` with bottom inset 266. The valid IME input region explains blind tapping. Native IME leash is in the control map, `mIsLeashInitialized=true`, and `mImeParent=ActivityRecord` on Display 2. The real `VRI-InputMethod#1543` has a buffer, logical frontend visibility and `isSecure=false`, yet is missing from Display 2 Output Layers.

The Xiaomi-only SF property `miVisibleStateForDisplay=128` is correlated with this case but its bit semantics remain unverified; do not force it or claim it is definitely an exclusion bit. The observed IME control timeout may be one incomplete request while a later control already exists; avoid turning it into a forced leash-delivery workaround.

## Source audit: prior patch limitations

| Version | Implementation | New conclusion |
|---|---|---|
| v23 | IPv4 gateway fast-ready | Preserve unchanged |
| v28 | Direct post-WM Surface reparent to display | Experimental, default off; not a reliable transaction model |
| v41 | Post-update direct reparent + large setLayer | Experimental, default off; potential conflict with WM's sync transactions |
| v44 | Hook computeImeParent but require SurfaceControl return | Wrong for Android 16; v45 fixed signature |
| v45 | Hook computeImeParent and shouldImeAttachedToApp | Hook installed; previously zero modifications. **Premature requires mInputMethodWindow != null in app-attachment decision**; v48 tests this root cause |
| v46 | Single-VD + transparent 0x0 original-style anchor | Actually removed from build; single VD did not by itself restore keyboard |
| v47 | Add IME_FLAG_NO_FULLSCREEN per editor | Observed IME already not fullscreen with 266px Insets and still invisible; not sufficient |
| v48 | Scoped native parent policy experiment | Do not claim success until display-area parent is observed and Output Layer actually includes real IME |

## v48 code changes and safety

- The v48-specific `shouldImeAttachedToApp` path **does not require `mInputMethodWindow` to exist before parent selection**. It returns false only when the original AOSP decision is true, the pane is an AADisplay VD and the IME container is explicitly not organized.
- V48 uses only WindowManager's native `computeImeParent()` and `updateImeParent()` transactions and normal relative layering. No custom `reparent`, `setLayer`, fabricated leash or SurfaceFlinger private-flag mutation.
- Add diagnostic hooks for `DisplayContent.updateImeParent` and opt-in read-only `ImeInsetsSourceProvider.onPostLayout`, plus counts proving AOSP parent updates.
- All v48 diagnostics and policy default OFF. Scoped to live VD 2/3 (dynamic IDs), never physical Display 0.
- No changes to network handshake/BT, existing v23/v39/v40 optimizations, Greezer background app policy, codecs or user applications.

## A/B verification

Install v48 APK and **reboot Android** to reload Xposed's `system_server`. While CarPlay is disconnected, first disable past experimental paths:

```sh
su -c 'setprop debug.carplay.v28_ime_root 0; setprop debug.carplay.v41_ime_reparent 0; setprop debug.carplay.v44_ime_parent_policy 0; setprop debug.carplay.v45_ime_parent_policy 0; setprop debug.carplay.v47_ime_no_fullscreen 0; setprop debug.carplay.v48_ime_diag 1; setprop debug.carplay.v48_leash_diag 1; setprop debug.carplay.v48_ime_display_area 0'
```

### A: read-only baseline

Connect CarPlay, focus Via/MT Manager input field. Leave physical phone untouched. Use the delayed capture script (below) and label A. Confirm hook installed/attachDecision and nativeUpdate events. If logs show method unavailable, stop interpreting the proposed fix as tested.

### B: native display-area parent (opt-in)

```sh
su -c 'setprop debug.carplay.v48_ime_display_area 1'
```

Completely dismiss/reopen the soft keyboard (or switch to another input field) so WindowManager recomputes the IME parent. Ideally **disconnect/reconnect after enabling** for an unambiguous start of IME lifecycle. Compare the same app and unlocked/locked conditions. Key evidence: `v48 attachDecision`, `v48 display-area decision`, `v48 nativeUpdate parent=...` and `dumpsys window displays: mImeParent`. Also require actual `VRI-InputMethod` inside Display 2/3 SF Output Layers and visibly working touch.

### Direct delayed capture: no files to download

Execute before touching car display; return focus to car UI after launching:

```sh
su -c '(
  M=B
  D=/sdcard/Download/v48_$M
  mkdir -p "$D"
  logcat -b all -c 2>/dev/null || true
  (
    sleep 15
    date > "$D/date.txt"
    getprop debug.carplay.v48_ime_diag > "$D/diag.txt"
    getprop debug.carplay.v48_ime_display_area > "$D/policy.txt"
    getprop debug.carplay.v48_leash_diag > "$D/leash.txt"
    dumpsys input_method > "$D/ime.txt" 2>&1
    dumpsys window displays > "$D/window.txt" 2>&1
    dumpsys SurfaceFlinger --layers > "$D/sf.txt" 2>&1
    dumpsys display > "$D/display.txt" 2>&1
    logcat -b all -d -v threadtime |
      grep -iE "v48 |v45 |AAD_VdImeDisplayPin|ImeTracker|MiuiMirrorInputMethodImpl" |
      tail -500 > "$D/events.txt"
    tar -czf /sdcard/Download/v48_$M.tar.gz -C /sdcard/Download v48_$M
  ) >/sdcard/Download/v48_capture_errors.txt 2>&1 &
)'
```

After command, return focus to car screen and keep keyboard open for at least 20 seconds. Upload `v48_A.tar.gz` and `v48_B.tar.gz`. (The `logcat -c` line clears available log buffers. If unwanted, remove it before running.)

Rollback:

```sh
su -c 'setprop debug.carplay.v48_ime_display_area 0; setprop debug.carplay.v48_leash_diag 0; setprop debug.carplay.v48_ime_diag 0'
```

Reopen input field; reboot if a stale window surface persists.

## Decision table

- `changed > 0`, native parent becomes `ImePlaceholder`/display area, real IME joins Output Layers: strong support for early parent decision root cause.
- `changed > 0`, parent changes but real IME still excluded: WindowManager attachment alone is **not sufficient**; next investigate OEM SF filtering, no more parent reparent attempts.
- No `attachDecision`: hook not installed, method not invoked or filter was rejected. Inspect `v48 runtime`, scope and display IDs before judging hypothesis.
- Organized IME container: do **not** force reparent; native vendor organizer owns placement. Need trace organizer's SurfaceControl actions.
- Native leash is ready but Output Layers exclude IME: keep leash/IME control as secondary hypothesis; inspect vendor composition only with firmware symbols or known OEM source.

**Security:** do not add untrusted displays, override secure-keyboard capture protections or log actual input characters/clipboard content. Test without entering passwords.

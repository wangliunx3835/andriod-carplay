# AADisplay CarPlay v45 — Android16 IME parent signature fix

VersionCode `3145`, versionName `0.3#17.8-v45`. Built from pinned upstream `494dcc4909e8765e8798be4e7b8031fefd90a4eb` plus v2–v45 patches.

## Why v44 had no effect

v44 looked for `DisplayContent.computeImeParent(): SurfaceControl`, while AOSP Android 16 returns `WindowContainer`. The version-specific predicate can fail before any hook is registered. In v45, we locate `computeImeParent()` without assuming its return type, then return either the native display-area `WindowContainer` (new Android) or its `SurfaceControl` (older Android) as appropriate. The native `shouldImeAttachedToApp()` hook is an additional, optional way to prevent app-attached IME on CarPlay pane virtual displays. Normal WindowManager surface transactions and relative layer ordering are preserved.

**This is a source-level compatibility repair and a testable hypothesis, not proof the keyboard display problem is fixed.** Xiaomi's `MiuiMirrorInputMethodImpl` can still change placement, and missing real-IME SurfaceFlinger output layers may have other causes.

- No global keyboard visibility forcing, no modifications to physical Display 0.
- No package-specific app freezer list or forced background app priority: v43's Gboard-only guard stays retired.
- Existing v23 IPv4 readiness, v39 connection stability, v40 lean runtime and v42 mute optimizations are unchanged.
- All v45 modifications are **OFF by default** until explicitly opted in. Unrecognized ROM methods are logged and ignored.

## Install and reboot

1. Install v45 APK and **reboot Android** for LSPosed system-server hooks.
2. Reconnect CarPlay. First make sure old IME experiments are off:

```sh
su -c 'setprop debug.carplay.v28_ime_root 0; setprop debug.carplay.v41_ime_reparent 0; setprop debug.carplay.v44_ime_parent_policy 0; setprop debug.carplay.v43_ime_freeze_guard 0'
```

## A: Observe without changing IME parent

```sh
su -c 'setprop debug.carplay.v45_ime_diag 1; setprop debug.carplay.v45_ime_parent_policy 0'
```

Dismiss and reopen the keyboard on Display 2 or 3. Capture logs. Ensure `v45 discovered computeImeParent return=` prints a **real** method return type; `v45 runtime ...` proves the installed code is invoked. If missing, inspect LSPosed system-framework scope and reboot state.

## B: Enable IME parent policy

```sh
su -c 'setprop debug.carplay.v45_ime_parent_policy 1'
```

Dismiss and reopen keyboard, test while physical screen is locked and unlocked, same app and input field. Observe actual keyboard visibility and touch responsiveness.

Collect:

```sh
su -c '(
  echo "=== VERSION ==="
  dumpsys package io.github.nitsuya.aa.display | grep -m 2 -E "versionCode=|versionName="
  echo "=== FLAGS ==="
  getprop debug.carplay.v45_ime_diag
  getprop debug.carplay.v45_ime_parent_policy
  echo "=== HOOK & OEM ==="
  logcat -b all -d -v time |
    grep -iE "v45 |AAD_VdImeDisplayPin|MiuiMirrorInputMethodImpl|InputMethod is not responding" |
    tail -250
) > /sdcard/Download/v45_ime_test.txt 2>&1'
```

If behavior stays the same, also capture `dumpsys SurfaceFlinger --layers` to check whether real `VRI-InputMethod` is now in Display 2/3 Output Layers. If no `v45 app-attached IME disabled` and no `v45 IME parent decision` is logged, the hook has not been validated as active; do not claim a successful repair.

## Rollback

```sh
su -c 'setprop debug.carplay.v45_ime_parent_policy 0'
```

Dismiss/reopen IME. If graphics state does not recover, reboot with property disabled. No persistent v45 whitelist or global policy is written.

## References

- Android 16: https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/services/core/java/com/android/server/wm/DisplayContent.java
- Android 13: https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/wm/DisplayContent.java

# v43 — HyperOS Greezer Gboard freeze A/B (opt-in)

VersionCode `3143`, versionName `0.3#17.8-v43`.

## Evidence from real v42 capture (2026-10-31)

- 23:00:23 — InputDispatcher ANR, `9f1eea7 InputMethod` did not respond to DOWN for **5000 ms**.
- 23:07:01.592 — OEM framework `ActionExecute` logged:
  `freezeUid SUCCESS: uid=10337 pkg=com.google.android.inputmethod.latin reason=screen_on`.
- 23:07:25.648 — input dispatcher confirmed Gboard InputMethod took **4984 ms**
  and **4326 ms** to process touchscreen DOWN events.
- Display 3 input window `a90c1ce InputMethod` (ownerUid=10337, pid=5796)
  had touchableRegion `[0,0][1280,720]`, covering Via's whole screen.
- `A_ime_stuck` and `B_touch_ok` had **the same** Display 3 IME window,
  focus and touch region even after the visible car-side pane toggle; the
  outer display controls may work without clearing system IME state.
- Phone display group 0 dozed, while VD group 1 remained interactive.
- `DispatchEnabled=true` and `DispatchFrozen=false` describe the **global
  dispatcher**, not Gboard's separately freezer-managed app process.

This makes OEM app freezing a **strong candidate** for the touch freeze, not a
confirmed sole explanation. IME geometry / unlocked-phone invisibility remains
a separate issue.

## Implementation

**Off by default. No global freezer or keyguard change.** The experimental
property is `debug.carplay.v43_ime_freeze_guard=1`.

During a CarPlay session (from the existing binder
`reportCarPlaySessionLive` callback), v43:
1. Checks the existing OEM
   `Settings.System["com.miui.game.allowlist"]` *exact package* entries.
2. Only if absent, appends `com.google.android.inputmethod.latin`, preserving
   the existing entries; records the original value (including absence).
3. Sends the Xiaomi `com.xiaomi.mipush.REFRESH_WHITE_LIST_ACTION` broadcast
   scoped to package `android`, with `pkgName=...` and `option=-1`. This
   was observed to thaw the target without MiPush membership changes on a
   separately studied HyperOS ROM. **It is an internal, unsupported OEM API,
   and may not work on this device.**
4. On ordinary CarPlay session disconnect, removes only the entry added by
   v43; if no other writer modified the list, restores the original string.
5. Reports events using log tag `AAD_V43ImeFreezeGuard`.

**Limitations:** Unexpected process/system_server crash or force-close may
skip cleanup, leaving Gboard in an OEM allowlist until manually removed.
Other Xiaomi components can rewrite the shared list while CarPlay is active.
Not all HyperOS ROMs implement the same exemption or thaw receiver.
Security, lockscreen and phone's input logic remain untouched. Experiment
only on a rooted test device.

## A/B steps

1. Install the v43 APK and reboot the Android phone so LSPosed system_server
   picks up the new module code.
2. **Read and save pre-test OEM setting**:
   ```sh
   su -c 'settings --user 0 get system com.miui.game.allowlist > /sdcard/Download/v43_allowlist_before.txt'
   ```
3. **Test A: default off.** Confirm `getprop debug.carplay.v43_ime_freeze_guard`
   is `0` or empty. Connect CarPlay and check the known keyboard issue.
4. Disconnect CarPlay. **Test B: turn on guard before new connection**:
   ```sh
   su -c 'setprop debug.carplay.v43_ime_freeze_guard 1'
   ```
   Reconnect CarPlay, then lock screen, focus Gboard and attempt typing.
5. Capture:
   ```sh
   su -c '{
      echo "=== PROP ==="
      getprop debug.carplay.v43_ime_freeze_guard
      echo "=== OEM LIST ==="
      settings --user 0 get system com.miui.game.allowlist
      echo "=== GUARD AND FREEZER ==="
      logcat -b main -b system -d -v time |
        grep -iE "AAD_V43ImeFreezeGuard|freezeUid SUCCESS|InputMethod spent|InputMethod is not responding" | tail -90
   } > /sdcard/Download/v43_freeze_test.txt 2>&1'
   ```
   Upload that file, noting if the keyboard became responsive on lockscreen.
6. Disconnect CarPlay; verify
   `settings --user 0 get system com.miui.game.allowlist`
   equals the pre-test value.

## Rollback

```sh
su -c 'setprop debug.carplay.v43_ime_freeze_guard 0'
```

On a normal disconnect, v43 removes only its own addition. If Android or
the module crashes while active, manually restore the exact saved old value.
If the original command printed `null` (key absent), use:

```sh
su -c 'settings --user 0 delete system com.miui.game.allowlist'
```

If the original key contained a string, restore the exact original string
with `settings --user 0 put system com.miui.game.allowlist "ORIGINAL_VALUE"`
without dropping any other game entries.

## Source basis and caveat

Independent reverse engineering of HyperOS Greezer's
`GreezeManagerService.preCheckInterest()` and OEM thaw broadcast:
https://github.com/dingwen07/hyperos-fcm-fix/blob/main/docs/xiaomi-hyperos4-nighttime-fcm-investigation.md

Only `com.google.android.inputmethod.latin` is targeted. No non-Gboard
IME package is modified. v23 fast IPv4, v39 reconnect, v40 lean runtime
and v42 quiet phone-mute remain in their original order.

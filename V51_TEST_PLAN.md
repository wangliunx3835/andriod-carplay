# v51 — Reverse-camera default + crash-safe CarPlay cleanup

Base v50 `317fef2eb6b0fe9aac23a20a8301d932c0768e37`. Pinned AADisplay upstream `494dcc4909e8765e8798be4e7b8031fefd90a4eb`. Apply after v50; no v46 one-display experiment. Keeps v23 IPv4 gateway, v29 single-owner, v31 Event and v39 stable TCP.

## Proven reverse camera now automatic

The user verified that setting `debug.carplay.v50_reverse_video_gate=1` fixes reverse-image switching in their vehicle. v51 makes the gate ON by default for new RTSP sessions. When the receiver sends authenticated `changeModes` for MainScreen resource 1, transfer 3 BORROW/transfer 4 UNBORROW, suppress H.264 while the receiver owns screen, resume + request keyframe when returned. No changes to audio or control packets. Emergency rollback: `su -c 'setprop debug.carplay.v50_reverse_video_gate 0'` and reconnect. This only applies when the HU sends MainScreen ownership change; not arbitrary reverse CAN detection.

## Crash and stale session cleanup

- App-process Binder owner token registered with system_server before reporting live. System server observes `linkToDeath` and, after an actual app crash, clears phone mute/MediaProjection, ends session-live and promptly tears down virtual displays, avoiding old 180-second idle recovery for a dead app process. It does not trigger during expected RTSP soft reconnect when the app process remains alive.
- Audio `setEnabled(false)` is now idempotent even when `armed=false` with a stuck mute or Projection, and unused MediaProjection sessions are closed on audio fallback.
- Service `tearDown()` reports live=false in `finally` even if session/host stop fails. `CarPlaySourceSession.stop()` itself also requests live=false.
- UI manual reconnect actually tears down stale listen and starts fresh. Automatic BootArm is unchanged.

## Notifications blank after disconnect

The user's disconnected `dumpsys media_projection` returned `null`; this does NOT prove a projection was active after disconnect. v51 strengthens resource teardown but does not disable Android privacy protections or guarantee SystemUI notification restoration. Optional A/B no MediaProjection path: `su -c 'setprop debug.carplay.v51_skip_media_projection 1'`, restart CarPlay, compare notifications, keyboard and audio. Audio may fall back and work differently; default OFF. Reset property 0 and reconnect.

## Test

1. Install v51 and REBOOT Android to reload system_server LSPosed and release old v50 stuck state. Clear old experimental flags: `su -c 'setprop debug.carplay.v50_ime_mirror 0; setprop debug.carplay.v50_reverse_video_gate 1'`. The second command is **optional**; v51 default is already ON.
2. Without setting any reverse flag, connect and safely test reverse in a stationary vehicle. Confirm no flashing, no disconnection, and normal picture on leaving reverse. Use `v50_reverse_capture.sh` only if it fails.
3. Disconnect normally, observe the phone volume, screen-share indicator and notification previews. Return to the app, tap `重新连接` to verify a truly new listen session rather than `正在准备画面`.
4. Force-stop or simulate the app terminating only **while parked**, reconnect and observe whether system_server logs `v51 CarPlay app binder died`, whether system audio un-mutes and projection disappears. Do not perform this test while driving.
5. If notifications remain blank despite `dumpsys media_projection` null, compare before/during/after with v51 opt-in no-Projection A/B. Do not toggle global screen-sharing privacy protections permanently.

## Diagnostic command

```sh
su -c 'logcat -b main -b system -d -t 12000 -v threadtime | grep -Ei "v51|CarPlayAudioCapture|reportCarPlaySessionLive|MediaProjection" | tail -220 > /sdcard/Download/v51_lifecycle.txt'
```

Upload `v51_lifecycle.txt`, and note three results: reverse flicker, restored phone volume, notification previews.

Caution: v51 build success does not establish the actual behavior of OEM audio or SystemUI. Fixes are limited to AADisplay-owned resources; it does not rewrite users' notification privacy settings.

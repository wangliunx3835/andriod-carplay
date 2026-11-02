# v50 — IME live mirror and reverse-camera screen ownership experiments

Base v49 commit 06a3c1beb4ed7b86b5df6da00da6a9841486de18, pinned upstream 494dcc4909e8765e8798be4e7b8031fefd90a4eb. v46 one-display trial remains removed. No modifications to v23 IPv4, v29 single session, v31 Event, v39 connection, v40 runtime, dual VD, codec or RTSP handshakes.

## IME: controlled experimental live mirror, default OFF

v49 proved real InputMethod Surface has a buffer and is in LayerStack 2 but absent from Output Layers; locked screen shows a non-interactive IME screenshot under the app ActivityRecord. v50 mirrors the *existing* IME SurfaceControl hierarchy under the same app ActivityRecord, without reparenting original IME or stealing touch. Scoped to AADisplay VDs and non-secure IME/app windows only. Hook updateImeParent and setImeLayeringTarget; no frame polling. This is an unvalidated experiment; Xiaomi compositor could still exclude the mirror.

Install APK, reboot Android (system_server/LSPosed). Disable prior parent experiments:
su -c 'setprop debug.carplay.v28_ime_root 0; setprop debug.carplay.v41_ime_reparent 0; setprop debug.carplay.v44_ime_parent_policy 0; setprop debug.carplay.v45_ime_parent_policy 0; setprop debug.carplay.v48_ime_display_area 0; setprop debug.carplay.v47_ime_no_fullscreen 0'

A: property debug.carplay.v50_ime_mirror=0; open an ordinary MT Manager text field; capture with v49_capture.sh unlocked 15.
B: set su -c 'setprop debug.carplay.v50_ime_mirror 1'; fully close/reopen IME; capture again. Look for v50 mirror created and mirrored hierarchy inside Display 2 Output Layers. Test normal non-sensitive typing only. To disable: setprop debug.carplay.v50_ime_mirror 0 and close/reopen IME; reboot if mirror persists. Avoid passwords/financial input.

## Reverse camera: verified MainScreen ownership, default OFF

v30 only suppresses modesChanged screen reclaims when the receiver owns MainScreen; it does NOT stop H.264 video. Apple CarPlay resource management prescribes backup-camera BORROW MainScreen and UNBORROW after reverse, while audio may continue. v50 adds debug.carplay.v50_reverse_video_gate=1, which suppresses the encoded screen frames ONLY after authenticated HU changeModes has transferred MainScreen to the receiver. Resumes and requests a keyframe on return; no RTSP reconnect, no codec recycle, audio/feedback unaffected.

Critical: no previous log conclusively showed BORROW during reverse. If the Linux receiver never sends it, this code cannot automatically recognize reverse and the head-unit/MCU/CAN or receiver compositor must enforce priority. A silent video stream could also trigger disconnection on some receivers; this is why the gate defaults OFF.

Stationary vehicle only, passenger operates terminal. First diagnostics with:
su -c 'setprop debug.carplay.v50_reverse_trace 1; setprop debug.carplay.v50_reverse_video_gate 0'
Reconnect CarPlay so options reload. Run sh /sdcard/Download/v50_reverse_capture.sh under su, reproduce reverse transition while stationary and upload archive. Confirm event changeModes resourceID 1 and Borrow/Unborrow before enabling gate.
If verified, set su -c 'setprop debug.carplay.v50_reverse_video_gate 1'; reconnect and repeat stationary capture. Check v50 video suppressed and whether rear camera priority/flicker changes, plus whether CarPlay stays connected.
Rollback: su -c 'setprop debug.carplay.v50_ime_mirror 0; setprop debug.carplay.v50_reverse_video_gate 0; setprop debug.carplay.v50_reverse_trace 0' then restart session. Never use a black overlay or source-side fake reverse signal as a substitute for receiver camera priority.

Release assets: v50 APK, checksum, prior v49_capture.sh, v50_reverse_capture.sh.
# v51 — reverse-camera default and safe CarPlay disconnect recovery

Base v50 commit 317fef2eb6b0fe9aac23a20a8301d932c0768e37, upstream fixed 494dcc4909e8765e8798be4e7b8031fefd90a4eb. Keep v23 IPv4 fast-ready, v29 single session, v31 events, v39 stable first connect, dual VD. v46 single-display experiment excluded.

User confirmed v50 MainScreen BORROW/UNBORROW H264 suppression successfully fixes reversing. v51 defaults the gate ON when `debug.carplay.v50_reverse_video_gate` unset, with explicit 0 opt-out. No fake gear signals or RTSP/control shutdown.

On media teardown v51 waits existing 4s soft reconnect grace and checks the receiver still isn't streaming; then disarms system-server audio, stops encoder, releases GPU/dual VDs, marks host idle and keeps BT+RTSP listeners listening. Full service teardown always reports session live=false. HostActivity no longer boots a compositor during idle/listen. Status now confirms actual streaming instead of relying on a stale system_server live flag. System-server audio watchdog stops orphan capture and restores phone volume after 90s without PCM pulls (30s tick granularity); this can also disarm legitimate long-running video-only sessions that generate no audio pulls.

The disconnected projection diagnostic showed `Media Projection: null`, and turning off screen-share protection did not fix notifications or keyboard. That does NOT prove a shared root cause. An unused MediaProjection is now stopped if audio capture fails before REMOTE_SUBMIX fallback. `debug.carplay.v51_no_media_projection=1` explicitly bypasses projection acquisition for controlled notification/IME A/B only; default OFF. Audio may be silent or play on the handset in this experiment. The v50 IME surface mirror remains default OFF; no new forced IME or privacy bypass hooks.

## Test

Install APK, reboot Android to reload system_server LSPosed. Reverse gate ON by default after reboot: do not manually toggle. In a safely parked vehicle, confirm rear camera priority and CarPlay frame return after reverse.

Disconnect the CarPlay receiver normally; after 5s the phone should regain volume, old dual VDs/encoder should have stopped and the status should say "等待车机连接", not falsely "正在准备画面". Reconnect to test fresh automatic Host/VD startup. If app is force-stopped while audio muted, system-server orphan recovery needs approximately 90–120s.

For notification/IME correlation, collect A with normal audio (property `debug.carplay.v51_no_media_projection=0`), then disconnect and set:
```sh
su -c 'setprop debug.carplay.v51_no_media_projection 1'
```
Reconnect, compare **phone notification text** and **Gboard on virtual display** with the same generic non-sensitive app, while separately checking audio. Restore 0 and reconnect afterwards. Never paste actual messages/passwords into logs.

To collect concise non-sensitive status logs: put `v51_state_capture.sh` under `/sdcard/Download`, run `su -c 'sh /sdcard/Download/v51_state_capture.sh connected'`, or `disconnected`, or `reconnected`, and upload the generated archive. Report notification empty? volume unmuted? reconnect restored? reverse stable?

Rollback reverse gate: `su -c 'setprop debug.carplay.v50_reverse_video_gate 0'`, then reconnect; clearing this property or rebooting makes the default ON again. The no-projection switch must not disable system-wide privacy settings.

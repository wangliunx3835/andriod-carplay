# AADisplay CarPlay v60 — reverse-camera safe + lean runtime

## Evidence (v59 log, Nov 4 2026)
- Camera UNBORROW at 20:42:25.675.
- Sender stalled 2.513s. First screen-only SETUP at 20:42:28.605 got RTSP 400 Bad Request.
- At 20:42:40.614, second screen-only SETUP got 200 OK. CONFIG + IDR followed by 20:42:40.670 and video recovered.
- Reason for first RTSP 400 is unproven; v60 adds settle time rather than changing AirPlay fields or full reconnect.

## v60 changes
1. Track authoritative backupCamera BORROW/UNBORROW in EventChannel. No keyframe request from requestUI while backup-camera BORROW is active.
2. No screen-only SETUP during BORROW or for 5.5 seconds after camera UNBORROW. Single delayed return check at 6 seconds rather than 4 seconds. No periodic new watcher.
3. On SETUP failure, retry only if normal encoder keeps reporting unusable video. Backoff after failures 4/8/16s; successful recovery retains v58's 12s cooldown.
4. While camera BORROW is active, the GL compositor draws at 10fps rather than 60fps; normal target rate resumes immediately after UNBORROW, encoder/VD/Surface are retained. Camera interval is excluded from frame-rate auto-degrade.
5. Idle video sender waits on a condition variable instead of waking every 1 second.
6. Existing lean defaults unchanged: automatic GPU screenshot off, manual trigger-file poll off, verbose RTSP feedback parsing off. Additional duplicate iAP2 detect-marker logs reduced.

## A/B and risk
- Camera GL 10fps trial is enabled by default. To disable before new session: su -c 'setprop debug.carplay.v60_reverse_lowfps 0'
- Return to default: su -c 'setprop debug.carplay.v60_reverse_lowfps 1'
- The new staged recovery and camera guard remain enabled regardless of 10fps flag.
- RTSP 400 can be caused by other receiver conditions. Real hardware verification is still required.

## Test while safely parked
1. Install v60, reconnect and confirm video/audio, Gboard keyboard, and media lyrics.
2. Hold reverse 10/30/60 seconds; watch for flashes WHILE camera showing. Camera must remain top priority.
3. Return to CarPlay and time any black screen. Repeat HU HOME -> CarPlay.
4. Only on a reproduced issue, run v58_black_capture_reliable.sh to collect a bounded tar.gz, then stop the recorder. The recorder is a separate Root terminal script and is NOT bundled in or auto-started by the APK.
5. Compare key logs: v60 backupCamera borrowed; v59 return probe; v58 video-only recovery and failureCount; RTSP 400.

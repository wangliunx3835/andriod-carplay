# v58 Long reverse black screen video-only recovery — experimental

v57 confirmed symptom: video network sender blocked for 32572ms and dropped 6375 compressed frames while CarPlay audio stayed connected. Queue clearing cannot cancel the in-flight blocked Socket.write. This patch attempts a video-only recovery rather than unsafe codec restarts or full CarPlay re-pairing.

## Changes
- Stop enqueuing video immediately when MainScreen is HU-owned; flush old GOP at BORROW/TAKE. This avoids the queue backlog that v57 generated because its reverse gate was inside the already-blocked TCP sender.
- After MainScreen returns (or on requestUI), if video sender remains blocked over 2.5s, close only the blocked video dataPort and send an encrypted AirPlay video type-110 SETUP on the existing live control channel. Reuse existing H264 codec/config, negotiate new streamConnectionID/dataPort, request new IDR. AAC, Bluetooth, pairing, event channel, voice and virtual displays remain untouched.
- Recovery limited to one active attempt, and >=12s between attempts. Refuses any attempt if the HU still owns MainScreen (including backupCamera BORROW). No periodic watchdog or unbounded frames.
- **Deliberately no SO_SNDTIMEO** in this first version: a send timeout would close the stream even while the vehicle is in reverse. Instead close only after explicit return and a confirmed in-flight stall. Android Socket.setSoTimeout does not bound write anyway.
- Fully opt-out with `su -c 'setprop debug.carplay.v58_video_recover 0'` BEFORE starting a new CarPlay session. Restart session after setting. Restore 1 to re-enable.

## Critical limits
- The target HU has NOT verified video-only SETUP on a live AirPlay control session. A successful build does NOT prove receiver accepts new video-only SETUP. If it rejects, v58 logs the failure but keeps audio; next explicit requestUI may retry after 12s.
- This only targets a confirmed sender stall; if the receiver decoder freezes while still consuming video, separate evidence is required.

## Parked-only verification
1. Install v58, reboot, connect CarPlay, confirm QQ/Soda lyrics and initial video/audio.
2. Test 10s, 30s, 60s reverse display **while safely parked**, then return to CarPlay; verify camera is never covered while in reverse. Also test HU HOME > CarPlay.
3. On black or any unwanted disconnect, export:
```sh
su -c 'logcat -d -b main -b system -t 30000 -v threadtime | grep -Ei "AADisplay_CarPlay.*(v58|v57|v55 requestUI|changeModes|MainScreen|screen dataPort|screen CONFIG|SETUP screen|AVC|AirPlay enc|releaseMediaStreams)" | tail -n 750 > /sdcard/Download/v58_video_filtered.txt'
```
4. Note whether initial video works; whether 10s or only 60s reverse fails; whether audio continues and whether "v58 video-only recovery result=true" appears.

## Scope
Preserves v23 fast IPv4, v47 dual-VD IME, v54 media controls and QQ/Soda lyrics, v55 requestUI screen ownership, v56 card width/height and 430ms lyric scroll, and v57 bounded codec/egress queue. No random disconnects or 30s full-RTSP rejoin.

# v58 long reverse black screen: video-only recovery

Base v57, preserving v23 IPv4 quick readiness, v55 HU TAKE->requestUI, v56 adjustable media widget and scrolling lyrics, v54 QQ/Soda lyric and media controls, audio, iAP2 and dual VDs.

## Grounded
User provided a short v57_filtered log with:
- 12:37:21 AVC requestKeyFrame
- 12:37:22 v57 video TCP sender potentially blocked for **32572ms**, pending=7, dropped=6375
This is direct proof the v57 sender was stuck in one network sending operation when sampled. It does not by itself prove whether HU paused reads, Wi-Fi transport stalled, or receiver video decode was wedged. The existing v57 queue cannot interrupt a blocked in-flight Socket write.

## Fix
1. When reverse/main screen is owned by HU and v50 reverse gate is enabled (default from v51), suppress H264 at the encoder->queue entry, not only at the network send exit. On HU return, flush stale queued frames and request a fresh IDR.
2. When screen is phone-owned, active encrypted control continues, and in-flight video TCP sending is stalled >4.5s, attempt a **video-only type-110 SETUP** via the already authenticated RTSP encrypted control channel:
   - mark video not streaming briefly, abort old blocked video dataPort Socket without acquiring BufferedOutputStream writer lock
   - retire old sender epoch and start one new worker for the new video stream
   - send new screen type110 SETUP with a **fresh streamConnectionID** (fresh per-video ChaCha key), parse HU dataPort, open new bound TCP video socket
   - re-use the existing MediaCodec SPS/PPS (no mid-stream codec recycle), request IDR, resume video
   - AAC/RTP audio, iAP2, BT, pairing and whole RTSP service are not restarted.
3. Max 2 video-only repair attempts per session, 25s cooldown, only while MainScreen belongs to phone and the control pump is alive. Never auto-reclaim the screen in active reverse.
4. Logs: `v58 suppress enqueue`, `v58 repairing video only`, `v58 video-only screen SETUP result` and `v58 video-only screen rearmed`.

## Experimental controls
Default new repair ON, disable BEFORE establishing a new RTSP CarPlay session:
`su -c 'setprop debug.carplay.v58_video_repair 0'`
Restore:
`su -c 'setprop debug.carplay.v58_video_repair 1'`
During testing, retain v57 async video=1 and v55 requestUI=1. All tests only with safely parked vehicle.

## Testing
1. Install and reboot; ensure CarPlay connects, video+audio, v56 overlay lyrics/control and dual VDs unchanged.
2. Park, enter reverse camera for 10-30s, exit; repeat. Ensure reverse camera is NEVER covered while active. Check HU home->CarPlay return.
3. If still black, take logs:
```
su -c 'logcat -d -b main -b system -t 30000 -v threadtime | grep -Ei "AADisplay_CarPlay.*(v58|v57|MainScreen|requestUI|SETUP screen|screen CONFIG|screen VIDEO|dataPort|AVC|modesChanged|RTSP)" | tail -n 700 > /sdcard/Download/v58_video_return.txt'
```

## Caution
Screen-only SETUP on an existing AirPlay control session is protocol-dependent and may be rejected by some car receivers. CI compile does not validate actual HU behavior. If the HU does not allow screen re-SETUP without a full session, we need receiver-specific evidence and a different recovery negotiation. The patch does not restart CarPlay/audio automatically when SETUP is rejected.

# AADisplay CarPlay v34 – Optional Media Setup Barrier & StartSession Recovery

Based on v33. **The core first-connection TCP reset is not yet proven fixed**. This release adds a controlled experiment for the suspected asynchronous media-start ordering.

## Changes

- New **opt-in** DiPlay RTSP media gate. When enabled, screen H.264 AVC CONFIG/IDR and DiPlay PCM media/speech RTP are not sent until screen SETUP, media/speech audio SETUP, and the session-ready callback finish. Pre-gate AVC CONFIG may be cached; then fresh IDR is requested. This experiment is **off by default** and not applied to Audi MIB3.
- Persist that iAP2 **0x4301 CarPlayStartSession** was received across an RFCOMM disconnect; avoid mistakenly treating an old session as having never received StartSession and launching a spurious fallback. The remembered bit resets only when a new iAP2 authentication round completes or on full source stop. Any pending old v14 recovery is cancelled at new authentication.
- Keep v23 IPv4 gateway readiness, v29 one-owner AirPlay, v30 reverse-camera arbitration, v31 event-channel response demux, v32 MediaCodec and probe fixes, and v33 A/V experiments/logging.
- No change to the default H.264 profile, bitrate or 60fps policy. IME visibility is not yet fixed.

## A/B test procedure (root terminal, vehicle safely parked)

**A — v34 default (media barrier off, 60fps, no extra audio delay)**:
```sh
su -c 'setprop debug.carplay.v34_media_barrier 0; setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
```
Manually reopen app, start logcat BEFORE connecting, then connect and keep for at least 30 seconds:
```sh
su -c 'logcat -c; logcat -b main -b system -v threadtime -f /sdcard/Download/v34_default.txt'
```
Ctrl-C to stop.

**B — v34 media gate enabled** (other properties remain 0):
```sh
su -c 'setprop debug.carplay.v34_media_barrier 1; setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
```
Reopen, capture to `/sdcard/Download/v34_gate1.txt` with same logcat command but changed filename.

## Evidence to look for

- `v34-setup-gate enabled=true mib3=false`
- `v34-video-held await audio SETUP`
- `v34-audio-held type=media`
- `v34-gate-open audioMedia=true ...`
- `v34 0x4301 received; history retained after RFCOMM close`
- If an old RTSP session ends after a verified 0x4301: `v34 prevent no-StartSession recovery ...`
- Count first-connect disconnects, timing of control/event `Connection reset`, Wi-Fi `CTRL-EVENT-DISCONNECTED`, and first successfully sent IDR.

Note: Comparison across separate runs cannot establish causality unless repeated and wireless conditions are similar. Do not run both v33 audio delay and v34 gate experiments simultaneously.

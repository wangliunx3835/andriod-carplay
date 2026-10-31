# AADisplay CarPlay v35 — AirPlay Feedback + Optional Protocol Experiments

Built on v34 (pinned upstream `494dcc4909e8765e8798be4e7b8031fefd90a4eb`). **This is a diagnostic and A/B experiment release. It does not claim to have fixed the receiver-originated first-connect TCP Reset.**

## Changes

1. **Default-on, low-noise encrypted RTSP /feedback diagnostics.** The existing sole control reader parses the response bplist `streams` and records `type`, `streamConnectionID`, `sampleTime`, `sr`, `timestamp`. Logs first 12 responses, then 1 in 20. It does not alter CSeq handling, RTSP feedback cadence, or any outbound network packet.
2. **Opt-in DiPlay Screen KeepAlive.** `debug.carplay.v35_screen_ka=1` sends a plaintext 128-byte opcode=2 frame every 1s on the video TCP data port, only **after first IDR**. Uses the same output-stream lock as encrypted H.264 writes; does not advance video ChaCha nonce. Worker ends on egress close. Default **off**. Not enabled on Audi MIB3.
3. **Opt-in post-audio RECORD.** `debug.carplay.v35_post_audio_record=1` issues **one additional RTSP RECORD after audio SETUP, before session-ready**. The original pre-screen RECORD remains in place. This is a safer first experiment, *not* yet the alternative CarPToCarL ordering of deferring the first RECORD. Failure returns a failed setup; diagnostic records its response. Default **off**. Not enabled on Audi MIB3.

Retains v23 quick IPv4 gateway readiness, v29 single-owner guard, v30 reverse-camera arbitration, v31 event demux, v32 codec lifetime, v33 30fps and audio-delay switches, v34 0x4301 history and optional media barrier. Default 60fps profile/bitrate unchanged. IME visibility not claimed fixed.

## Test procedure — vehicle parked

Set flags **before app restart**, then manually reopen AADisplay and connect to HU. Always collect logcat starting *before* initial CarPlay connect:

```sh
su -c 'setprop debug.carplay.v35_screen_ka 0; setprop debug.carplay.v35_post_audio_record 0; setprop debug.carplay.v34_media_barrier 0; setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
su -c 'logcat -c; logcat -b main -b system -v threadtime -s AADisplay_CarPlay:V WifiClientModeImpl:I wpa_supplicant:I "*:S" -f /sdcard/Download/v35_baseline.txt'
```

Ctrl-C after disconnect/reconnect to stop logcat. Expect `v35-options screenKA=false postAudioRecord=false` and `v35-feedback n=...` with stream fields, if HU returns a bplist.

**A/B 1: Screen KeepAlive ONLY** (use same capture command with `v35_screen_ka.txt` filename):
```sh
su -c 'setprop debug.carplay.v35_screen_ka 1; setprop debug.carplay.v35_post_audio_record 0; setprop debug.carplay.v34_media_barrier 0; setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
```
Expect `v35-options screenKA=true`, `v35 screen KA armed`, `v35 screen KA sent #1`.

**A/B 2: Additional RECORD ONLY** (use `v35_record.txt` log):
```sh
su -c 'setprop debug.carplay.v35_screen_ka 0; setprop debug.carplay.v35_post_audio_record 1; setprop debug.carplay.v34_media_barrier 0; setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
```
Expect `v35-options postAudioRecord=true`, `v35-post-audio-record start`, `v35-post-audio-record success=true`.

For all modes compare: first session elapsed time to `Connection reset`, `wlan0 CTRL-EVENT-DISCONNECTED`, first screen CONFIG/IDR, audio SETUP, feedback media sampleTime, and eventual 0x4301 recovery. Reproduce each option more than once before inferring causality.

## Important

The option defaults are 0. Screen keepalive uses opcode=2 (no stats) because DiPlay does not require `/info.keepAliveSendStatsAsBody=true`; some receivers require opcode=5 with stats, so do not treat a failed opcode=2 trial as disproving all keepalive mechanisms. A successful RTSP 200 response alone does not confirm actual media rendering.

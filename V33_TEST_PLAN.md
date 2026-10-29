# AADisplay CarPlay v33 – First-connection diagnostics

v33 is a **diagnostic/test release** built on v32, not a confirmed fix for the Linux receiver's first-connection reset. It keeps all v23-v32 changes, including IPv4 quick readiness, exclusive AirPlay owner, reverse-camera MainScreen resource arbitration, RTSP event-response demux, MediaCodec generation guard and probe-only EOF isolation. Existing invisible Gboard keyboard behavior is not resolved by this release.

## What changed
- A session-scoped monotonic `v33` log timeline identifies **start-session** vs **fallback**, pairing, SETUP, control-pump start/exit, screen egress, media audio first packet, and the first six AVC output buffers (PTS/delta, codec configuration, IDR flag). No pairing secrets are printed.
- **Default**: v32 behavior. Two opt-in properties are read at new connection/recreation; change one at a time.
- `debug.carplay.v33_audio_delay_ms=800`: delay the first **DiPlay type-100 media RTP** packet by 800 ms (0-1500 supported), not audio SETUP and not speech or AAC. Preserves the existing 1200 ms pause *after* the first packet.
- `debug.carplay.v33_video_fps=30`: fix encoder/frame supply and **type-110 screen SETUP fps** at 30 rather than 60. This test leaves H.264 High profile, resolution and bitrate policy unchanged. It does not test H.264 Baseline.
- Return both properties to 0 to restore the v32-default behavior.

## Root terminal test, vehicle safely parked
Connect with **one setting at a time**, fully disconnect and recreate the session after changing flags. Capture from before connecting:
```sh
su -c 'setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
su -c 'logcat -c; logcat -b main -b system -v threadtime -f /sdcard/Download/v33_default.txt'
```
Stop live logcat with Ctrl-C after the connection becomes stable.

For the **audio test**, before the next CarPlay attempt:
```sh
su -c 'setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 800'
```
Collect `v33_audio800.txt` using the same logcat command, replacing the filename.

For the **video test**, before the next attempt:
```sh
su -c 'setprop debug.carplay.v33_video_fps 30; setprop debug.carplay.v33_audio_delay_ms 0'
```
Collect `v33_fps30.txt`.

Restore defaults:
```sh
su -c 'setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
```
On all trials record how many visual connect/disconnect cycles occurred. An optional simultaneous packet capture on wlan0 of host `10.81.24.134` helps correlate RSTs with the `v33` time trace. IP address may differ in future sessions. Redact SSIDs or identifiers before sharing logs.

# AADisplay CarPlay v40 — lean runtime, preserve stable v39 first connection

## Evidence and performance baseline
Measured from timestamped sender logs (one first-session sample per version):

| Stage | v37 | v38 | v39 |
|---|---:|---:|---:|
| RFCOMM accepted -> iAP2 auth completed | 581ms | 693ms | 635ms |
| RFCOMM accepted -> Wi-Fi bound | 2263ms | 1453ms | 1278ms |
| RFCOMM accepted -> media SETUP finished | 3574ms | 2515ms | 2469ms |
| AirPlay session start -> media SETUP finished | 832ms | 567ms | 728ms |

These samples do not prove a meaningful 46ms speed increase. The sender v39 log
ends at 16:38:51.448, roughly 42s after session begin, with no recorded reset;
the user's direct observation was over one minute of stable projection.

Longer wall-clock startup remains partly outside this 2.5s build-up:
v39 logs repeated outbound RFCOMM dialing to a different bonded device before
the OPPO DiPlay inbound RFCOMM was accepted. This version deliberately avoids
changing Bluetooth policy while the new stable first-connection path is validated.

## v40 scope and safety constraints
Default behavior changes affect observation work only:
1. **No-art NowPlaying fetch:** Previously every 1s refresh launched a fresh
   `cp-nowplaying-art` thread, requested JPEG via `CoreApi` Binder, and logged
   `artwork skip — jpeg=-1B` if no album cover was available. v40 attempts at
   most once per 20s for an unchanged failed art revision; a new art revision
   retries immediately. Only one fetch worker may run at a time, and the latch
   is released in `finally`. Valid artwork transfers are unchanged.
2. **Manual GPU diagnostic trigger:** v27/v28's filesystem existence check
   every 1s in compositor is now **disabled by default**. To keep that feature,
   explicitly opt in at app startup with
   `debug.carplay.v40_manual_gpu_capture=1`, then create the existing
   `v27_capture.trigger` file to capture frames. This reduces normal per-frame
   monitoring without deleting capture functionality.
3. **RTSP feedback diagnostics:** `POST /feedback` must remain at its current
   cadence and is still sent, read and demultiplexed exactly as before.
   Only verbose binary-plist inspection is now opt-in
   (`debug.carplay.v36_verbose_feedback=1`). In normal mode, suppress every
   subsequent expected orphan 200 log after the first, and suppress 1Hz
   `control feedback →` debug log; optional
   `debug.carplay.v40_verbose_control=1` restores that log.

**Unaffected:** v39 no-standalone wireless TCP probe (critical first-connect
fix), v23 IPv4 gateway readiness, iAP2 handshake, RTSP setup/record ordering,
the actual RTSP heartbeat, audio/video codecs, 20ms audio pacing, Bluetooth
recovery, automatic reconnect, touch and IME UI/policy.

Version: `versionCode=3140` / `versionName=0.3#17.8-v40`.

## Root Android testing

Normal baseline (set before launching the app):

```sh
su -c 'setprop debug.carplay.v39_legacy_tcp_probe 0; setprop debug.carplay.v38_legacy_audio_pause 0; setprop debug.carplay.v37_claim_before_screen 0; setprop debug.carplay.v37_record_after_screen 0; setprop debug.carplay.v36_verbose_feedback 0; setprop debug.carplay.v40_manual_gpu_capture 0; setprop debug.carplay.v40_verbose_control 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
su -c 'logcat -c'
su -c 'logcat -b main -b system -v threadtime -s AADisplay_CarPlay:V "*:S" -f /sdcard/Download/v40_first.txt'
```

Connect to DiPlay and keep the first session active for at least one minute.
Stop logcat using Ctrl+C. Repeat a fresh first connection if convenient.

**Acceptance:** `v39 skip standalone TCP probe wireless`; no 2/4/8s
scheduled receiver reset; normal RTSP responses and audio/video throughput
continue; no repeating `artwork skip — jpeg=-1B` warnings and no ordinary
1Hz `control feedback →` or `orphan cseq` lines. If unexpected teardown
appears, save a new DiPlay report with timestamps aligned.

For protocol debugging only:
```sh
su -c 'setprop debug.carplay.v36_verbose_feedback 1; setprop debug.carplay.v40_verbose_control 1'
su -c 'am force-stop io.github.nitsuya.aa.display'
```

For manual one-shot GPU readbacks only (after enabling and restarting):
```sh
su -c 'setprop debug.carplay.v40_manual_gpu_capture 1'
su -c 'am force-stop io.github.nitsuya.aa.display'
# Start the app and its virtual displays before running:
su -c 'mkdir -p /data/user/0/io.github.nitsuya.aa.display/files/CarPlayV26; touch /data/user/0/io.github.nitsuya.aa.display/files/CarPlayV26/v27_capture.trigger'
```

## Limitations
Reducing logs/diagnostic IPC does not imply measured CPU or battery savings.
It should reduce unnecessary threads, Binder requests and log volume by direct
code reasoning; confirm impact with Android profiler if precise benchmarks are
required. Bluetooth initial inbound accept delay is not fixed in v40.

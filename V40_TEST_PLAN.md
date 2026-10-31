# v40 — Less diagnostic overhead, same first-connect fix

## Base and scope
Based on verified and stable v39 `v39-no-standalone-tcp-probe`.
The **v39 removal of the standalone wireless TCP probe remains on by default**;
all v23 IPv4 readiness and v38 continuous audio functionality remains.

Measured with actual user logs:
| Event | v36 first | v37 (DiPlay) | v38 first | v39 first |
|---|---:|---:|---:|---:|
| RFCOMM accepted -> media SETUP ready | 3.448s | 3.574s (v37 A) | 2.515s | **2.469s** |
| StartSession -> media SETUP ready | 1.450s | 2.726s (v37 A) | 1.429s | 1.549s |
| AirPlay session start -> media SETUP ready | 0.547s | 0.832s (v37 A) | 0.567s | 0.729s |
| First session still up 8s later | no | no | no | **yes** |

The v39 log ends about 42s after RTSP start, so its file alone cannot
corroborate the user's >60s observation, although they explicitly reported it.

## v40 optimization
1. `CarPlayNowPlaying.maybeTransferArtwork`: record a positive artwork
   revision as attempted before scheduling its fetch thread. Without this,
   the absence of the JPEG caused a new `cp-nowplaying-art` thread, Binder
   artwork request and warning every single second indefinitely.
   A changed art revision, new-track rebind or egress reset permits another
   attempt; elapsed NowPlaying updates still run once per second.
2. `CarPlayRtspSession.sendControlFeedback`: do **not** suppress the actual
   keepalive or change its cadence. Only suppress per-packet DEBUG log by
   default.
3. `CarPlayRtspSession.controlOnMessage`: expected 200 responses with CSeq
   900000+ are no longer logged as `orphan` once per second by default.
   Non-feedback orphan responses are still logged. Existing v35/v36 sampled
   diagnostics and all protocol read/demux paths are unchanged.
4. Set `debug.carplay.v40_verbose_control=1` and force-stop/restart to
   restore the old debug logs when tracing is required.

**Not modified:** Bluetooth automatic dial / fallback, Bonjour, Wi-Fi
handoff, iAP2 authentication, AirPlay setup, feedback transmissions,
RTSP state machine, video, audio RTP, v39 preflight removal.

## Comparison of cold-connect waits
- The long wait *before* RFCOMM acceptance varies widely, e.g. 13.202s
  in one v38 run versus at least 14.979s from the first observed
  Bluetooth activity in v39; the v39 recording begins after RFCOMM
  listeners were already armed, so this is not an exact listen-to-accept
  measurement.
- Previous v36/v37 logs also have 13–19s listener-to-accept waits.
- The v39 slow feeling is therefore likely **not** attributable to the
  20–30ms removal of the TCP probe. Do not suppress Bluetooth scans or
  RFCOMM dialing without a separate controlled experiment.

## Test
```sh
su -c 'setprop debug.carplay.v39_legacy_tcp_probe 0; setprop debug.carplay.v40_verbose_control 0; setprop debug.carplay.v38_legacy_audio_pause 0; setprop debug.carplay.v37_claim_before_screen 0; setprop debug.carplay.v37_record_after_screen 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
su -c 'logcat -c'
su -c 'logcat -b main -b system -v threadtime -s AADisplay_CarPlay:V "*:S" -f /sdcard/Download/v40_first.txt'
```
Verify:
- `v39 skip standalone TCP probe wireless`
- No first-session restart at 2/4/8/16s
- Media continues for >= 60s.
- No per-second `artwork skip` when the artwork revision stays unchanged.
- No per-second `control feedback →` or `orphan cseq=9000xx` logs,
  but continuous audio, video and no RTSP timeout.
- Artwork still transfers when revision changes and a JPEG exists.

Comparison option: `setprop debug.carplay.v40_verbose_control 1`
then force-stop and restart the app. This changes logging only.

The completed v39 remains available as rollback if any regression is seen.

# v36 — Lean baseline and Bonjour readiness experiment

## Audit of v33–v35 actual results

| Prior change | Evidence | v36 decision |
|---|---|---|
| v23 IPv4 gateway quick ready | Essential project behavior | RETAIN |
| v29 one AirPlay owner, v31 event response demux, v32 codec/probe lifecycle | Prevent known competing connection and stale surface failures | RETAIN |
| v33 30fps and 800ms delayed audio | First RST reproduced under both tests | Both OFF by default (already) |
| v34 A/V media barrier | Verified gate really opened after audio SETUP yet first reset remained | OFF by default (already) |
| v34 0x4301 observed-across-RFCOMM history | Confirmed prevents incorrect no-StartSession fallback | RETAIN enabled |
| v35 extra post-audio RECORD | Two first connections reset around 2.02s | OFF by default (already) |
| v35 screen opcode 2 keepalive | Frame #1 sent before receiver reset around 2.06s | OFF by default (already) |
| v35 /feedback decode | type=100 audio sampleTime advanced before reset | Sample first 2 then 1 in 30; full mode opt-in |
| v33 first 6 AVC payload/PTS hex dumps | No proven fault isolated by heavy logging | OFF by default; one-property diagnostic opt-in |
| v25/v26 GPU captures and v28/v30 IME experiment | No observed keyboard fix; legacy switches are opt-in | Do not enable, preserve source for rollback |

No earlier patch scripts are deleted, since patch chain is ordered. Disabling proven ineffective experiments is safer than unwinding v33–v35 code while preserving security and lifecycle fixes.

## v36 changes

- Default AirPlay media protocol, frame rate, audio latency and wifi path are unchanged from v35 default.
- New debug.carplay.v36_ctrl_quiet_ms=600: after successful TCP probe but before AirPlay media preparation, wait on the FIRST wireless dial worker for fresh _carplay-ctrl NsdManager onServiceRegistered callback plus 600ms quiet time. Bound wait to 2000ms; if timed out proceed. Use per-registration generation to reject stale callback. Default 0: no waiting. Does not block Wi-Fi or Bluetooth callbacks and leaves v23 IPv4 optimization intact.
- New debug.carplay.v36_verbose_video=1 reenables v33 6-frame video debug, sampled ONCE per AirPlay session; default 0 reduces per-frame processing.
- New debug.carplay.v36_verbose_feedback=1 reenables v35 feedback sampling (first 12 then 1/20); default logs first 2 then 1/30, retaining the crucial first-failure evidence.
- All experimental props (v33 fps/audio, v34 barrier, v35 screen KA/RECORD, v36 Bonjour wait) default to 0.
- v34 verified 0x4301 recovery guard is preserved. IME issue is separate, not claimed fixed.

## Two independent tests (parked)

1. Configure BASELINE (no wait); stop then reopen app:
```sh
su -c 'setprop debug.carplay.v36_ctrl_quiet_ms 0; setprop debug.carplay.v36_verbose_video 0; setprop debug.carplay.v36_verbose_feedback 0; setprop debug.carplay.v35_screen_ka 0; setprop debug.carplay.v35_post_audio_record 0; setprop debug.carplay.v34_media_barrier 0; setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
su -c 'logcat -c; logcat -b main -b system -v threadtime -s AADisplay_CarPlay:V WifiClientModeImpl:I wpa_supplicant:I "*:S" -f /sdcard/Download/v36_baseline.txt'
```
2. Configure EXPERIMENT (only Bonjour registration quiet wait):
```sh
su -c 'setprop debug.carplay.v36_ctrl_quiet_ms 600; setprop debug.carplay.v36_verbose_video 0; setprop debug.carplay.v36_verbose_feedback 0; setprop debug.carplay.v35_screen_ka 0; setprop debug.carplay.v35_post_audio_record 0; setprop debug.carplay.v34_media_barrier 0; setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
su -c 'logcat -c; logcat -b main -b system -v threadtime -s AADisplay_CarPlay:V WifiClientModeImpl:I wpa_supplicant:I "*:S" -f /sdcard/Download/v36_ctrl600.txt'
```
Collect from BEFORE first 0x4301 through 1+ reconnect and stop with Ctrl+C. Compare v36 ctrl-settle outcome, Bonjour registration/probes, first media IDR, RST, reason/locally_generated Wi-Fi disassociation. Repeat each condition. If slower or broken, set the quiet prop 0 and force-stop/relaunch.

## Research: public implementations and limits

- shihabal3amri/DiPlay is an Android BYD/DiLink CARPLAY RECEIVER; the Linux HU identifying itself DiPlay has not been proven to use this code. https://github.com/shihabal3amri/DiPlay
- DiPlay startup diagnostic guide treats authenticated iAP2, usable IPv4/IPv6, Bonjour control probe, AirPlay TCP accept and actual session activation as distinct milestones. https://github.com/shihabal3amri/DiPlay/blob/main/docs/WIRELESS_DIAGNOSTICS.md
- DiPlay release 0.2.22 documents hotspot-interface selection and slow DNS reverse lookup fixes; neither proves why our already-connected session resets. https://github.com/shihabal3amri/DiPlay/blob/main/docs/RELEASE-NOTES-0.2.22.md
- DiPlay connection reliability explicitly distinguishes repaired source tests from real-device acceptance. https://github.com/shihabal3amri/DiPlay/blob/main/docs/CONNECTION_RELIABILITY.md
- CarPToCarL documents separate RTSP feedback, UDP keepalive, screen keepalive and RECORD sequencing; v35 tested only additional RECORD, not moved initial RECORD. https://github.com/jjuugk/CarPToCarL/blob/main/docs/PROTOCOL-NOTES.md
- CarDeck is an Android CarPlay sender useful for comparing the complementary side of a wireless link. https://github.com/shaonialife/cardeck
- PlayPort ports the DiPlay AirPlay/iAP2 protocol layer to a JVM receiver and is useful for controlled protocol response comparison; not a drop-in Linux HU binary. https://github.com/youcci/playport

The first 2s RST root cause is NOT confirmed. A new successful registration callback means Android NsdManager has accepted advertising, not that the Linux receiver has completed IPv4/IPv6 control probes. A contemporaneous TCP capture or Linux receiver log remains the strongest next evidence.
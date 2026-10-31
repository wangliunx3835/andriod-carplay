# AADisplay CarPlay v37 – initial RTSP session state experiments

## Grounded evidence

- Repeated v35 and v36 first-session TCP reset, typically about +2s or +4s. v36 Bonjour gate completed _carplay-ctrl registration/IPv4+IPv6 probes before AirPlay, yet the first encrypted SETUP still reset at +448ms; second streaming session reset at +4.044s. Therefore control-service overlap is not a sufficient cause.
- In v35 extra audio RECORD succeeded but two first sessions still reset at +2.02s. Video opcode-2 keepalive was actually written about 495ms before first RST, but did not prevent reset. Media gate, lower fps and audio start delay were also ineffective; all are off by default.
- Receiver playback feedback type=100 sampleTime continued to advance until first disconnect; no evidence for frozen audio clock. IDR can be large on a failed session, so 715B first-IDR is not proof of faulty AVC.
- catplay-labs/catplay: after initial SETUP receiver enters PreRecord, RECORD transitions to PostRecord, and screen SETUP is permitted in either state (receiver.rs lines 444-452, 554-570). Therefore our old RECORD→screen SETUP ordering is legal on some receivers.
- jjuugk/CarPToCarL: actual receiver-specific workaround orders initial screen SETUP→video dataPort TCP→RECORD; client.assertModes() sends modesChanged before screen SETUP, validated on some Audi receivers. This is not necessarily mandatory for Linux DiPlay, hence separate opt-in tests.
- openxplay/openxplay-relay: receiver session activation on RECORD is distinct from main-screen SETUP and a rendered-frame event; its FirstTcpWatchdog defaults to a 30-second first TCP budget and has optional post-accept deadline, not proof of our 2/4-second timeout.
- lvalen91/CPC200-CCPA_resources documents a real wireless iAP2→Wi-Fi→HomeKit flow, but for a different receiver on TCP 5000. It does not establish a uniform RTSP sequence or timeout for the user's Linux 10.85.189.9:7000 receiver.

## Version policy

Default v37 is exactly the default v36 protocol. No protocol experiments active unless setprop to 1. v36 Bonjour wait remains OFF; v23 IPv4 rapid gateway, v29 owner, v31 event demux, v32 codec lifecycle and v34 0x4301 recovery retained. v35 post-audio RECORD, video screen KA, v34 gate and v33 delay/fps stay OFF. v36 reduced diagnostics stays.

## Experimental modes (mutually exclusive)

- debug.carplay.v37_claim_before_screen=1: AFTER existing first RECORD and event channel setup, POST /command modesChanged over encrypted control to explicitly claim main screen resource 1 and main audio resource 2 for phone, BEFORE type-110 screen SETUP. Require RTSP 200. Do not change first RECORD timing; do not change source identity. Audi MIB3 excluded.
- debug.carplay.v37_record_after_screen=1: OMIT first RECORD before type-110 SETUP; perform type-110 screen SETUP, CONNECT video dataPort TCP, THEN RECORD and only then reset media clock/start AVC and audio. Matches the CarPToCarL-inspired order, without changing AUDIO SETUP, stream body, video header or encryption. If RECORD rejected, stop session and close egress. Audi MIB3 excluded.
- Both flags at 1: refuse the combination and log error (to protect experiment validity). No change to default session path.

## Test (stationary vehicle, run each twice in isolation)

Set common flags first in Android root terminal:
```sh
su -c 'setprop debug.carplay.v36_ctrl_quiet_ms 0; setprop debug.carplay.v35_post_audio_record 0; setprop debug.carplay.v35_screen_ka 0; setprop debug.carplay.v34_media_barrier 0; setprop debug.carplay.v33_video_fps 0; setprop debug.carplay.v33_audio_delay_ms 0'
```
BASELINE: setprop debug.carplay.v37_claim_before_screen 0; setprop debug.carplay.v37_record_after_screen 0
A / MODES: setprop debug.carplay.v37_claim_before_screen 1; setprop debug.carplay.v37_record_after_screen 0
B / RECORD: setprop debug.carplay.v37_claim_before_screen 0; setprop debug.carplay.v37_record_after_screen 1

After flags, execute:
```sh
su -c 'am force-stop io.github.nitsuya.aa.display'
su -c 'logcat -c; logcat -b main -b system -v threadtime -s AADisplay_CarPlay:V WifiClientModeImpl:I wpa_supplicant:I "*:S" -f /sdcard/Download/v37_test.txt'
```
Reopen app and connect; capture the first RST and subsequent reconnection, then Ctrl+C. Rename log for each test: v37_baseline.txt, v37_modes.txt, v37_record.txt. EXPECT: v37-options, v37-modes-before-screen success=true, or v37-record-after-screen success=true; compare time from 0x4301, encrypted SETUP, screen dataPort, first IDR, feedback sampleTime, RST and Wi-Fi disconnection.

## Limits and possible receiver-side root causes

- A receiver-originated TCP RST is proven by an earlier synchronized packet capture, but does not prove the Linux process crashed. It might be receiver state timeout, competing session, delayed MFi callback, resource arbitration, broken screen decoder or an explicit session policy.
- Multiple receiver implementations differ. None of the reviewed public repos is confirmed to be the exact Linux DiPlay firmware. Only receiver logs or control-message captures on the HU can name its final teardown cause.
- Never enable both flags. If an experiment worsens connection, turn it off and restart. A failed test is useful protocol evidence, not a reason to make experimental ordering default.

## Links

- https://github.com/catplay-labs/catplay/blob/master/carplay/catplay_carplay/src/carplay_rx/sink/receiver.rs
- https://github.com/openxplay/openxplay-relay/blob/main/rust/carplay-airplay/src/air_play_session.rs
- https://github.com/openxplay/openxplay-relay/blob/main/rust/carplay-airplay/src/first_tcp_watchdog.rs
- https://github.com/jjuugk/CarPToCarL/blob/main/docs/PROTOCOL-NOTES.md
- https://github.com/jjuugk/CarPToCarL/blob/main/app/src/main/java/io/github/shaonialife/carptocar/airplay/AirPlayClient.kt
- https://github.com/lvalen91/CPC200-CCPA_resources/blob/main/documentation/02_Protocol_Reference/wireless_carplay.md
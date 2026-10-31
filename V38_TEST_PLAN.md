# AADisplay CarPlay v38 — continuous first-media-audio RTP A/B

## Goal
Isolate one confirmed sender defect observed in the v35–v37 logs: after the first
type-100 PCM media RTP packet, the sender deliberately goes silent for 1,200 ms
and then transmits packets at 22 ms intervals for eight seconds, despite each
packet carrying 960 frames of 48 kHz PCM (= 20 ms of audio). This is a targeted
experiment, **not proof that the head unit's TCP RST cause is fixed**.

## Changes from v37
- Apply **after** the complete v2…v37 patch chain from the pinned upstream commit.
- On non-AAC media PCM egress, default to 20 ms per packet, with no post-first-packet
  1,200 ms pause and no 8 s soft-pace. Preserve the existing monotonic pacer,
  no-burst late-packet discard, media clock, RTP headers, encryption and packet size.
- New optional property `debug.carplay.v38_legacy_audio_pause=1` restores the old
  1,200-ms post-packet pause and 22-ms soft-pace to make a controlled A/B comparison.
- No changes to v23 fast IPv4 gateway readiness, v29 owner control, v31 demux,
  v34 recovery history, video, iAP2, RTSP message order, Bonjour, Wi-Fi or audio
  CODEC. All historical experiments retain their previous defaults.
- Increment app versionCode to 3138 and versionName to `0.3#17.8-v38`.

## Recommended CarUp / FreeAuto controlled tests
On the root Android phone, keep **v37 modesChanged A enabled** in both conditions
so *only the v38 audio pacing bit differs*.

**Experiment T — continuous audio (new default):**

```sh
su -c 'setprop debug.carplay.v37_claim_before_screen 1; setprop debug.carplay.v37_record_after_screen 0; setprop debug.carplay.v38_legacy_audio_pause 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
su -c 'logcat -c'
su -c 'logcat -b main -b system -v threadtime -s AADisplay_CarPlay:V WifiClientModeImpl:I wpa_supplicant:I "*:S" -f /sdcard/Download/v38_continuous.txt'
```

Run the logcat command in one terminal; launch the app and connect the vehicle
while it is recording. Use Ctrl+C to stop. Run at least 3 separate first-attempt
connections, ideally after fully resetting the car receiver between runs.

**Experiment C — legacy pacing control:**

```sh
su -c 'setprop debug.carplay.v37_claim_before_screen 1; setprop debug.carplay.v37_record_after_screen 0; setprop debug.carplay.v38_legacy_audio_pause 1'
su -c 'am force-stop io.github.nitsuya.aa.display'
su -c 'logcat -c'
su -c 'logcat -b main -b system -v threadtime -s AADisplay_CarPlay:V WifiClientModeImpl:I wpa_supplicant:I "*:S" -f /sdcard/Download/v38_legacy.txt'
```

Keep all other `debug.carplay.*` flags at their v37 baseline. To rule out another
enabled experiment, check using `getprop | grep debug.carplay`.

**Expected audit records:**
- New: `v38 audio cadence profile=media mode=continuous-20ms`.
- Control: `v38 audio cadence profile=media mode=legacy-pause-1200ms-soft-22ms`
  followed by `audio HU settle pause 1200ms` and `audio soft-pace 8000ms`.
- Count first RTP sends, RTSP control worker resets, Event resets, and RFCOMM
  close order. Do not infer head-unit cause from `Connection reset` alone.

Do **not** enable both v37 claimBeforeScreen and recordAfterScreen; they are mutually
exclusive. For a second receiver type (DiPlay), repeat the identical two-condition
comparison with the v37 claim flag held constant.

## Interpretation
- If first-connect resets disappear only for continuous audio, the old audio gap
  is implicated and can be retired.
- If both conditions still fail, do not change RTSP ordering. Capture receiver-side
  logs / TCP reset attribution; next independent tests could investigate RTP packet
  fragmentation (960 vs 352 frames) or audio-control NTP anchors.
- If the 2-second failure improves but ~15-second RFCOMM-first failure remains, treat
  that as a separate iAP2/event transport question.

## Source references
- Sender baseline: `lagXkjy/AADisplay` pinned `494dcc4909e8765e8798be4e7b8031fefd90a4eb`.
- Reference sender PCM pacing: `shaonialife/cardeck` AudioSender.kt;
  `catplay-labs/catplay` rtp_session_tx.rs.
- Relevant logs: v36 baseline, v37 modes A/B, and v37_A_bluetooth.txt.

# AADisplay CarPlay v39 — remove empty wireless TCP probe

## Finding verified in both sides' logs
On **DiPlay 0.2.22 (OPPO PKJ110)**, the sender opened a short-lived TCP
connection to the head unit's AirPlay RTSP port 7000, then closed it without
sending RTSP. The DiPlay log recorded `airplay control closing reason=peer EOF
activeStreams=[]`, followed by `AirPlay session ended; retrying in ...ms`.
The **real** AirPlay connection then succeeded and rendered video; however,
the old scheduled reconnect fired and tore down the live session.

DiPlay's current `CarPlayHostActivity` tracks a `pendingReconnect`, and
`onSessionActive` resets the retry counter without clearing that pending task.
A receiver-side fix should ignore empty probe sessions and cancel stale pending
reconnects on new active sessions. This v39 APK **fixes the sender-side trigger**
without needing to modify the third-party DiPlay app.

## Exactly one runtime behavior changed versus v38
- In `CarPlaySourceSession.kt` (0x4301 StartSession primary dial path), the
  **wireless** path no longer calls `CarPlayAccessoryNet.openTcp().connect()`
  just to immediately close that socket. The first wireless connection to port
  7000 now goes straight to the real AirPlay/RTSP session.
- The original wired or loopback preflight is unchanged.
- Keep the preflight reproducible via the optional property
  `debug.carplay.v39_legacy_tcp_probe=1`. **Default 0 = fixed mode.**
- All v2–v38 patches still apply, and v23 quick IPv4 gateway readiness, Wi-Fi
  rebind, fallback logic, codec, audio cadence and RTSP message ordering stay
  the same. `versionCode=3139`, `versionName=0.3#17.8-v39`.

## First test (default, no empty probe)
Root Android terminal:

```sh
su -c 'setprop debug.carplay.v39_legacy_tcp_probe 0; setprop debug.carplay.v38_legacy_audio_pause 0; setprop debug.carplay.v37_claim_before_screen 0; setprop debug.carplay.v37_record_after_screen 0'
su -c 'am force-stop io.github.nitsuya.aa.display'
su -c 'logcat -c'
su -c 'logcat -b main -b system -v threadtime -s AADisplay_CarPlay:V WifiClientModeImpl:I wpa_supplicant:I "*:S" -f /sdcard/Download/v39_first.txt'
```

With logcat running, start DiPlay and the phone client after a receiver reset.
Keep streaming for at least 45 seconds, then stop logcat using Ctrl+C.
Repeat cold starts 3 times where possible, collecting the DiPlay diagnostic
report immediately after a failure.

Expected sender:
`v39 skip standalone TCP probe wireless <address>:7000; real RTSP dial only`
and **no** `v6 TCP probe begin` or preflight success in the wireless path.

Expected receiver:
- No abandoned probe-only TCP connection preceding the *real* /info request
  from this sender.
- No `AirPlay session ended; retrying in ...ms` scheduled on such a probe.
- No premature 2/4/8/16-second teardown when real media is healthy.

## Controlled regression test (only if needed)
Set `debug.carplay.v39_legacy_tcp_probe 1` and restart the app while
all other `debug.carplay.*` flags are identical. The sender then opens
and closes the old preflight socket. A/B the first-cold-connect outcome.

## Interpretation
- If the first attempt now remains stable, stale retry from empty TCP probe
  was the root cause for this receiver's first disconnection.
- If a disconnection remains, inspect same-time DiPlay report for any
  other probe or independent session closure. Do not infer cause from an
  unrelated packet capture or just a TCP RST.
- Bluetooth pre-RFCOMM delay and an Android MODIFY_PHONE_STATE exception
  are **separate issues**, not fixed by this change.

## Relevant source
- Sender pinned source: lagXkjy/AADisplay, commit
  `494dcc4909e8765e8798be4e7b8031fefd90a4eb`,
  `aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlaySourceSession.kt`.
- Receiver: shihabal3amri/DiPlay,
  `common/src/main/java/com/shilapi/xcertplay/CarPlayHostActivity.kt`.
- Captured diagnostics: `DiPlay-20261031-161131-869.txt`,
  `v38_continuous.txt`, `v38_tcp_rst.pcap`.

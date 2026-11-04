# AADisplay CarPlay v59 — faster video-only recovery after long reverse

## Evidence from v58 capture on 2026-11-04
- Audio and CarPlay control stayed connected while video was black.
- Old screen TCP dataPort 35741 remained ESTABLISHED; Send-Q grew from 94,597 B to 391,068 B in ~11 s, but bytes_acked stayed at 490,467.
- Hardware AVC encoder continued producing frames.
- At 20:02:56 v58 screen-only recovery negotiated new dataPort 44423 (RTSP 200), sent CONFIG + IDR, then screen recovered.
- These facts implicate video dataPort backpressure / receiver-side consumption; no proof of the receiver's internal fault.

## v59 narrow changes
1. Video socket only: request SO_SNDBUF 128 KiB *before* connect so a receiver that stops reading causes sender backpressure to become visible sooner. Log actual kernel buffer size; SO_SNDBUF is only a hint.
2. Bounded v57 sender queue tracks successful Socket.write completion. If there are pending AUs but no successful completion for >3.5 s, begin v58 recovery evaluation. Empty queue is not considered stalled.
3. Arm one delayed 4 s probe on explicit requestUI, MainScreen restore (UNBORROW), or first encoder output after HU ownership ends. The probe is single-flight and de-bounced 8 s; refuses to act if HU currently owns MainScreen. No permanent polling.
4. Reuse v58's verified video-only RTSP type 110 SETUP/IDR path; keep AAC, pairing, event, keyboard, virtual displays, and full CarPlay control connection unchanged. v58 still applies 12 s recovery cooldown.
5. Preserve all v23 IPv4, v29 single-session, v31 event splitting, and v38–v40 connection stability fixes.

## A/B switches (set before starting a fresh session)
- New return probe OFF: `su -c 'setprop debug.carplay.v59_video_probe 0'`
- Video buffer cap OFF: `su -c 'setprop debug.carplay.v59_video_sockbuf_kb 0'`
- Default buffer: 128 KiB. Advanced 256 KiB alternative: `su -c 'setprop debug.carplay.v59_video_sockbuf_kb 256'`
- Entire v58/v59 recovery OFF: `su -c 'setprop debug.carplay.v58_video_recover 0'`

These flags do not persist across reboot. Reconnect CarPlay after changing them. Leave other debug flags at defaults.

## Testing while safely parked
1. Install debug APK, restart and confirm initial video, audio, Gboard/IME, QQ/Soda lyrics and normal controls.
2. Camera reverse 10s, 30s and 60s. After camera exits, measure time until video appears. Ensure backup-camera display is not obscured.
3. Repeat HU HOME -> CarPlay. Watch for extra unwanted screen SETUP during normal video.
4. Capture with existing v58 reliable script. Key log labels:
    - `v59 video SO_SNDBUF`
    - `v59 return probe ... stalledMs`
    - `v58 video-only recovery start ...`
    - `v58 video-only recovery result=true`
    - `v57 video TCP sender potentially blocked`
5. If video stutters, compare v59 send-buffer 128 KiB vs 256 KiB (restart session), and include Wi-Fi RTT/Send-Q in log.

## Important limits
- v59 is based on strong kernel-level evidence, but only real HU hardware testing can prove the latency improvement.
- Kernel SO_SNDBUF may round/clamp the requested value; actual value is logged.
- Source-side detection cannot directly read HU decoder state. This patch intentionally does not rebuild the video encoder or full session.

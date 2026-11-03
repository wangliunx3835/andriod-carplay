# v57 Nonblocking AVC output-buffer release
Includes all v2–v56 patches, QQ/Soda lyrics, independent floating dimensions and 430ms rolling lyrics, v55 MainScreen requestUI re-entry.

## User log evidence
At 21:43:53 MainScreen 1/1 and modesChanged 200; at 21:43:57 MTK CCodecBuffers output stash 11->16; at 21:43:59 black-screen mark while AAC audio continues; at 21:44:11 MediaCodec encode 0, DQout 0. The v32 drainOnce already copies and releases each MediaCodec output buffer before invoking onEncodedAccessUnit. However that callback synchronously writes and flushes TCP on the same drain thread, potentially blocking the next dequeue. Socket backpressure is plausible but not proven by a Java thread dump.

## Fix
- The preexisting v32 drainOnce releases output before the callback; v57 sends copied output to an 8-frame bounded queue instead of waiting for socket writes. A single daemon video writer invokes unchanged sendVideoAccessUnit/ScreenStreamEgress, preserving TCP per-frame flush, packet order, AirPlay H264 CONFIG and ChaCha nonce progression.
- Full queue discards obsolete queued non-CONFIG AVC frames, waits for a new IDR, retains codec CONFIG. Natural 1-second keyframe interval allows resynchronization. No unbounded memory use, no per-frame thread launch.
- On encoder stop/restart, pending queue is cleared and generation incremented, preventing old queued frames from leaking to new codec instance. On egress close the TCP socket is closed before BufferedOutputStream so blocked output is interrupted.
- Does not change AirPlay pairing, RTSP exchanges, event modes, reverse priority, sender codec parameters, audio, keyboard, split displays or lyrics/overlay.

## Test on stationary vehicle
1. Install/reboot, test normal CarPlay 2min with audio and lyrics. Repeated native HU HOME and parked reverse return 10x.
2. Watch if black-screen with audio persists; if yes, run existing v56_black_video_capture.sh while testing (valid for v57). Capture a filtered log:
su -c 'logcat -d -b main -b system -t 25000 -v threadtime | grep -Ei "v57|AADisplay_CarPlay|CCodecBuffers|video-debug-enc" | tail -n 700 > /sdcard/Download/v57_avc_log.txt'
3. Interpretation: v57 AVC drain protected warnings indicate HU video TCP writes are backpressured; v57 video socket write delayMs reports completed slow sends. Codec encode count should keep increasing even during a temporarily blocked HU video sink.

## Important limitation
This isolates codec from a slow socket; it does NOT implement unsafe automatic re-SETUP while an authenticated stream is active. A receiver that permanently stops reading the existing video connection can still need a negotiated screen SETUP; logs will guide that second-stage change. Build success alone does not prove in-car restoration.

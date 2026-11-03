# AADisplay CarPlay v57 — MTK AVC drain / TCP video backpressure

Base: pinned upstream plus apply_v2 .. apply_v56. Includes v55 guarded requestUI MainScreen reclaim, v56 floating media independent width/height and 430ms double-line rolling lyric; preserves all CarPlay handshake, reverse priority, codec configuration, audio, IPv4 quick readiness, IME.

## v56 actual black-screen log — 2026-11-03
- 21:43:53: v55 requestUI screen=1/1 reclaimed=true, modesChanged response 200 OK.
- 21:43:57: MediaTek c2.mtk.avc.encoder output stashed 11 -> 16 buffers.
- 21:43:59: user marked black; audio and event traffic continued.
- 21:44:11: codec log encode:0, DQout:0/0.
- No direct socket blocking stack trace: synchronous TCP flush in onEncodedAccessUnit is the code-supported hypothesis, not yet independently proven.
- Existing synchronous chain: CarPlayVideoEncoder.drainOnce -> callback -> CarPlayRtspSession.sendVideoAccessUnit -> ScreenStreamEgress.sendVideo -> Socket BufferedOutputStream.flush.

## v57 changes
- Keep hardware codec drain nonblocking by moving H264 transmission to one ordered network worker (no parallel crypto writers).
- Queue bounded to 32 encoded access units. When queue overflows, drop entire queued old GOP, retain newest queued codec CONFIG, reject subsequent P frames until next IDR and request new IDR (>=1.5 seconds apart). This avoids handing the receiver an arbitrary broken P-frame dependency chain.
- Queue resets on RTSP screen re-SETUP and release; keep stream generation number to discard stale pending frames.
- Close video Socket before buffered stream on teardown; a blocked network write should be unblocked instead of waiting for a close-time flush.
- New log labels: v57 async video enabled, v57 video queue overflow, v57 slow video TCP send, v57 video TCP sender potentially blocked, v57 video queue reset.
- No forced RTSP reconnect, midstream codec CONFIG resend, audio reset, changed screen ownership, additional VDs, or cyclic watchdog.

## A/B fallback
Disable new worker via root BEFORE new CarPlay RTSP session:
su -c 'setprop debug.carplay.v57_async_video 0'
Enable again:
su -c 'setprop debug.carplay.v57_async_video 1'
The setting is read per RTSP object creation, so fully stop/restart AADisplay CarPlay (or reboot) after changing it.

## Parked testing
1. Install, reboot and connect CarPlay. Test HU home->CarPlay return, reverse camera->CarPlay return, QQ/Soda lyrics, cover, rolling lyrics, floating media sizing and normal audio.
2. Repeat switching 3-5 times while vehicle safely parked. If black, observe whether audio, media overlay and split divider remain.
3. Export filtered log:
su -c 'logcat -d -b main -b system -t 30000 -v threadtime | grep -Ei "AADisplay_CarPlay.*(v57|v55 requestUI|MainScreen|changeModes|modesChanged|screen CONFIG|screen VIDEO|screen dataPort|releaseMediaStreams|GL|AVC)" | tail -n 650 > /sdcard/Download/v57_video_filtered.txt'

## Limits
A successful CI build does not prove the receiver can resume if its video decode pipeline itself is wedged. This patch prevents the sender's network backpressure from blocking the encoder but does not forcibly recreate a dead receiver-side decoder.

# v61 — video peer-FIN recovery and Soda car metadata/lyrics

## Evidence
- v60 black snapshot from 2026-11-05 08:30:53: CarPlay RTSP control TCP port 7000 remained ESTAB; an AADisplay TCP connection toward HU port 48478 was CLOSE-WAIT. The latter is consistent with peer FIN, but on-device socket identity should still be verified.
- At 08:30:57, delayed check returned stalledMs=0, closed=false and did not repair.
- At 08:31:07, screen-only SETUP type 110 returned RTSP 200; new video dataPort 35491 transmitted CONFIG+IDR; image recovered.
- v54 already included com.luna.music.car in LSPosed scope and provider allowlist, yet old hook depended on platform MediaSession and app-specific TrackLyric classes.

## v61 video: no new periodic polling
- After backupCamera UNBORROW, existing v59 delayed one-shot worker probes sender-only type-110 TCP input with SO_TIMEOUT 35ms. EOF means HU has sent FIN even if Java socket.isClosed is false.
- A missing video egress, a closed socket, or verified remote FIN can now trigger the existing v58 video-only SETUP. Keep v60 >5.5s camera exit guard, on-demand probe ~6s, retries and all audio/control unchanged.
- Debug A/B opt-out for read probe: setprop debug.carplay.v61_peer_fin_probe 0, then reconnect CarPlay.
- Do not probe during active backupCamera BORROW or from codec output thread. Actual receiver decoder health remains unknowable without receiver telemetry.

## v61 Soda car: separate title/cover/lyrics paths
- Existing hook supports com.luna.music / com.luna.music.car. Several third-party listings use both names for what they call a car version; verify installed package locally with pm list packages.
- Continue to use platform MediaSession.setMetadata first. For com.luna.music.car only, add event-triggered NotificationManager.notify interception for MediaStyle notifications containing title, artist, and large icon; deduplicate each song/artwork. No periodic UI scanning or network lyric scraping.
- MediaMetadata lyricInfo JSON is unwrapped to the actual lyric string before parsing; support android.media.metadata.LYRICS, lyrics and lrc keys.
- Prefer current com.luna.music.car metadata over a stale Settings.Global ticker belonging to a different player.
- Raw lyric is still available only when the car app or another provider exposes it as LRC/KRC or lyricInfo. No proof the car APK exposes compatible lyric classes; titles and covers may succeed without lyrics.

## CPU/battery
- Cache LRC parse timeline per unchanged body instead of parsing/sorting ~every 650ms.
- Stop repeated privileged Bluetooth setScanMode calls once denied in a session. Keep standard media feedback, auto-connect and ongoing playback.
- Preserve v28/v40 defaults disabling GPU diagnostic captures and unnecessary feedback processing.

## Test
1. Safely parked, install v61 and fully restart CarPlay. Check camera 15/45/60s, then HU return time. No camera flicker.
2. In root terminal: pm list packages | grep -i -E 'luna|music.car'
3. In LSPosed, enable AADisplay for the actual installed Soda car app package (not just com.luna.music if actual package is com.luna.music.car), and restart that app.
4. Play/skip tracks. Check the floating card song title, artist, cover, and individual/next lines separately. On first run you may need to re-enable the media overlay if disabled.
5. If song and artwork now appear but lyrics do not, collect a short rooted media_session + logcat snapshot using tools/v61_soda_diag.sh. Do not upload the proprietary APK unless you explicitly choose to provide it for deeper analysis.
6. Video debug: v61 return probe reports egressMissing / egressClosed / peerFin. Upload previously working v58_black_capture_reliable.sh results if black remains.

## Scope
Full historical patches v2..v60 remain intact; v23 IPv4 gateway, v29 session, v31 Event channel, v39-v40 stable connection, and v51 IME/audio changes are preserved.

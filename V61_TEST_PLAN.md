# AADisplay CarPlay v61 — long-reverse screen & QiShui car music

## Known black-screen evidence
- v60 camera UNBORROW 08:30:51.399; v59 one-shot probe 08:30:57.421 reported `stalledMs=0`, yet user confirmed screen black.
- v60 screen-only re-SETUP 08:31:07 returned RTSP 200 and delivered SPS/PPS and IDR; picture recovered at ~08:31:09.
- Kernel socket may stay ESTAB with Send-Q=0 even while decoder shows black; software lacks receiver-side displayed-frame ACK.

## v61 test intervention
- If **backupCamera MainScreen BORROW lasts 8 seconds or longer**, perform ONE video-only re-SETUP on the normal delayed return probe (~6s after UNBORROW), even if socket reports no blocked sender.
- Respect `backupCamera` ownership and v60 >=5.5s receiver-settle guard, v58 single-flight and cooldown. No full CarPlay restart, no audio/IME reconfiguration, no permanent watcher.
- Short camera visits (<8s) do not cause proactive setup. No default screenshot or high-volume log capture.
- This trial may cause one short video transition if the HU already recovered by itself; the receiver does not expose display-state ACK.

## Dedicated QiShui car version
- Public distributions include `com.luna.music.car` as a **different package** from `com.luna.music` mobile. Other so-called car editions still use `com.luna.music`; verify the package installed on your device.
- Add `com.luna.music.car` to LSPosed scope and UID allowlist.
- Add car-specific listener of Android MediaSession metadata/playback state plus a MediaStyle notification fallback, and known TrackLyric / timed-LRC models if present.
- Send song/artist and bounded 320-pixel JPEG artwork to the existing private bridge. Decode JPEG only on revision change. No cloud lyric API, no app-wide TextView interception, no network sniffing, no persistent capture.
- **Limits:** no installed car APK was provided to inspect, so app-internal lyric classes are conditional. A build pass does not guarantee the car build exposes timed lyrics through a public MediaSession key or the known TrackLyric class. If title works but timed lyrics remain missing, acquire a scoped diagnostic from the actual APK.

## LSPosed and test
1. Install v61; open LSPosed module scope, ensure **com.luna.music.car** is selected if installed, retain app/system/QQ scopes already working; restart QiShui car app and AADisplay.
2. In Android terminal run `su -c 'pm list packages | grep -i luna'` to confirm which QiShui package is installed.
3. Play a QiShui car track while parked. Check title, artist, cover and current/next lyric; check whether `AAD_V61Car: v61 car source active`, `v61 car metadata`, `v61 car cover`, `v61 car lyric model` appear in `logcat -d`.
4. Reverse for ~10, ~30, ~60s while safely parked, return to CarPlay, check whether picture comes back by the six-second probe and whether camera remains stable. Test 3s reverse for regression.
5. Check QQ and mobile QiShui still work and prior stable connection/audio/IME behavior is preserved.
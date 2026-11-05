# AADisplay CarPlay v62 — QiShui car cross-process music IPC repair

## Evidence from v61_dual_20261105_092435.tar.gz
- The tester installed versionCode 3161 at **09:07:23**, before the final v61 Release was published at 09:17:31. The log used the older AAD_V53Lyrics car MediaStyle branch; it does NOT validate the final v61 long-camera-return video refresh.
- Installed car app: `com.luna.music.car` version 1.1.35. Android's media_session dump shows an ACTIVE session, PLAYING, complete title and artist.
- From 09:20:38 onward, `ContentProviderHelper: Can't resolve content provider io.github.nitsuya.aa.display.lyricv53`, followed by `AAD_V53Lyrics: IPC error IllegalArgumentException`. The metadata/cover/lyrics bridge was inaccessible to this target-30 music app. Potential causes include package visibility and provider resolution; missing data is not proof the app publishes none.
- Old v61 video: UNBORROW 09:20:01.859, peerFIN=false at 09:20:07.907, 2.5s dataPort sender block at 09:20:20.872, RTSP 400 at 09:20:20.881, RTSP 200 at 09:20:24.887, new CONFIG/IDR at 09:20:24.944/947, recovered marker 09:20:27. Video is unchanged from the separately published FINAL v61 in this v62 hotfix.

## v62 changes
- Car-only (com.luna.music.car) metadata/position/LRC/JPEG now use a fixed-component explicit broadcast on Android 14+, with BroadcastOptions.setShareIdentityEnabled(true). Receiver checks the system-provided sender UID and package against PackageManager. It refuses unknown UID, unrecognized package, absent identity and malformed/oversized payload. No general-purpose exported feed.
- Reuse the existing v54 private artwork cache and v53 bounded lyric SharedPreferences. Old mobile/QQ/Netease ContentProvider pathway is untouched. API 33 retains legacy behavior.
- No new timers, polling, screen capture, audio, MediaCodec, CarPlay handshake or RTSP changes. All v23 IPv4, v29 single session, v31 Event, v38-v40 connection, v51 IME/audio and final v61 reverse-protection retained.

## Validation
1. Install v62. Restart the QiShui car app process completely (force-stop + launch) so LSPosed loads `AAD_V61Car`, not `AAD_V53Lyrics`.
2. Enable AADisplay LSPosed scope for the independent car package `com.luna.music.car`, and enable media overlay.
3. Play a track. Check `logcat -d -s AAD_V61Car AAD_V62Media` for **`v61 car source active`**, **`car new song metadata received`**, and **`car cover received bytes=`** (if a cover is provided). No repeating `Failed to find provider info` should arise from the car hook.
4. Check title/artist/album art first, then lyric lines separately. The log's `Soda lyric ctor absent` and `TrackLyric absent` leave lyrics dependent on player-provided metadata/LRC, not yet guaranteed.
5. Park safely, test 15/45/60-second reverse to evaluate final-v61 video refresh. Upload a newer video log only if it still blacks out; this music-only hotfix does not claim to fix that hardware issue.

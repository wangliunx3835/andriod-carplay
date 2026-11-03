# v53 experimental music-app lyrics capture

Based on v52r1, all connection/RTSP/iAP2/video/audio/reverse/Gboard/input/wheel code unchanged.

Upstream AADisplay is not an AVRCP Bluetooth packet extractor: it reads MediaSession LYRIC, writes current line as MediaInfo title, sends via AA or iAP2 NowPlaying. Source: upstream docs/CLUSTER_LYRIC_CLOCK.md, LyricLineExtractor, CarPlayNowPlaying.

v53 introduces app-scoped read-only Xposed observation of music MediaSession.setMetadata and setPlaybackState for Soda, QQ, Netease and QQ car/HD. Soda also observes in-process raw Lyric constructor and TrackLyric getter/setter, informed by HChenX/SuperLyric research. The raw bounded payload (max 64k chars) enters a UID-checked application ContentProvider; the existing media overlay uses it to display current and next LRC/KRC line. This is *not* fake Bluetooth pairing; if the application requires real A2DP before producing its lyrics, no lyrics may be captured. App hooks are version sensitive.

Test: install v53, reboot, **add the music app packages to the LSPosed scope of AADisplay**. Keep android scope. Force-stop/restart music app; open its native lyric screen, play a track and watch floating media. Run on phone root terminal:

su -c 'logcat -d -t 12000 -v threadtime | grep -Ei "AAD_V53Lyrics|Soda lyric|Soda TrackLyric" | tail -n 150 > /sdcard/Download/v53_lyrics_filtered.txt'

Upload the filtered log and report the music app version and whether song title/current/next lyric appeared. No lyric text is written to logcat.

Do not combine with Fake Bluetooth Connect during the first A/B experiment. QQ and Netease may require private app-specific hooks later. The previous v52 fallback remains available and the overlay can be disabled in the phone AADisplay settings.

Sources: https://github.com/HChenX/SuperLyric ; https://github.com/liuran001/Fake-Bluetooth-Connect ; https://github.com/lagXkjy/AADisplay
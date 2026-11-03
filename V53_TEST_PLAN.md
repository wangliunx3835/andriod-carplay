# v53 raw lyric interception experiment

Based on v52r1. CarPlay connection, Bluetooth service, video encoder, audio routing and reverse-camera code remain unchanged.

LSPosed: enable AADisplay for 汽水音乐 com.luna.music (plus original framework scope); force stop and reopen Soda after enabling. No fake A2DP is performed. For QQ official and NetEase, only probe MediaMetadata.Builder.putString lyric keys. Actual Soda uses Lyric entity constructor raw KRC/LRC parameter. App provider verifies calling music package UID and logs only length and format, not words.

Enable floating media in phone settings. If live caption does not appear, capture log: su -c 'logcat -d -t 12000 -v threadtime | grep -E "AAD_V53Lyric|AAD_ClusterLyricMirror" | tail -n 180 > /sdcard/Download/v53_lyric_log.txt'. Test with Soda lyric page visible and hidden; note package version. Some apps generate lyric payload only after visible lyric page and some preload future tracks. This validation version cannot promise all apps support or full correct track identity.

Open-source references: HChenX/SuperLyric soda raw lyric constructor & per-song stash (GPL reference, not copied); liuran001/Fake-Bluetooth-Connect app-side audio query emulation (not enabled due to CarPlay audio-safety); tomakino/lyricon; ColorOS provider plugins for QQ/NetEase.

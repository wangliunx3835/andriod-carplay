# v54 Floating Media Improvements

Based on v53. Does NOT modify CarPlay pairing, RTSP, iAP2, codec, reverse video gate, audio reset, IPv4 readiness or steering wheel HID mapping.

- Support com.luna.music.car as well as com.luna.music in Xposed scope, intake provider and optional Soda internal lyric hooks. Many landscape car-labelled APKs still use com.luna.music; check installed package.
- Use a single AudioManager pair (DOWN+UP) for floating controls. Never route through the existing wheel method that uses CoreApi + AudioManager. Use explicit PLAY or PAUSE rather than PLAY_PAUSE, chosen from observed playback state.
- Center lyric text in the space between cover and controls; when controls hide recompute the center.
- Offer independent current/next lyric colors in AADisplay phone setting, strengthen theme tint, draw low-cost frosted-glass appearance with layered gradient (not a true GPU backdrop blur).
- Observe music session ART / ALBUM_ART bitmap; downscale and publish a bounded JPEG to UID-checked provider, cache and decode off GL draw thread. Fallback to existing cluster cover.

### Setup
Install and reboot Android. In LSPosed AADisplay scope select com.luna.music.car if it actually exists as installed package, plus other music apps you test, preserve android/system scope. Restart those players. Open phone AADisplay > floating media settings, test active cover, lyric colors, paused-state buttons, six-second auto-hide, resizing and draggable position. Test reversing, Gboard and disconnection audio as regression.

### Diagnostics
Use this command *while testing*, not after a long idle session:
```sh
su -c 'logcat -d -b main -b system -t 30000 -v threadtime | grep -Ei "AAD_V53Lyrics|AAD_V54Media|v54 media dispatch|Soda lyric|Soda TrackLyric|LSPosed" | tail -n 200 > /sdcard/Download/v54_media_log.txt'
```
If filtered output is empty, inspect LSPosed module logs and normal unfiltered logcat. An empty filtered file is not evidence the code is inactive. Music-app privacy and installed-version compatibility must be checked on-device.

### Caveats
Cover may be absent if a player publishes only a media-art URI and no bitmap; this build uses ART/ALBUM_ART bitmaps. 'Frosted' means translucent gradient, not real-time sampled blur. Real-time blur requires framebuffer sampling and may impact car GPU/encoder. QQ/Soda metadata may be delayed on some builds.
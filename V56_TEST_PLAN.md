# v56: v55 CarPlay screen re-entry + independent floating-media width and height + scrolling double-line lyrics

Base: pinned AADisplay upstream + v2-v55, including v55's event-channel requestUI MainScreen reclaim after HU TAKE. v56 only changes CarPlayMediaOverlaySettings, CarPlayMediaSettingsUi, and the existing CarPlayMediaOverlay Canvas painter. It does not change Bluetooth, iAP2, RTSP, codec, video egress, camera or audio resources.

## Added in v56
- Independent floating-media **width (70–180%)** and **height (90–180%)** controls, saved in the existing v52 SharedPreferences. Existing global size (65–155%) remains; width/height multiply global scaling. Card always clamps to 88% of output width and 90% of height to prevent offscreen overflow.
- Double-line lyrics: on sequential lyric transitions (previous next -> new current), previous current lyric slides up and fades, previous next lyric rolls up to current with color/size interpolation, upcoming line rises from below. 430ms easing. Changes when seeking/skipping use a cross-scroll; first display, single-line, pause, and track changes render directly.
- No extra animation timer, thread, new decoder, or framebuffer texture. Uses existing frame drawing and Canvas clip to keep lyrics from spilling over artwork or controls.
- Previous v54 lyric colors, gradient theme, cover, play controls, Soda car app scope remain intact.

## v55 included screen-reentry experiment
After HU TAKE (MainScreen 0/0) followed by its explicit requestUI, AADisplay changes MainScreen to phone (1/1), triggers the existing asynchronous modesChanged callback, and requests an IDR. Does not take ownership during outstanding backupCamera BORROW; no polling and no preemptive reclaim. A/B disable:
`su -c 'setprop debug.carplay.v55_requestui_reclaim 0'`
Restore:
`su -c 'setprop debug.carplay.v55_requestui_reclaim 1'`

## Test while vehicle is stationary
1. Install APK, reboot, connect wireless CarPlay.
2. Test native HU HOME -> tap CarPlay twice, and reverse-camera enter/exit. Verify camera is not overwritten and normal CarPlay returns.
3. Open phone AADisplay connection screen -> floating media. Keep global component scaling at 100% initially, independently vary width 70/120/180 and height 90/130/180. Test controls hidden and showing, with and without album cover.
4. Play QQ and Soda music with double-line LRC/KRC and observe current lyric rolling up at transitions; verify no scroll on first display, track skip, pause or single-line mode.
5. If re-entry still fails, collect:
```sh
su -c 'logcat -d -b main -b system -t 30000 -v threadtime | grep -Ei "AADisplay_CarPlay.*(v55 requestUI|changeModes|modesChanged|requestUI|MainScreen|video suppressed|screen VIDEO|screen dataPort|releaseMediaStreams|HU idle cleanup|ensureEncoder|GL bind|attachGl)" | tail -n 350 > /sdcard/Download/v56_reentry.txt'
```
6. Share log and whether new animation/card dimensions worked.

## Scope
GitHub Actions compile/release validates build, **not** actual HU app switching. v55 recovery is still an experiment until confirmed on the actual car. Never test reverse camera changes while driving.

Upstream architecture: https://github.com/lagXkjy/AADisplay .

#!/system/bin/sh
# v61 one-shot QiShui car metadata diagnosis; local root terminal, no daemon.
OUT="/sdcard/Download/V61_QiShui_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT" || exit 1
date > "$OUT/time.txt"
getprop ro.build.version.release >> "$OUT/time.txt"
pm list packages | grep -i -E 'luna|qishui' > "$OUT/installed_music_packages.txt" 2>&1
logcat -d -b main -b system -v threadtime -t 20000 2>/dev/null |
  grep -Ei 'AAD_V61Car|AAD_V53Lyrics|AAD_V54Media|AADisplay_CarPlay.*(v61|v58 video-only|v59 return)' |
  tail -n 800 > "$OUT/carplay_qishui_filtered.txt"
dumpsys media_session 2>/dev/null |
  grep -Ei -A 16 -B 4 'com\.luna\.music|com\.luna\.music\.car|MediaMetadata|active session|PlaybackState' |
  head -n 360 > "$OUT/mediaplayer_sessions_filtered.txt"
echo "v61 diagnostics saved: $OUT"

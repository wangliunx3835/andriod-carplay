#!/system/bin/sh
# One-shot v65 music diagnostics from rooted on-device terminal (no adb).
T="$(date +%Y%m%d_%H%M%S)"
D="/sdcard/Download/V65Lyrics_$T"
mkdir -p "$D" || exit 1
date > "$D/meta.txt"
pm list packages | grep -Ei '^package:com\.luna\.music' > "$D/packages.txt" 2>/dev/null
logcat -d -b main -b system -v threadtime -t 22000 2>/dev/null |
 grep -E 'AAD_V61Car|AAD_V62Media|AAD_V63Lyrics|AAD_V65Lyrics' |
 tail -n 1100 > "$D/car_lyrics_filtered.txt"
dumpsys media_session 2>/dev/null |
 grep -Ei -A 11 -B 3 'com\.luna\.music\.car|com\.luna\.music|MediaMetadata|PlaybackState' |
 head -n 170 > "$D/media_session_summary.txt"
tar -czf "$D.tar.gz" -C /sdcard/Download "$(basename "$D")" 2>/dev/null
if [ -f "$D.tar.gz" ]; then
 echo "Upload $D.tar.gz"
else
 echo "Upload $D/car_lyrics_filtered.txt"
fi

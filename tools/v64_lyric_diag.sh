#!/system/bin/sh
# v64 once-only log collection; uses local root terminal, no adb required.
T="$(date +%Y%m%d_%H%M%S)"
D="/sdcard/Download/V64Lyrics_$T"
mkdir -p "$D" || exit 1
date > "$D/meta.txt"
pm list packages 2>/dev/null | grep -Ei 'com.luna.music' > "$D/packages.txt"
logcat -d -b main -b system -v threadtime -t 20000 2>/dev/null |
 grep -E 'AAD_V61Car|AAD_V62Media|AAD_V63Lyrics|AAD_V53Lyrics' |
 tail -n 1000 > "$D/lyrics_filtered.txt"
dumpsys media_session 2>/dev/null |
 grep -Ei -A 8 -B 3 'com\.luna\.music\.car|com\.luna\.music|PlaybackState' |
 head -n 120 > "$D/session_summary.txt"
ARCHIVE="$D.tar.gz"
tar -czf "$ARCHIVE" -C /sdcard/Download "$(basename "$D")" 2>/dev/null
if [ -f "$ARCHIVE" ]; then
 echo "Upload this entire file: $ARCHIVE"
else
 echo "Please upload $D/lyrics_filtered.txt (not meta.txt)"
fi

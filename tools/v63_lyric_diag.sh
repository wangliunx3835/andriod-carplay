#!/system/bin/sh
# v63 one-shot, bounded lyric transport diagnostics. Root terminal; no adb.
O="/sdcard/Download/V63_Lyrics_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$O" || exit 1
date > "$O/meta.txt"
pm list packages | grep -i 'luna' > "$O/car_package.txt" 2>/dev/null
logcat -d -b main -v threadtime -t 20000 2>/dev/null |
 grep -E 'AAD_V61Car|AAD_V62Media|AAD_V63Lyrics|AAD_V53Lyrics' |
 tail -n 900 > "$O/lyrics_filtered.txt"
echo "Saved to $O"

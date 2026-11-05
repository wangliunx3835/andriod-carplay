#!/system/bin/sh
# One-shot diagnostics: package name and Android MediaSession publication.
# Rooted on-device terminal, no adb, no permanent watcher/logcat recorder.
OUT="/sdcard/Download/v61_soda_diag_$(date +%Y%m%d_%H%M%S).txt"
{
  echo "=== packages $(date) ==="
  pm list packages | grep -Ei 'com\.luna|music\.car|soda'
  echo "=== MediaSessions (selected lines) ==="
  dumpsys media_session 2>&1 | grep -Ein -C 4 'com\.luna\.music|com\.luna\.music\.car|metadata|title=|artist=|album=|PlaybackState' | tail -n 240
  echo "=== relevant recent app/module logcat ==="
  logcat -d -b main -b system -t 4000 -v threadtime 2>&1 | grep -Ei 'AAD_V53Lyrics|AAD_V54Media|v61 car|LyricV53|CarPlayMediaOverlay|v61 return probe|v61 screen TCP peer FIN|v58 video-only recovery' | tail -n 220
} > "$OUT"
echo "$OUT"

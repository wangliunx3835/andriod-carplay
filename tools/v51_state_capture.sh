#!/system/bin/sh
# v51 state snapshot. Does not collect notification text.
P="$1"
case "$P" in connected|disconnected|reconnected) ;; *) echo "use connected|disconnected|reconnected"; exit 2;; esac
[ "$(id -u)" = 0 ] || { echo "root required"; exit 1; }
D="/sdcard/Download/v51_state_$P-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$D" || exit 1
date > "$D/date.txt"
getprop | grep debug.carplay > "$D/props.txt"
dumpsys media_projection > "$D/projection.txt" 2>&1
dumpsys audio 2>&1 | grep -iE 'STREAM_MUSIC|STREAM_NOTIFICATION|STREAM_RING|mute|volume|mRingerMode' | head -150 > "$D/audio_summary.txt"
logcat -b main -b system -v threadtime -d -t 12000 |
 grep -iE 'v51|v50 MainScreen|v50 video suppressed|CarPlayAudioCapture|releaseMediaStreams|CarPlayProjectionService|SensitiveNotificationProtection|SensitiveContentProtection|CarPlayHostRuntime stop' |
 tail -600 > "$D/events.txt"
tar -czf "$D.tar.gz" -C /sdcard/Download "$(basename "$D")"
echo "$D.tar.gz"

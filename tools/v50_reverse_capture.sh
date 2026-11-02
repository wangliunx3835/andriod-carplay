#!/system/bin/sh
# v50 passive reverse resource trace. Use only while stationary.
if [ "$(id -u)" != "0" ]; then echo "Root required"; exit 1; fi
D="/sdcard/Download/v50_reverse_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$D" || exit 1
date > "$D/start.txt"
getprop | grep 'debug.carplay' > "$D/props.txt"
echo "Stationary test only: recording 35 seconds of CarPlay resource traffic."
logcat -b main -b system -v threadtime -d -t 5000 |
 grep -iE 'changeModes|MainScreen|modesChanged|backupCamera|v30|v50|RTSP streaming|screen egress' |
 tail -450 > "$D/before.txt"
(
 logcat -b main -b system -v threadtime -T 1 |
 grep --line-buffered -iE 'changeModes|MainScreen|modesChanged|backupCamera|v30|v50|CarPlay.*(SETUP|screen|session|Video)' > "$D/during.txt"
) &
PID=$!
sleep 35
kill "$PID" 2>/dev/null
wait "$PID" 2>/dev/null
date > "$D/end.txt"
tar -czf "$D.tar.gz" -C /sdcard/Download "$(basename "$D")"
echo "Saved $D.tar.gz"

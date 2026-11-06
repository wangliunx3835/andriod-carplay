#!/system/bin/sh
# Run on the rooted Android phone hosting AADisplay. No adb required.
if [ "$(id -u)" != 0 ]; then
  echo "请使用 su -c 'sh /sdcard/Download/carplay_bt_connect_capture_v2.sh 300'"
  exit 1
fi
if [ "$1" = mark ]; then
  shift
  log -p i -t CARPLAY_CAPTURE "$*"
  echo "已标记：$(date '+%H:%M:%S') $*"
  exit 0
fi
DURATION=${1:-300}
case "$DURATION" in ''|*[!0-9]*) DURATION=300 ;; esac
[ "$DURATION" -lt 60 ] && DURATION=60
[ "$DURATION" -gt 600 ] && DURATION=600
BASE=/sdcard/Download
NAME=CarPlay_BT_V2_$(date +%Y%m%d_%H%M%S)_$$
OUT="$BASE/$NAME"
mkdir -p "$OUT" || exit 1
exec 3>>"$OUT/capture_status.txt"
LOGPID=
APPLOGPID=
DONE=0
bounded() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 8 "$@"
  else
    echo "SKIPPED: timeout unavailable: $*" >&3
  fi
}
record() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$OUT/markers.txt"
  log -p i -t CARPLAY_CAPTURE "$*" 2>/dev/null
}
snapshot() {
  PHASE=$1
  {
    date
    cat /proc/uptime
    bounded dumpsys bluetooth_manager
  } >"$OUT/bluetooth_$PHASE.txt" 2>&1
  {
    date
    bounded ip addr
    bounded ip route show table all
    bounded ip neigh
    bounded ss -tn
    bounded dumpsys wifi
    bounded dumpsys connectivity
    bounded ps -A
  } >"$OUT/network_$PHASE.txt" 2>&1
}
finish() {
  [ "$DONE" = 1 ] && return
  DONE=1
  trap '' INT TERM
  record "CAPTURE_END"
  [ -n "$APPLOGPID" ] && kill "$APPLOGPID" 2>/dev/null
  [ -n "$APPLOGPID" ] && wait "$APPLOGPID" 2>/dev/null
  [ -n "$LOGPID" ] && kill "$LOGPID" 2>/dev/null
  [ -n "$LOGPID" ] && wait "$LOGPID" 2>/dev/null
  # Compact index only; keep unfiltered logs in the same archive.
  grep -Eai 'CARPLAY_CAPTURE|AADisplay|CarPlay|CarLetter|Car Audio|Bluetooth|btif|bta_|btm_|RFCOMM|iAP2|AirPlay|RTSP|Bonjour|NSD|mDNS|pair|auth|timeout|exception|disconnect|DHCP' "$OUT"/logcat* >"$OUT/highlights.txt" 2>/dev/null
  bounded dumpsys package io.github.nitsuya.aa.display >"$OUT/app_version_final.txt" 2>&1
  if tar -czf "$BASE/$NAME.tar.gz" -C "$BASE" "$NAME" 2>"$OUT/archive_error.txt"; then
    echo "抓取完成，请发送整个压缩包：$BASE/$NAME.tar.gz"
  else
    echo "压缩失败，请用文件管理器压缩并发送此目录：$OUT"
  fi
}
trap 'finish; exit 0' INT TERM
{
  date
  id
  getprop ro.build.version.release
  getprop ro.build.version.sdk
  bounded dumpsys package io.github.nitsuya.aa.display
} >"$OUT/version.txt" 2>&1
# Rotation caps log volume at roughly 32 MiB. Never clear the device log buffers.
logcat -b all -v threadtime -T 1000 -f "$OUT/logcat.txt" -r 8192 -n 3 2>"$OUT/logcat_stderr.txt" &
LOGPID=$!
sleep 1
if ! kill -0 "$LOGPID" 2>/dev/null; then
  wait "$LOGPID" 2>/dev/null
  logcat -b all -v threadtime -f "$OUT/logcat.txt" -r 8192 -n 3 2>>"$OUT/logcat_stderr.txt" &
  LOGPID=$!
  sleep 1
fi
if ! kill -0 "$LOGPID" 2>/dev/null; then
  echo "logcat 未能启动，错误见 $OUT/logcat_stderr.txt；请保留本目录反馈。"
  exit 2
fi
# Keep protocol logs independently so SurfaceFlinger cannot evict the handshake.
logcat -b main -b system -b crash -v threadtime -T 1000 \
  -f "$OUT/connection.txt" -r 8192 -n 3 \
  AADisplay_CarPlay:V AAD_CarPlay:V CARPLAY_CAPTURE:V \
  AAD_CarPlayAudioCap:I AAD_CpProcBoost:I BluetoothManagerService:I \
  BluetoothAdapter:I BluetoothSocket:V BluetoothA2dp:I \
  A2dpService:V A2dpStateMachine:V HeadsetStateMachine:V \
  BluetoothDatabase:V bt_btif_sock_rfcomm:V bt_btm_sec:V \
  '*:S' 2>"$OUT/connection_stderr.txt" &
APPLOGPID=$!
sleep 1
if ! kill -0 "$APPLOGPID" 2>/dev/null; then
  echo "专用连接日志启动失败，请反馈 connection_stderr.txt；不要仅重复旧抓取。" >&3
fi
record "CAPTURE_START duration=$DURATION"
echo "现在可以启动车机并等待自动连接。保持本终端运行，约 $DURATION 秒后自动打包。"
echo "不要先重配对或清除应用数据；请记录手动点蓝牙/CarPlay和成功出画面的时间。"
START=$(date +%s)
snapshot before
INDEX=0
NEXT=20
while :; do
  NOW=$(date +%s)
  ELAPSED=$((NOW - START))
  [ "$ELAPSED" -ge "$DURATION" ] && break
  if [ "$ELAPSED" -ge "$NEXT" ]; then
    INDEX=$((INDEX + 1))
    snapshot "during_$INDEX"
    NEXT=$(( $(date +%s) - START + 20 ))
  fi
  sleep 2
done
snapshot final
finish

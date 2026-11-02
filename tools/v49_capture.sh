#!/system/bin/sh
# v49 one-shot locked/unlocked SF and WM diagnostic. No automatic polling.
# su -c 'sh /sdcard/Download/v49_capture.sh unlocked 15'
# su -c 'sh /sdcard/Download/v49_capture.sh locked 15'
set -u
PHASE="${1:-}"
case "$PHASE" in unlocked|locked) ;; *) echo "usage: sh $0 unlocked|locked [delay-seconds]"; exit 2 ;; esac
DELAY="${2:-15}"
case "$DELAY" in *[!0-9]*|"") echo "delay must be a nonnegative number"; exit 2 ;; esac
if [ "$(id -u)" != 0 ]; then echo "Use su -c sh ..."; exit 1; fi
BASE=/sdcard/Download
STAMP="$(date +%Y%m%d_%H%M%S)"
NAME="v49_${PHASE}_$STAMP"
D="$BASE/$NAME"
mkdir -p "$D" || exit 1
echo "Phase=$PHASE Start=$STAMP Delay=$DELAY" > "$D/metadata.txt"
echo "In $DELAY seconds the snapshot begins. Keep CarPlay text field open."
sleep "$DELAY"
date >> "$D/metadata.txt"
getprop ro.build.version.release >> "$D/metadata.txt"
getprop ro.build.version.incremental >> "$D/metadata.txt"
getprop | grep 'debug.carplay' > "$D/props.txt"
dumpsys input_method > "$D/ime.txt" 2>"$D/ime.err"
dumpsys window displays > "$D/window.txt" 2>"$D/window.err"
dumpsys display > "$D/display.txt" 2>"$D/display.err"
dumpsys SurfaceFlinger --layers > "$D/sf_1.txt" 2>"$D/sf_1.err"
sleep 2
dumpsys SurfaceFlinger --layers > "$D/sf_2.txt" 2>"$D/sf_2.err"
logcat -b main -b system -b events -d -t 12000 -v threadtime 2>"$D/logcat.err" |
  grep -iE 'v49 |v48 |v45 |AAD_VdImeDisplayPin|ImeTracker|MiuiMirrorInputMethod|InputMethodManagerService|SF-MICapture' |
  tail -1400 > "$D/events.txt"
{
  echo '=== SF IME & output markers ==='
  grep -nE 'Output Layers|Output Layer|LayerStack=2|LayerStack=3|VRI-InputMethod|InputMethod#|miVisibleStateForDisplay' "$D/sf_1.txt" | tail -100
  echo '=== IME WM status ==='
  grep -nE 'mImeParent=|mImeShowing=|mLastDrawn=|mInputShown=' "$D/window.txt" "$D/ime.txt" | tail -100
  echo '=== Hook activity ==='
  grep -E 'v49 attachEntry|v48 runtime|v48 nativeUpdate|v48 attachDecision' "$D/events.txt" | tail -100
} > "$D/highlights.txt" 2>/dev/null
tar -czf "$BASE/$NAME.tar.gz" -C "$BASE" "$NAME"
R=$?
echo "Capture result=$R archive=$BASE/$NAME.tar.gz"
exit "$R"

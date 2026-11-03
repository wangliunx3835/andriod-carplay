# v55: MainScreen re-entry after HU TAKE

Based on v54 with all v2-v54 patches. No changes to handshake, Bluetooth, RTSP, stream encoder, audio, reverse priority, IME, lyrics or media overlay.

## Evidence in user's 2026-11-03 v54 logs
- backupCamera BORROW (screen=0/1) and UNBORROW (screen=1/1) worked twice.
- At 20:27:49 after UNBORROW, encrypted video keyframes continue and compositor ~60fps.
- At 20:27:56 HU issued permanent MainScreen TAKE (0/0), then requestUI at 20:27:56 and 20:28:01. v54 responded to requestUI only by requesting video keyframe, not by notifying changed MainScreen ownership.
- User gate-off A/B did not restore CarPlay; captured archive itself had gate prop empty, meaning default ON, so this A/B is user reported, not shown in this archive.

## v55 correction
On explicit event requestUI, when MainScreen permanent and current owners are both accessory (0/0) and a backupCamera BORROW is not active, transition MainScreen to controller (1/1), notify HU using existing asynchronous onModesRestoredToPhone -> modesChanged path, and ask for an IDR. MainAudio state unchanged. Does not force screen takeover by timer or after any ordinary TAKE; respects backup camera. Debug opt-out command: su -c 'setprop debug.carplay.v55_requestui_reclaim 0' ; back to 1 to enable. No code changes in reverse/encoder components.

## Parked A/B test
Install and reboot Android. Open CarPlay, switch to HU home, re-open CarPlay; repeat. Test reverse screen entry/exit only while safely parked. If failure reproduce then capture:
su -c 'logcat -d -b main -b system -t 30000 -v threadtime | grep -Ei "AADisplay_CarPlay.*(v55 requestUI|changeModes|modesChanged|requestUI|MainScreen|video suppressed|screen VIDEO|screen dataPort|releaseMediaStreams|HU idle cleanup|ensureEncoder|GL bind|attachGl)" | tail -n 350 > /sdcard/Download/v55_reentry_filtered.txt'

Result still needs HU test; if modesChanged confirms ownership but HU does not render, investigate receiver video presentation/requestUI URL. Apple WWDC 2016 resource manager: https://developer.apple.com/videos/play/wwdc2016/723/ .

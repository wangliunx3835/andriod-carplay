# v52 AADisplay floating media controls

BASE: v51-reverse-default-audio-recovery. v52 edits ONLY overlay canvas drawing, existing input dispatch, phone connection-page settings, lyric metadata extension, Host overlay start/stop, and version. The unchanged apply_v2..apply_v51 ensure pinned original CarPlay handshake, reverse resource ownership / video gating, audio mute recovery, RTSP transport, and MediaCodec drain behavior.

After installing v52 reboot Android for the existing LSPosed system_server baseline. Connect CarPlay as usual. In AADisplay phone connection page click **悬浮媒体设置（歌词／封面／样式／拖动）** and switch on the media overlay (default OFF until user chooses).

**Appearance:** centered album cover top; current lyric larger and bold, next lyric smaller (only when source provides next timed LRC line); media controls at bottom when paused or when revealed. No mode switch or wheel text appears on car video. Tap card to reveal controls, default six seconds; when already visible tap the lower left, middle or right control to perform previous, toggle or next. Drag anywhere on card with >15px movement; persist normalized position. Font 14–54px; corner 0–64px; background alpha 10–95%; size 65–155%; thematic tints; show album, two-line, auto-hide switch. Settings apply in the same app process without reconnect.

**Compatibility:** Original physical steering wheel media mapping including hold-to-swap and recents is unchanged; overlay invokes the same dispatcher. No new virtual display/surface/video stream. GL draws onto existing chrome Canvas texture, tee fallback calls same draw. Media and album fetch are moved off the render thread at 650ms, art only re-decoded when revision or track changes. If lyrics only provide one line, render only current; never synthesize a future line.

**Regression:** confirm v51 camera reverse (no manual gate), back from reverse no black screen, first/second CarPlay connection, unmute on disconnect, Gboard input, notifications, split divider drag, pane app touch, wheel short and long press, overlay dragging, paused controls, track changes, cover matching, no memory leak when disconnecting. User's occasional black screen on reverse return remains an independently reported issue not claimed fixed here.

**Log:** logcat -d -t 12000 -v threadtime | grep -iE 'v52|media overlay|CarPlayGlCompositor|keyframe|MainScreen|black|Exception' > /sdcard/Download/v52_media_filtered.txt

**Limits:** no supplied timed LRC = no next line. Android media-session specifics differ by app; controls must be validated on-device. No OS privacy-protection override. To fully disable without changing stable CarPlay logic, switch the overlay OFF in app settings.

### v52r1 final QA
- Paused playback retains last media metadata and album art even after 15-second freshness timeout in the instrument-cluster store.
- Media overlay paints beneath modal app-picker and recents, matching their existing touch priority.
- No CarPlay connection, reverse, encoder, codec, or audio changes relative to v51.

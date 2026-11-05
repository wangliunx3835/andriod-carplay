# v63 — QiShui Car lyric source fallback (after v62)

## What is confirmed
- On the user's v62 installation, song title and artist now appear. This proves the v62 source app -> explicit receiver -> overlay metadata path works.
- The installed car variant is `com.luna.music.car` (v1.1.35 in the preceding diagnostic).
- Earlier captures found neither mobile-style `com.luna.common.arch.db.entity.lyrics.Lyric` nor `TrackLyric`. Standard MediaSession metadata contains the track but has not yielded usable timed LRC.
- Neither missing lyrics nor successful external fetching has been proven for this exact APK and network yet.

## New v63 behavior
- Only for `com.luna.music.car` with the overlay enabled; does not change other music apps.
- Prefer actual LRC/KRC from the original app Hook. When no timed lyrics are present, do one short asynchronous metadata-based search for the current song title + artist.
- Query the public QiShui track search API. Only accept exact title matches and compatible artist names; reject likely unrelated tracks.
- Read the public music.douyin.com car track share page; try the standard qishui.com share page as backup. Parse the embedded timestamped sentence data into ordinary LRC. Never request user cookies, accounts, or music files.
- Bound responses to <=600 KB JSON / <=2.4 MB HTML, timeouts of 4s connect / 5s read, no redirects, 64 KB LRC cap. Keep up to 12 results in RAM; cache failed lookups for 15 minutes and successful lookups for 24h.
- On new track, discard stale LRC. Before applying an asynchronous result, check that current package, song title and artist still match, so a slow response cannot overwrite the next song.
- Expose an overlay settings switch `汽水音乐车机版在线歌词兜底（联网匹配歌曲）` (enabled by default); disabling it prevents any new lyric lookup. The network request sends **only the current title and artist** to public QiShui lookup services. No background polling or scraping.
- Log only lookup status / number of lines; do not log or export copyrighted lyric bodies.
- Preserve the exact v62-v61 reverse video behavior, v23 network, v29 session, v31 Event, v39-v40 connection, v51 keyboard and audio.

## How to test
1. Install v63, enable the existing media overlay and the new `汽水音乐车机版在线歌词兜底` switch. Fully restart CarPlay.
2. Play a known song with timed lyrics for at least 15 seconds. The first lookup needs connectivity; later repeats should come from RAM cache.
3. In root terminal run: `su -c 'logcat -d -s AAD_V61Car AAD_V62Media AAD_V63Lyrics'`.
4. Success signals: `car online lyric result=ok lines=N` and `car online timed lyric committed`. Failure signals: `result=no-match` or a network response code; there is no claim the service's public endpoint cannot change.
5. If still no lyrics, send `tools/v63_lyric_diag.sh` output. It is a bounded one-shot capture, not permanent logging. Only the error class and media-session availability are needed, not the actual lyric texts.
6. CarPlay reverse black-screen testing remains separate. v63 does not change its logic.

## Open-source research
- Implementation concept: https://github.com/zuo-qirun/Lyrics-Companion (GPL-3.0; used for protocol research, code independently authored)
- The independent QiShui car variant's public share URL structure is not the same as its mobile package; users should not assume mobile Xposed hooks work in the car APK.

# v64 — QiShui car dual-source synchronized lyrics

## Root cause analysis
- User v62 confirmed title and artist are reaching AADisplay. v63 still no lyrics.
- The only file uploaded with this report, `meta.txt`, contains `Thu Nov 5 12:54:52 CST 2026`, not app logs. This does **not** establish if source search returned 200+empty, network failed, lyrics weren't found, or lines failed to display.
- v63 tries `api.qishui.com/luna/pc/search/track` with no official client signature, which may return HTTP 200 but an empty response in recent deployments. Public reverse-engineering reports confirm this failure mode.
- LRCLIB is an independently operated, publicly documented lyric catalog with anonymous `/api/search` and `syncedLyrics` fields, which provides a separate chance when QiShui lookup fails.

## Changes
- v64 preserves the v63 same-song cache, delayed misses, private LRC store, title/artist, MediaSession, art, and reverse-camera path. Only the lyric lookup logic changes.
- Use existing QiShui share first. If it returns no usable timed LRC, or throws due to empty/invalid response, query LRCLIB separately.
- Select only same normalized title and compatible artist, reject instrumental records, reject lyrics without LRC timestamps and oversized payloads. Never substitute an unrelated song.
- Bounded request limits unchanged: 4s connect, 5s read, max 600KB source response, 64KB lyrics, no redirects, no auth or cookies.
- LRCLIB requests use an identifying User-Agent as requested in its API documentation.
- Logs distinguish `soda-ok`, `lrclib-ok`, `no-match`, and network/parse failures. Lyrics themselves are not logged or uploaded.
- Network search is triggered when the song changes or an earlier cache misses; no continuous HTTP polling, no Xposed UI scanning, no microphone, no OCR.
- Existing v63 user toggle controls both online providers. When enabled, the current song title and artist can be transmitted to public QiShui and LRCLIB services, respectively.
- All previously resolved v23, v29, v31, v39-v40, v51, v60-62 patches are retained.

## Test / evidence collection
1. Fully reinstall v64, restart CarPlay and car QiShui.
2. Enable media overlay and the "汽水音乐车机版在线歌词兜底（联网匹配歌曲）" setting.
3. Play a commercial studio song with known timed lyrics for 20 seconds, then switch to another track.
4. Look at `logcat -d -s AAD_V61Car AAD_V62Media AAD_V63Lyrics`.
   - `car online lyric result=lrclib-ok` / `soda-ok`: a timed lyric was obtained.
   - `car online timed lyric committed`: result was written to the media overlay store.
   - `no-match`: both sources lacked a safe matching timed lyric (or service unavailable).
   - `soda lookup error=...` or `car lyric empty response host=api.qishui.com`: source failure.
5. Run the bundled `v64_lyric_diag.sh` **once** (su root terminal), upload its generated `.tar.gz`, not just `meta.txt`. It captures only filtered tags (not complete system logs).
6. If a valid LRC is committed but not displayed, next investigate overlay preference, lyric timeline and source selection. If no source obtains LRC, concentrate on car app's in-memory lyric model or local database instead.

## Public references
https://lrclib.net/docs
https://github.com/zuo-qirun/Lyrics-Companion
https://github.com/XxHuberrr/Mineradio/issues/451

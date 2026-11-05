# v65 — QiShui Car Real Track ID → H5 Karaoke Lyrics

## Verified public interface (2026-11-05)
- QiShui old PC search `api.qishui.com/luna/pc/search/track`: HTTP 200, 0-byte body in repeated public-network checks.
- QiShui H5 `https://beta-luna.douyin.com/luna/h5/seo_track?track_id=<ID>&device_platform=web`: HTTP 200, JSON with `seo_track.track.id/name/artists` and `lyric.content`. Independently observed 39 KRC lines and 401 word-timing tags for an existing public test track. See GitHub Actions lyric API verification.
- QiShui car share pages contained 41 timestamped sentences for the public test track.
- LRCLIB and AMLL are available but returned an empty set for the observed car track “越界” by ShameU; returning HTTP 200 alone is not enough to show the correct song.

## v65 focused changes
- Continue the existing v62 secure car IPC. v65 separately captures a VALIDATED numeric QiShui ID from `MediaMetadata.MEDIA_ID`, car-specific metadata ID keys or an explicit media URI. Only 6–24 numeric digits are allowed. Avoid synthetic `car:<hash>` media IDs.
- Forward this song ID independently of the old UI/album-art identity in the UID-verified receiver and `LyricV53Bridge.Music`; clear stale song lyrics on title/artist changes even if the media ID is reused by the player.
- Prioritize QiShui H5 SEO track lookup by validated ID. Verify returned ID, title AND artist before using lyric content; never display another track's lyrics.
- Convert KRC `[startMs,durationMs]<wordMs,duration,flag>word...` into canonical LRC `[mm:ss.SSS]words` expected by v53 lyric renderer. Keep response byte limits, HTTPS-only requests, 4s connect and 5s read limits, no redirect.
- If H5 fails, reuse existing public QiShui car share page by ID; then the prior title/artist lookup + LRCLIB fallback. The old PC search may fail, but does not block next sources.
- Song-specific result caching from v63/v64 is preserved; cache key now includes numeric song ID to distinguish versions. Network requests occur only when no timed lyrics are available for a song.
- No changes to CarPlay video egress, reverse-camera screen ownership, RTSP, AAC, encoder, IME, wheel, IPv4 gateway or Bluetooth.

## Test
1. Install v65. Restart CarPlay and the QiShui car app. Enable AADisplay LSPosed scope for `com.luna.music.car`.
2. Enable the existing floating media component and the `汽水音乐车机版在线歌词兜底` option.
3. Play a track known to have lyrics for 15–20 seconds; try 2–3 other tracks. Check title, artist, cover, lyrics separately.
4. In rooted Android terminal: `su -c 'logcat -d -s AAD_V61Car AAD_V62Media AAD_V63Lyrics AAD_V65Lyrics'`.
5. Expected diagnostics:
   - `v65 MediaSession numericTrackId=true` and `car metadata changed, numericTrackId=true`: real track ID made it through.
   - `v65 H5 source decoded lines=...`, `car online lyric result=h5-id-ok`, `car online timed lyric committed`: confirmed transfer into renderer.
   - `v65 no numeric song ID`: app did not expose a qualifying ID through the observed metadata; capture a short diagnostic, not a blind guess.
   - `title mismatch`/`artist mismatch`: H5 returned a track that could not safely be identified.
6. Use tools/v65_lyric_diag.sh for an automatically archived filtered log and upload the entire .tar.gz, not only meta.txt.

## Limitations
Code build + API verification do not establish real-device success until the installed QiShui car version emits a usable track ID or an accurate fallback match. Song lyrics are not logged or uploaded; only counts/status are recorded.

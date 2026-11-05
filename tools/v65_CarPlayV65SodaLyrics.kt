package io.github.nitsuya.aa.display.carplay

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.Locale
import kotlin.concurrent.thread

/**
 * Optional, song-change-only external LRC fallback for com.luna.music.car.
 *
 * - The original car hook has first priority. Never overwrites an existing
 *   valid LRC/KRC captured from the player itself.
 * - Makes at most one bounded lookup per unknown song, then caches the result.
 * - Searches by title+artist and insists on exact normalized title and
 *   compatible artist, avoiding wrong-match karaoke lyrics.
 * - No recurring timer, no listening to audio, no screen OCR, no auth cookies.
 * - Uses a public share page and not any proprietary private app endpoint.
 */
internal object CarPlayV63SodaLyrics {
    private const val TAG = "AAD_V63Lyrics"
    private const val PACKAGE = "com.luna.music.car"
    private const val STORE = "v53_lyrics"
    private const val MAX_LRC = 64_000
    private const val MAX_SEARCH = 600_000
    private const val MAX_HTML = 2_400_000
    private const val MISS_TTL_MS = 15L * 60L * 1000L
    private const val HIT_TTL_MS = 24L * 60L * 60L * 1000L

    private data class Cached(val text: String?, val until: Long)
    private val monitor = Any()
    private val cache = LinkedHashMap<String, Cached>(12, 0.75f, true)
    private var fetching = false
    private var queryKey = ""

    private val lrcTimestamp = Regex("""(?m)^\[\d{1,3}:\d{2}[.:]\d{1,3}]""")
    private val normalizeSeparators = Regex("""[\p{P}\p{Z}\s]+""")
    private val krcLine = Regex("""^\[(\d+),(\d+)](.*)$""")
    private val krcWord = Regex("""<\d+,\d+,\d+>""")

    fun maybeFetch(context: Context, music: LyricV53Bridge.Companion.Music, enabled: Boolean) {
        if (!enabled || music.sourcePkg != PACKAGE || music.song.isBlank()) return
        val app = context.applicationContext
        val pref = app.getSharedPreferences(STORE, Context.MODE_PRIVATE)
        if (lrcTimestamp.containsMatchIn(pref.getString("body", "").orEmpty())) return

        val title = music.song.trim().take(160)
        val artist = music.artist.trim().take(160)
        val realId = validTrackId(music.mediaId)
        val key = normalize(title) + "|" + normalize(artist) + "|" + (realId ?: "")
        if (key.length < 3) return
        val now = System.currentTimeMillis()
        var known: Cached? = null
        synchronized(monitor) {
            val prior = cache[key]
            if (prior != null && prior.until > now) {
                known = prior
            } else if (!fetching) {
                fetching = true
                queryKey = key
            } else return
        }
        if (known != null) {
            known?.text?.let { saveForCurrent(app, music.song, music.artist, it) }
            return
        }

        thread(name = "carplay-v63-lyrics-on-song-change", isDaemon = true) {
            var lyrics: String? = null
            var reason = "no-match"
            try {
                if (realId != null) {
                    Log.i(TAG, "v65 numeric song ID available; query QiShui H5")
                    lyrics = runCatching { lookupH5(realId, title, artist) }
                        .onFailure { Log.w(TAG, "v65 H5 error=" +
                            it.javaClass.simpleName) }.getOrNull()
                    if (lyrics != null) reason = "h5-id-ok"
                    if (lyrics == null) {
                        lyrics = runCatching { lookupShareById(realId) }
                            .onFailure { Log.w(TAG, "v65 share error=" +
                                it.javaClass.simpleName) }.getOrNull()
                        if (lyrics != null) reason = "share-id-ok"
                    }
                } else {
                    Log.i(TAG, "v65 no numeric song ID; title/artist catalog only")
                }
                if (lyrics == null) {
                    lyrics = runCatching { lookup(title, artist) }
                        .onFailure { Log.w(TAG, "soda search error=" +
                            it.javaClass.simpleName) }.getOrNull()
                    if (lyrics != null) reason = "soda-search-ok"
                }
                if (lyrics == null) {
                    lyrics = runCatching { lookupLrclib(title, artist) }
                        .onFailure { Log.w(TAG, "lrclib error=" +
                            it.javaClass.simpleName) }.getOrNull()
                    if (lyrics != null) reason = "lrclib-ok"
                }
            } catch (error: Throwable) {
                reason = error.javaClass.simpleName
            } finally {
                synchronized(monitor) {
                    cache[key] = Cached(lyrics,
                        System.currentTimeMillis() +
                            if (lyrics == null) MISS_TTL_MS else HIT_TTL_MS)
                    while (cache.size > 12) cache.remove(cache.keys.first())
                    fetching = false
                    queryKey = ""
                }
                if (lyrics != null) saveForCurrent(app, music.song, music.artist, lyrics)
                Log.i(TAG, "car online lyric result=" + reason +
                    " lines=" + (lyrics?.lineSequence()?.count() ?: 0))
            }
        }
    }

    private fun saveForCurrent(app: Context, title: String, artist: String, lrc: String) {
        val pref = app.getSharedPreferences(STORE, Context.MODE_PRIVATE)
        if (pref.getString("pkg", "") != PACKAGE ||
            pref.getString("song", "") != title ||
            pref.getString("artist", "") != artist) return
        // Native lyric wins when it has arrived during our network request.
        if (lrcTimestamp.containsMatchIn(pref.getString("body", "").orEmpty())) return
        if (lrc.length > MAX_LRC || !lrcTimestamp.containsMatchIn(lrc)) return
        pref.edit().putString("body", lrc).apply()
        Log.i(TAG, "car online timed lyric committed")
    }

    private fun validTrackId(id: String?): String? {
        val raw = id?.trim().orEmpty()
        if (raw.matches(Regex("""\d{6,24}"""))) return raw
        val match = Regex("""(?:track[_-]?id|song[_-]?id)[=:/?](\d{6,24})(?!\d)""",
            RegexOption.IGNORE_CASE).find(raw)
        return match?.groupValues?.getOrNull(1)
    }

    /** Only use H5 lyrics if returned track ID, name and artist all agree. */
    private fun lookupH5(id: String, title: String, artist: String): String? {
        val address = "https://beta-luna.douyin.com/luna/h5/seo_track?track_id=" +
            URLEncoder.encode(id, "UTF-8") + "&device_platform=web"
        val raw = fetch(address, "https://music.douyin.com/", MAX_HTML) ?: return null
        val root = JSONObject(raw)
        val track = root.optJSONObject("seo_track")?.optJSONObject("track")
        if (track == null) {
            Log.i(TAG, "v65 H5 missing track metadata")
            return null
        }
        if (track.optString("id", "") != id) {
            Log.w(TAG, "v65 H5 returned mismatching song ID")
            return null
        }
        if (normalize(track.optString("name", "")) != normalize(title)) {
            Log.i(TAG, "v65 H5 title mismatch")
            return null
        }
        val wantedArtist = normalize(artist)
        val actualArtists = track.optJSONArray("artists")
        if (wantedArtist.isNotEmpty() && actualArtists != null &&
            actualArtists.length() > 0) {
            var found = false
            for (i in 0 until actualArtists.length().coerceAtMost(12)) {
                val name = normalize(actualArtists.optJSONObject(i)
                    ?.optString("name", "").orEmpty())
                if (name.isNotBlank() && (name == wantedArtist ||
                    wantedArtist.contains(name) || name.contains(wantedArtist))) {
                    found = true
                    break
                }
            }
            if (!found) {
                Log.i(TAG, "v65 H5 artist mismatch")
                return null
            }
        }
        val payload = root.optJSONObject("lyric")
            ?.optString("content", "").orEmpty()
        val converted = krcToLrc(payload)
        Log.i(TAG, "v65 H5 source decoded lines=" +
            (converted?.lineSequence()?.count() ?: 0) +
            " rawLength=" + payload.length)
        return converted
    }

    private fun lookupShareById(id: String): String? {
        for ((index, address) in listOf(
            "https://music.douyin.com/qishui/share/track?track_id=" + id,
            "https://www.qishui.com/share/track?track_id=" + id
        ).withIndex()) {
            val html = fetch(address,
                if (index == 0) "https://music.douyin.com/"
                else "https://www.qishui.com/", MAX_HTML) ?: continue
            val result = parseShare(html)
            if (result != null) {
                Log.i(TAG, "v65 share by ID decoded lines=" +
                    result.lineSequence().count())
                return result
            }
        }
        return null
    }

    /** Convert native KRC [startMs,durationMs] + word tags to LRC. */
    private fun krcToLrc(raw: String): String? {
        if (raw.length !in 12..MAX_LRC) return null
        if (lrcTimestamp.containsMatchIn(raw)) return raw
        val out = StringBuilder()
        var last = -1L
        for (line in raw.lineSequence()) {
            val parts = krcLine.matchEntire(line.trim()) ?: continue
            val ms = parts.groupValues[1].toLongOrNull() ?: continue
            if (ms < 0L || ms > 7_200_000L || ms < last) continue
            val words = krcWord.replace(parts.groupValues[3], "")
                .replace('\r', ' ').trim().take(180)
            if (words.isBlank()) continue
            val marker = String.format(Locale.ROOT, "[%02d:%02d.%03d]",
                ms / 60000L, ms / 1000L % 60L, ms % 1000L)
            if (out.length + marker.length + words.length + 1 > MAX_LRC) break
            out.append(marker).append(words).append('\n')
            last = ms
        }
        return out.toString().takeIf { lrcTimestamp.containsMatchIn(it) }
    }

    private fun lookup(title: String, artist: String): String? {
        if (title.isBlank()) return null
        val keyword = (title + " " + artist).trim()
        val searchUrl = "https://api.qishui.com/luna/pc/search/track?q=" +
            URLEncoder.encode(keyword, "UTF-8") +
            "&cursor=0&search_method=input&aid=386088" +
            "&device_platform=web&channel=pc_web"
        val search = fetch(searchUrl, "https://www.qishui.com/", MAX_SEARCH)
            ?: return null
        val root = JSONObject(search)
        val groups = root.optJSONArray("result_groups") ?: return null

        var selectedId = ""
        var bestScore = -1
        for (i in 0 until groups.length().coerceAtMost(12)) {
            val records = groups.optJSONObject(i)?.optJSONArray("data") ?: continue
            for (j in 0 until records.length().coerceAtMost(25)) {
                val t = records.optJSONObject(j)?.optJSONObject("entity")
                    ?.optJSONObject("track") ?: continue
                val candidate = t.optString("name", "")
                if (normalize(candidate) != normalize(title)) continue
                val owner = artists(t.optJSONArray("artists"))
                val wantedArtist = normalize(artist)
                val candidateArtist = normalize(owner)
                if (wantedArtist.isNotBlank() && candidateArtist.isNotBlank() &&
                    !wantedArtist.contains(candidateArtist) &&
                    !candidateArtist.contains(wantedArtist)) continue
                val id = t.optString("id", "")
                if (!id.matches(Regex("""\d{6,24}"""))) continue
                val score = if (wantedArtist.isNotEmpty() && candidateArtist.isNotEmpty()) {
                    if (wantedArtist == candidateArtist) 3 else 2
                } else 1
                if (score > bestScore) {
                    selectedId = id
                    bestScore = score
                }
            }
        }
        if (selectedId.isBlank()) return null
        val addresses = listOf(
            "https://music.douyin.com/qishui/share/track?track_id=" + selectedId,
            "https://www.qishui.com/share/track?track_id=" + selectedId,
        )
        for ((index, address) in addresses.withIndex()) {
            val html = fetch(address,
                if (index == 0) "https://music.douyin.com/"
                else "https://www.qishui.com/", MAX_HTML) ?: continue
            val lrc = parseShare(html)
            if (!lrc.isNullOrBlank()) return lrc
        }
        return null
    }

    /** Second source, applied only if QiShui search produced no usable LRC. */
    private fun lookupLrclib(title: String, artist: String): String? {
        if (title.isBlank() || artist.isBlank()) return null
        val address = "https://lrclib.net/api/search?track_name=" +
            URLEncoder.encode(title, "UTF-8") + "&artist_name=" +
            URLEncoder.encode(artist, "UTF-8")
        val response = fetch(address, "https://lrclib.net/", MAX_SEARCH)
            ?: return null
        val entries = JSONArray(response)
        val wantedTitle = normalize(title)
        val wantedArtist = normalize(artist)
        var best: String? = null
        var bestScore = -1
        for (i in 0 until entries.length().coerceAtMost(20)) {
            val item = entries.optJSONObject(i) ?: continue
            if (item.optBoolean("instrumental", false)) continue
            if (normalize(item.optString("trackName", "")) != wantedTitle) continue
            val artistName = normalize(item.optString("artistName", ""))
            if (artistName.isBlank() ||
                !(wantedArtist == artistName || wantedArtist.contains(artistName) ||
                    artistName.contains(wantedArtist))) continue
            val lrc = item.optString("syncedLyrics", "")
            if (lrc.length !in 20..MAX_LRC ||
                !lrcTimestamp.containsMatchIn(lrc)) continue
            val score = if (wantedArtist == artistName) 2 else 1
            if (score > bestScore) {
                bestScore = score
                best = lrc
            }
        }
        return best
    }

    private fun artists(array: JSONArray?): String {
        if (array == null) return ""
        val names = ArrayList<String>()
        for (i in 0 until array.length().coerceAtMost(10)) {
            val name = array.optJSONObject(i)?.optString("name", "").orEmpty().trim()
            if (name.isNotBlank()) names.add(name)
        }
        return names.joinToString(" ")
    }

    private fun normalize(s: String): String =
        normalizeSeparators.replace(s.lowercase(Locale.ROOT), "")

    private fun parseShare(html: String): String? {
        val marker = html.indexOf("_ROUTER_DATA")
        if (marker < 0) return null
        val eq = html.indexOf('=', marker)
        if (eq < 0 || eq - marker > 100) return null
        val begin = html.indexOf('{', eq)
        if (begin < 0 || begin - eq > 100) return null
        val end = balancedObjectEnd(html, begin)
        if (end < 0) return null
        val router = JSONObject(html.substring(begin, end + 1))
        val sentences = router.optJSONObject("loaderData")
            ?.optJSONObject("track_page")
            ?.optJSONObject("audioWithLyricsOption")
            ?.optJSONObject("lyrics")
            ?.optJSONArray("sentences") ?: return null

        val output = StringBuilder()
        var lastTime = -1L
        for (i in 0 until sentences.length().coerceAtMost(2000)) {
            val item = sentences.optJSONObject(i) ?: continue
            val ms = item.optLong("startMs", -1L)
            if (ms < 0L || ms > 7_200_000L || ms < lastTime) continue
            var line = item.optString("text", "").trim()
            if (line.isBlank()) {
                val words = item.optJSONArray("words")
                if (words != null) {
                    val joined = StringBuilder()
                    for (j in 0 until words.length().coerceAtMost(200)) {
                        joined.append(words.optJSONObject(j)?.optString("text", "").orEmpty())
                    }
                    line = joined.toString().trim()
                }
            }
            if (line.isBlank()) continue
            line = line.replace('\n', ' ').replace('\r', ' ').take(180)
            val minutes = ms / 60000L
            val seconds = (ms / 1000L) % 60L
            val millis = ms % 1000L
            val tag = String.format(Locale.ROOT, "[%02d:%02d.%03d]",
                minutes, seconds, millis)
            if (output.length + tag.length + line.length + 1 > MAX_LRC) break
            output.append(tag).append(line).append('\n')
            lastTime = ms
        }
        return output.toString().takeIf { lrcTimestamp.containsMatchIn(it) }
    }

    /** JSON object scanner: ignore braces inside strings and escaped quotes. */
    private fun balancedObjectEnd(text: String, at: Int): Int {
        var depth = 0
        var quote = false
        var escape = false
        for (i in at until text.length) {
            val c = text[i]
            if (quote) {
                if (escape) escape = false
                else if (c == '\\') escape = true
                else if (c == '"') quote = false
            } else if (c == '"') quote = true
            else if (c == '{') depth++
            else if (c == '}') {
                depth--
                if (depth == 0) return i
            }
        }
        return -1
    }

    private fun fetch(address: String, referer: String, bound: Int): String? {
        val url = URL(address)
        if (url.protocol != "https") return null
        val conn = url.openConnection() as HttpURLConnection
        try {
            conn.instanceFollowRedirects = false
            conn.connectTimeout = 4_000
            conn.readTimeout = 5_000
            conn.setRequestProperty("User-Agent",
                if (url.host == "lrclib.net")
                    "AADisplayCarPlay/0.3.64 (+https://github.com/wangliunx3835/andriod-carplay)"
                else "Mozilla/5.0 (Linux; Android 17) AppleWebKit/537.36 " +
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
            conn.setRequestProperty("Accept", "application/json,text/html,*/*")
            conn.setRequestProperty("Referer", referer)
            if (conn.responseCode != 200) {
                Log.i(TAG, "car lyrics response code=" + conn.responseCode +
                    " host=" + url.host)
                return null
            }
            conn.inputStream.use { stream ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val n = stream.read(buffer)
                    if (n < 0) break
                    if (output.size() + n > bound) return null
                    output.write(buffer, 0, n)
                }
                val body = output.toString(StandardCharsets.UTF_8.name())
                if (body.isBlank()) {
                    Log.i(TAG, "car lyric empty response host=" + url.host)
                    return null
                }
                return body
            }
        } finally {
            conn.disconnect()
        }
    }
}

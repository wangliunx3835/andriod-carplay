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

    fun maybeFetch(context: Context, music: LyricV53Bridge.Companion.Music, enabled: Boolean) {
        if (!enabled || music.sourcePkg != PACKAGE || music.song.isBlank()) return
        val app = context.applicationContext
        val pref = app.getSharedPreferences(STORE, Context.MODE_PRIVATE)
        if (lrcTimestamp.containsMatchIn(pref.getString("body", "").orEmpty())) return

        val title = music.song.trim().take(160)
        val artist = music.artist.trim().take(160)
        val key = normalize(title) + "|" + normalize(artist)
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
                lyrics = lookup(title, artist)
                if (lyrics != null) reason = "ok"
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
                "Mozilla/5.0 (Linux; Android 17) AppleWebKit/537.36 " +
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
                return output.toString(StandardCharsets.UTF_8.name())
            }
        } finally {
            conn.disconnect()
        }
    }
}

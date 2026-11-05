#!/usr/bin/env python3
"""v65 after v64: preserve real QiShui track ID across hook->receiver->overlay.

Music-only. Keep v23 IPv4, v29 session, v31 event, v39-40 connection,
v51 IME/audio, v60-64 reverse video/metadata, and all original media art.
"""
from pathlib import Path

R=Path("aa-display/src/main")
C="java/io/github/nitsuya/aa/display/carplay/"
X="java/io/github/nitsuya/aa/display/xposed/hook/"
def one(path,a,b,label):
 p=R/path
 s=p.read_text(encoding="utf-8")
 n=s.count(a)
 if n!=1:raise AssertionError("v65 "+label+" anchors="+str(n))
 p.write_text(s.replace(a,b,1),encoding="utf-8")

# Cross-process data model: existing media id stays as album-art identity;
# new songId carries only a validated track ID for QiShui H5.
one(C+"LyricV53Bridge.kt",
'''   val sourcePkg:String)''',
'''   val sourcePkg:String,val mediaId:String)''',
"music id model")
one(C+"LyricV53Bridge.kt",
'''    p.getString("pkg","").orEmpty())''',
'''    p.getString("pkg","").orEmpty(),
    p.getString("qishui_track_id","").orEmpty())''',
"music id read")

# Only the already UID-verified receiver can write this field. Never trust a
# number in a new title/cover or an unverified sender.
one(C+"CarPlayV62CarMediaReceiver.kt",
'''                if (id != old) {
                    edit.remove("body").remove("line")''',
'''                val changed = id != old ||
                    name != prefs.getString("song", "").orEmpty() ||
                    artist != prefs.getString("artist", "").orEmpty()
                if (changed) {
                    edit.remove("body").remove("line")
                        .remove("qishui_track_id")''',
"clear old lyric when song actually changes")
one(C+"CarPlayV62CarMediaReceiver.kt",
'''                edit.putString("song", name).putString("artist", artist)
                    .putString("id", id)''',
'''                val numericId = data.getString("trackId").orEmpty()
                val trustedId = numericId.takeIf {
                    it.matches(Regex("""\d{6,24}"""))
                }.orEmpty()
                if (trustedId.isNotEmpty()) edit.putString("qishui_track_id", trustedId)
                edit.putString("song", name).putString("artist", artist)
                    .putString("id", id)
                if (changed) Log.i("AAD_V65Lyrics",
                    "car metadata changed, numericTrackId=" + trustedId.isNotEmpty())''',
"persist validated track ID")

# Application-side hook forwards only numeric song IDs, not private tokens.
one(X+"LyricV61CarHook.kt",
'''        var lastKey = ""
        var lastMetaAt = 0L''',
'''        var lastKey = ""
        var lastMetaAt = 0L
        var v65LastTrackId = ""''',
"track ID sender cache")

one(X+"LyricV61CarHook.kt",
'''        fun publish(title: String, artist: String, id: String, image: Bitmap?, source: String) {''',
'''        fun v65RealTrackId(meta: MediaMetadata, platformId: String): String {
            val idRegex = Regex("""\d{6,24}""")
            val embedded = Regex(
                """(?:track[_-]?id|song[_-]?id)[=:/?](\d{6,24})(?!\d)""",
                RegexOption.IGNORE_CASE)
            fun valid(raw: String?): String {
                val value = raw?.trim().orEmpty()
                if (idRegex.matches(value)) return value
                return embedded.find(value)?.groupValues?.getOrNull(1).orEmpty()
            }
            val first = valid(platformId)
            if (first.isNotBlank()) return first
            val likely = arrayOf("track_id", "trackId", "song_id",
                "songId", "luna_track_id", "music_track_id",
                MediaMetadata.METADATA_KEY_MEDIA_URI)
            for (key in likely) {
                val value = runCatching { meta.getString(key) }.getOrNull()
                val id = valid(value)
                if (id.isNotBlank()) return id
            }
            // Key names are observed only in-process; don't log their values.
            for (key in meta.keySet().take(64)) {
                val lower = key.lowercase()
                if (!(lower.contains("track") || lower.contains("song")) ||
                    !lower.contains("id")) continue
                val id = valid(runCatching { meta.getText(key)?.toString() }.getOrNull())
                if (id.isNotBlank()) return id
            }
            return ""
        }

        fun publish(title: String, artist: String, id: String, image: Bitmap?,
                    source: String, trackId: String = "") {''',
"media ID extractor")

one(X+"LyricV61CarHook.kt",
'''            val changed = key != lastKey
            val now = SystemClock.elapsedRealtime()
            if (changed) {
                lastKey = key''',
'''            val cleanTrackId = if (trackId.matches(Regex("""\d{6,24}""")))
                trackId else ""
            val changed = key != lastKey || cleanTrackId != v65LastTrackId
            val now = SystemClock.elapsedRealtime()
            if (changed) {
                lastKey = key
                v65LastTrackId = cleanTrackId''',
"media ID update trigger")

one(X+"LyricV61CarHook.kt",
'''                    it.putString("id", key)
                }
            }
            cover(image, key)''',
'''                    it.putString("id", key)
                    it.putString("trackId", cleanTrackId)
                }
            }
            cover(image, key)''',
"send ID only with meta")

one(X+"LyricV61CarHook.kt",
'''                                publish(title, artist, id, art, "session")''',
'''                                val trackId = v65RealTrackId(m, id)
                                publish(title, artist, id, art, "session", trackId)
                                Log.i(tagName, "v65 MediaSession numericTrackId=" +
                                    trackId.isNotBlank())''',
"hook pass real ID")

# Keep the old v64 lyric class name for minimal source churn.
p=R/(C+"CarPlayV63SodaLyrics.kt")
s=p.read_text(encoding="utf-8")
if "private fun lookupLrclib" not in s or "private fun lookupH5" in s:
 raise AssertionError("v65 requires exact v64 lyric chain")
full=Path("../tools/v65_CarPlayV65SodaLyrics.kt").read_text(encoding="utf-8")
assert full.count("private fun lookupH5(")==1
assert full.count("private fun krcToLrc(")==1
p.write_text(full,encoding="utf-8")

g=Path("aa-display/build.gradle.kts")
v=g.read_text(encoding="utf-8")
if v.count("versionCode = 3164")!=1 or v.count('versionName = "0.3#17.8-v64"')!=1:
 raise AssertionError("v65 exact v64 baseline required")
g.write_text(v.replace("versionCode = 3164","versionCode = 3165")
  .replace('versionName = "0.3#17.8-v64"',
           'versionName = "0.3#17.8-v65"'),encoding="utf-8")
print("v65 QiShui H5 ID/metadata/KRC bridge active, all stable video patches preserved")

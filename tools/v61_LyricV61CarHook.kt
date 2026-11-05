package io.github.nitsuya.aa.display.xposed.hook

import android.app.Application
import android.app.Notification
import android.app.NotificationManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.drawable.BitmapDrawable
import android.net.Uri
import android.util.Size
import android.media.MediaMetadata
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Bundle
import android.os.SystemClock
import android.util.Log
import de.robv.android.xposed.XC_MethodHook
import de.robv.android.xposed.XposedBridge
import de.robv.android.xposed.XposedHelpers
import de.robv.android.xposed.callbacks.XC_LoadPackage
import io.github.nitsuya.aa.display.carplay.LyricV53Bridge
import java.io.ByteArrayOutputStream
import kotlin.concurrent.thread

/** v61 car-only hook. No frame polling, generic UI interception or network scraping. */
object LyricV61CarHook : BaseHook() {
    override val tagName = "AAD_V61Car"
    override fun init(lp: XC_LoadPackage.LoadPackageParam) {
        if (lp.packageName != "com.luna.music.car") return
        var ctx: Context? = null
        var lastKey = ""
        var lastCover = ""
        var lastArtUri = ""
        var lastState = -1
        var lastStateAt = 0L
        var lastSessionAt = 0L
        var lastRawHash = 0

        fun feed(kind: String, fill: (Bundle) -> Unit) {
            val c = ctx ?: return
            runCatching {
                val b = Bundle()
                b.putString("pkg", lp.packageName)
                b.putString("kind", kind)
                fill(b)
                c.contentResolver.call(LyricV53Bridge.URI, "feed", null, b)
            }.onFailure { Log.w(tagName, "v61 bridge " + kind + " failed", it) }
        }

        fun rawLyrics(raw: String) {
            if (raw.length !in 12..64000 || !raw.contains('[')) return
            val hash = raw.hashCode()
            if (hash == lastRawHash) return
            lastRawHash = hash
            feed("raw") { it.putString("body", raw) }
            Log.i(tagName, "v61 timed lyrics accepted len=" + raw.length)
        }

        fun cover(image: Bitmap?, key: String) {
            if (image == null || image.isRecycled || key.isBlank()) return
            val fingerprint = key + ":" + image.generationId
            if (fingerprint == lastCover) return
            lastCover = fingerprint
            thread(name = "v61-car-cover-once", isDaemon = true) {
                runCatching {
                    val w = image.width.coerceAtLeast(1)
                    val h = image.height.coerceAtLeast(1)
                    val factor = minOf(1f, 320f / maxOf(w, h))
                    val sw = (w * factor).toInt().coerceAtLeast(1)
                    val sh = (h * factor).toInt().coerceAtLeast(1)
                    val scaled = if (sw == w && sh == h) image
                        else Bitmap.createScaledBitmap(image, sw, sh, true)
                    val output = ByteArrayOutputStream(40_000)
                    scaled.compress(Bitmap.CompressFormat.JPEG, 76, output)
                    if (scaled !== image) scaled.recycle()
                    val bytes = output.toByteArray()
                    if (bytes.size in 256..160000) {
                        feed("art") {
                            it.putString("id", key)
                            it.putByteArray("jpeg", bytes)
                        }
                        Log.i(tagName, "v61 car cover len=" + bytes.size)
                    }
                }.onFailure { Log.w(tagName, "v61 car cover failed", it) }
            }
        }

        /** Media3/car players may expose only a content URI rather than Bitmap. */
        fun coverUri(uriText: String, key: String) {
            val c = ctx ?: return
            val identity = key + "|" + uriText
            if (uriText.isBlank() || identity == lastArtUri) return
            lastArtUri = identity
            thread(name = "v61-car-cover-uri", isDaemon = true) {
                runCatching {
                    val uri = Uri.parse(uriText)
                    if (uri.scheme == "content" || uri.scheme == "android.resource") {
                        val thumb = c.contentResolver.loadThumbnail(uri, Size(320, 320), null)
                        cover(thumb, key)
                    }
                }.onFailure { Log.w(tagName, "v61 art URI unavailable", it) }
            }
        }

        fun publish(title: String, artist: String, id: String, image: Bitmap?, source: String) {
            val name = title.trim().take(160)
            if (name.isBlank()) return
            val singer = artist.trim().take(160)
            val key = id.trim().ifBlank { "car:" + (name + "|" + singer).hashCode() }
            if (key != lastKey) {
                lastKey = key
                Log.i(tagName, "v61 car metadata source=" + source +
                    " titleLen=" + name.length + " artistLen=" + singer.length +
                    " cover=" + (image != null))
            }
            feed("meta") {
                it.putString("song", name)
                it.putString("artist", singer)
                it.putString("id", key)
            }
            cover(image, key)
        }

        fun state(value: Int, position: Long) {
            val now = SystemClock.elapsedRealtime()
            if (value == lastState && now - lastStateAt < 1_500L) return
            lastState = value
            lastStateAt = now
            feed("state") {
                it.putInt("state", value)
                it.putLong("pos", position.coerceAtLeast(0L))
            }
        }

        XposedBridge.hookAllMethods(Application::class.java, "attach",
            object : XC_MethodHook() {
                override fun afterHookedMethod(p: MethodHookParam) {
                    if (ctx != null) return
                    ctx = p.args.getOrNull(0) as? Context ?: return
                    Log.i(tagName, "v61 car source active")

                    XposedBridge.hookAllMethods(MediaSession::class.java, "setMetadata",
                        object : XC_MethodHook() {
                            override fun afterHookedMethod(q: MethodHookParam) {
                                val m = q.args.getOrNull(0) as? MediaMetadata ?: return
                                val title = m.getString(MediaMetadata.METADATA_KEY_TITLE)
                                    ?: m.getString(MediaMetadata.METADATA_KEY_DISPLAY_TITLE)
                                    ?: ""
                                val artist = m.getString(MediaMetadata.METADATA_KEY_ARTIST)
                                    ?: m.getString(MediaMetadata.METADATA_KEY_DISPLAY_SUBTITLE)
                                    ?: ""
                                val art = m.getBitmap(MediaMetadata.METADATA_KEY_ART)
                                    ?: m.getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART)
                                    ?: m.getBitmap(MediaMetadata.METADATA_KEY_DISPLAY_ICON)
                                lastSessionAt = SystemClock.elapsedRealtime()
                                val id = m.getString(MediaMetadata.METADATA_KEY_MEDIA_ID) ?: ""
                                publish(title, artist, id, art, "session")
                                if (art == null) {
                                    val artUri = m.getString(MediaMetadata.METADATA_KEY_ART_URI)
                                        ?: m.getString(MediaMetadata.METADATA_KEY_ALBUM_ART_URI)
                                        ?: m.getString(MediaMetadata.METADATA_KEY_DISPLAY_ICON_URI)
                                        ?: ""
                                    val identity = id.trim().ifBlank {
                                        "car:" + (title.trim().take(160) + "|" +
                                            artist.trim().take(160)).hashCode()
                                    }
                                    coverUri(artUri, identity)
                                }
                                for (k in arrayOf("lyricInfo",
                                    "android.media.metadata.LYRIC", "lyrics")) {
                                    m.getText(k)?.toString()?.let { rawLyrics(it) }
                                }
                            }
                        })

                    XposedBridge.hookAllMethods(MediaSession::class.java, "setPlaybackState",
                        object : XC_MethodHook() {
                            override fun afterHookedMethod(q: MethodHookParam) {
                                val s = q.args.getOrNull(0) as? PlaybackState ?: return
                                state(s.state, s.position)
                            }
                        })

                    // Some older car builds only expose MediaStyle notifications.
                    XposedBridge.hookAllMethods(NotificationManager::class.java, "notify",
                        object : XC_MethodHook() {
                            override fun afterHookedMethod(q: MethodHookParam) {
                                if (SystemClock.elapsedRealtime() - lastSessionAt < 4_000L) return
                                val n = q.args.firstOrNull { it is Notification } as? Notification
                                    ?: return
                                val extras = n.extras ?: return
                                if (n.category != Notification.CATEGORY_TRANSPORT &&
                                    !extras.containsKey("android.mediaSession")) return
                                val title = extras.getCharSequence(Notification.EXTRA_TITLE)
                                    ?.toString().orEmpty()
                                val artist = extras.getCharSequence(Notification.EXTRA_TEXT)
                                    ?.toString().orEmpty()
                                val image = n.largeIcon ?: runCatching {
                                    (n.getLargeIcon()?.loadDrawable(ctx) as? BitmapDrawable)?.bitmap
                                }.getOrNull()
                                publish(title, artist, "", image, "notification")
                                state(PlaybackState.STATE_PLAYING, 0L)
                            }
                        })

                    // The car variant may share the old phone lyric models.
                    val track = XposedHelpers.findClassIfExists(
                        "com.luna.common.arch.db.entity.TrackLyric", lp.classLoader)
                    if (track != null) {
                        runCatching {
                            XposedBridge.hookAllMethods(track, "getLyric",
                                object : XC_MethodHook() {
                                    override fun afterHookedMethod(q: MethodHookParam) {
                                        (q.result as? String)?.let { rawLyrics(it) }
                                    }
                                })
                        }
                        runCatching {
                            XposedBridge.hookAllMethods(track, "setLyric",
                                object : XC_MethodHook() {
                                    override fun afterHookedMethod(q: MethodHookParam) {
                                        (q.args.getOrNull(0) as? String)?.let { rawLyrics(it) }
                                    }
                                })
                        }
                    }
                    val lyric = XposedHelpers.findClassIfExists(
                        "com.luna.common.arch.db.entity.lyrics.Lyric", lp.classLoader)
                    if (lyric != null) {
                        runCatching {
                            XposedBridge.hookAllConstructors(lyric,
                                object : XC_MethodHook() {
                                    override fun afterHookedMethod(q: MethodHookParam) {
                                        (q.args.getOrNull(1) as? String)?.let { rawLyrics(it) }
                                    }
                                })
                        }
                    }
                    Log.i(tagName, "v61 car lyric model track=" + (track != null) +
                        " lyric=" + (lyric != null))
                }
            })
    }
}

#!/usr/bin/env python3
"""v62: fix QiShui car cross-app metadata delivery on Android 17.

v61 independent car hook used ContentResolver.call to an exported provider.
Log 09:20:38~09:21:04: Android cannot resolve the authority from the car
application, so all title/art/lyrics IPC failed. Keep the provider for the
original phone/QQ hooks; give ONLY the car variant an explicit UID-verified
broadcast fallback. No polling, no audio/video/IME/RTSP changes.

On Android API >=34, BroadcastOptions shares actual sending UID and package;
the receiver refuses unknown/forged senders. API 33 retains old provider.
"""
from pathlib import Path
R=Path("aa-display/src/main")
def one(path,old,new,label):
 p=R/path
 s=p.read_text(encoding="utf-8")
 n=s.count(old)
 if n!=1:raise AssertionError(f"v62 {label}: wanted 1 got {n}")
 p.write_text(s.replace(old,new,1),encoding="utf-8")

receiver=R/"java/io/github/nitsuya/aa/display/carplay/CarPlayV62CarMediaReceiver.kt"
if receiver.exists():raise AssertionError("v62 receiver already exists")
receiver.write_text(r'''package io.github.nitsuya.aa.display.carplay

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.media.session.PlaybackState
import android.util.Log

/**
 * Only the independent QiShui car package can send these explicit broadcasts.
 * API 34+ verifies the OS-supplied identity (not merely the payload).
 * No public query/read API. The pre-existing v54 overlay store is reused.
 */
class CarPlayV62CarMediaReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION || Build.VERSION.SDK_INT < 34) return
        val uid = getSentFromUid()
        val sender = getSentFromPackage()
        if (sender != CAR_PKG || uid < 10000 ||
            context.packageManager.getPackagesForUid(uid)?.contains(CAR_PKG) != true) {
            Log.w("AAD_V62Media", "rejected unverified sender")
            return
        }
        val data = intent.extras ?: return
        val kind = data.getString("kind").orEmpty()
        val prefs = context.getSharedPreferences("v53_lyrics", Context.MODE_PRIVATE)
        val edit = prefs.edit()
        when (kind) {
            "meta" -> {
                val name = data.getString("song").orEmpty().trim().take(160)
                val artist = data.getString("artist").orEmpty().trim().take(160)
                val id = data.getString("id").orEmpty().trim().take(160)
                if (name.isBlank() || id.isBlank()) return
                val old = prefs.getString("id", "").orEmpty()
                if (id != old) {
                    edit.remove("body").remove("line")
                    context.deleteFile("v54_overlay_art.jpg")
                    // Force overlay to clear its old bitmap on track change.
                    edit.putLong("art_revision", SystemClock.elapsedRealtimeNanos())
                    Log.i("AAD_V62Media", "car new song metadata received")
                }
                edit.putString("song", name).putString("artist", artist)
                    .putString("id", id)
            }
            "state" -> {
                val state = data.getInt("state", PlaybackState.STATE_NONE)
                edit.putInt("state", state)
                    .putLong("pos", data.getLong("pos", 0L).coerceAtLeast(0L))
                    .putLong("updated", SystemClock.elapsedRealtime())
            }
            "raw" -> {
                val raw = data.getString("body").orEmpty()
                if (raw.length !in 12..64000 || !raw.contains('[')) return
                edit.putString("body", raw)
                Log.i("AAD_V62Media", "car LRC received len=" + raw.length)
            }
            "art" -> {
                val bytes = data.getByteArray("jpeg") ?: return
                val key = data.getString("id").orEmpty()
                if (key.isBlank() || key != prefs.getString("id", "") ||
                    bytes.size !in 256..160000) return
                try {
                    context.openFileOutput("v54_overlay_art.jpg",
                        Context.MODE_PRIVATE).use { it.write(bytes) }
                    edit.putLong("art_revision", SystemClock.elapsedRealtimeNanos())
                    Log.i("AAD_V62Media", "car cover received bytes=" + bytes.size)
                } catch (e: Exception) {
                    Log.w("AAD_V62Media", "cover persist failed", e)
                    return
                }
            }
            else -> return
        }
        edit.putString("pkg", CAR_PKG)
            .putLong("at", System.currentTimeMillis()).apply()
    }

    companion object {
        const val CAR_PKG = "com.luna.music.car"
        const val ACTION = "io.github.nitsuya.aa.display.action.CAR_MEDIA_V62"
    }
}
''',encoding="utf-8")

# The receiver does not use implicit broadcast resolution; it has a fixed
# package-qualified ComponentName and sender opts in to sharing its identity.
one("AndroidManifest.xml",
'''        <provider
            android:name=".carplay.LyricV53Bridge"''',
'''        <receiver android:name=".carplay.CarPlayV62CarMediaReceiver"
            android:exported="true" />
        <provider
            android:name=".carplay.LyricV53Bridge"''',"receiver manifest")

# Dedicated v61 car hook is a repository template copied by apply_v61.py.
# Edit the *generated* code only; the template remains the v61 baseline.
one("java/io/github/nitsuya/aa/display/xposed/hook/LyricV61CarHook.kt",
'''import android.app.Application''',
'''import android.app.Application
import android.app.BroadcastOptions
import android.content.ComponentName
import android.content.Intent
import android.os.Build''',"hook imports")

one("java/io/github/nitsuya/aa/display/xposed/hook/LyricV61CarHook.kt",
'''                c.contentResolver.call(LyricV53Bridge.URI, "feed", null, b)
            }.onFailure { Log.w(tagName, "v61 bridge " + kind + " failed", it) }''',
'''                if (Build.VERSION.SDK_INT >= 34) {
                    val to = Intent(CarPlayV62CarMediaReceiver.ACTION).apply {
                        component = ComponentName(
                            "io.github.nitsuya.aa.display",
                            "io.github.nitsuya.aa.display.carplay.CarPlayV62CarMediaReceiver")
                        putExtras(b)
                    }
                    val opts = BroadcastOptions.makeBasic()
                        .setShareIdentityEnabled(true).toBundle()
                    c.sendBroadcast(to, null, opts)
                } else {
                    // Old platforms: existing v53 exported provider.
                    c.contentResolver.call(LyricV53Bridge.URI, "feed", null, b)
                }
            }.onFailure { Log.w(tagName, "v62 car IPC " + kind + " failed", it) }''',
"car send broadcast")

one("java/io/github/nitsuya/aa/display/xposed/hook/LyricV61CarHook.kt",
'''import io.github.nitsuya.aa.display.carplay.LyricV53Bridge''',
'''import io.github.nitsuya.aa.display.carplay.LyricV53Bridge
import io.github.nitsuya.aa.display.carplay.CarPlayV62CarMediaReceiver''',
"receiver import")

g=Path("aa-display/build.gradle.kts");s=g.read_text(encoding="utf-8")
if s.count("versionCode = 3161")!=1 or s.count('versionName = "0.3#17.8-v61"')!=1:
 raise AssertionError("v62 requires exact v61 final baseline")
g.write_text(s.replace("versionCode = 3161","versionCode = 3162")
  .replace('versionName = "0.3#17.8-v61"',
           'versionName = "0.3#17.8-v62"'),encoding="utf-8")
print("v62 verified car broadcast IPC and original v54 art store; no video changes")

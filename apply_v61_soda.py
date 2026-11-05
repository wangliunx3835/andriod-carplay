#!/usr/bin/env python3
"""v61 Soda car: media-notification fallback and correct lyricInfo JSON decode."""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(path,a,b,label):
 p=R/path;s=p.read_text(encoding="utf-8");n=s.count(a)
 if n!=1:raise AssertionError("v61 soda "+label+" count="+str(n))
 p.write_text(s.replace(a,b,1),encoding="utf-8")

one("xposed/hook/LyricV53Hook.kt",
 """import android.graphics.Bitmap
import java.io.ByteArrayOutputStream""",
 """import android.graphics.Bitmap
import android.graphics.drawable.BitmapDrawable
import android.app.Notification
import android.app.NotificationManager
import org.json.JSONObject
import java.io.ByteArrayOutputStream""","imports")

one("xposed/hook/LyricV53Hook.kt",
 """  var previousTitle="";var lastBody=0;var lastArtworkKey="" """.rstrip(),
 """  var previousTitle="";var lastBody=0;var lastArtworkKey=""
  var v61PlatformMetaAt=0L
  var v61PlatformStateSeen=false
  var v61NotificationSong=""
  var v61NotificationArt="" """.rstrip(),"fallback state")

one("xposed/hook/LyricV53Hook.kt",
 """  fun accept(raw:String){
   if(raw.length !in 12..64000 || !raw.contains('['))return
   if(raw.hashCode()==lastBody)return
   lastBody=raw.hashCode()
   post("raw"){it.putString("body",raw)}
  }""",
 """  fun accept(raw:String){
   // LRC may arrive wrapped in ColorOS/LyricInfo JSON.
   val value=if(raw.trimStart().startsWith("{"))runCatching{
    val json=JSONObject(raw)
    json.optString("lyric").ifBlank{json.optString("rawLyric")}
   }.getOrDefault("") else raw
   if(value.length !in 12..64000 || !value.contains('['))return
   if(value.hashCode()==lastBody)return
   lastBody=value.hashCode()
   post("raw"){it.putString("body",value)}
  }""","unwrap JSON lyricInfo")

one("xposed/hook/LyricV53Hook.kt",
 """      val m=q.args.getOrNull(0) as? MediaMetadata?:return
      val title=m.getString""",
 """      val m=q.args.getOrNull(0) as? MediaMetadata?:return
      v61PlatformMetaAt=android.os.SystemClock.elapsedRealtime()
      val title=m.getString""","prefer platform metadata")

one("xposed/hook/LyricV53Hook.kt",
 """       val s=q.args.getOrNull(0) as? PlaybackState?:return
       post("state")""",
 """       val s=q.args.getOrNull(0) as? PlaybackState?:return
       v61PlatformStateSeen=true
       post("state")""","prefer platform play state")

one("xposed/hook/LyricV53Hook.kt",
 """      for(key in arrayOf("android.media.metadata.LYRIC","lyricInfo")){""",
 """      for(key in arrayOf("android.media.metadata.LYRIC","lyricInfo",
       "android.media.metadata.LYRICS","lyrics","lrc")){""","extra lyric metadata keys")

one("xposed/hook/LyricV53Hook.kt",
 """    if(pkg=="com.luna.music" || pkg=="com.luna.music.car"){""",
 """    // Independent Soda car builds can publish only a MediaStyle notification.
    // The v54 car package is already in LSP scope. This adds an event-only
    // fallback for song, artist and art; it does NOT sample/scrape UI frames.
    if(pkg=="com.luna.music.car"){
     XposedBridge.hookAllMethods(NotificationManager::class.java,"notify",
      object:XC_MethodHook(){
       override fun afterHookedMethod(q:MethodHookParam){
        val n=q.args.firstOrNull{it is Notification} as? Notification?:return
        val extras=n.extras?:return
        val media=extras.containsKey("android.mediaSession") ||
         n.category==Notification.CATEGORY_TRANSPORT ||
         extras.getString(Notification.EXTRA_TEMPLATE).orEmpty().contains("MediaStyle")
        if(!media)return
        val title=extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()
         ?.trim().orEmpty()
        val singer=extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()
         ?.trim().orEmpty()
        if(title.isBlank() || title=="汽水音乐" || title=="Soda Music")return
        val now=android.os.SystemClock.elapsedRealtime()
        if(now-v61PlatformMetaAt>12_000L){
         val key=title+"|"+singer
         if(key!=v61NotificationSong){
          v61NotificationSong=key
          post("meta"){
           it.putString("song",title.take(160))
           it.putString("artist",singer.take(160))
           it.putString("id",key.take(160))
          }
          Log.i(tagName,"v61 car notification song accepted")
         }
         if(!v61PlatformStateSeen)post("state"){
          it.putInt("state",PlaybackState.STATE_PLAYING)
          it.putLong("pos",0L)
         }
        }
        val ctx=c?:return
        val art=n.largeIcon ?: runCatching{
         (n.getLargeIcon()?.loadDrawable(ctx) as? BitmapDrawable)?.bitmap
        }.getOrNull()
        val artKey=title+"|"+singer+"|"+(art?.generationId?:0)
        if(art!=null && artKey!=v61NotificationArt){
         v61NotificationArt=artKey
         runCatching{
          val small=Bitmap.createScaledBitmap(art,192,192,true)
          val jpg=ByteArrayOutputStream().use{out->
           small.compress(Bitmap.CompressFormat.JPEG,78,out)
           out.toByteArray()
          }
          if(small!==art)small.recycle()
          if(jpg.size in 256..160000)post("art"){
           it.putByteArray("jpeg",jpg)
          }
         }.onFailure{Log.w(tagName,"v61 car cover encode failed",it)}
        }
       }
      })
     Log.i(tagName,"v61 car MediaStyle fallback installed")
    }
    if(pkg=="com.luna.music" || pkg=="com.luna.music.car"){""",
 "notification metadata/art fallback")

one("carplay/LyricV53Bridge.kt",
 """   val next:String,val playing:Boolean,val artworkRevision:Long)""",
 """   val next:String,val playing:Boolean,val artworkRevision:Long,
   val sourcePkg:String)""","source package model")

one("carplay/LyricV53Bridge.kt",
 """    playing,p.getLong("art_revision",0L))""",
 """    playing,p.getLong("art_revision",0L),
    p.getString("pkg","").orEmpty())""","source package read")

one("carplay/CarPlayMediaOverlay.kt",
 """            (observed.playing||rawTitle.isBlank())) {""",
 """            (observed.playing||rawTitle.isBlank()||
                observed.sourcePkg=="com.luna.music.car")) {""",
 "prioritize car metadata over stale lyric ticker")
print("v61 Soda car notification fallback + lyricInfo JSON fix applied")

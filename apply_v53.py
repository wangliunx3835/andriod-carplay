#!/usr/bin/env python3
from pathlib import Path
r=Path("aa-display/src/main")
def upd(p,a,b):
 f=r/p;s=f.read_text()
 if s.count(a)!=1:raise RuntimeError(str(p)+" match "+str(s.count(a)))
 f.write_text(s.replace(a,b,1))
def new(p,t):
 f=r/p;f.parent.mkdir(parents=True,exist_ok=True)
 if f.exists():raise RuntimeError("exists "+str(p))
 f.write_text(t)
new("java/io/github/nitsuya/aa/display/carplay/LyricV53Bridge.kt",r'''package io.github.nitsuya.aa.display.carplay
import android.content.*
import android.database.Cursor
import android.net.Uri
import android.os.*
import android.media.session.PlaybackState
import android.util.Log

class LyricV53Bridge:ContentProvider() {
 companion object {
  val URI=Uri.parse("content://io.github.nitsuya.aa.display.lyricv53")
  private val allowed=setOf("com.luna.music","com.tencent.qqmusic",
   "com.tencent.qqmusiccar","com.tencent.qqmusicpad","com.netease.cloudmusic")
  private const val FILE="v53_lyrics"
  data class Music(val song:String,val artist:String,val current:String,
   val next:String,val playing:Boolean)
  private val lrc=Regex("""\[(\d+):(\d+)(?:[.:](\d+))?]\s*(.*)""")
  private val krc=Regex("""\[(\d+),(\d+)]\s*(.*)""")
  private val word=Regex("""<\d+,\d+,\d+>""")
  private fun lines(raw:String,position:Long):Pair<String,String>? {
   val list=ArrayList<Pair<Long,String>>()
   for(row in raw.lineSequence()){
    val s=row.trim()
    val m=lrc.matchEntire(s)
    if(m!=null) {
     val a=m.groupValues;val f=a[3]
     val ms=when(f.length){1->(f.toLongOrNull()?:0)*100L
      2->(f.toLongOrNull()?:0)*10L
      else->f.take(3).padEnd(3,'0').toLongOrNull()?:0L}
     list.add(((a[1].toLongOrNull()?:0)*60000L+
      (a[2].toLongOrNull()?:0)*1000L+ms) to a[4])
    } else {
     val k=krc.matchEntire(s)?:continue
     list.add((k.groupValues[1].toLongOrNull()?:0L) to
      k.groupValues[3].replace(word,""))
    }
   }
   list.sortBy{it.first}
   val i=list.indexOfLast{it.first<=position}
   if(i<0)return null
   return list[i].second to list.getOrNull(i+1)?.second.orEmpty()
  }
  fun read(c:Context):Music? {
   val p=c.getSharedPreferences(FILE,0)
   val name=p.getString("song","").orEmpty()
   if(name.isBlank()||System.currentTimeMillis()-p.getLong("at",0L)>600000L)return null
   val state=p.getInt("state",0)
   val playing=state==PlaybackState.STATE_PLAYING||state==PlaybackState.STATE_BUFFERING
   val tick=(SystemClock.elapsedRealtime()-p.getLong("updated",0L)).coerceIn(0L,600000L)
   val pos=p.getLong("pos",0L)+(if(playing)tick else 0L)
   val l=lines(p.getString("body","").orEmpty(),pos)
   return Music(name,p.getString("artist","").orEmpty(),
    l?.first?:p.getString("line","").orEmpty(),l?.second.orEmpty(),playing)
  }
 }
 override fun onCreate()=true
 override fun query(uri:Uri,projection:Array<out String>?,selection:String?,
  selectionArgs:Array<out String>?,sortOrder:String?):Cursor?=null
 override fun getType(uri:Uri):String?=null
 override fun insert(uri:Uri,values:ContentValues?):Uri?=null
 override fun delete(uri:Uri,selection:String?,selectionArgs:Array<out String>?):Int=0
 override fun update(uri:Uri,values:ContentValues?,selection:String?,
  selectionArgs:Array<out String>?):Int=0
 override fun call(method:String,arg:String?,extras:Bundle?):Bundle {
  val result=Bundle()
  val c=context?:return result
  if(method!="feed"||extras==null)return result
  val pkg=extras.getString("pkg").orEmpty()
  val own=c.packageManager.getPackagesForUid(Binder.getCallingUid())?.toSet().orEmpty()
  if(pkg !in allowed || pkg !in own)return result
  val p=c.getSharedPreferences(FILE,0)
  val e=p.edit()
  when(extras.getString("kind")){
   "meta" -> {
    val s=extras.getString("song").orEmpty().take(160)
    if(s.isBlank())return result
    val id=extras.getString("id").orEmpty().take(160)
    if(id.isNotBlank()&&id!=p.getString("id",""))e.remove("body").remove("line")
    e.putString("song",s).putString("id",id)
     .putString("artist",extras.getString("artist").orEmpty().take(160))
    val l=extras.getString("line").orEmpty()
    if(l.isNotBlank())e.putString("line",l.take(160))
   }
   "state" -> e.putInt("state",extras.getInt("state",0))
    .putLong("pos",extras.getLong("pos",0L))
    .putLong("updated",SystemClock.elapsedRealtime())
   "raw" -> {
    val body=extras.getString("body").orEmpty()
    if(body.length in 12..64000){
     e.putString("body",body)
     Log.i("AAD_V53Lyrics","raw accepted pkg="+pkg+" length="+body.length)
    }
   }
   else -> return result
  }
  e.putString("pkg",pkg).putLong("at",System.currentTimeMillis()).apply()
  result.putBoolean("ok",true)
  return result
 }
}
''')

new("java/io/github/nitsuya/aa/display/xposed/hook/LyricV53Hook.kt",r'''package io.github.nitsuya.aa.display.xposed.hook
import android.app.Application
import android.content.Context
import android.media.MediaMetadata
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Bundle
import android.util.Log
import de.robv.android.xposed.XC_MethodHook
import de.robv.android.xposed.XposedBridge
import de.robv.android.xposed.XposedHelpers
import de.robv.android.xposed.callbacks.XC_LoadPackage
import io.github.nitsuya.aa.display.carplay.LyricV53Bridge
/** App-only observation: no A2DP spoof, audio route or system_server change. */
object LyricV53Hook:BaseHook(){
 override val tagName="AAD_V53Lyrics"
 override fun init(lp:XC_LoadPackage.LoadPackageParam){
  val pkg=lp.packageName
  var c:Context?=null;var song="";var artist="";var mediaId=""
  var previousTitle="";var lastBody=0
  fun post(kind:String,build:(Bundle)->Unit){
   val ctx=c?:return
   runCatching{
    val b=Bundle()
    b.putString("pkg",pkg);b.putString("kind",kind);build(b)
    ctx.contentResolver.call(LyricV53Bridge.URI,"feed",null,b)
   }.onFailure{Log.w(tagName,"IPC error "+it.javaClass.simpleName)}
  }
  fun accept(raw:String){
   if(raw.length !in 12..64000 || !raw.contains('['))return
   if(raw.hashCode()==lastBody)return
   lastBody=raw.hashCode()
   post("raw"){it.putString("body",raw)}
  }
  XposedBridge.hookAllMethods(Application::class.java,"attach",object:XC_MethodHook(){
   override fun afterHookedMethod(p:MethodHookParam){
    if(c!=null)return
    c=p.args.getOrNull(0) as? Context?:return
    XposedBridge.hookAllMethods(MediaSession::class.java,"setMetadata",object:XC_MethodHook(){
     override fun afterHookedMethod(q:MethodHookParam){
      val m=q.args.getOrNull(0) as? MediaMetadata?:return
      val title=m.getString(MediaMetadata.METADATA_KEY_TITLE).orEmpty().trim()
      val singer=m.getString(MediaMetadata.METADATA_KEY_ARTIST).orEmpty().trim()
      val id=m.getString(MediaMetadata.METADATA_KEY_MEDIA_ID).orEmpty().trim()
      val line=if(id.isNotBlank()&&id==mediaId&&singer==artist&&
       title.isNotBlank()&&title!=previousTitle)title else ""
      if(id!=mediaId||singer!=artist||song.isBlank()) {
       song=title;artist=singer;mediaId=id
      }
      previousTitle=title
      post("meta"){
       it.putString("song",song.ifBlank{title})
       it.putString("artist",singer)
       it.putString("id",id)
       it.putString("line",line)
      }
      for(key in arrayOf("android.media.metadata.LYRIC","lyricInfo")){
       val payload=runCatching{m.getText(key)?.toString()}.getOrNull()
       if(!payload.isNullOrBlank())accept(payload)
      }
      if(line.isNotBlank())Log.i(tagName,"ticker captured pkg="+pkg+" length="+line.length)
     }
    })
    XposedBridge.hookAllMethods(MediaSession::class.java,"setPlaybackState",
     object:XC_MethodHook(){
      override fun afterHookedMethod(q:MethodHookParam){
       val s=q.args.getOrNull(0) as? PlaybackState?:return
       post("state"){it.putInt("state",s.state)
        it.putLong("pos",s.position.coerceAtLeast(0L))}
      }
     })
    if(pkg=="com.luna.music"){
     val lyric=XposedHelpers.findClassIfExists(
      "com.luna.common.arch.db.entity.lyrics.Lyric",lp.classLoader)
     if(lyric!=null){
      XposedBridge.hookAllConstructors(lyric,object:XC_MethodHook(){
       override fun afterHookedMethod(q:MethodHookParam){
        accept(q.args.getOrNull(1) as? String?:return)
       }
      })
      Log.i(tagName,"Soda lyric ctor ready")
     } else Log.w(tagName,"Soda lyric ctor absent")
     val track=XposedHelpers.findClassIfExists(
      "com.luna.common.arch.db.entity.TrackLyric",lp.classLoader)
     if(track!=null){
      XposedBridge.hookAllMethods(track,"getLyric",object:XC_MethodHook(){
       override fun afterHookedMethod(q:MethodHookParam){
        accept(q.result as? String?:return)
       }
      })
      XposedBridge.hookAllMethods(track,"setLyric",object:XC_MethodHook(){
       override fun afterHookedMethod(q:MethodHookParam){
        accept(q.args.getOrNull(0) as? String?:return)
       }
      })
      Log.i(tagName,"Soda TrackLyric ready")
     } else Log.w(tagName,"Soda TrackLyric absent")
    }
    Log.i(tagName,"hook installed pkg="+pkg)
   }
  })
 }
}
''')

upd("java/io/github/nitsuya/aa/display/xposed/XposedInit.kt",
 'import io.github.nitsuya.aa.display.xposed.hook.BaseHook',
 'import io.github.nitsuya.aa.display.xposed.hook.BaseHook\nimport io.github.nitsuya.aa.display.xposed.hook.LyricV53Hook')
upd("java/io/github/nitsuya/aa/display/xposed/XposedInit.kt",
 '            packageName == "io.github.nitsuya.aa.display" -> arrayOf(AaDisplayProcessHook)\n            else -> null',
 '            packageName == "io.github.nitsuya.aa.display" -> arrayOf(AaDisplayProcessHook)\n            packageName in setOf("com.luna.music","com.tencent.qqmusic",\n                "com.tencent.qqmusiccar","com.tencent.qqmusicpad",\n                "com.netease.cloudmusic") -> arrayOf(LyricV53Hook)\n            else -> null')
upd("res/values/arrays.xml",
 '        <item>io.github.nitsuya.aa.display</item>',
 '        <item>io.github.nitsuya.aa.display</item>\n        <item>com.luna.music</item>\n        <item>com.tencent.qqmusic</item>\n        <item>com.tencent.qqmusiccar</item>\n        <item>com.tencent.qqmusicpad</item>\n        <item>com.netease.cloudmusic</item>')
upd("AndroidManifest.xml",
 '        <service\n            android:name=".service.ClusterLyricMediaService"',
 '        <provider\n            android:name=".carplay.LyricV53Bridge"\n            android:authorities="io.github.nitsuya.aa.display.lyricv53"\n            android:exported="true" />\n        <service\n            android:name=".service.ClusterLyricMediaService"')
upd("java/io/github/nitsuya/aa/display/carplay/CarPlayMediaOverlay.kt",
 '        val fresh = ClusterLyricStore.readFresh(cr)',
 '        val observed=LyricV53Bridge.read(c)\n        val fresh = ClusterLyricStore.readFresh(cr)')
upd("java/io/github/nitsuya/aa/display/carplay/CarPlayMediaOverlay.kt",
 '        if (rawTitle.isBlank()) { media = Media(); return }',
 '        if (observed!=null && observed.song.isNotBlank() &&\n            (observed.playing||rawTitle.isBlank())) {\n            media=Media(title=observed.song,artist=observed.artist,\n                current=observed.current,next=observed.next,\n                playing=observed.playing,art=cachedArt)\n            return\n        }\n        if (rawTitle.isBlank()) { media = Media(); return }')
p=Path("aa-display/build.gradle.kts")
s=p.read_text()
if "versionCode = 3152" not in s:raise RuntimeError("v52 version missing")
s=s.replace("versionCode = 3152","versionCode = 3153")
s=s.replace('versionName = "0.3#17.8-v52"','versionName = "0.3#17.8-v53"')
p.write_text(s)
print("v53 app-only lyric hooks and bounded IPC applied")

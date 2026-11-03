from pathlib import Path
R=Path("aa-display/src/main")
def change(path,old,new):
 p=R/path;s=p.read_text()
 assert s.count(old)==1,(path,s.count(old))
 p.write_text(s.replace(old,new,1))
def add(path,src):
 p=R/path;assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(src)
J="java/io/github/nitsuya/aa/display/"
add(J+"xposed/hook/V53SodaHook.kt",r'''package io.github.nitsuya.aa.display.xposed.hook
import android.app.Application
import android.net.Uri
import android.os.Bundle
import android.util.Log
import de.robv.android.xposed.XC_MethodHook
import de.robv.android.xposed.XposedBridge
import de.robv.android.xposed.callbacks.XC_LoadPackage
import android.media.MediaMetadata

/** Passive app-local LRC/KRC capture; does not spoof Bluetooth state. */
object V53SodaHook {
    private const val TAG="AAD_V53Lyric"
    private val uri=Uri.parse("content://io.github.nitsuya.aa.display.v53lyrics")
    @Volatile private var lastHash=0
    fun install(lp:XC_LoadPackage.LoadPackageParam) {
        val pkg=lp.packageName
        if(pkg=="com.luna.music") {
            val cls=runCatching{Class.forName("com.luna.common.arch.db.entity.lyrics.Lyric",false,lp.classLoader)}.getOrNull()
            if(cls==null) { Log.w(TAG,"Soda lyric class not found in "+lp.processName);return }
            var count=0
            for(ctor in cls.declaredConstructors) {
                val params=ctor.parameterTypes
                if(params.size<2 || params[1]!=String::class.java || !params[0].name.endsWith(".NetLyricType"))continue
                if(params.any { it.name=="kotlin.jvm.internal.DefaultConstructorMarker" })continue
                runCatching { XposedBridge.hookMethod(ctor,object:XC_MethodHook() {
                    override fun afterHookedMethod(param:MethodHookParam) {
                        val body=param.args.getOrNull(1) as? String ?:return
                        val format=param.args.getOrNull(0)?.toString().orEmpty()
                        val lang=param.args.getOrNull(2)?.toString().orEmpty()
                        send(pkg,format,lang,body)
                    }
                });count++ }.onFailure {Log.w(TAG,"Soda hook fail",it)}
            }
            Log.i(TAG,"Soda raw lyric constructors hooked="+count+" process="+lp.processName)
        } else if(pkg=="com.tencent.qqmusic" || pkg=="com.netease.cloudmusic") {
            val m=MediaMetadata.Builder::class.java.getDeclaredMethod("putString",String::class.java,String::class.java)
            runCatching {XposedBridge.hookMethod(m,object:XC_MethodHook(){
                override fun afterHookedMethod(param:MethodHookParam) {
                    val k=param.args.getOrNull(0) as? String ?:return
                    val v=param.args.getOrNull(1) as? String ?:return
                    if(k.contains("lyric",ignoreCase=true))send(pkg,"MEDIA",k,v)
                }
            })}.onFailure{Log.w(TAG,"metadata probe failed",it)}
            Log.i(TAG,"metadata lyric probe armed "+pkg+" process="+lp.processName)
        }
    }
    private fun send(pkg:String,fmt:String,lang:String,body:String) {
        if(body.length !in 18..160000)return
        val key=pkg.hashCode()*31+body.hashCode()+fmt.hashCode()
        if(key==lastHash)return
        lastHash=key
        val app=runCatching {
            val at=Class.forName("android.app.ActivityThread")
            at.getDeclaredMethod("currentApplication").invoke(null) as? Application
        }.getOrNull() ?:run {
            Log.w(TAG,"App context unavailable");return
        }
        runCatching {
            val r=app.contentResolver.call(uri,"publish",null,Bundle().apply {
                putString("pkg",pkg);putString("fmt",fmt.take(32))
                putString("lang",lang.take(40));putString("body",body)
            })
            Log.i(TAG,"capture package="+pkg+" format="+fmt+" length="+body.length+" accepted="+r?.getBoolean("ok"))
        }.onFailure{Log.w(TAG,"IPC error "+it.javaClass.simpleName+": "+it.message)}
    }
}
''')
add(J+"carplay/V53LyricProvider.kt",r'''package io.github.nitsuya.aa.display.carplay
import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.net.Uri
import android.os.Binder
import android.os.Bundle
import android.os.SystemClock
import android.util.Log

/** App-private lyric IPC. Only UID of requested music app is accepted. */
class V53LyricProvider:ContentProvider(){
    override fun onCreate()=true
    override fun call(method:String,arg:String?,extras:Bundle?):Bundle? {
        if(method!="publish")return Bundle()
        val c=context ?:return Bundle()
        val pkg=extras?.getString("pkg").orEmpty()
        val allowed=setOf("com.luna.music","com.tencent.qqmusic","com.netease.cloudmusic")
        val identities=c.packageManager.getPackagesForUid(Binder.getCallingUid())?.toSet().orEmpty()
        if(pkg !in allowed || pkg !in identities){
            Log.w("AAD_V53Lyric","caller rejected");return Bundle()
        }
        val body=extras?.getString("body").orEmpty()
        if(body.length !in 18..160000)return Bundle()
        c.getSharedPreferences("v53_lyric",0).edit()
            .putString("pkg",pkg).putString("fmt",extras?.getString("fmt"))
            .putString("lang",extras?.getString("lang")).putString("body",body)
            .putLong("at",SystemClock.elapsedRealtime()).apply()
        Log.i("AAD_V53Lyric","stored raw lyric from "+pkg+" chars="+body.length)
        return Bundle().apply{putBoolean("ok",true)}
    }
    override fun query(u:Uri,p:Array<String>?,s:String?,a:Array<String>?,o:String?):Cursor?=null
    override fun getType(u:Uri):String?=null
    override fun insert(u:Uri,v:ContentValues?):Uri?=null
    override fun delete(u:Uri,s:String?,a:Array<String>?):Int=0
    override fun update(u:Uri,v:ContentValues?,s:String?,a:Array<String>?):Int=0
}
''')
add(J+"carplay/V53CapturedLyrics.kt",r'''package io.github.nitsuya.aa.display.carplay
import android.content.Context
import android.os.SystemClock
import android.util.Log

/** Lightweight line-timed LRC/KRC adapter, runs off GL/render thread. */
object V53CapturedLyrics {
    data class Line(val t:Long,val s:String)
    private val lrc=Regex("""\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?]\s*(.+)""")
    private val krc=Regex("""^\[(\d+),(\d+)](.*)""")
    private val word=Regex("""<\d+,\d+(?:,\d+)?>""")
    private var lastHash=0
    private var cached=emptyList<Line>()
    private var lastPkg=""
    fun get(context:Context,pkg:String,pos:Long):Pair<String,String> {
        val pref=context.getSharedPreferences("v53_lyric",0)
        val source=pref.getString("pkg","").orEmpty()
        val at=pref.getLong("at",0L)
        if(source!=pkg || at<=0L || SystemClock.elapsedRealtime()-at>90000L)return "" to ""
        val body=pref.getString("body","").orEmpty()
        val hash=body.hashCode()
        if(hash!=lastHash || source!=lastPkg) {
            val parsed=ArrayList<Line>()
            for(raw in body.lineSequence()) {
                val text=raw.trim()
                val m=lrc.matchEntire(text)
                if(m!=null) {
                    val mm=m.groupValues[1].toLongOrNull()?:continue
                    val ss=m.groupValues[2].toLongOrNull()?:continue
                    val d=m.groupValues[3]
                    val frac=when(d.length){0->0L;1->d.toLong()*100;2->d.toLong()*10;else->d.take(3).toLong()}
                    parsed.add(Line(mm*60000+ss*1000+frac,m.groupValues[4].trim()))
                    continue
                }
                val k=krc.matchEntire(text)?:continue
                val start=k.groupValues[1].toLongOrNull()?:continue
                parsed.add(Line(start,k.groupValues[3].replace(word,"").trim()))
            }
            cached=parsed.filter{it.s.isNotBlank()}.sortedBy{it.t}.take(500)
            lastHash=hash;lastPkg=source
            Log.i("AAD_V53Lyric","parsed "+source+" lines="+cached.size)
        }
        if(cached.size<2)return "" to ""
        val i=cached.indexOfLast{it.t<=pos}
        return if(i<0)"" to "" else cached[i].s to cached.getOrNull(i+1)?.s.orEmpty()
    }
}
''')
change(J+"xposed/XposedInit.kt",
'import io.github.nitsuya.aa.display.xposed.hook.BaseHook',
'import io.github.nitsuya.aa.display.xposed.hook.BaseHook\nimport io.github.nitsuya.aa.display.xposed.hook.V53SodaHook')
change(J+"xposed/XposedInit.kt",
'        val packageName = lpparam.packageName\n        when {',
'''        val packageName = lpparam.packageName
        if(packageName in setOf("com.luna.music","com.tencent.qqmusic","com.netease.cloudmusic")) {
            runCatching { V53SodaHook.install(lpparam) }
                .onFailure { android.util.Log.w(TAG,"v53 hook error",it) }
            return
        }
        when {''')
change("res/values/arrays.xml",
'        <item>io.github.nitsuya.aa.display</item>',
'''        <item>io.github.nitsuya.aa.display</item>
        <item>com.luna.music</item>
        <item>com.tencent.qqmusic</item>
        <item>com.netease.cloudmusic</item>''')
change("AndroidManifest.xml",
'        <activity\n            android:name=".ui.main.MainActivity"',
'''        <provider
            android:name=".carplay.V53LyricProvider"
            android:authorities="io.github.nitsuya.aa.display.v53lyrics"
            android:exported="true" />
        <activity
            android:name=".ui.main.MainActivity"''')
change(J+"carplay/CarPlayMediaOverlay.kt",
'''        media = Media(
            title = song.ifEmpty { rawTitle },''',
'''        val currentPkg=Settings.Global.getString(cr,ClusterLyricStore.SETTINGS_SOURCE_PKG).orEmpty()
        val progress=ClusterLyricStore.readProgress(cr)
        val lyricPos=progress?.let { ClusterLyricStore.extrapolatePosition(it) } ?:0L
        val v53Pair=V53CapturedLyrics.get(c,currentPkg,lyricPos)
        media = Media(
            title = song.ifEmpty { rawTitle },''')
change(J+"carplay/CarPlayMediaOverlay.kt",
'''            current = rawTitle.takeIf { it != song && it.isNotBlank() }.orEmpty(),
            next = next,''',
'''            current = v53Pair.first.ifBlank {
                rawTitle.takeIf { it != song && it.isNotBlank() }.orEmpty()
            },
            next = v53Pair.second.ifBlank { next },''')
p=Path("aa-display/build.gradle.kts")
v=p.read_text();assert "versionCode = 3152" in v and 'versionName = "0.3#17.8-v52"' in v
v=v.replace("versionCode = 3152","versionCode = 3153").replace('versionName = "0.3#17.8-v52"','versionName = "0.3#17.8-v53"')
p.write_text(v)
print("v53 passive lyric capture patch applied")

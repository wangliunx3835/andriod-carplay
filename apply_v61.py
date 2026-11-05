#!/usr/bin/env python3
"""v61 after v60: long-reverse video refresh + dedicated QiShui car metadata bridge."""
from pathlib import Path
R=Path("aa-display/src/main")
def one(path,old,new,label):
 p=R/path;s=p.read_text(encoding="utf-8");n=s.count(old)
 if n!=1:raise AssertionError("v61 "+label+" matches="+str(n))
 p.write_text(s.replace(old,new,1),encoding="utf-8")

# Without receiver-side displayed-frame feedback, TCP Send-Q=0 is not proof
# of a decoded picture. Refresh video ONLY ONCE after >=8s backupCamera BORROW,
# after the proven v60 5.5s safe window. Do not restart RTSP/AAC/encoder.
one("java/io/github/nitsuya/aa/display/carplay/CarPlayV60VideoPolicy.kt",
'''    @Volatile private var lastReturnMs = 0L''',
'''    @Volatile private var lastReturnMs = 0L
    private var v61BorrowStartMs = 0L
    private var v61LongReturnPending = false
    fun claimLongReturn(): Boolean = synchronized(this) {
        if (cameraBorrowed || !v61LongReturnPending || !mayReSetupVideo()) false
        else {
            v61LongReturnPending = false
            true
        }
    }''',"camera pending")
one("java/io/github/nitsuya/aa/display/carplay/CarPlayV60VideoPolicy.kt",
'''        // Release timestamp is published before cameraBorrowed=false.
        if (!borrowed) lastReturnMs = SystemClock.elapsedRealtime()
        cameraBorrowed = borrowed''',
'''        val now = SystemClock.elapsedRealtime()
        if (borrowed) {
            v61BorrowStartMs = now
            v61LongReturnPending = false
        } else {
            val held = if (v61BorrowStartMs>0) now-v61BorrowStartMs else 0L
            v61LongReturnPending = held >= 8_000L
            v61BorrowStartMs = 0L
            lastReturnMs = now
            Log.i(CarPlayConsts.TAG,"v61 camera heldMs="+held+
                " videoRefreshPending="+v61LongReturnPending)
        }
        cameraBorrowed = borrowed''',"camera duration")
one("java/io/github/nitsuya/aa/display/carplay/CarPlayV60VideoPolicy.kt",
'''        cameraBorrowed = false
        lastReturnMs = 0L
    }''',
'''        cameraBorrowed = false
        lastReturnMs = 0L
        v61BorrowStartMs = 0L
        v61LongReturnPending = false
    }''',"camera reset")

one("java/io/github/nitsuya/aa/display/carplay/CarPlayRtspSession.kt",
'''    private fun v58TryRecovery(reason: String) {''',
'''    private fun v58TryRecovery(reason: String, forceVideo: Boolean = false) {''',
"recovery signature")
one("java/io/github/nitsuya/aa/display/carplay/CarPlayRtspSession.kt",
'''        val closed = screenEgress.get()?.isClosed() == true
        if (stall < 2500L && !closed && !v58VideoUnusable.get()) return''',
'''        // Null video stream is unavailable, NOT a healthy open socket.
        val closed = screenEgress.get()?.isClosed() != false
        if (stall < 2500L && !closed && !v58VideoUnusable.get() &&
            !forceVideo) return''',"null socket health")
one("java/io/github/nitsuya/aa/display/carplay/CarPlayRtspSession.kt",
'''                    Log.i(CarPlayConsts.TAG, "v59 return probe reason=" + reason +
                        " stalledMs=" + stall + " egressClosed=" +
                        (screenEgress.get()?.isClosed() == true))
                    v58TryRecovery("v59-return:" + reason)''',
'''                    val video = screenEgress.get()
                    val missing = video == null || video.isClosed()
                    val cameraReturn = CarPlayV60VideoPolicy.claimLongReturn()
                    Log.i(CarPlayConsts.TAG,"v61 return probe reason="+reason+
                        " stalledMs="+stall+" videoMissing="+missing+
                        " longCamera="+cameraReturn+
                        " localFrames="+(video?.stats()?.first ?: -1L))
                    v58TryRecovery("v61-return:"+reason,
                        forceVideo = missing || cameraReturn)''',
"one-shot long camera return")

# Dedicated package has a separate LSPosed scope and hook. Phone version and
# QQ/Netease source hooks are untouched.
one("java/io/github/nitsuya/aa/display/xposed/XposedInit.kt",
'import io.github.nitsuya.aa.display.xposed.hook.LyricV53Hook',
'''import io.github.nitsuya.aa.display.xposed.hook.LyricV53Hook
import io.github.nitsuya.aa.display.xposed.hook.LyricV61CarHook''',"car import")
one("java/io/github/nitsuya/aa/display/xposed/XposedInit.kt",
'''            packageName in setOf("com.luna.music","com.tencent.qqmusic",''',
'''            packageName == "com.luna.music.car" -> arrayOf(LyricV61CarHook)
            packageName in setOf("com.luna.music","com.tencent.qqmusic",''',
"car package match")
one("res/values/arrays.xml",
'''        <item>com.luna.music</item>''',
'''        <item>com.luna.music</item>
        <item>com.luna.music.car</item>''',"LSPosed scope")

p=R/"java/io/github/nitsuya/aa/display/xposed/hook/LyricV61CarHook.kt"
if p.exists():raise AssertionError("v61 duplicate car source")
p.write_text(Path("../tools/v61_LyricV61CarHook.kt").read_text(encoding="utf-8"),
 encoding="utf-8")

one("java/io/github/nitsuya/aa/display/carplay/LyricV53Bridge.kt",
'''  private val allowed=setOf("com.luna.music","com.tencent.qqmusic",''',
'''  private val allowed=setOf("com.luna.music","com.luna.music.car",
   "com.tencent.qqmusic",''',"bridge allowed packages")
one("java/io/github/nitsuya/aa/display/carplay/LyricV53Bridge.kt",
'''  data class Music(val song:String,val artist:String,val current:String,
   val next:String,val playing:Boolean)''',
'''  data class Music(val song:String,val artist:String,val current:String,
   val next:String,val playing:Boolean,val pkg:String,val coverRev:Long)
  fun readCarCover(c:Context):ByteArray? = runCatching {
   c.openFileInput("v61_car_cover.jpg").use{it.readBytes()}
  }.getOrNull()''',"bridge cover revision")
one("java/io/github/nitsuya/aa/display/carplay/LyricV53Bridge.kt",
'''    l?.first?:p.getString("line","").orEmpty(),l?.second.orEmpty(),playing)''',
'''    l?.first?:p.getString("line","").orEmpty(),l?.second.orEmpty(),playing,
    p.getString("pkg","").orEmpty(),p.getLong("coverRev",0L))''',"bridge read revision")
one("java/io/github/nitsuya/aa/display/carplay/LyricV53Bridge.kt",
'''    if(id.isNotBlank()&&id!=p.getString("id",""))e.remove("body").remove("line")''',
'''    if(id.isNotBlank()&&id!=p.getString("id","")) {
     e.remove("body").remove("line").putLong("coverRev",0L)
    }''',"new song clears old art")
one("java/io/github/nitsuya/aa/display/carplay/LyricV53Bridge.kt",
'''   else -> return result
  }
  e.putString("pkg",pkg)''',
'''   "cover" -> {
    if(pkg!="com.luna.music.car")return result
    val jpg=extras.getByteArray("jpeg")?:return result
    if(jpg.size !in 100..260000)return result
    val id=extras.getString("id").orEmpty()
    if(id.isBlank() || id!=p.getString("id","").orEmpty())return result
    runCatching {
     c.openFileOutput("v61_car_cover.jpg",Context.MODE_PRIVATE).use{it.write(jpg)}
     e.putLong("coverRev",SystemClock.elapsedRealtimeNanos())
    }.onFailure{Log.w("AAD_V61Car","cover write failed",it)}
   }
   else -> return result
  }
  e.putString("pkg",pkg)''',"bounded jpg IPC")

# Decode cover JPEG only on its version change, not every 650ms refresh;
# keep existing cluster artwork and mobile QiShui behavior unchanged.
one("java/io/github/nitsuya/aa/display/carplay/CarPlayMediaOverlay.kt",
'''    private var cachedArt: Bitmap? = null''',
'''    private var cachedArt: Bitmap? = null
    private var v61ArtRev = Long.MIN_VALUE
    private var v61CarArt: Bitmap? = null''',"media cover fields")
one("java/io/github/nitsuya/aa/display/carplay/CarPlayMediaOverlay.kt",
'''        cachedArt = null
        lastArtRevision = Long.MIN_VALUE''',
'''        cachedArt = null
        v61CarArt = null
        v61ArtRev = Long.MIN_VALUE
        lastArtRevision = Long.MIN_VALUE''',"media cover cleanup")
one("java/io/github/nitsuya/aa/display/carplay/CarPlayMediaOverlay.kt",
'''        if (observed!=null && observed.song.isNotBlank() &&
            (observed.playing||rawTitle.isBlank())) {
            media=Media(title=observed.song,artist=observed.artist,
                current=observed.current,next=observed.next,
                playing=observed.playing,art=cachedArt)''',
'''        if (observed!=null && observed.song.isNotBlank() &&
            (observed.playing||rawTitle.isBlank())) {
            if(observed.pkg=="com.luna.music.car" && observed.coverRev!=v61ArtRev){
                v61ArtRev=observed.coverRev
                val jpg=if(observed.coverRev!=0L) LyricV53Bridge.readCarCover(c)
                    else null
                v61CarArt=if(jpg!=null)runCatching {
                    BitmapFactory.decodeByteArray(jpg,0,jpg.size)
                }.getOrNull() else null
            }
            media=Media(title=observed.song,artist=observed.artist,
                current=observed.current,next=observed.next,
                playing=observed.playing,
                art=if(observed.pkg=="com.luna.music.car")
                    v61CarArt ?: cachedArt else cachedArt)''',"overlay car cover")

g=Path("aa-display/build.gradle.kts")
s=g.read_text(encoding="utf-8")
if s.count("versionCode = 3160")!=1 or s.count('versionName = "0.3#17.8-v60"')!=1:
 raise AssertionError("v61 exact v60 baseline required")
g.write_text(s.replace("versionCode = 3160","versionCode = 3161")
  .replace('versionName = "0.3#17.8-v60"',
   'versionName = "0.3#17.8-v61"'),encoding="utf-8")
print("v61 long-reverse one-shot video refresh + QiShui car metadata/cover/lyrics")

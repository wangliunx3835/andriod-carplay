#!/usr/bin/env python3
from pathlib import Path
r=Path("aa-display/src/main")
def update(path,edits):
 f=r/path;s=f.read_text()
 for old,new,label in edits:
  n=s.count(old)
  if n!=1:raise AssertionError(f"{path}: {label}: {n}")
  s=s.replace(old,new,1)
 f.write_text(s)
C="java/io/github/nitsuya/aa/display/carplay/"
X="java/io/github/nitsuya/aa/display/xposed/"
update(X+"XposedInit.kt",[
 ('"com.netease.cloudmusic") -> arrayOf(LyricV53Hook)',
  '"com.netease.cloudmusic","com.luna.music.car") -> arrayOf(LyricV53Hook)',"car scope")])
update("res/values/arrays.xml",[
 ('        <item>com.luna.music</item>',
  '        <item>com.luna.music</item>\n        <item>com.luna.music.car</item>',"car array")])
update(C+"LyricV53Bridge.kt",[
 ('"com.tencent.qqmusiccar","com.tencent.qqmusicpad","com.netease.cloudmusic")',
  '"com.tencent.qqmusiccar","com.tencent.qqmusicpad","com.netease.cloudmusic",\n   "com.luna.music.car")',"car provider"),
 ('  data class Music(val song:String,val artist:String,val current:String,\n   val next:String,val playing:Boolean)',
  '  data class Music(val song:String,val artist:String,val current:String,\n   val next:String,val playing:Boolean,val artworkRevision:Long)',"art model"),
 ('    l?.first?:p.getString("line","").orEmpty(),l?.second.orEmpty(),playing)',
  '    l?.first?:p.getString("line","").orEmpty(),l?.second.orEmpty(),\n    playing,p.getLong("art_revision",0L))',"art read"),
 ('   "raw" -> {\n    val body=extras.getString("body").orEmpty()',
  '''   "art" -> {
    val jpg=extras.getByteArray("jpeg")
    if(jpg!=null && jpg.size in 256..160000) {
     runCatching {
      c.openFileOutput("v54_overlay_art.jpg",Context.MODE_PRIVATE).use { it.write(jpg) }
      e.putLong("art_revision",SystemClock.elapsedRealtime())
     }.onFailure { Log.w("AAD_V54Media","cover write failed",it) }
    }
   }
   "raw" -> {
    val body=extras.getString("body").orEmpty()''',"art write")
])
update(X+"hook/LyricV53Hook.kt",[
 ('import android.media.MediaMetadata',
  'import android.media.MediaMetadata\nimport android.graphics.Bitmap\nimport java.io.ByteArrayOutputStream',
  "art imports"),
 ('  var previousTitle="";var lastBody=0',
  '  var previousTitle="";var lastBody=0;var lastArtworkKey=""',
  "art cache"),
 ('      previousTitle=title\n      post("meta"){',
  '''      previousTitle=title
      val art=m.getBitmap(MediaMetadata.METADATA_KEY_ART)
       ?: m.getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART)
      val artworkKey=id+"|"+title+"|"+(art?.generationId ?: 0)
      if(artworkKey!=lastArtworkKey){
       lastArtworkKey=artworkKey
       if(art!=null)runCatching{
        val small=Bitmap.createScaledBitmap(art,192,192,true)
        val jpg=ByteArrayOutputStream().use { stream ->
         small.compress(Bitmap.CompressFormat.JPEG,78,stream)
         stream.toByteArray()
        }
        if(small!==art)small.recycle()
        post("art"){it.putByteArray("jpeg",jpg)}
       }.onFailure{Log.w(tagName,"art encode failed",it)}
      }
      post("meta"){''',
  "art sender"),
 ('if(pkg=="com.luna.music"){',
  'if(pkg=="com.luna.music" || pkg=="com.luna.music.car"){',
  "car internal lyric")
])
update(C+"CarPlayMediaOverlay.kt",[
 ('    private var cachedArt: Bitmap? = null',
  '''    private var cachedArt: Bitmap? = null
    private var observedArtRevision=0L
    private var observedArt:Bitmap?=null''',"art cache"),
 ('        cachedArt = null\n        lastArtRevision = Long.MIN_VALUE',
  '''        cachedArt = null
        observedArt=null
        observedArtRevision=0L
        lastArtRevision = Long.MIN_VALUE''',"art cleanup"),
 ('        val observed=LyricV53Bridge.read(c)\n        val fresh',
  '''        val observed=LyricV53Bridge.read(c)
        if(observed!=null && observed.artworkRevision!=observedArtRevision){
            observedArtRevision=observed.artworkRevision
            observedArt=runCatching {
                c.openFileInput("v54_overlay_art.jpg").use{BitmapFactory.decodeStream(it)}
            }.getOrNull()
        }
        val fresh''',"art worker"),
 ('                playing=observed.playing,art=cachedArt)',
  '                playing=observed.playing,art=observedArt ?: cachedArt)',"art display"),
 ('                        CarPlayWheelController.pressOverlayMediaKey(key)',
  '''                        // Do not use wheel's CoreApi+AudioManager dual-path here.
                        dispatchOverlayKey(ctx,if(key==KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE){
                            if(m.playing)KeyEvent.KEYCODE_MEDIA_PAUSE else KeyEvent.KEYCODE_MEDIA_PLAY
                        }else key)''',"single media key"),
 ('    /** Touch is consumed only for a pointer DOWN that starts inside the card. */',
  '''    private fun dispatchOverlayKey(ctx:Context,key:Int){
        runCatching{
            val audio=ctx.getSystemService(android.media.AudioManager::class.java)
                ?:return@runCatching
            val now=SystemClock.uptimeMillis()
            audio.dispatchMediaKeyEvent(KeyEvent(now,now,KeyEvent.ACTION_DOWN,key,0))
            audio.dispatchMediaKeyEvent(KeyEvent(now,now,KeyEvent.ACTION_UP,key,0))
            android.util.Log.i(CarPlayConsts.TAG,"v54 media dispatch key="+key)
        }.onFailure{android.util.Log.w(CarPlayConsts.TAG,"v54 media key error",it)}
    }

    /** Touch is consumed only for a pointer DOWN that starts inside the card. */''',
  "single media handler"),
 ('        val ch = (34f * scale + artH + lyricH + if (controls) 60f * scale else 13f * scale)',
  '        val ch = (35f * scale + artH + lyricH + if (controls) 60f * scale else 28f * scale)',"widget size"),
 ('        val center = g.x+g.w/2\n        var y = g.y + 18f*scale',
  '        val center = g.x+g.w/2\n        var y = g.y + (if(g.showControls)18f else 22f)*scale',
  "top padding"),
 ('            y += 98f*scale\n        }\n        glyph.textAlign',
  '''            y += 98f*scale
        }
        val bottom=if(g.showControls)g.controlY-19f*scale else g.y+g.h-13f*scale
        val textBlock=if(m.playing && m.current.isNotBlank() &&
            cfg.doubleLine && m.next.isNotBlank())53f*scale else 39f*scale
        y=(y+(bottom-y-textBlock)/2f).coerceAtLeast(y)
        glyph.textAlign''',
  "lyric vertical center"),
 ('        bg.color = Color.argb((cfg.transparency * 255 / 100).coerceIn(0,255),\n            Color.red(cfg.tint)/5 + 9, Color.green(cfg.tint)/5 + 13,\n            Color.blue(cfg.tint)/5 + 22)\n        canvas.drawRoundRect(g.x,g.y,g.x+g.w,g.y+g.h,corner,corner,bg)',
  '''        val opacity=(cfg.transparency*255/100).coerceIn(0,255)
        bg.color=Color.argb(opacity,
            (Color.red(cfg.tint)*0.32f+14).toInt().coerceIn(0,255),
            (Color.green(cfg.tint)*0.32f+17).toInt().coerceIn(0,255),
            (Color.blue(cfg.tint)*0.32f+25).toInt().coerceIn(0,255))
        canvas.drawRoundRect(g.x,g.y,g.x+g.w,g.y+g.h,corner,corner,bg)
        bg.shader=android.graphics.LinearGradient(g.x,g.y,g.x+g.w,g.y+g.h,
            intArrayOf(0x48ffffff,0x08ffffff,0x19000000),null,
            android.graphics.Shader.TileMode.CLAMP)
        canvas.drawRoundRect(g.x+1,g.y+1,g.x+g.w-1,g.y+g.h-1,corner,corner,bg)
        bg.shader=null''',
  "frosted appearance"),
 ('        line.color = Color.argb(95, Color.red(cfg.tint), Color.green(cfg.tint), Color.blue(cfg.tint))',
  '        line.color = Color.argb(180, Color.red(cfg.tint), Color.green(cfg.tint), Color.blue(cfg.tint))',
  "theme border"),
 ('        glyph.textAlign = Paint.Align.CENTER\n        glyph.color = Color.WHITE\n        glyph.typeface = Typeface.create("sans-serif-medium",Typeface.BOLD)',
  '        glyph.textAlign = Paint.Align.CENTER\n        glyph.color = cfg.lyricColor\n        glyph.typeface = Typeface.create("sans-serif-medium",Typeface.BOLD)',
  "lyric primary color"),
 ('                glyph.color = 0xffcbd3e1.toInt()',
  '                glyph.color = cfg.nextLyricColor',
  "lyric secondary color")
])
update(C+"CarPlayMediaOverlaySettings.kt",[
 ('        val tint: Int = Color.rgb(52, 112, 204),',
  '        val tint: Int = Color.rgb(52, 112, 204),\n        val lyricColor: Int = Color.WHITE,\n        val nextLyricColor: Int = 0xffcbd3e1.toInt(),',"color config"),
 ('            tint = s.getInt("tint", Color.rgb(52, 112, 204)),',
  '            tint = s.getInt("tint", Color.rgb(52, 112, 204)),\n            lyricColor=s.getInt("lyric_color",Color.WHITE),\n            nextLyricColor=s.getInt("next_color",0xffcbd3e1.toInt()),',
  "color read"),
 ('            .putInt("tint", cfg.tint)',
  '            .putInt("tint", cfg.tint)\n            .putInt("lyric_color",cfg.lyricColor)\n            .putInt("next_color",cfg.nextLyricColor)',
  "color store")
])
update(C+"CarPlayMediaSettingsUi.kt",[
 ('        panel.addView(sp)\n        panel.addView(TextView(activity).apply {',
  '''        panel.addView(sp)
        fun lyricColorPicker(title:String,initial:Int,apply:(Int)->Unit) {
            panel.addView(TextView(activity).apply{
                text=title;textSize=14f;setPadding(0,12,0,6)
            })
            val names=listOf("白色","淡蓝","青色","金黄","粉色","浅灰")
            val colors=listOf(Color.WHITE,0xff9ad9ff.toInt(),0xff8cf2d5.toInt(),
                0xffffdb76.toInt(),0xffffa4d2.toInt(),0xffcbd3e1.toInt())
            val selector=Spinner(activity)
            selector.adapter=ArrayAdapter(activity,android.R.layout.simple_spinner_dropdown_item,names)
            selector.setSelection(colors.indexOf(initial).coerceAtLeast(0))
            selector.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener {
                override fun onItemSelected(parent:android.widget.AdapterView<*>?,
                    view:View?,position:Int,id:Long){apply(colors[position])}
                override fun onNothingSelected(parent:android.widget.AdapterView<*>?) {}
            }
            panel.addView(selector)
        }
        lyricColorPicker("当前歌词颜色",cfg.lyricColor){save(cfg.copy(lyricColor=it))}
        lyricColorPicker("下一行歌词颜色",cfg.nextLyricColor){
            save(cfg.copy(nextLyricColor=it))
        }
        panel.addView(TextView(activity).apply {''',
  "color pickers")
])
g=Path("aa-display/build.gradle.kts");s=g.read_text()
assert "versionCode = 3153" in s and 'versionName = "0.3#17.8-v53"' in s
g.write_text(s.replace("versionCode = 3153","versionCode = 3154")
 .replace('versionName = "0.3#17.8-v53"','versionName = "0.3#17.8-v54"'))
print("v54 media-only patch applied")

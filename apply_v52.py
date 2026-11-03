#!/usr/bin/env python3
"""v52: floating car media overlay + phone connection-page settings.
No CarPlay protocol, RTSP, encoder, audio, reverse gate, or session ownership edits.
Apply strictly after v51.
"""
from pathlib import Path
R=Path("aa-display/src/main")
J=R/"java/io/github/nitsuya/aa/display"
def one(s,a,b,label):
    n=s.count(a)
    if n != 1:
        raise AssertionError(f"v52 {label}: {n} anchors")
    return s.replace(a,b,1)
def update(path,changes):
    p=R/path
    s=p.read_text(encoding="utf-8")
    for a,b,label in changes: s=one(s,a,b,label)
    p.write_text(s,encoding="utf-8")
def new(path,text):
    p=R/path
    if p.exists(): raise AssertionError("v52 already exists: "+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding="utf-8")

new("java/io/github/nitsuya/aa/display/carplay/CarPlayMediaOverlaySettings.kt",r'''package io.github.nitsuya.aa.display.carplay

import android.content.Context
import android.graphics.Color

/**
 * Ordinary application-process preferences; no system-server hooks, shell props,
 * permission grants, or new Surface/Display ownership.
 */
object CarPlayMediaOverlaySettings {
    private const val FILE = "carplay_media_overlay_v52"
    data class Config(
        val enabled: Boolean = false,
        val doubleLine: Boolean = true,
        val showCover: Boolean = true,
        val hideControlsPlaying: Boolean = true,
        val fontPx: Int = 27,
        val cornerPx: Int = 20,
        val transparency: Int = 66,
        val sizePct: Int = 100,
        val tint: Int = Color.rgb(52, 112, 204),
        val hideSeconds: Int = 6,
        val posX: Float = 0.73f,
        val posY: Float = 0.51f,
    )
    private fun p(c: Context) = c.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun read(context: Context): Config {
        val s = p(context)
        return Config(
            enabled = s.getBoolean("on", false),
            doubleLine = s.getBoolean("two", true),
            showCover = s.getBoolean("cover", true),
            hideControlsPlaying = s.getBoolean("hide", true),
            fontPx = s.getInt("font", 27).coerceIn(14, 54),
            cornerPx = s.getInt("corner", 20).coerceIn(0, 64),
            transparency = s.getInt("alpha", 66).coerceIn(10, 95),
            sizePct = s.getInt("size", 100).coerceIn(65, 155),
            tint = s.getInt("tint", Color.rgb(52, 112, 204)),
            hideSeconds = s.getInt("seconds", 6).coerceIn(2, 15),
            posX = s.getFloat("posx", 0.73f).coerceIn(0.02f, 0.98f),
            posY = s.getFloat("posy", 0.51f).coerceIn(0.02f, 0.98f),
        )
    }

    fun save(context: Context, cfg: Config) {
        p(context).edit()
            .putBoolean("on", cfg.enabled)
            .putBoolean("two", cfg.doubleLine)
            .putBoolean("cover", cfg.showCover)
            .putBoolean("hide", cfg.hideControlsPlaying)
            .putInt("font", cfg.fontPx)
            .putInt("corner", cfg.cornerPx)
            .putInt("alpha", cfg.transparency)
            .putInt("size", cfg.sizePct)
            .putInt("tint", cfg.tint)
            .putInt("seconds", cfg.hideSeconds)
            .putFloat("posx", cfg.posX)
            .putFloat("posy", cfg.posY)
            .apply()
        CarPlayMediaOverlay.refreshSettings()
    }
}
''')

new("java/io/github/nitsuya/aa/display/carplay/CarPlayMediaOverlay.kt",r'''package io.github.nitsuya.aa.display.carplay

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.media.session.PlaybackState
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.provider.Settings
import android.view.KeyEvent
import android.view.MotionEvent
import io.github.nitsuya.aa.display.CoreApi
import io.github.nitsuya.aa.display.xposed.cluster.ClusterArtStore
import io.github.nitsuya.aa.display.xposed.cluster.ClusterLyricStore
import kotlin.math.abs
import kotlin.math.hypot

/**
 * v52: a single Canvas painter composited into the already-existing CarPlay
 * chrome texture. There is no Android Window, new VirtualDisplay, MediaCodec,
 * TCP packet, MediaProjection or system_server overlay. Disabled by default.
 */
object CarPlayMediaOverlay {
    private data class Media(
        val title: String = "",
        val artist: String = "",
        val current: String = "",
        val next: String = "",
        val playing: Boolean = false,
        val art: Bitmap? = null,
    )
    @Volatile private var context: Context? = null
    @Volatile private var config = CarPlayMediaOverlaySettings.Config()
    @Volatile private var media = Media()
    @Volatile private var active = false
    @Volatile private var controlsUntil = 0L
    private var worker: HandlerThread? = null
    private var handler: Handler? = null
    private var lastArtRevision = Long.MIN_VALUE
    private var lastArtTrackId = ""
    private var cachedArt: Bitmap? = null

    @Volatile private var pointerCaptured = false
    private var downX = 0f
    private var downY = 0f
    private var dragged = false
    private var originX = 0f
    private var originY = 0f
    private var clickedControls = false

    private val bg = Paint(Paint.ANTI_ALIAS_FLAG)
    private val line = Paint(Paint.ANTI_ALIAS_FLAG)
    private val glyph = Paint(Paint.ANTI_ALIAS_FLAG)
    private val image = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val tmp = RectF()

    fun start(c: Context) {
        stop()
        context = c.applicationContext
        refreshSettings()
        active = true
        val t = HandlerThread("carplay-media-overlay-v52").also { it.start() }
        worker = t
        val h = Handler(t.looper)
        handler = h
        h.post(object : Runnable {
            override fun run() {
                if (!active) return
                runCatching { updateMedia() }
                    .onFailure { android.util.Log.w(CarPlayConsts.TAG, "v52 media read failed", it) }
                if (active) h.postDelayed(this, 650L)
            }
        })
    }

    fun stop() {
        active = false
        pointerCaptured = false
        handler?.removeCallbacksAndMessages(null)
        worker?.quitSafely()
        handler = null
        worker = null
        media = Media()
        cachedArt = null
        lastArtRevision = Long.MIN_VALUE
        lastArtTrackId = ""
        context = null
        controlsUntil = 0L
    }

    fun refreshSettings() {
        val ctx = context ?: return
        config = CarPlayMediaOverlaySettings.read(ctx)
    }

    private fun updateMedia() {
        val c = context ?: return
        val cfg = config
        if (!cfg.enabled) { media = Media(); return }
        val cr = c.contentResolver
        val fresh = ClusterLyricStore.readFresh(cr)
        // v52r1: paused player must retain art even when ticker expires at 15s.
        val rawTitle = fresh?.title ?: Settings.Global.getString(cr,
            ClusterLyricStore.SETTINGS_TITLE)?.trim().orEmpty()
        if (rawTitle.isBlank()) { media = Media(); return }
        val song = Settings.Global.getString(cr, ClusterLyricStore.SETTINGS_OVERLAY_SONG)?.trim().orEmpty()
        val artist = Settings.Global.getString(cr, ClusterLyricStore.SETTINGS_OVERLAY_ARTIST)?.trim().orEmpty()
        val next = Settings.Global.getString(cr, ClusterLyricStore.SETTINGS_OVERLAY_NEXT)?.trim().orEmpty()
        val trackId = Settings.Global.getString(cr, ClusterLyricStore.SETTINGS_TRACK_MEDIA_ID)?.trim().orEmpty()
        val state = ClusterLyricStore.readProgress(cr)?.playbackState
            ?: Settings.Global.getString(cr, ClusterLyricStore.SETTINGS_PLAYBACK_STATE)?.toIntOrNull()
        val playing = state == PlaybackState.STATE_PLAYING ||
            state == PlaybackState.STATE_BUFFERING
        val revision = ClusterArtStore.readRevision(cr)
        if (revision != lastArtRevision || trackId != lastArtTrackId) {
            lastArtRevision = revision
            lastArtTrackId = trackId
            val artMediaId = Settings.Global.getString(cr, ClusterArtStore.SETTINGS_ART_MEDIA_ID)?.trim().orEmpty()
            cachedArt = if (trackId.isNotEmpty() && trackId == artMediaId) {
                val bytes = runCatching { CoreApi.getClusterArtJpeg() }.getOrNull()
                if (bytes != null && bytes.isNotEmpty()) {
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                } else null
            } else null
        }
        media = Media(
            title = song.ifEmpty { rawTitle },
            artist = artist.ifEmpty { fresh?.subtitle ?: Settings.Global.getString(cr,
                ClusterLyricStore.SETTINGS_SUBTITLE).orEmpty() },
            current = rawTitle.takeIf { it != song && it.isNotBlank() }.orEmpty(),
            next = next,
            playing = playing,
            art = cachedArt,
        )
    }

    private data class Geometry(
        val x: Float, val y: Float, val w: Float, val h: Float,
        val controlY: Float, val showControls: Boolean,
    )
    private fun geometry(w: Int, h: Int, cfg: CarPlayMediaOverlaySettings.Config, m: Media): Geometry {
        val scale = cfg.sizePct / 100f
        val cw = (342f * scale).coerceAtMost(w * 0.75f)
        val artH = if (cfg.showCover) 102f * scale else 0f
        val now = SystemClock.uptimeMillis()
        val controls = !m.playing || !cfg.hideControlsPlaying || now < controlsUntil
        val lyricH = if (m.playing && m.current.isNotEmpty()) {
            (if (cfg.doubleLine && m.next.isNotBlank()) 74f else 47f) * scale
        } else 54f * scale
        val ch = (34f * scale + artH + lyricH + if (controls) 60f * scale else 13f * scale)
            .coerceAtMost(h * 0.86f)
        val x = (cfg.posX * w - cw / 2f).coerceIn(4f, (w - cw - 4f).coerceAtLeast(4f))
        val y = (cfg.posY * h - ch / 2f).coerceIn(4f, (h - ch - 4f).coerceAtLeast(4f))
        return Geometry(x,y,cw,ch,y+ch-32f*scale,controls)
    }

    fun draw(canvas: Canvas, w: Int, h: Int) {
        if (!active) return
        val cfg = config
        val m = media
        if (!cfg.enabled || m.title.isBlank() || w <= 0 || h <= 0) return
        val g = geometry(w,h,cfg,m)
        val scale = cfg.sizePct / 100f
        val corner = cfg.cornerPx * scale
        bg.color = Color.argb((cfg.transparency * 255 / 100).coerceIn(0,255),
            Color.red(cfg.tint)/5 + 9, Color.green(cfg.tint)/5 + 13,
            Color.blue(cfg.tint)/5 + 22)
        canvas.drawRoundRect(g.x,g.y,g.x+g.w,g.y+g.h,corner,corner,bg)
        line.color = Color.argb(95, Color.red(cfg.tint), Color.green(cfg.tint), Color.blue(cfg.tint))
        line.style = Paint.Style.STROKE
        line.strokeWidth = 1.5f * scale
        canvas.drawRoundRect(g.x,g.y,g.x+g.w,g.y+g.h,corner,corner,line)
        line.style = Paint.Style.FILL

        val center = g.x+g.w/2
        var y = g.y + 18f*scale
        val art = if (cfg.showCover) m.art else null
        if (cfg.showCover) {
            val side = 88f * scale
            if (art != null && !art.isRecycled) {
                val dest = RectF(center-side/2,y,center+side/2,y+side)
                canvas.drawBitmap(art,null,dest,image)
            } else {
                bg.color = Color.argb(170,42,53,81)
                canvas.drawRoundRect(center-side/2,y,center+side/2,y+side,12f*scale,12f*scale,bg)
                glyph.color = Color.WHITE
                glyph.typeface = Typeface.DEFAULT_BOLD
                glyph.textSize = 38f*scale
                glyph.textAlign = Paint.Align.CENTER
                canvas.drawText("♫",center,y+side*.65f,glyph)
            }
            y += 98f*scale
        }
        glyph.textAlign = Paint.Align.CENTER
        glyph.color = Color.WHITE
        glyph.typeface = Typeface.create("sans-serif-medium",Typeface.BOLD)
        glyph.textSize = (cfg.fontPx*scale).coerceAtLeast(12f)
        if (m.playing && m.current.isNotBlank()) {
            canvas.drawText(fit(m.current,g.w-22f*scale,glyph),center,y+20f*scale,glyph)
            if (cfg.doubleLine && m.next.isNotBlank()) {
                glyph.textSize = (cfg.fontPx*.77f*scale).coerceAtLeast(11f)
                glyph.typeface = Typeface.DEFAULT
                glyph.color = 0xffcbd3e1.toInt()
                canvas.drawText(fit(m.next,g.w-24f*scale,glyph),center,y+50f*scale,glyph)
            }
        } else {
            glyph.textSize = (cfg.fontPx*.85f*scale).coerceAtLeast(12f)
            canvas.drawText(fit(m.title,g.w-22f*scale,glyph),center,y+16f*scale,glyph)
            glyph.textSize = (cfg.fontPx*.60f*scale).coerceAtLeast(11f)
            glyph.typeface = Typeface.DEFAULT
            glyph.color = 0xffcbd3e1.toInt()
            canvas.drawText(fit(m.artist,g.w-22f*scale,glyph),center,y+39f*scale,glyph)
        }
        if (g.showControls) {
            glyph.color = Color.WHITE
            glyph.typeface = Typeface.DEFAULT_BOLD
            glyph.textSize = 27f*scale
            canvas.drawText("◀❘",center-g.w*.28f,g.controlY+11f*scale,glyph)
            canvas.drawText(if (m.playing) "Ⅱ" else "▶",
                center,g.controlY+11f*scale,glyph)
            canvas.drawText("❘▶",center+g.w*.28f,g.controlY+11f*scale,glyph)
        }
    }

    private fun fit(text:String,maxWidth:Float,p:Paint):String {
        if (p.measureText(text)<=maxWidth) return text
        var s=text
        while(s.length>1 && p.measureText(s+"…")>maxWidth) s=s.dropLast(1)
        return s+"…"
    }

    /** Touch is consumed only for a pointer DOWN that starts inside the card. */
    fun onTouch(xNorm:Float,yNorm:Float,action:Int):Boolean {
        val ctx=context ?: return false
        val cfg=config; val m=media
        if (!active || !cfg.enabled || m.title.isBlank()) return false
        val w=CarPlayInputBridge.shellWidthPx.coerceAtLeast(1)
        val h=CarPlayInputBridge.shellHeightPx.coerceAtLeast(1)
        val px=xNorm*w; val py=yNorm*h
        val g=geometry(w,h,cfg,m)
        when(action) {
            MotionEvent.ACTION_DOWN -> {
                if (px < g.x || px > g.x+g.w || py < g.y || py > g.y+g.h) return false
                pointerCaptured=true
                downX=px; downY=py
                originX=cfg.posX; originY=cfg.posY
                dragged=false
                clickedControls=g.showControls
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                if (!pointerCaptured) return false
                if (hypot(px-downX,py-downY)>15f) dragged=true
                if (dragged) {
                    config=config.copy(
                        posX=(originX+(px-downX)/w).coerceIn(0.02f,0.98f),
                        posY=(originY+(py-downY)/h).coerceIn(0.02f,0.98f))
                }
                return true
            }
            MotionEvent.ACTION_UP -> {
                if (!pointerCaptured) return false
                pointerCaptured=false
                if (dragged) {
                    CarPlayMediaOverlaySettings.save(ctx,config)
                } else {
                    val now=SystemClock.uptimeMillis()
                    controlsUntil=now+cfg.hideSeconds*1000L
                    if (clickedControls && py>=g.controlY-24f*cfg.sizePct/100f &&
                        py<=g.y+g.h && px>=g.x && px<=g.x+g.w) {
                        val key=when {
                            px<g.x+g.w*.37f -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
                            px>g.x+g.w*.63f -> KeyEvent.KEYCODE_MEDIA_NEXT
                            else -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
                        }
                        CarPlayWheelController.pressOverlayMediaKey(key)
                    }
                }
                return true
            }
            MotionEvent.ACTION_CANCEL -> {pointerCaptured=false; return true}
        }
        return pointerCaptured
    }
}
''')

new("java/io/github/nitsuya/aa/display/carplay/CarPlayMediaSettingsUi.kt",r'''package io.github.nitsuya.aa.display.carplay

import android.app.Activity
import android.app.AlertDialog
import android.graphics.Color
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.Spinner
import android.widget.ArrayAdapter
import android.widget.Switch
import android.widget.TextView

/** Settings live in the phone's AADisplay CarPlay connection page, not the HU widget. */
object CarPlayMediaSettingsUi {
    fun show(activity: Activity) {
        var cfg = CarPlayMediaOverlaySettings.read(activity)
        val root = ScrollView(activity)
        val panel = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            val d=(activity.resources.displayMetrics.density*18).toInt()
            setPadding(d,d,d,d)
        }
        root.addView(panel)
        fun save(c:CarPlayMediaOverlaySettings.Config) {
            cfg=c
            CarPlayMediaOverlaySettings.save(activity,c)
        }
        fun toggle(title:String, on:Boolean, cb:(Boolean)->Unit) {
            val switch=Switch(activity).apply {
                text=title
                isChecked=on
                setPadding(0,8,0,8)
                setOnCheckedChangeListener { _,checked->cb(checked) }
            }
            panel.addView(switch)
        }
        fun slider(title:String, value:Int, low:Int, high:Int, units:String, cb:(Int)->Unit) {
            val label=TextView(activity).apply {
                text=title+"："+value+units
                textSize=14f
                setPadding(0,14,0,0)
            }
            panel.addView(label)
            val bar=SeekBar(activity).apply {
                max=high-low
                progress=(value-low).coerceIn(0,max)
                setOnSeekBarChangeListener(object:SeekBar.OnSeekBarChangeListener {
                    override fun onProgressChanged(seek:SeekBar?,progress:Int,fromUser:Boolean) {
                        if (!fromUser) return
                        val v=(low+progress).coerceIn(low,high)
                        label.text=title+"："+v+units
                        cb(v)
                    }
                    override fun onStartTrackingTouch(seek:SeekBar?) {}
                    override fun onStopTrackingTouch(seek:SeekBar?) {}
                })
            }
            panel.addView(bar)
        }
        toggle("启用车机悬浮媒体",cfg.enabled) { save(cfg.copy(enabled=it)) }
        toggle("双行歌词（关闭为单行）",cfg.doubleLine) { save(cfg.copy(doubleLine=it)) }
        toggle("显示专辑封面",cfg.showCover) { save(cfg.copy(showCover=it)) }
        toggle("播放时隐藏控制按钮",cfg.hideControlsPlaying) {
            save(cfg.copy(hideControlsPlaying=it))
        }
        slider("歌词字体大小",cfg.fontPx,14,54," px") { save(cfg.copy(fontPx=it)) }
        slider("圆角大小",cfg.cornerPx,0,64," px") { save(cfg.copy(cornerPx=it)) }
        slider("背景透明度",cfg.transparency,10,95,"%") {
            save(cfg.copy(transparency=it))
        }
        slider("组件大小",cfg.sizePct,65,155,"%") { save(cfg.copy(sizePct=it)) }
        slider("点击后控制显示时长",cfg.hideSeconds,2,15," 秒") {
            save(cfg.copy(hideSeconds=it))
        }
        panel.addView(TextView(activity).apply {
            text="主题颜色"
            textSize=14f
            setPadding(0,12,0,6)
        })
        val choices=listOf("蓝色","紫色","玫红","绿色","橙色","灰色")
        val tints=listOf(Color.rgb(52,112,204),Color.rgb(112,73,196),
            Color.rgb(205,66,119),Color.rgb(39,145,106),
            Color.rgb(210,124,41),Color.rgb(98,107,125))
        val sp=Spinner(activity)
        sp.adapter=ArrayAdapter(activity,android.R.layout.simple_spinner_dropdown_item,choices)
        sp.setSelection(tints.indexOf(cfg.tint).coerceAtLeast(0))
        sp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent:android.widget.AdapterView<*>?,
                view:View?,position:Int,id:Long) {
                save(cfg.copy(tint=tints[position]))
            }
            override fun onNothingSelected(parent:android.widget.AdapterView<*>?) {}
        }
        panel.addView(sp)
        panel.addView(TextView(activity).apply {
            text="方向盘按键：保持原有上一曲／暂停／下一曲及长按手势，不改变映射"
            textSize=12f
            setPadding(0,16,0,0)
        })
        AlertDialog.Builder(activity)
            .setTitle("悬浮媒体设置")
            .setView(root)
            .setPositiveButton("完成",null)
            .setNeutralButton("恢复默认") { _,_->
                save(CarPlayMediaOverlaySettings.Config())
            }
            .show()
    }
}
''')

update("java/io/github/nitsuya/aa/display/carplay/CarPlayGlCompositor.kt",[
('''        if (showRecents) {
            CarPlayRecentsOverlay.draw(canvas, encodeWidth, encodeHeight)
        }
        if (showPicker) {
            CarPlayAppPickerOverlay.draw(canvas, encodeWidth, encodeHeight)
        }
        GLES20.glBindTexture''',
'''        // Paint behind modal picker/recents; they retain first touch priority.
        CarPlayMediaOverlay.draw(canvas, encodeWidth, encodeHeight)
        if (showRecents) {
            CarPlayRecentsOverlay.draw(canvas, encodeWidth, encodeHeight)
        }
        if (showPicker) {
            CarPlayAppPickerOverlay.draw(canvas, encodeWidth, encodeHeight)
        }
        GLES20.glBindTexture''',"GL composite")
])
update("java/io/github/nitsuya/aa/display/carplay/FrameEgressTee.kt",[
('''        canvas.drawText(
            "mode=test-pattern",
            width / 20f,
            height / 2f + paint.textSize * 1.6f,
            paint,
        )
    }''',
'''        canvas.drawText(
            "mode=test-pattern",
            width / 20f,
            height / 2f + paint.textSize * 1.6f,
            paint,
        )
        // CarPlay fallback still exposes the same media control and lyrics.
        CarPlayMediaOverlay.draw(canvas,width,height)
    }''',"canvas fallback")
])
update("java/io/github/nitsuya/aa/display/carplay/CarPlayInputBridge.kt",[
('''        if (CarPlayRecentsOverlay.isVisible()) {
            CarPlayRecentsOverlay.onTouch(x, y, action)
            return
        }

        // CarPlay exclusive''',
'''        if (CarPlayRecentsOverlay.isVisible()) {
            CarPlayRecentsOverlay.onTouch(x, y, action)
            return
        }
        // v52: consume only touches that begin inside the floating media card.
        // Preserve all existing divider, pane, gesture and keyboard routing.
        if (ProjectionSessionGate.shouldUseCarPlayHost() &&
            CarPlayMediaOverlay.onTouch(x,y,action)) return

        // CarPlay exclusive''',"overlay hit test")
])
update("java/io/github/nitsuya/aa/display/carplay/CarPlayWheelController.kt",[
('''    /** VD inject + active media-session dispatch (map-focused pane otherwise eats keys). */
    private fun pressMediaKey(keyCode: Int) {''',
'''    /** Overlay buttons use the exact same media command path as the wheel. */
    fun pressOverlayMediaKey(keyCode: Int) {
        if (keyCode != KeyEvent.KEYCODE_MEDIA_PREVIOUS &&
            keyCode != KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE &&
            keyCode != KeyEvent.KEYCODE_MEDIA_NEXT) return
        pressMediaKey(keyCode)
    }

    /** VD inject + active media-session dispatch (map-focused pane otherwise eats keys). */
    private fun pressMediaKey(keyCode: Int) {''',"wheel shared dispatch")
])
update("java/io/github/nitsuya/aa/display/carplay/CarPlayHostRuntime.kt",[
('''            val paneW = (w / 2).coerceAtLeast(16)
            val gl = CarPlayGlCompositor()''',
'''            val paneW = (w / 2).coerceAtLeast(16)
            // v52 only reads media; starting it never affects receiver handshakes.
            CarPlayMediaOverlay.start(app)
            val gl = CarPlayGlCompositor()''',"overlay start"),
('''            CarPlayAppPickerOverlay.unbind()
            CarPlayProjectionService.attachGlCompositor(null)''',
'''            CarPlayAppPickerOverlay.unbind()
            CarPlayMediaOverlay.stop()
            CarPlayProjectionService.attachGlCompositor(null)''',"overlay stop")
])
update("java/io/github/nitsuya/aa/display/carplay/CarPlayStatusUi.kt",[
('''        binding.btnBtDiscoverable.setOnClickListener {
            CarPlayProjectionService.requestDiscoverable(activity)
            toast(activity, "请允许蓝牙可被发现（300 秒）")
        }
        refresh''',
'''        binding.btnBtDiscoverable.setOnClickListener {
            CarPlayProjectionService.requestDiscoverable(activity)
            toast(activity, "请允许蓝牙可被发现（300 秒）")
        }
        binding.btnCarplayMediaSettings.setOnClickListener {
            CarPlayMediaSettingsUi.show(activity)
        }
        refresh''',"settings button")
])
update("res/layout/activity_main.xml",[
('''                <TextView
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="16dp"
                    android:text="使用提示"''',
'''                <Button
                    android:id="@+id/btn_carplay_media_settings"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="10dp"
                    android:minHeight="48dp"
                    android:text="悬浮媒体设置（歌词／封面／样式／拖动）" />

                <TextView
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="16dp"
                    android:text="使用提示"''',"main carplay settings entry")
])
# Extend the existing extractor without changing current-title decisions used by CarPlay NowPlaying.
update("java/io/github/nitsuya/aa/display/xposed/cluster/LyricLineExtractor.kt",[
('''        val needsPositionTick: Boolean,
    )''',
'''        val needsPositionTick: Boolean,
        val nextLyric: String,
    )''',"extract result next"),
('''            needsPositionTick = timedEntries != null,
        )''',
'''            needsPositionTick = timedEntries != null,
            nextLyric = timedEntries?.let { nextLineAtPosition(it,positionMs) }.orEmpty(),
        )''',"extract next"),
('''    private fun lineAtPosition(entries: List<LrcEntry>, positionMs: Long): String? {''',
'''    /** Returns a strictly later non-credit line, never invents a lyric. */
    private fun nextLineAtPosition(entries:List<LrcEntry>, positionMs:Long):String? {
        for (e in entries) {
            if (e.timeMs > positionMs && !isCreditOrProductionLine(e.text))
                return e.text.trim()
        }
        return null
    }

    private fun lineAtPosition(entries: List<LrcEntry>, positionMs: Long): String? {''',"next line resolver")
])
update("java/io/github/nitsuya/aa/display/xposed/cluster/ClusterLyricStore.kt",[
('''    const val SETTINGS_SOURCE_PKG = "aadisplay_cluster_np_source_pkg"''',
'''    const val SETTINGS_SOURCE_PKG = "aadisplay_cluster_np_source_pkg"
    // v52 additional snapshot fields; existing cluster/iAP keys unchanged.
    const val SETTINGS_OVERLAY_SONG = "aadisplay_overlay_song_v52"
    const val SETTINGS_OVERLAY_ARTIST = "aadisplay_overlay_artist_v52"
    const val SETTINGS_OVERLAY_NEXT = "aadisplay_overlay_next_v52"
    private var lastOverlay = Triple("","","")

    fun publishOverlay(cr:ContentResolver,song:String,artist:String,next:String) {
        val snap=Triple(song,artist,next)
        if (snap == lastOverlay) return
        lastOverlay=snap
        runCatching {
            Settings.Global.putString(cr,SETTINGS_OVERLAY_SONG,song)
            Settings.Global.putString(cr,SETTINGS_OVERLAY_ARTIST,artist)
            Settings.Global.putString(cr,SETTINGS_OVERLAY_NEXT,next)
        }.onFailure { log(TAG,"v52 overlay metadata write failed",it) }
    }''',"metadata additional fields"),
('''    fun clear(cr: ContentResolver) {''',
'''    fun clear(cr: ContentResolver) {
        publishOverlay(cr,"","","")''',"overlay clear")
])
update("java/io/github/nitsuya/aa/display/xposed/cluster/ClusterLyricMirror.kt",[
('''        publishProgress(controller, state, playbackState)

        if (extracted.mediaId''',
'''        publishProgress(controller, state, playbackState)
        // Optional independent fields for v52. Never change existing iAP title.
        appContext?.let { ctx ->
            ClusterLyricStore.publishOverlay(ctx.contentResolver,
                extracted.songTitle,extracted.artist,extracted.nextLyric)
        }

        if (extracted.mediaId''',"source overlay metadata")
])
p=Path("aa-display/build.gradle.kts")
v=p.read_text(encoding="utf-8")
v=one(v,"versionCode = 3151","versionCode = 3152","versionCode")
v=one(v,'versionName = "0.3#17.8-v51"','versionName = "0.3#17.8-v52"',"version name")
p.write_text(v,encoding="utf-8")
print("v52 applied: optional in-video overlay, persisted phone UI, LRC next, wheel reuse")

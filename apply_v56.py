#!/usr/bin/env python3
"""v56 independent floating-media width and height + lightweight rolling double lyric.

Apply after v55. No touch to CarPlay event, RTSP, iAP2, camera resource
ownership, audio routing, MediaCodec, MediaProjection or GL encoder binding.
"""
from pathlib import Path

R=Path("aa-display/src/main")
C="java/io/github/nitsuya/aa/display/carplay/"
def edit(path,changes):
    p=R/path
    s=p.read_text(encoding="utf-8")
    for old,new,label in changes:
        n=s.count(old)
        if n!=1:raise AssertionError("v56 "+str(path)+" "+label+" anchor="+str(n))
        s=s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")

edit(C+"CarPlayMediaOverlaySettings.kt",[
    ("        val sizePct: Int = 100,\n        val tint: Int = ",
     "        val sizePct: Int = 100,\n        val widthPct: Int = 100,\n        val heightPct: Int = 100,\n        val tint: Int = ",
     "config fields"),
    ('            sizePct = s.getInt("size", 100).coerceIn(65, 155),',
     '''            sizePct = s.getInt("size", 100).coerceIn(65, 155),
            widthPct = s.getInt("width_pct", 100).coerceIn(70, 180),
            heightPct = s.getInt("height_pct", 100).coerceIn(90, 180),''',
     "settings read"),
    ('            .putInt("size", cfg.sizePct)',
     '''            .putInt("size", cfg.sizePct)
            .putInt("width_pct", cfg.widthPct)
            .putInt("height_pct", cfg.heightPct)''',
     "settings persist"),
])

edit(C+"CarPlayMediaSettingsUi.kt",[
    ('        slider("组件大小",cfg.sizePct,65,155,"%") { save(cfg.copy(sizePct=it)) }',
     '''        slider("组件大小（整体缩放）",cfg.sizePct,65,155,"%") {
            save(cfg.copy(sizePct=it))
        }
        slider("悬浮媒体宽度",cfg.widthPct,70,180,"%") {
            save(cfg.copy(widthPct=it))
        }
        slider("悬浮媒体高度",cfg.heightPct,90,180,"%") {
            save(cfg.copy(heightPct=it))
        }''',
     "independent sliders"),
])

edit(C+"CarPlayMediaOverlay.kt",[
    ('    private var cachedArt: Bitmap? = null',
     '''    private var cachedArt: Bitmap? = null

    // v56: animation state owned by the existing canvas render path.
    // No new thread, ticker, decoder or Surface is created.
    private const val V56_LYRIC_SCROLL_MS = 430L
    private var v56Song = ""
    private var v56Current = ""
    private var v56Next = ""
    private var v56OldCurrent = ""
    private var v56OldNext = ""
    private var v56SlideAt = 0L
    private var v56IsSequential = false''',
     "animation state"),
    ('        media = Media()\n        cachedArt = null',
     '''        media = Media()
        v56Song = ""
        v56Current = ""
        v56Next = ""
        v56OldCurrent = ""
        v56OldNext = ""
        v56SlideAt = 0L
        cachedArt = null''',
     "reset animation lifecycle"),
    ('        val cw = (342f * scale).coerceAtMost(w * 0.75f)',
     '''        val cw = (342f * scale * cfg.widthPct / 100f).coerceAtMost(w * 0.88f)''',
     "card width"),
    ('        val ch = (35f * scale + artH + lyricH + if (controls) 60f * scale else 28f * scale)\n            .coerceAtMost(h * 0.86f)',
     '''        val baseH = 35f * scale + artH + lyricH +
            if (controls) 60f * scale else 28f * scale
        val ch = (baseH * cfg.heightPct / 100f).coerceAtMost(h * 0.90f)''',
     "card height"),
    ('''        if (m.playing && m.current.isNotBlank()) {
            canvas.drawText(fit(m.current,g.w-22f*scale,glyph),center,y+20f*scale,glyph)
            if (cfg.doubleLine && m.next.isNotBlank()) {
                glyph.textSize = (cfg.fontPx*.77f*scale).coerceAtLeast(11f)
                glyph.typeface = Typeface.DEFAULT
                glyph.color = cfg.nextLyricColor
                canvas.drawText(fit(m.next,g.w-24f*scale,glyph),center,y+50f*scale,glyph)
            }
        } else {''',
     '''        if (m.playing && m.current.isNotBlank()) {
            drawV56Lyrics(canvas, g, cfg, m, center, y, bottom, scale)
        } else {
            // Paused/metadata card does not animate lyrics.
            v56SlideAt = 0L
            v56Song = ""
            v56Current = ""
            v56Next = ""''',
     "lyric painter replacement"),
    ('    private fun fit(text:String,maxWidth:Float,p:Paint):String {',
     r'''    private fun v56DrawLine(
        canvas: Canvas, text: String, x: Float, baseline: Float,
        available: Float, font: Float, color: Int, opacity: Float, isCurrent: Boolean,
    ) {
        if (text.isBlank() || opacity <= 0f) return
        glyph.textAlign = Paint.Align.CENTER
        glyph.color = color
        glyph.alpha = (Color.alpha(color) * opacity.coerceIn(0f, 1f)).toInt()
            .coerceIn(0, 255)
        glyph.textSize = font
        glyph.typeface = if (isCurrent) {
            Typeface.create("sans-serif-medium", Typeface.BOLD)
        } else Typeface.DEFAULT
        canvas.drawText(fit(text, available, glyph), x, baseline, glyph)
        glyph.alpha = 255
    }

    private fun v56BlendColor(from: Int, to: Int, fraction: Float): Int {
        val t = fraction.coerceIn(0f, 1f)
        fun mix(a: Int, b: Int) = (a + (b - a) * t).toInt().coerceIn(0, 255)
        return Color.argb(mix(Color.alpha(from), Color.alpha(to)),
            mix(Color.red(from), Color.red(to)),
            mix(Color.green(from), Color.green(to)),
            mix(Color.blue(from), Color.blue(to)))
    }

    private fun drawV56Lyrics(
        canvas: Canvas, g: Geometry, cfg: CarPlayMediaOverlaySettings.Config,
        m: Media, x: Float, y: Float, bottom: Float, scale: Float,
    ) {
        val now = SystemClock.uptimeMillis()
        val hasTwoLines = cfg.doubleLine && m.next.isNotBlank()
        if (m.title != v56Song || !hasTwoLines) {
            v56SlideAt = 0L
        } else if (m.current != v56Current && v56Current.isNotBlank()) {
            v56OldCurrent = v56Current
            v56OldNext = v56Next
            v56IsSequential = v56OldNext.isNotBlank() && v56OldNext == m.current
            v56SlideAt = now
        }
        v56Song = m.title
        v56Current = m.current
        v56Next = m.next

        val firstY = y + 20f * scale
        val secondY = y + 50f * scale
        val gap = secondY - firstY
        val primarySize = (cfg.fontPx * scale).coerceAtLeast(12f)
        val secondarySize = (cfg.fontPx * .77f * scale).coerceAtLeast(11f)
        val textW = (g.w - 24f * scale).coerceAtLeast(1f)

        // Drawing is clipped to the lyric band: never cover album art or buttons.
        val clipTop = (y - 11f * scale).coerceAtLeast(g.y + 5f * scale)
        val clipBottom = (bottom + 3f * scale).coerceAtMost(g.y + g.h - 5f * scale)
        val saveCount = canvas.save()
        if (clipBottom > clipTop) {
            canvas.clipRect(g.x + 5f * scale, clipTop,
                g.x + g.w - 5f * scale, clipBottom)
        }

        val elapsed = now - v56SlideAt
        val rolling = hasTwoLines && v56SlideAt > 0L &&
            elapsed in 0 until V56_LYRIC_SCROLL_MS
        if (rolling) {
            val t = (elapsed.toFloat() / V56_LYRIC_SCROLL_MS).coerceIn(0f, 1f)
            val eased = t * t * (3f - 2f * t)
            // The previous current lyric exits above, fading out.
            v56DrawLine(canvas, v56OldCurrent, x, firstY - gap * eased,
                textW, primarySize, cfg.lyricColor, 1f - eased, true)
            if (v56IsSequential) {
                // The previous next line slides into the highlighted current position.
                val movingColor = v56BlendColor(
                    cfg.nextLyricColor, cfg.lyricColor, eased)
                val movingSize = secondarySize +
                    (primarySize - secondarySize) * eased
                v56DrawLine(canvas, m.current, x, secondY - gap * eased,
                    textW, movingSize, movingColor, 1f, eased >= .5f)
            } else {
                // Seek/skip: use an entry scroll without pretending lines matched.
                v56DrawLine(canvas, m.current, x, firstY + gap * (1f - eased),
                    textW, primarySize, cfg.lyricColor, eased, true)
            }
            // The upcoming lyric moves upward from below instead of hard cutting.
            v56DrawLine(canvas, m.next, x, secondY + gap * (1f - eased),
                textW, secondarySize, cfg.nextLyricColor, eased, false)
        } else {
            if (v56SlideAt != 0L) v56SlideAt = 0L
            v56DrawLine(canvas, m.current, x, firstY, textW,
                primarySize, cfg.lyricColor, 1f, true)
            if (hasTwoLines) {
                v56DrawLine(canvas, m.next, x, secondY, textW,
                    secondarySize, cfg.nextLyricColor, 1f, false)
            }
        }
        canvas.restoreToCount(saveCount)
        glyph.alpha = 255
    }

    private fun fit(text:String,maxWidth:Float,p:Paint):String {''',
     "new lightweight lyric roller"),
])

g=Path("aa-display/build.gradle.kts")
s=g.read_text(encoding="utf-8")
if s.count("versionCode = 3155")!=1 or s.count('versionName = "0.3#17.8-v55"')!=1:
    raise AssertionError("v55 build baseline missing")
g.write_text(s.replace("versionCode = 3155","versionCode = 3156")
    .replace('versionName = "0.3#17.8-v55"','versionName = "0.3#17.8-v56"'))
print("v56 independent width/height and 430ms dual-line scroll applied")

#!/usr/bin/env python3
"""v26: one-shot raw OES and pre-encoder framebuffer PNG capture.
Preserves v23 networking and v25 diagnostics.
"""
from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlayGlCompositor.kt")
s=p.read_text()
def replace(a,b):
    global s
    assert s.count(a)==1,(a,s.count(a))
    s=s.replace(a,b,1)
replace('import android.graphics.Bitmap','import android.graphics.Bitmap\nimport android.app.Application\nimport java.io.File')
replace('    private var v25LastReportMs = 0L','''    private var v25LastReportMs = 0L
    private var v26CaptureAtMs = 0L
    private var v26Captured = false''')
replace('                windowStart = SystemClock.uptimeMillis()\n                handler.removeCallbacks(renderTick)','''                windowStart = SystemClock.uptimeMillis()
                v26CaptureAtMs = windowStart + 15000L
                v26Captured = false
                handler.removeCallbacks(renderTick)''')
replace('        val fs = CarPlayInputBridge.fullscreenPane','''        // v26: sample the actual OES textures on the encoder EGL surface, once.
        // Restore the framebuffer before normal video composition.
        val v26Capture = !v26Captured && SystemClock.uptimeMillis() >= v26CaptureAtMs
        if (v26Capture) {
            v26Captured = true
            for (pane in 0..1) {
                GLES20.glViewport(0, 0, encodeWidth, encodeHeight)
                GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT)
                drawPane(pane, 0, 0, encodeWidth, encodeHeight)
                v26SaveFrame("raw_pane_${pane}", encodeWidth, encodeHeight)
            }
            GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT)
        }

        val fs = CarPlayInputBridge.fullscreenPane''')
replace('        drawChromeLayer(seamX, chromeFullscreen)\n        // v25:','''        drawChromeLayer(seamX, chromeFullscreen)
        if (v26Capture) v26SaveFrame("encoder_before_swap", encodeWidth, encodeHeight)
        // v25:''')
replace('    /**\n     * Fullscreen peel drag preview:', '''    /** Read pixels only once per encoder attachment, then flip GL bottom-up rows.
     * Saved in private app storage, retrievable using root via /data/user/0/PACKAGE/files.
     */
    private fun v26SaveFrame(label: String, width: Int, height: Int) {
        try {
            val size = width.toLong() * height.toLong() * 4L
            if (size <= 0L || size > 48L * 1024L * 1024L) return
            val pixels = ByteBuffer.allocateDirect(size.toInt()).order(ByteOrder.nativeOrder())
            GLES20.glFinish()
            GLES20.glReadPixels(0, 0, width, height,
                GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, pixels)
            val error = GLES20.glGetError()
            if (error != GLES20.GL_NO_ERROR) {
                Log.e(CarPlayConsts.TAG, "v26 capture $label glError=$error")
                return
            }
            val ints = IntArray(width * height)
            for (y in 0 until height) {
                for (x in 0 until width) {
                    val i = (y * width + x) * 4
                    val r = pixels.get(i).toInt() and 255
                    val g = pixels.get(i + 1).toInt() and 255
                    val b = pixels.get(i + 2).toInt() and 255
                    val a = pixels.get(i + 3).toInt() and 255
                    ints[(height - 1 - y) * width + x] =
                        (a shl 24) or (r shl 16) or (g shl 8) or b
                }
            }
            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
            bitmap.setPixels(ints, 0, width, 0, 0, width, height)
            val packageName = Application.getProcessName().substringBefore(':')
            val directory = File("/data/user/0/$packageName/files/CarPlayV26")
            if (!directory.exists()) directory.mkdirs()
            val output = File(directory, "$label.png")
            output.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
            bitmap.recycle()
            Log.i(CarPlayConsts.TAG,
                "v26 PNG $label saved=${output.absolutePath} bytes=${output.length()} " +
                "dimensions=${width}x$height")
        } catch (e: Throwable) {
            Log.e(CarPlayConsts.TAG, "v26 PNG $label failed", e)
        }
    }

    /**
     * Fullscreen peel drag preview:''')
p.write_text(s)
g=Path("aa-display/build.gradle.kts")
v=g.read_text()
assert 'versionCode = 3125' in v and 'versionName = "0.3#17.8-v25"' in v
g.write_text(v.replace('versionCode = 3125','versionCode = 3126',1).replace('versionName = "0.3#17.8-v25"','versionName = "0.3#17.8-v26"',1))
print("v26 GPU screenshots enabled")

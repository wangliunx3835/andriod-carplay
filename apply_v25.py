#!/usr/bin/env python3
"""v25: CarPlay GL virtual-display IME capture verification and frame-latch recovery.
Preserves v23 connection and all IME policy hooks.
"""
from pathlib import Path
root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p=root/"carplay/CarPlayGlCompositor.kt"
s=p.read_text()
old='''    private val frameAvailable = booleanArrayOf(false, false)
    private val texMatrix = FloatArray(16)'''
new='''    private val frameAvailable = booleanArrayOf(false, false)
    // v25: distinguish a VD buffer arriving from a compositor/encoder presentation.
    private val v25Received = longArrayOf(0L, 0L)
    private val v25Consumed = longArrayOf(0L, 0L)
    private var v25LastReportMs = 0L
    private val texMatrix = FloatArray(16)'''
assert s.count(old)==1
s=s.replace(old,new,1)
old='''                synchronized(frameAvailable) { frameAvailable[i] = true }'''
new='''                synchronized(frameAvailable) {
                    frameAvailable[i] = true
                    v25Received[i]++
                }'''
assert s.count(old)==1
s=s.replace(old,new,1)
old='''                    surfaceTextures[i]?.updateTexImage()
                } catch (e: Throwable) {'''
new='''                    surfaceTextures[i]?.updateTexImage()
                    v25Consumed[i]++
                } catch (e: Throwable) {'''
assert s.count(old)==1
s=s.replace(old,new,1)
old='''        drawChromeLayer(seamX, chromeFullscreen)

        // Shared media clock'''
new='''        drawChromeLayer(seamX, chromeFullscreen)
        // v25: small GL readback from the exact encoder framebuffer, once every 5s.
        // A non-black pixel sample below the IME boundary helps distinguish
        // SurfaceFlinger screenshot success from missing OES/compositor pixels.
        val v25Now = SystemClock.uptimeMillis()
        if (v25Now - v25LastReportMs >= 5000L) {
            v25LastReportMs = v25Now
            val probe = ByteBuffer.allocateDirect(4 * 4).order(ByteOrder.nativeOrder())
            val x = (encodeWidth / 2).coerceAtLeast(0)
            val y = (encodeHeight / 4).coerceAtLeast(0)
            GLES20.glReadPixels(x, y, 2, 2, GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, probe)
            val err = GLES20.glGetError()
            val pixels = (0 until 16).joinToString("") {
                "%02x".format(probe.get(it).toInt() and 255)
            }
            val recv: LongArray
            synchronized(frameAvailable) { recv = v25Received.clone() }
            Log.i(CarPlayConsts.TAG,
                "v25 GL-IME-probe recv=${recv.contentToString()} " +
                "consumed=${v25Consumed.contentToString()} attached=${encoderAttached.get()} " +
                "sampleXY=$x,$y rgba=$pixels glError=$err")
        }

        // Shared media clock'''
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)
g=Path("aa-display/build.gradle.kts")
v=g.read_text()
assert 'versionCode = 3124' in v and 'versionName = "0.3#17.8-v24"' in v
g.write_text(v.replace('versionCode = 3124','versionCode = 3125',1).replace('versionName = "0.3#17.8-v24"','versionName = "0.3#17.8-v25"',1))
print("v25 GL capture instrumentation applied")

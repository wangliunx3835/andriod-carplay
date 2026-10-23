from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlaySourceSession.kt")
s=p.read_text()
a='''        val (encW, encH) = if (
            width > 0 && height > 0 &&
            (width != CarPlayConsts.DEFAULT_VIDEO_WIDTH || height != CarPlayConsts.DEFAULT_VIDEO_HEIGHT)
        ) {
            width.coerceAtLeast(16) to height.coerceAtLeast(16)
        } else {
            CarPlayConsts.ENCODE_WIDTH to CarPlayConsts.ENCODE_HEIGHT
        }'''
b='''        // v13: Every receiver's negotiated size is authoritative, including
        // 1280x720 and ultrawide panels. No fixed-resolution fallback for a
        // valid SETUP size: it caused 16:9 frames to be stretched to 8:3.
        val (encW, encH) = if (width > 0 && height > 0) {
            width.coerceAtLeast(16) to height.coerceAtLeast(16)
        } else {
            CarPlayConsts.ENCODE_WIDTH to CarPlayConsts.ENCODE_HEIGHT
        }
        Log.i(CarPlayConsts.TAG,
            "v13 resolution negotiated=${width}x${height} encoder=${encW}x${encH} " +
            "ratio=${if (encH > 0) encW.toFloat() / encH else 0f}")'''
assert s.count(a)==1,s.count(a)
s=s.replace(a,b,1)
a='''        if (rtsp?.isStreaming() == true) {
            if (forceSurfaceRefresh'''
b='''        if (rtsp?.isStreaming() == true) {
            Log.i(CarPlayConsts.TAG,
                "v13 streaming lifecycle: keep codec, requested=${width}x${height} " +
                "encoder=${encW}x${encH} interactive=" +
                "${appContext.getSystemService(android.os.PowerManager::class.java)?.isInteractive} " +
                "accessoryNetwork=${CarPlayAccessoryNet.get()}")
            if (forceSurfaceRefresh'''
assert s.count(a)==1,s=s.replace(a,b,1) if False else None
s=s.replace(a,b,1)
p.write_text(s)
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlayWifiHandoff.kt")
s=p.read_text()
a='''                    Log.w(CarPlayConsts.TAG, "WiFi handoff lost ssid=$ssid — schedule rejoin")'''
b='''                    Log.w(CarPlayConsts.TAG,
                        "v13 WiFi onLost ssid=$ssid network=$network " +
                        "current=$current interactive=" +
                        "${appContext.getSystemService(android.os.PowerManager::class.java)?.isInteractive} " +
                        "— schedule rejoin")'''
# avoid touching WifiHandoff until appContext availability is verified
p=Path("aa-display/build.gradle.kts")
s=p.read_text()
assert 'versionCode = 3112' in s and 'versionName = "0.3#17.8-v12"' in s
p.write_text(s.replace('versionCode = 3112','versionCode = 3113',1).replace('versionName = "0.3#17.8-v12"','versionName = "0.3#17.8-v13"',1))
print("v13 dynamic resolution and lifecycle diagnostics applied")

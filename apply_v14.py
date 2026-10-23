from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlaySourceSession.kt")
s=p.read_text()
a='''            onHuMediaEnded = { reason -> schedulePhoneAudioRelease(reason) },'''
b='''            onHuMediaEnded = { reason ->
                schedulePhoneAudioRelease(reason)
                if (!usbMode.get() && running.get()) {
                    airplayDialed.set(false)
                    mainHandler.removeCallbacks(v14Recovery)
                    mainHandler.postDelayed(v14Recovery, 2_500L)
                    Log.w(CarPlayConsts.TAG, "v14 RTSP ended; recovery scheduled")
                }
            },'''
assert s.count(a)==1
s=s.replace(a,b,1)
a='''    private fun cancelPhoneAudioRelease() {
        mainHandler.removeCallbacks(releasePhoneAudio)
    }'''
b='''    private val v14Recovery = Runnable {
        if (running.get() && !usbMode.get() &&
            rtsp?.isStreaming() != true &&
            CarPlayAccessoryNet.hasNetwork()) {
            Log.i(CarPlayConsts.TAG, "v14 recovery fallback dial")
            dialAirPlayFallback("v14-rtsp-recovery")
        }
    }

    private fun cancelPhoneAudioRelease() {
        mainHandler.removeCallbacks(v14Recovery)
        mainHandler.removeCallbacks(releasePhoneAudio)
    }'''
assert s.count(a)==1
s=s.replace(a,b,1)
p.write_text(s)
p=Path("aa-display/build.gradle.kts")
s=p.read_text()
assert 'versionCode = 3113' in s and 'versionName = "0.3#17.8-v13"' in s
p.write_text(s.replace('versionCode = 3113','versionCode = 3114',1).replace('versionName = "0.3#17.8-v13"','versionName = "0.3#17.8-v14"',1))
print("v14 applied")

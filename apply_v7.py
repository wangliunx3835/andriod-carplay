from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlaySourceSession.kt")
s=p.read_text()
a='''                rtsp?.releaseMediaStreams("iap-rfcomm-closed")
                CarPlayNowPlaying.stop()
                dialGeneration.incrementAndGet()
                airplayDialed.set(false)'''
b='''                // v7: RFCOMM is not the video transport. Keep an already
                // streaming AirPlay session alive across brief screen lock/unlock.
                // Control-pump death still releases media via CarPlayRtspSession.
                if (rtsp?.isStreaming() == true) {
                    Log.w(CarPlayConsts.TAG,
                        "v7 RFCOMM closed while RTSP streaming: preserve media; " +
                            "wifiNet=${CarPlayAccessoryNet.get()}")
                    return@disconnect
                }
                Log.i(CarPlayConsts.TAG, "v7 RFCOMM closed without active RTSP: release media")
                rtsp?.releaseMediaStreams("iap-rfcomm-closed")
                CarPlayNowPlaying.stop()
                dialGeneration.incrementAndGet()
                airplayDialed.set(false)'''
assert s.count(a)==1,s.count(a)
s=s.replace(a,b,1)
p.write_text(s)
p=Path("aa-display/build.gradle.kts");s=p.read_text()
assert 'versionCode = 3106' in s and 'versionName = "0.3#17.8-v6"' in s
p.write_text(s.replace('versionCode = 3106','versionCode = 3107').replace('versionName = "0.3#17.8-v6"','versionName = "0.3#17.8-v7"'))
print("v7 applied")

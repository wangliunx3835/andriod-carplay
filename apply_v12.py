from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlayRtspSession.kt")
s=p.read_text()
a='''        if (mib3) {
            Log.i(CarPlayConsts.TAG, "v11 screen SETUP 200; awaiting control SYN before video TCP")
            awaitWifiSyn(4_000L)
            Log.i(CarPlayConsts.TAG, "v11 control SYN wait finished; video TCP target=$peerHost:$dataPort")
        }'''
b='''        if (mib3) {
            // v12: v11 logs show a 4-second SYN wait followed by TCP failure
            // and Wi-Fi NetworkAgent loss. Do not delay the receiver's
            // advertised video socket while waiting for an optional SYN.
            Log.i(CarPlayConsts.TAG,
                "v12 SETUP 200; dial video immediately target=$peerHost:$dataPort " +
                "accessoryNetwork=${CarPlayAccessoryNet.get()}")
        }'''
assert s.count(a)==1
s=s.replace(a,b,1)
p.write_text(s)
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/protocol/ScreenStreamEgress.kt")
s=p.read_text()
a='''                socket.connect(InetSocketAddress(host, dataPort), 10_000)'''
b='''                // v12: fail fast rather than holding an abandoned Wi-Fi AP
                // socket for ten seconds and causing rapid session churn.
                Log.i(CarPlayConsts.TAG,
                    "v12 video TCP dial network=${io.github.nitsuya.aa.display.carplay.CarPlayAccessoryNet.get()} " +
                    "target=$host:$dataPort")
                socket.connect(InetSocketAddress(host, dataPort), 3_000)'''
assert s.count(a)==1
s=s.replace(a,b,1)
p.write_text(s)
p=Path("aa-display/build.gradle.kts")
s=p.read_text()
assert 'versionCode = 3111' in s and 'versionName = "0.3#17.8-v11"' in s
p.write_text(s.replace('versionCode = 3111','versionCode = 3112',1).replace('versionName = "0.3#17.8-v11"','versionName = "0.3#17.8-v12"',1))
print("v12 patch applied")

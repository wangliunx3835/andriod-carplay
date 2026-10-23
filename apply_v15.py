from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlaySourceSession.kt")
s=p.read_text()
anchor="    private val mainHandler = Handler(Looper.getMainLooper())"
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'''
    // v15: keep CPU and the accessory Wi-Fi radio active while wireless
    // CarPlay is in use; this does not turn the display on.
    private val v15WifiManager = appContext.applicationContext.getSystemService(
        android.content.Context.WIFI_SERVICE
    ) as android.net.wifi.WifiManager
    private val v15PowerManager = appContext.applicationContext.getSystemService(
        android.content.Context.POWER_SERVICE
    ) as android.os.PowerManager
    private val v15WifiLock = v15WifiManager.createWifiLock(
        android.net.wifi.WifiManager.WIFI_MODE_FULL_HIGH_PERF, "AADisplay:CarPlay"
    ).apply { setReferenceCounted(false) }
    private val v15CpuLock = v15PowerManager.newWakeLock(
        android.os.PowerManager.PARTIAL_WAKE_LOCK, "AADisplay:CarPlay"
    ).apply { setReferenceCounted(false) }
    private fun v15AcquireLocks() {
        if (usbMode.get()) return
        try {
            if (!v15WifiLock.isHeld) v15WifiLock.acquire()
            if (!v15CpuLock.isHeld) v15CpuLock.acquire()
            Log.i(CarPlayConsts.TAG, "v15 wireless locks held wifi=\\$"+"{v15WifiLock.isHeld} cpu=\\$"+"{v15CpuLock.isHeld}")
        } catch (e: Throwable) {
            Log.e(CarPlayConsts.TAG, "v15 wireless locks acquire failed", e)
        }
    }
    private fun v15ReleaseLocks() {
        try { if (v15WifiLock.isHeld) v15WifiLock.release() } catch (_: Throwable) {}
        try { if (v15CpuLock.isHeld) v15CpuLock.release() } catch (_: Throwable) {}
    }
'''.replace('\\$','$'),1)
anchor="        usbMode.set(wired)"
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'''
        v15AcquireLocks()''',1)
anchor="        cancelPhoneAudioRelease()\n        val (sent, bytes) = rtsp?.rtpStats()"
assert s.count(anchor)==1
s=s.replace(anchor,"        cancelPhoneAudioRelease()\n        v15ReleaseLocks()\n        val (sent, bytes) = rtsp?.rtpStats()",1)
# Prevent stale v14 fallback from racing with a new explicit StartSession.
anchor="    private fun dialCarPlayControl(start: Iap2Csm.CarPlayStart) {"
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'''
        mainHandler.removeCallbacks(v14Recovery)
        Log.i(CarPlayConsts.TAG, "v15 StartSession primary dial; cancelled fallback")
''',1)
# v14 fallback must never compete with iAP2 StartSession.
anchor='''            CarPlayAccessoryNet.hasNetwork()) {
            Log.i(CarPlayConsts.TAG, "v14 recovery fallback dial")'''
assert s.count(anchor)==1
s=s.replace(anchor,'''            CarPlayAccessoryNet.hasNetwork() &&
            iap2?.hasSeenStartSession() != true) {
            Log.i(CarPlayConsts.TAG, "v15 recovery fallback (no StartSession)")''',1)
p.write_text(s)
p=Path("aa-display/src/main/AndroidManifest.xml")
s=p.read_text()
if 'android.permission.WAKE_LOCK' not in s:
    s=s.replace('<manifest xmlns:android=', '<manifest xmlns:android=',1)
    i=s.index('    <uses-permission ')
    s=s[:i]+'    <uses-permission android:name="android.permission.WAKE_LOCK" />\n'+s[i:]
p.write_text(s)
p=Path("aa-display/build.gradle.kts")
s=p.read_text()
assert 'versionCode = 3114' in s and 'versionName = "0.3#17.8-v14"' in s
p.write_text(s.replace('versionCode = 3114','versionCode = 3115',1).replace('versionName = "0.3#17.8-v14"','versionName = "0.3#17.8-v15"',1))
print("v15 lock and reconnect arbitration applied")

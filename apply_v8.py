from pathlib import Path
root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p=root/"carplay/CarPlaySourceSession.kt"
s=p.read_text()
def rep(a,b):
 global s
 assert s.count(a)==1,(a[:70],s.count(a))
 s=s.replace(a,b,1)
rep('''    private val running = AtomicBoolean(false)''','''    private val running = AtomicBoolean(false)
    // v8: Keep the CPU and accessory Wi-Fi radio active while wireless CarPlay
    // owns the link. Acquire only after accessory Wi-Fi bind, never at idle arm.
    private var v8CpuLock: android.os.PowerManager.WakeLock? = null
    private var v8WifiLock: android.net.wifi.WifiManager.WifiLock? = null
    private fun v8AcquireRadioLocks() {
        if (!running.get() || usbMode.get()) return
        try {
            if (v8CpuLock?.isHeld != true) {
                val pm = appContext.getSystemService(android.os.PowerManager::class.java)
                v8CpuLock = pm.newWakeLock(
                    android.os.PowerManager.PARTIAL_WAKE_LOCK,
                    "AADisplay:CarPlayWireless"
                ).also { it.setReferenceCounted(false); it.acquire() }
            }
            if (v8WifiLock?.isHeld != true) {
                val wm = appContext.applicationContext.getSystemService(
                    android.content.Context.WIFI_SERVICE
                ) as android.net.wifi.WifiManager
                v8WifiLock = wm.createWifiLock(
                    android.net.wifi.WifiManager.WIFI_MODE_FULL_HIGH_PERF,
                    "AADisplay:CarPlayWireless"
                ).also { it.setReferenceCounted(false); it.acquire() }
            }
            Log.i(CarPlayConsts.TAG, "v8 radio locks acquired cpu=${v8CpuLock?.isHeld} wifi=${v8WifiLock?.isHeld}")
        } catch (e: Throwable) {
            Log.e(CarPlayConsts.TAG, "v8 radio locks acquire failed", e)
        }
    }
    private fun v8ReleaseRadioLocks() {
        try { if (v8WifiLock?.isHeld == true) v8WifiLock?.release() }
        catch (e: Throwable) { Log.w(CarPlayConsts.TAG, "v8 wifi lock release failed", e) }
        try { if (v8CpuLock?.isHeld == true) v8CpuLock?.release() }
        catch (e: Throwable) { Log.w(CarPlayConsts.TAG, "v8 cpu lock release failed", e) }
        v8WifiLock = null
        v8CpuLock = null
        Log.i(CarPlayConsts.TAG, "v8 radio locks released")
    }''')
rep('''    private fun onAccessoryWifiBound(staMac: String?) {
        val bj = bonjour ?: return''','''    private fun onAccessoryWifiBound(staMac: String?) {
        v8AcquireRadioLocks()
        val bj = bonjour ?: return''')
rep('''        if (!running.compareAndSet(true, false)) return
        cancelPhoneAudioRelease()''','''        if (!running.compareAndSet(true, false)) return
        v8ReleaseRadioLocks()
        cancelPhoneAudioRelease()''')
p.write_text(s)
p=Path("aa-display/src/main/AndroidManifest.xml");s=p.read_text()
assert '<uses-permission android:name="android.permission.INTERNET" />' in s
s=s.replace('<uses-permission android:name="android.permission.INTERNET" />',
'''<uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />''',1)
p.write_text(s)
p=Path("aa-display/build.gradle.kts");s=p.read_text()
assert 'versionCode = 3107' in s and 'versionName = "0.3#17.8-v7"' in s
p.write_text(s.replace('versionCode = 3107','versionCode = 3108').replace('versionName = "0.3#17.8-v7"','versionName = "0.3#17.8-v8"'))
print("v8 applied")

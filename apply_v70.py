from pathlib import Path
R=Path('aa-display/src/main/java/io/github/nitsuya/aa/display')
def edit(path,old,new):
 p=R/path;s=p.read_text();assert s.count(old)==1,(path,s.count(old));p.write_text(s.replace(old,new,1))
for name,dest in [('v70_smartbox_audio.kt','carplay/SmartBoxV70Audio.kt'),('v70_system_audio.kt','xposed/carplay/SmartBoxV70SystemAudio.kt')]:
 (R/dest).write_text(Path('../tools/'+name).read_text())
edit('carplay/CarPlaySourceSession.kt','    private val running = AtomicBoolean(false)','    private val running = AtomicBoolean(false)\n    private val v70Audio = SmartBoxV70Audio(appContext)\n    @Volatile private var v70Box = false')
edit('carplay/CarPlaySourceSession.kt','    private fun startWirelessTransport(rtspSession: CarPlayRtspSession) {','''    private fun startWirelessTransport(rtspSession: CarPlayRtspSession) {
        rtspSession.smartBoxPeer = { v70Box }
        rtspSession.smartBoxAudioBypass = { v70Box && v70Audio.enabled() }''')
edit('carplay/CarPlaySourceSession.kt','            onPeer = { name, address -> iap2?.notePeer(name, address) },','''            onPeer = { name, address ->
                v70Box = SmartBoxV69DialPolicy.matches(name)
                if (v70Box) v70Audio.notePeer(name, address) else v70Audio.stop()
                iap2?.notePeer(name, address)
            },''')
edit('carplay/CarPlaySourceSession.kt','    fun stop() {\n        if (!running.compareAndSet(true, false)) return','''    fun stop() {
        if (!running.compareAndSet(true, false)) return
        v70Audio.stop()
        v70Box = false''')
edit('carplay/CarPlayMediaSettingsUi.kt','        root.addView(panel)','        root.addView(panel)\n        SmartBoxV70Audio.addSettings(activity, panel)')
edit('carplay/CarPlayRtspSession.kt','    fun isStreaming(): Boolean = streaming.get()','''    var smartBoxPeer: () -> Boolean = { false }
    var smartBoxAudioBypass: () -> Boolean = { false }
    fun isStreaming(): Boolean = streaming.get()''')
# Existing event iAP2 engine is retained; no new type-130 negotiation.
edit('carplay/CarPlayRtspSession.kt','            Log.i(CarPlayConsts.TAG, "RECORD ok")','''            Log.i(CarPlayConsts.TAG, "RECORD ok")
            if (smartBoxPeer() && !phoneMac.isNullOrBlank()) {
                val body = BinaryPlist.encode(mapOf("type" to "disableBluetooth",
                    "params" to mapOf("deviceID" to phoneMac)))
                val response = exchangeEncrypted(RtspMessage("POST /command RTSP/1.0",
                    headers(mapOf("Content-Type" to "application/x-apple-binary-plist",
                        "Content-Length" to body.size.toString())), body))
                Log.i(CarPlayConsts.TAG, "v70 SmartBox handoff response=${response?.firstLine}")
            }''')
a='        // Audio: Audi MIB3 needs type-102 AAC-LC (CSM path). DiPlay keeps type-100 PCM.'
edit('carplay/CarPlayRtspSession.kt',a,'''        if (smartBoxAudioBypass()) {
            Log.i(CarPlayConsts.TAG, "v70 SmartBox sound uses selected car A2DP; skip AirPlay audio")
        } else {
'''+a)
edit('carplay/CarPlayRtspSession.kt','        CarPlayV33Diag.stage("audio-setup-finished")','        }\n        CarPlayV33Diag.stage("audio-setup-finished")')
edit('xposed/carplay/CarPlayAudioCapture.kt','    fun setEnabled(enabled: Boolean) {','''    fun setEnabled(requested: Boolean) {
        val enabled = requested && !SmartBoxV70SystemAudio.bypass()''')
edit('xposed/carplay/CarPlayAudioCapture.kt','            desired.set(enabled)','            desired.set(requested)')
edit('xposed/carplay/CarPlayAudioCapture.kt','    private fun enableLocked() {','    private fun enableLocked() {\n        if (SmartBoxV70SystemAudio.bypass()) return')
method='''    override fun smartBoxAudioRoute(box: String, target: String, connect: Boolean): Boolean {
        val identity = android.os.Binder.clearCallingIdentity()
        return try {
            io.github.nitsuya.aa.display.xposed.carplay.SmartBoxV70SystemAudio.route(
                systemContext, box, target, connect)
        } finally { android.os.Binder.restoreCallingIdentity(identity) }
    }

'''
edit('xposed/CoreManagerService.kt','    override fun isCarPlaySessionLive(): Boolean = carPlaySessionLive',method+'    override fun isCarPlaySessionLive(): Boolean = carPlaySessionLive')
edit('xposed/CoreManager.kt','    override fun setCarPlayAudioEgressEnabled(enabled: Boolean) {','''    override fun smartBoxAudioRoute(box: String, target: String, connect: Boolean): Boolean =
        runCatching { getService()?.smartBoxAudioRoute(box, target, connect) == true }
            .getOrDefault(false)

    override fun setCarPlayAudioEgressEnabled(enabled: Boolean) {''')
p=Path('aa-display/src/main/aidl/io/github/nitsuya/aa/display/xposed/ICoreManager.aidl');s=p.read_text();i=s.rfind('}');p.write_text(s[:i]+'''    // Appended: selected SmartBox audio capability; existing ordinals unchanged.
    boolean smartBoxAudioRoute(String box, String target, boolean connect);
'''+s[i:])
p=Path('aa-display/build.gradle.kts');s=p.read_text();assert 'versionCode = 3169' in s;p.write_text(s.replace('versionCode = 3169','versionCode = 3170').replace('0.3#17.8-v69','0.3#17.8-v70'))
print('v70 SmartBox-only dual Bluetooth audio and handoff applied')

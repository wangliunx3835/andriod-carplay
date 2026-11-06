from pathlib import Path
R=Path('aa-display/src/main/java/io/github/nitsuya/aa/display/carplay')
def edit(f,a,b):
 p=R/f;s=p.read_text();assert s.count(a)==1,(f,s.count(a));p.write_text(s.replace(a,b,1))
(R/'CarPlayV68ScreenState.kt').write_text(Path('../tools/v68_screen_state.kt').read_text())
t=Path('aa-display/src/test/java/io/github/nitsuya/aa/display/carplay/CarPlayV68ScreenStateTest.kt');t.parent.mkdir(parents=True,exist_ok=True);t.write_text(Path('../tools/v68_screen_state_test.kt').read_text())
f='protocol/CarPlayEventChannel.kt'
edit(f,'    private val onPhoneScreenRequested: () -> Unit,','    private val onPhoneScreenRequested: () -> Unit,\n    private val onMainScreenChanged: () -> Unit,')
edit(f,'            onPhoneScreenRequested: () -> Unit = {},','            onPhoneScreenRequested: () -> Unit = {},\n            onMainScreenChanged: () -> Unit = {},')
edit(f,'                    onPhoneScreenRequested = onPhoneScreenRequested,','                    onPhoneScreenRequested = onPhoneScreenRequested,\n                    onMainScreenChanged = onMainScreenChanged,')
edit(f,'        var replyBody = ByteArray(0)','        val screenWasPhone = isPhoneOwningMainScreen()\n        var replyBody = ByteArray(0)')
edit(f,'        reply200(msg, replyBody)','''        reply200(msg, replyBody)
        if (screenWasPhone != isPhoneOwningMainScreen()) {
            runCatching { onMainScreenChanged() }
                .onFailure { Log.w(CarPlayConsts.TAG,"v68 ownership callback failed",it) }
        }''')
edit(f,'    private fun currentModesParams(): Map<String, Any?>','    fun currentModesParams(): Map<String, Any?>')
f='CarPlayRtspSession.kt'
edit(f,'    private val v58ReopenScreen = AtomicReference<(() -> Boolean)?>(null)','''    private val v58ReopenScreen = AtomicReference<(() -> Boolean)?>(null)
    private val v68Epoch = AtomicLong(0L)
    private val v68Action = AtomicReference<((Boolean) -> Unit)?>(null)
    private val v68Enabled = AtomicBoolean(false)
    private val v68Executor = java.util.concurrent.Executors.newSingleThreadExecutor { task ->
        Thread(task,"carplay-v68-screen").apply { isDaemon = true }
    }''')
edit(f,'    private fun v59ArmReturnProbe(reason: String) {','''    private fun v59ArmReturnProbe(reason: String) {
        if (v68Enabled.get()) { v68Action.get()?.invoke(false); return }''')
edit(f,'    private fun v58TryRecovery(reason: String, forceVideo: Boolean = false) {','''    private fun v58TryRecovery(reason: String, forceVideo: Boolean = false) {
        if (v68Enabled.get()) { v68Action.get()?.invoke(true); return }''')
edit(f,'    fun releaseMediaStreams(reason: String) {','''    fun releaseMediaStreams(reason: String) {
        v68Epoch.incrementAndGet()
        v68Action.set(null)
        v68Enabled.set(false)''')
edit(f,'        val mib3 = huProfile.usesMib3WirelessPath\n        val v34Enabled','''        val mib3 = huProfile.usesMib3WirelessPath
        // Only the observed CarLetter receiver opts into the new lifecycle.
        val v68Session = huProfile.id == "carletter"
        val sessionEpoch = v68Epoch.get()
        v68Enabled.set(v68Session)
        fun v68Live() = v68Epoch.get() == sessionEpoch && running.get() &&
            streaming.get() && controlPumpLive.get()
        val v34Enabled''')
edit(f,'        var cseq = cseqStart','        val cseq = AtomicInteger(cseqStart)')
p=R/f;s=p.read_text();a=s.index('        val cseq = AtomicInteger(cseqStart)');s=s[:a]+s[a:].replace('(cseq++).toString()','cseq.getAndIncrement().toString()').replace('val seq = cseq++','val seq = cseq.getAndIncrement()');p.write_text(s)
edit(f,'                onPhoneScreenRequested = {\n                    v58TryRecovery("requestUI")','''                onMainScreenChanged = { if (v68Session) v68Action.get()?.invoke(false) },
                onPhoneScreenRequested = {
                    if (v68Session) v68Action.get()?.invoke(false)
                    else v58TryRecovery("requestUI")''')
edit(f,'                        v58TryRecovery("MainScreen restored")','''                        if (v68Session) v68Action.get()?.invoke(false)
                        else v58TryRecovery("MainScreen restored")''')
edit(f,'                if (reply?.firstLine?.contains("200") != true || port == null || port<=0) {','''                if (v68Session && !v68Live()) {
                    false
                } else if (reply?.firstLine?.contains("200") != true || port == null || port<=0) {''')
edit(f,'                    if (fresh == null) false\n                    else {','''                    if (fresh == null) false
                    else if (v68Session && !v68Live()) { fresh.close(); false }
                    else {''')
edit(f,'        // Audio: Audi MIB3 needs type-102 AAC-LC',Path('../tools/v68_integration.kt').read_text()+'        // Audio: Audi MIB3 needs type-102 AAC-LC')
edit(f,'                controlPumpLive.set(true)\n                pumpEncryptedControl','''                controlPumpLive.set(true)
                if (v68Enabled.get() && eventChannel.get()?.isPhoneOwningMainScreen() == false)
                    v68Action.get()?.invoke(false)
                pumpEncryptedControl''')
edit(f,'        v57VideoQueue.close()','        v57VideoQueue.close()\n        v68Executor.shutdownNow()')
p=Path('aa-display/build.gradle.kts');s=p.read_text();assert 'versionCode = 3167' in s
p.write_text(s.replace('versionCode = 3167','versionCode = 3168').replace('0.3#17.8-v67','0.3#17.8-v68').replace('dependencies {','dependencies {\n    testImplementation("junit:junit:4.13.2")',1))
print('v68 CarLetter screen lifecycle patch applied')

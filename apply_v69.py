from pathlib import Path
R=Path('aa-display/src/main/java/io/github/nitsuya/aa/display/carplay')
def edit(f,a,b):
 p=R/f;s=p.read_text();assert s.count(a)==1,(f,s.count(a));p.write_text(s.replace(a,b,1))
(R/'SmartBoxV69DialPolicy.kt').write_text(Path('../tools/v69_smartbox_policy.kt').read_text())
t=Path('aa-display/src/test/java/io/github/nitsuya/aa/display/carplay/SmartBoxV69DialPolicyTest.kt');t.parent.mkdir(parents=True,exist_ok=True);t.write_text(Path('../tools/v69_smartbox_policy_test.kt').read_text())
f='CarPlayBluetoothLink.kt'
edit(f,'    private val sessionLive: () -> Boolean = { false },','    private val sessionLive: () -> Boolean = { false },\n    private val mediaActive: () -> Boolean = { false },')
edit(f,'    private val accessoryUuid: UUID = UUID.fromString(CarPlayConsts.IAP2_ACCESSORY_RFCOMM_UUID)',Path('../tools/v69_bt_integration.kt').read_text())
edit(f,'                    when (action) {','''                    when (action) {
                        BluetoothDevice.ACTION_UUID -> {
                            if (!SmartBoxV69DialPolicy.matches(device.name)) return
                            @Suppress("DEPRECATION")
                            val values = intent.getParcelableArrayExtra(BluetoothDevice.EXTRA_UUID)
                            if (values != null) {
                                val services = values.mapNotNull { (it as? android.os.ParcelUuid)?.uuid }.toSet()
                                v69Services[device.address] = services
                                Log.i(CarPlayConsts.TAG,"v69 SmartBox SDP name="+device.name+
                                    " UUIDs="+services+" caff="+services.contains(accessoryUuid)+
                                    " cafe="+services.contains(phoneUuid))
                            } else Log.w(CarPlayConsts.TAG,"v69 SmartBox SDP missing; no guessed channel")
                            return
                        }''')
edit(f,'                    addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED)','                    addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED)\n                    addAction(BluetoothDevice.ACTION_UUID)')
edit(f,'        val profile = CarPlayProfileResolver.matchName(device.name)\n        if (profile?.dialPolicy','''        if (SmartBoxV69DialPolicy.matches(device.name)) return v69CanDial(device)
        val profile = CarPlayProfileResolver.matchName(device.name)
        if (profile?.dialPolicy''')
edit(f,'        val current = clientSocket\n        if (current?.isConnected','''        if (SmartBoxV69DialPolicy.matches(device.name)) {
            if (!v69CanDial(device) ||
                !v69Policy.reserve(device.address,SystemClock.elapsedRealtime())) return null
        }
        val current = clientSocket
        if (current?.isConnected''')
edit(f,'                if (clientSocket?.isConnected == true && sessionLive()) {','''                if (SmartBoxV69DialPolicy.matches(socket.remoteDevice?.name) &&
                    (mediaActive() || (clientSocket?.isConnected == true &&
                        clientSocket?.remoteDevice?.address != socket.remoteDevice?.address))) {
                    Log.i(CarPlayConsts.TAG,"v69 SmartBox inbound deferred: existing connection protected")
                    socket.closeQuietly()
                    continue
                }
                if (clientSocket?.isConnected == true && sessionLive()) {''')
edit(f,'        rfcommArmed.set(false)\n        discoverableRequested.set(false)','        rfcommArmed.set(false)\n        v69Policy.clear()\n        v69Services.clear()\n        discoverableRequested.set(false)')
edit('CarPlaySourceSession.kt','            sessionLive = { iap2?.isNegotiatingOrLive() == true },','''            sessionLive = { iap2?.isNegotiatingOrLive() == true },
            mediaActive = { rtsp?.isStreaming() == true || rtsp?.isAirPlaySourceActive() == true },''')
p=Path('aa-display/build.gradle.kts');s=p.read_text();assert 'versionCode = 3168' in s
p.write_text(s.replace('versionCode = 3168','versionCode = 3169').replace('0.3#17.8-v68','0.3#17.8-v69'))
print('v69 SmartBox-only transport adaptation applied')

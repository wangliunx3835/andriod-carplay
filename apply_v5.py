from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlaySourceSession.kt")
s=p.read_text()
def change(a,b):
 global s
 assert s.count(a)==1,(a[:70],s.count(a))
 s=s.replace(a,b,1)
change('''        val host = CarPlayUsbHandoff.pickDialHost(start.ipAddresses)
            ?: if (!wired) wifiHandoff?.accessoryIpv4Hint(start.ssid) else null
            ?: start.ipAddresses.firstOrNull()''','''        val advertised = CarPlayUsbHandoff.pickDialHost(start.ipAddresses)
            ?: start.ipAddresses.firstOrNull()
        val gateway = if (!wired) wifiHandoff?.accessoryIpv4Hint(start.ssid) else null
        val host = advertised ?: gateway''')
change('''            val addr = try {
                InetAddress.getByName(host)
            } catch (e: Throwable) {
                Log.e(CarPlayConsts.TAG, "StartSession resolve failed $host", e)
                return@Thread
            }
            // HU-stub / lab loopback: plain sockets, no accessory Network bind.
            val loopback = addr.isLoopbackAddress''','''            fun scopedAddress(candidate: String): InetAddress {
                val raw = InetAddress.getByName(candidate)
                if (raw is java.net.Inet6Address && raw.isLinkLocalAddress && raw.scopeId == 0) {
                    val net = CarPlayAccessoryNet.get()
                        ?: throw IllegalStateException("accessory Network absent for IPv6 scope")
                    val cm = appContext.getSystemService(android.net.ConnectivityManager::class.java)
                    val ifaceName = cm.getLinkProperties(net)?.interfaceName
                        ?: throw IllegalStateException("accessory interface unknown for IPv6 scope")
                    val iface = java.net.NetworkInterface.getByName(ifaceName)
                        ?: throw IllegalStateException("interface $ifaceName not found")
                    return java.net.Inet6Address.getByAddress(null, raw.address, iface)
                }
                return raw
            }
            Log.i(CarPlayConsts.TAG, "v5 AirPlay candidates advertised=$advertised gateway=$gateway port=$port")''')
change('''                try {
                    if (!loopback) {''','''                try {
                    val candidate = if (attempt <= 6 || gateway.isNullOrBlank() || gateway == advertised)
                        host else gateway
                    val preliminaryLoopback = candidate == "127.0.0.1" || candidate == "::1"
                    if (!preliminaryLoopback) {''')
change('''                    Log.i(
                        CarPlayConsts.TAG,
                        "AirPlay source dial from StartSession $host:$port " +''','''                    val addr = scopedAddress(candidate)
                    val loopback = addr.isLoopbackAddress
                    Log.i(CarPlayConsts.TAG, "v5 AirPlay endpoint=$candidate resolved=$addr network=${CarPlayAccessoryNet.get()} attempt=$attempt")
                    Log.i(
                        CarPlayConsts.TAG,
                        "AirPlay source dial from StartSession $candidate:$port " +''')
change('''            Log.e(CarPlayConsts.TAG, "StartSession dial failed $host:$port after retries", lastErr)''','''            Log.e(CarPlayConsts.TAG, "StartSession dial failed advertised=$advertised gateway=$gateway port=$port after retries", lastErr)''')
p.write_text(s)
p=Path("aa-display/build.gradle.kts");s=p.read_text()
assert 'versionCode = 3104' in s and 'versionName = "0.3#17.8-v4"' in s
p.write_text(s.replace('versionCode = 3104','versionCode = 3105').replace('versionName = "0.3#17.8-v4"','versionName = "0.3#17.8-v5"'))
print("v5 applied")

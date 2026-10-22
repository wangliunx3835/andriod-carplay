from pathlib import Path
import hashlib
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlaySourceSession.kt")
s=p.read_text()
old='''            val addr = try {
                InetAddress.getByName(host)
            } catch (e: Throwable) {
                Log.e(CarPlayConsts.TAG, "StartSession resolve failed $host", e)
                return@Thread
            }
            // HU-stub / lab loopback: plain sockets, no accessory Network bind.
            val loopback = addr.isLoopbackAddress'''
new='''            // Do not resolve an unscoped fe80:: address before the Wi-Fi handoff
            // has settled. Android rejects link-local TCP without an interface scope.
            // Re-evaluate the DHCP gateway on each attempt because the initial
            // StartSession can arrive before LinkProperties become available.
            val linkLocal = host.startsWith("fe80:", ignoreCase = true)
            // HU-stub / lab loopback: plain sockets, no accessory Network bind.
            val loopback = !linkLocal && try {
                InetAddress.getByName(host).isLoopbackAddress
            } catch (_: Throwable) { false }'''
assert old in s, 'v2 patch block 1 missing'
s=s.replace(old,new,1)
marker='''                    Log.i(
                        CarPlayConsts.TAG,
                        "AirPlay source dial from StartSession $host:$port " +'''
inject='''                    val dialHost = if (linkLocal && !wired) {
                        wifiHandoff?.accessoryIpv4Hint(start.ssid ?: lastWifiSsid)
                    } else null
                    val effectiveHost = dialHost ?: host
                    val addr = InetAddress.getByName(effectiveHost)
                    if (linkLocal && dialHost == null) {
                        throw IllegalStateException(
                            "StartSession fe80 address lacks interface scope; " +
                                "waiting for accessory IPv4 DHCP gateway",
                        )
                    }
                    if (dialHost != null) {
                        Log.i(CarPlayConsts.TAG,
                            "AirPlay link-local fallback via DHCP gateway $dialHost")
                    }
'''
assert marker in s, 'v2 patch block 2 missing'
s=s.replace(marker,inject+marker.replace('$host:$port','$effectiveHost:$port'),1)
marker='                    // Probe reachability before committing the AirPlay handshake thread.'
assert marker in s, 'v2 patch block 3 missing'
s=s.replace(marker,'                    Log.i(CarPlayConsts.TAG, "AirPlay TCP probe target=$addr:$port networkBound=${CarPlayAccessoryNet.hasNetwork()} attempt=$attempt")\n'+marker,1)
p.write_text(s)
digest=hashlib.sha256(p.read_bytes()).hexdigest()
expected='fe84b57bd87214d50aeb724b36aaf7eee0536c42ad62460938091c2d3240bbcc'
print('Patched source SHA256:',digest)
assert digest==expected,'v2 checksum mismatch'

from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlaySourceSession.kt")
s=p.read_text()
a='        val host = advertised ?: gateway'
b='''        // v11: prefer accessory IPv4 over advertised fe80 link-local.
        val advertisedIsLinkLocal = advertised?.substringBefore('%')
            ?.startsWith("fe80:", ignoreCase = true) == true
        val preferGateway = !wired && advertisedIsLinkLocal &&
            !gateway.isNullOrBlank() &&
            runCatching { java.net.InetAddress.getByName(gateway) is java.net.Inet4Address }
                .getOrDefault(false)
        val host = if (preferGateway) gateway else advertised ?: gateway
        Log.i(CarPlayConsts.TAG,
            "v11 endpoint advertised=$advertised gateway=$gateway " +
            "preferGateway=$preferGateway selected=$host")'''
assert s.count(a)==1
s=s.replace(a,b,1)
a='''                    val candidate = if (attempt <= 6 || gateway.isNullOrBlank() || gateway == advertised)
                        host else gateway'''
b='''                    val candidate = if (preferGateway) {
                        host
                    } else if (attempt <= 6 || gateway.isNullOrBlank() || gateway == advertised) {
                        host
                    } else {
                        gateway
                    }'''
assert s.count(a)==1
s=s.replace(a,b,1)
p.write_text(s)

p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlayRtspSession.kt")
s=p.read_text()
a='''            if (screen.firstLine.contains("400")) {
                Log.w(CarPlayConsts.TAG,
                    "v9 screen SETUP 400 profile='''
b='''            if (screen.firstLine.contains("400") && !mib3) {
                Log.w(CarPlayConsts.TAG,
                    "v9 screen SETUP 400 profile='''
assert s.count(a)==1
s=s.replace(a,b,1)
a='''            if (!screen.firstLine.contains("200")) {
                Log.w(CarPlayConsts.TAG, "v9 SETUP screen non-200: ${screen.firstLine}")
                return false
            }'''
b='''            if (!screen.firstLine.contains("200")) {
                Log.w(CarPlayConsts.TAG,
                    "v11 MIB3 screen SETUP rejected without blind retries: ${screen.firstLine}")
                return false
            }'''
assert s.count(a)==1
s=s.replace(a,b,1)
a='''        if (mib3) awaitWifiSyn(4_000L)'''
b='''        if (mib3) {
            Log.i(CarPlayConsts.TAG, "v11 screen SETUP 200; awaiting control SYN before video TCP")
            awaitWifiSyn(4_000L)
            Log.i(CarPlayConsts.TAG, "v11 control SYN wait finished; video TCP target=$peerHost:$dataPort")
        }'''
assert s.count(a)==1
s=s.replace(a,b,1)
p.write_text(s)
p=Path("aa-display/build.gradle.kts")
s=p.read_text()
assert 'versionCode = 3110' in s and 'versionName = "0.3#17.8-v10"' in s
p.write_text(s.replace('versionCode = 3110','versionCode = 3111',1).replace('versionName = "0.3#17.8-v10"','versionName = "0.3#17.8-v11"',1))
print("v11 fixes applied")

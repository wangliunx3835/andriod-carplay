from pathlib import Path
root=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p=root/"ui/main/MainActivity.kt";s=p.read_text()
needle='''        CarPlayStatusUi.bind(this, baseBinding)'''
assert s.count(needle)==1
s=s.replace(needle,'''        // v6: Android 16 local-network permission is runtime gated.
        // Ask while the status Activity is visible; background FGS cannot show a prompt.
        if (android.os.Build.VERSION.SDK_INT >= 37 &&
            checkSelfPermission("android.permission.ACCESS_LOCAL_NETWORK") !=
                android.content.pm.PackageManager.PERMISSION_GRANTED) {
            android.util.Log.i(CarPlayConsts.TAG, "v6 requesting ACCESS_LOCAL_NETWORK")
            requestPermissions(arrayOf("android.permission.ACCESS_LOCAL_NETWORK"), 3106)
        }
        CarPlayStatusUi.bind(this, baseBinding)''',1)
needle='''        CarPlayStatusUi.onPermissionsResult(this, baseBinding, requestCode, grantResults)'''
assert s.count(needle)==1
s=s.replace(needle,'''        if (requestCode == 3106) {
            android.util.Log.i(CarPlayConsts.TAG,
                "v6 local network permission granted=${grantResults.firstOrNull() == android.content.pm.PackageManager.PERMISSION_GRANTED}")
            return
        }
        CarPlayStatusUi.onPermissionsResult(this, baseBinding, requestCode, grantResults)''',1)
p.write_text(s)
p=root/"carplay/CarPlaySourceSession.kt";s=p.read_text()
needle='''            Log.i(CarPlayConsts.TAG, "v5 AirPlay candidates advertised=$advertised gateway=$gateway port=$port")'''
assert s.count(needle)==1
s=s.replace(needle,'''            Log.i(CarPlayConsts.TAG, "v5 AirPlay candidates advertised=$advertised gateway=$gateway port=$port")
            val perm = appContext.checkSelfPermission("android.permission.ACCESS_LOCAL_NETWORK")
            Log.i(CarPlayConsts.TAG, "v6 localNetworkPermission=$perm sdk=${android.os.Build.VERSION.SDK_INT}")''',1)
needle='''                    Log.i(CarPlayConsts.TAG, "v5 AirPlay endpoint=$candidate resolved=$addr network=${CarPlayAccessoryNet.get()} attempt=$attempt")'''
assert s.count(needle)==1
s=s.replace(needle,'''                    val activeNet = CarPlayAccessoryNet.get()
                    val cm = appContext.getSystemService(android.net.ConnectivityManager::class.java)
                    val props = activeNet?.let { cm.getLinkProperties(it) }
                    Log.i(CarPlayConsts.TAG,
                        "v6 route net=$activeNet iface=${props?.interfaceName} " +
                        "addresses=${props?.linkAddresses} routes=${props?.routes}")
                    Log.i(CarPlayConsts.TAG, "v5 AirPlay endpoint=$candidate resolved=$addr network=${CarPlayAccessoryNet.get()} attempt=$attempt")''',1)
needle='''                    // Probe reachability before committing the AirPlay handshake thread.'''
assert s.count(needle)==1
s=s.replace(needle,'''                    Log.i(CarPlayConsts.TAG, "v6 TCP probe begin $addr:$port")
                    // Probe reachability before committing the AirPlay handshake thread.''',1)
needle='''                    // HU reachable — warm Host/VD/audio before SETUP so first frame is ready.'''
assert s.count(needle)==1
s=s.replace(needle,'''                    Log.i(CarPlayConsts.TAG, "v6 TCP probe SUCCESS $addr:$port")
                    // HU reachable — warm Host/VD/audio before SETUP so first frame is ready.''',1)
p.write_text(s)
p=Path("aa-display/build.gradle.kts");s=p.read_text()
assert 'versionCode = 3105' in s and 'versionName = "0.3#17.8-v5"' in s
p.write_text(s.replace('versionCode = 3105','versionCode = 3106').replace('versionName = "0.3#17.8-v5"','versionName = "0.3#17.8-v6"'))
print("v6 applied")

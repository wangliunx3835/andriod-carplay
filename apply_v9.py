from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlayRtspSession.kt")
s=p.read_text()
a='''            val screen = sendScreenSetup(listOf(screenStream), "screen") ?: return false
            if (!screen.firstLine.contains("200")) {
                Log.w(CarPlayConsts.TAG, "SETUP screen audi non-200: ${screen.firstLine}")
                return false
            }
            screen'''
b='''            // v9: Some generic Linux CarPlay receivers reject Audi/CSM-specific
            // screen fields even though the encrypted AirPlay control channel works.
            // Retry only after explicit 400, never on a working MIB3 receiver.
            var screen = sendScreenSetup(listOf(screenStream), "screen") ?: return false
            if (screen.firstLine.contains("400")) {
                Log.w(CarPlayConsts.TAG,
                    "v9 screen SETUP 400 profile=${huProfile} responseHeaders=${screen.headers.keys} " +
                        "responseBodyBytes=${screen.body.size}; trying compatible stream variants")
                val variants: List<Pair<String, Map<String, Any?>>> = listOf(
                    "displayUUID" to linkedMapOf(
                        "type" to 110, "streamConnectionID" to streamConnectionId,
                        "latencyMs" to 75, "displayUUID" to (accessoryDisplayUuid ?: ""),
                    ),
                    "generic" to linkedMapOf(
                        "type" to 110L, "streamConnectionID" to streamConnectionId,
                        "latencyMs" to 60L,
                        "fps" to CarPlayConsts.DEFAULT_VIDEO_FPS.toLong(),
                        "usingScreen" to true,
                        "supportsHighAccuracyTimestamps" to true,
                        "timestampInfo" to timestampInfo,
                    ),
                )
                for ((name, variant) in variants) {
                    Log.i(CarPlayConsts.TAG,
                        "v9 SETUP fallback=$name fields=${variant.keys} size=${screenW}x${screenH}")
                    val retry = sendScreenSetup(listOf(variant), "v9-$name") ?: break
                    Log.i(CarPlayConsts.TAG,
                        "v9 SETUP fallback=$name status=${retry.firstLine} bodyBytes=${retry.body.size}")
                    screen = retry
                    if (screen.firstLine.contains("200") || !screen.firstLine.contains("400")) break
                }
            }
            if (!screen.firstLine.contains("200")) {
                Log.w(CarPlayConsts.TAG, "v9 SETUP screen non-200: ${screen.firstLine}")
                return false
            }
            screen'''
assert s.count(a)==1,s.count(a)
s=s.replace(a,b,1)
p.write_text(s)
p=Path("aa-display/build.gradle.kts")
s=p.read_text()
assert 'versionCode = 3108' in s and 'versionName = "0.3#17.8-v8"' in s
p.write_text(s.replace('versionCode = 3108','versionCode = 3109').replace('versionName = "0.3#17.8-v8"','versionName = "0.3#17.8-v9"'))
print("v9 applied")

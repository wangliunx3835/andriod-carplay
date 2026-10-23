from pathlib import Path
p=Path("aa-display/src/main/java/io/github/nitsuya/aa/display/carplay/CarPlayRtspSession.kt")
s=p.read_text()
def rep(a,b):
 global s
 assert s.count(a)==1,(a[:80],s.count(a))
 s=s.replace(a,b,1)
rep('''        val mib3 = huProfile.usesMib3WirelessPath
        var cseq = cseqStart''','''        val mib3 = huProfile.usesMib3WirelessPath
        Log.i(CarPlayConsts.TAG, "v10 DIAG profile=${huProfile.id} mib3=$mib3 cseqStart=$cseqStart")
        var cseq = cseqStart''')
rep('''            Log.i(
                CarPlayConsts.TAG,
                "SETUP screen mib3=$mib3 $label''','''            val decoded = runCatching {
                BinaryPlist.asDict(BinaryPlist.decode(setupScreenBody))
            }.getOrNull()
            val decodedStreams = decoded?.get("streams") as? List<*>
            val decodedFirst = BinaryPlist.asDict(decodedStreams?.firstOrNull())
            val fieldTypes = requested.firstOrNull()?.entries?.joinToString(",") {
                (k,v) -> "$k:${v?.javaClass?.simpleName ?: "null"}"
            } ?: "none"
            val decodedTypes = decodedFirst?.entries?.joinToString(",") {
                (k,v) -> "$k:${v?.javaClass?.simpleName ?: "null"}"
            } ?: "none"
            Log.i(CarPlayConsts.TAG,
                "v10 DIAG screen fields=$fieldTypes decoded=$decodedTypes " +
                "streams=${decodedStreams?.size} refSize=${if (mib3) 2 else 1}")
            Log.i(
                CarPlayConsts.TAG,
                "SETUP screen mib3=$mib3 $label''')
rep('''            return exchangeEncrypted(
                RtspMessage(
                    "SETUP $sessionUrl RTSP/1.0",
                    headers(
                        mapOf(
                            "Content-Type" to "application/x-apple-binary-plist",
                            "Content-Length" to setupScreenBody.size.toString(),
                        ),
                    ),
                    setupScreenBody,
                ),
            )
        }
        fun sendRecord()''','''            val req = RtspMessage(
                "SETUP $sessionUrl RTSP/1.0",
                headers(mapOf(
                    "Content-Type" to "application/x-apple-binary-plist",
                    "Content-Length" to setupScreenBody.size.toString(),
                )),
                setupScreenBody,
            )
            Log.i(CarPlayConsts.TAG, "v10 DIAG SETUP tx label=$label cseq=${req.cSeq} " +
                "headerNames=${req.headers.keys} bodyBytes=${req.body.size}")
            val resp = exchangeEncrypted(req)
            Log.i(CarPlayConsts.TAG, "v10 DIAG SETUP rx label=$label status=${resp?.firstLine} " +
                "cseq=${resp?.cSeq} headers=${resp?.headers} bodyBytes=${resp?.body?.size ?: -1}")
            if (resp != null && resp.body.isNotEmpty()) {
                val parsed = runCatching { BinaryPlist.asDict(BinaryPlist.decode(resp.body)) }.getOrNull()
                Log.i(CarPlayConsts.TAG, "v10 DIAG response plistKeys=${parsed?.keys}")
            }
            return resp
        }
        fun sendRecord()''')
rep('''            val timingOk = timingSocket?.awaitPacket(1_200L) == true
            if (!timingOk)''','''            val timingOk = timingSocket?.awaitPacket(1_200L) == true
            Log.i(CarPlayConsts.TAG, "v10 DIAG pre-SETUP commands=$commands timing=$timingOk")
            if (!timingOk)''')
p.write_text(s)
p=Path("aa-display/build.gradle.kts")
s=p.read_text()
assert 'versionCode = 3109' in s and 'versionName = "0.3#17.8-v9"' in s
p.write_text(s.replace('versionCode = 3109','versionCode = 3110',1).replace('versionName = "0.3#17.8-v9"','versionName = "0.3#17.8-v10"',1))
print("v10 diagnostics applied")

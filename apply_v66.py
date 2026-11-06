from pathlib import Path
R=Path('aa-display/src/main/java/io/github/nitsuya/aa/display/carplay')
def edit(f,a,b):
 p=R/f;s=p.read_text();assert s.count(a)==1,(f,s.count(a));p.write_text(s.replace(a,b,1))
edit('profile/CarPlayProfileRegistry.kt','    /** Ordered: first matching non-generic profile wins in the resolver. */','''    /** Observed CarLetter receiver; model unknown, proven compatible wire format. */
    val carletter = mib3.copy(
        id = "carletter",
        nameHints = listOf("car audio_", "carletter"),
        ssidHints = listOf("car audio_"),
    )

    /** Ordered: first matching non-generic profile wins in the resolver. */''')
edit('profile/CarPlayProfileRegistry.kt','listOf(mib3, generic)','listOf(carletter, mib3, generic)')
edit('profile/CarPlayProfileResolver.kt','if (list.any { n.contains(it, ignoreCase = true) }) return profile','''if (list.any { hint ->
                    if (profile.id == "mib3") {
                        Regex("(?i)(?<![a-z])" + Regex.escape(hint) + "(?![a-z])")
                            .containsMatchIn(n)
                    } else n.contains(hint, ignoreCase = true)
                }) return profile''')
edit('CarPlayRtspSession.kt','eventChannel.get()?.awaitBeforeScreen(900L) ?: 0','eventChannel.get()?.awaitBeforeScreen(if (huProfile.id == "carletter") 0L else 900L) ?: 0')
edit('CarPlayRtspSession.kt','val timingOk = timingSocket?.awaitPacket(1_200L) == true','val timingOk = timingSocket?.awaitPacket(if (huProfile.id == "carletter") 0L else 1_200L) == true')
edit('CarPlayRtspSession.kt','        screenEgress.getAndSet(egress)?.close()','''        screenEgress.getAndSet(egress)?.close()
        // Queue detect without blocking or adding a competing control reader.
        if (mib3) wifiIap.get()?.announce()''')
edit('CarPlayRtspSession.kt','forceVideo = missing || cameraReturn','forceVideo = missing')
edit('CarPlayRtspSession.kt','"id=$streamConnectionId body=${setupScreenBody.size}B",','"id=${requested.firstOrNull()?.get("streamConnectionID")} body=${setupScreenBody.size}B",')
edit('CarPlayRtspSession.kt','                screenEgress.getAndSet(null)?.close()','''                // Cancel only a failed/blocked transport before negotiation.
                if (closed || stall >= 2500L) screenEgress.getAndSet(null)?.close()''')
p=R/'CarPlayRtspSession.kt';s=p.read_text();a=s.index('        /**\n         * iPhone: screen SETUP → phone detect');b=s.index('        controlIapFlush.set',a);p.write_text(s[:a]+s[b:])
edit('CarPlayRtspSession.kt','"v61 return probe reason="','"v66 return probe reason="')
p=Path('aa-display/build.gradle.kts');s=p.read_text();assert 'versionCode = 3165' in s;p.write_text(s.replace('versionCode = 3165','versionCode = 3166').replace('0.3#17.8-v65','0.3#17.8-v66'))
print('v66 connection and reverse-video patch applied')

from pathlib import Path
R=Path('aa-display/src/main/java/io/github/nitsuya/aa/display/carplay')
def edit(name,old,new):
 p=R/name;s=p.read_text();assert s.count(old)==1,(name,s.count(old));p.write_text(s.replace(old,new,1))
edit('CarPlayRtspSession.kt',
 'eventChannel.get()?.awaitBeforeScreen(if (huProfile.id == "carletter") 0L else 900L) ?: 0',
 'eventChannel.get()?.awaitBeforeScreen(900L) ?: 0')
edit('CarPlayRtspSession.kt',
 'val timingOk = timingSocket?.awaitPacket(if (huProfile.id == "carletter") 0L else 1_200L) == true',
 'val timingOk = timingSocket?.awaitPacket(1_200L) == true')
edit('CarPlayRtspSession.kt',
 '''        // Queue detect without blocking or adding a competing control reader.
        if (mib3) wifiIap.get()?.announce()''',
 '''        // v67: restore the v65 wire sequence. Active detect here was flushed
        // synchronously before audio SETUP and preceded repeated peer shutdowns.
        // Do not send optional iAP commands during media startup.''')
edit('CarPlayRtspSession.kt','"v66 return probe reason="','"v67 return probe reason="')
s=(R/'CarPlayRtspSession.kt').read_text()
assert '.announce()' not in s and 'awaitWifiSyn(' not in s
assert 'forceVideo = missing || cameraReturn' not in s
assert 'eventChannel.get()?.awaitBeforeScreen(900L)' in s
assert 'timingSocket?.awaitPacket(1_200L)' in s
p=Path('aa-display/build.gradle.kts');s=p.read_text();assert 'versionCode = 3166' in s
p.write_text(s.replace('versionCode = 3166','versionCode = 3167').replace('0.3#17.8-v66','0.3#17.8-v67'))
print('v67: restored v65 connection waits, removed active startup iAP detect; retained profile/reverse fixes')

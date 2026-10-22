from pathlib import Path
r=Path('aa-display/src/main/java/io/github/nitsuya/aa/display/carplay')
p=r/'protocol/Iap2Session.kt';s=p.read_text()
a=s.index('    private fun negotiateLinkLocked(lsp: LinkSyncPayload): LinkSyncPayload {')
b=s.index('\n    private fun schedulePeerSynReadyLocked()',a)
s=s[:a]+'''    private fun negotiateLinkLocked(lsp: LinkSyncPayload): LinkSyncPayload {
        // v4: Echo the HU session IDs and versions; DiPlay v3 changed control v2 to v1.
        Log.i(CarPlayConsts.TAG, "v4 iAP peer LSP echo sessions=${lsp.sessions}")
        return lsp
    }
'''+s[b:];p.write_text(s)
p=r/'CarPlaySourceSession.kt';s=p.read_text()
def rep(old,new,count=None):
    global s
    if count is not None: assert s.count(old)==count,(old,s.count(old))
    s=s.replace(old,new)
rep('    private val airplayDialed = AtomicBoolean(false)','    private val airplayDialed = AtomicBoolean(false)\n    private val dialGeneration = AtomicLong(0)',1)
rep('        airplayDialed.set(false)\n        mediaPrepared.set(false)','        dialGeneration.incrementAndGet()\n        airplayDialed.set(false)\n        mediaPrepared.set(false)',1)
rep('                airplayDialed.set(false)','                dialGeneration.incrementAndGet()\n                airplayDialed.set(false)')
rep('        airplayDialed.set(true)\n        if (host.startsWith','        val dialToken = dialGeneration.incrementAndGet()\n        airplayDialed.set(true)\n        Log.i(CarPlayConsts.TAG, "v4 dial token=$dialToken host=$host port=$port ips=${start.ipAddresses}")\n        if (host.startsWith',1)
rep('                if (!running.get()) return@Thread\n                try {','                if (!running.get() || dialGeneration.get() != dialToken) {\n                    Log.i(CarPlayConsts.TAG, "v4 obsolete dial cancelled token=$dialToken")\n                    return@Thread\n                }\n                try {',1)
rep('                    // HU reachable — warm Host/VD/audio before SETUP so first frame is ready.','                    if (dialGeneration.get() != dialToken) return@Thread\n                    // HU reachable — warm Host/VD/audio before SETUP so first frame is ready.',1)
rep('        if (!running.compareAndSet(true, false)) return\n        cancelPhoneAudioRelease()','        if (!running.compareAndSet(true, false)) return\n        dialGeneration.incrementAndGet()\n        cancelPhoneAudioRelease()',1)
p.write_text(s)
p=Path('aa-display/build.gradle.kts');s=p.read_text()
assert 'versionCode = 3103' in s and 'versionName = "0.3#17.8-v3"' in s
p.write_text(s.replace('versionCode = 3103','versionCode = 3104').replace('versionName = "0.3#17.8-v3"','versionName = "0.3#17.8-v4"'))
print('v4 applied')

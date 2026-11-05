#!/usr/bin/env python3
"""v61 power trim: avoid repeated privileged BT failures and LRC reparsing."""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(path,a,b,label):
 p=R/path;s=p.read_text(encoding="utf-8");n=s.count(a)
 if n!=1:raise AssertionError("v61 finish "+label+" count="+str(n))
 p.write_text(s.replace(a,b,1),encoding="utf-8")

one("carplay/CarPlayBluetoothLink.kt",
 """    private val discoverableRequested = AtomicBoolean(false)""",
 """    private val discoverableRequested = AtomicBoolean(false)
    @Volatile private var v61PrivilegedScanDenied = false""","BT deny field")
one("carplay/CarPlayBluetoothLink.kt",
 """        if (!enabled) return
        val mode = readScanMode(bt) ?: return""",
 """        if (!enabled) return
        if (v61PrivilegedScanDenied && discoverableRequested.get()) return
        val mode = readScanMode(bt) ?: return""","BT repeated check")
one("carplay/CarPlayBluetoothLink.kt",
 """        val ok = try {
            val method = bt.javaClass.getMethod("setScanMode", Int::class.javaPrimitiveType)""",
 """        val ok = if (v61PrivilegedScanDenied) false else try {
            val method = bt.javaClass.getMethod("setScanMode", Int::class.javaPrimitiveType)""","BT privilege attempt")
# Use dynamically constructed Kotlin dollar interpolation anchor inside Python
# to keep literal source matching and not require external tooling.
D="$"
old='            Log.w(CarPlayConsts.TAG, "BT setScanMode discoverable failed: '+D+'{e.cause?.message ?: e.message}")\n            false'
new='''            val why = (e.cause?.message ?: e.message).orEmpty()
            if (e.cause is SecurityException || e is SecurityException ||
                why.contains("BLUETOOTH_PRIVILEGED")) {
                v61PrivilegedScanDenied = true
                Log.i(CarPlayConsts.TAG, "v61 BT privileged scan denied; suppress repeat")
            } else Log.w(CarPlayConsts.TAG,"BT setScanMode discoverable failed: " + why)
            false'''
one("carplay/CarPlayBluetoothLink.kt",old,new,"BT permission log")

# Existing v53 code reparses up to 64 KiB LRC and sorts rows on every 650ms
# overlay refresh. Parse only when the text actually changes; keep position
# calculation live and do not add a background timer.
path="carplay/LyricV53Bridge.kt"
p=R/path;s=p.read_text(encoding="utf-8")
begin=s.index("  private fun lines(raw:String,position:Long):Pair<String,String>? {")
end=s.index("  fun read(c:Context):Music? {",begin)
old=s[begin:end]
if old.count("   list.sortBy{it.first}")!=1 or old.count("   val i=list.indexOfLast")!=1:
 raise AssertionError("v61 LRC parse shape changed")
modified=old
modified=modified.replace("  private fun lines(raw:String,position:Long):Pair<String,String>? {\n   val list=ArrayList<Pair<Long,String>>()",
 """  private var v61LastRaw: String? = null
  private var v61Parsed: List<Pair<Long,String>> = emptyList()
  private fun lines(raw:String,position:Long):Pair<String,String>? {
   val list = synchronized(this) {
    if(raw==v61LastRaw) v61Parsed else {
     val parsed=ArrayList<Pair<Long,String>>()""")
modified=modified.replace("list.add(", "parsed.add(")
modified=modified.replace("""   list.sortBy{it.first}
   val i=list.indexOfLast""",
 """     parsed.sortBy{it.first}
     v61LastRaw=raw
     v61Parsed=parsed
     parsed
    }
   }
   val i=list.indexOfLast""")
if modified==old or "v61Parsed=parsed" not in modified:raise AssertionError("v61 LRC unchanged")
s=s[:begin]+modified+s[end:]
p.write_text(s,encoding="utf-8")
g=Path("aa-display/build.gradle.kts")
v=g.read_text(encoding="utf-8")
if v.count("versionCode = 3160")!=1 or v.count('versionName = "0.3#17.8-v60"')!=1:
 raise AssertionError("v61 requires v60")
g.write_text(v.replace("versionCode = 3160","versionCode = 3161")
 .replace('versionName = "0.3#17.8-v60"','versionName = "0.3#17.8-v61"'),
 encoding="utf-8")
print("v61 quiet BT + lyric parse cache + version 3161")

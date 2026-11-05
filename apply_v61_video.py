#!/usr/bin/env python3
"""v61 video: detect peer FIN on AirPlay type-110 output-only dataPort."""
from pathlib import Path
R=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
def one(path,a,b,label):
 p=R/path; s=p.read_text(encoding="utf-8"); n=s.count(a)
 if n!=1: raise AssertionError("v61 video "+label+" count="+str(n))
 p.write_text(s.replace(a,b,1),encoding="utf-8")

one("carplay/protocol/ScreenStreamEgress.kt",
 """    private val closed = AtomicBoolean(false)
    private val framesSent""",
 """    private val closed = AtomicBoolean(false)
    private val v61RemoteFin = AtomicBoolean(false)
    private val v61FinProbeEnabled = runCatching {
        val c = Class.forName("android.os.SystemProperties")
        val g = c.getMethod("get", String::class.java, String::class.java)
        (g.invoke(null, "debug.carplay.v61_peer_fin_probe", "1") as String) != "0"
    }.getOrDefault(true)
    private val framesSent""","FIN fields")
one("carplay/protocol/ScreenStreamEgress.kt",
 """    fun isClosed(): Boolean = closed.get()""",
 """    fun isClosed(): Boolean = closed.get()
    fun v61RemoteFinSeen(): Boolean = v61RemoteFin.get()

    // Called ONLY on the post-camera one-shot probe worker. Android Socket
    // isClosed remains false after receiving FIN until locally closed.
    fun v61ProbeRemoteFin(): Boolean {
        if (!v61FinProbeEnabled || closed.get()) return closed.get()
        if (v61RemoteFin.get()) return true
        return runCatching {
            val previous = socket.soTimeout
            try {
                socket.soTimeout = 35
                val b = socket.getInputStream().read()
                if (b < 0) {
                    v61RemoteFin.set(true)
                    Log.w(CarPlayConsts.TAG, "v61 screen TCP peer FIN observed")
                    true
                } else {
                    Log.w(CarPlayConsts.TAG, "v61 unexpected inbound byte on video egress")
                    false
                }
            } finally {
                runCatching { socket.soTimeout = previous }
            }
        }.recover { e ->
            if (e is java.net.SocketTimeoutException) false
            else {
                Log.w(CarPlayConsts.TAG, "v61 peer-FIN probe unavailable", e)
                false
            }
        }.getOrDefault(false)
    }""","FIN method")
one("carplay/CarPlayRtspSession.kt",
 """        val closed = screenEgress.get()?.isClosed() == true
        if (stall < 2500L && !closed && !v58VideoUnusable.get()) return""",
 """        val currentScreen = screenEgress.get()
        val missing = currentScreen == null
        val closed = currentScreen?.isClosed() == true
        val peerFin = currentScreen?.v61RemoteFinSeen() == true
        if (stall < 2500L && !closed && !missing && !peerFin &&
            !v58VideoUnusable.get()) return""","unhealthy or missing")
one("carplay/CarPlayRtspSession.kt",
 """                    reason + " blockedMs=" + stall + " socketClosed=" + closed)""",
 """                    reason + " blockedMs=" + stall + " socketClosed=" + closed +
                    " socketMissing=" + missing + " peerFin=" + peerFin)""",
 "recovery state log")
one("carplay/CarPlayRtspSession.kt",
 """                    val stall = maxOf(v57VideoQueue.blockedForMs(),
                        v57VideoQueue.queuedWithoutProgressMs())
                    Log.i(CarPlayConsts.TAG, "v59 return probe reason=" + reason +
                        " stalledMs=" + stall + " egressClosed=" +
                        (screenEgress.get()?.isClosed() == true))""",
 """                    val stall = maxOf(v57VideoQueue.blockedForMs(),
                        v57VideoQueue.queuedWithoutProgressMs())
                    val egress = screenEgress.get()
                    val peerFin = egress?.v61ProbeRemoteFin() == true
                    Log.i(CarPlayConsts.TAG, "v61 return probe reason=" + reason +
                        " stalledMs=" + stall + " egressMissing=" +
                        (egress == null) + " egressClosed=" +
                        (egress?.isClosed() == true) + " peerFin=" + peerFin)""",
 "single return probe")
print("v61 video peer FIN probe applied")

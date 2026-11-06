package io.github.nitsuya.aa.display.carplay

/** A transport policy, never an iAP/AirPlay identity selector. */
internal class SmartBoxV69DialPolicy {
    data class Decision(val discover: Boolean, val dial: Boolean, val reason: String)
    private data class Peer(val first: Long, var sdp: Long? = null, var dial: Long? = null)
    private val peers = mutableMapOf<String,Peer>()
    @Synchronized fun evaluate(name: String?, address: String, now: Long,
        bonded: Boolean, occupied: Boolean, accessory: Boolean): Decision? {
        if (!matches(name)) return null
        if (occupied) return Decision(false,false,"existing-session")
        if (!bonded) return Decision(false,false,"wait-bond")
        val p=peers.getOrPut(address) { Peer(now) }
        val discover=p.sdp==null || now-p.sdp!!>=30_000L
        if (discover) p.sdp=now
        val reason=when {
            now-p.first<5_000L -> "inbound-grace"
            !accessory -> "no-caff-wait-inbound"
            p.dial!=null && now-p.dial!!<30_000L -> "dial-backoff"
            else -> "advertised-caff"
        }
        return Decision(discover,reason=="advertised-caff",reason)
    }
    @Synchronized fun reserve(address: String,now: Long): Boolean {
        val p=peers[address] ?: return false
        if (p.dial!=null && now-p.dial!!<30_000L) return false
        p.dial=now
        return true
    }
    @Synchronized fun clear() { peers.clear() }
    companion object {
        fun matches(name: String?) = name?.trim()?.startsWith("smartbox",ignoreCase=true)==true
    }
}

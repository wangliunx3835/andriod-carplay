package io.github.nitsuya.aa.display.carplay

import org.junit.Assert.*
import org.junit.Test

class SmartBoxV69DialPolicyTest {
    private fun step(p: SmartBoxV69DialPolicy,t: Long,a: Boolean=true,
        busy: Boolean=false,bonded: Boolean=true) =
        p.evaluate("smartBox-0EA4","one",t,bonded,busy,a)!!
    @Test fun matchesAllCasesAndSuffixes() {
        for(n in listOf("smartBox-0EA4","SMARTBOX-ABCD","Smartbox_1234","smartbox"," smartBOX-ffff "))
            assertTrue(n,SmartBoxV69DialPolicy.matches(n))
    }
    @Test fun leavesOtherReceiversAlone() {
        for(n in listOf(null,"Car Audio_457f","Audi MMI","DiPlay","Box-F4D0","not-smartBox"))
            assertFalse(SmartBoxV69DialPolicy.matches(n))
        assertNull(SmartBoxV69DialPolicy().evaluate("Audi MMI","x",0,true,false,true))
    }
    @Test fun doesNotInterfereWithBonding() {
        val d=step(SmartBoxV69DialPolicy(),0,bonded=false)
        assertFalse(d.discover); assertFalse(d.dial)
    }
    @Test fun neverProbesAnOccupiedSession() {
        val d=step(SmartBoxV69DialPolicy(),0,busy=true)
        assertFalse(d.discover); assertFalse(d.dial)
    }
    @Test fun inboundGetsFiveSeconds() {
        val p=SmartBoxV69DialPolicy(); assertTrue(step(p,0).discover)
        assertFalse(step(p,4999).dial); assertTrue(step(p,5000).dial)
    }
    @Test fun noBlindDialWhenServiceMissing() {
        val p=SmartBoxV69DialPolicy(); step(p,0,a=false)
        assertFalse(step(p,6000,a=false).dial); assertTrue(step(p,6000).dial)
    }
    @Test fun limitsSdpRequests() {
        val p=SmartBoxV69DialPolicy(); assertTrue(step(p,0).discover)
        assertFalse(step(p,29999).discover); assertTrue(step(p,30000).discover)
    }
    @Test fun limitsFailedDials() {
        val p=SmartBoxV69DialPolicy(); step(p,0)
        assertTrue(step(p,5000).dial); assertTrue(p.reserve("one",5000))
        assertFalse(step(p,9000).dial); assertFalse(p.reserve("one",9000))
        assertTrue(step(p,35000).dial)
    }
    @Test fun separatePeerTimers() {
        val p=SmartBoxV69DialPolicy(); step(p,0); p.reserve("one",5000)
        assertFalse(p.evaluate("SMARTBOX-two","two",6000,true,false,true)!!.dial)
        assertTrue(p.evaluate("SMARTBOX-two","two",11000,true,false,true)!!.dial)
    }
    @Test fun stopResetsPolicy() {
        val p=SmartBoxV69DialPolicy(); step(p,0); p.clear()
        val d=step(p,60000); assertTrue(d.discover); assertFalse(d.dial)
    }
}

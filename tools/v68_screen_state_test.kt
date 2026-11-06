package io.github.nitsuya.aa.display.carplay

import org.junit.Assert.*
import org.junit.Test

class CarPlayV68ScreenStateTest {
    private class Harness {
        val state = CarPlayV68ScreenState()
        val calls = mutableListOf<String>()
        var live = true
        var owns = false
        var ack = true
        var setupOk = true
        var modesOk = true
        var dieOnAck = false
        var takeDuringSetup = false
        fun step(force: Boolean = false) = state.reconcile({ live }, { owns }, force,
            { calls += "close" }, { calls += "teardown"; if (dieOnAck) live = false; ack },
            { calls += "modes"; modesOk },
            { calls += "setup"; if (takeDuringSetup) owns = false; setupOk },
            { calls += "resume" })
    }
    @Test fun leaveThenReturnOrdersReleaseBeforeSetup() {
        val h = Harness(); assertTrue(h.step()); h.owns = true; assertTrue(h.step())
        assertEquals(listOf("modes", "close", "teardown", "modes", "setup", "resume"), h.calls)
    }
    @Test fun failedReleaseNeverStartsReplacement() {
        val h = Harness(); h.ack = false; assertFalse(h.step()); h.owns = true
        assertFalse(h.step()); assertFalse(h.calls.contains("setup"))
        h.ack = true; assertTrue(h.step()); assertEquals(1,h.calls.count { it == "close" })
    }
    @Test fun rejectedSetupStaysReleasedUntilExplicitRetry() {
        val h = Harness(); h.step(); h.owns = true; h.setupOk = false
        assertFalse(h.step()); assertEquals(CarPlayV68ScreenState.Phase.RELEASED,h.state.phase)
        assertFalse(h.calls.contains("resume")); h.setupOk = true; assertTrue(h.step())
    }
    @Test fun healthyRequestDoesNotRebuild() {
        val h = Harness(); h.owns = true; assertTrue(h.step()); assertTrue(h.calls.isEmpty())
    }
    @Test fun takeoverDuringSetupDoesNotResume() {
        val h = Harness(); h.step(); h.owns = true; h.takeDuringSetup = true; h.step()
        assertFalse(h.calls.contains("resume"))
        assertEquals(CarPlayV68ScreenState.Phase.RELEASED,h.state.phase)
    }
    @Test fun obsoleteSessionDoesNoWork() {
        val h = Harness(); h.live = false; assertFalse(h.step(true)); assertTrue(h.calls.isEmpty())
    }
    @Test fun failedModesDoesNotCloseOrSetup() {
        val h = Harness(); h.modesOk = false; assertFalse(h.step())
        assertEquals(listOf("modes"),h.calls)
    }
    @Test fun sessionEndingDuringAckNeverSetsUpReplacement() {
        val h = Harness(); h.owns = true; h.dieOnAck = true; assertFalse(h.step(true))
        assertFalse(h.calls.contains("setup")); assertFalse(h.calls.contains("resume"))
    }
    @Test fun brokenActiveStreamIsReleasedBeforeReplacement() {
        val h = Harness(); h.owns = true; h.step(true)
        assertEquals(listOf("close", "teardown", "modes", "setup", "resume"), h.calls)
    }
}

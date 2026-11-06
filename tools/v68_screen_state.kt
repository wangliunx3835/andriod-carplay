package io.github.nitsuya.aa.display.carplay

/** Serialized by the session worker. A socket close is not a protocol teardown. */
internal class CarPlayV68ScreenState {
    enum class Phase { ACTIVE, RELEASE_REQUIRED, RELEASED }
    var phase = Phase.ACTIVE
        private set

    private var closedForRelease = false

    fun reconcile(
        live: () -> Boolean,
        ownsScreen: () -> Boolean,
        force: Boolean,
        pauseAndClose: () -> Unit,
        teardown: () -> Boolean,
        publishModes: () -> Boolean,
        setup: () -> Boolean,
        resume: () -> Unit,
    ): Boolean {
        if (!live()) return false
        if (phase == Phase.ACTIVE && (!ownsScreen() || force)) {
            phase = Phase.RELEASE_REQUIRED
            closedForRelease = false
        }
        if (phase == Phase.RELEASE_REQUIRED) {
            if (!closedForRelease) {
                if (!ownsScreen() && !publishModes()) return false
                if (!live()) return false
                pauseAndClose()
                closedForRelease = true
            }
            if (!live() || !teardown() || !live()) return false
            phase = Phase.RELEASED
        }
        if (phase == Phase.RELEASED && ownsScreen()) {
            if (!live() || !publishModes() || !live() || !ownsScreen()) return false
            if (!setup() || !live()) return false
            phase = Phase.ACTIVE
            // An ownership change while SETUP was in flight must not enable video.
            if (!ownsScreen()) return reconcile(live, ownsScreen, false,
                pauseAndClose, teardown, publishModes, setup, resume)
            resume()
        }
        return true
    }
}

#!/usr/bin/env python3
"""v16: IME-only improvements. No wireless, RTSP, iAP2 or media changes."""
from pathlib import Path

root = Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
controller = root / "ui/aa/split/SplitDisplayController.kt"
source = controller.read_text()
assert "internal val ime = SplitImeController(this)" in source
assert "fun onDestroy() {" in source
assert "        ime.stop()" in source
assert "        onCreated(primaryDisplayId)" in source
source = source.replace(
    "import io.github.nitsuya.aa.display.xposed.hook.VdDensityPin",
    "import io.github.nitsuya.aa.display.xposed.hook.VdDensityPin\nimport io.github.nitsuya.aa.display.xposed.hook.VdImeDisplayPin",
    1,
)
source = source.replace(
    "        onCreated(primaryDisplayId)",
    """        // v16: enable the upstream VD IME pinning + soft keyboard even with
        // Bluetooth hardware-keyboard presence. Executed in system_server.
        // Existing hook is already display-scoped to AADisplay panes.
        runCatching { VdImeDisplayPin.onAaDisplaysActive(context) }
            .onFailure { log(TAG, "v16 IME activate failed", it) }
        onCreated(primaryDisplayId)""",
    1,
)
source = source.replace(
    "        ime.stop()",
    """        ime.stop()
        runCatching { VdImeDisplayPin.onAaDisplaysInactive(context) }
            .onFailure { log(TAG, "v16 IME restore failed", it) }""",
    1,
)
controller.write_text(source)

inp = root / "ui/aa/split/SplitInputRecents.kt"
source = inp.read_text()
assert "Instances.iInputManager.injectInputEvent(event, 0)" in source
source = source.replace(
    "            Instances.iInputManager.injectInputEvent(event, 0)",
    """            val injected = Instances.iInputManager.injectInputEvent(event, 0)
            // v16: report actual injection result and target display on DOWN/UP.
            // Previously CoreApi.touchPane returned Unit, hiding injection failures.
            if (event is android.view.MotionEvent &&
                (event.actionMasked == android.view.MotionEvent.ACTION_DOWN ||
                    event.actionMasked == android.view.MotionEvent.ACTION_UP)) {
                log(SplitDisplayController.TAG,
                    "v16 IME touch display=$displayId action=${event.actionMasked} injected=$injected")
            }
            injected""",
    1,
)
inp.write_text(source)

bridge = root / "carplay/CarPlayInputBridge.kt"
source = bridge.read_text()
assert "CoreApi.touchPane(pane, event)" in source
source = source.replace(
    "                CoreApi.touchPane(pane, event)",
    """                if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_UP) {
                    Log.i(CarPlayConsts.TAG,
                        "v16 IME paneTouch pane=$pane action=$action x=$px y=$py")
                }
                CoreApi.touchPane(pane, event)""",
    1,
)
bridge.write_text(source)

# v16 is strictly scoped to IME/touch diagnostics and its lifecycle.
# The v15 wireless and media patch stack is preserved verbatim.
gradle = Path("aa-display/build.gradle.kts")
version = gradle.read_text()
assert 'versionCode = 3115' in version
assert 'versionName = "0.3#17.8-v15"' in version
version = version.replace('versionCode = 3115', 'versionCode = 3116', 1)
version = version.replace('versionName = "0.3#17.8-v15"', 'versionName = "0.3#17.8-v16"', 1)
gradle.write_text(version)
print("v16 IME patch applied")

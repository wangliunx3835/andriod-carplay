#!/usr/bin/env python3
"""v21: native Android IME routing, same policy model as original AADisplay.
Applied after v20; revert only experimental IME interventions.
Never change CarPlay transport, VD flags, density, or video pipeline.
"""
from pathlib import Path
import subprocess

base=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
controller=base/"ui/aa/split/SplitImeController.kt"
original=subprocess.check_output(["git","show","HEAD:"+controller.as_posix()],text=True)
assert "private val pollRunnable" in original and "fun hide()" in original
controller.write_text(original)
# v17 touch policy reassert callback is no longer needed.
p=base/"ui/aa/split/SplitInputRecents.kt"
s=p.read_text()
old='''            if (event is android.view.MotionEvent &&
                event.actionMasked == android.view.MotionEvent.ACTION_DOWN) {
                c.ime.onPaneTouch(displayId)
            }
'''
assert old in s
p.write_text(s.replace(old,"",1))
# Avoid forced IMMS display-id rewriting. System creates and moves IME
# windows according to the local policy set on each virtual display.
p=base/"xposed/CoreManagerService.kt"
s=p.read_text()
old='''            runCatching { VdImeDisplayPin.ensureHooked() }
                .onFailure { log(TAG, "VdImeDisplayPin.ensureHooked failed", it) }'''
assert old in s
s=s.replace(old,'''            // v21: native IME routing; do not install display-id rewriting hooks.''',1)
old='''                            runCatching { VdImeDisplayPin.onAaDisplaysActive(systemContext) }
                                .onFailure { log(TAG, "VdImeDisplayPin session-active failed", it) }'''
assert old in s
s=s.replace(old,'''                            // v21: leave IME routing and hardware-keyboard settings to Android.''',1)
old='''                runCatching { VdImeDisplayPin.onAaDisplaysInactive(systemContext) }
                    .onFailure { log(TAG, "VdImeDisplayPin session-inactive failed", it) }'''
assert old in s
s=s.replace(old,'''                // v21: no IME override to restore.''',1)
p.write_text(s)
g=Path("aa-display/build.gradle.kts")
s=g.read_text()
assert 'versionCode = 3120' in s and 'versionName = "0.3#17.8-v20"' in s
s=s.replace('versionCode = 3120','versionCode = 3121',1).replace('versionName = "0.3#17.8-v20"','versionName = "0.3#17.8-v21"',1)
g.write_text(s)
print("v21: original IME controller restored; extra IMMS routing hooks disabled")

#!/usr/bin/env python3
"""v22: restore lagXkjy's original virtual-display IME routing hooks.
Run after v21. Preserve CarPlay transport, VD flags, density and video.
"""
from pathlib import Path

base=Path("aa-display/src/main/java/io/github/nitsuya/aa/display")
p=base/"xposed/CoreManagerService.kt"
s=p.read_text()
changes=[
("            // v21: native IME routing; do not install display-id rewriting hooks.",
 '''            runCatching { VdImeDisplayPin.ensureHooked() }
                .onFailure { log(TAG, "VdImeDisplayPin.ensureHooked failed", it) }'''),
("                            // v21: leave IME routing and hardware-keyboard settings to Android.",
 '''                            runCatching { VdImeDisplayPin.onAaDisplaysActive(systemContext) }
                                .onFailure { log(TAG, "VdImeDisplayPin session-active failed", it) }'''),
("                // v21: no IME override to restore.",
 '''                runCatching { VdImeDisplayPin.onAaDisplaysInactive(systemContext) }
                    .onFailure { log(TAG, "VdImeDisplayPin session-inactive failed", it) }''')
]
for old,new in changes:
    assert s.count(old)==1, f"Unexpected CoreManagerService context: {old}"
    s=s.replace(old,new,1)
p.write_text(s)
g=Path("aa-display/build.gradle.kts")
s=g.read_text()
assert 'versionCode = 3121' in s and 'versionName = "0.3#17.8-v21"' in s
g.write_text(s.replace('versionCode = 3121','versionCode = 3122',1).replace('versionName = "0.3#17.8-v21"','versionName = "0.3#17.8-v22"',1))
print("v22: original VdImeDisplayPin hook lifecycle restored")

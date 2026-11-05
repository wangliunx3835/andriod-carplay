#!/usr/bin/env python3
"""v64: bounded, independent synced-lyrics catalog fallback after v63.

Only touches QiShui lyric source and version, no CarPlay control/AV/video.
"""
from pathlib import Path
r=Path("aa-display/src/main")
p=r/"java/io/github/nitsuya/aa/display/carplay/CarPlayV63SodaLyrics.kt"
s=p.read_text(encoding="utf-8")
if 'private fun lookup(title: String, artist: String): String?' not in s:
 raise AssertionError("v64 requires v63 lyrics source")
if 'private fun lookupLrclib' in s:
 raise AssertionError("v64 applied already")
replacement=Path("../tools/v64_CarPlayV64SodaLyrics.kt").read_text(encoding="utf-8")
assert replacement.count('private fun lookupLrclib')==1
assert replacement.count('private fun lookup(title: String, artist: String)')==1
p.write_text(replacement,encoding="utf-8")
g=Path("aa-display/build.gradle.kts")
v=g.read_text(encoding="utf-8")
if v.count("versionCode = 3163")!=1 or v.count('versionName = "0.3#17.8-v63"')!=1:
 raise AssertionError("v64 exact v63 baseline required")
g.write_text(v.replace("versionCode = 3163","versionCode = 3164")
 .replace('versionName = "0.3#17.8-v63"','versionName = "0.3#17.8-v64"'),
 encoding="utf-8")
print("v64 independent LRCLIB synced-LRC fallback installed")

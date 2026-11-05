#!/usr/bin/env python3
"""v63: opt-in song-change-only Soda car lyrics using the public share route.

Applies exactly after v62; does not touch video/RTSP/IME/audio/connection.
No timed network polling, no continuous app hooks, and no screen text scraping.
"""
from pathlib import Path
R=Path("aa-display/src/main")
C="java/io/github/nitsuya/aa/display/carplay/"
def one(path,old,new,label):
 p=R/path;s=p.read_text(encoding="utf-8");n=s.count(old)
 if n!=1:raise AssertionError("v63 "+label+" matches="+str(n))
 p.write_text(s.replace(old,new,1),encoding="utf-8")

# AADisplay runs online lookup on its existing media-overlay worker as a
# trigger only; the actual HTTPS operation happens once on its own daemon.
# Opt-in is enabled by default for independent QiShui car as requested;
# user can toggle off from the existing media settings screen.
one(C+"CarPlayMediaOverlaySettings.kt",
'''        val showCover: Boolean = true,''',
'''        val showCover: Boolean = true,
        val sodaCarOnlineLyrics: Boolean = true,''',"preference field")
one(C+"CarPlayMediaOverlaySettings.kt",
'''            showCover = s.getBoolean("cover", true),''',
'''            showCover = s.getBoolean("cover", true),
            sodaCarOnlineLyrics = s.getBoolean("soda_car_online_lrc", true),''',
"read preference")
one(C+"CarPlayMediaOverlaySettings.kt",
'''            .putBoolean("cover", cfg.showCover)''',
'''            .putBoolean("cover", cfg.showCover)
            .putBoolean("soda_car_online_lrc", cfg.sodaCarOnlineLyrics)''',
"save preference")
one(C+"CarPlayMediaSettingsUi.kt",
'''        toggle("启用车机悬浮媒体",cfg.enabled) { save(cfg.copy(enabled=it)) }''',
'''        toggle("启用车机悬浮媒体",cfg.enabled) { save(cfg.copy(enabled=it)) }
        toggle("汽水音乐车机版在线歌词兜底（联网匹配歌曲）",cfg.sodaCarOnlineLyrics) {
            save(cfg.copy(sodaCarOnlineLyrics=it))
        }''',"media setting toggle")

p=R/(C+"CarPlayV63SodaLyrics.kt")
if p.exists():raise AssertionError("v63 lyrics already exists")
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(Path("../tools/v63_CarPlayV63SodaLyrics.kt").read_text(encoding="utf-8"),
 encoding="utf-8")

one(C+"CarPlayMediaOverlay.kt",
'''        val observed=LyricV53Bridge.read(c)''',
'''        val observed=LyricV53Bridge.read(c)
        if (observed != null) {
            CarPlayV63SodaLyrics.maybeFetch(c, observed, cfg.sodaCarOnlineLyrics)
        }''',"single event-driven lyric fallback")

g=Path("aa-display/build.gradle.kts")
s=g.read_text(encoding="utf-8")
if s.count("versionCode = 3162")!=1 or
        s.count('versionName = "0.3#17.8-v62"')!=1:
 raise AssertionError("v63 exact v62 baseline required")
g.write_text(s.replace("versionCode = 3162","versionCode = 3163")
    .replace('versionName = "0.3#17.8-v62"',
             'versionName = "0.3#17.8-v63"'),encoding="utf-8")
print("v63 car online lyric fallback with cached one-shot lookup and user toggle")

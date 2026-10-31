#!/usr/bin/env python3
"""v43: opt-in Gboard-only Xiaomi Greezer guard while CarPlay is live.

Proof: v42 dumpsys input ANR: InputMethod 5s; Xiaomi ActionExecute logged
freezeUid SUCCESS uid=Gboard while the external VDs were awake. 
No global freezer disable; no input surface or touch route changes.
Apply after v42.
"""
from pathlib import Path

ROOT = Path("aa-display/src/main/java/io/github/nitsuya/aa/display")

def replace_once(src, old, new, what):
    matches = src.count(old)
    if matches != 1:
        raise AssertionError(f"v43 {what}: expected exactly 1 match; got {matches}")
    return src.replace(old, new, 1)

# Small dedicated helper: no system-wide policies, only the single known
# input-method package, with explicit user opt-in.
src = r'''package io.github.nitsuya.aa.display.xposed.hook

import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.os.Process
import android.provider.Settings
import io.github.nitsuya.aa.display.xposed.util.log

/**
 * v43 diagnostic A/B guard. Xiaomi Greezer's preCheckInterest() may exempt UIDs
 * in com.miui.game.allowlist (internal, NOT a public API; ROM-dependent).
 *
 * Only when debug.carplay.v43_ime_freeze_guard=1 AND a CarPlay session is live:
 *  - temporarily add Gboard's *exact package* to the OEM setting;
 *  - ask the OEM's exported Mipush whitelist receiver to thaw the UID;
 *  - restore the previous setting at ordinary session teardown.
 *
 * The setting is shared with Xiaomi game predownload. Preserve other entries,
 * never overwrite a third party's full list on teardown, and never disable
 * Greezer globally. This is opt-in because an abrupt system_server reboot
 * cannot guarantee teardown/cleanup. See V43_TEST_PLAN.md.
 */
object V43ImeFreezeGuard {
    private const val TAG = "AAD_V43ImeFreezeGuard"
    private const val PROP = "debug.carplay.v43_ime_freeze_guard"
    private const val PKG = "com.google.android.inputmethod.latin"
    private const val OEM_LIST = "com.miui.game.allowlist"
    private val main = Handler(Looper.getMainLooper())

    private var sessionLive = false
    private var ownedEntry = false
    private var originalValue: String? = null
    private var writtenValue: String? = null
    private var lastThawMs = 0L

    private fun enabled(): Boolean = runCatching {
        val p = Class.forName("android.os.SystemProperties")
        val m = p.getMethod("get", String::class.java, String::class.java)
        (m.invoke(null, PROP, "0") as? String) == "1"
    }.getOrDefault(false)

    private fun entries(value: String?): List<String> =
        value.orEmpty().split("_").filter { it.isNotBlank() }

    fun onCarPlaySession(context: Context, live: Boolean) {
        // Binder callbacks may be on non-main threads. Serialize list updates
        // and cleanup; do not hold any CoreManagerService or WM locks.
        main.post {
            if (live) {
                val start = !sessionLive
                sessionLive = true
                if (enabled()) {
                    if (start || !ownedEntry) applyGuard(context)
                    else requestThaw(context)
                } else if (start) {
                    log(TAG, "v43 guard OFF by default (no OEM setting changed)")
                }
            } else {
                sessionLive = false
                restore(context)
            }
        }
    }

    private fun applyGuard(context: Context) {
        try {
            val old = Settings.System.getString(context.contentResolver, OEM_LIST)
            if (PKG in entries(old)) {
                // User or another component already owns the exemption; never
                // remove it later.
                log(TAG, "v43 guard existing allowlist entry; no write")
                requestThaw(context)
                return
            }
            val newValue = (entries(old) + PKG).joinToString("_")
            val ok = Settings.System.putString(context.contentResolver, OEM_LIST, newValue)
            if (!ok) {
                log(TAG, "v43 guard could not update OEM allowlist")
                return
            }
            originalValue = old
            writtenValue = newValue
            ownedEntry = true
            log(TAG, "v43 guard applied CarPlay-only Gboard exemption; previousNull=" +
                (old == null) + " otherEntries=" + entries(old).size)
            requestThaw(context)
        } catch (t: Throwable) {
            log(TAG, "v43 guard apply failure", t)
        }
    }

    private fun requestThaw(context: Context) {
        val now = SystemClock.uptimeMillis()
        if (now - lastThawMs < 15_000L) return
        lastThawMs = now
        try {
            // On independently studied Xiaomi HyperOS builds, option=-1 asks
            // updateMipushProtectAppList() to thaw the UID without modifying
            // MiPush protect list membership. It is not a public stable API.
            val intent = Intent("com.xiaomi.mipush.REFRESH_WHITE_LIST_ACTION")
                .setPackage("android")
                .putExtra("pkgName", PKG)
                .putExtra("option", -1)
            context.sendBroadcastAsUser(intent, Process.myUserHandle())
            log(TAG, "v43 requested OEM Gboard thaw (broadcast sent; effect unverified)")
        } catch (t: Throwable) {
            log(TAG, "v43 OEM thaw broadcast failed", t)
        }
    }

    private fun restore(context: Context) {
        if (!ownedEntry) return
        try {
            val current = Settings.System.getString(context.contentResolver, OEM_LIST)
            val result: String? = if (current == writtenValue) {
                // Exact original restoration (including null/empty).
                originalValue
            } else {
                // A Xiaomi writer changed the list while CarPlay was active:
                // remove ONLY our package, preserving other entries.
                entries(current).filterNot { it == PKG }.joinToString("_")
            }
            val ok = Settings.System.putString(context.contentResolver, OEM_LIST, result)
            if (ok) {
                log(TAG, "v43 guard restored allowlist after CarPlay session")
                ownedEntry = false
                originalValue = null
                writtenValue = null
            } else {
                log(TAG, "v43 guard restore failed; manual cleanup may be needed")
            }
        } catch (t: Throwable) {
            log(TAG, "v43 guard restore exception; manual cleanup may be needed", t)
        }
    }
}
'''
p = ROOT / "xposed/hook/V43ImeFreezeGuard.kt"
if p.exists():
    raise AssertionError("v43 helper already exists")
p.write_text(src, encoding="utf-8")

core = ROOT / "xposed/CoreManagerService.kt"
s = core.read_text(encoding="utf-8")
# Import beside another hook import to avoid duplicate import declarations.
s = replace_once(
    s,
    "import io.github.nitsuya.aa.display.xposed.hook.VdImeDisplayPin",
    "import io.github.nitsuya.aa.display.xposed.hook.VdImeDisplayPin\nimport io.github.nitsuya.aa.display.xposed.hook.V43ImeFreezeGuard",
    "guard import",
)
s = replace_once(
    s,
    """        mSessionPolicy?.onSecondaryEgressLiveChanged(live)
        runCatching { CarPlayProcessBoost.setBoost(live) }""",
    """        mSessionPolicy?.onSecondaryEgressLiveChanged(live)
        // v43 opt-in, CarPlay-session-only Xiaomi Greezer IME workaround.
        // On false, restore any OEM list entry added by this guard.
        runCatching { V43ImeFreezeGuard.onCarPlaySession(systemContext, live) }
            .onFailure { log(TAG, "v43 IME freezer guard dispatch failed", it) }
        runCatching { CarPlayProcessBoost.setBoost(live) }""",
    "CarPlay lifecycle guard",
)
core.write_text(s, encoding="utf-8")

gradle = Path("aa-display/build.gradle.kts")
v = gradle.read_text(encoding="utf-8")
v = replace_once(v, "versionCode = 3142", "versionCode = 3143", "version code")
v = replace_once(v, 'versionName = "0.3#17.8-v42"',
                 'versionName = "0.3#17.8-v43"', "version name")
gradle.write_text(v, encoding="utf-8")

print("v43: opt-in Gboard OEM Greezer guard + targeted thaw, cleanup on session end")

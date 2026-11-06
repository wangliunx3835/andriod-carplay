package io.github.nitsuya.aa.display.carplay

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.widget.Button
import android.widget.LinearLayout
import io.github.nitsuya.aa.display.CoreApi

/** Separate transport and sound targets; never changes non-SmartBox sessions. */
internal class SmartBoxV70Audio(private val context: Context) {
    private val handler = Handler(Looper.getMainLooper())
    @Volatile private var box: String? = null
    @Volatile private var active = false
    private var attempts = 0
    private var selectedTarget = ""
    private val tick = object : Runnable {
        override fun run() {
            val peer = box ?: return
            if (!active) return
            val target = selectedTarget
            if (target.isNotBlank() && !target.equals(peer, true)) {
                runCatching { CoreApi.smartBoxAudioRoute(peer, target, attempts < 3) }
                    .onFailure { Log.w(CarPlayConsts.TAG, "v70 audio route requires module reboot", it) }
                attempts++
            }
            handler.postDelayed(this, 3000)
        }
    }
    fun notePeer(name: String?, address: String?) {
        if (address.isNullOrBlank()) return
        if (!SmartBoxV69DialPolicy.matches(name)) return
        if (box == address && active) return
        stop()
        box = address
        active = true
        attempts = 0
        selectedTarget = context.getSharedPreferences("carplay_media_overlay_v52", Context.MODE_PRIVATE).getString(KEY, "").orEmpty()
        handler.post(tick)
    }
    fun enabled(): Boolean = active && box != null &&
        selectedTarget.isNotBlank() && !selectedTarget.equals(box, true)
    fun stop() {
        active = false
        handler.removeCallbacks(tick)
        val old = box
        box = null
        if (old != null) runCatching { CoreApi.smartBoxAudioRoute(old, "", false) }
    }
    companion object {
        private const val KEY = "aadisplay_smartbox_audio_target_v70"
        @SuppressLint("MissingPermission")
        fun addSettings(activity: Activity, panel: LinearLayout) {
            panel.addView(Button(activity).apply {
                text = "SmartBox 双蓝牙音频（重连后生效）"
                setOnClickListener {
                    val devices = runCatching {
                        activity.getSystemService(BluetoothManager::class.java).adapter.bondedDevices
                            .filter { !SmartBoxV69DialPolicy.matches(it.name) &&
                                it.bluetoothClass?.majorDeviceClass == android.bluetooth.BluetoothClass.Device.Major.AUDIO_VIDEO }
                            .sortedBy { it.name ?: it.address }
                    }.getOrDefault(emptyList())
                    val labels = listOf("关闭旁路，保持原音频方式") + devices.map { "${it.name} (${it.address.takeLast(5)})" }
                    AlertDialog.Builder(activity).setTitle("选择原车音响，勿选耳机")
                        .setItems(labels.toTypedArray()) { _, which ->
                            val address = if (which == 0) "" else devices[which - 1].address
                            runCatching { activity.getSharedPreferences("carplay_media_overlay_v52", Context.MODE_PRIVATE).edit().putString(KEY, address).apply() }
                                .onFailure { android.widget.Toast.makeText(activity, "保存失败，请确认模块已激活", 1).show() }
                        }
                        .setNeutralButton("配对原车蓝牙") { _, _ ->
                            activity.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                        }.setNegativeButton("取消", null).show()
                }
            })
        }
    }
}

package io.github.nitsuya.aa.display.xposed.carplay

import android.annotation.SuppressLint
import android.bluetooth.BluetoothA2dp
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log

/** System capability only: targeted A2DP connect plus expiring capture bypass. */
internal object SmartBoxV70SystemAudio {
    private val handler = Handler(Looper.getMainLooper())
    @Volatile private var expires = 0L
    private val release = Runnable {
        if (SystemClock.elapsedRealtime() >= expires) {
            expires = 0L
            // Resume only if the source session still wants audio capture.
            CarPlayAudioCapture.setEnabled(CarPlayAudioCapture.isDesired())
        }
    }
    fun bypass(): Boolean = SystemClock.elapsedRealtime() < expires
    @SuppressLint("MissingPermission")
    fun route(context: Context, box: String, target: String, connect: Boolean): Boolean {
        val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter ?: return false
        val peers = adapter.bondedDevices
        val transport = peers.firstOrNull { it.address.equals(box, true) } ?: return false
        if (transport.name?.trim()?.startsWith("smartbox", true) != true) return false
        if (target.isEmpty()) {
            expires = 0L
            handler.removeCallbacks(release)
            CarPlayAudioCapture.setEnabled(CarPlayAudioCapture.isDesired())
            return true
        }
        val audio = peers.firstOrNull { it.address.equals(target, true) && it.address != transport.address }
            ?: return false
        val am = context.getSystemService(AudioManager::class.java)
        val routed = am.isBluetoothA2dpOn && am.getDevices(AudioManager.GET_DEVICES_OUTPUTS).any {
            it.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP && it.address.equals(target, true)
        }
        if (routed) {
            expires = SystemClock.elapsedRealtime() + 10000L
            handler.removeCallbacks(release)
            handler.postDelayed(release, 10000L)
            CarPlayAudioCapture.setEnabled(CarPlayAudioCapture.isDesired())
        } else if (bypass()) {
            expires = 0L
            handler.removeCallbacks(release)
            CarPlayAudioCapture.setEnabled(CarPlayAudioCapture.isDesired())
        }
        if (connect && !routed) handler.post {
            adapter.getProfileProxy(context, object : BluetoothProfile.ServiceListener {
                override fun onServiceConnected(profile: Int, proxy: BluetoothProfile) {
                    try {
                        proxy.javaClass.getMethod("connect", android.bluetooth.BluetoothDevice::class.java)
                            .invoke(proxy, audio)
                        Log.i("AAD_CarPlay", "v70 requested selected car A2DP connection")
                    } catch (e: Throwable) {
                        Log.w("AAD_CarPlay", "v70 A2DP connect failed; pair/connect car audio in Settings", e)
                    } finally { adapter.closeProfileProxy(profile, proxy) }
                }
                override fun onServiceDisconnected(profile: Int) {}
            }, BluetoothProfile.A2DP)
        }
        return routed
    }
}

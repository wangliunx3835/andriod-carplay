    private val accessoryUuid: UUID = UUID.fromString(CarPlayConsts.IAP2_ACCESSORY_RFCOMM_UUID)
    private val v69Policy = SmartBoxV69DialPolicy()
    private val v69Services = java.util.concurrent.ConcurrentHashMap<String,Set<UUID>>()

    @SuppressLint("MissingPermission")
    private fun v69CanDial(device: BluetoothDevice): Boolean {
        val cached = v69Services[device.address] ?: device.uuids?.map { it.uuid }?.toSet()
        val decision = v69Policy.evaluate(device.name,device.address,SystemClock.elapsedRealtime(),
            device.bondState == BluetoothDevice.BOND_BONDED,
            clientSocket?.isConnected == true || sessionLive() || mediaActive(),
            cached?.contains(accessoryUuid) == true) ?: return false
        if (decision.discover) {
            // SDP only; never brute force channels or switch the protocol identity.
            val requested = runCatching { device.fetchUuidsWithSdp() }.getOrDefault(false)
            Log.i(CarPlayConsts.TAG,"v69 SmartBox policy="+decision.reason+
                " name="+device.name+" SDP-requested="+requested+
                " cachedUUIDs="+cached+" listen=cafe,caff,wcp")
        }
        return decision.dial
    }

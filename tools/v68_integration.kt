        if (v68Session) {
            val state = CarPlayV68ScreenState()
            val busy = AtomicBoolean(false)
            var failures = 0
            val retryAfter = AtomicLong(0L)
            fun owns() = eventChannel.get()?.isPhoneOwningMainScreen() == true
            v68Action.set action@ { force ->
                if (!v68Live() || android.os.SystemClock.elapsedRealtime() < retryAfter.get() ||
                    !busy.compareAndSet(false,true)) return@action
                try {
                    v68Executor.execute {
                        val ownerAtStart = owns()
                        try {
                            val ok = state.reconcile(::v68Live, ::owns, force,
                                pauseAndClose = {
                                    v58VideoUnusable.set(true)
                                    v57VideoQueue.dropUntilIdr("v68-release")
                                    screenEgress.getAndSet(null)?.close()
                                },
                                teardown = teardown@ {
                                    val uuid = accessoryDisplayUuid?.takeIf { it.isNotBlank() }
                                        ?: return@teardown false
                                    val body = BinaryPlist.encode(mapOf("streams" to listOf(
                                        mapOf("type" to 110,"uuid" to uuid))))
                                    val reply = exchangeEncrypted(RtspMessage(
                                        "TEARDOWN $sessionUrl RTSP/1.0",
                                        headers(mapOf("Content-Type" to "application/x-apple-binary-plist",
                                            "Content-Length" to body.size.toString())),body))
                                    Log.i(CarPlayConsts.TAG,"v68 screen TEARDOWN status="+reply?.firstLine)
                                    reply?.firstLine?.contains("200") == true
                                },
                                publishModes = {
                                    val modes = eventChannel.get()?.currentModesParams()
                                    modes != null && postControlCommand(
                                        mapOf("type" to "modesChanged","params" to modes),"v68-screen-state")
                                },
                                setup = { v58ReopenScreen.get()?.invoke() == true },
                                resume = {
                                    v57VideoQueue.dropUntilIdr("v68-resume")
                                    v58VideoUnusable.set(false)
                                    onForceKeyFrame()
                                })
                            if (!ok && v68Live()) {
                                failures++
                                retryAfter.set(if (failures>=3) Long.MAX_VALUE else
                                    android.os.SystemClock.elapsedRealtime()+(1000L shl (failures-1)))
                            } else if (ok) { failures=0; retryAfter.set(0L) }
                            Log.i(CarPlayConsts.TAG,"v68 screen phase="+state.phase+
                                " owner="+owns()+" ok="+ok+" failures="+failures)
                        } catch (e: Throwable) {
                            retryAfter.set(Long.MAX_VALUE)
                            Log.e(CarPlayConsts.TAG,"v68 screen transition stopped",e)
                        } finally {
                            busy.set(false)
                            if (v68Live() && ownerAtStart != owns()) v68Action.get()?.invoke(false)
                        }
                    }
                } catch (_: java.util.concurrent.RejectedExecutionException) { busy.set(false) }
            }
        }

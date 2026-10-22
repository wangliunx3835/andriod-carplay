from pathlib import Path
root=Path('aa-display/src/main/java/io/github/nitsuya/aa/display/carplay')
p=root/'protocol/Iap2Session.kt'
s=p.read_text()
needle='''        if (packet.hasSyn) {
            handleSynLocked(packet)
            return
        }'''
replace='''        if (packet.hasSyn) {
            // After link-ready, peer SYN|ACK retransmits must be ACKed, not renegotiated.
            if (linkReady) {
                peerSeq = packet.seq
                if (packet.hasAck) trackPeerAckLocked(packet.ack)
                sendLinkLocked(CONTROL_ACK, sessionId = 0, payload = ByteArray(0))
                Log.i(CarPlayConsts.TAG,
                    "v3 iAP duplicate SYN acknowledged seq=${packet.seq} ack=${packet.ack} state=$state")
            } else {
                handleSynLocked(packet)
            }
            return
        }'''
assert s.count(needle)==1
s=s.replace(needle,replace)
needle='''        if (packet.hasAck) {
            markLinkReadyLocked("syn-ack")
        } else if (negotiated === lsp) {'''
replace='''        if (packet.hasAck) {
            // Explicit ACK before control-session identification.
            peerSeq = packet.seq
            trackPeerAckLocked(packet.ack)
            sendLinkLocked(CONTROL_ACK, sessionId = 0, payload = ByteArray(0))
            Log.i(CarPlayConsts.TAG, "v3 iAP SYN|ACK accepted and ACK sent peerSeq=$peerSeq")
            markLinkReadyLocked("syn-ack")
        } else if (negotiated === lsp) {'''
assert s.count(needle)==1
s=s.replace(needle,replace)
p.write_text(s)
p=Path('aa-display/build.gradle.kts')
s=p.read_text()
assert 'versionCode = 3102' in s
s=s.replace('versionCode = 3102','versionCode = 3103').replace('versionName = "0.3#17.8-r2"','versionName = "0.3#17.8-v3"')
p.write_text(s)
print('v3 patch applied')

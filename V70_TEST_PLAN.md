# v70 SmartBox 双蓝牙适配（待实车验证）

基于 v69 e5f1919。所有新握手/音频逻辑仅在已连接蓝牙名称以 smartBox 开头（不区分大小写）时启用。CarLetter/MIB3/DiPlay 保留 v69 默认路径。

- 手机设置页 → 悬浮媒体设置 → SmartBox 双蓝牙音频：选择已配对原车音响。默认关闭旁路；多个候选不自动猜选。设置在下一次 SmartBox 连接时读取。
- 视频/触摸仍经盒子 Wi-Fi；声音通过原车 A2DP。尝试连接只限选定设备，至多 3 次，不改变其他设备配对和自动连接策略。
- 仅确认蓝牙 A2DP 输出可用时解除采集/静音；音频旁路续租失效最多 10 秒后恢复原有采集机制。没有连上目标音响时不会主动释放手机静音。
- SmartBox 的 RECORD 成功后发送 disableBluetooth；不关闭手机蓝牙总开关。保留已有事件 iAP2 和 v7/v29/v31 蓝牙交接保护，不新增 type-130 隧道。
- 新 AIDL 方法仅追加在末尾；安装后需重启手机，使 system_server 加载一致版本。

验证：CarLetter、DiPlay、MIB3 各自进行原路径连接/音频/断开恢复；SmartBox 旁路开/关、原车音响缺席、两个音响候选、A2DP 中断、应用退出；验证没有重复 AirPlay 音频、手机漏音和遗留静音。当前没有硬件实测，不能承诺无回归。

Linux/CarLetter 仍先补日志，运行 tools/carplay_bt_connect_capture_v2.sh；connection.txt 独立保留协议和蓝牙关键标签，完整 logcat 另行轮转，避免图形刷屏覆盖握手。脚本不修改连接设置、不清空日志。

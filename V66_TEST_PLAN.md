# v66 测试版（3166）

修正 Audio 被误判 Audi；CarLetter 明确保留已连通的 MIB3 兼容协议，型号仍未知。CarLetter 启动移除串行 900ms/1200ms 前置等待，Timing/Event 服务继续运行。视频连接建立后非阻塞启动 Wi-Fi iAP2 detect，沿用现有控制通道。长倒车不再无条件触发视频连接重建；失效/堵塞重建仍保留。修正 SETUP ID 诊断日志。

覆盖安装后重启手机。请分别测试三次首次连接，倒车 5 秒、15 秒、30 秒以及车机主页返回。记录首次出画耗时、黑屏持续时间与声音是否连续。日志应出现 carletter、Wi-Fi iAP2 detect sent；核对后续 SYN/认证是否完成。健康视频 socket 不应仅因 longCamera=true 而重建。

这是一版待真机验证的修复，不能视为黑屏已解决。保留 v23 IPv4、v29 单会话、v31 Event 分流、v38–40 连续发送与无空 TCP 探测、输入法和音频修复。

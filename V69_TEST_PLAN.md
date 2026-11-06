# v69 SmartBox 蓝牙连接策略适配测试版（3169）

仅匹配去除首尾空白后 smartBox 前缀，不区分大小写，不限定后缀或 MAC。没有将 SmartBox 加入 MIB3/CarLetter 配置；iAP、AirPlay、音视频与 v68 相同。CarLetter 屏幕生命周期修复继续保留。

SmartBox 策略：已配对且没有现有 RFCOMM/iAP/AirPlay 会话时查询 SDP，给盒子至少 5 秒回连机会。发现 accessory caff 服务后才允许主动连接，失败拨号和 SDP 查询各至少间隔 30 秒。不猜 RFCOMM 数字通道，不重命名手机，不删配对、不切换盒子 CP/AA 模式。SmartBox 入站也不能抢占其他连接或正在运行的投屏。非 SmartBox 原连接分支保持原样。

增加十项 SmartBox 策略测试，连同 v68 九项测试一起运行。覆盖安装后重启手机。先验证现有 Car Audio_457f 连接正常，再断开该会话，仅给 SmartBox 供电并配对，抓取 60–90 秒日志。重点 v69 SmartBox policy、SDP UUIDs、caff/cafe、RFCOMM peer 和后续 iAP。测试时关闭其他可能自动连接盒子的手机蓝牙/Wi-Fi，使用盒子 CarPlay 模式。

这是一轮基于现有 scn=0 故障证据的连接策略适配，尚未实测证明这只 SmartBox 已连通；若仍无 caff 也无回连，日志用于确定服务广播或模式识别问题，不能直接认定 Wi-Fi 密码/音视频故障。

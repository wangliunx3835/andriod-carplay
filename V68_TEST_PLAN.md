# v68 屏幕流生命周期测试版（3168）

仅 CarLetter 配置启用：主屏转交车机后通过当前状态 modesChanged 通知，关闭旧视频连接并发送指定 type=110 + uuid 的 TEARDOWN；确认 200 后才允许返回时 SETUP。保留整个 RTSP、音频、编码器与双虚拟屏。返回经 requestUI/资源归还触发，串行确认模式再建立视频流、刷新关键帧。

依据 CatPlay 固定提交 7f5847ed11c1f75cc3ed6364088feb74996d5a6f 的 car_manager/teardown_task/transmitter_impl 时序，独立实现，未复制其代码。该实现尚未在此 CarLetter 实车验证，不代表已经证明 400 的内部原因。

新增九项纯状态机回归测试：释放确认顺序、释放失败禁止 SETUP、SETUP 拒绝、健康流不重建、SETUP 途中屏幕被借走、失效会话隔离、阻塞流恢复、模式通知失败、释放途中会话失效。启动保留 v67 等待和无主动 iAP detect；不改变 MIB3 与 DiPlay 的既有屏幕恢复路径。

覆盖安装后重启手机，停车先确认连接稳定一分钟，再测主页停留 10/30 秒与倒车 5/20 秒返回。日志重点 v68 screen TEARDOWN status、screen phase、v58-screen-resume。预期 TEARDOWN 200 在新 SETUP 前，音频持续。若三次恢复失败则停止自动尝试，重连后重新建立状态，避免 400 循环。

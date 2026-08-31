# ExecutiveHealthBridge

HealthKit iOS Bridge source for the Executive HealthOps local backend.

- 只读取成员授权的数据类型。
- 每个类型使用 `HKAnchoredObjectQuery`；后端确认后才保存 anchor。
- 使用 `HKObserverQuery` 和 background delivery 触发系统调度的自动同步，不承诺实时。
- 不在代码中保存 bridge token；复制示例创建被 Git 忽略的 `BridgeSecrets.xcconfig`。

在 Mac 上用 Xcode 打开该项目。Windows 环境不能构建或验证真实 iPhone。完整说明见 [Apple Health 接入说明](../../docs/APPLE_HEALTH_SETUP_GUIDE_ZH.md)。

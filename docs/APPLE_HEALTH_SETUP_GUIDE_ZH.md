# Apple 健康接入说明

本项目的 Apple 健康接入由 iPhone 上的 **Executive Health Bridge** 完成：

```text
Apple Watch / iPhone / 已连接 App
        ↓
Apple 健康（HealthKit）
        ↓
Executive Health Bridge（iOS）
        ↓ HTTPS
/integrations/apple-health/sync
        ↓
AppleHealthAdapter → 原始接入记录 → 标准化健康数据
```

它只是一条数据来源链路：不会自动调用 open-source LLM，也不会自行形成诊断、处方或风险阈值结论。

## A. Windows 上现在能做什么

Windows 可以启动 HealthOps 后端、查看后端接收状态、运行 Python 回归测试，并准备 Bridge 源码。Windows 不能构建 HealthKit App，也不能验证 iPhone 的授权、后台同步或设备数据。

## B. 准备条件

- Mac 与当前可用的 Xcode；
- Apple Developer Signing 环境（个人开发调试也必须可给设备签名）；
- 一台 iPhone，Health App 中至少有一项可授权数据；
- HealthOps FastAPI 服务能从 iPhone 访问；公网地址必须是 HTTPS；
- 已在后端为成员登记 `apple_health` 外部身份；
- 由安全配置提供的 `APPLE_HEALTH_BRIDGE_TOKEN`。不要把 token 提交到 Git、聊天或截图中。

## C. 在 Mac / Xcode 打开项目

1. 将项目安全地复制到 Mac。
2. 用 Xcode 打开 `ios/ExecutiveHealthBridge/ExecutiveHealthBridge.xcodeproj`。
3. 在 target 的 **Signing & Capabilities** 选择你的 Team，并改成唯一的 Bundle ID。
4. 在 **Signing & Capabilities** 添加 **HealthKit**。项目已包含 HealthKit entitlement；仍须由你的 Team 签名确认。

## D. 配置本机后端地址、成员和 token

1. 复制 `ios/ExecutiveHealthBridge/BridgeSecrets.xcconfig.example` 为同目录的 `BridgeSecrets.xcconfig`。
2. 填写：

   - `HEALTHOPS_API_BASE_URL`：例如受控 HTTPS 地址 `https://healthops.example.com`，末尾不要加 `/`；
   - `HEALTHOPS_BRIDGE_TOKEN`：与后端环境变量一致的 bridge token；
   - `HEALTHOPS_MEMBER_EXTERNAL_ID`：该成员已登记的 Apple Health 外部标识。

3. 确认这个文件不会进入 Git：项目 `.gitignore` 已忽略它。
4. `Info.plist` 中已带 HealthKit 的中文 Usage Description。若要更改文案，请保持“只同步用户授权的数据”的含义，不要承诺实时或全部权限。

## E. 启动后端

1. 在受控环境设置 `APPLE_HEALTH_BRIDGE_TOKEN`；不要把实际值写进源码或 `.env.example`。
2. 启动 FastAPI（默认 `:8000`）。
3. 确认 `GET /docs` 可访问，且 iPhone 对后端网络可达。
4. 开发时可使用受控局域网进行测试；任何公网 PHI 传输必须使用 HTTPS。不要用裸 HTTP 公网地址。

## F. 安装到 iPhone

1. 用 USB 或无线调试连接 iPhone，选择真机 target。
2. 在 iPhone 信任对应开发者签名（如系统提示）。
3. 点击 Run 安装 Executive Health Bridge。
4. 首次启动若提示本机配置未完成，检查 `BridgeSecrets.xcconfig` 是否已加入 target 配置并重建。

## G. 首次授权与同步

1. 打开 Bridge，点击 **连接 Apple 健康**。
2. iOS 会显示按类型授权界面。成员可授权或拒绝：步数、活动消耗、活动时长、心率、静息心率、睡眠、血氧、体重。
3. 授权后 Bridge 立即执行一次增量同步；后续由 `HKObserverQuery` 和 HealthKit background delivery 触发自动同步。
4. Apple 不向应用披露所有“读取权限”细节。因此页面只以“Apple 健康授权已完成”和**实际同步过的数据类型**表达状态，绝不声称已获得全部权限。
5. 也可从成员健康中心的 **个人设置 → 设备与数据 → 连接 Apple 健康** 用深链打开已安装的 Bridge。

## H. 同步内容与缺失数据

Bridge 只上传 HealthKit 实际返回的 sample：

- 步数、活动消耗、活动时长；
- 心率、静息心率；
- 睡眠分析（in bed、awake、asleep、core、deep、REM、unspecified 按原状态传递）；
- 血氧、体重。

没有的数据不会上传。睡眠 `asleepCore`、`asleepDeep`、`asleepREM` 分别保留，不会把所有睡眠误标为深睡。

## I. 如何确认平台收到数据

1. Bridge 显示“同步完成”。
2. HealthOps 后台：**更多 → 数据接入与设备**，Apple 健康卡应显示“已收到桥接同步”、最近同步时间，并分开展示：后端接收 / iOS Bridge 源码 / 真机验证。
3. 成员：**个人设置 → 设备与数据**，可看到 Apple 健康分配状态和最近成功同步。
4. 成员健康数据页可看到被现有标准化层接受的指标。重复 HealthKit UUID 不会重复创建 Observation。

## J. 修改或撤销权限、删除数据

- 在 iPhone 的 **健康 App → 头像 → App 与服务 → Executive Health Bridge** 修改或撤销授权。
- 下次 iOS 的 anchored query 会收到删除的 HealthKit sample；Bridge 将 UUID 发送给现有 sync endpoint。
- 平台保留删除审计记录，但把对应 Observation 标为来源已删除并排除新的趋势/风险分析。聚合睡眠 session 中任一原始 sleep sample 被删除时，该来源睡眠 session 也会被保守排除，避免继续使用旧数据。

## K. 常见故障

| 现象 | 排查 |
|---|---|
| 授权后没有数据 | 检查 Health App 是否已有该类型记录；授权可部分拒绝；Bridge 不会伪造数据。 |
| “尚未配置本机后端” | 检查 `BridgeSecrets.xcconfig`、Base Configuration 和重新 Build。 |
| 同步未完成 / 后端拒绝 | 检查 HTTPS 地址、iPhone 网络、`APPLE_HEALTH_BRIDGE_TOKEN` 与成员外部标识。 |
| 后台没有立即同步 | HealthKit 后台 delivery 由 iOS 调度，不承诺实时；打开 Bridge 后点“立即同步”确认。 |
| 平台显示演示同步 | 演示入口与真实 `/integrations/apple-health/sync` 分开；使用 Bridge 的 Bearer token 同步才会显示桥接同步。 |
| Xcode 签名失败 | 在 target 选择正确 Team、唯一 Bundle ID，并确认 HealthKit capability 对当前 App ID 生效。 |

## L. 验证边界

截至本说明提交时，Windows 开发环境已完成后端和 iOS 源码准备；**没有 Mac + Xcode + iPhone 的实际运行记录时，真机验证状态必须是“未验证”**。只有按上面步骤在真实设备授权、同步并在平台观察到数据后，才能将该成员标为真实桥接同步已验证。

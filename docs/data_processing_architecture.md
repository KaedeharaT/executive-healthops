# 数据处理架构

当前平台采用可演进的混合处理架构，避免把设备接入、医疗风险和本地 AI 混为一层。

## 当前处理边界

- 本地 Qwen：仅在本机通过 Ollama 辅助整理体检报告复杂原文；不决定风险、诊断、用药或处置。
- 健康平台：当前在本地/私有服务中保存原始来源、标准化 Observation、人工确认、规则风险和运营记录。
- 设备云：由未来 Provider 决定；平台接口预留 `EDGE_PROCESSING`、`CLOUD_PROVIDER_PROCESSING`、`DIRECT_DEVICE_SYNC` 三种处理模式。

## 模式

| 模式 | 典型路径 | 优点 | 边界 |
| --- | --- | --- | --- |
| EDGE_PROCESSING | 手机/设备 → 本平台 | 隐私好、响应快、敏感数据不必外发 | 设备性能与本地维护限制 |
| CLOUD_PROVIDER_PROCESSING | 设备 → 厂商云 → 本平台 | 集中维护、跨设备统一、更新方便 | 网络、合规与厂商依赖 |
| DIRECT_DEVICE_SYNC | 设备/本地桥接 → 本平台 | 数据路径清晰、可控 | 需要设备协议或桥接支持 |

长期建议为 Hybrid：对高敏感、低延迟处理优先本地/边缘；对 Provider 同步采用受治理的云端连接。所有医疗风险仍只由 `APPROVED + ACTIVE` 的确定性 RiskRule 执行。

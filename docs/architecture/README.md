# Executive HealthOps 当前架构地图

审计基准：当前 working tree 的真实代码，导航结构更新于 2026-08-30。本文档集只描述可在当前代码、迁移或本地 SQLite 审计数据中定位到的能力；不把历史设计目标当作已实现能力。

| 文档 | 用途 |
|---|---|
| [00_EXECUTIVE_OVERVIEW.md](00_EXECUTIVE_OVERVIEW.md) | 给业务负责人的一页健康运营闭环图。 |
| [01_PLATFORM_OVERVIEW.md](01_PLATFORM_OVERVIEW.md) | 产品能力、数据来源、AI 与确定性风险的总览。 |
| [02_PRODUCT_ARCHITECTURE.md](02_PRODUCT_ARCHITECTURE.md) | Streamlit 当前真实页面与入口结构。 |
| [../NAVIGATION_DEPTH_AUDIT.md](../NAVIGATION_DEPTH_AUDIT.md) | 本轮两级导航的基线、目标树与深度登记。 |
| [03_CORE_WORKFLOWS.md](03_CORE_WORKFLOWS.md) | 报告、风险、时间轴、服务、医生协同的真实流程。 |
| [04_TECHNICAL_ARCHITECTURE.md](04_TECHNICAL_ARCHITECTURE.md) | 进程、服务层、数据库、集成、部署与安全边界。 |
| [05_ARCHITECTURE_GAPS.md](05_ARCHITECTURE_GAPS.md) | 当前状态与目标之间的缺口、重复与架构债务。 |

## 统一图例

- ✅ **CURRENT**：当前代码中可调用，且有对应模型、服务或路由。
- 🟡 **PARTIAL**：有模型或流程基础，但受人工、实现范围或入口限制。
- 🧪 **TEST / DEMO**：仅合成数据、模拟适配器或演示工作流。
- ❌ **NOT IMPLEMENTED**：当前代码未发现可用实现。

所有 Mermaid 图采用这个状态含义；状态并不等同于生产就绪或医学有效性。

# Portfolio 截图清单

当前执行环境没有可用的浏览器截图运行时，因此未生成或伪造截图。请在 `PORTFOLIO_DEMO=true`、`Demo Executive A` 和 1440px 宽度下手动截取；截图前确认浏览器、文件路径和本地环境信息不可见。

| 文件名 | 页面 | 必须展示 | 必须隐藏 |
|---|---|---|---|
| `01_member_home.png` | 成员健康中心 → 首页 | 当前状态、关键数据、下一步 | 内部对象名、调试信息 |
| `02_report_summary.png` | 健康 → 体检 | 2024年度综合体检报告（演示）、主要发现、异常指标 | 原始上传文件、真实医院/成员信息 |
| `03_report_evidence.png` | 体检报告 → 查看依据 | LDL-C 或胸部 CT 的页码、区块、原始片段 | UUID、技术 metadata |
| `04_health_data.png` | 健康 → 健康数据 | 睡眠、活动、血压/血糖趋势 | unknown/None/原始 provider code |
| `05_health_timeline.png` | 成员健康中心 → 历程 | 趋势、期间总结、生命轴和 Inspector | synthetic/test 名称 |
| `06_manager_workbench.png` | 运营后台 → 今日 | Demo Executive A、优先工作项、下一步 | rule code、RiskEvent ID |
| `07_doctor_review.png` | 医疗协同 → 内部医生 | 人工复核问题、资料、意见区 | OPEN/doctor/raw enum |
| `08_knowledge_center.png` | 更多 → 知识库 | 搜索、来源、已保存、待审核 | raw JSON、provider endpoint |
| `09_service_center.png` | 成员健康中心 → 服务 | 服务分类、申请状态 | 内部服务请求 ID |
| `10_architecture.png` | README 或 docs/architecture/00_EXECUTIVE_OVERVIEW.md | 产品总图 | 数据库路径、凭证 |

截图复核：文字不溢出；所有风险颜色仅用于正式风险；“演示风险”明显；未出现真实 PHI、token、`.db` 路径或原始报告文件名。

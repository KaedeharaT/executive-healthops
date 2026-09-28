# Phase 1A 验收记录

日期：2026-09-29。开始 HEAD：`2e28cb7`。备份分支：`backup/pre-ai-native-phase1a`。没有 push。

## 业务结果

| 场景 | 统一事件 | 长期身份 | Goal / 数据结果 |
|---|---|---|---|
| A：Chromium 上传健康资料 | 1 个 MANUAL / HEALTH_DOCUMENT_UPLOADED | 原身份，唤醒 1 次；IDLE → RUNNING → WAITING_MANAGER | 原 Profile Intake 创建 1 个 Goal；运行时不新增人工待办，等待健管后进入 Today |
| B：Chromium 医生提交 | 1 个 SYSTEM / DOCTOR_REVIEW_COMPLETED | 原身份，累计唤醒 2 次（报告 + 医生回复） | RESUME_CURRENT_GOAL；原体检后 Goal 不变，总 Goal 数仍为 1 |
| C：合成血压设备 | 50 个 DEVICE_RAW_MEASUREMENT + 1 个规则变化事件 | 原始测量唤醒 0 次；规则变化唤醒 1 次 | 50 个 Observation；0 个新 Goal、Task、正式 Risk |
| 重复投递 / 并发 | 同来源事实只有 1 条事件 | 并发 8 次调用仍只有 1 个身份、1 次唤醒 | 新幂等键也不能绕过来源唯一约束 |
| 重启 | 已处理事件不回放 | 身份、等待状态、唤醒次数不变 | 未来到期事件保留，未到时间不唤醒 |

真实 Chromium 151.0.7922.34，1440×900，从普通首页真实点击；未使用内部详情 URL。医生意见整理实际复用了原本地 AI；问卷按结构化映射处理。普通界面显示中文来源，没有新增技术事件菜单。

## 页面证据

- [上传前](../images/ai-native-phase1a/01-before-upload.png)
- [资料事件触发运行](../images/ai-native-phase1a/02-document-trigger.png)
- [等待健管，spinner 停止](../images/ai-native-phase1a/03-intake-waiting-manager.png)
- [Today 人工工作](../images/ai-native-phase1a/04-today-human-work.png)
- [医生原事项](../images/ai-native-phase1a/05-doctor-original-goal.png)
- [医生提交](../images/ai-native-phase1a/06-doctor-submitted.png)
- [医生返回 Today](../images/ai-native-phase1a/07-doctor-returned-today.png)
- [恢复原 Goal，显示系统结果触发](../images/ai-native-phase1a/08-resumed-same-goal.png)
- [管理员复用同一资料面板](../images/ai-native-phase1a/09-admin-shared-panel.png)

持久化核对：[浏览器流程](../images/ai-native-phase1a/browser-evidence.json)、[设备规则](../images/ai-native-phase1a/device-evidence.json)、[重启](../images/ai-native-phase1a/restart-evidence.json)。全部业务截图使用独立合成数据库。

## 数据与事务

正式 Demo 没有删除或重建。迁移前备份 `.runtime/ai-native-phase1a/pre-migration.db`。迁移后会员 10、方案 11、既有健康事件 12、Observation 5678、医生复核 1、Goal 14、Task 15，与迁移前一致。新增 1 个长期身份，对应已有未归档管理会员。

迁移副本升级 / 降级 / 再升级均成功，12 条既有健康事件的全部旧字段一致。运行时校验了 AI 请求期间另一数据库连接能够提交写入，且取消后过期 AI 结果不能恢复流程。

正式 Streamlit 8501、FastAPI 8000 已重启并返回 HTTP 200；浏览器首页正常；现有 worker 正常运行，重启后没有新增错误日志。

## 回归修复

本轮保持归档事件重放的历史时间不变，无关医生事件安全忽略，未确认医生结果不会消耗幂等键。管理员资料看板遗留的已删除样式函数调用已移除，仍复用统一面板；对应测试去掉失效 mock，保留同 Goal / 同 renderer 断言。

## 复现入口

首次准备独立 QA 数据：`python scripts/qa_ai_native_phase1a.py --prepare`，数据库已存在时会拒绝覆盖。使用现有 `service_processes.py` 启动隔离的 platform 实例，设置 `DATABASE_URL` 为 `.runtime/ai-native-phase1a/browser.db`，API 18600、UI 18601、`PORTFOLIO_DEMO=true`。运行 `python scripts/qa_ai_native_phase1a.py`。不需要更换 LLM 配置。

设备、幂等、唯一性、到期与事务边界回归：`python -m pytest -q tests/test_health_event_runtime.py`。全量回归：`python -m pytest -q`。

最终结果：全量 **942 passed / 0 failed**。随后补充冷启动注册校验，并在最终代码运行事件层、归档、体检后流程、UI 去重定向回归：**76 passed / 0 failed**。两组结果有重叠，不相加。冷启动场景还通过独立 Python 进程验证，无需先导入上传入口，确认已有 Goal 即可同步 MemberAgent 状态。

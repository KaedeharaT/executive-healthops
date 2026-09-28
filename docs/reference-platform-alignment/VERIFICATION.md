# V6 服务业务对齐验收

## 起点与范围

- 起始提交：94597cd；备份：backup/pre-service-operations-alignment。
- 独立原提交工作树的基线：**858 passed / 0 failed**（536.42 秒）。
- 审计 27 项：ADOPT 8、ALREADY_STRONGER 9、PARTIAL 3、NOT_NOW 5、NOT_APPLICABLE 2。分类含义见 MAPPING.md，不代表对未接入参考平台的实测评价。
- 无新业务表或迁移，无第二套会员、Agent、档案、预约、LLM 或医生详情。经理导航为六个不同工作视角，Member360 保持五个 Tab。

## 本轮实际修复

1. 申请服务继承已有方案、阶段和责任健管；原始服务 ID 贯穿今日、会员、全局服务台。
2. 服务执行台使用六个交付状态，显示来源方案、责任、时间及真正下一步；结果确认与后续回访沿用 Task / ManagementLog。
3. 完成服务产生现有管理日志，保留结果、执行方、依据，并创建有方案归属的人工结果确认任务。重复提交不重复写结果日志或消耗权益。
4. 服务回访链持续有未完成任务时仍显示待回访。
5. 医生返回和阶段结果任务继承方案责任健管；仅与本次医生复核关联的初评才生成初评交接，避免无关年度/初评重复待办。
6. 阶段交接不能排在尚未处理的医生返回工作前面；未处理完阶段事项仍禁止进入下一阶段。
7. 复盘草稿保留服务执行、管理日志、会员沟通、真实指标依据、已确认医生意见及未解决事项，仍由健管确认。
8. 初评未开始、已提交、待基线、待方案均有明确下一步；今日的新会员资料入口直达既有 Agent 与例外处理工作区。阶段核心事项提前完成后也可进入今日复盘队列。
9. 专项管理从已有 OutcomeEvaluation 展示记录日期、起点、当前、目标、任务进度和责任；不推测缺失目标，也不把任务完成当健康改善。
10. 管理员组织与人员仅展示现有责任记录，明确当前并非生产 IAM / 多机构 RBAC。

## Chromium 完整故事

Chromium **151.0.7922.34**。浏览器插件没有可连接浏览器，使用本地安装的 Chromium + Playwright。所有业务操作从页面入口开始，未注入 session state、未调用内部 URL 或 API 代替点击。

可变更的故事仅在 `.runtime/service-operations/qa.db` 的合成数据库、端口 18587 运行。预置内容只有数据库结构和一个合成服务目录项。会员、评估、方案、服务与医生判断均由实际页面操作建立。

1. 健管首页 → 会员入组 → **Demo Executive A / V6责任健管**。
2. 上传一份合成结构化问卷 → 同一 Agent 整理 → 自动预填 **26 项**，健管补录 **5 项本人明确未知的回答**。可选资料继续未知，不填写虚构“无”。结构化输入没有 LLM 或知识检索，页面如实显示未使用。
3. 处理例外 → 一次提交初评 → 健管初评确认。
4. 通过已有年度基线能力保存人工草稿并确认；未将缺失疾病、用药资料补为事实。
5. 建立第一阶段 → 启动年度方案 → 创建睡眠记录任务 → 记录处理结果。
6. 从阶段申请服务 → 审核 → 预约 → 开始执行 → 填写结果与完成依据 → 结果回访确认。
7. 记录合成体重结果 **90 → 85.8 kg**、已确认目标 **83 kg**；只是合成观察数据，不证明服务因果效果。
8. 完成相关事项 → 核对阶段草稿 → 提交医学问题 → 医生端人工判断并提交。
9. 健管处理医生返回事项 → 确认下一阶段 → 页面直接出现“确认下一阶段执行安排”。
10. 服务台显示已完成；专项表选择记录回到同一个会员、同一方案；管理员可查看组织责任边界。

数据库只读复核：**1 个会员、1 份年度方案、1 个已完成阶段 + 1 个活动阶段、1 个已完成服务、1 条服务结果日志、1 个已确认 DoctorReview、1 个已完成资料 Agent、0 个新 Risk**。

以上是完整故事完成时的快照。最后在 18588 冷启动实例继续验证两条入口：完成下一阶段核心任务后，今日工作立即出现阶段复盘；另外从 UI 入组一位独立的“V6入口验证会员（合成）”，从今日工作进入同一健康档案 Agent 上传与例外处理工作区，不打开 11 步目录。对应 [提前复盘](../images/service-operations-alignment/21-early-phase-review-in-today.png)、[今日资料入口](../images/service-operations-alignment/22-today-to-agent-not-wizard.png)。这位入口测试会员与 Demo Executive A 是两个明确不同的合成人物，不是重复模型或重复建档。

截图：[01 首页](../images/service-operations-alignment/01-manager-home.png)、[03 Agent](../images/service-operations-alignment/03-agent-and-exceptions.png)、[08 基线](../images/service-operations-alignment/08-confirmed-baseline.png)、[11 预约](../images/service-operations-alignment/11-appointment.png)、[12 结果](../images/service-operations-alignment/12-service-result-writeback.png)、[13 复盘](../images/service-operations-alignment/13-stage-review.png)、[15 医生提交](../images/service-operations-alignment/15-doctor-submitted.png)、[16 下一阶段](../images/service-operations-alignment/16-next-phase.png)、[17 服务台](../images/service-operations-alignment/17-service-operations.png)、[18 专项](../images/service-operations-alignment/18-special-progress.png)。

## 本机现有平台

确认无 RUNNING Agent 后重启现有服务组；8501 Streamlit、8000 FastAPI 与原 Agent worker 保留。本地模型配置未更换。

从 8501 正常入口逐角色只读检查：健管六个工作区、Member360 五个 Tab、医生待判断与历史、成员五页、管理员四页。**全部 PASS，0 个 Streamlit 页面异常**。现有本机资料截图只保存在忽略目录 `.runtime/service-operations/live-smoke/`，不写入仓库；仓库中保留的本轮截图全部来自上述合成会员。

部署限制：最后两条今日工作路径修改后，再次重启本机整组服务被自动审批拒绝（仅返回 `blocked by policy`，没有更具体理由）。未通过其它方式强行停止本机服务。8501 继续运行上次已加载版本，最后两条路径以 18588 冷启动实例验收为准；8501 需在允许重启后加载这些最终改动。

## 测试与复现

业务定向验证已通过 **60 项**；最终全量运行 **878 passed / 0 failed**（513.34 秒）。随后新增“提前完成阶段进入今日工作”测试，并对最后两条入口及影响到的工作队列、管理、导航进行冷启动补测：**71 passed / 0 failed**（38.76 秒）。71 项包含 70 项重复验证及 1 项新增回归，当前共有 **879 个不同测试已验证通过**，没有把重复测试累加为新的用例数量。

开发中的首次运行与代码编辑重叠，出现旧模块缓存 / 新导航断言不一致；独立快照基线和最终冷启动回归分别验证，不能把开发中的失败记成已通过。

```powershell
.venv/Scripts/python.exe scripts/qa_service_operations.py --prepare
.venv/Scripts/python.exe scripts/service_processes.py start --instance service-v6 --profile qa --manifest .runtime/service-operations/manifest.json
.venv/Scripts/python.exe scripts/qa_service_operations.py --enroll
.venv/Scripts/python.exe scripts/qa_service_operations.py --review
.venv/Scripts/python.exe scripts/qa_service_operations.py --baseline
.venv/Scripts/python.exe scripts/qa_service_operations.py --execute
.venv/Scripts/python.exe -m pytest -q
```

`--prepare` 拒绝覆盖已有 QA 数据库；复测需使用新的隔离路径。过程中的 `--handoff / --doctor / --finish` 为中断后的可见页面续验，不修改数据库跳过关卡。

本轮不新增商城、支付、积分、分润或聊天。生产多机构、真实设备连接、身份鉴权依然是 Mapping 中明确的局限。**Push: NO**。

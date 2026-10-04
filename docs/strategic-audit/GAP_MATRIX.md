# HealthOps Strategic Gap Matrix

审计基线：`bf1b0558425480b9209d9867b046f24c25134dfd`，2026-10-04。

本轮只审计，不实施下列方向。P0=核心护城河缺口；P1=下一阶段重要；P2=后续增强。P0不是声称发生了急性医疗事故。类别采用DATA / MEMORY / AGENT / HUMAN / OUTCOME / KNOWLEDGE / UI / INFRA。

详细正反证据、数据库故事、工具清单及评分见 [HEALTHOPS_MOAT_AUDIT.md](HEALTHOPS_MOAT_AUDIT.md)。路径均相对项目根目录，`src/executive_health_ai/`下文简写为`src/…/`。

| ID / Gap | Current evidence | Why it matters | Moat impact | Priority / Category | Recommended direction | Do not implement yet / implement next |
|---|---|---|---|---|---|---|
| G01 治理后的Care Memory缺失 | `services/care_memory.py:22`仅识别夜班/出差/联系不上；每Goal最多一条trace；Demo care_context=0 | 不能积累“为什么失败/什么有效”，换人后仍需重读日志 | 每次服务不能提高下一次个体管理质量 | **P0 / MEMORY** | 从已有日志/障碍/医生/结果提炼有证据的管理经验；明确time range、confirmed/inferred、失效、纠错、刷新；不复制正式健康事实 | **Implement next：第1–2月**；本轮不实现 |
| G02 Decision→Intervention→Execution→Outcome不贯通 | `models/program.py` OutcomeEvaluation仅program与文字依据；`management_workflow.py`有部分related FK；`longitudinal.py:1727`前后比较无干预身份 | 无法稳定识别哪条建议被改、哪次行动被执行、结果属于哪次尝试 | 不能沉淀个人响应模式，不能安全评价策略 | **P0 / OUTCOME + HUMAN** | 复用Task/Recheck/Service作为执行对象，增加共同管理尝试身份/关系协议；明确接受/修改/拒绝、执行原因、结果窗口与Observation/反馈证据 | **Implement next：第2–4月**；不是新建第二套任务系统 |
| G03 目标驱动统一Context Assembly缺失 | `post_checkup.context`、`daily_summary.lookback`分别拼上下文；`get_care_context`正常Planner未调用；通用read工具多为count/exists | 同一人不同入口看到不同历史；新模型不会自动修补缺失上下文 | 事实与Memory无法转化为可持续个性化决策 | **P0 / AGENT + DATA** | 建立Goal/Metric/Event相关的有界上下文合同；包含有效事实、目标、阶段、相关历史/Memory、责任和开放行动引用 | **Implement next：第1月定义合同，第4–6月闭环验收** |
| G04 历史来源链不完整 | Demo 1522 Observation中118无Raw FK、source_type全空、confirmed_by全空；22候选无revision | 新链正确不等于老数据可追溯；GOVERNED容易被误读为人确认 | 可信事实资产被高估，历史审计断层 | P1 / DATA | 做只读覆盖清单与来源等级；只对可验证依据建立关系；无法恢复的原文标unknown，不补造 | Implement next：第1月先定验收；历史处理须独立迁移方案 |
| G05 版本关系未覆盖目标/计划/文本事实 | ManagementGoal一program一条；Intake.version是表单版本；`chronic_care.py:130`覆盖plan.content | 不能知道某时点依据哪个目标/方案决定，修正对Memory影响不可控 | 长期决策历史不稳定 | P1 / DATA + MEMORY | 先明确目标/计划变更与事实有效时间、记录时间，再复用现有audit/快照补版本关系 | Implement next：第1–3月；不全库重构 |
| G06 Metric时间语义不足 | Registry43代码主要numeric/unit/range；Daily累计类MAX；来源无point/interval/cumulative合同 | 同为“步数/睡眠时长”不一定可同样聚合，多设备重叠可失真 | 新设备接入仍可能侵入核心 | P1 / DATA | 扩充现有Metric语义：值类型、发生区间、时区、累积口径、去重/来源优先级、聚合策略 | Implement next：先覆盖一个真实连续数据场景 |
| G07 Goal-Metric映射治理不足 | `goal_metrics.py:37`硬编码；有version字符串/快照，部分Daily/readiness仍用live mapping | 改版后历史目标口径可能变化；CUSTOM/FOLLOWUP无数值映射 | 目标语义不能稳定复用或审计 | P1 / DATA + HUMAN | 在既有registry增加审核/版本/生效范围，所有运行读取确认时版本；非数值目标单独语义 | Implement next：第1–2月；不扩几十种目标 |
| G08 日Summary存量/来源覆盖断层 | Demo Summary/Revision/WorkItem全0；30 SleepSession却无sleep_duration Observation；默认旧库无表 | 浏览能看睡眠不等于自动管理能使用睡眠 | 连续状态资产未实际积累 | P1 / DATA + INFRA | 定义启用范围、观测覆盖、历史回填/不回填策略；只对满足来源质量的会员持续运行并监控 | Implement next：受控队列试点；不重建Demo |
| G09 Summary重算与变化证据失配 | hash未含规则版本；事件key为summary/rule/day，不含版本；旧日修正不自动重算之后比较窗 | 防重复可能同时保留过时变化证据；无法解释修正后的旧决定 | 长期证据可信度和恢复能力下降 | P1 / DATA + AGENT | 区分逻辑事件身份与证据修订；定义迟到数据、撤销/替代、下游窗口重算和幂等范围 | Implement next：连续数据试点前 |
| G10 Meaningful Change规则时间口径不统一 | 连续规则按最近N有值日，不验连续日期；风险匹配最后Observation而摘要显示mean；30日/基线主要上下文 | “显著变化”的解释可能不一致，缺数据被当持续 | 状态→决策质量受限 | P1 / DATA + HUMAN | 沿用RiskRule/ManagementRule统一时间/单位/样本/持续条件及版本；由业务/医生批准医学适用规则 | Implement next：第2–4月；本轮不设临床阈值 |
| G11 MEMBER Human Gate未统一 | Router只有AUTO/MANAGER/DOCTOR/ESCALATE；WAITING_MEMBER有状态；MemberPlanChoice更新program/task但未绑定原问题Goal | 本人意愿、执行、症状/偏好可能仍依赖健管转录 | 第一手反馈及个体响应资产不足 | P1 / HUMAN + OUTCOME | 小问题、来源身份、问题/Goal关联、自动原事项恢复；保留健管代录与本人提交的区别 | Implement next：伴随G02，优先执行反馈 |
| G12 人工重复核对未按例外细分 | Post-checkup manager review+action approval；FOLLOWUP_RESULT全量确认；Profile医生后仍等健管入档 | 自动整理节省不一定转成人力下降 | 高质量human correction信号被无修改批准淹没 | P1 / HUMAN | 记录why-human、改动/无改动、责任范围、耗时；仅对已批准可逆低风险事项评估免二次审，保留目标/计划/医学Gate | Implement next：先量化后调整 |
| G13 旧Service旁路与认证边界 | `chronic_care.py:94/130`阶段直接推进/计划覆盖；member接受方案激活；role多为传入字符串，UI演示切换不是鉴权 | 中央策略存在不等于所有入口遵守 | 责任资产不可全域复核 | P1 / HUMAN + INFRA | 枚举可达写入口、统一授权/来源/阶段协议；实际身份与医生签署独立验证 | Implement next：真实业务开放前；本轮未执行越权测试 |
| G14 旧医生流程不都same Goal resume | `chronic_care.py:195`医生结果直接建Task；新post-checkup/Daily路径有绑定事件恢复 | 多入口医生决定可能停留局部流程 | 医疗决定与后续行动、Memory关系不完整 | P1 / HUMAN + AGENT | 先关联既有医生记录与当前等待事项；不伪造无原Goal的历史Goal | Implement next：G02统一关系时 |
| G15 Planner固定模板、read tools过薄 | `planner.validate`要求proposed完全等于template；get_latest_outcome只bool；get_recent_observations LIMIT25 | 名称误导能力评估；无法基于个人经历受控重规划 | Agent差异化主要仍是流程 | P1 / AGENT | 先补有效上下文/结果合同，再允许小范围有约束选择与重规划；保留角色关卡 | Implement next：第4–6月；自由L4 NOT PRIORITY |
| G16 设备两条入口副作用不一致 | HealthEvent RAW STORE_ONLY；`integrations/service.py`每Observation还跑Risk/ManagementRouting | RAW测试不代表真实adapter吞吐和行为 | 规模化连续记忆成本不确定 | P1 / INFRA + DATA | 明确实时安全评估与批量状态聚合职责；用现有真实适配器契约做负载/幂等/重复删除验证 | Implement next：只选一个端到端来源 |
| G17 两个数据库schema不同 | Demo0032、默认库0031，新Goal/Daily/Communication表缺失 | 同HEAD换入口即可出现功能状态差异 | 证据与部署可复现性受损 | P1 / INFRA | 启动时只读识别路径/schema；独立、可回滚增量迁移审批与演练，避免把正式库当测试库 | Implement next：下一部署任务；本轮绝不迁移 |
| G18 知识使用治理未贯通 | 已有27文档/85chunks/审核/有效期；KnowledgeUseRecord0；retrieve_knowledge启用而knowledge_search禁用 | 有知识库不等于知道这次建议用了哪个有效版本 | 知识和人类纠正难沉淀到可信建议记录 | P1 / KNOWLEDGE | 统一READ_ONLY业务合同，逐建议引用快照、范围、批准和使用回执；检索backfill脱离读取 | Implement next：第5–6月；不先换检索引擎 |
| G19 UI下一步矛盾与读时写入 | 本人页同时“继续填写”与“无需操作”；goal_loop.gate读取时prepare+commit | 用户不清楚是否需行动；审计读取也可能产生业务状态 | 交互信号和真实决策时间被污染 | P1 / UI + HUMAN | 沿现有V7统一下一步来源，状态准备移至明确业务事件；保持同一导航与样式 | Implement next：相关闭环集成时，不重设计UI |
| G20 工具声明与执行保障差距 | 57工具均idempotent；timeout_seconds通用执行未强制；READ_ONLY也写trace/可能backfill | 集成方可能误解副作用/超时保证 | 更换运行框架、只读审计和故障恢复成本增加 | P2 / INFRA + AGENT | 明确业务read与存储副作用、统一执行预算和恢复合同；保留已有幂等结果引用 | Do not implement yet：除非试点暴露实际瓶颈 |
| G21 无跨季度资产复用评测 | 既有memory测试仅一条夜班提示；Outcome与下次决策无长期测试故事 | 回归通过也可能每次从零管理 | 无法证明护城河在增长 | P1 / MEMORY + OUTCOME | 同一会员多次尝试、拒绝/失败/修正、重启、后续决策使用记忆；评测引用正确与不使用过期推断 | Implement next：贯穿六个月，先定义评测再实现 |
| G22 多来源原文的保留完整性边界 | RawData ORM保护、外部文件storage_reference；没有由此证明文件生命周期/WORM/全SQL防改 | “永久保留”不能只由ORM事件担保 | 稀缺纠错与原始证据资产可能不可恢复 | P1 / DATA + INFRA | 明确保留/备份/校验/授权删除与修正协议；定期验证来源可恢复，不需要先采购复杂平台 | Implement next：真实数据试点前 |

## 非Gap或不应夸大的问题

- 没有向量数据库不是当前核心短板；知识审核、版本/引用已有基础。
- 不是没有Outcome，也不是所有行为都无关联；问题在完整链及经验回用。
- 不是没有MemberAgent；身份、等待、事件去重和重启已由真实代码/测试支持。
- 不是所有设备数据都调用LLM；审计没有发现逐Raw LLM调用主链。
- 不是所有来源丢失；source文本、Raw及文档证据仍存在，只是不满足统一完整追溯。
- 不是普通页面大量暴露Goal/Trace/JSON；实际14个视图未见架构泄漏，管理员技术展开不算健管泄漏。
- 当前管理空壳已被前置状态替代；不应以旧截图要求再次重做UI。

## 本轮边界

表中“Implement next”是路线建议，不是已实施变更。本轮无业务代码/UI/数据库修改，无新增业务功能、commit或push。

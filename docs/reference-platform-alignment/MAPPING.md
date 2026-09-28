# HealthOps V6 参考业务对齐

定位：会员全周期健康服务与管理工作台。

参考范围是本轮用户提供的“安瑜智慧健康平台”业务逻辑说明；未取得原平台系统或完整 95 菜单清单，不对其真实实现作比较结论。ALREADY_STRONGER 表示 HealthOps 已具备本轮要求、无需复制，而非未经验证的竞品优劣判断。

审计起点：94597cd；备份：backup/pre-service-operations-alignment。先审计模型、命令、导航和已有测试，再实施以下差距修复。

| 参考能力 | HealthOps 已有 | 差距 | 分类 | 实现方式 |
|---|---|---|---|---|
| 会员建档及责任管家 | enroll / HealthProgram.owner / Member360 | 服务申请未继承责任与周期 | ADOPT | 复用年度负责人，申请绑定当前方案、阶段 |
| 健康资料多来源 | Document / Observation / HealthRecord | 无需新档案 | ALREADY_STRONGER | 保留统一上传、设备、报告、问卷、手录 |
| 自动资料整理 | 同一 Agent / LocalLLMClient | 无需新助手 | ALREADY_STRONGER | 保留来源绑定、真实调用、例外队列 |
| 初始评估 | IntakeAssessment / 11 步修正入口 | 已有自动预填、人工例外确认 | ALREADY_STRONGER | 保留现有主路径 |
| 年度健康基线 | HealthAssessment | 已有人工确认与年度隔离 | ALREADY_STRONGER | 保留基线、趋势与证据 |
| 风险与异常 | Risk Engine / Responsibility Router | 不复制参考评分 | ALREADY_STRONGER | 确定性风险与原医生边界 |
| 医生判断 | DoctorReview | 已有人工作出医学判断 | ALREADY_STRONGER | 保留原协同详情及来源 |
| 长期历史 | Timeline / Evidence | 不应为简洁删证据 | ALREADY_STRONGER | 保留结果和原文件来源 |
| 方案与任务区分 | HealthProgram / ProgramPhase / Task | 页面缺少服务执行语义 | ADOPT | 管理区按阶段显示执行与结果，复用同一详情 |
| 服务执行台 | ServiceRequest / MemberServiceOperations | 状态合并，缺来源方案 | ADOPT | 六个业务状态、责任、时间、下一步表格 |
| 预约 | scheduled_at / provider / RecheckPlan | 展示不集中 | ADOPT | 服务详情明确预约时间、服务方；复查保留原流程 |
| 回访 | ManagementLog / Task | 已能建下一待办，需贯通服务结果 | ADOPT | 服务结果复核任务保留方案归属、回写日志 |
| 服务结果回流 | ServiceRequest.result_summary / Timeline | 完成时尚未直接进入管理日志 | ADOPT | 同事务生成既有 ManagementLog 与结果确认任务 |
| 阶段结果 | StageReview / OutcomeEvaluation | 摘要未包括真实指标和医生意见 | ADOPT | 汇总阶段内既有结果、反馈、意见供健管确认 |
| 下一阶段 | review_stage / advance_phase | 已有限定和医学关卡 | ALREADY_STRONGER | 复用现有命令与 Agent 工作流 |
| 专项管理 | OutcomeEvaluation / 计划、任务 | 无集中专项进度视图 | ADOPT | 只读专项表，真实起点/当前/目标，直达同一 Member360 |
| 年度组合视角 | AnnualPortfolio | 已与会员目录区分 | ALREADY_STRONGER | 保留 portfolio-first 路径 |
| 组织与人员 | 现有负责人、医生及演示角色 | 无生产机构与 IAM | PARTIAL | 管理员展示现有责任记录；标明 RBAC 局限 |
| 真实设备接入 | 网关与模拟适配器 | 缺已验证真实设备连接 | PARTIAL | 沿用既有入口，明确状态，不虚构连接 |
| 服务评价 | 会员反馈 / 管理日志 | 非独立评价平台 | PARTIAL | 使用已有会员反馈，不新建评分系统 |
| 获客营销 | 无 | 非本轮主链 | NOT_NOW | 仅文档边界 |
| 商品商城 | 演示服务目录 | 不应扩张商城 | NOT_NOW | 不新增商品交易能力 |
| 订单支付 | 无 | 非本轮范围 | NOT_NOW | Commercial 边界预留 |
| 积分兑换码 | 无 | 非本轮范围 | NOT_NOW | 不实现 |
| 服务费分润续费 | 演示权益 | 无合同与结算系统 | NOT_NOW | Entitlement 边界预留，不推导实际收费权益 |
| AI 管家聊天 | 后台业务 Agent | 用户明确不需要聊天 | NOT_APPLICABLE | 不新增聊天入口 |
| 菜单数量及伪改善评分 | 无 | 不属于可验证业务价值 | NOT_APPLICABLE | 不复制、不编造 |

## 唯一业务主链与责任

入组 → 责任健管 → 上传资料 → 原 Agent 整理 → 初始评估 → 健管初评 → 必要医生判断 → 年度基线 → 年度/阶段方案 → 服务、任务、预约与随访 → 执行结果与管理日志 → 异常按原责任分流 → 阶段复盘 → 下一阶段 → 年度复盘与下一年度。

会员目录找人，今日工作处理事，服务管理跨会员看执行，年度管理看年度组合，专项管理看已有目标与观测进度，所有会员详情回到唯一 Member360。Agent 是嵌入业务的后台执行者，不新增一级 Agent 菜单。管理方案决定管什么，Task/ServiceRequest/RecheckPlan 决定谁在什么时候做什么。

## 边界

- 不新建 Member、Agent、HealthRecord、Appointment 或商业模型。
- 正式风险继续由确定性 Risk Engine 产生，医学判断继续由医生完成。
- 任务完成率只描述执行情况；指标变化不能证明服务因果效果。
- Commercial / Entitlement Boundary：未来合同、支付、订单只能通过独立适配边界提供已确认权益；不得影响本轮健康事实、医学判断或服务执行。现有演示权益能力保留，本轮不新增商业模块。
- Organization Boundary：现有责任姓名不是生产身份或机构成员关系。生产 RBAC、多机构隔离、人员生命周期仍是 Limitations，不以演示角色切换冒充鉴权。
- LLM、网络、文件解析等耗时工作不得持有数据库写事务，沿用 docs/DEVELOPMENT.md。

## 验证

基线、定向测试、完整测试和 Chromium 业务故事结果完成后记录在 VERIFICATION.md。

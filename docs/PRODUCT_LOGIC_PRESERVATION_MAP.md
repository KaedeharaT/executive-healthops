# Product Logic Preservation Map

修改UI前冻结：`3ba46b2`。业务要素组与底层调用点分开统计；动态列表按模板盘点，不按每条数据算功能。
业务要素组：102；唯一底层调用点：1390。完整控件/图表/表单快照见 `product_logic_elements.json`。

|Element ID|当前名称 / 作用|当前位置|所属逻辑|新位置|处理|Renderer|
|---|---|---|---|---|---|---|
|MEM-001|首页今日行动|首页主行动与其他今日行动|健康运营|首页：主行动 → 管理阶段 → 变化 → 负责人 → 下个节点；完整信息展开|GROUP|home|
|MEM-002|管理周期与阶段|首页管理摘要与详情|健康运营|首页：主行动 → 管理阶段 → 变化 → 负责人 → 下个节点；完整信息展开|GROUP|home|
|MEM-003|负责人及下一步|首页照护团队与行动区|健康运营|首页：主行动 → 管理阶段 → 变化 → 负责人 → 下个节点；完整信息展开|GROUP|home|
|MEM-004|自动跟进状态|首页管理进展详情|健康运营|首页：主行动 → 管理阶段 → 变化 → 负责人 → 下个节点；完整信息展开|GROUP|home|
|MEM-005|下次服务|首页近期事项|健康运营|首页：主行动 → 管理阶段 → 变化 → 负责人 → 下个节点；完整信息展开|GROUP|home|
|MEM-006|近期趋势与下钻|首页双趋势与查看趋势|健康状态|首页：主行动 → 管理阶段 → 变化 → 负责人 → 下个节点；完整信息展开|GROUP|home|
|MEM-007|上传报告快捷入口|首页常用入口|健康状态|首页：主行动 → 管理阶段 → 变化 → 负责人 → 下个节点；完整信息展开|GROUP|home|
|MEM-008|年度健康基线|健康概览顶部|健康状态|健康概览：年度参考点 → 当前状态 → 比较与趋势 → 关注与背景|GROUP|overview|
|MEM-009|基线与当前对比|主趋势下方完整比较|健康状态|主趋势下方完整比较|KEEP|render_baseline_progress|
|MEM-010|基线趋势与指标选择|健康概览主视觉|健康状态|健康概览主视觉|KEEP|render_baseline_progress|
|MEM-011|基线详细依据与范围|年度基线详情|健康状态|年度基线详情|KEEP|render_baseline_visualization|
|MEM-012|基线修订记录|年度基线详情|健康状态|年度基线详情|KEEP|render_baseline_visualization|
|MEM-013|持续关注事项|趋势后关注列表|健康运营|健康概览：年度参考点 → 当前状态 → 比较与趋势 → 关注与背景|GROUP|overview|
|MEM-014|重要健康背景|健康背景展开区|健康状态|健康概览：年度参考点 → 当前状态 → 比较与趋势 → 关注与背景|GROUP|overview|
|MEM-015|健康数据与范围|健康数据指标工作区|健康状态|健康数据指标工作区|KEEP|render_health_explorer|
|MEM-016|数据来源与记录|图下来源展开区|健康运营|图下来源展开区|KEEP|render_health_explorer|
|MEM-017|体检报告与上传|健康体检最近结果与上传|健康状态|健康体检最近结果与上传|KEEP|_render_client_checkup_page|
|MEM-018|跨报告指标趋势|健康体检历史比较|健康状态|健康体检历史比较|KEEP|render_report_trends|
|MEM-019|医疗档案用药病史|健康医疗档案|健康状态|健康医疗档案|KEEP|_render_client_medical_archive|
|MEM-020|计划目标与负责人|计划目标摘要带|健康运营|计划目标摘要带|KEEP|plan|
|MEM-021|计划进度|计划执行进度|健康运营|计划执行进度|KEEP|plan|
|MEM-022|接受调整暂缓方案|方案选择展开区|健康运营|方案选择展开区|KEEP|plan|
|MEM-023|任务分类与完成|当前任务列表|健康运营|当前任务列表|KEEP|plan|
|MEM-024|近期节点|任务旁近期节点|健康运营|任务旁近期节点|KEEP|plan|
|MEM-025|阶段结果|任务旁阶段复盘|长期记录|任务旁阶段复盘|KEEP|plan|
|MEM-026|可用服务与权益|服务可用服务页签|健康运营|服务可用服务页签|KEEP|_render_client_service|
|MEM-027|服务申请|服务可用服务详情|健康运营|服务可用服务详情|KEEP|_render_client_service|
|MEM-028|当前申请与安排|服务默认当前申请|健康运营|服务默认当前申请|KEEP|_render_client_service|
|MEM-029|取消申请|当前申请详情|健康运营|当前申请详情|KEEP|_render_client_service|
|MEM-030|服务历史结果依据|服务记录页签|健康状态|服务记录页签|KEEP|_render_client_service|
|MEM-031|重要健康事件|日期轨道列表|健康运营|日期轨道列表|KEEP|_timeline_content|
|MEM-032|完整时间轴与筛选|查看完整历程与依据|长期记录|查看完整历程与依据|KEEP|render_longitudinal_timeline|
|MEM-033|个人资料|右上个人设置|健康运营|右上个人设置|KEEP|_render_client_profile|
|MEM-034|设备Apple健康来源|个人设置设备与数据|健康运营|个人设置设备与数据|KEEP|_render_client_profile|
|MEM-035|隐私授权撤回|个人设置隐私授权|健康运营|个人设置隐私授权|KEEP|_render_client_profile|
|MGR-001|今日行动数字|今日摘要带|健康运营|今日统一队列 → 选中事项 → 上下文与原处理命令|MERGE|today|
|MGR-002|工作队列及类型筛选|左列表与筛选|健康运营|今日统一队列 → 选中事项 → 上下文与原处理命令|MERGE|today|
|MGR-003|原因责任截止下一步|右侧事项详情|健康运营|今日统一队列 → 选中事项 → 上下文与原处理命令|MERGE|today|
|MGR-004|处理工作入口|选中事项处理|健康运营|今日统一队列 → 选中事项 → 上下文与原处理命令|MERGE|today|
|MGR-005|超过12项的工作|队列其他事项分页/展开|健康运营|今日统一队列 → 选中事项 → 上下文与原处理命令|MERGE|today|
|MGR-006|自动跟进及审批|今日详情展开与管理审批|健康运营|今日详情展开与管理审批|KEEP|approvals|
|MGR-007|成员列表|成员列表|健康运营|成员列表|KEEP|render_members_workspace|
|MGR-008|成员360摘要|成员360上下文头|健康运营|成员360上下文头|KEEP|member_detail|
|MGR-009|成员360基线摘要|概览完整基线展开|健康状态|概览完整基线展开|KEEP|member_detail|
|MGR-010|成员360最近趋势|概览主要区域|健康状态|概览主要区域|KEEP|member_detail|
|MGR-011|当前计划与服务摘要|趋势旁管理摘要|健康运营|趋势旁管理摘要|KEEP|member_detail|
|MGR-012|开放关注事项处理|概览关注处理展开|健康运营|概览关注处理展开|KEEP|member_detail|
|MGR-013|成员服务操作|概览服务展开与管理快捷入口|健康运营|概览服务展开与管理快捷入口|KEEP|render_member_service_management|
|MGR-014|健康数据|成员健康数据|健康状态|成员健康数据|KEEP|render_member_archive|
|MGR-015|报告列表上传确认|成员健康体检|健康状态|成员健康体检|KEEP|render_report_upload|
|MGR-016|报告候选人工核对|体检审核详情|健康状态|体检审核详情|KEEP|render_report_review|
|MGR-017|报告解析与重跑|报告高级信息|健康状态|报告高级信息|KEEP|render_report_review|
|MGR-018|年度基线建立确认冻结|成员健康基线|健康状态|成员健康基线|KEEP|render_health_assessments|
|MGR-019|基线修订年度切换|基线详情与修订|健康状态|基线详情与修订|KEEP|render_health_assessments|
|MGR-020|健康史|成员健康史|健康状态|成员健康史|KEEP|render_member_archive|
|MGR-021|当前管理计划选择|管理摘要与计划选择|健康运营|管理摘要与计划选择|KEEP|management|
|MGR-022|建立调整计划|管理表单与360快捷入口|健康运营|管理表单与360快捷入口|KEEP|management|
|MGR-023|安排随访|管理随访表单与快捷入口|健康运营|管理随访表单与快捷入口|KEEP|management|
|MGR-024|阶段结果录入与下一步|管理结果表单与快捷入口|长期记录|管理结果表单与快捷入口|KEEP|management|
|MGR-025|执行任务|管理工作进展|健康运营|管理工作进展|KEEP|render_tasks|
|MGR-026|计划详情阶段结果|工作进展详情展开|长期记录|工作进展详情展开|KEEP|render_programs|
|MGR-027|自动跟进健康管理信号|管理记录展开|健康运营|管理记录展开|KEEP|render_member_management_signals|
|MGR-028|成员医疗上下文|成员医疗|健康运营|成员医疗|KEEP|render_member_medical_workspace|
|MGR-029|内部医生协同|统一医生队列只读|健康运营|统一医生队列只读|KEEP|render_collaboration_workspace|
|MGR-030|外部医生转诊|外部医疗|健康运营|外部医疗|KEEP|render_external_doctor_workspace|
|MGR-031|服务运营队列|服务工作台|健康运营|服务工作台|KEEP|render_service_operations_workspace|
|MGR-032|服务审核安排完成|原上下文服务操作|健康运营|原上下文服务操作|KEEP|render_member_service_management|
|MGR-033|知识检索与资料|更多专业资料|健康运营|更多专业资料|KEEP|render_knowledge_library_entry|
|DOC-001|复核队列与已完成|队列筛选与选择|健康运营|队列筛选与选择|KEEP|workspace|
|DOC-002|医学问题与提交信息|详情首屏问题带|健康运营|医生复核：问题 → 背景 → 趋势 → 依据 → 用药 → 行动 → 结论|MOVE|detail|
|DOC-003|成员背景年度基线|临床上下文展开区|健康状态|医生复核：问题 → 背景 → 趋势 → 依据 → 用药 → 行动 → 结论|MOVE|detail|
|DOC-004|关键指标用药|左侧临床上下文|健康状态|医生复核：问题 → 背景 → 趋势 → 依据 → 用药 → 行动 → 结论|MOVE|detail|
|DOC-005|相关趋势|左侧主要图表|健康状态|左侧主要图表|KEEP|render_doctor_trend|
|DOC-006|证据完整性与原文|左侧报告依据|健康运营|左侧报告依据|KEEP|evidence_summary|
|DOC-007|完整资料位置核对|依据高级展开|健康运营|医生复核：问题 → 背景 → 趋势 → 依据 → 用药 → 行动 → 结论|MOVE|detail|
|DOC-008|已采取行动|临床背景展开|健康运营|医生复核：问题 → 背景 → 趋势 → 依据 → 用药 → 行动 → 结论|MOVE|detail|
|DOC-009|人工意见与交回|右侧结论与执行交接|健康运营|医生复核：问题 → 背景 → 趋势 → 依据 → 用药 → 行动 → 结论|MOVE|detail|
|DOC-010|旧警报基线医学确认|原兼容复核分支|健康状态|原兼容复核分支|KEEP|workspace|
|DOC-011|医生审批|选中成员审批区|健康运营|选中成员审批区|KEEP|approvals|
|ADM-001|集成状态与检查|左连接列表右操作|支撑能力|左连接列表右操作|KEEP|integrations|
|ADM-002|数据包模板上传检查|集成数据导入|支撑能力|集成数据导入|KEEP|_render_data_package_import|
|ADM-003|预览确认正式写入|集成数据导入确认|支撑能力|集成数据导入确认|KEEP|_render_data_package_import|
|ADM-004|AI配置测试|集成AI操作区|支撑能力|集成AI操作区|KEEP|_render_ai_service_integration|
|ADM-005|专业知识Adapter与审核|集成专业知识与规则知识|支撑能力|集成专业知识与规则知识|KEEP|_render_knowledge_service_integration|
|ADM-006|设备测试导入|集成设备与规则知识|支撑能力|集成设备与规则知识|KEEP|_render_device_integration|
|ADM-007|自动化目标等待状态|自动化状态与选中目标|支撑能力|自动化状态与选中目标|KEEP|_render_admin_automation|
|ADM-008|人工接手恢复取消|目标详情操作|支撑能力|目标详情操作|KEEP|_render_admin_automation|
|ADM-009|Trace技术诊断|自动化高级信息|支撑能力|自动化高级信息|KEEP|_render_admin_automation|
|ADM-010|风险规则配置|规则与知识规则页|支撑能力|管理员 → 规则与知识 / 系统状态；更多保留兼容跳转|ADVANCED|render_risk_rules|
|ADM-011|系统连接状态|系统状态摘要|支撑能力|系统状态摘要|KEEP|workspace|
|ADM-012|审计记录|系统操作记录展开|支撑能力|系统操作记录展开|KEEP|render_audit|
|ADM-013|反馈质量治理|AI质量治理高级|支撑能力|AI质量治理高级|KEEP|render_ai_improvement|
|ADM-014|旧健康图表与数据网关|系统高级兼容工具|支撑能力|系统高级兼容工具|KEEP|render_health_data|
|ADM-015|监管及演示旧详情|系统高级兼容工具|支撑能力|系统高级兼容工具|KEEP|render_oversight_summary|
|V2-001|健康团队只读摘要|首页团队区|健康运营|首页变化下方负责人|MOVE|care_team|
|V2-002|演示角色切换|侧栏popover|支撑能力|原位置；仍明示非鉴权|KEEP|_render_surface_switcher|
|V2-003|全指标比较表|健康趋势下方展开|健康状态|健康概览比较与依据展开|KEEP|_render_comparison_details|
|V2-004|健管查找与事项选择|今日|健康运营|统一队列筛选与详情|GROUP|today|
|V2-005|360随访与结果快捷入口|360概览|健康运营|360管理及概览快捷入口|KEEP|member_detail|
|V2-006|十五项历史兼容工具|系统状态高级信息|支撑能力|管理员系统状态高级信息|LEGACY ACCESS|legacy_tools|
|V2-007|所有自动化目标明细|自动化运营展开|支撑能力|管理员自动化运营展开|KEEP|_render_admin_automation|
|V2-008|近期与完整历程展开|成员历程|长期记录|长期记录：近期事件与完整依据|KEEP|_timeline_content|

## 验收约束

所有原函数、图表、API保留；旧导航别名继续解析。三条业务主线是阅读与处理顺序，不是新事实表。次级能力必须有可点击路径，不能仅保留代码。最终测试与截图完成后核对Missing与Preserved。


## 完成核对

业务要素102/102保留（100%）：KEEP 77、GROUP 11、MOVE 7、MERGE 5、ADVANCED 1、LEGACY ACCESS 1。Deleted 0，Missing 0。

348个原UI函数、280个既有控件key表达式、66个API路由契约均保留；原图表实现和坐标轴配置未改。元素名称/顺序变化不等于能力删除。关键可达性由 `tests/test_product_element_preservation.py`、既有角色/兼容工具AppTest和真实Chromium交互共同验证。

旧标签兼容包括历程 → 健康数据的时间范围传递，以及更多 → 风险规则/审计/系统的管理员归类。详见 [前后对照](PRODUCT_LOGIC_REFACTOR_BEFORE_AFTER.md) 和 [真实视觉验收](PRODUCT_LOGIC_VISUAL_QA.md)。

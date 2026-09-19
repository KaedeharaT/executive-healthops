# UX V3 元素保留验收

基准：冻结研究03的121条；102业务分组、15兼容子项、4导航组。每个元素仍有具体归属，默认隐藏不等于删除。

Total: **121** · Preserved: **121** · Deleted: **0** · Missing: **0** · Unassigned: **0**

验证分三层：逐项检查原渲染器仍在对应源文件、新入口归属非空；原保留测试检查此前函数兼容合同；真实角色路径与全部15个Legacy工具通过AppTest执行，主要场景另用真实Chromium验收。不是用“源码函数存在”替代全部运行证明，也不是穷举每种动态记录。

机器清单：[elements.json](elements.json)。回归：`tests/test_ux_v3_implementation.py`、`test_ux_element_preservation.py`、`test_product_element_preservation.py`。视觉及交互证据见03。

|ID|原元素|实现位置|新归属|展示层|保留|
|---|---|---|---|---|---|
|MEM-001|首页今日行动|[home](../../src/executive_health_ai/ui/pages/member/experience.py#L44)|首页 → 今日行动与管理摘要|PRIMARY|YES|
|MEM-002|管理周期与阶段|[home](../../src/executive_health_ai/ui/pages/member/experience.py#L44)|首页 → 今日行动与管理摘要|PRIMARY|YES|
|MEM-003|负责人及下一步|[home](../../src/executive_health_ai/ui/pages/member/experience.py#L44)|首页 → 今日行动与管理摘要|PRIMARY|YES|
|MEM-004|自动跟进状态|[home](../../src/executive_health_ai/ui/pages/member/experience.py#L44)|首页 → 管理进展详情|DETAIL|YES|
|MEM-005|下次服务|[home](../../src/executive_health_ai/ui/pages/member/experience.py#L44)|首页 → 近期安排；服务 → 当前服务|SECONDARY|YES|
|MEM-006|近期趋势与下钻|[home](../../src/executive_health_ai/ui/pages/member/experience.py#L44)|首页 → 最近变化（两张预览/一个下钻入口）|PRIMARY|YES|
|MEM-007|上传报告快捷入口|[home](../../src/executive_health_ai/ui/pages/member/experience.py#L44)|健康 → 体检与检查 → 上传；无资料首页主行动|SECONDARY|YES|
|MEM-008|年度健康基线|[overview](../../src/executive_health_ai/ui/pages/member/experience.py#L107)|健康概览 P2 → 年度基线/当前比较/主趋势|PRIMARY|YES|
|MEM-009|基线与当前对比|[render_baseline_progress](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L96)|健康概览 P2 → 年度基线/当前比较/主趋势|PRIMARY|YES|
|MEM-010|基线趋势与指标选择|[render_baseline_progress](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L96)|健康概览 P2 → 年度基线/当前比较/主趋势|PRIMARY|YES|
|MEM-011|基线详细依据与范围|[render_baseline_visualization](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L18)|健康概览 → 年度基线详情 → 依据/参考范围/修订|DETAIL|YES|
|MEM-012|基线修订记录|[render_baseline_visualization](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L18)|健康概览 → 年度基线详情 → 依据/参考范围/修订|DETAIL|YES|
|MEM-013|持续关注事项|[overview](../../src/executive_health_ai/ui/pages/member/experience.py#L107)|健康概览 → 当前关注|PRIMARY|YES|
|MEM-014|重要健康背景|[overview](../../src/executive_health_ai/ui/pages/member/experience.py#L107)|健康 → 健康档案 → 问题/用药/病史/医疗事件|DETAIL|YES|
|MEM-015|健康数据与范围|[render_health_explorer](../../src/executive_health_ai/ui/pages/health_visualization.py#L35)|健康 → 健康数据 → 指标与时间范围|PRIMARY|YES|
|MEM-016|数据来源与记录|[render_health_explorer](../../src/executive_health_ai/ui/pages/health_visualization.py#L35)|健康数据 → 数据来源/详细记录/查看依据|DETAIL|YES|
|MEM-017|体检报告与上传|[_render_client_checkup_page](../../streamlit_app.py#L5920)|健康 → 体检与检查 → 最近报告/历史比较/上传|DETAIL|YES|
|MEM-018|跨报告指标趋势|[render_report_trends](../../src/executive_health_ai/ui/pages/health_visualization.py#L78)|健康 → 体检与检查 → 最近报告/历史比较/上传|DETAIL|YES|
|MEM-019|医疗档案用药病史|[_render_client_medical_archive](../../streamlit_app.py#L5943)|健康 → 健康档案 → 问题/用药/病史/医疗事件|DETAIL|YES|
|MEM-020|计划目标与负责人|[plan](../../src/executive_health_ai/ui/pages/member/experience.py#L143)|计划 → 当前目标/任务/执行进度/下个节点|PRIMARY|YES|
|MEM-021|计划进度|[plan](../../src/executive_health_ai/ui/pages/member/experience.py#L143)|计划 → 当前目标/任务/执行进度/下个节点|PRIMARY|YES|
|MEM-022|接受调整暂缓方案|[plan](../../src/executive_health_ai/ui/pages/member/experience.py#L143)|计划 → 当前方案 → 接受/调整/暂缓|SECONDARY|YES|
|MEM-023|任务分类与完成|[plan](../../src/executive_health_ai/ui/pages/member/experience.py#L143)|计划 → 当前目标/任务/执行进度/下个节点|PRIMARY|YES|
|MEM-024|近期节点|[plan](../../src/executive_health_ai/ui/pages/member/experience.py#L143)|计划 → 当前目标/任务/执行进度/下个节点|PRIMARY|YES|
|MEM-025|阶段结果|[plan](../../src/executive_health_ai/ui/pages/member/experience.py#L143)|计划 → 本计划阶段结果；历程 → 对应结果事件|DETAIL|YES|
|MEM-026|可用服务与权益|[_render_client_service](../../streamlit_app.py#L5754)|服务 → 可用服务/申请表|SECONDARY|YES|
|MEM-027|服务申请|[_render_client_service](../../streamlit_app.py#L5754)|服务 → 可用服务/申请表|SECONDARY|YES|
|MEM-028|当前申请与安排|[_render_client_service](../../streamlit_app.py#L5754)|服务 → 进行中的申请/安排/下一步|PRIMARY|YES|
|MEM-029|取消申请|[_render_client_service](../../streamlit_app.py#L5754)|服务 → 对应申请详情/取消/历史结果|DETAIL|YES|
|MEM-030|服务历史结果依据|[_render_client_service](../../streamlit_app.py#L5754)|服务 → 对应申请详情/取消/历史结果|DETAIL|YES|
|MEM-031|重要健康事件|[_timeline_content](../../src/executive_health_ai/ui/pages/member/experience.py#L215)|历程 → 重要事件|PRIMARY|YES|
|MEM-032|完整时间轴与筛选|[render_longitudinal_timeline](../../src/executive_health_ai/ui/pages/member/experience.py#L25)|历程 → 完整历程/筛选/事件详情|DETAIL|YES|
|MEM-033|个人资料|[_render_client_profile](../../streamlit_app.py#L5844)|个人设置 → 资料/设备与数据/隐私授权；健康数据来源链接同一设置|DETAIL|YES|
|MEM-034|设备Apple健康来源|[_render_client_profile](../../streamlit_app.py#L5844)|个人设置 → 资料/设备与数据/隐私授权；健康数据来源链接同一设置|DETAIL|YES|
|MEM-035|隐私授权撤回|[_render_client_profile](../../streamlit_app.py#L5844)|个人设置 → 资料/设备与数据/隐私授权；健康数据来源链接同一设置|DETAIL|YES|
|MGR-001|今日行动数字|[today](../../src/executive_health_ai/ui/pages/manager/experience.py#L38)|今日 P3 → 工作摘要/短队列/选中事项处理|PRIMARY|YES|
|MGR-002|工作队列及类型筛选|[today](../../src/executive_health_ai/ui/pages/manager/experience.py#L38)|今日 P3 → 工作摘要/短队列/选中事项处理|PRIMARY|YES|
|MGR-003|原因责任截止下一步|[today](../../src/executive_health_ai/ui/pages/manager/experience.py#L38)|今日 P3 → 工作摘要/短队列/选中事项处理|PRIMARY|YES|
|MGR-004|处理工作入口|[today](../../src/executive_health_ai/ui/pages/manager/experience.py#L38)|今日 P3 → 工作摘要/短队列/选中事项处理|PRIMARY|YES|
|MGR-005|超过12项的工作|[today](../../src/executive_health_ai/ui/pages/manager/experience.py#L38)|今日 → 完整队列（保留分页/展开后续事项）|SECONDARY|YES|
|MGR-006|自动跟进及审批|[approvals](../../src/executive_health_ai/ui/pages/manager/experience.py#L19)|今日待确认事项/成员360管理 → 自动跟进确认|DETAIL|YES|
|MGR-007|成员列表|[render_members_workspace](../../streamlit_app.py#L2883)|成员 → 成员列表|PRIMARY|YES|
|MGR-008|成员360摘要|[member_detail](../../src/executive_health_ai/ui/pages/manager/experience.py#L224)|成员360 P4 → 抬头/基线摘要/趋势/当前安排|PRIMARY|YES|
|MGR-009|成员360基线摘要|[member_detail](../../src/executive_health_ai/ui/pages/manager/experience.py#L224)|成员360 P4 → 抬头/基线摘要/趋势/当前安排|PRIMARY|YES|
|MGR-010|成员360最近趋势|[member_detail](../../src/executive_health_ai/ui/pages/manager/experience.py#L224)|成员360 P4 → 抬头/基线摘要/趋势/当前安排|PRIMARY|YES|
|MGR-011|当前计划与服务摘要|[member_detail](../../src/executive_health_ai/ui/pages/manager/experience.py#L224)|成员360 P4 → 抬头/基线摘要/趋势/当前安排|PRIMARY|YES|
|MGR-012|开放关注事项处理|[member_detail](../../src/executive_health_ai/ui/pages/manager/experience.py#L224)|成员360 → 开放事项摘要；选中进入唯一处理详情|DETAIL|YES|
|MGR-013|成员服务操作|[render_member_service_management](../../streamlit_app.py#L5688)|服务运营/成员360管理 → 服务详情|DETAIL|YES|
|MGR-014|健康数据|[render_member_archive](../../streamlit_app.py#L4385)|成员360健康 → 主趋势/数据记录|PRIMARY|YES|
|MGR-015|报告列表上传确认|[render_report_upload](../../streamlit_app.py#L4314)|成员360健康 → 报告详情 → 上传/确认/解析详情|DETAIL|YES|
|MGR-016|报告候选人工核对|[render_report_review](../../streamlit_app.py#L4002)|成员360健康 → 报告详情 → 上传/确认/解析详情|DETAIL|YES|
|MGR-017|报告解析与重跑|[render_report_review](../../streamlit_app.py#L4002)|成员360健康 → 报告详情 → 上传/确认/解析详情|DETAIL|YES|
|MGR-018|年度基线建立确认冻结|[render_health_assessments](../../streamlit_app.py#L4449)|成员360健康 → 年度基线详情 → 建立/确认/修订/年度|DETAIL|YES|
|MGR-019|基线修订年度切换|[render_health_assessments](../../streamlit_app.py#L4449)|成员360健康 → 年度基线详情 → 建立/确认/修订/年度|DETAIL|YES|
|MGR-020|健康史|[render_member_archive](../../streamlit_app.py#L4385)|成员360健康 → 健康档案/健康史|DETAIL|YES|
|MGR-021|当前管理计划选择|[management](../../src/executive_health_ai/ui/pages/manager/experience.py#L130)|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|YES|
|MGR-022|建立调整计划|[management](../../src/executive_health_ai/ui/pages/manager/experience.py#L130)|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|YES|
|MGR-023|安排随访|[management](../../src/executive_health_ai/ui/pages/manager/experience.py#L130)|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|YES|
|MGR-024|阶段结果录入与下一步|[management](../../src/executive_health_ai/ui/pages/manager/experience.py#L130)|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|YES|
|MGR-025|执行任务|[render_tasks](../../streamlit_app.py#L1767)|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|YES|
|MGR-026|计划详情阶段结果|[render_programs](../../streamlit_app.py#L2612)|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|YES|
|MGR-027|自动跟进健康管理信号|[render_member_management_signals](../../streamlit_app.py#L2676)|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|YES|
|MGR-028|成员医疗上下文|[render_member_medical_workspace](../../streamlit_app.py#L4346)|医疗协同/成员360医疗 → 同源复核/转诊/医学依据|DETAIL|YES|
|MGR-029|内部医生协同|[render_collaboration_workspace](../../streamlit_app.py#L3750)|医疗协同/成员360医疗 → 同源复核/转诊/医学依据|DETAIL|YES|
|MGR-030|外部医生转诊|[render_external_doctor_workspace](../../streamlit_app.py#L6045)|医疗协同/成员360医疗 → 同源复核/转诊/医学依据|DETAIL|YES|
|MGR-031|服务运营队列|[render_service_operations_workspace](../../streamlit_app.py#L3761)|服务运营/成员360管理 → 服务详情|DETAIL|YES|
|MGR-032|服务审核安排完成|[render_member_service_management](../../streamlit_app.py#L5688)|服务运营/成员360管理 → 服务详情|DETAIL|YES|
|MGR-033|知识检索与资料|[render_knowledge_library_entry](../../streamlit_app.py#L3424)|更多 → 专业资料；事项旁查看引用|SECONDARY|YES|
|DOC-001|复核队列与已完成|[workspace](../../src/executive_health_ai/ui/pages/doctor/experience.py#L100)|待我复核/历史 → 问题队列|PRIMARY|YES|
|DOC-002|医学问题与提交信息|[detail](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15)|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|YES|
|DOC-003|成员背景年度基线|[detail](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15)|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|YES|
|DOC-004|关键指标用药|[detail](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15)|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|YES|
|DOC-005|相关趋势|[render_doctor_trend](../../src/executive_health_ai/ui/pages/health_visualization.py#L95)|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|YES|
|DOC-006|证据完整性与原文|[evidence_summary](../../src/executive_health_ai/ui/experience.py#L182)|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|YES|
|DOC-007|完整资料位置核对|[detail](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15)|医生复核 → 完整资料/既有行动展开|DETAIL|YES|
|DOC-008|已采取行动|[detail](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15)|医生复核 → 完整资料/既有行动展开|DETAIL|YES|
|DOC-009|人工意见与交回|[detail](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15)|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|YES|
|DOC-010|旧警报基线医学确认|[workspace](../../src/executive_health_ai/ui/pages/doctor/experience.py#L100)|待我复核 → 年度基线/旧警报/后续安排确认，分别说明任务性质|DETAIL|YES|
|DOC-011|医生审批|[approvals](../../src/executive_health_ai/ui/pages/manager/experience.py#L19)|待我复核 → 年度基线/旧警报/后续安排确认，分别说明任务性质|DETAIL|YES|
|ADM-001|集成状态与检查|[integrations](../../src/executive_health_ai/ui/pages/admin/experience.py#L22)|系统状态 P6 → 集成与运行状态概况|PRIMARY|YES|
|ADM-002|数据包模板上传检查|[_render_data_package_import](../../streamlit_app.py#L3487)|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|YES|
|ADM-003|预览确认正式写入|[_render_data_package_import](../../streamlit_app.py#L3487)|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|YES|
|ADM-004|AI配置测试|[_render_ai_service_integration](../../streamlit_app.py#L3606)|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|YES|
|ADM-005|专业知识Adapter与审核|[_render_knowledge_service_integration](../../streamlit_app.py#L3640)|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|YES|
|ADM-006|设备测试导入|[_render_device_integration](../../streamlit_app.py#L3716)|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|YES|
|ADM-007|自动化目标等待状态|[_render_admin_automation](../../streamlit_app.py#L319)|自动化运营 → 选中过程 → 等待/异常/人工操作|DETAIL|YES|
|ADM-008|人工接手恢复取消|[_render_admin_automation](../../streamlit_app.py#L319)|自动化运营 → 选中过程 → 等待/异常/人工操作|DETAIL|YES|
|ADM-009|Trace技术诊断|[_render_admin_automation](../../streamlit_app.py#L319)|自动化运营 → 对应过程 → 高级诊断/Trace|ADVANCED|YES|
|ADM-010|风险规则配置|[render_risk_rules](../../streamlit_app.py#L6316)|规则与知识 → 风险规则|DETAIL|YES|
|ADM-011|系统连接状态|[workspace](../../src/executive_health_ai/ui/pages/admin/experience.py#L54)|系统状态 P6 → 集成与运行状态概况|PRIMARY|YES|
|ADM-012|审计记录|[render_audit](../../streamlit_app.py#L2578)|系统状态 → 操作记录|DETAIL|YES|
|ADM-013|反馈质量治理|[render_ai_improvement](../../src/executive_health_ai/ui/pages/ai_improvement.py#L25)|系统状态 → AI质量治理（高级）|ADVANCED|YES|
|ADM-014|旧健康图表与数据网关|[render_health_data](../../streamlit_app.py#L2414)|系统状态 → 兼容工具 → 同名原工具|LEGACY|YES|
|ADM-015|监管及演示旧详情|[render_oversight_summary](../../streamlit_app.py#L3738)|系统状态 → 兼容工具 → 同名原工具|LEGACY|YES|
|V2-001|健康团队只读摘要|[care_team](../../src/executive_health_ai/ui/components.py#L66)|首页管理摘要及近期安排 → 健康团队|PRIMARY|YES|
|V2-002|演示角色切换|[_render_surface_switcher](../../streamlit_app.py#L396)|演示入口/角色预览菜单|SECONDARY|YES|
|V2-003|全指标比较表|[_render_comparison_details](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L156)|健康概览 → 全指标基线与当前对比|DETAIL|YES|
|V2-004|健管查找与事项选择|[today](../../src/executive_health_ai/ui/pages/manager/experience.py#L38)|今日 → 队列筛选与选中事项|PRIMARY|YES|
|V2-005|360随访与结果快捷入口|[member_detail](../../src/executive_health_ai/ui/pages/manager/experience.py#L224)|成员360 → 当前下一步主动作/管理详情|SECONDARY|YES|
|V2-006|十五项历史兼容工具|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具目录（15个子项逐项见LEG）|LEGACY|YES|
|V2-007|所有自动化目标明细|[_render_admin_automation](../../streamlit_app.py#L319)|自动化运营 → 全部目标详情|ADVANCED|YES|
|V2-008|近期与完整历程展开|[_timeline_content](../../src/executive_health_ai/ui/pages/member/experience.py#L215)|历程 → 更多重要事件/完整历程|DETAIL|YES|
|LEG-001|健康数据完整视图|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 健康数据完整视图|LEGACY|YES|
|LEG-002|报告比较|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 报告比较|LEGACY|YES|
|LEG-003|干预前后比较|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 干预前后比较|LEGACY|YES|
|LEG-004|风险监管摘要|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 风险监管摘要|LEGACY|YES|
|LEG-005|数据接入网关|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 数据接入网关|LEGACY|YES|
|LEG-006|成员设备分配|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 成员设备分配|LEGACY|YES|
|LEG-007|演示路径|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 演示路径|LEGACY|YES|
|LEG-008|完整成员摘要|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 完整成员摘要|LEGACY|YES|
|LEG-009|历史健康问题|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 历史健康问题|LEGACY|YES|
|LEG-010|历史医疗记录|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 历史医疗记录|LEGACY|YES|
|LEG-011|全部异常处理|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 全部异常处理|LEGACY|YES|
|LEG-012|原始观测详情|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 原始观测详情|LEGACY|YES|
|LEG-013|数据来源详情|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 数据来源详情|LEGACY|YES|
|LEG-014|阶段结果详情|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 阶段结果详情|LEGACY|YES|
|LEG-015|历史时间轴|[legacy_tools](../../src/executive_health_ai/ui/pages/admin/experience.py#L98)|系统状态 → 兼容工具 → 历史时间轴|LEGACY|YES|
|NAV-001|Member主导航/健康四视图|[render_member_client_view](../../streamlit_app.py#L6009)|成员：首页/健康/计划/服务/历程|PRIMARY|YES|
|NAV-002|Manager主导航/360五视图|[member_detail](../../src/executive_health_ai/ui/pages/manager/experience.py#L224)|健管：今日/成员/医疗协同/服务/更多|PRIMARY|YES|
|NAV-003|Doctor队列筛选|[workspace](../../src/executive_health_ai/ui/pages/doctor/experience.py#L100)|医生：待我复核/历史|PRIMARY|YES|
|NAV-004|Admin系统四分区|[workspace](../../src/executive_health_ai/ui/pages/admin/experience.py#L54)|管理员：系统状态/集成与数据/自动化运营/规则与知识|PRIMARY|YES|

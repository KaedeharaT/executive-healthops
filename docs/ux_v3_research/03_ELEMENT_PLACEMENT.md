# UX V3 · Element Placement

基准 HEAD `78a1263536bdf1f05c6e0fec64ac15423d9e4ca5`；2026-09-20。只做设计归属，不修改实际入口。

## 口径与结果

业务/导航/兼容目录条目 **121**（102个既有业务组 + 15个兼容子项 + 4组导航）；Assigned **121**；Preserved **100%**；Deleted **0**；Unassigned **0**。父组与兼容子项存在包含关系，这不是独立业务模块数量。

另对当前源码重新扫描所有UI声明/调用模板，见 [03A](03A_SOURCE_ELEMENT_REGISTER.md)。旧 `product_logic_elements.json` 的102业务组仅作漏项检查起点，其1390旧调用数未沿用；当前文件行号与调用重新解析。PRIMARY/SECONDARY/DETAIL/ADVANCED/LEGACY表示新位置的可见性，不修改权限。PRIMARY表示该元素在自己的任务场景主显，不表示121项同屏。

L1现在行动；L2理解状态；L3详细资料；L4支撑后台。业务健康状态/健康运营/长期记录与这些信息层级是两种维度，不能用L4取代业务责任。

|ID|Element|Current location|Business purpose|Layer|New location|Visibility|Primary role|Secondary role|Reason|Preserved|
|---|---|---|---|---|---|---|---|---|---|---|
|MEM-001|首页今日行动|[src/executive_health_ai/ui/pages/member/experience.py:44](../../src/executive_health_ai/ui/pages/member/experience.py#L44) · home|健康运营：首页今日行动|L1|首页 → 今日行动与管理摘要|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-002|管理周期与阶段|[src/executive_health_ai/ui/pages/member/experience.py:44](../../src/executive_health_ai/ui/pages/member/experience.py#L44) · home|健康运营：管理周期与阶段|L1|首页 → 今日行动与管理摘要|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-003|负责人及下一步|[src/executive_health_ai/ui/pages/member/experience.py:44](../../src/executive_health_ai/ui/pages/member/experience.py#L44) · home|健康运营：负责人及下一步|L1|首页 → 今日行动与管理摘要|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-004|自动跟进状态|[src/executive_health_ai/ui/pages/member/experience.py:44](../../src/executive_health_ai/ui/pages/member/experience.py#L44) · home|健康运营：自动跟进状态|L2|首页 → 管理进展详情|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-005|下次服务|[src/executive_health_ai/ui/pages/member/experience.py:44](../../src/executive_health_ai/ui/pages/member/experience.py#L44) · home|健康运营：下次服务|L1|首页 → 近期安排；服务 → 当前服务|SECONDARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-006|近期趋势与下钻|[src/executive_health_ai/ui/pages/member/experience.py:44](../../src/executive_health_ai/ui/pages/member/experience.py#L44) · home|健康状态：近期趋势与下钻|L2|首页 → 最近变化（两张预览/一个下钻入口）|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-007|上传报告快捷入口|[src/executive_health_ai/ui/pages/member/experience.py:44](../../src/executive_health_ai/ui/pages/member/experience.py#L44) · home|健康状态：上传报告快捷入口|L3|健康 → 体检与检查 → 上传；无资料首页主行动|SECONDARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-008|年度健康基线|[src/executive_health_ai/ui/pages/member/experience.py:109](../../src/executive_health_ai/ui/pages/member/experience.py#L109) · overview|健康状态：年度健康基线|L2|健康概览 P2 → 年度基线/当前比较/主趋势|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-009|基线与当前对比|[src/executive_health_ai/ui/pages/baseline_visualization.py:96](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L96) · render_baseline_progress|健康状态：基线与当前对比|L2|健康概览 P2 → 年度基线/当前比较/主趋势|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-010|基线趋势与指标选择|[src/executive_health_ai/ui/pages/baseline_visualization.py:96](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L96) · render_baseline_progress|健康状态：基线趋势与指标选择|L2|健康概览 P2 → 年度基线/当前比较/主趋势|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-011|基线详细依据与范围|[src/executive_health_ai/ui/pages/baseline_visualization.py:18](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L18) · render_baseline_visualization|健康状态：基线详细依据与范围|L3|健康概览 → 年度基线详情 → 依据/参考范围/修订|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-012|基线修订记录|[src/executive_health_ai/ui/pages/baseline_visualization.py:18](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L18) · render_baseline_visualization|健康状态：基线修订记录|L3|健康概览 → 年度基线详情 → 依据/参考范围/修订|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-013|持续关注事项|[src/executive_health_ai/ui/pages/member/experience.py:109](../../src/executive_health_ai/ui/pages/member/experience.py#L109) · overview|健康运营：持续关注事项|L2|健康概览 → 当前关注|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-014|重要健康背景|[src/executive_health_ai/ui/pages/member/experience.py:109](../../src/executive_health_ai/ui/pages/member/experience.py#L109) · overview|健康状态：重要健康背景|L3|健康 → 健康档案 → 问题/用药/病史/医疗事件|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-015|健康数据与范围|[src/executive_health_ai/ui/pages/health_visualization.py:32](../../src/executive_health_ai/ui/pages/health_visualization.py#L32) · render_health_explorer|健康状态：健康数据与范围|L2|健康 → 健康数据 → 指标与时间范围|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-016|数据来源与记录|[src/executive_health_ai/ui/pages/health_visualization.py:32](../../src/executive_health_ai/ui/pages/health_visualization.py#L32) · render_health_explorer|健康运营：数据来源与记录|L3|健康数据 → 数据来源/详细记录/查看依据|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-017|体检报告与上传|[streamlit_app.py:5919](../../streamlit_app.py#L5919) · _render_client_checkup_page|健康状态：体检报告与上传|L3|健康 → 体检与检查 → 最近报告/历史比较/上传|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-018|跨报告指标趋势|[src/executive_health_ai/ui/pages/health_visualization.py:73](../../src/executive_health_ai/ui/pages/health_visualization.py#L73) · render_report_trends|健康状态：跨报告指标趋势|L3|健康 → 体检与检查 → 最近报告/历史比较/上传|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-019|医疗档案用药病史|[streamlit_app.py:5939](../../streamlit_app.py#L5939) · _render_client_medical_archive|健康状态：医疗档案用药病史|L3|健康 → 健康档案 → 问题/用药/病史/医疗事件|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-020|计划目标与负责人|[src/executive_health_ai/ui/pages/member/experience.py:145](../../src/executive_health_ai/ui/pages/member/experience.py#L145) · plan|健康运营：计划目标与负责人|L1|计划 → 当前目标/任务/执行进度/下个节点|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-021|计划进度|[src/executive_health_ai/ui/pages/member/experience.py:145](../../src/executive_health_ai/ui/pages/member/experience.py#L145) · plan|健康运营：计划进度|L1|计划 → 当前目标/任务/执行进度/下个节点|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-022|接受调整暂缓方案|[src/executive_health_ai/ui/pages/member/experience.py:145](../../src/executive_health_ai/ui/pages/member/experience.py#L145) · plan|健康运营：接受调整暂缓方案|L1|计划 → 当前方案 → 接受/调整/暂缓|SECONDARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-023|任务分类与完成|[src/executive_health_ai/ui/pages/member/experience.py:145](../../src/executive_health_ai/ui/pages/member/experience.py#L145) · plan|健康运营：任务分类与完成|L1|计划 → 当前目标/任务/执行进度/下个节点|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-024|近期节点|[src/executive_health_ai/ui/pages/member/experience.py:145](../../src/executive_health_ai/ui/pages/member/experience.py#L145) · plan|健康运营：近期节点|L1|计划 → 当前目标/任务/执行进度/下个节点|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-025|阶段结果|[src/executive_health_ai/ui/pages/member/experience.py:145](../../src/executive_health_ai/ui/pages/member/experience.py#L145) · plan|长期记录：阶段结果|L2|计划 → 本计划阶段结果；历程 → 对应结果事件|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-026|可用服务与权益|[streamlit_app.py:5753](../../streamlit_app.py#L5753) · _render_client_service|健康运营：可用服务与权益|L1|服务 → 可用服务/申请表|SECONDARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-027|服务申请|[streamlit_app.py:5753](../../streamlit_app.py#L5753) · _render_client_service|健康运营：服务申请|L1|服务 → 可用服务/申请表|SECONDARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-028|当前申请与安排|[streamlit_app.py:5753](../../streamlit_app.py#L5753) · _render_client_service|健康运营：当前申请与安排|L1|服务 → 进行中的申请/安排/下一步|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-029|取消申请|[streamlit_app.py:5753](../../streamlit_app.py#L5753) · _render_client_service|健康运营：取消申请|L3|服务 → 对应申请详情/取消/历史结果|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-030|服务历史结果依据|[streamlit_app.py:5753](../../streamlit_app.py#L5753) · _render_client_service|健康状态：服务历史结果依据|L3|服务 → 对应申请详情/取消/历史结果|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-031|重要健康事件|[src/executive_health_ai/ui/pages/member/experience.py:212](../../src/executive_health_ai/ui/pages/member/experience.py#L212) · _timeline_content|健康运营：重要健康事件|L2|历程 → 重要事件|PRIMARY|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-032|完整时间轴与筛选|[src/executive_health_ai/ui/pages/member/experience.py:25](../../src/executive_health_ai/ui/pages/member/experience.py#L25) / [streamlit_app.py:5001](../../streamlit_app.py#L5001) · render_longitudinal_timeline|长期记录：完整时间轴与筛选|L3|历程 → 完整历程/筛选/事件详情|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-033|个人资料|[streamlit_app.py:5843](../../streamlit_app.py#L5843) · _render_client_profile|健康运营：个人资料|L3|个人设置 → 资料/设备与数据/隐私授权；健康数据来源链接同一设置|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-034|设备Apple健康来源|[streamlit_app.py:5843](../../streamlit_app.py#L5843) · _render_client_profile|健康运营：设备Apple健康来源|L3|个人设置 → 资料/设备与数据/隐私授权；健康数据来源链接同一设置|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MEM-035|隐私授权撤回|[streamlit_app.py:5843](../../streamlit_app.py#L5843) · _render_client_profile|健康运营：隐私授权撤回|L3|个人设置 → 资料/设备与数据/隐私授权；健康数据来源链接同一设置|DETAIL|成员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-001|今日行动数字|[src/executive_health_ai/ui/pages/manager/experience.py:38](../../src/executive_health_ai/ui/pages/manager/experience.py#L38) · today|健康运营：今日行动数字|L1|今日 P3 → 工作摘要/短队列/选中事项处理|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-002|工作队列及类型筛选|[src/executive_health_ai/ui/pages/manager/experience.py:38](../../src/executive_health_ai/ui/pages/manager/experience.py#L38) · today|健康运营：工作队列及类型筛选|L1|今日 P3 → 工作摘要/短队列/选中事项处理|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-003|原因责任截止下一步|[src/executive_health_ai/ui/pages/manager/experience.py:38](../../src/executive_health_ai/ui/pages/manager/experience.py#L38) · today|健康运营：原因责任截止下一步|L1|今日 P3 → 工作摘要/短队列/选中事项处理|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-004|处理工作入口|[src/executive_health_ai/ui/pages/manager/experience.py:38](../../src/executive_health_ai/ui/pages/manager/experience.py#L38) · today|健康运营：处理工作入口|L1|今日 P3 → 工作摘要/短队列/选中事项处理|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-005|超过12项的工作|[src/executive_health_ai/ui/pages/manager/experience.py:38](../../src/executive_health_ai/ui/pages/manager/experience.py#L38) · today|健康运营：超过12项的工作|L1|今日 → 完整队列（保留分页/展开后续事项）|SECONDARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-006|自动跟进及审批|[src/executive_health_ai/ui/pages/manager/experience.py:19](../../src/executive_health_ai/ui/pages/manager/experience.py#L19) · approvals|健康运营：自动跟进及审批|L1|今日待确认事项/成员360管理 → 自动跟进确认|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-007|成员列表|[streamlit_app.py:2883](../../streamlit_app.py#L2883) · render_members_workspace|健康运营：成员列表|L1|成员 → 成员列表|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-008|成员360摘要|[src/executive_health_ai/ui/pages/manager/experience.py:214](../../src/executive_health_ai/ui/pages/manager/experience.py#L214) · member_detail|健康运营：成员360摘要|L2|成员360 P4 → 抬头/基线摘要/趋势/当前安排|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-009|成员360基线摘要|[src/executive_health_ai/ui/pages/manager/experience.py:214](../../src/executive_health_ai/ui/pages/manager/experience.py#L214) · member_detail|健康状态：成员360基线摘要|L2|成员360 P4 → 抬头/基线摘要/趋势/当前安排|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-010|成员360最近趋势|[src/executive_health_ai/ui/pages/manager/experience.py:214](../../src/executive_health_ai/ui/pages/manager/experience.py#L214) · member_detail|健康状态：成员360最近趋势|L2|成员360 P4 → 抬头/基线摘要/趋势/当前安排|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-011|当前计划与服务摘要|[src/executive_health_ai/ui/pages/manager/experience.py:214](../../src/executive_health_ai/ui/pages/manager/experience.py#L214) · member_detail|健康运营：当前计划与服务摘要|L2|成员360 P4 → 抬头/基线摘要/趋势/当前安排|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-012|开放关注事项处理|[src/executive_health_ai/ui/pages/manager/experience.py:214](../../src/executive_health_ai/ui/pages/manager/experience.py#L214) · member_detail|健康运营：开放关注事项处理|L1|成员360 → 开放事项摘要；选中进入唯一处理详情|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-013|成员服务操作|[streamlit_app.py:5687](../../streamlit_app.py#L5687) · render_member_service_management|健康运营：成员服务操作|L1|服务运营/成员360管理 → 服务详情|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-014|健康数据|[streamlit_app.py:4384](../../streamlit_app.py#L4384) · render_member_archive|健康状态：健康数据|L2|成员360健康 → 主趋势/数据记录|PRIMARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-015|报告列表上传确认|[streamlit_app.py:4313](../../streamlit_app.py#L4313) · render_report_upload|健康状态：报告列表上传确认|L3|成员360健康 → 报告详情 → 上传/确认/解析详情|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-016|报告候选人工核对|[streamlit_app.py:4001](../../streamlit_app.py#L4001) · render_report_review|健康状态：报告候选人工核对|L3|成员360健康 → 报告详情 → 上传/确认/解析详情|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-017|报告解析与重跑|[streamlit_app.py:4001](../../streamlit_app.py#L4001) · render_report_review|健康状态：报告解析与重跑|L3|成员360健康 → 报告详情 → 上传/确认/解析详情|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-018|年度基线建立确认冻结|[streamlit_app.py:4448](../../streamlit_app.py#L4448) · render_health_assessments|健康状态：年度基线建立确认冻结|L2|成员360健康 → 年度基线详情 → 建立/确认/修订/年度|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-019|基线修订年度切换|[streamlit_app.py:4448](../../streamlit_app.py#L4448) · render_health_assessments|健康状态：基线修订年度切换|L2|成员360健康 → 年度基线详情 → 建立/确认/修订/年度|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-020|健康史|[streamlit_app.py:4384](../../streamlit_app.py#L4384) · render_member_archive|健康状态：健康史|L3|成员360健康 → 健康档案/健康史|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-021|当前管理计划选择|[src/executive_health_ai/ui/pages/manager/experience.py:120](../../src/executive_health_ai/ui/pages/manager/experience.py#L120) · management|健康运营：当前管理计划选择|L1|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-022|建立调整计划|[src/executive_health_ai/ui/pages/manager/experience.py:120](../../src/executive_health_ai/ui/pages/manager/experience.py#L120) · management|健康运营：建立调整计划|L1|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-023|安排随访|[src/executive_health_ai/ui/pages/manager/experience.py:120](../../src/executive_health_ai/ui/pages/manager/experience.py#L120) · management|健康运营：安排随访|L1|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-024|阶段结果录入与下一步|[src/executive_health_ai/ui/pages/manager/experience.py:120](../../src/executive_health_ai/ui/pages/manager/experience.py#L120) · management|长期记录：阶段结果录入与下一步|L1|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-025|执行任务|[streamlit_app.py:1767](../../streamlit_app.py#L1767) · render_tasks|健康运营：执行任务|L1|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-026|计划详情阶段结果|[streamlit_app.py:2612](../../streamlit_app.py#L2612) · render_programs|长期记录：计划详情阶段结果|L1|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-027|自动跟进健康管理信号|[streamlit_app.py:2676](../../streamlit_app.py#L2676) · render_member_management_signals|健康运营：自动跟进健康管理信号|L1|成员360管理 → 当前计划/任务/随访/阶段结果/自动跟进|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-028|成员医疗上下文|[streamlit_app.py:4345](../../streamlit_app.py#L4345) · render_member_medical_workspace|健康运营：成员医疗上下文|L1|医疗协同/成员360医疗 → 同源复核/转诊/医学依据|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-029|内部医生协同|[streamlit_app.py:3749](../../streamlit_app.py#L3749) · render_collaboration_workspace|健康运营：内部医生协同|L1|医疗协同/成员360医疗 → 同源复核/转诊/医学依据|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-030|外部医生转诊|[streamlit_app.py:6041](../../streamlit_app.py#L6041) · render_external_doctor_workspace|健康运营：外部医生转诊|L1|医疗协同/成员360医疗 → 同源复核/转诊/医学依据|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-031|服务运营队列|[streamlit_app.py:3760](../../streamlit_app.py#L3760) · render_service_operations_workspace|健康运营：服务运营队列|L1|服务运营/成员360管理 → 服务详情|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-032|服务审核安排完成|[streamlit_app.py:5687](../../streamlit_app.py#L5687) · render_member_service_management|健康运营：服务审核安排完成|L1|服务运营/成员360管理 → 服务详情|DETAIL|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|MGR-033|知识检索与资料|[streamlit_app.py:3424](../../streamlit_app.py#L3424) · render_knowledge_library_entry|健康运营：知识检索与资料|L3|更多 → 专业资料；事项旁查看引用|SECONDARY|健管|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-001|复核队列与已完成|[src/executive_health_ai/ui/pages/doctor/experience.py:94](../../src/executive_health_ai/ui/pages/doctor/experience.py#L94) / [src/executive_health_ai/ui/pages/admin/experience.py:44](../../src/executive_health_ai/ui/pages/admin/experience.py#L44) · workspace|健康运营：复核队列与已完成|L1|待我复核/历史 → 问题队列|PRIMARY|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-002|医学问题与提交信息|[src/executive_health_ai/ui/pages/doctor/experience.py:15](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15) · detail|健康运营：医学问题与提交信息|L1|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-003|成员背景年度基线|[src/executive_health_ai/ui/pages/doctor/experience.py:15](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15) · detail|健康状态：成员背景年度基线|L1|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-004|关键指标用药|[src/executive_health_ai/ui/pages/doctor/experience.py:15](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15) · detail|健康状态：关键指标用药|L1|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-005|相关趋势|[src/executive_health_ai/ui/pages/health_visualization.py:90](../../src/executive_health_ai/ui/pages/health_visualization.py#L90) · render_doctor_trend|健康状态：相关趋势|L1|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-006|证据完整性与原文|[src/executive_health_ai/ui/experience.py:182](../../src/executive_health_ai/ui/experience.py#L182) · evidence_summary|健康运营：证据完整性与原文|L1|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-007|完整资料位置核对|[src/executive_health_ai/ui/pages/doctor/experience.py:15](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15) · detail|健康运营：完整资料位置核对|L3|医生复核 → 完整资料/既有行动展开|DETAIL|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-008|已采取行动|[src/executive_health_ai/ui/pages/doctor/experience.py:15](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15) · detail|健康运营：已采取行动|L3|医生复核 → 完整资料/既有行动展开|DETAIL|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-009|人工意见与交回|[src/executive_health_ai/ui/pages/doctor/experience.py:15](../../src/executive_health_ai/ui/pages/doctor/experience.py#L15) · detail|健康运营：人工意见与交回|L1|医生复核 P5 → 问题/背景趋势/依据/人工结论与交接|PRIMARY|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-010|旧警报基线医学确认|[src/executive_health_ai/ui/pages/doctor/experience.py:94](../../src/executive_health_ai/ui/pages/doctor/experience.py#L94) / [src/executive_health_ai/ui/pages/admin/experience.py:44](../../src/executive_health_ai/ui/pages/admin/experience.py#L44) · workspace|健康状态：旧警报基线医学确认|L1|待我复核 → 年度基线/旧警报/后续安排确认，分别说明任务性质|DETAIL|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|DOC-011|医生审批|[src/executive_health_ai/ui/pages/manager/experience.py:19](../../src/executive_health_ai/ui/pages/manager/experience.py#L19) · approvals|健康运营：医生审批|L1|待我复核 → 年度基线/旧警报/后续安排确认，分别说明任务性质|DETAIL|医生|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-001|集成状态与检查|[src/executive_health_ai/ui/pages/admin/experience.py:11](../../src/executive_health_ai/ui/pages/admin/experience.py#L11) · integrations|支撑能力：集成状态与检查|L4|系统状态 P6 → 集成与运行状态概况|PRIMARY|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-002|数据包模板上传检查|[streamlit_app.py:3487](../../streamlit_app.py#L3487) · _render_data_package_import|支撑能力：数据包模板上传检查|L4|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-003|预览确认正式写入|[streamlit_app.py:3487](../../streamlit_app.py#L3487) · _render_data_package_import|支撑能力：预览确认正式写入|L4|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-004|AI配置测试|[streamlit_app.py:3606](../../streamlit_app.py#L3606) · _render_ai_service_integration|支撑能力：AI配置测试|L4|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-005|专业知识Adapter与审核|[streamlit_app.py:3640](../../streamlit_app.py#L3640) · _render_knowledge_service_integration|支撑能力：专业知识Adapter与审核|L4|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-006|设备测试导入|[streamlit_app.py:3715](../../streamlit_app.py#L3715) · _render_device_integration|支撑能力：设备测试导入|L4|集成与数据 → 选中服务 → 配置/检查/测试/预览/确认|DETAIL|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-007|自动化目标等待状态|[streamlit_app.py:319](../../streamlit_app.py#L319) · _render_admin_automation|支撑能力：自动化目标等待状态|L4|自动化运营 → 选中过程 → 等待/异常/人工操作|DETAIL|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-008|人工接手恢复取消|[streamlit_app.py:319](../../streamlit_app.py#L319) · _render_admin_automation|支撑能力：人工接手恢复取消|L4|自动化运营 → 选中过程 → 等待/异常/人工操作|DETAIL|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-009|Trace技术诊断|[streamlit_app.py:319](../../streamlit_app.py#L319) · _render_admin_automation|支撑能力：Trace技术诊断|L4|自动化运营 → 对应过程 → 高级诊断/Trace|ADVANCED|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-010|风险规则配置|[streamlit_app.py:6312](../../streamlit_app.py#L6312) · render_risk_rules|支撑能力：风险规则配置|L4|规则与知识 → 风险规则|DETAIL|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-011|系统连接状态|[src/executive_health_ai/ui/pages/admin/experience.py:44](../../src/executive_health_ai/ui/pages/admin/experience.py#L44) / [src/executive_health_ai/ui/pages/doctor/experience.py:94](../../src/executive_health_ai/ui/pages/doctor/experience.py#L94) · workspace|支撑能力：系统连接状态|L4|系统状态 P6 → 集成与运行状态概况|PRIMARY|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-012|审计记录|[streamlit_app.py:2578](../../streamlit_app.py#L2578) · render_audit|支撑能力：审计记录|L4|系统状态 → 操作记录|DETAIL|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-013|反馈质量治理|[src/executive_health_ai/ui/pages/ai_improvement.py:25](../../src/executive_health_ai/ui/pages/ai_improvement.py#L25) · render_ai_improvement|支撑能力：反馈质量治理|L4|系统状态 → AI质量治理（高级）|ADVANCED|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-014|旧健康图表与数据网关|[streamlit_app.py:2414](../../streamlit_app.py#L2414) · render_health_data|支撑能力：旧健康图表与数据网关|L4|系统状态 → 兼容工具 → 同名原工具|LEGACY|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|ADM-015|监管及演示旧详情|[streamlit_app.py:3737](../../streamlit_app.py#L3737) · render_oversight_summary|支撑能力：监管及演示旧详情|L4|系统状态 → 兼容工具 → 同名原工具|LEGACY|管理员|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|V2-001|健康团队只读摘要|[src/executive_health_ai/ui/components.py:22](../../src/executive_health_ai/ui/components.py#L22) · care_team|健康运营：健康团队只读摘要|L2|首页管理摘要及近期安排 → 健康团队|PRIMARY|按原角色|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|V2-002|演示角色切换|[streamlit_app.py:396](../../streamlit_app.py#L396) · _render_surface_switcher|支撑能力：演示角色切换|L4|演示入口/角色预览菜单|SECONDARY|按原角色|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|V2-003|全指标比较表|[src/executive_health_ai/ui/pages/baseline_visualization.py:162](../../src/executive_health_ai/ui/pages/baseline_visualization.py#L162) · _render_comparison_details|健康状态：全指标比较表|L2|健康概览 → 全指标基线与当前对比|DETAIL|按原角色|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|V2-004|健管查找与事项选择|[src/executive_health_ai/ui/pages/manager/experience.py:38](../../src/executive_health_ai/ui/pages/manager/experience.py#L38) · today|健康运营：健管查找与事项选择|L1|今日 → 队列筛选与选中事项|PRIMARY|按原角色|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|V2-005|360随访与结果快捷入口|[src/executive_health_ai/ui/pages/manager/experience.py:214](../../src/executive_health_ai/ui/pages/manager/experience.py#L214) · member_detail|健康运营：360随访与结果快捷入口|L1|成员360 → 当前下一步主动作/管理详情|SECONDARY|按原角色|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|V2-006|十五项历史兼容工具|[src/executive_health_ai/ui/pages/admin/experience.py:77](../../src/executive_health_ai/ui/pages/admin/experience.py#L77) · legacy_tools|支撑能力：十五项历史兼容工具|L4|系统状态 → 兼容工具目录（15个子项逐项见LEG）|LEGACY|按原角色|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|V2-007|所有自动化目标明细|[streamlit_app.py:319](../../streamlit_app.py#L319) · _render_admin_automation|支撑能力：所有自动化目标明细|L4|自动化运营 → 全部目标详情|ADVANCED|按原角色|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|V2-008|近期与完整历程展开|[src/executive_health_ai/ui/pages/member/experience.py:212](../../src/executive_health_ai/ui/pages/member/experience.py#L212) · _timeline_content|长期记录：近期与完整历程展开|L3|历程 → 更多重要事件/完整历程|DETAIL|按原角色|同源引用角色；不新增权限|保留业务能力；按任务优先级与所属上下文分层|YES|
|LEG-001|健康数据完整视图|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 健康数据完整视图|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-002|报告比较|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 报告比较|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-003|干预前后比较|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 干预前后比较|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-004|风险监管摘要|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 风险监管摘要|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-005|数据接入网关|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 数据接入网关|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-006|成员设备分配|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 成员设备分配|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-007|演示路径|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 演示路径|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-008|完整成员摘要|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 完整成员摘要|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-009|历史健康问题|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 历史健康问题|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-010|历史医疗记录|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 历史医疗记录|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-011|全部异常处理|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 全部异常处理|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-012|原始观测详情|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 原始观测详情|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-013|数据来源详情|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 数据来源详情|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-014|阶段结果详情|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 阶段结果详情|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|LEG-015|历史时间轴|系统状态/高级信息·兼容工具 · admin/experience.py::legacy_tools|历史完整功能及核对|L4|系统状态 → 兼容工具 → 历史时间轴|LEGACY|管理员|授权工作人员|具名保留；不作日常业务必经入口|YES|
|NAV-001|Member主导航/健康四视图|成员侧栏与健康radio|入口与局部视图全部保留|L1|成员：首页/健康/计划/服务/历程|PRIMARY|成员|无|减少导航同权，不删除任何内容|YES|
|NAV-002|Manager主导航/360五视图|健管侧栏与成员详情radio|入口与局部视图全部保留|L1|健管：今日/成员/医疗协同/服务/更多|PRIMARY|健管|无|减少导航同权，不删除任何内容|YES|
|NAV-003|Doctor队列筛选|医生workspace|入口与局部视图全部保留|L1|医生：待我复核/历史|PRIMARY|医生|无|减少导航同权，不删除任何内容|YES|
|NAV-004|Admin系统四分区|管理员workspace|入口与局部视图全部保留|L4|管理员：系统状态/集成与数据/自动化运营/规则与知识|PRIMARY|管理员|无|减少导航同权，不删除任何内容|YES|

## 保留约束

所有表格/表单/按钮/图表的具体声明均在03A编号；动态记录实例不逐人复制编号。原文/引用/来源定位、基线修订、完整时间轴、旧健康图与治理流程保留。零点/单点/等待/错误状态也随原组件保留。本轮的100%指静态盘点元素已分配设计归属，**不代表尚未实现的新路由已通过运行验收**。

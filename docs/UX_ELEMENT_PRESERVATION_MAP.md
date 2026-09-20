# UX Element Preservation Map

盘点时间：2026-09-19；产品修改前基于 `62d9ae3`。

业务要素组：**94**；底层UI调用点：**1215**。组数与控件调用点不混算。动态列表按一个模板编号，实际每条数据不算新功能。HTML内部文本归属其renderer。

每项作用即名称所述的查看/操作能力；原数据、服务调用及详细字段保留。尚未接通旧函数的入口列为高级兼容，不能用保留代码冒充可达。实现后逐项核对路径并在Visual QA记录结果。

## 实现后核对

94 / 94业务要素组保留：KEEP 62、MOVE 13、MERGE 7、COLLAPSE 5、SECONDARY 2、ADVANCED 5；移除0，缺失0。附录1,215项是改版前唯一调用点快照，不是1,215个独立功能或1,215次浏览器点击。

语义保留采用下表的新路径；标签、布局及组件允许替换。原UI函数集合由自动化核对；成员/健管/医生/管理员关键路径由AppTest和Chromium检查；15个兼容工具逐个运行。没有更改后端事实表、医疗规则、业务服务或Agent模型。具体截图和验收范围见 `UX_V2_VISUAL_QA.md`，不把静态函数存在本身当作视觉通过。

|Element ID|当前名称 / 作用|当前位置|新位置|处理|原Renderer|
|---|---|---|---|---|---|
|MEM-001|首页今日行动|首页|首页主行动与其他今日行动|MOVE|home|
|MEM-002|管理周期与阶段|首页|首页管理摘要与详情|MERGE|home|
|MEM-003|负责人及下一步|首页|首页照护团队与行动区|MOVE|home|
|MEM-004|自动跟进状态|首页|首页管理进展详情|COLLAPSE|home|
|MEM-005|下次服务|首页|首页近期事项|KEEP|home|
|MEM-006|近期趋势与下钻|首页|首页双趋势与查看趋势|KEEP|home|
|MEM-007|上传报告快捷入口|首页|首页常用入口|SECONDARY|home|
|MEM-008|年度健康基线|健康概览|健康概览顶部|KEEP|overview|
|MEM-009|基线与当前对比|健康概览|主趋势下方完整比较|COLLAPSE|render_baseline_progress|
|MEM-010|基线趋势与指标选择|健康概览|健康概览主视觉|MOVE|render_baseline_progress|
|MEM-011|基线详细依据与范围|年度基线|年度基线详情|KEEP|render_baseline_visualization|
|MEM-012|基线修订记录|年度基线|年度基线详情|KEEP|render_baseline_visualization|
|MEM-013|持续关注事项|健康概览|趋势后关注列表|KEEP|overview|
|MEM-014|重要健康背景|健康概览|健康背景展开区|COLLAPSE|overview|
|MEM-015|健康数据与范围|健康数据|健康数据指标工作区|KEEP|render_health_explorer|
|MEM-016|数据来源与记录|健康数据|图下来源展开区|KEEP|render_health_explorer|
|MEM-017|体检报告与上传|健康体检|健康体检最近结果与上传|KEEP|_render_client_checkup_page|
|MEM-018|跨报告指标趋势|健康体检|健康体检历史比较|KEEP|render_report_trends|
|MEM-019|医疗档案用药病史|健康医疗档案|健康医疗档案|KEEP|_render_client_medical_archive|
|MEM-020|计划目标与负责人|计划|计划目标摘要带|MERGE|plan|
|MEM-021|计划进度|计划|计划执行进度|KEEP|plan|
|MEM-022|接受调整暂缓方案|计划|方案选择展开区|KEEP|plan|
|MEM-023|任务分类与完成|计划|当前任务列表|KEEP|plan|
|MEM-024|近期节点|计划|任务旁近期节点|MOVE|plan|
|MEM-025|阶段结果|计划|任务旁阶段复盘|MOVE|plan|
|MEM-026|可用服务与权益|服务默认|服务可用服务页签|SECONDARY|_render_client_service|
|MEM-027|服务申请|服务|服务可用服务详情|KEEP|_render_client_service|
|MEM-028|当前申请与安排|服务我的申请|服务默认当前申请|MOVE|_render_client_service|
|MEM-029|取消申请|服务详情|当前申请详情|KEEP|_render_client_service|
|MEM-030|服务历史结果依据|服务记录|服务记录页签|KEEP|_render_client_service|
|MEM-031|重要健康事件|历程|日期轨道列表|MERGE|_timeline_content|
|MEM-032|完整时间轴与筛选|历程详情|查看完整历程与依据|KEEP|render_longitudinal_timeline|
|MEM-033|个人资料|个人设置|右上个人设置|KEEP|_render_client_profile|
|MEM-034|设备Apple健康来源|个人设置|个人设置设备与数据|KEEP|_render_client_profile|
|MEM-035|隐私授权撤回|个人设置|个人设置隐私授权|KEEP|_render_client_profile|
|MGR-001|今日行动数字|今日|今日摘要带|MERGE|today|
|MGR-002|工作队列及类型筛选|今日|左列表与筛选|MOVE|today|
|MGR-003|原因责任截止下一步|今日每行|右侧事项详情|MOVE|today|
|MGR-004|处理工作入口|今日|选中事项处理|KEEP|today|
|MGR-005|超过12项的工作|今日其他事项|队列其他事项分页/展开|KEEP|today|
|MGR-006|自动跟进及审批|今日与管理|今日详情展开与管理审批|KEEP|approvals|
|MGR-007|成员列表|成员|成员列表|KEEP|render_members_workspace|
|MGR-008|成员360摘要|成员详情|成员360上下文头|MERGE|member_detail|
|MGR-009|成员360基线摘要|概览|概览完整基线展开|COLLAPSE|member_detail|
|MGR-010|成员360最近趋势|概览底部|概览主要区域|MOVE|member_detail|
|MGR-011|当前计划与服务摘要|概览|趋势旁管理摘要|MOVE|member_detail|
|MGR-012|开放关注事项处理|概览|概览关注处理展开|KEEP|member_detail|
|MGR-013|成员服务操作|概览|概览服务展开与管理快捷入口|KEEP|render_member_service_management|
|MGR-014|健康数据|成员健康|成员健康数据|KEEP|render_member_archive|
|MGR-015|报告列表上传确认|成员体检|成员健康体检|KEEP|render_report_upload|
|MGR-016|报告候选人工核对|报告详情|体检审核详情|KEEP|render_report_review|
|MGR-017|报告解析与重跑|报告高级|报告高级信息|ADVANCED|render_report_review|
|MGR-018|年度基线建立确认冻结|成员基线|成员健康基线|KEEP|render_health_assessments|
|MGR-019|基线修订年度切换|成员基线|基线详情与修订|KEEP|render_health_assessments|
|MGR-020|健康史|成员健康|成员健康史|KEEP|render_member_archive|
|MGR-021|当前管理计划选择|成员管理|管理摘要与计划选择|KEEP|management|
|MGR-022|建立调整计划|成员管理|管理表单与360快捷入口|KEEP|management|
|MGR-023|安排随访|成员管理|管理随访表单与快捷入口|KEEP|management|
|MGR-024|阶段结果录入与下一步|成员管理|管理结果表单与快捷入口|KEEP|management|
|MGR-025|执行任务|成员管理|管理工作进展|KEEP|render_tasks|
|MGR-026|计划详情阶段结果|成员管理|工作进展详情展开|KEEP|render_programs|
|MGR-027|自动跟进健康管理信号|成员管理|管理记录展开|KEEP|render_member_management_signals|
|MGR-028|成员医疗上下文|成员医疗|成员医疗|KEEP|render_member_medical_workspace|
|MGR-029|内部医生协同|医疗协同|统一医生队列只读|KEEP|render_collaboration_workspace|
|MGR-030|外部医生转诊|医疗协同|外部医疗|KEEP|render_external_doctor_workspace|
|MGR-031|服务运营队列|服务运营|服务工作台|KEEP|render_service_operations_workspace|
|MGR-032|服务审核安排完成|服务详情|原上下文服务操作|KEEP|render_member_service_management|
|MGR-033|知识检索与资料|更多|更多专业资料|KEEP|render_knowledge_library_entry|
|DOC-001|复核队列与已完成|医生工作台|队列筛选与选择|KEEP|workspace|
|DOC-002|医学问题与提交信息|复核详情|详情首屏问题带|MOVE|detail|
|DOC-003|成员背景年度基线|复核详情|临床上下文展开区|COLLAPSE|detail|
|DOC-004|关键指标用药|复核详情|左侧临床上下文|MOVE|detail|
|DOC-005|相关趋势|复核详情|左侧主要图表|KEEP|render_doctor_trend|
|DOC-006|证据完整性与原文|复核详情|左侧报告依据|KEEP|evidence_summary|
|DOC-007|完整资料位置核对|复核详情|依据高级展开|KEEP|detail|
|DOC-008|已采取行动|复核详情|临床背景展开|KEEP|detail|
|DOC-009|人工意见与交回|复核详情底部|右侧结论与执行交接|MOVE|detail|
|DOC-010|旧警报基线医学确认|复核队列|原兼容复核分支|KEEP|workspace|
|DOC-011|医生审批|复核详情|选中成员审批区|KEEP|approvals|
|ADM-001|集成状态与检查|集成中心|左连接列表右操作|MERGE|integrations|
|ADM-002|数据包模板上传检查|集成数据|集成数据导入|KEEP|_render_data_package_import|
|ADM-003|预览确认正式写入|集成数据|集成数据导入确认|KEEP|_render_data_package_import|
|ADM-004|AI配置测试|集成AI|集成AI操作区|KEEP|_render_ai_service_integration|
|ADM-005|专业知识Adapter与审核|集成知识|集成专业知识与规则知识|KEEP|_render_knowledge_service_integration|
|ADM-006|设备测试导入|集成设备|集成设备与规则知识|KEEP|_render_device_integration|
|ADM-007|自动化目标等待状态|自动化运营|自动化状态与选中目标|MERGE|_render_admin_automation|
|ADM-008|人工接手恢复取消|自动化运营|目标详情操作|KEEP|_render_admin_automation|
|ADM-009|Trace技术诊断|自动化高级|自动化高级信息|ADVANCED|_render_admin_automation|
|ADM-010|风险规则配置|规则知识|规则与知识规则页|KEEP|render_risk_rules|
|ADM-011|系统连接状态|系统状态|系统状态摘要|KEEP|workspace|
|ADM-012|审计记录|系统状态|系统操作记录展开|KEEP|render_audit|
|ADM-013|反馈质量治理|系统高级|AI质量治理高级|ADVANCED|render_ai_improvement|
|ADM-014|旧健康图表与数据网关|旧函数兼容层|系统高级兼容工具|ADVANCED|render_health_data|
|ADM-015|监管及演示旧详情|旧函数兼容层|系统高级兼容工具|ADVANCED|render_oversight_summary|

## 所有底层可见要素（修改前快照）

包含导航选项、页签、表单、输入、按钮、图表、表格、状态与空态。每个调用点具有独立ID。精确原文/完整表达式和源码位置见 `ux_v2_widget_inventory.json`。未单独迁移的调用点KEEP并继承上表其renderer路径；旧专用renderer归入管理员兼容工具。

|ID|文件 / 函数|类型|原标签 / 内容表达式|处理|
|---|---|---|---|---|
|UI-0001|streamlit_app.py:176 `_status_pill`|status_badge|status|KEEP / 继承所属要素组迁移|
|UI-0002|streamlit_app.py:313 `_render_member_automation_status`|caption|f"下一步：{goal.next_action or '健康管理团队继续跟进'} · 负责人：{goal.owner or '健康管理团队'}"|KEEP / 继承所属要素组迁移|
|UI-0003|streamlit_app.py:315 `_render_member_automation_status`|caption|'下一检查：' + _fmt_dt(goal.next_check_at)|KEEP / 继承所属要素组迁移|
|UI-0004|streamlit_app.py:335 `_render_admin_automation`|dataframe|pd.DataFrame([{'成员': _member_display(members.get(goal.member_id)), '目标': goal.title, '当前阶段': goal.current_stage, '状态': GOAL_LABELS.get(goal.status, '进行中'), '负责人': goal.owner or '待分|KEEP / 继承所属要素组迁移|
|UI-0005|streamlit_app.py:341 `_render_admin_automation`|selectbox|'查看目标'|KEEP / 继承所属要素组迁移|
|UI-0006|streamlit_app.py:343 `_render_admin_automation`|caption|'下一步：' + (selected.next_action or '等待人工确认')|KEEP / 继承所属要素组迁移|
|UI-0007|streamlit_app.py:345 `_render_admin_automation`|button|'人工接手'|KEEP / 继承所属要素组迁移|
|UI-0008|streamlit_app.py:350 `_render_admin_automation`|button|'恢复自动跟进'|KEEP / 继承所属要素组迁移|
|UI-0009|streamlit_app.py:355 `_render_admin_automation`|button|'取消目标'|KEEP / 继承所属要素组迁移|
|UI-0010|streamlit_app.py:361 `_render_admin_automation`|caption|f'当前有 {len(pending_approvals)} 项等待人工确认。'|KEEP / 继承所属要素组迁移|
|UI-0011|streamlit_app.py:362 `_render_admin_automation`|expander|'高级信息'|KEEP / 继承所属要素组迁移|
|UI-0012|streamlit_app.py:363 `_render_admin_automation`|caption|'仅管理员排障使用；普通成员、健管与医生页面不会显示技术执行明细。'|KEEP / 继承所属要素组迁移|
|UI-0013|streamlit_app.py:349 `_render_admin_automation`|success|'自动跟进已暂停，当前事项保留供人工处理。'|KEEP / 继承所属要素组迁移|
|UI-0014|streamlit_app.py:354 `_render_admin_automation`|success|'已恢复自动跟进。'|KEEP / 继承所属要素组迁移|
|UI-0015|streamlit_app.py:359 `_render_admin_automation`|success|'目标已取消并保留审计记录。'|KEEP / 继承所属要素组迁移|
|UI-0016|streamlit_app.py:367 `_render_admin_automation`|dataframe|pd.DataFrame([{'动作': row.action, '状态': row.status, '时间': _fmt_dt(row.started_at), '结果': row.result_summary or row.error_summary or '已记录'} for row in traces])|KEEP / 继承所属要素组迁移|
|UI-0017|streamlit_app.py:377 `_render_timed`|warning|'[PERF] renderer:%s %.1f ms'|KEEP / 继承所属要素组迁移|
|UI-0018|streamlit_app.py:382 `_render_sidebar_navigation`|caption|'健康管理师工作区'|KEEP / 继承所属要素组迁移|
|UI-0019|streamlit_app.py:388 `_render_sidebar_navigation`|radio|'工作区'|KEEP / 继承所属要素组迁移|
|UI-0020|streamlit_app.py:397 `_render_surface_switcher`|radio|'当前视图'|KEEP / 继承所属要素组迁移|
|UI-0021|streamlit_app.py:398 `_render_surface_switcher`|caption|'演示角色预览 · 不代表登录鉴权'|KEEP / 继承所属要素组迁移|
|UI-0022|streamlit_app.py:405 `_render_member_center_navigation`|caption|'看状态、健康资料、计划与服务'|KEEP / 继承所属要素组迁移|
|UI-0023|streamlit_app.py:407 `_render_member_center_navigation`|radio|'成员健康中心导航'|KEEP / 继承所属要素组迁移|
|UI-0024|streamlit_app.py:433 `_page_header`|page_header|title|KEEP / 继承所属要素组迁移|
|UI-0025|streamlit_app.py:440 `page_header`|title|title|KEEP / 继承所属要素组迁移|
|UI-0026|streamlit_app.py:441 `page_header`|caption|guidance|KEEP / 继承所属要素组迁移|
|UI-0027|streamlit_app.py:445 `_section_header`|subheader|title|KEEP / 继承所属要素组迁移|
|UI-0028|streamlit_app.py:447 `_section_header`|caption|guidance|KEEP / 继承所属要素组迁移|
|UI-0029|streamlit_app.py:456 `section_frame`|caption|guidance|KEEP / 继承所属要素组迁移|
|UI-0030|streamlit_app.py:486 `risk_badge`|status_badge|labels.get(str(level or '').upper(), '暂无正式风险评估')|KEEP / 继承所属要素组迁移|
|UI-0031|streamlit_app.py:504 `primary_action`|button|label|KEEP / 继承所属要素组迁移|
|UI-0032|streamlit_app.py:508 `secondary_action`|button|label|KEEP / 继承所属要素组迁移|
|UI-0033|streamlit_app.py:517 `detail_panel`|caption|note|KEEP / 继承所属要素组迁移|
|UI-0034|streamlit_app.py:527 `work_item_card`|status_badge|status|KEEP / 继承所属要素组迁移|
|UI-0035|streamlit_app.py:545 `member_card`|status_badge|status|KEEP / 继承所属要素组迁移|
|UI-0036|streamlit_app.py:768 `_render_snapshot_item_evidence`|expander|'逐项查看依据'|KEEP / 继承所属要素组迁移|
|UI-0037|streamlit_app.py:779 `_render_snapshot_item_evidence`|caption|f"依据：建立基线前30天的有效健康数据汇总 · {item.get('sample_count', 0)}条 · 最近数据：{str(item.get('latest_observed_at') or '未记录')[:10]}"|KEEP / 继承所属要素组迁移|
|UI-0038|streamlit_app.py:784 `_render_snapshot_item_evidence`|caption|'依据：已确认的健康档案记录；详细原始记录保留在对应健康史或用药记录中。'|KEEP / 继承所属要素组迁移|
|UI-0039|streamlit_app.py:789 `_render_metric_evidence`|caption|'该指标的来源保留在已确认健康记录中；当前没有可单独展示的报告区间。'|KEEP / 继承所属要素组迁移|
|UI-0040|streamlit_app.py:791 `_render_metric_evidence`|expander|'查看该指标依据'|KEEP / 继承所属要素组迁移|
|UI-0041|streamlit_app.py:902 `render_evidence_panel`|caption|'来源说明：' + str(evidence['source_note'])|KEEP / 继承所属要素组迁移|
|UI-0042|streamlit_app.py:908 `render_evidence_panel`|caption|'当前未保存可展示的原文片段。'|KEEP / 继承所属要素组迁移|
|UI-0043|streamlit_app.py:931 `render_evidence_panel`|caption|'当前仅保存识别文字，暂无原始区域定位。'|KEEP / 继承所属要素组迁移|
|UI-0044|streamlit_app.py:896 `render_evidence_panel`|download_button|'查看完整文件'|KEEP / 继承所属要素组迁移|
|UI-0045|streamlit_app.py:898 `render_evidence_panel`|caption|'来源文件当前不可直接打开。'|KEEP / 继承所属要素组迁移|
|UI-0046|streamlit_app.py:941 `render_evidence_panel`|caption|'本结果基于当前健康资料整理，未使用额外医疗规范。'|KEEP / 继承所属要素组迁移|
|UI-0047|streamlit_app.py:920 `render_evidence_panel`|dataframe|pd.DataFrame({'相关表格行': [row]})|KEEP / 继承所属要素组迁移|
|UI-0048|streamlit_app.py:916 `render_evidence_panel`|dataframe|pd.DataFrame([dict(zip(header_cells, row_cells))])|KEEP / 继承所属要素组迁移|
|UI-0049|streamlit_app.py:918 `render_evidence_panel`|dataframe|pd.DataFrame({'相关表格行': [row]})|KEEP / 继承所属要素组迁移|
|UI-0050|streamlit_app.py:926 `render_evidence_panel`|caption|'当前已保存识别文字，但尚未保存精确图片区域定位。'|KEEP / 继承所属要素组迁移|
|UI-0051|streamlit_app.py:950 `render_evidence_panel`|expander|'高级信息'|KEEP / 继承所属要素组迁移|
|UI-0052|streamlit_app.py:951 `render_evidence_panel`|dataframe|pd.DataFrame([{{'rule_code': '规则编号', 'risk_event_id': '风险记录编号'}.get(key, key): value for key, value in technical.items() if value not in {None, ''}}])|KEEP / 继承所属要素组迁移|
|UI-0053|streamlit_app.py:960 `evidence_action`|button|'查看依据'|KEEP / 继承所属要素组迁移|
|UI-0054|streamlit_app.py:984 `_render_related_knowledge`|expander|'相关医学参考'|KEEP / 继承所属要素组迁移|
|UI-0055|streamlit_app.py:985 `_render_related_knowledge`|caption|'仅显示已批准、未归档且未过期的资料，用于解释与人工参考；不会改变风险、诊断、处方或医疗规则。'|KEEP / 继承所属要素组迁移|
|UI-0056|streamlit_app.py:987 `_render_related_knowledge`|info|'当前没有可引用的已批准资料。'|KEEP / 继承所属要素组迁移|
|UI-0057|streamlit_app.py:992 `_render_related_knowledge`|caption|f"{citation['source'] or '来源待补充'} · {citation['location'] or '位置待补充'} · 获取时间：{citation['retrieved_at'] or '未记录'}"|KEEP / 继承所属要素组迁移|
|UI-0058|streamlit_app.py:996 `_render_related_knowledge`|link_button|'查看官方来源'|KEEP / 继承所属要素组迁移|
|UI-0059|streamlit_app.py:1005 `_section_frame`|caption|guidance|KEEP / 继承所属要素组迁移|
|UI-0060|streamlit_app.py:1024 `_navigation_stage`|warning|'[PERF] %s %.1f ms'|KEEP / 继承所属要素组迁移|
|UI-0061|streamlit_app.py:1177 `_render_current_risk_actions`|subheader|'紧急处置'|KEEP / 继承所属要素组迁移|
|UI-0062|streamlit_app.py:1178 `_render_current_risk_actions`|error|'医疗处置优先。请先确认成员当前安全情况并按实际情况寻求医疗帮助。'|KEEP / 继承所属要素组迁移|
|UI-0063|streamlit_app.py:1180 `_render_current_risk_actions`|caption|f'发现时间：{_fmt_dt(event.created_at)} · {_risk_event_evidence_caption(event)}'|KEEP / 继承所属要素组迁移|
|UI-0064|streamlit_app.py:1189 `_render_current_risk_actions`|link_button|'使用设备拨打120'|KEEP / 继承所属要素组迁移|
|UI-0065|streamlit_app.py:1190 `_render_current_risk_actions`|button|'记录已开始紧急处置'|KEEP / 继承所属要素组迁移|
|UI-0066|streamlit_app.py:1197 `_render_current_risk_actions`|caption|'请使用可拨号设备操作。如无法直接拨号，请使用手机拨打120；系统不会自动拨号或联系任何人。'|KEEP / 继承所属要素组迁移|
|UI-0067|streamlit_app.py:1187 `_render_current_risk_actions`|caption|f'紧急联系人：{contacts[0].name}（{contacts[0].relationship}，合成演示联系人）'|KEEP / 继承所属要素组迁移|
|UI-0068|streamlit_app.py:1195 `_render_current_risk_actions`|success|'已记录紧急处置开始；系统不会自动拨打120或联系任何真实联系人。'|KEEP / 继承所属要素组迁移|
|UI-0069|streamlit_app.py:1199 `_render_current_risk_actions`|form|f'red-risk-close-{event.id}'|KEEP / 继承所属要素组迁移|
|UI-0070|streamlit_app.py:1200 `_render_current_risk_actions`|text_area|'关闭原因'|KEEP / 继承所属要素组迁移|
|UI-0071|streamlit_app.py:1201 `_render_current_risk_actions`|text_area|'最终人工处置'|KEEP / 继承所属要素组迁移|
|UI-0072|streamlit_app.py:1202 `_render_current_risk_actions`|form_submit_button|'记录结果并关闭风险事项'|KEEP / 继承所属要素组迁移|
|UI-0073|streamlit_app.py:1208 `_render_current_risk_actions`|success|'已记录人工处置结果并关闭风险事项。'|KEEP / 继承所属要素组迁移|
|UI-0074|streamlit_app.py:1211 `_render_current_risk_actions`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0075|streamlit_app.py:1218 `render_yellow_risk_operations`|subheader|'需要关注'|KEEP / 继承所属要素组迁移|
|UI-0076|streamlit_app.py:1219 `render_yellow_risk_operations`|caption|f'{_risk_event_source(event)} · {_label(event.status)}'|KEEP / 继承所属要素组迁移|
|UI-0077|streamlit_app.py:1221 `render_yellow_risk_operations`|caption|f'触发时间：{_fmt_dt(event.created_at)} · {_risk_event_evidence_caption(event)}'|KEEP / 继承所属要素组迁移|
|UI-0078|streamlit_app.py:1225 `render_yellow_risk_operations`|radio|'处理方式'|KEEP / 继承所属要素组迁移|
|UI-0079|streamlit_app.py:1226 `render_yellow_risk_operations`|form|f'yellow-action-form-{event.id}'|KEEP / 继承所属要素组迁移|
|UI-0080|streamlit_app.py:1227 `render_yellow_risk_operations`|text_input|'健康管理师'|KEEP / 继承所属要素组迁移|
|UI-0081|streamlit_app.py:1229 `render_yellow_risk_operations`|text_area|'观察原因 / 备注'|KEEP / 继承所属要素组迁移|
|UI-0082|streamlit_app.py:1230 `render_yellow_risk_operations`|date_input|'下次复核日期'|KEEP / 继承所属要素组迁移|
|UI-0083|streamlit_app.py:1231 `render_yellow_risk_operations`|form_submit_button|'保存并创建复核任务'|KEEP / 继承所属要素组迁移|
|UI-0084|streamlit_app.py:1270 `render_yellow_risk_operations`|form|f'yellow-followup-{event.id}'|KEEP / 继承所属要素组迁移|
|UI-0085|streamlit_app.py:1271 `render_yellow_risk_operations`|text_area|'记录跟进结果'|KEEP / 继承所属要素组迁移|
|UI-0086|streamlit_app.py:1272 `render_yellow_risk_operations`|form_submit_button|'完成本次跟进'|KEEP / 继承所属要素组迁移|
|UI-0087|streamlit_app.py:1286 `render_yellow_risk_operations`|form|f'yellow-close-{event.id}'|KEEP / 继承所属要素组迁移|
|UI-0088|streamlit_app.py:1287 `render_yellow_risk_operations`|text_area|'关闭原因'|KEEP / 继承所属要素组迁移|
|UI-0089|streamlit_app.py:1288 `render_yellow_risk_operations`|form_submit_button|'完成跟进后关闭事件'|KEEP / 继承所属要素组迁移|
|UI-0090|streamlit_app.py:1233 `render_yellow_risk_operations`|selectbox|'联系方式'|KEEP / 继承所属要素组迁移|
|UI-0091|streamlit_app.py:1234 `render_yellow_risk_operations`|selectbox|'联系结果'|KEEP / 继承所属要素组迁移|
|UI-0092|streamlit_app.py:1235 `render_yellow_risk_operations`|text_area|'联系记录 / 备注'|KEEP / 继承所属要素组迁移|
|UI-0093|streamlit_app.py:1236 `render_yellow_risk_operations`|date_input|'下次复核日期（可选）'|KEEP / 继承所属要素组迁移|
|UI-0094|streamlit_app.py:1237 `render_yellow_risk_operations`|form_submit_button|'保存人工联系记录'|KEEP / 继承所属要素组迁移|
|UI-0095|streamlit_app.py:1265 `render_yellow_risk_operations`|success|'已保存人工处置记录。系统未发送真实消息，也未自动作出医疗决定。'|KEEP / 继承所属要素组迁移|
|UI-0096|streamlit_app.py:1303 `render_yellow_risk_operations`|caption|f'{_fmt_dt(item.created_at)} · {_role_label(item.actor_role, name=item.actor)} · {get_audit_action_display(item.action)}'|KEEP / 继承所属要素组迁移|
|UI-0097|streamlit_app.py:1239 `render_yellow_risk_operations`|text_area|'数据问题原因'|KEEP / 继承所属要素组迁移|
|UI-0098|streamlit_app.py:1240 `render_yellow_risk_operations`|form_submit_button|'记录数据问题并关闭事件'|KEEP / 继承所属要素组迁移|
|UI-0099|streamlit_app.py:1268 `render_yellow_risk_operations`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0100|streamlit_app.py:1281 `render_yellow_risk_operations`|success|'已记录跟进结果。'|KEEP / 继承所属要素组迁移|
|UI-0101|streamlit_app.py:1293 `render_yellow_risk_operations`|success|'已关闭本次需要关注事件。'|KEEP / 继承所属要素组迁移|
|UI-0102|streamlit_app.py:1242 `render_yellow_risk_operations`|text_area|'调整原因'|KEEP / 继承所属要素组迁移|
|UI-0103|streamlit_app.py:1243 `render_yellow_risk_operations`|text_area|'调整内容 / 下一步任务'|KEEP / 继承所属要素组迁移|
|UI-0104|streamlit_app.py:1244 `render_yellow_risk_operations`|date_input|'复核日期（可选）'|KEEP / 继承所属要素组迁移|
|UI-0105|streamlit_app.py:1245 `render_yellow_risk_operations`|form_submit_button|'创建健康管理任务'|KEEP / 继承所属要素组迁移|
|UI-0106|streamlit_app.py:1247 `render_yellow_risk_operations`|text_area|'希望医生确认什么？'|KEEP / 继承所属要素组迁移|
|UI-0107|streamlit_app.py:1248 `render_yellow_risk_operations`|selectbox|'建议科室'|KEEP / 继承所属要素组迁移|
|UI-0108|streamlit_app.py:1249 `render_yellow_risk_operations`|form_submit_button|'提交医生复核'|KEEP / 继承所属要素组迁移|
|UI-0109|streamlit_app.py:1284 `render_yellow_risk_operations`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0110|streamlit_app.py:1296 `render_yellow_risk_operations`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0111|streamlit_app.py:1508 `_render_kpis`|metric|'高优先级事件'|KEEP / 继承所属要素组迁移|
|UI-0112|streamlit_app.py:1509 `_render_kpis`|metric|'待健康管理师核实'|KEEP / 继承所属要素组迁移|
|UI-0113|streamlit_app.py:1510 `_render_kpis`|metric|'待医生复核'|KEEP / 继承所属要素组迁移|
|UI-0114|streamlit_app.py:1511 `_render_kpis`|metric|'逾期任务'|KEEP / 继承所属要素组迁移|
|UI-0115|streamlit_app.py:1512 `_render_kpis`|metric|'7日内待复查'|KEEP / 继承所属要素组迁移|
|UI-0116|streamlit_app.py:1513 `_render_kpis`|metric|'当前未闭环健康问题'|KEEP / 继承所属要素组迁移|
|UI-0117|streamlit_app.py:1514 `_render_kpis`|metric|'本月已闭环健康问题'|KEEP / 继承所属要素组迁移|
|UI-0118|streamlit_app.py:1515 `_render_kpis`|metric|'平均响应时间'|KEEP / 继承所属要素组迁移|
|UI-0119|streamlit_app.py:1525 `_render_program_funnel`|subheader|'成员健康管理阶段'|KEEP / 继承所属要素组迁移|
|UI-0120|streamlit_app.py:1532 `_render_program_funnel`|metric|'已进入管理计划'|KEEP / 继承所属要素组迁移|
|UI-0121|streamlit_app.py:1533 `_render_program_funnel`|metric|'已完成管理计划'|KEEP / 继承所属要素组迁移|
|UI-0122|streamlit_app.py:1534 `_render_program_funnel`|metric|'已完成阶段效果评估'|KEEP / 继承所属要素组迁移|
|UI-0123|streamlit_app.py:1535 `_render_program_funnel`|metric|'已升级医疗处理'|KEEP / 继承所属要素组迁移|
|UI-0124|streamlit_app.py:1536 `_render_program_funnel`|metric|'进入稳定管理'|KEEP / 继承所属要素组迁移|
|UI-0125|streamlit_app.py:1528 `_render_program_funnel`|metric|label|KEEP / 继承所属要素组迁移|
|UI-0126|streamlit_app.py:1587 `_render_member_header`|caption|'健康基线：尚未建立'|KEEP / 继承所属要素组迁移|
|UI-0127|streamlit_app.py:1590 `_render_member_header`|caption|'健康基线初稿等待确认'|KEEP / 继承所属要素组迁移|
|UI-0128|streamlit_app.py:1591 `_render_member_header`|button|'处理'|KEEP / 继承所属要素组迁移|
|UI-0129|streamlit_app.py:1593 `_render_member_header`|caption|f'健康基线：已建立 · {_fmt_dt(baseline.confirmed_at or baseline.assessed_at)}'|KEEP / 继承所属要素组迁移|
|UI-0130|streamlit_app.py:1623 `_render_problem_card`|caption|f"负责人：{_role_label(problem.responsible_role, name=problem.owner)} · 创建：{_fmt_dt(problem.opened_at)} · 截止：{_fmt_dt(next((item.due_at for item in related['tasks'] if item.due_at), No|KEEP / 继承所属要素组迁移|
|UI-0131|streamlit_app.py:1638 `_render_problem_card`|caption|item.content|KEEP / 继承所属要素组迁移|
|UI-0132|streamlit_app.py:1640 `_render_problem_card`|caption|'尚未形成经医生确认的管理计划。'|KEEP / 继承所属要素组迁移|
|UI-0133|streamlit_app.py:1648 `_render_problem_card`|caption|item.opinion|KEEP / 继承所属要素组迁移|
|UI-0134|streamlit_app.py:1650 `_render_problem_card`|caption|'尚待医生复核。'|KEEP / 继承所属要素组迁移|
|UI-0135|streamlit_app.py:1657 `_render_problem_card`|success|f'闭环结果：已由人工随访关闭（{_fmt_dt(problem.closed_at)}）。'|KEEP / 继承所属要素组迁移|
|UI-0136|streamlit_app.py:1659 `_render_problem_card`|expander|'记录随访并关闭健康问题'|KEEP / 继承所属要素组迁移|
|UI-0137|streamlit_app.py:1655 `_render_problem_card`|caption|item.outcome|KEEP / 继承所属要素组迁移|
|UI-0138|streamlit_app.py:1661 `_render_problem_card`|form|f'followup-{problem.id}'|KEEP / 继承所属要素组迁移|
|UI-0139|streamlit_app.py:1662 `_render_problem_card`|text_input|'随访记录人'|KEEP / 继承所属要素组迁移|
|UI-0140|streamlit_app.py:1663 `_render_problem_card`|text_area|'随访结果（人工记录）'|KEEP / 继承所属要素组迁移|
|UI-0141|streamlit_app.py:1664 `_render_problem_card`|selectbox|'关联执行任务'|KEEP / 继承所属要素组迁移|
|UI-0142|streamlit_app.py:1665 `_render_problem_card`|form_submit_button|'保存随访并关闭'|KEEP / 继承所属要素组迁移|
|UI-0143|streamlit_app.py:1668 `_render_problem_card`|error|'请填写随访记录人与结果。'|KEEP / 继承所属要素组迁移|
|UI-0144|streamlit_app.py:1675 `_render_problem_card`|success|'已写入随访、关闭关联事项并保留审计记录。'|KEEP / 继承所属要素组迁移|
|UI-0145|streamlit_app.py:1680 `render_problems`|subheader|'健康问题'|KEEP / 继承所属要素组迁移|
|UI-0146|streamlit_app.py:1683 `render_problems`|info|'暂无健康问题。仅在人工确认需要持续处理时创建。'|KEEP / 继承所属要素组迁移|
|UI-0147|streamlit_app.py:1689 `_render_create_task`|expander|'创建执行任务'|KEEP / 继承所属要素组迁移|
|UI-0148|streamlit_app.py:1690 `_render_create_task`|form|f'task-{(alert.id if alert else problem.id if problem else patient.id)}'|KEEP / 继承所属要素组迁移|
|UI-0149|streamlit_app.py:1691 `_render_create_task`|text_input|'任务内容'|KEEP / 继承所属要素组迁移|
|UI-0150|streamlit_app.py:1692 `_render_create_task`|text_area|'执行说明'|KEEP / 继承所属要素组迁移|
|UI-0151|streamlit_app.py:1693 `_render_create_task`|selectbox|'优先级'|KEEP / 继承所属要素组迁移|
|UI-0152|streamlit_app.py:1694 `_render_create_task`|text_input|'执行人/角色'|KEEP / 继承所属要素组迁移|
|UI-0153|streamlit_app.py:1695 `_render_create_task`|date_input|'截止日期'|KEEP / 继承所属要素组迁移|
|UI-0154|streamlit_app.py:1696 `_render_create_task`|form_submit_button|'创建任务'|KEEP / 继承所属要素组迁移|
|UI-0155|streamlit_app.py:1699 `_render_create_task`|error|'请完整填写任务内容、说明和执行人。'|KEEP / 继承所属要素组迁移|
|UI-0156|streamlit_app.py:1707 `_render_create_task`|success|'已创建可追溯的执行任务。'|KEEP / 继承所属要素组迁移|
|UI-0157|streamlit_app.py:1714 `_render_alert_card`|caption|f'负责人：{_role_label(alert.responsible_role, name=alert.owner)} · 创建：{_fmt_dt(alert.created_at)} · 截止：{_fmt_dt(alert.due_at)}'|KEEP / 继承所属要素组迁移|
|UI-0158|streamlit_app.py:1718 `_render_alert_card`|caption|'筛查证据日期：' + '、'.join(dates) + '（用于人工核实，不构成诊断）'|KEEP / 继承所属要素组迁移|
|UI-0159|streamlit_app.py:1720 `_render_alert_card`|info|f'核实记录：{alert.review_note}'|KEEP / 继承所属要素组迁移|
|UI-0160|streamlit_app.py:1724 `_render_alert_card`|form|f'alert-review-{alert.id}'|KEEP / 继承所属要素组迁移|
|UI-0161|streamlit_app.py:1725 `_render_alert_card`|text_input|'健康管理师'|KEEP / 继承所属要素组迁移|
|UI-0162|streamlit_app.py:1726 `_render_alert_card`|radio|'核实结果'|KEEP / 继承所属要素组迁移|
|UI-0163|streamlit_app.py:1727 `_render_alert_card`|text_area|'核实记录'|KEEP / 继承所属要素组迁移|
|UI-0164|streamlit_app.py:1728 `_render_alert_card`|selectbox|'健康问题处理'|KEEP / 继承所属要素组迁移|
|UI-0165|streamlit_app.py:1729 `_render_alert_card`|form_submit_button|'保存人工核实'|KEEP / 继承所属要素组迁移|
|UI-0166|streamlit_app.py:1744 `_render_alert_card`|warning|'已完成健康管理师确认，下一步为医生复核。请在“医生复核工作台”填写人工意见。'|KEEP / 继承所属要素组迁移|
|UI-0167|streamlit_app.py:1732 `_render_alert_card`|error|'请填写健康管理师姓名和核实记录。'|KEEP / 继承所属要素组迁移|
|UI-0168|streamlit_app.py:1741 `_render_alert_card`|success|'人工核实已保存，并已写入审计记录。'|KEEP / 继承所属要素组迁移|
|UI-0169|streamlit_app.py:1746 `_render_alert_card`|info|'医生复核与管理方案已形成，正在等待执行任务和随访完成。'|KEEP / 继承所属要素组迁移|
|UI-0170|streamlit_app.py:1751 `render_alerts`|subheader|'健康异常与事件'|KEEP / 继承所属要素组迁移|
|UI-0171|streamlit_app.py:1752 `render_alerts`|caption|'处理路径：新建 → 规则筛查完成 → 管理师核实 → 医生复核 → 随访 → 已关闭'|KEEP / 继承所属要素组迁移|
|UI-0172|streamlit_app.py:1754 `render_alerts`|info|'暂无健康异常。筛查发现的异常必须先由人工核实。'|KEEP / 继承所属要素组迁移|
|UI-0173|streamlit_app.py:1760 `render_tasks`|subheader|'执行任务'|KEEP / 继承所属要素组迁移|
|UI-0174|streamlit_app.py:1763 `render_tasks`|info|'暂无执行任务。'|KEEP / 继承所属要素组迁移|
|UI-0175|streamlit_app.py:1771 `render_tasks`|button|'标记完成'|KEEP / 继承所属要素组迁移|
|UI-0176|streamlit_app.py:1783 `render_tasks`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0177|streamlit_app.py:1818 `_render_legacy_doctor_reviews`|subheader|'医生复核'|KEEP / 继承所属要素组迁移|
|UI-0178|streamlit_app.py:1886 `_render_legacy_doctor_reviews`|info|f'来源：{automation_goal.title} · 当前需要：医学复核。完成后由健康管理师继续执行。'|KEEP / 继承所属要素组迁移|
|UI-0179|streamlit_app.py:2009 `_render_legacy_doctor_reviews`|caption|'当前没有待医生复核事项。'|KEEP / 继承所属要素组迁移|
|UI-0180|streamlit_app.py:1862 `_render_legacy_doctor_reviews`|expander|f'{confirmed_baseline.cycle_year or confirmed_baseline.assessed_at.year}年度健康基线医学摘要'|KEEP / 继承所属要素组迁移|
|UI-0181|streamlit_app.py:1898 `_render_legacy_doctor_reviews`|caption|f"提交：{_fmt_dt(review.created_at)} · {(_risk_event_evidence_caption(event) if event else '相关数据已归档')}"|KEEP / 继承所属要素组迁移|
|UI-0182|streamlit_app.py:1835 `_render_legacy_doctor_reviews`|dataframe|pd.DataFrame([{'指标': _metric_display_name(str(row.get('metric') or '')), '基线数值': f"{row.get('value', '未记录')} {row.get('unit', '')}".strip(), '采集时间': str(row.get('observed_at') or '|KEEP / 继承所属要素组迁移|
|UI-0183|streamlit_app.py:1849 `_render_legacy_doctor_reviews`|form|f'baseline-medical-review-{baseline_medical_review.id}'|KEEP / 继承所属要素组迁移|
|UI-0184|streamlit_app.py:1850 `_render_legacy_doctor_reviews`|text_input|'医生姓名'|KEEP / 继承所属要素组迁移|
|UI-0185|streamlit_app.py:1851 `_render_legacy_doctor_reviews`|text_area|'医学资料复核说明'|KEEP / 继承所属要素组迁移|
|UI-0186|streamlit_app.py:1852 `_render_legacy_doctor_reviews`|form_submit_button|'完成医学资料复核'|KEEP / 继承所属要素组迁移|
|UI-0187|streamlit_app.py:1859 `_render_legacy_doctor_reviews`|success|'医学相关资料已复核，已返回健康管理师完成基线确认。'|KEEP / 继承所属要素组迁移|
|UI-0188|streamlit_app.py:1871 `_render_legacy_doctor_reviews`|dataframe|pd.DataFrame([{'关键指标': _metric_display_name(str(row.get('metric') or '')), '基线数值': f"{row.get('value', '未记录')} {row.get('unit', '')}".strip(), '采集时间': str(row.get('observed_at') or|KEEP / 继承所属要素组迁移|
|UI-0189|streamlit_app.py:1905 `_render_legacy_doctor_reviews`|form|f'yellow-doctor-review-{review.id}'|KEEP / 继承所属要素组迁移|
|UI-0190|streamlit_app.py:1906 `_render_legacy_doctor_reviews`|text_input|'医生姓名'|KEEP / 继承所属要素组迁移|
|UI-0191|streamlit_app.py:1907 `_render_legacy_doctor_reviews`|text_input|'科室'|KEEP / 继承所属要素组迁移|
|UI-0192|streamlit_app.py:1908 `_render_legacy_doctor_reviews`|text_area|'医生人工意见'|KEEP / 继承所属要素组迁移|
|UI-0193|streamlit_app.py:1909 `_render_legacy_doctor_reviews`|text_area|'后续跟进任务'|KEEP / 继承所属要素组迁移|
|UI-0194|streamlit_app.py:1910 `_render_legacy_doctor_reviews`|date_input|'建议跟进日期'|KEEP / 继承所属要素组迁移|
|UI-0195|streamlit_app.py:1911 `_render_legacy_doctor_reviews`|form_submit_button|'保存医生复核并创建跟进任务'|KEEP / 继承所属要素组迁移|
|UI-0196|streamlit_app.py:1932 `_render_legacy_doctor_reviews`|form|f'outcome-doctor-review-{review.id}'|KEEP / 继承所属要素组迁移|
|UI-0197|streamlit_app.py:1933 `_render_legacy_doctor_reviews`|text_input|'医生姓名'|KEEP / 继承所属要素组迁移|
|UI-0198|streamlit_app.py:1934 `_render_legacy_doctor_reviews`|text_input|'科室'|KEEP / 继承所属要素组迁移|
|UI-0199|streamlit_app.py:1935 `_render_legacy_doctor_reviews`|text_area|'医生人工意见'|KEEP / 继承所属要素组迁移|
|UI-0200|streamlit_app.py:1936 `_render_legacy_doctor_reviews`|text_area|'后续跟进任务'|KEEP / 继承所属要素组迁移|
|UI-0201|streamlit_app.py:1937 `_render_legacy_doctor_reviews`|date_input|'建议跟进日期'|KEEP / 继承所属要素组迁移|
|UI-0202|streamlit_app.py:1938 `_render_legacy_doctor_reviews`|form_submit_button|'保存医生复核并创建跟进任务'|KEEP / 继承所属要素组迁移|
|UI-0203|streamlit_app.py:1963 `_render_legacy_doctor_reviews`|caption|alert.finding|KEEP / 继承所属要素组迁移|
|UI-0204|streamlit_app.py:1969 `_render_legacy_doctor_reviews`|dataframe|_recent_observation_table(ctx['observations']).head(12)|KEEP / 继承所属要素组迁移|
|UI-0205|streamlit_app.py:1970 `_render_legacy_doctor_reviews`|form|f'doctor-review-{alert.id}'|KEEP / 继承所属要素组迁移|
|UI-0206|streamlit_app.py:1971 `_render_legacy_doctor_reviews`|text_input|'医生姓名'|KEEP / 继承所属要素组迁移|
|UI-0207|streamlit_app.py:1972 `_render_legacy_doctor_reviews`|selectbox|'科室'|KEEP / 继承所属要素组迁移|
|UI-0208|streamlit_app.py:1973 `_render_legacy_doctor_reviews`|text_input|'建议进一步检查（可留空）'|KEEP / 继承所属要素组迁移|
|UI-0209|streamlit_app.py:1974 `_render_legacy_doctor_reviews`|text_input|'建议随访周期（可留空）'|KEEP / 继承所属要素组迁移|
|UI-0210|streamlit_app.py:1975 `_render_legacy_doctor_reviews`|text_area|'医生意见 / 确认'|KEEP / 继承所属要素组迁移|
|UI-0211|streamlit_app.py:1976 `_render_legacy_doctor_reviews`|form_submit_button|'确认医生复核并创建管理方案与任务'|KEEP / 继承所属要素组迁移|
|UI-0212|streamlit_app.py:1993 `_render_legacy_doctor_reviews`|expander|'查看整理摘要与相关数据'|KEEP / 继承所属要素组迁移|
|UI-0213|streamlit_app.py:2014 `_render_legacy_doctor_reviews`|expander|f'{_fmt_dt(review.reviewed_at)} · {review.department} · {review.doctor_name}'|KEEP / 继承所属要素组迁移|
|UI-0214|streamlit_app.py:1918 `_render_legacy_doctor_reviews`|success|'已保存医生人工复核，并创建关联跟进任务。'|KEEP / 继承所属要素组迁移|
|UI-0215|streamlit_app.py:1944 `_render_legacy_doctor_reviews`|success|'已保存医生人工复核，并创建关联跟进任务。'|KEEP / 继承所属要素组迁移|
|UI-0216|streamlit_app.py:1979 `_render_legacy_doctor_reviews`|error|'请填写医生姓名和人工意见。'|KEEP / 继承所属要素组迁移|
|UI-0217|streamlit_app.py:1991 `_render_legacy_doctor_reviews`|success|'已记录医生人工复核，并创建关联管理方案与执行任务。'|KEEP / 继承所属要素组迁移|
|UI-0218|streamlit_app.py:2019 `_render_legacy_doctor_reviews`|expander|'查看当时整理摘要'|KEEP / 继承所属要素组迁移|
|UI-0219|streamlit_app.py:1921 `_render_legacy_doctor_reviews`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0220|streamlit_app.py:1947 `_render_legacy_doctor_reviews`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0221|streamlit_app.py:2024 `render_observations`|subheader|'关键健康趋势'|KEEP / 继承所属要素组迁移|
|UI-0222|streamlit_app.py:2025 `render_observations`|caption|'先查看近期趋势；详细记录和技术来源收纳在页面下方。'|KEEP / 继承所属要素组迁移|
|UI-0223|streamlit_app.py:2042 `render_observations`|multiselect|'数据来源'|KEEP / 继承所属要素组迁移|
|UI-0224|streamlit_app.py:2043 `render_observations`|multiselect|'数据质量'|KEEP / 继承所属要素组迁移|
|UI-0225|streamlit_app.py:2044 `render_observations`|date_input|'记录时间从'|KEEP / 继承所属要素组迁移|
|UI-0226|streamlit_app.py:2028 `render_observations`|info|'暂无健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0227|streamlit_app.py:2048 `render_observations`|info|'当前筛选条件下暂无健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0228|streamlit_app.py:2053 `render_observations`|line_chart|chart.tail(60)|KEEP / 继承所属要素组迁移|
|UI-0229|streamlit_app.py:2054 `render_observations`|expander|'查看详细记录'|KEEP / 继承所属要素组迁移|
|UI-0230|streamlit_app.py:2055 `render_observations`|multiselect|'显示指标'|KEEP / 继承所属要素组迁移|
|UI-0231|streamlit_app.py:2056 `render_observations`|dataframe|frame[frame['指标'].isin(selected)] if selected else frame.iloc[0:0]|KEEP / 继承所属要素组迁移|
|UI-0232|streamlit_app.py:2037 `render_observations`|metric|display_observation(code)|KEEP / 继承所属要素组迁移|
|UI-0233|streamlit_app.py:2160 `_render_realtime_section`|subheader|'健康监测'|KEEP / 继承所属要素组迁移|
|UI-0234|streamlit_app.py:2161 `_render_realtime_section`|caption|'只显示最近有效的医疗监测与生命体征；趋势按需展开。'|KEEP / 继承所属要素组迁移|
|UI-0235|streamlit_app.py:2193 `_render_realtime_section`|radio|'动态血糖时间'|KEEP / 继承所属要素组迁移|
|UI-0236|streamlit_app.py:2199 `_render_realtime_section`|caption|f'最近{window_label}动态曲线'|KEEP / 继承所属要素组迁移|
|UI-0237|streamlit_app.py:2200 `_render_realtime_section`|line_chart|_downsample_for_chart(frame).set_index('记录时间')[['数值']]|KEEP / 继承所属要素组迁移|
|UI-0238|streamlit_app.py:2172 `_render_realtime_section`|metric|'当前'|KEEP / 继承所属要素组迁移|
|UI-0239|streamlit_app.py:2173 `_render_realtime_section`|caption|'状态：需要审核' if glucose_event else '状态：正常'|KEEP / 继承所属要素组迁移|
|UI-0240|streamlit_app.py:2174 `_render_realtime_section`|button|'查看血糖详情'|KEEP / 继承所属要素组迁移|
|UI-0241|streamlit_app.py:2188 `_render_realtime_section`|metric|'最近心率'|KEEP / 继承所属要素组迁移|
|UI-0242|streamlit_app.py:2189 `_render_realtime_section`|caption|_observation_when(realtime.latest_heart_rate)|KEEP / 继承所属要素组迁移|
|UI-0243|streamlit_app.py:2182 `_render_realtime_section`|metric|'最近血压'|KEEP / 继承所属要素组迁移|
|UI-0244|streamlit_app.py:2183 `_render_realtime_section`|caption|_observation_when(realtime.latest_systolic)|KEEP / 继承所属要素组迁移|
|UI-0245|streamlit_app.py:2185 `_render_realtime_section`|metric|'最近血压'|KEEP / 继承所属要素组迁移|
|UI-0246|streamlit_app.py:2207 `_render_lifestyle_section`|subheader|'今天的生活状态'|KEEP / 继承所属要素组迁移|
|UI-0247|streamlit_app.py:2208 `_render_lifestyle_section`|caption|'睡眠、活动和恢复数据来自已连接或演示的数据来源。'|KEEP / 继承所属要素组迁移|
|UI-0248|streamlit_app.py:2258 `_render_lifestyle_section`|caption|_lifestyle_status_caption(signal_by_metric.get('sleep_duration'), None)|KEEP / 继承所属要素组迁移|
|UI-0249|streamlit_app.py:2259 `_render_lifestyle_section`|button|'查看睡眠详情'|KEEP / 继承所属要素组迁移|
|UI-0250|streamlit_app.py:2226 `_render_lifestyle_section`|metric|'步数'|KEEP / 继承所属要素组迁移|
|UI-0251|streamlit_app.py:2227 `_render_lifestyle_section`|caption|_lifestyle_status_caption(signal_by_metric.get('steps'), steps)|KEEP / 继承所属要素组迁移|
|UI-0252|streamlit_app.py:2230 `_render_lifestyle_section`|metric|'活动消耗'|KEEP / 继承所属要素组迁移|
|UI-0253|streamlit_app.py:2231 `_render_lifestyle_section`|caption|_observation_when(calories, today_label='设备提供') if calories else '暂无设备活动消耗数据'|KEEP / 继承所属要素组迁移|
|UI-0254|streamlit_app.py:2234 `_render_lifestyle_section`|metric|'运动时间'|KEEP / 继承所属要素组迁移|
|UI-0255|streamlit_app.py:2235 `_render_lifestyle_section`|caption|_lifestyle_status_caption(signal_by_metric.get('exercise_minutes'), exercise)|KEEP / 继承所属要素组迁移|
|UI-0256|streamlit_app.py:2246 `_render_lifestyle_section`|caption|f'7天平均：{average:.0f} 步 · {delta}'|KEEP / 继承所属要素组迁移|
|UI-0257|streamlit_app.py:2247 `_render_lifestyle_section`|button|'查看步数趋势'|KEEP / 继承所属要素组迁移|
|UI-0258|streamlit_app.py:2274 `_render_lifestyle_section`|line_chart|steps_frame.tail(7).set_index('日期')[['数值']]|KEEP / 继承所属要素组迁移|
|UI-0259|streamlit_app.py:2254 `_render_lifestyle_section`|metric|'睡眠'|KEEP / 继承所属要素组迁移|
|UI-0260|streamlit_app.py:2257 `_render_lifestyle_section`|metric|'深度睡眠'|KEEP / 继承所属要素组迁移|
|UI-0261|streamlit_app.py:2268 `_render_lifestyle_section`|metric|label|KEEP / 继承所属要素组迁移|
|UI-0262|streamlit_app.py:2269 `_render_lifestyle_section`|caption|_observation_when(observation, today_label='最近有效值') if observation else '暂无数据'|KEEP / 继承所属要素组迁移|
|UI-0263|streamlit_app.py:2316 `_sleep_stage_timeline`|caption|'深度睡眠 · 浅睡 · REM · 清醒（设备实际提供的睡眠阶段）'|KEEP / 继承所属要素组迁移|
|UI-0264|streamlit_app.py:2298 `_sleep_stage_timeline`|info|'当前设备仅提供总睡眠时间，暂无睡眠阶段数据。'|KEEP / 继承所属要素组迁移|
|UI-0265|streamlit_app.py:2335 `_render_sleep_detail`|metric|'总睡眠'|KEEP / 继承所属要素组迁移|
|UI-0266|streamlit_app.py:2336 `_render_sleep_detail`|metric|'深度睡眠'|KEEP / 继承所属要素组迁移|
|UI-0267|streamlit_app.py:2337 `_render_sleep_detail`|metric|'深睡占比'|KEEP / 继承所属要素组迁移|
|UI-0268|streamlit_app.py:2338 `_render_sleep_detail`|metric|'入睡时间'|KEEP / 继承所属要素组迁移|
|UI-0269|streamlit_app.py:2339 `_render_sleep_detail`|metric|'醒来时间'|KEEP / 继承所属要素组迁移|
|UI-0270|streamlit_app.py:2341 `_render_sleep_detail`|metric|'REM'|KEEP / 继承所属要素组迁移|
|UI-0271|streamlit_app.py:2342 `_render_sleep_detail`|metric|'浅睡'|KEEP / 继承所属要素组迁移|
|UI-0272|streamlit_app.py:2344 `_render_sleep_detail`|metric|'夜间清醒'|KEEP / 继承所属要素组迁移|
|UI-0273|streamlit_app.py:2345 `_render_sleep_detail`|metric|'夜间中断'|KEEP / 继承所属要素组迁移|
|UI-0274|streamlit_app.py:2346 `_render_sleep_detail`|caption|_lifestyle_status_caption(signal, None)|KEEP / 继承所属要素组迁移|
|UI-0275|streamlit_app.py:2348 `_render_sleep_detail`|radio|'睡眠趋势时间'|KEEP / 继承所属要素组迁移|
|UI-0276|streamlit_app.py:2322 `_render_sleep_detail`|caption|'暂无设备睡眠记录。'|KEEP / 继承所属要素组迁移|
|UI-0277|streamlit_app.py:2355 `_render_sleep_detail`|metric|f'{window}平均总睡眠'|KEEP / 继承所属要素组迁移|
|UI-0278|streamlit_app.py:2356 `_render_sleep_detail`|metric|'平均深度睡眠'|KEEP / 继承所属要素组迁移|
|UI-0279|streamlit_app.py:2357 `_render_sleep_detail`|metric|'平均深睡占比'|KEEP / 继承所属要素组迁移|
|UI-0280|streamlit_app.py:2358 `_render_sleep_detail`|metric|'平均REM'|KEEP / 继承所属要素组迁移|
|UI-0281|streamlit_app.py:2359 `_render_sleep_detail`|metric|'平均入睡时间'|KEEP / 继承所属要素组迁移|
|UI-0282|streamlit_app.py:2361 `_render_sleep_detail`|line_chart|values.set_index('日期')[['总睡眠(分钟)', '深睡(分钟)']]|KEEP / 继承所属要素组迁移|
|UI-0283|streamlit_app.py:2371 `_render_long_term_section`|subheader|'长期健康趋势'|KEEP / 继承所属要素组迁移|
|UI-0284|streamlit_app.py:2372 `_render_long_term_section`|caption|'查看可调整时间范围内的重要健康变化。'|KEEP / 继承所属要素组迁移|
|UI-0285|streamlit_app.py:2373 `_render_long_term_section`|radio|'长期趋势时间'|KEEP / 继承所属要素组迁移|
|UI-0286|streamlit_app.py:2386 `_render_long_term_section`|caption|'当前时间范围内暂无长期趋势数据。'|KEEP / 继承所属要素组迁移|
|UI-0287|streamlit_app.py:2397 `_render_long_term_section`|expander|'查看详细趋势'|KEEP / 继承所属要素组迁移|
|UI-0288|streamlit_app.py:2395 `_render_long_term_section`|caption|f"{summary['指标']}趋势"|KEEP / 继承所属要素组迁移|
|UI-0289|streamlit_app.py:2396 `_render_long_term_section`|line_chart|_downsample_for_chart(frame).set_index('记录时间')[['数值']]|KEEP / 继承所属要素组迁移|
|UI-0290|streamlit_app.py:2402 `_render_long_term_section`|caption|f'{title}趋势'|KEEP / 继承所属要素组迁移|
|UI-0291|streamlit_app.py:2403 `_render_long_term_section`|line_chart|_downsample_for_chart(frame).set_index('记录时间')[['数值']]|KEEP / 继承所属要素组迁移|
|UI-0292|streamlit_app.py:2510 `render_health_data`|expander|'查看全部健康数据'|KEEP / 继承所属要素组迁移|
|UI-0293|streamlit_app.py:2511 `render_health_data`|dataframe|_recent_observation_table(detail_records)|KEEP / 继承所属要素组迁移|
|UI-0294|streamlit_app.py:2512 `render_health_data`|expander|'查看监测详情'|KEEP / 继承所属要素组迁移|
|UI-0295|streamlit_app.py:2419 `render_health_data`|info|f'正在查看时间轴选择的时间段：{start_at.date()} 至 {end_at.date()}'|KEEP / 继承所属要素组迁移|
|UI-0296|streamlit_app.py:2420 `render_health_data`|button|'返回默认'|KEEP / 继承所属要素组迁移|
|UI-0297|streamlit_app.py:2526 `render_health_data`|dataframe|pd.DataFrame(rows)|KEEP / 继承所属要素组迁移|
|UI-0298|streamlit_app.py:2530 `render_medications`|subheader|'用药信息'|KEEP / 继承所属要素组迁移|
|UI-0299|streamlit_app.py:2531 `render_medications`|caption|'此处展示既有医生管理计划与用户记录；系统不提供自动处方、停药、换药或剂量调整。'|KEEP / 继承所属要素组迁移|
|UI-0300|streamlit_app.py:2534 `render_medications`|dataframe|pd.DataFrame([{'药物': item.drug_name or '待补充', '剂量': ' '.join((part for part in (item.dose, item.dose_unit) if part)) or '待补充', '频率': item.frequency or '待补充', '途径': item.route or '待|KEEP / 继承所属要素组迁移|
|UI-0301|streamlit_app.py:2536 `render_medications`|info|'暂无已记录的用药信息。'|KEEP / 继承所属要素组迁移|
|UI-0302|streamlit_app.py:2540 `render_medications`|dataframe|pd.DataFrame([{'计划时间': _fmt_dt(item.scheduled_at), '实际记录': _fmt_dt(item.taken_at), '状态': _label(item.status)} for item in events[:50]])|KEEP / 继承所属要素组迁移|
|UI-0303|streamlit_app.py:2544 `render_timeline`|subheader|'健康时间线'|KEEP / 继承所属要素组迁移|
|UI-0304|streamlit_app.py:2567 `render_timeline`|title||KEEP / 继承所属要素组迁移|
|UI-0305|streamlit_app.py:2572 `render_audit`|subheader|'操作记录'|KEEP / 继承所属要素组迁移|
|UI-0306|streamlit_app.py:2577 `render_audit`|dataframe|pd.DataFrame([{'时间': _fmt_dt(item.created_at), '操作者': item.actor or '未记录', '角色': _role_label(item.actor_role), '处理动作': get_audit_action_display(item.action), '处理事项': get_entity_typ|KEEP / 继承所属要素组迁移|
|UI-0307|streamlit_app.py:2575 `render_audit`|info|'暂无审计记录。'|KEEP / 继承所属要素组迁移|
|UI-0308|streamlit_app.py:2591 `render_overview`|subheader|'健康概览'|KEEP / 继承所属要素组迁移|
|UI-0309|streamlit_app.py:2593 `render_overview`|info|f'运营摘要：{status}。本系统展示 HealthOps 工作状态，健康数值仅作为人工复核的事实依据。'|KEEP / 继承所属要素组迁移|
|UI-0310|streamlit_app.py:2600 `render_overview`|success|f"已完成：{problem.title}，{len(related['reviews'])} 次医生复核、{len(related['tasks'])} 个跟进任务、{len(related['followups'])} 条随访。请在成员历程中查看每一步。"|KEEP / 继承所属要素组迁移|
|UI-0311|streamlit_app.py:2602 `render_overview`|caption|'闭环将在管理师确认、医生复核与人工随访后逐步出现。'|KEEP / 继承所属要素组迁移|
|UI-0312|streamlit_app.py:2606 `render_programs`|subheader|'健康管理'|KEEP / 继承所属要素组迁移|
|UI-0313|streamlit_app.py:2607 `render_programs`|caption|'把阶段目标、执行任务、调整和复盘放在同一处查看。'|KEEP / 继承所属要素组迁移|
|UI-0314|streamlit_app.py:2610 `render_programs`|info|'尚未建立健康评估或健康管理计划。'|KEEP / 继承所属要素组迁移|
|UI-0315|streamlit_app.py:2623 `render_programs`|progress|day / 90|KEEP / 继承所属要素组迁移|
|UI-0316|streamlit_app.py:2627 `render_programs`|caption|'支持目标：' + ' · '.join(program.supporting_goals_json)|KEEP / 继承所属要素组迁移|
|UI-0317|streamlit_app.py:2633 `render_programs`|caption|'暂无执行任务。'|KEEP / 继承所属要素组迁移|
|UI-0318|streamlit_app.py:2642 `render_programs`|caption|f"已调整为：{latest.resolution or '等待健康管理师确认'}"|KEEP / 继承所属要素组迁移|
|UI-0319|streamlit_app.py:2644 `render_programs`|caption|f'最近复盘：{reviews[0].key_changes} · 下周重点：{reviews[0].next_week_focus}'|KEEP / 继承所属要素组迁移|
|UI-0320|streamlit_app.py:2646 `render_programs`|success|'阶段结果：' + '；'.join((f'{_metric_display_name(o.metric)} {o.baseline_value}{o.unit} → {o.current_value}{o.unit}（{_label(o.result)}）' for o in outcomes))|KEEP / 继承所属要素组迁移|
|UI-0321|streamlit_app.py:2666 `render_programs`|info|f'下一步安排：{_label(program.next_decision)}'|KEEP / 继承所属要素组迁移|
|UI-0322|streamlit_app.py:2648 `render_programs`|expander|'确认阶段结果后的下一步'|KEEP / 继承所属要素组迁移|
|UI-0323|streamlit_app.py:2649 `render_programs`|radio|'后续管理决定'|KEEP / 继承所属要素组迁移|
|UI-0324|streamlit_app.py:2653 `render_programs`|text_area|'说明（可选）'|KEEP / 继承所属要素组迁移|
|UI-0325|streamlit_app.py:2661 `render_programs`|success|'已记录阶段结果后的人工管理决定，并创建对应下一步。'|KEEP / 继承所属要素组迁移|
|UI-0326|streamlit_app.py:2664 `render_programs`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0327|streamlit_app.py:2682 `render_member_management_signals`|caption|f'最近发现：{_fmt_dt(signal.last_detected_at)} · 建议：{ROUTE_LABELS.get(signal.recommended_route, signal.recommended_route)}'|KEEP / 继承所属要素组迁移|
|UI-0328|streamlit_app.py:2684 `render_member_management_signals`|button|'创建任务'|KEEP / 继承所属要素组迁移|
|UI-0329|streamlit_app.py:2703 `render_member_management_signals`|success|'已创建健康管理跟进任务。'|KEEP / 继承所属要素组迁移|
|UI-0330|streamlit_app.py:2705 `render_member_management_signals`|info|'该信号已有进行中的跟进任务。'|KEEP / 继承所属要素组迁移|
|UI-0331|streamlit_app.py:2709 `render_outcomes`|subheader|'阶段效果评估'|KEEP / 继承所属要素组迁移|
|UI-0332|streamlit_app.py:2710 `render_outcomes`|caption|'仅描述基线与当前可观测变化；不构成疾病治愈或自动医学结论。'|KEEP / 继承所属要素组迁移|
|UI-0333|streamlit_app.py:2715 `render_outcomes`|dataframe|pd.DataFrame([{'指标': item.metric, '基线': f'{item.baseline_value} {item.unit}', '当前': f'{item.current_value} {item.unit}', '目标': item.target_value or '—', '方向': item.direction, '结果':|KEEP / 继承所属要素组迁移|
|UI-0334|streamlit_app.py:2713 `render_outcomes`|info|'尚未完成阶段效果评估。'|KEEP / 继承所属要素组迁移|
|UI-0335|streamlit_app.py:2723 `render_data_sources`|subheader|'数据来源'|KEEP / 继承所属要素组迁移|
|UI-0336|streamlit_app.py:2724 `render_data_sources`|caption|'展示成员外部身份与最近同步状态；原始数据仅在数据接入中心的高级信息中查看。'|KEEP / 继承所属要素组迁移|
|UI-0337|streamlit_app.py:2730 `render_data_sources`|dataframe|pd.DataFrame([{'数据来源': get_provider_display(item.provider), '连接状态': _label(item.status), '最近同步': _fmt_dt(next((job.completed_at for job in jobs if job.source_system == item.provide|KEEP / 继承所属要素组迁移|
|UI-0338|streamlit_app.py:2728 `render_data_sources`|info|'尚未配置外部身份映射。系统不会自动猜测成员。'|KEEP / 继承所属要素组迁移|
|UI-0339|streamlit_app.py:2793 `render_simple_member_overview`|caption|f'当前正在执行：{program.main_goal or display_program_type(program.program_type)}'|KEEP / 继承所属要素组迁移|
|UI-0340|streamlit_app.py:2750 `render_simple_member_overview`|status_badge|_severity(problem.severity)|KEEP / 继承所属要素组迁移|
|UI-0341|streamlit_app.py:2800 `render_simple_health_problems`|subheader|'健康问题'|KEEP / 继承所属要素组迁移|
|UI-0342|streamlit_app.py:2803 `render_simple_health_problems`|success|'当前没有需要持续跟进的健康问题。'|KEEP / 继承所属要素组迁移|
|UI-0343|streamlit_app.py:2815 `render_simple_health_problems`|caption|'已完成：' + ' · '.join((item for item in done if item)) if any(done) else '当前等待健康管理师处理'|KEEP / 继承所属要素组迁移|
|UI-0344|streamlit_app.py:2820 `render_simple_health_problems`|button|'处理'|KEEP / 继承所属要素组迁移|
|UI-0345|streamlit_app.py:2825 `render_simple_medical_records`|caption|'上传、查看和人工确认体检报告；技术解析信息默认隐藏。'|KEEP / 继承所属要素组迁移|
|UI-0346|streamlit_app.py:2826 `render_simple_medical_records`|button|'上传体检报告'|KEEP / 继承所属要素组迁移|
|UI-0347|streamlit_app.py:2836 `render_simple_medical_records`|caption|'暂无需要持续跟进的健康问题。'|KEEP / 继承所属要素组迁移|
|UI-0348|streamlit_app.py:2845 `render_simple_medical_records`|caption|'暂无手术或住院记录。'|KEEP / 继承所属要素组迁移|
|UI-0349|streamlit_app.py:2850 `render_simple_medical_records`|dataframe|pd.DataFrame([{'药品名称': plan.drug_name, '剂量': f'{plan.dose} {plan.dose_unit}', '频次': plan.frequency, '使用方式': plan.route} for plan in plans[:10]])|KEEP / 继承所属要素组迁移|
|UI-0350|streamlit_app.py:2852 `render_simple_medical_records`|caption|'暂无已记录的用药信息。'|KEEP / 继承所属要素组迁移|
|UI-0351|streamlit_app.py:2864 `render_simple_medical_records`|caption|'当前没有需要查看的医生意见。'|KEEP / 继承所属要素组迁移|
|UI-0352|streamlit_app.py:2873 `render_simple_medical_records`|caption|'暂无外部医疗协同记录。'|KEEP / 继承所属要素组迁移|
|UI-0353|streamlit_app.py:2843 `render_simple_medical_records`|caption|f'{_fmt_dt(event.start_at)} · {event.description}'|KEEP / 继承所属要素组迁移|
|UI-0354|streamlit_app.py:2871 `render_simple_medical_records`|caption|f"{referral.specialty or '专科待确认'} · {_label(referral.status)} · {referral.organization or '机构待确认'}"|KEEP / 继承所属要素组迁移|
|UI-0355|streamlit_app.py:2862 `render_simple_medical_records`|caption|f'复核问题：{review.question_for_doctor}'|KEEP / 继承所属要素组迁移|
|UI-0356|streamlit_app.py:2878 `render_members_workspace`|text_input|'搜索成员'|KEEP / 继承所属要素组迁移|
|UI-0357|streamlit_app.py:2891 `render_members_workspace`|button|'查看成员'|KEEP / 继承所属要素组迁移|
|UI-0358|streamlit_app.py:2893 `render_members_workspace`|empty_state|'未找到匹配成员'|KEEP / 继承所属要素组迁移|
|UI-0359|streamlit_app.py:2886 `render_members_workspace`|work_item|_member_display(member)|KEEP / 继承所属要素组迁移|
|UI-0360|streamlit_app.py:2889 `render_members_workspace`|caption|ux.owner(program.owner if program else None)|KEEP / 继承所属要素组迁移|
|UI-0361|streamlit_app.py:2890 `render_members_workspace`|caption|'最近管理记录：' + ux.when(task.created_at if task else program.created_at if program else None)|KEEP / 继承所属要素组迁移|
|UI-0362|streamlit_app.py:3010 `_render_knowledge_search_detail`|caption|result.subtitle|KEEP / 继承所属要素组迁移|
|UI-0363|streamlit_app.py:3013 `_render_knowledge_search_detail`|caption|f'获取时间：{_fmt_dt(result.retrieved_at)}'|KEEP / 继承所属要素组迁移|
|UI-0364|streamlit_app.py:3030 `_render_knowledge_search_detail`|link_button|'查看官方来源'|KEEP / 继承所属要素组迁移|
|UI-0365|streamlit_app.py:3024 `_render_knowledge_search_detail`|caption|'FDA/openFDA 监管资料，不构成个体化诊疗或用药建议。'|KEEP / 继承所属要素组迁移|
|UI-0366|streamlit_app.py:3041 `_render_knowledge_detail`|caption|f'{display_knowledge_category(document.category)} · 版本：{document.source_version or document.version} · 获取时间：{_fmt_dt(document.retrieved_at or document.updated_at)}'|KEEP / 继承所属要素组迁移|
|UI-0367|streamlit_app.py:3049 `_render_knowledge_detail`|link_button|'查看官方来源'|KEEP / 继承所属要素组迁移|
|UI-0368|streamlit_app.py:3053 `_render_knowledge_detail`|caption|'署名要求：' + document.attribution|KEEP / 继承所属要素组迁移|
|UI-0369|streamlit_app.py:3055 `_render_knowledge_detail`|caption|'许可/使用说明：' + document.license_note|KEEP / 继承所属要素组迁移|
|UI-0370|streamlit_app.py:3067 `_render_knowledge_detail`|status_badge|display_knowledge_review_status(document.review_status)|KEEP / 继承所属要素组迁移|
|UI-0371|streamlit_app.py:3070 `_render_knowledge_detail`|caption|f'下次复核：{document.review_due_at.isoformat()}' + ('（已到期，AI 暂不使用）' if not ai_eligible else '')|KEEP / 继承所属要素组迁移|
|UI-0372|streamlit_app.py:3072 `_render_knowledge_detail`|caption|f'审核人：{document.reviewed_by} · 审核时间：{_fmt_dt(document.reviewed_at)}'|KEEP / 继承所属要素组迁移|
|UI-0373|streamlit_app.py:3074 `_render_knowledge_detail`|caption|'审核说明：' + document.review_comment|KEEP / 继承所属要素组迁移|
|UI-0374|streamlit_app.py:3076 `_render_knowledge_detail`|caption|f'已建立 {len(chunks)} 个可追溯知识片段；仅批准后可被检索。'|KEEP / 继承所属要素组迁移|
|UI-0375|streamlit_app.py:3082 `_render_knowledge_detail`|text_area|'审核说明（可选）'|KEEP / 继承所属要素组迁移|
|UI-0376|streamlit_app.py:3084 `_render_knowledge_detail`|button|'批准并允许 AI 引用'|KEEP / 继承所属要素组迁移|
|UI-0377|streamlit_app.py:3093 `_render_knowledge_detail`|button|'退回资料'|KEEP / 继承所属要素组迁移|
|UI-0378|streamlit_app.py:3051 `_render_knowledge_detail`|caption|'原始来源链接仅供高级核对，不在普通页面直接打开接口地址。'|KEEP / 继承所属要素组迁移|
|UI-0379|streamlit_app.py:3064 `_render_knowledge_detail`|caption|'出版信息：' + ' · '.join(publication_parts)|KEEP / 继承所属要素组迁移|
|UI-0380|streamlit_app.py:3080 `_render_knowledge_detail`|caption|f'{usage.feature or usage.output_type} · {_fmt_dt(usage.created_at)}'|KEEP / 继承所属要素组迁移|
|UI-0381|streamlit_app.py:3142 `_render_knowledge_detail`|download_button|'下载原始文件'|KEEP / 继承所属要素组迁移|
|UI-0382|streamlit_app.py:3144 `_render_knowledge_detail`|caption|'原始文件目前不可用。'|KEEP / 继承所属要素组迁移|
|UI-0383|streamlit_app.py:3146 `_render_knowledge_detail`|expander|'高级信息'|KEEP / 继承所属要素组迁移|
|UI-0384|streamlit_app.py:3147 `_render_knowledge_detail`|caption|'内部标识和原始元数据仅供授权人员核对。'|KEEP / 继承所属要素组迁移|
|UI-0385|streamlit_app.py:3103 `_render_knowledge_detail`|expander|'版本与归档'|KEEP / 继承所属要素组迁移|
|UI-0386|streamlit_app.py:3104 `_render_knowledge_detail`|caption|'归档后仍保留审计记录，但不会继续供 AI 正式引用。新版本须再次经过人工审核。'|KEEP / 继承所属要素组迁移|
|UI-0387|streamlit_app.py:3149 `_render_knowledge_detail`|dataframe|pd.DataFrame([{'原状态': _label(item.previous_status), '新状态': _label(item.new_status), '审核人': item.reviewer or '未记录', '时间': _fmt_dt(item.created_at)} for item in audits])|KEEP / 继承所属要素组迁移|
|UI-0388|streamlit_app.py:3158 `_render_knowledge_detail`|expander|'查看原始技术信息'|KEEP / 继承所属要素组迁移|
|UI-0389|streamlit_app.py:3115 `_render_knowledge_detail`|form|f'knowledge-replacement-{key_scope}-{document.id}'|KEEP / 继承所属要素组迁移|
|UI-0390|streamlit_app.py:3116 `_render_knowledge_detail`|text_input|'新版本号'|KEEP / 继承所属要素组迁移|
|UI-0391|streamlit_app.py:3117 `_render_knowledge_detail`|text_area|'新版本摘要'|KEEP / 继承所属要素组迁移|
|UI-0392|streamlit_app.py:3118 `_render_knowledge_detail`|form_submit_button|'保存为待审核新版本'|KEEP / 继承所属要素组迁移|
|UI-0393|streamlit_app.py:3172 `_render_knowledge_search`|text_input|'关键词'|KEEP / 继承所属要素组迁移|
|UI-0394|streamlit_app.py:3173 `_render_knowledge_search`|selectbox|'来源'|KEEP / 继承所属要素组迁移|
|UI-0395|streamlit_app.py:3206 `_render_knowledge_search`|warning|error|KEEP / 继承所属要素组迁移|
|UI-0396|streamlit_app.py:3225 `_render_knowledge_search`|caption|f'{result.source_name} · {result.source_organization}'|KEEP / 继承所属要素组迁移|
|UI-0397|streamlit_app.py:3226 `_render_knowledge_search`|caption|result.subtitle|KEEP / 继承所属要素组迁移|
|UI-0398|streamlit_app.py:3232 `_render_knowledge_search`|button|'查看'|KEEP / 继承所属要素组迁移|
|UI-0399|streamlit_app.py:3228 `_render_knowledge_search`|caption|'药物标准资料 · 用于统一药物名称与同义名称'|KEEP / 继承所属要素组迁移|
|UI-0400|streamlit_app.py:3238 `_render_knowledge_search`|button|'已保存'|KEEP / 继承所属要素组迁移|
|UI-0401|streamlit_app.py:3239 `_render_knowledge_search`|button|'查看已保存资料'|KEEP / 继承所属要素组迁移|
|UI-0402|streamlit_app.py:3242 `_render_knowledge_search`|button|'保存到知识库'|KEEP / 继承所属要素组迁移|
|UI-0403|streamlit_app.py:3230 `_render_knowledge_search`|caption|result.summary[:220]|KEEP / 继承所属要素组迁移|
|UI-0404|streamlit_app.py:3271 `_render_knowledge_source_cards`|info|'WHO ICD-11 需要在安全配置中提供官方 API 凭证；未配置前不会发起查询，也不会把分类结果当作诊断。'|KEEP / 继承所属要素组迁移|
|UI-0405|streamlit_app.py:3262 `_render_knowledge_source_cards`|caption|source.organization or KNOWLEDGE_SOURCE_PROVIDER_LABELS.get(source.source_code, source.provider)|KEEP / 继承所属要素组迁移|
|UI-0406|streamlit_app.py:3263 `_render_knowledge_source_cards`|caption|f"{KNOWLEDGE_SOURCE_TYPE_LABELS.get(source.source_type, '医学资料')} · {_knowledge_source_status(source)}"|KEEP / 继承所属要素组迁移|
|UI-0407|streamlit_app.py:3265 `_render_knowledge_source_cards`|button|'搜索'|KEEP / 继承所属要素组迁移|
|UI-0408|streamlit_app.py:3267 `_render_knowledge_source_cards`|button|'配置说明'|KEEP / 继承所属要素组迁移|
|UI-0409|streamlit_app.py:3269 `_render_knowledge_source_cards`|caption|'暂未启用'|KEEP / 继承所属要素组迁移|
|UI-0410|streamlit_app.py:3278 `_render_knowledge_add_form`|expander|'添加资料'|KEEP / 继承所属要素组迁移|
|UI-0411|streamlit_app.py:3279 `_render_knowledge_add_form`|radio|'添加方式'|KEEP / 继承所属要素组迁移|
|UI-0412|streamlit_app.py:3281 `_render_knowledge_add_form`|form|'knowledge-manual-form'|KEEP / 继承所属要素组迁移|
|UI-0413|streamlit_app.py:3282 `_render_knowledge_add_form`|text_input|'标题 *'|KEEP / 继承所属要素组迁移|
|UI-0414|streamlit_app.py:3283 `_render_knowledge_add_form`|selectbox|'分类 *'|KEEP / 继承所属要素组迁移|
|UI-0415|streamlit_app.py:3284 `_render_knowledge_add_form`|text_area|'摘要'|KEEP / 继承所属要素组迁移|
|UI-0416|streamlit_app.py:3285 `_render_knowledge_add_form`|text_area|'正文'|KEEP / 继承所属要素组迁移|
|UI-0417|streamlit_app.py:3286 `_render_knowledge_add_form`|selectbox|'资料来源类型'|KEEP / 继承所属要素组迁移|
|UI-0418|streamlit_app.py:3287 `_render_knowledge_add_form`|text_input|'来源名称'|KEEP / 继承所属要素组迁移|
|UI-0419|streamlit_app.py:3288 `_render_knowledge_add_form`|text_input|'版本'|KEEP / 继承所属要素组迁移|
|UI-0420|streamlit_app.py:3289 `_render_knowledge_add_form`|date_input|'下次复核日期'|KEEP / 继承所属要素组迁移|
|UI-0421|streamlit_app.py:3290 `_render_knowledge_add_form`|text_input|'标签'|KEEP / 继承所属要素组迁移|
|UI-0422|streamlit_app.py:3291 `_render_knowledge_add_form`|caption|'审核状态：草稿。只有完成审核的资料才能在未来作为 AI 的正式知识来源。'|KEEP / 继承所属要素组迁移|
|UI-0423|streamlit_app.py:3292 `_render_knowledge_add_form`|form_submit_button|'保存草稿'|KEEP / 继承所属要素组迁移|
|UI-0424|streamlit_app.py:3308 `_render_knowledge_add_form`|form|'knowledge-upload-form'|KEEP / 继承所属要素组迁移|
|UI-0425|streamlit_app.py:3309 `_render_knowledge_add_form`|file_uploader|'选择资料文件'|KEEP / 继承所属要素组迁移|
|UI-0426|streamlit_app.py:3310 `_render_knowledge_add_form`|selectbox|'分类 *'|KEEP / 继承所属要素组迁移|
|UI-0427|streamlit_app.py:3311 `_render_knowledge_add_form`|text_input|'资料标题（可留空，默认使用文件名）'|KEEP / 继承所属要素组迁移|
|UI-0428|streamlit_app.py:3312 `_render_knowledge_add_form`|selectbox|'资料来源类型'|KEEP / 继承所属要素组迁移|
|UI-0429|streamlit_app.py:3313 `_render_knowledge_add_form`|text_input|'来源名称'|KEEP / 继承所属要素组迁移|
|UI-0430|streamlit_app.py:3314 `_render_knowledge_add_form`|text_input|'版本'|KEEP / 继承所属要素组迁移|
|UI-0431|streamlit_app.py:3315 `_render_knowledge_add_form`|text_input|'作者（如适用）'|KEEP / 继承所属要素组迁移|
|UI-0432|streamlit_app.py:3316 `_render_knowledge_add_form`|text_input|'出版社（如适用）'|KEEP / 继承所属要素组迁移|
|UI-0433|streamlit_app.py:3317 `_render_knowledge_add_form`|text_input|'出版年份（如适用）'|KEEP / 继承所属要素组迁移|
|UI-0434|streamlit_app.py:3318 `_render_knowledge_add_form`|text_input|'上传来源'|KEEP / 继承所属要素组迁移|
|UI-0435|streamlit_app.py:3319 `_render_knowledge_add_form`|date_input|'下次复核日期'|KEEP / 继承所属要素组迁移|
|UI-0436|streamlit_app.py:3320 `_render_knowledge_add_form`|text_input|'标签'|KEEP / 继承所属要素组迁移|
|UI-0437|streamlit_app.py:3321 `_render_knowledge_add_form`|text_area|'版权/授权说明 *'|KEEP / 继承所属要素组迁移|
|UI-0438|streamlit_app.py:3322 `_render_knowledge_add_form`|caption|'教材与参考书只能上传您拥有合法使用权的文件。文件默认待审核，不会自动作为 AI 来源或医疗规则。'|KEEP / 继承所属要素组迁移|
|UI-0439|streamlit_app.py:3323 `_render_knowledge_add_form`|form_submit_button|'登记上传资料'|KEEP / 继承所属要素组迁移|
|UI-0440|streamlit_app.py:3294 `_render_knowledge_add_form`|error|'请填写标题和来源名称。'|KEEP / 继承所属要素组迁移|
|UI-0441|streamlit_app.py:3325 `_render_knowledge_add_form`|error|'请选择文件，填写来源名称和版权/授权说明。'|KEEP / 继承所属要素组迁移|
|UI-0442|streamlit_app.py:3356 `_render_saved_knowledge`|text_input|'搜索已保存资料'|KEEP / 继承所属要素组迁移|
|UI-0443|streamlit_app.py:3357 `_render_saved_knowledge`|selectbox|'分类'|KEEP / 继承所属要素组迁移|
|UI-0444|streamlit_app.py:3358 `_render_saved_knowledge`|selectbox|'审核状态'|KEEP / 继承所属要素组迁移|
|UI-0445|streamlit_app.py:3376 `_render_saved_knowledge`|button|document.title|KEEP / 继承所属要素组迁移|
|UI-0446|streamlit_app.py:3380 `_render_saved_knowledge`|caption|f'{display_knowledge_category(document.category)} · {source_label}'|KEEP / 继承所属要素组迁移|
|UI-0447|streamlit_app.py:3381 `_render_saved_knowledge`|caption|f'{display_knowledge_review_status(document.review_status)} · {ai_status}'|KEEP / 继承所属要素组迁移|
|UI-0448|streamlit_app.py:3407 `_render_pending_knowledge`|button|document.title|KEEP / 继承所属要素组迁移|
|UI-0449|streamlit_app.py:3410 `_render_pending_knowledge`|caption|f'{source_label} · {_fmt_dt(document.updated_at)}'|KEEP / 继承所属要素组迁移|
|UI-0450|streamlit_app.py:3447 `render_knowledge_library_entry`|radio|'知识功能'|KEEP / 继承所属要素组迁移|
|UI-0451|streamlit_app.py:3427 `render_knowledge_library_entry`|success|notice|KEEP / 继承所属要素组迁移|
|UI-0452|streamlit_app.py:3442 `render_knowledge_library_entry`|caption|'外部服务只接收去标识化的知识查询，并须返回真实来源信息。'|KEEP / 继承所属要素组迁移|
|UI-0453|streamlit_app.py:3445 `render_knowledge_library_entry`|caption|f'{local_sop_count} 份已审核资料可用于工作流程说明。'|KEEP / 继承所属要素组迁移|
|UI-0454|streamlit_app.py:3453 `render_knowledge_library_entry`|caption|f"已保存 {sum((int(value) for value in review_counts.values()))} 份；已批准 {int(review_counts.get('APPROVED', 0))} 份；待审核 {int(review_counts.get('PENDING_REVIEW', 0) + review_counts.get('D|KEEP / 继承所属要素组迁移|
|UI-0455|streamlit_app.py:3462 `_integration_card`|caption|description|KEEP / 继承所属要素组迁移|
|UI-0456|streamlit_app.py:3467 `_integration_card`|button|action_label|KEEP / 继承所属要素组迁移|
|UI-0457|streamlit_app.py:3482 `_render_data_package_import`|caption|'适用于合作方交付、历史迁移和设备批量数据。成员日常上传体检报告仍在体检页面完成。'|KEEP / 继承所属要素组迁移|
|UI-0458|streamlit_app.py:3500 `_render_data_package_import`|selectbox|'数据包来源'|KEEP / 继承所属要素组迁移|
|UI-0459|streamlit_app.py:3501 `_render_data_package_import`|file_uploader|'拖拽文件到这里，或点击选择'|KEEP / 继承所属要素组迁移|
|UI-0460|streamlit_app.py:3523 `_render_data_package_import`|success|'数据包检查完成。确认预览后才会写入健康档案。'|KEEP / 继承所属要素组迁移|
|UI-0461|streamlit_app.py:3525 `_render_data_package_import`|metric|'成员'|KEEP / 继承所属要素组迁移|
|UI-0462|streamlit_app.py:3526 `_render_data_package_import`|metric|'健康数据'|KEEP / 继承所属要素组迁移|
|UI-0463|streamlit_app.py:3527 `_render_data_package_import`|metric|'其他资料'|KEEP / 继承所属要素组迁移|
|UI-0464|streamlit_app.py:3528 `_render_data_package_import`|metric|'需要确认'|KEEP / 继承所属要素组迁移|
|UI-0465|streamlit_app.py:3488 `_render_data_package_import`|download_button|'下载数据模板'|KEEP / 继承所属要素组迁移|
|UI-0466|streamlit_app.py:3495 `_render_data_package_import`|download_button|'下载匿名演示数据包'|KEEP / 继承所属要素组迁移|
|UI-0467|streamlit_app.py:3508 `_render_data_package_import`|caption|f'文件：{uploaded.name} · 大小：{uploaded.size / 1024:.1f} KB'|KEEP / 继承所属要素组迁移|
|UI-0468|streamlit_app.py:3509 `_render_data_package_import`|button|'检查数据包'|KEEP / 继承所属要素组迁移|
|UI-0469|streamlit_app.py:3536 `_render_data_package_import`|dataframe|pd.DataFrame(overview)|KEEP / 继承所属要素组迁移|
|UI-0470|streamlit_app.py:3554 `_render_data_package_import`|warning|f'有 {len(unmatched_codes)} 名成员需要确认。'|KEEP / 继承所属要素组迁移|
|UI-0471|streamlit_app.py:3570 `_render_data_package_import`|warning|'该数据包已导入过。可在最近导入记录中查看上次结果。'|KEEP / 继承所属要素组迁移|
|UI-0472|streamlit_app.py:3571 `_render_data_package_import`|button|'确认导入'|KEEP / 继承所属要素组迁移|
|UI-0473|streamlit_app.py:3592 `_render_data_package_import`|metric|'成员'|KEEP / 继承所属要素组迁移|
|UI-0474|streamlit_app.py:3593 `_render_data_package_import`|metric|'新增健康数据'|KEEP / 继承所属要素组迁移|
|UI-0475|streamlit_app.py:3594 `_render_data_package_import`|metric|'跳过重复'|KEEP / 继承所属要素组迁移|
|UI-0476|streamlit_app.py:3595 `_render_data_package_import`|metric|'待人工确认'|KEEP / 继承所属要素组迁移|
|UI-0477|streamlit_app.py:3596 `_render_data_package_import`|caption|'导入记录已保留文件指纹、来源、数量、操作人与时间；页面不显示内部编号。'|KEEP / 继承所属要素组迁移|
|UI-0478|streamlit_app.py:3538 `_render_data_package_import`|expander|f'查看需要确认的项目（{len(inspection.issues)}）'|KEEP / 继承所属要素组迁移|
|UI-0479|streamlit_app.py:3543 `_render_data_package_import`|expander|'查看前20条'|KEEP / 继承所属要素组迁移|
|UI-0480|streamlit_app.py:3544 `_render_data_package_import`|dataframe|pd.DataFrame([{'成员': row.member, '原始名称': row.metric, '平台识别': row.recognized_metric, '数值': row.value, '单位': row.unit, '采集时间': row.observed_at, '来源': row.source} for row in preview])|KEEP / 继承所属要素组迁移|
|UI-0481|streamlit_app.py:3557 `_render_data_package_import`|selectbox|f'外部成员 {code}'|KEEP / 继承所属要素组迁移|
|UI-0482|streamlit_app.py:3586 `_render_data_package_import`|warning|'本次没有写入健康数据。请处理待确认项目后重新导入；现有数据未受影响。'|KEEP / 继承所属要素组迁移|
|UI-0483|streamlit_app.py:3588 `_render_data_package_import`|warning|'数据包已部分导入；其余记录保留为待人工确认，不会被当作正式健康事实。'|KEEP / 继承所属要素组迁移|
|UI-0484|streamlit_app.py:3590 `_render_data_package_import`|success|'导入完成。健康数据已进入标准化、质量检查和现有健康运营流程。'|KEEP / 继承所属要素组迁移|
|UI-0485|streamlit_app.py:3516 `_render_data_package_import`|error|str(exc)|KEEP / 继承所属要素组迁移|
|UI-0486|streamlit_app.py:3519 `_render_data_package_import`|error|'数据包检查未完成。现有健康数据没有受到影响，请确认文件后重试。'|KEEP / 继承所属要素组迁移|
|UI-0487|streamlit_app.py:3582 `_render_data_package_import`|error|'数据包未能导入，所有变更已撤回；现有健康数据没有受到影响。'|KEEP / 继承所属要素组迁移|
|UI-0488|streamlit_app.py:3602 `_render_ai_service_integration`|caption|'AI只辅助整理、摘要和有依据的解释，不决定风险或替代医生。'|KEEP / 继承所属要素组迁移|
|UI-0489|streamlit_app.py:3604 `_render_ai_service_integration`|info|f"当前：{current_type} · {('已配置' if settings.enabled and settings.model else '未配置')}"|KEEP / 继承所属要素组迁移|
|UI-0490|streamlit_app.py:3630 `_render_ai_service_integration`|caption|'此表单仅测试连接，不保存配置。持久配置由部署环境管理；页面不会显示完整密钥。'|KEEP / 继承所属要素组迁移|
|UI-0491|streamlit_app.py:3605 `_render_ai_service_integration`|form|'integration-ai-form'|KEEP / 继承所属要素组迁移|
|UI-0492|streamlit_app.py:3606 `_render_ai_service_integration`|radio|'服务类型'|KEEP / 继承所属要素组迁移|
|UI-0493|streamlit_app.py:3607 `_render_ai_service_integration`|text_input|'服务地址'|KEEP / 继承所属要素组迁移|
|UI-0494|streamlit_app.py:3608 `_render_ai_service_integration`|text_input|'模型名称'|KEEP / 继承所属要素组迁移|
|UI-0495|streamlit_app.py:3609 `_render_ai_service_integration`|text_input|'API Key'|KEEP / 继承所属要素组迁移|
|UI-0496|streamlit_app.py:3615 `_render_ai_service_integration`|form_submit_button|'测试连接'|KEEP / 继承所属要素组迁移|
|UI-0497|streamlit_app.py:3625 `_render_ai_service_integration`|caption|'连接测试未发送成员健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0498|streamlit_app.py:3610 `_render_ai_service_integration`|expander|'高级设置'|KEEP / 继承所属要素组迁移|
|UI-0499|streamlit_app.py:3611 `_render_ai_service_integration`|number_input|'连接超时（秒）'|KEEP / 继承所属要素组迁移|
|UI-0500|streamlit_app.py:3612 `_render_ai_service_integration`|number_input|'最大输入字符'|KEEP / 继承所属要素组迁移|
|UI-0501|streamlit_app.py:3613 `_render_ai_service_integration`|checkbox|'允许向外部AI服务发送去标识化健康内容'|KEEP / 继承所属要素组迁移|
|UI-0502|streamlit_app.py:3614 `_render_ai_service_integration`|warning|'默认不向外部服务发送健康隐私数据。开启前需完成组织授权和隐私评估。'|KEEP / 继承所属要素组迁移|
|UI-0503|streamlit_app.py:3627 `_render_ai_service_integration`|success|'连接正常，已找到所选模型。测试未发送成员健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0504|streamlit_app.py:3629 `_render_ai_service_integration`|warning|health.reason or 'AI服务暂不可用。测试未发送成员健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0505|streamlit_app.py:3647 `_render_knowledge_service_integration`|metric|'本地内部规范'|KEEP / 继承所属要素组迁移|
|UI-0506|streamlit_app.py:3648 `_render_knowledge_service_integration`|caption|f'{local_count} 份已审核资料'|KEEP / 继承所属要素组迁移|
|UI-0507|streamlit_app.py:3649 `_render_knowledge_service_integration`|metric|'合作方知识服务'|KEEP / 继承所属要素组迁移|
|UI-0508|streamlit_app.py:3650 `_render_knowledge_service_integration`|caption|'必须返回标题、来源、机构和版本'|KEEP / 继承所属要素组迁移|
|UI-0509|streamlit_app.py:3678 `_render_knowledge_service_integration`|caption|'知识数据包需包含资料名称、来源机构、版本或日期以及内容；缺少来源的资料不能正式启用。'|KEEP / 继承所属要素组迁移|
|UI-0510|streamlit_app.py:3679 `_render_knowledge_service_integration`|file_uploader|'上传知识包（可选）'|KEEP / 继承所属要素组迁移|
|UI-0511|streamlit_app.py:3651 `_render_knowledge_service_integration`|form|'integration-knowledge-form'|KEEP / 继承所属要素组迁移|
|UI-0512|streamlit_app.py:3652 `_render_knowledge_service_integration`|text_input|'服务地址'|KEEP / 继承所属要素组迁移|
|UI-0513|streamlit_app.py:3653 `_render_knowledge_service_integration`|text_input|'API Key'|KEEP / 继承所属要素组迁移|
|UI-0514|streamlit_app.py:3657 `_render_knowledge_service_integration`|form_submit_button|'测试连接'|KEEP / 继承所属要素组迁移|
|UI-0515|streamlit_app.py:3680 `_render_knowledge_service_integration`|button|'检查知识包'|KEEP / 继承所属要素组迁移|
|UI-0516|streamlit_app.py:3691 `_render_knowledge_service_integration`|success|f'检查完成：{len(knowledge_inspection.documents)} 份资料、{len(knowledge_inspection.chunks)} 个知识片段、{knowledge_inspection.source_count} 个来源。'|KEEP / 继承所属要素组迁移|
|UI-0517|streamlit_app.py:3692 `_render_knowledge_service_integration`|caption|'确认后仅进入待审核区，不会直接供 AI 使用。'|KEEP / 继承所属要素组迁移|
|UI-0518|streamlit_app.py:3693 `_render_knowledge_service_integration`|button|'确认导入待审核区'|KEEP / 继承所属要素组迁移|
|UI-0519|streamlit_app.py:3704 `_render_knowledge_service_integration`|expander|'查看已审核内部规范'|KEEP / 继承所属要素组迁移|
|UI-0520|streamlit_app.py:3661 `_render_knowledge_service_integration`|warning|'专业知识服务暂不可用；内部规范仍可使用。'|KEEP / 继承所属要素组迁移|
|UI-0521|streamlit_app.py:3685 `_render_knowledge_service_integration`|error|str(exc)|KEEP / 继承所属要素组迁移|
|UI-0522|streamlit_app.py:3688 `_render_knowledge_service_integration`|error|'知识数据包检查未完成，现有知识资料没有受到影响。'|KEEP / 继承所属要素组迁移|
|UI-0523|streamlit_app.py:3698 `_render_knowledge_service_integration`|success|f'已导入 {created} 份待审核资料。完成来源与版本审核后才可启用。'|KEEP / 继承所属要素组迁移|
|UI-0524|streamlit_app.py:3670 `_render_knowledge_service_integration`|success|'连接正常。'|KEEP / 继承所属要素组迁移|
|UI-0525|streamlit_app.py:3672 `_render_knowledge_service_integration`|caption|result.source_name|KEEP / 继承所属要素组迁移|
|UI-0526|streamlit_app.py:3674 `_render_knowledge_service_integration`|warning|'服务已连接，但固定测试查询没有返回可引用资料。'|KEEP / 继承所属要素组迁移|
|UI-0527|streamlit_app.py:3677 `_render_knowledge_service_integration`|warning|'专业知识服务暂不可用；内部规范仍可使用。'|KEEP / 继承所属要素组迁移|
|UI-0528|streamlit_app.py:3702 `_render_knowledge_service_integration`|error|'知识资料未能导入，所有变更已撤回。'|KEEP / 继承所属要素组迁移|
|UI-0529|streamlit_app.py:3716 `_render_device_integration`|dataframe|pd.DataFrame(rows)|KEEP / 继承所属要素组迁移|
|UI-0530|streamlit_app.py:3717 `_render_device_integration`|caption|'设备只负责采集和触达；正式风险仍由平台规则和人工流程判断。'|KEEP / 继承所属要素组迁移|
|UI-0531|streamlit_app.py:3727 `render_more_workspace`|button|'进入系统'|KEEP / 继承所属要素组迁移|
|UI-0532|streamlit_app.py:3729 `render_more_workspace`|expander|'专业资料'|KEEP / 继承所属要素组迁移|
|UI-0533|streamlit_app.py:3734 `render_oversight_summary`|title|'风险监管摘要'|KEEP / 继承所属要素组迁移|
|UI-0534|streamlit_app.py:3735 `render_oversight_summary`|caption|'演示环境 · 仅显示服务汇总，不展示个人疾病、用药、报告或具体指标。'|KEEP / 继承所属要素组迁移|
|UI-0535|streamlit_app.py:3740 `render_oversight_summary`|metric|'医生待复核'|KEEP / 继承所属要素组迁移|
|UI-0536|streamlit_app.py:3741 `render_oversight_summary`|metric|'风险关闭率'|KEEP / 继承所属要素组迁移|
|UI-0537|streamlit_app.py:3742 `render_oversight_summary`|metric|'个人临床信息'|KEEP / 继承所属要素组迁移|
|UI-0538|streamlit_app.py:3748 `render_collaboration_workspace`|radio|'医疗协同内容'|KEEP / 继承所属要素组迁移|
|UI-0539|streamlit_app.py:3772 `render_service_operations_workspace`|radio|'服务状态筛选'|KEEP / 继承所属要素组迁移|
|UI-0540|streamlit_app.py:3793 `render_service_operations_workspace`|caption|f"当前状态：{_label(selected.status)} · 负责人：{selected.assigned_manager or '待分配'}"|KEEP / 继承所属要素组迁移|
|UI-0541|streamlit_app.py:3794 `render_service_operations_workspace`|caption|f"申请时间：{_fmt_dt(selected.requested_at)} · 预计处理：{(_fmt_dt(selected.sla_due_at) if selected.sla_due_at else '待确认')}"|KEEP / 继承所属要素组迁移|
|UI-0542|streamlit_app.py:3802 `render_service_operations_workspace`|form|f'service-operations-schedule-{selected.id}'|KEEP / 继承所属要素组迁移|
|UI-0543|streamlit_app.py:3803 `render_service_operations_workspace`|date_input|'预约日期'|KEEP / 继承所属要素组迁移|
|UI-0544|streamlit_app.py:3804 `render_service_operations_workspace`|time_input|'预约时间'|KEEP / 继承所属要素组迁移|
|UI-0545|streamlit_app.py:3805 `render_service_operations_workspace`|text_input|'服务执行方（可选）'|KEEP / 继承所属要素组迁移|
|UI-0546|streamlit_app.py:3806 `render_service_operations_workspace`|form_submit_button|'确认服务安排'|KEEP / 继承所属要素组迁移|
|UI-0547|streamlit_app.py:3839 `render_service_operations_workspace`|caption|'完成依据：' + (selected.completion_evidence or '人工确认的服务完成记录')|KEEP / 继承所属要素组迁移|
|UI-0548|streamlit_app.py:3840 `render_service_operations_workspace`|caption|'下一步：' + (selected.next_action or '健康管理师确认后续安排')|KEEP / 继承所属要素组迁移|
|UI-0549|streamlit_app.py:3822 `render_service_operations_workspace`|form|f'service-operations-complete-{selected.id}'|KEEP / 继承所属要素组迁移|
|UI-0550|streamlit_app.py:3823 `render_service_operations_workspace`|text_area|'服务结果'|KEEP / 继承所属要素组迁移|
|UI-0551|streamlit_app.py:3824 `render_service_operations_workspace`|text_input|'完成依据'|KEEP / 继承所属要素组迁移|
|UI-0552|streamlit_app.py:3825 `render_service_operations_workspace`|text_input|'下一步'|KEEP / 继承所属要素组迁移|
|UI-0553|streamlit_app.py:3826 `render_service_operations_workspace`|form_submit_button|'记录服务完成'|KEEP / 继承所属要素组迁移|
|UI-0554|streamlit_app.py:3828 `render_service_operations_workspace`|error|'请填写服务结果、完成依据和下一步。'|KEEP / 继承所属要素组迁移|
|UI-0555|streamlit_app.py:3902 `_render_report_parse_method`|caption|f'解析时间：{_fmt_dt(run.completed_at or run.created_at)}'|KEEP / 继承所属要素组迁移|
|UI-0556|streamlit_app.py:3888 `_render_report_parse_method`|success|'本地AI辅助：已使用'|KEEP / 继承所属要素组迁移|
|UI-0557|streamlit_app.py:3892 `_render_report_parse_method`|caption|' · '.join(details) + '。所有AI辅助结果仍需人工确认后才会入档。'|KEEP / 继承所属要素组迁移|
|UI-0558|streamlit_app.py:3894 `_render_report_parse_method`|info|'本地AI辅助：本次未调用'|KEEP / 继承所属要素组迁移|
|UI-0559|streamlit_app.py:3895 `_render_report_parse_method`|caption|'原因：本报告相关内容已由规则可靠解析。'|KEEP / 继承所属要素组迁移|
|UI-0560|streamlit_app.py:3904 `_render_report_parse_method`|expander|'高级信息'|KEEP / 继承所属要素组迁移|
|UI-0561|streamlit_app.py:3912 `_render_report_parse_method`|caption|'重新解析会创建新的解析记录，不会覆盖已确认入档的健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0562|streamlit_app.py:3897 `_render_report_parse_method`|info|'本地AI辅助：未启用'|KEEP / 继承所属要素组迁移|
|UI-0563|streamlit_app.py:3898 `_render_report_parse_method`|caption|'原因：本地语义模型未启用；规则解析与人工确认仍可正常使用。'|KEEP / 继承所属要素组迁移|
|UI-0564|streamlit_app.py:3900 `_render_report_parse_method`|warning|'本地AI辅助：当前不可用'|KEEP / 继承所属要素组迁移|
|UI-0565|streamlit_app.py:3901 `_render_report_parse_method`|caption|f"原因：{run.llm_failure_reason or '本地开源大模型 当前不可用'}。规则解析与人工确认仍可正常使用。"|KEEP / 继承所属要素组迁移|
|UI-0566|streamlit_app.py:3923 `_run_report_parse_with_progress`|progress|0|KEEP / 继承所属要素组迁移|
|UI-0567|streamlit_app.py:3928 `_run_report_parse_with_progress`|caption|f'已用时：{elapsed_seconds:.1f} 秒'|KEEP / 继承所属要素组迁移|
|UI-0568|streamlit_app.py:3931 `_run_report_parse_with_progress`|caption|'正在识别结构化健康指标。'|KEEP / 继承所属要素组迁移|
|UI-0569|streamlit_app.py:3934 `_run_report_parse_with_progress`|caption|f'识别结构化指标：{event.rule_candidate_count or 0} 项'|KEEP / 继承所属要素组迁移|
|UI-0570|streamlit_app.py:3938 `_run_report_parse_with_progress`|caption|f'模型：local LLM · {event.message}'|KEEP / 继承所属要素组迁移|
|UI-0571|streamlit_app.py:3943 `_run_report_parse_with_progress`|caption|f"当前：{event.section_name or '复杂检查内容'} · 第 {event.current or 0} / {event.total or 0} 次 · 已完成：{completed} · 待处理：{remaining}"|KEEP / 继承所属要素组迁移|
|UI-0572|streamlit_app.py:3948 `_run_report_parse_with_progress`|progress|(event.current or 0) / event.total|KEEP / 继承所属要素组迁移|
|UI-0573|streamlit_app.py:3956 `_run_report_parse_with_progress`|caption|'复杂检查内容将保留供人工确认，规则解析继续完成。'|KEEP / 继承所属要素组迁移|
|UI-0574|streamlit_app.py:3959 `_run_report_parse_with_progress`|caption|'本报告没有需要本地AI辅助整理的复杂检查内容。'|KEEP / 继承所属要素组迁移|
|UI-0575|streamlit_app.py:3980 `_run_report_parse_with_progress`|caption|' · '.join(completion)|KEEP / 继承所属要素组迁移|
|UI-0576|streamlit_app.py:3981 `_run_report_parse_with_progress`|progress|1.0|KEEP / 继承所属要素组迁移|
|UI-0577|streamlit_app.py:4012 `render_report_review`|caption|f"{run.detected_hospital or '体检机构待补充'} · {run.detected_report_date or '体检日期未识别'} · 报告整理完成"|KEEP / 继承所属要素组迁移|
|UI-0578|streamlit_app.py:4006 `render_report_review`|error|'未找到体检报告解析记录。'|KEEP / 继承所属要素组迁移|
|UI-0579|streamlit_app.py:4010 `render_report_review`|warning|'该报告为扫描件，需要文字识别后继续解析。原文件已保留，系统不会伪造解析结果。'|KEEP / 继承所属要素组迁移|
|UI-0580|streamlit_app.py:4018 `render_report_review`|caption|'处理方式：' + _report_risk_next_step(str(report_risk['level']))|KEEP / 继承所属要素组迁移|
|UI-0581|streamlit_app.py:4054 `render_report_review`|success|f'本次重新解析完成，识别 {run.candidate_count} 项候选资料；所有结果仍需人工确认后才会入档。'|KEEP / 继承所属要素组迁移|
|UI-0582|streamlit_app.py:4071 `render_report_review`|caption|'异常指标、影像检查和随访建议均保留来源依据；人工确认前不会作为正式医疗结论。'|KEEP / 继承所属要素组迁移|
|UI-0583|streamlit_app.py:4072 `render_report_review`|expander|f'需要医生复核 · 影像与检查 · {len(findings)} 项'|KEEP / 继承所属要素组迁移|
|UI-0584|streamlit_app.py:4076 `render_report_review`|expander|f'关键健康指标 · {len(observations)} 项'|KEEP / 继承所属要素组迁移|
|UI-0585|streamlit_app.py:4078 `render_report_review`|expander|f'主要异常与健康问题 · {len(management)} 项'|KEEP / 继承所属要素组迁移|
|UI-0586|streamlit_app.py:4080 `render_report_review`|expander|f'建议复查 · {len(followups)} 项'|KEEP / 继承所属要素组迁移|
|UI-0587|streamlit_app.py:4082 `render_report_review`|expander|f'需要人工核对内容 · {len(manual)} 项'|KEEP / 继承所属要素组迁移|
|UI-0588|streamlit_app.py:4084 `render_report_review`|expander|f'一般记录 · {len(general)} 项'|KEEP / 继承所属要素组迁移|
|UI-0589|streamlit_app.py:4087 `render_report_review`|expander|'查看全部指标'|KEEP / 继承所属要素组迁移|
|UI-0590|streamlit_app.py:4089 `render_report_review`|dataframe|pd.DataFrame(rows)|KEEP / 继承所属要素组迁移|
|UI-0591|streamlit_app.py:4091 `render_report_review`|expander|'查看解析详情（高级信息）'|KEEP / 继承所属要素组迁移|
|UI-0592|streamlit_app.py:4093 `render_report_review`|caption|'如原始文件已更新，可在此重新整理；已确认资料和长期健康档案不会被覆盖。'|KEEP / 继承所属要素组迁移|
|UI-0593|streamlit_app.py:4115 `render_report_review`|expander|'查看完整文件'|KEEP / 继承所属要素组迁移|
|UI-0594|streamlit_app.py:4075 `render_report_review`|caption|f'其余 {len(findings) - 3} 项请在完整报告中继续处理。'|KEEP / 继承所属要素组迁移|
|UI-0595|streamlit_app.py:4113 `render_report_review`|caption|'查看历史解析'|KEEP / 继承所属要素组迁移|
|UI-0596|streamlit_app.py:4114 `render_report_review`|dataframe|pd.DataFrame([{'解析时间': _fmt_dt(old_run.completed_at or old_run.created_at), '解析方式': '混合解析' if old_run.llm_used else '规则解析', '解析器版本': old_run.parser_version, '本地AI辅助': f'LLM {old_ru|KEEP / 继承所属要素组迁移|
|UI-0597|streamlit_app.py:4118 `render_report_review`|download_button|'查看完整文件'|KEEP / 继承所属要素组迁移|
|UI-0598|streamlit_app.py:4120 `render_report_review`|warning|'原始报告文件不可用。'|KEEP / 继承所属要素组迁移|
|UI-0599|streamlit_app.py:4051 `render_report_review`|caption|'新增或持续项目不会自动形成医学结论；请在下方按“仅记录、健康管理、医生复核或建议复查”完成人工分流。'|KEEP / 继承所属要素组迁移|
|UI-0600|streamlit_app.py:4106 `render_report_review`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0601|streamlit_app.py:4109 `render_report_review`|error|'报告重新解析失败。原有解析记录和已确认健康数据均未改变。'|KEEP / 继承所属要素组迁移|
|UI-0602|streamlit_app.py:4151 `_render_baseline_draft_action`|caption|'初稿只汇总已确认的报告资料和既有健康档案；缺失项目会明确标为待补充。'|KEEP / 继承所属要素组迁移|
|UI-0603|streamlit_app.py:4152 `_render_baseline_draft_action`|button|'生成健康基线初稿'|KEEP / 继承所属要素组迁移|
|UI-0604|streamlit_app.py:4128 `_render_baseline_draft_action`|caption|'该成员已有正式健康基线。本报告会用于长期体检比较，不会覆盖初始基线。'|KEEP / 继承所属要素组迁移|
|UI-0605|streamlit_app.py:4135 `_render_baseline_draft_action`|info|'当前年度仍在资料收集期，可将这份初始报告合并进同一份健康基线初稿。'|KEEP / 继承所属要素组迁移|
|UI-0606|streamlit_app.py:4136 `_render_baseline_draft_action`|button|'纳入当前年度基线初稿'|KEEP / 继承所属要素组迁移|
|UI-0607|streamlit_app.py:4148 `_render_baseline_draft_action`|caption|'完成至少一项报告资料的人工确认后，可生成健康基线初稿。'|KEEP / 继承所属要素组迁移|
|UI-0608|streamlit_app.py:4133 `_render_baseline_draft_action`|info|'本报告已纳入当前年度健康基线初稿，正在等待资料收集完成与人工确认。'|KEEP / 继承所属要素组迁移|
|UI-0609|streamlit_app.py:4157 `_render_baseline_draft_action`|success|'已生成健康基线初稿，请补充资料并确认。'|KEEP / 继承所属要素组迁移|
|UI-0610|streamlit_app.py:4141 `_render_baseline_draft_action`|success|'已纳入当前年度健康基线初稿。'|KEEP / 继承所属要素组迁移|
|UI-0611|streamlit_app.py:4160 `_render_baseline_draft_action`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0612|streamlit_app.py:4144 `_render_baseline_draft_action`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0613|streamlit_app.py:4164 `_render_report_candidate_group`|subheader|f'{title} {len(candidates)}'|KEEP / 继承所属要素组迁移|
|UI-0614|streamlit_app.py:4166 `_render_report_candidate_group`|caption|'暂无项目。'|KEEP / 继承所属要素组迁移|
|UI-0615|streamlit_app.py:4171 `_render_report_candidate_group`|dataframe|pd.DataFrame(rows)|KEEP / 继承所属要素组迁移|
|UI-0616|streamlit_app.py:4172 `_render_report_candidate_group`|expander|'逐项查看依据'|KEEP / 继承所属要素组迁移|
|UI-0617|streamlit_app.py:4180 `_render_report_candidate_group`|expander|f'处理：{_report_candidate_label(item)}'|KEEP / 继承所属要素组迁移|
|UI-0618|streamlit_app.py:4187 `_render_report_candidate_group`|caption|f"检查：{_report_section_display(item.source_section)} · 第 {item.source_page or '—'} 页"|KEEP / 继承所属要素组迁移|
|UI-0619|streamlit_app.py:4193 `_render_report_candidate_group`|caption|f"来源：第 {item.source_page or '—'} 页 · {_report_section_display(item.source_section)}"|KEEP / 继承所属要素组迁移|
|UI-0620|streamlit_app.py:4203 `_render_report_manual_review_group`|subheader|f'需要人工核对内容 {len(candidates)}'|KEEP / 继承所属要素组迁移|
|UI-0621|streamlit_app.py:4205 `_render_report_manual_review_group`|caption|'没有检测到无法可靠恢复的文本。'|KEEP / 继承所属要素组迁移|
|UI-0622|streamlit_app.py:4209 `_render_report_manual_review_group`|caption|'系统未自动生成正式医疗建议；请核对原报告后再人工录入，不会自动创建任务或进入风险评估。'|KEEP / 继承所属要素组迁移|
|UI-0623|streamlit_app.py:4210 `_render_report_manual_review_group`|caption|f"来源：第 {item.source_page or '—'} 页 · {_report_section_display(item.source_section)}"|KEEP / 继承所属要素组迁移|
|UI-0624|streamlit_app.py:4217 `_render_report_observation_actions`|caption|f"当前状态：{_label(candidate.status, context='report_candidate')}"|KEEP / 继承所属要素组迁移|
|UI-0625|streamlit_app.py:4232 `_render_report_observation_actions`|button|'确认入档'|KEEP / 继承所属要素组迁移|
|UI-0626|streamlit_app.py:4223 `_render_report_observation_actions`|warning|'该健康指标可能已经入档。为避免重复写入，本次候选仍保留待人工确认。'|KEEP / 继承所属要素组迁移|
|UI-0627|streamlit_app.py:4251 `_render_report_observation_actions`|expander|'其他处理'|KEEP / 继承所属要素组迁移|
|UI-0628|streamlit_app.py:4252 `_render_report_observation_actions`|button|'忽略'|KEEP / 继承所属要素组迁移|
|UI-0629|streamlit_app.py:4256 `_render_report_observation_actions`|button|'人工修正'|KEEP / 继承所属要素组迁移|
|UI-0630|streamlit_app.py:4224 `_render_report_observation_actions`|expander|'其他处理'|KEEP / 继承所属要素组迁移|
|UI-0631|streamlit_app.py:4225 `_render_report_observation_actions`|caption|f'已有记录：{display_observation(duplicate.metric_code)} {duplicate.value_numeric} {duplicate.unit} · {_fmt_dt(duplicate.observed_at)}'|KEEP / 继承所属要素组迁移|
|UI-0632|streamlit_app.py:4226 `_render_report_observation_actions`|button|'忽略重复项'|KEEP / 继承所属要素组迁移|
|UI-0633|streamlit_app.py:4259 `_render_report_observation_actions`|form|f'{key_scope}-correct-form-{candidate.id}'|KEEP / 继承所属要素组迁移|
|UI-0634|streamlit_app.py:4262 `_render_report_observation_actions`|selectbox|'对应健康指标'|KEEP / 继承所属要素组迁移|
|UI-0635|streamlit_app.py:4267 `_render_report_observation_actions`|text_input|'数值'|KEEP / 继承所属要素组迁移|
|UI-0636|streamlit_app.py:4268 `_render_report_observation_actions`|text_input|'单位'|KEEP / 继承所属要素组迁移|
|UI-0637|streamlit_app.py:4269 `_render_report_observation_actions`|text_input|'修正原因'|KEEP / 继承所属要素组迁移|
|UI-0638|streamlit_app.py:4270 `_render_report_observation_actions`|form_submit_button|'保存修正'|KEEP / 继承所属要素组迁移|
|UI-0639|streamlit_app.py:4280 `_render_report_finding_actions`|button|'请医生复核'|KEEP / 继承所属要素组迁移|
|UI-0640|streamlit_app.py:4278 `_render_report_finding_actions`|caption|f"当前状态：{_label(candidate.status, context='report_candidate')}"|KEEP / 继承所属要素组迁移|
|UI-0641|streamlit_app.py:4284 `_render_report_finding_actions`|expander|'其他处理'|KEEP / 继承所属要素组迁移|
|UI-0642|streamlit_app.py:4286 `_render_report_finding_actions`|button|'纳入健康管理'|KEEP / 继承所属要素组迁移|
|UI-0643|streamlit_app.py:4290 `_render_report_finding_actions`|button|'仅保留记录'|KEEP / 继承所属要素组迁移|
|UI-0644|streamlit_app.py:4300 `_render_report_followup_actions`|button|'创建随访任务'|KEEP / 继承所属要素组迁移|
|UI-0645|streamlit_app.py:4298 `_render_report_followup_actions`|caption|f"当前状态：{_label(candidate.status, context='report_candidate')}"|KEEP / 继承所属要素组迁移|
|UI-0646|streamlit_app.py:4323 `render_report_upload`|subheader|'上传体检报告'|KEEP / 继承所属要素组迁移|
|UI-0647|streamlit_app.py:4324 `render_report_upload`|caption|'选择已核对的成员后上传。报告中的姓名仅供人工核对，系统不会据此自动匹配成员。'|KEEP / 继承所属要素组迁移|
|UI-0648|streamlit_app.py:4325 `render_report_upload`|caption|'开始解析后，系统会用规则识别结构化指标，并使用本地AI辅助整理复杂检查结论。'|KEEP / 继承所属要素组迁移|
|UI-0649|streamlit_app.py:4326 `render_report_upload`|file_uploader|'选择报告文件'|KEEP / 继承所属要素组迁移|
|UI-0650|streamlit_app.py:4332 `render_report_upload`|button|'解析进行中…' if in_progress else '开始解析报告'|KEEP / 继承所属要素组迁移|
|UI-0651|streamlit_app.py:4343 `render_report_upload`|info|'该文件此前已上传过；已使用当前规则和本地AI创建新的解析结果。' if duplicate else '报告已完成本地解析，正在进入人工确认。'|KEEP / 继承所属要素组迁移|
|UI-0652|streamlit_app.py:4346 `render_report_upload`|error|'报告无法解析。请确认文件完整、格式受支持，或使用人工处理流程。'|KEEP / 继承所属要素组迁移|
|UI-0653|streamlit_app.py:4356 `render_member_medical_workspace`|radio|'医疗内容'|KEEP / 继承所属要素组迁移|
|UI-0654|streamlit_app.py:4385 `render_member_medical_workspace`|caption|f'时间：{_fmt_dt(selected.start_at)}'|KEEP / 继承所属要素组迁移|
|UI-0655|streamlit_app.py:4400 `render_member_archive`|radio|'成员健康内容'|KEEP / 继承所属要素组迁移|
|UI-0656|streamlit_app.py:4442 `render_health_assessments`|subheader|'健康基线'|KEEP / 继承所属要素组迁移|
|UI-0657|streamlit_app.py:4448 `render_health_assessments`|selectbox|'查看年度'|KEEP / 继承所属要素组迁移|
|UI-0658|streamlit_app.py:4465 `render_health_assessments`|caption|baseline.summary|KEEP / 继承所属要素组迁移|
|UI-0659|streamlit_app.py:4467 `render_health_assessments`|caption|'健康基线只记录周期起点事实；当前风险由确定性规则另行评估。没有风险记录不代表低风险。'|KEEP / 继承所属要素组迁移|
|UI-0660|streamlit_app.py:4550 `render_health_assessments`|expander|'建立年度健康基线初稿或阶段复评'|KEEP / 继承所属要素组迁移|
|UI-0661|streamlit_app.py:4498 `render_health_assessments`|caption|'这是资料完整度，不代表健康评分。'|KEEP / 继承所属要素组迁移|
|UI-0662|streamlit_app.py:4499 `render_health_assessments`|warning|'该初稿仅由已确认报告资料和现有健康档案整理，仍需健康管理师审核后才能成为正式健康基线。'|KEEP / 继承所属要素组迁移|
|UI-0663|streamlit_app.py:4522 `render_health_assessments`|success|f'已建立 · {_fmt_dt(baseline.confirmed_at or baseline.assessed_at)}；确认后已冻结，新健康数据不会覆盖该起点。'|KEEP / 继承所属要素组迁移|
|UI-0664|streamlit_app.py:4551 `render_health_assessments`|form|f'assessment-{patient.id}'|KEEP / 继承所属要素组迁移|
|UI-0665|streamlit_app.py:4552 `render_health_assessments`|selectbox|'评估类型'|KEEP / 继承所属要素组迁移|
|UI-0666|streamlit_app.py:4553 `render_health_assessments`|number_input|'管理周期'|KEEP / 继承所属要素组迁移|
|UI-0667|streamlit_app.py:4554 `render_health_assessments`|text_area|'健康管理摘要'|KEEP / 继承所属要素组迁移|
|UI-0668|streamlit_app.py:4555 `render_health_assessments`|checkbox|'包含需要医生确认的医学判断'|KEEP / 继承所属要素组迁移|
|UI-0669|streamlit_app.py:4556 `render_health_assessments`|form_submit_button|'保存初稿'|KEEP / 继承所属要素组迁移|
|UI-0670|streamlit_app.py:4477 `render_health_assessments`|expander|'重要健康背景'|KEEP / 继承所属要素组迁移|
|UI-0671|streamlit_app.py:4501 `render_health_assessments`|info|'其中包含需要医学判断的内容，正在等待医生复核；健管不能代替医生确认。'|KEEP / 继承所属要素组迁移|
|UI-0672|streamlit_app.py:4508 `render_health_assessments`|button|'确认健康基线'|KEEP / 继承所属要素组迁移|
|UI-0673|streamlit_app.py:4523 `render_health_assessments`|expander|'修订已确认资料'|KEEP / 继承所属要素组迁移|
|UI-0674|streamlit_app.py:4524 `render_health_assessments`|caption|'仅用于纠正原基线事实。后续健康变化应进入当前状态、比较和阶段结果。'|KEEP / 继承所属要素组迁移|
|UI-0675|streamlit_app.py:4545 `render_health_assessments`|expander|'查看健康评估历史'|KEEP / 继承所属要素组迁移|
|UI-0676|streamlit_app.py:4547 `render_health_assessments`|dataframe|pd.DataFrame([{'管理周期': item.cycle_year or item.assessed_at.year, '版本': item.version, '类型': {'BASELINE': '健康基线', 'REASSESSMENT': '阶段复评', 'ANNUAL': '年度评估'}.get(item.assessment_type, |KEEP / 继承所属要素组迁移|
|UI-0677|streamlit_app.py:4502 `render_health_assessments`|button|'提交医生复核'|KEEP / 继承所属要素组迁移|
|UI-0678|streamlit_app.py:4506 `render_health_assessments`|success|'已提交医生复核。'|KEEP / 继承所属要素组迁移|
|UI-0679|streamlit_app.py:4525 `render_health_assessments`|form|f'amend-baseline-{baseline.id}'|KEEP / 继承所属要素组迁移|
|UI-0680|streamlit_app.py:4526 `render_health_assessments`|text_area|'修订原因'|KEEP / 继承所属要素组迁移|
|UI-0681|streamlit_app.py:4527 `render_health_assessments`|text_area|'纠正内容'|KEEP / 继承所属要素组迁移|
|UI-0682|streamlit_app.py:4528 `render_health_assessments`|text_input|'支持依据'|KEEP / 继承所属要素组迁移|
|UI-0683|streamlit_app.py:4529 `render_health_assessments`|form_submit_button|'创建修订版本'|KEEP / 继承所属要素组迁移|
|UI-0684|streamlit_app.py:4557 `render_health_assessments`|error|'请填写人工健康管理摘要。'|KEEP / 继承所属要素组迁移|
|UI-0685|streamlit_app.py:4572 `render_health_assessments`|success|'已保存待确认初稿。'|KEEP / 继承所属要素组迁移|
|UI-0686|streamlit_app.py:4517 `render_health_assessments`|success|'健康基线已确认，并已进入重大健康时间轴。'|KEEP / 继承所属要素组迁移|
|UI-0687|streamlit_app.py:4540 `render_health_assessments`|success|'已创建新的基线修订版本，原版本仍保留。'|KEEP / 继承所属要素组迁移|
|UI-0688|streamlit_app.py:4483 `render_health_assessments`|dataframe|pd.DataFrame([_business_detail_row(item) for item in value if isinstance(item, dict)])|KEEP / 继承所属要素组迁移|
|UI-0689|streamlit_app.py:4487 `render_health_assessments`|caption|str(value['label'])|KEEP / 继承所属要素组迁移|
|UI-0690|streamlit_app.py:4489 `render_health_assessments`|caption|'待补充'|KEEP / 继承所属要素组迁移|
|UI-0691|streamlit_app.py:4520 `render_health_assessments`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0692|streamlit_app.py:4543 `render_health_assessments`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-0693|streamlit_app.py:4577 `render_report_comparison`|subheader|'体检变化对比'|KEEP / 继承所属要素组迁移|
|UI-0694|streamlit_app.py:4578 `render_report_comparison`|caption|'年度起点比较与报告间比较相互独立；只描述已确认事实，不自动判断医学改善或恶化。'|KEEP / 继承所属要素组迁移|
|UI-0695|streamlit_app.py:4605 `render_report_comparison`|selectbox|'较早报告'|KEEP / 继承所属要素组迁移|
|UI-0696|streamlit_app.py:4606 `render_report_comparison`|selectbox|'较新报告'|KEEP / 继承所属要素组迁移|
|UI-0697|streamlit_app.py:4641 `render_report_comparison`|caption|comparison['risk_summary']|KEEP / 继承所属要素组迁移|
|UI-0698|streamlit_app.py:4601 `render_report_comparison`|caption|'至少需要两份已解析并人工确认的体检报告，才能进行变化对比。'|KEEP / 继承所属要素组迁移|
|UI-0699|streamlit_app.py:4608 `render_report_comparison`|caption|'请选择两份不同报告。'|KEEP / 继承所属要素组迁移|
|UI-0700|streamlit_app.py:4616 `render_report_comparison`|dataframe|pd.DataFrame([{'指标': display_observation(str(item['metric'])), '此前': item['previous'] or '—', '当前': item['current'] or '—', '单位': item['unit'] or '—', '变化': item['delta'] if item['|KEEP / 继承所属要素组迁移|
|UI-0701|streamlit_app.py:4594 `render_report_comparison`|caption|baseline_comparison['interpretation']|KEEP / 继承所属要素组迁移|
|UI-0702|streamlit_app.py:4596 `render_report_comparison`|info|'年度健康基线确认后，将在这里显示从健康起点到当前状态的变化。'|KEEP / 继承所属要素组迁移|
|UI-0703|streamlit_app.py:4614 `render_report_comparison`|caption|str(error)|KEEP / 继承所属要素组迁移|
|UI-0704|streamlit_app.py:4617 `render_report_comparison`|expander|'逐项查看依据'|KEEP / 继承所属要素组迁移|
|UI-0705|streamlit_app.py:4634 `render_report_comparison`|expander|'检查结论的查看依据'|KEEP / 继承所属要素组迁移|
|UI-0706|streamlit_app.py:4586 `render_report_comparison`|dataframe|pd.DataFrame([{'指标': _metric_display_name(row['metric']), '年度起点': f"{row['baseline'] or '暂无'} {row['unit'] or ''}".strip(), '当前': f"{row['current'] or '暂无'} {row['unit'] or ''}".st|KEEP / 继承所属要素组迁移|
|UI-0707|streamlit_app.py:4623 `render_report_comparison`|caption|'此前报告'|KEEP / 继承所属要素组迁移|
|UI-0708|streamlit_app.py:4626 `render_report_comparison`|caption|'本次报告'|KEEP / 继承所属要素组迁移|
|UI-0709|streamlit_app.py:4645 `render_intervention_comparison`|subheader|'干预前后数据变化'|KEEP / 继承所属要素组迁移|
|UI-0710|streamlit_app.py:4646 `render_intervention_comparison`|caption|'展示观察到的前后变化，不表示本服务或某项干预造成该变化。'|KEEP / 继承所属要素组迁移|
|UI-0711|streamlit_app.py:4655 `render_intervention_comparison`|selectbox|'指标'|KEEP / 继承所属要素组迁移|
|UI-0712|streamlit_app.py:4656 `render_intervention_comparison`|date_input|'干预开始日'|KEEP / 继承所属要素组迁移|
|UI-0713|streamlit_app.py:4657 `render_intervention_comparison`|selectbox|'比较窗口'|KEEP / 继承所属要素组迁移|
|UI-0714|streamlit_app.py:4651 `render_intervention_comparison`|caption|'需要同一指标在干预前后均有可用数据，才能进行比较。'|KEEP / 继承所属要素组迁移|
|UI-0715|streamlit_app.py:4662 `render_intervention_comparison`|success|f"{display_observation(metric)}：干预前平均 {result['before_summary']:.1f} {result['unit']} → 干预后平均 {result['after_summary']:.1f} {result['unit']}（变化 {result['difference']:+.1f}）"|KEEP / 继承所属要素组迁移|
|UI-0716|streamlit_app.py:4663 `render_intervention_comparison`|caption|result['label']|KEEP / 继承所属要素组迁移|
|UI-0717|streamlit_app.py:4677 `render_intervention_comparison`|caption|'该窗口前后数据不足，暂不显示前后变化。'|KEEP / 继承所属要素组迁移|
|UI-0718|streamlit_app.py:4813 `_render_timeline_v4_trends`|caption|f"睡眠摘要：{_trend_value_summary(sleep_total, hours=True)} · 深度睡眠 {(_trend_value_summary(sleep_deep, hours=True) if sleep_deep else '暂无数据')}"|KEEP / 继承所属要素组迁移|
|UI-0719|streamlit_app.py:4833 `_render_timeline_v4_trends`|caption|f"活动摘要：{_trend_value_summary(steps)} · 活动消耗 {(_trend_value_summary(calories) if calories else '暂无数据')}"|KEEP / 继承所属要素组迁移|
|UI-0720|streamlit_app.py:4842 `_render_timeline_v4_trends`|altair_chart|alt.vconcat(*charts).resolve_scale(x='shared')|KEEP / 继承所属要素组迁移|
|UI-0721|streamlit_app.py:4844 `_render_timeline_v4_trends`|caption|'当前时间范围内暂无可用于趋势展示的健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0722|streamlit_app.py:4840 `_render_timeline_v4_trends`|line_chart|series|KEEP / 继承所属要素组迁移|
|UI-0723|streamlit_app.py:4938 `_timeline_lane_card`|button|label|KEEP / 继承所属要素组迁移|
|UI-0724|streamlit_app.py:4963 `_render_lifecycle_grid`|caption|'该时间范围内暂无重大健康事件。'|KEEP / 继承所属要素组迁移|
|UI-0725|streamlit_app.py:5000 `render_longitudinal_timeline`|subheader|'健康历程'|KEEP / 继承所属要素组迁移|
|UI-0726|streamlit_app.py:5001 `render_longitudinal_timeline`|caption|'按日期查看健康管理、用药、风险和医疗大事件。'|KEEP / 继承所属要素组迁移|
|UI-0727|streamlit_app.py:5092 `render_longitudinal_timeline`|caption|'拖动下方横条两端，直接调整整个健康时间窗口。'|KEEP / 继承所属要素组迁移|
|UI-0728|streamlit_app.py:5102 `render_longitudinal_timeline`|multiselect|'健康趋势（最多选择 4 项）'|KEEP / 继承所属要素组迁移|
|UI-0729|streamlit_app.py:5125 `render_longitudinal_timeline`|radio|'事件筛选'|KEEP / 继承所属要素组迁移|
|UI-0730|streamlit_app.py:5058 `render_longitudinal_timeline`|info|'暂无健康历程数据。上传体检报告或连接健康数据后，这里会展示可调整的长期健康历程。'|KEEP / 继承所属要素组迁移|
|UI-0731|streamlit_app.py:5082 `render_longitudinal_timeline`|button|label|KEEP / 继承所属要素组迁移|
|UI-0732|streamlit_app.py:5114 `render_longitudinal_timeline`|warning|'趋势图最多同时展示 4 项指标，当前仅显示前 4 项。'|KEEP / 继承所属要素组迁移|
|UI-0733|streamlit_app.py:5145 `render_longitudinal_timeline`|slider|'健康历程时间范围'|KEEP / 继承所属要素组迁移|
|UI-0734|streamlit_app.py:5151 `render_longitudinal_timeline`|caption|f'起始：{viewport.start.date().isoformat()} · 结束：{viewport.end.date().isoformat()} · 当前范围：{(viewport.end.date() - viewport.start.date()).days + 1} 天'|KEEP / 继承所属要素组迁移|
|UI-0735|streamlit_app.py:5161 `render_longitudinal_timeline`|caption|f'目前只有 {earliest_date.isoformat()} 一项健康记录。等有更多历史后即可调整时间范围。'|KEEP / 继承所属要素组迁移|
|UI-0736|streamlit_app.py:5173 `render_longitudinal_timeline`|caption|'健康管理 · 用药 · 服务'|KEEP / 继承所属要素组迁移|
|UI-0737|streamlit_app.py:5174 `render_longitudinal_timeline`|caption|'日期'|KEEP / 继承所属要素组迁移|
|UI-0738|streamlit_app.py:5175 `render_longitudinal_timeline`|caption|'风险 · 医疗 · 医生'|KEEP / 继承所属要素组迁移|
|UI-0739|streamlit_app.py:5203 `render_longitudinal_timeline`|caption|'拖动上方时间横条到包含重大健康事件的范围，再点击生命轴事件查看详情。'|KEEP / 继承所属要素组迁移|
|UI-0740|streamlit_app.py:5239 `render_longitudinal_timeline`|dataframe|pd.DataFrame([visible])|KEEP / 继承所属要素组迁移|
|UI-0741|streamlit_app.py:5291 `render_longitudinal_timeline`|dataframe|pd.DataFrame([{key: value for key, value in report_details.items() if value not in {None, ''}}])|KEEP / 继承所属要素组迁移|
|UI-0742|streamlit_app.py:5343 `render_longitudinal_timeline`|button|'查看这段时间的完整健康数据'|KEEP / 继承所属要素组迁移|
|UI-0743|streamlit_app.py:5358 `render_longitudinal_timeline`|caption|'仅显示已有正式记录；没有记录的信息不会被推断。'|KEEP / 继承所属要素组迁移|
|UI-0744|streamlit_app.py:5359 `render_longitudinal_timeline`|button|'查看手术履历详情'|KEEP / 继承所属要素组迁移|
|UI-0745|streamlit_app.py:5380 `render_longitudinal_timeline`|caption|'该比较不表示任何干预造成了该变化。'|KEEP / 继承所属要素组迁移|
|UI-0746|streamlit_app.py:5185 `render_longitudinal_timeline`|button|'查看当前时间范围健康数据'|KEEP / 继承所属要素组迁移|
|UI-0747|streamlit_app.py:5245 `render_longitudinal_timeline`|caption|'当时数据：' + '；'.join((f"{item.get('value')} {item.get('unit', '')}" for item in matches[-3:] if isinstance(item, dict)))|KEEP / 继承所属要素组迁移|
|UI-0748|streamlit_app.py:5283 `render_longitudinal_timeline`|caption|'该次评估未记录额外结构化快照。'|KEEP / 继承所属要素组迁移|
|UI-0749|streamlit_app.py:5320 `render_longitudinal_timeline`|button|'查看体检报告'|KEEP / 继承所属要素组迁移|
|UI-0750|streamlit_app.py:5328 `render_longitudinal_timeline`|button|'查看完整体检'|KEEP / 继承所属要素组迁移|
|UI-0751|streamlit_app.py:5333 `render_longitudinal_timeline`|button|'查看新旧报告对比'|KEEP / 继承所属要素组迁移|
|UI-0752|streamlit_app.py:5339 `render_longitudinal_timeline`|dataframe|pd.DataFrame([{'指标': item.get('label'), '平均': item.get('average'), '单位': item.get('unit'), '数据量': item.get('samples'), '本月变化': item.get('direction')} for item in metrics[:6]])|KEEP / 继承所属要素组迁移|
|UI-0753|streamlit_app.py:5364 `render_longitudinal_timeline`|button|'查看用药与医疗'|KEEP / 继承所属要素组迁移|
|UI-0754|streamlit_app.py:5381 `render_longitudinal_timeline`|button|'查看前后对比'|KEEP / 继承所属要素组迁移|
|UI-0755|streamlit_app.py:5270 `render_longitudinal_timeline`|dataframe|pd.DataFrame([{'指标': display_observation(str(item.get('metric', '—'))), '数值': f"{item.get('value', '—')} {item.get('unit', '')}"} for item in metric_rows[:8] if isinstance(item, di|KEEP / 继承所属要素组迁移|
|UI-0756|streamlit_app.py:5279 `render_longitudinal_timeline`|caption|'基本情况：' + ' · '.join((f'{key}：{value}' for key, value in safe_basic.items() if value not in {None, '', '待补充'}))|KEEP / 继承所属要素组迁移|
|UI-0757|streamlit_app.py:5281 `render_longitudinal_timeline`|caption|'这次评估汇总了当时已确认的健康问题、健康数据和当前管理重点。'|KEEP / 继承所属要素组迁移|
|UI-0758|streamlit_app.py:5398 `render_member_report_upload`|file_uploader|'选择最近一次体检报告'|KEEP / 继承所属要素组迁移|
|UI-0759|streamlit_app.py:5406 `render_member_report_upload`|button|'上传并整理报告'|KEEP / 继承所属要素组迁移|
|UI-0760|streamlit_app.py:5437 `render_member_report_upload`|warning|'当前报告暂时无法完整读取，健康管理团队将进一步处理。'|KEEP / 继承所属要素组迁移|
|UI-0761|streamlit_app.py:5440 `render_member_report_upload`|caption|'本地AI暂不可用，系统已保留规则整理结果，健康管理团队会继续人工确认。'|KEEP / 继承所属要素组迁移|
|UI-0762|streamlit_app.py:5465 `render_member_report_upload`|caption|'处理方式：' + _report_risk_next_step(str(report_risk['level']))|KEEP / 继承所属要素组迁移|
|UI-0763|streamlit_app.py:5473 `render_member_report_upload`|caption|'报告已保留；如需继续上传，请选择另一份体检报告。'|KEEP / 继承所属要素组迁移|
|UI-0764|streamlit_app.py:5474 `render_member_report_upload`|expander|'查看分类结果'|KEEP / 继承所属要素组迁移|
|UI-0765|streamlit_app.py:5420 `render_member_report_upload`|success|'报告已上传，正在整理体检报告……' if not duplicate else '该报告已上传过，已创建新的整理结果供健康管理团队审核。'|KEEP / 继承所属要素组迁移|
|UI-0766|streamlit_app.py:5458 `render_member_report_upload`|status_badge|intake_status|KEEP / 继承所属要素组迁移|
|UI-0767|streamlit_app.py:5477 `render_member_report_upload`|dataframe|pd.DataFrame([{'指标': _report_candidate_label(item), '本次': ' '.join((part for part in (item.normalized_value or item.raw_value or '—', item.unit or '') if part)), '状态': '等待确认' if it|KEEP / 继承所属要素组迁移|
|UI-0768|streamlit_app.py:5491 `render_member_report_upload`|expander|'查看依据'|KEEP / 继承所属要素组迁移|
|UI-0769|streamlit_app.py:5423 `render_member_report_upload`|error|'报告整理遇到问题，请稍后重试或联系健康管理团队。'|KEEP / 继承所属要素组迁移|
|UI-0770|streamlit_app.py:5509 `_render_member_baseline_center`|selectbox|'查看年度'|KEEP / 继承所属要素组迁移|
|UI-0771|streamlit_app.py:5525 `_render_member_baseline_center`|caption|'已由健康管理团队开始整理；成员补充资料后仍需健康管理师确认。'|KEEP / 继承所属要素组迁移|
|UI-0772|streamlit_app.py:5526 `_render_member_baseline_center`|caption|'您补充的内容会标记为成员自述资料，不会自动作为医学确认结论。'|KEEP / 继承所属要素组迁移|
|UI-0773|streamlit_app.py:5548 `_render_member_baseline_center`|caption|f'建立时间：{_fmt_dt(baseline.confirmed_at or baseline.assessed_at)}{update_note}'|KEEP / 继承所属要素组迁移|
|UI-0774|streamlit_app.py:5529 `_render_member_baseline_center`|expander|'补充我的健康资料'|KEEP / 继承所属要素组迁移|
|UI-0775|streamlit_app.py:5559 `_render_member_baseline_center`|expander|'重要健康背景'|KEEP / 继承所属要素组迁移|
|UI-0776|streamlit_app.py:5530 `_render_member_baseline_center`|form|f'member-reported-baseline-{baseline.id}'|KEEP / 继承所属要素组迁移|
|UI-0777|streamlit_app.py:5531 `_render_member_baseline_center`|text_area|'既往史'|KEEP / 继承所属要素组迁移|
|UI-0778|streamlit_app.py:5532 `_render_member_baseline_center`|text_area|'当前用药信息'|KEEP / 继承所属要素组迁移|
|UI-0779|streamlit_app.py:5533 `_render_member_baseline_center`|text_area|'手术 / 住院史'|KEEP / 继承所属要素组迁移|
|UI-0780|streamlit_app.py:5534 `_render_member_baseline_center`|text_area|'家族史'|KEEP / 继承所属要素组迁移|
|UI-0781|streamlit_app.py:5535 `_render_member_baseline_center`|text_area|'生活方式资料'|KEEP / 继承所属要素组迁移|
|UI-0782|streamlit_app.py:5536 `_render_member_baseline_center`|form_submit_button|'提交给健康管理团队'|KEEP / 继承所属要素组迁移|
|UI-0783|streamlit_app.py:5543 `_render_member_baseline_center`|success|'已提交为成员自述资料，等待健康管理团队审核。'|KEEP / 继承所属要素组迁移|
|UI-0784|streamlit_app.py:5565 `_render_member_baseline_center`|dataframe|pd.DataFrame([_business_detail_row(item) for item in value if isinstance(item, dict)])|KEEP / 继承所属要素组迁移|
|UI-0785|streamlit_app.py:5569 `_render_member_baseline_center`|caption|str(value['label'])|KEEP / 继承所属要素组迁移|
|UI-0786|streamlit_app.py:5571 `_render_member_baseline_center`|caption|'待补充'|KEEP / 继承所属要素组迁移|
|UI-0787|streamlit_app.py:5596 `_render_member_center_baseline_entry`|caption|f'建立日期：{_fmt_dt(baseline.confirmed_at or baseline.assessed_at)} · 新体检报告可在下方“体检与检查”上传并进行长期比较。'|KEEP / 继承所属要素组迁移|
|UI-0788|streamlit_app.py:5597 `_render_member_center_baseline_entry`|button|'查看完整健康基线'|KEEP / 继承所属要素组迁移|
|UI-0789|streamlit_app.py:5585 `_render_member_center_baseline_entry`|caption|'健康管理团队正在补充与审核初稿；确认后会成为正式健康基线。'|KEEP / 继承所属要素组迁移|
|UI-0790|streamlit_app.py:5586 `_render_member_center_baseline_entry`|button|'查看健康基线初稿'|KEEP / 继承所属要素组迁移|
|UI-0791|streamlit_app.py:5591 `_render_member_center_baseline_entry`|caption|'上传最近一次体检报告，系统可以帮助整理健康基线初稿。'|KEEP / 继承所属要素组迁移|
|UI-0792|streamlit_app.py:5592 `_render_member_center_baseline_entry`|button|'上传最近体检报告'|KEEP / 继承所属要素组迁移|
|UI-0793|streamlit_app.py:5659 `_render_client_report_intake_entry`|caption|guidance|KEEP / 继承所属要素组迁移|
|UI-0794|streamlit_app.py:5662 `_render_client_report_intake_entry`|button|label|KEEP / 继承所属要素组迁移|
|UI-0795|streamlit_app.py:5670 `_render_client_report_intake_entry`|button|'查看体检与检查'|KEEP / 继承所属要素组迁移|
|UI-0796|streamlit_app.py:5693 `render_member_service_management`|caption|f"可用服务：{len(rows)} 项 · 待处理申请：{sum((item.status != 'COMPLETED' for item in requests))} 项"|KEEP / 继承所属要素组迁移|
|UI-0797|streamlit_app.py:5694 `render_member_service_management`|dataframe|pd.DataFrame([{'服务': item.name, '使用情况': '不限次' if entitlement.total_quota is None else f'已使用 {entitlement.used_quota} / {entitlement.total_quota} 次'} for item, entitlement in rows])|KEEP / 继承所属要素组迁移|
|UI-0798|streamlit_app.py:5702 `render_member_service_management`|caption|f"申请原因：{request.reason} · 负责人：{request.assigned_manager or '待分配'} · SLA：{(_fmt_dt(request.sla_due_at) if request.sla_due_at else '待确认')} · 安排时间：{(_fmt_dt(request.scheduled_at) if r|KEEP / 继承所属要素组迁移|
|UI-0799|streamlit_app.py:5704 `render_member_service_management`|button|'审核服务申请'|KEEP / 继承所属要素组迁移|
|UI-0800|streamlit_app.py:5709 `render_member_service_management`|form|f'service-schedule-{request.id}'|KEEP / 继承所属要素组迁移|
|UI-0801|streamlit_app.py:5710 `render_member_service_management`|date_input|'安排日期'|KEEP / 继承所属要素组迁移|
|UI-0802|streamlit_app.py:5711 `render_member_service_management`|time_input|'安排时间'|KEEP / 继承所属要素组迁移|
|UI-0803|streamlit_app.py:5712 `render_member_service_management`|text_input|'负责人'|KEEP / 继承所属要素组迁移|
|UI-0804|streamlit_app.py:5713 `render_member_service_management`|text_input|'服务执行方（可选）'|KEEP / 继承所属要素组迁移|
|UI-0805|streamlit_app.py:5714 `render_member_service_management`|form_submit_button|'确认服务安排'|KEEP / 继承所属要素组迁移|
|UI-0806|streamlit_app.py:5720 `render_member_service_management`|button|'记录开始服务'|KEEP / 继承所属要素组迁移|
|UI-0807|streamlit_app.py:5726 `render_member_service_management`|form|f'service-complete-{request.id}'|KEEP / 继承所属要素组迁移|
|UI-0808|streamlit_app.py:5727 `render_member_service_management`|text_area|'服务结果摘要'|KEEP / 继承所属要素组迁移|
|UI-0809|streamlit_app.py:5728 `render_member_service_management`|text_input|'完成依据'|KEEP / 继承所属要素组迁移|
|UI-0810|streamlit_app.py:5729 `render_member_service_management`|text_input|'下一步'|KEEP / 继承所属要素组迁移|
|UI-0811|streamlit_app.py:5730 `render_member_service_management`|form_submit_button|'记录服务完成'|KEEP / 继承所属要素组迁移|
|UI-0812|streamlit_app.py:5742 `render_member_service_management`|caption|'完成结果：' + (request.result_summary or '已完成，结果待补充。')|KEEP / 继承所属要素组迁移|
|UI-0813|streamlit_app.py:5743 `render_member_service_management`|caption|'完成依据：' + (request.completion_evidence or '人工确认的服务完成记录')|KEEP / 继承所属要素组迁移|
|UI-0814|streamlit_app.py:5744 `render_member_service_management`|caption|'下一步：' + (request.next_action or '健康管理师确认后续安排')|KEEP / 继承所属要素组迁移|
|UI-0815|streamlit_app.py:5732 `render_member_service_management`|error|'请填写服务结果、完成依据和下一步。'|KEEP / 继承所属要素组迁移|
|UI-0816|streamlit_app.py:5757 `_render_client_service`|radio|'服务内容'|KEEP / 继承所属要素组迁移|
|UI-0817|streamlit_app.py:5810 `_render_client_service`|selectbox|'服务分类'|KEEP / 继承所属要素组迁移|
|UI-0818|streamlit_app.py:5777 `_render_client_service`|caption|f'当前状态：{_label(selected.status)} · 申请时间：{_fmt_dt(selected.requested_at)}'|KEEP / 继承所属要素组迁移|
|UI-0819|streamlit_app.py:5793 `_render_client_service`|caption|f"负责人：{selected.assigned_manager or '待分配'} · 预计处理：{(_fmt_dt(selected.sla_due_at) if selected.sla_due_at else '待确认')}"|KEEP / 继承所属要素组迁移|
|UI-0820|streamlit_app.py:5798 `_render_client_service`|caption|'下一步：' + (selected.next_action or next_member_action)|KEEP / 继承所属要素组迁移|
|UI-0821|streamlit_app.py:5834 `_render_client_service`|success|'服务申请已提交，健康管理师会审核权益与安排。'|KEEP / 继承所属要素组迁移|
|UI-0822|streamlit_app.py:5795 `_render_client_service`|caption|'服务执行方：' + selected.service_provider|KEEP / 继承所属要素组迁移|
|UI-0823|streamlit_app.py:5797 `_render_client_service`|caption|'完成依据：' + (selected.completion_evidence or '人工确认的服务完成记录')|KEEP / 继承所属要素组迁移|
|UI-0824|streamlit_app.py:5804 `_render_client_service`|success|'已取消本次服务申请；如仍有需要，可重新申请。'|KEEP / 继承所属要素组迁移|
|UI-0825|streamlit_app.py:5840 `_render_client_profile`|radio|'个人设置内容'|KEEP / 继承所属要素组迁移|
|UI-0826|streamlit_app.py:5873 `_render_client_profile`|caption|'可查看角色：您本人、负责的健康管理师，以及在需要医学判断时参与的持证医生。'|KEEP / 继承所属要素组迁移|
|UI-0827|streamlit_app.py:5844 `_render_client_profile`|caption|'医生确认后的反馈、服务安排和任务提醒会在相应业务页面显示。'|KEEP / 继承所属要素组迁移|
|UI-0828|streamlit_app.py:5867 `_render_client_profile`|link_button|'连接 Apple 健康'|KEEP / 继承所属要素组迁移|
|UI-0829|streamlit_app.py:5868 `_render_client_profile`|caption|'首次连接与后端配置请参阅项目内《Apple 健康接入说明》。'|KEEP / 继承所属要素组迁移|
|UI-0830|streamlit_app.py:5863 `_render_client_profile`|caption|'Apple 健康授权已完成；此处仅代表已收到桥接同步，不代表全部数据类型均已授权。'|KEEP / 继承所属要素组迁移|
|UI-0831|streamlit_app.py:5866 `_render_client_profile`|caption|'请先在 iPhone 安装 Bridge 后连接 Apple 健康。后台同步由 iOS 系统调度，不承诺实时。'|KEEP / 继承所属要素组迁移|
|UI-0832|streamlit_app.py:5880 `_render_client_profile`|caption|f'用途：{purpose}'|KEEP / 继承所属要素组迁移|
|UI-0833|streamlit_app.py:5886 `_render_client_profile`|button|label|KEEP / 继承所属要素组迁移|
|UI-0834|streamlit_app.py:5883 `_render_client_profile`|caption|f'最近变更：{_fmt_dt(changed_at)} · 来源：成员确认'|KEEP / 继承所属要素组迁移|
|UI-0835|streamlit_app.py:5857 `_render_client_profile`|caption|' · '.join((f'{display_provider(item.provider)}：{_client_device_status(item)}' for item in items))|KEEP / 继承所属要素组迁移|
|UI-0836|streamlit_app.py:5895 `_render_client_profile`|success|'授权状态已更新。'|KEEP / 继承所属要素组迁移|
|UI-0837|streamlit_app.py:5899 `_render_client_profile`|error|'当前授权状态无法更新，请联系健康管理团队。'|KEEP / 继承所属要素组迁移|
|UI-0838|streamlit_app.py:5936 `_render_client_medical_archive`|radio|'医疗档案内容'|KEEP / 继承所属要素组迁移|
|UI-0839|streamlit_app.py:5941 `_render_client_medical_archive`|dataframe|pd.DataFrame([{'药物': item.drug_name or '待补充', '剂量': ' '.join((part for part in (item.dose, item.dose_unit) if part)) or '待补充', '频率': item.frequency or '待补充', '状态': _label(item.stat|KEEP / 继承所属要素组迁移|
|UI-0840|streamlit_app.py:5960 `_render_client_medical_archive`|caption|f'时间：{_fmt_dt(selected.start_at)} · 经确认医疗资料'|KEEP / 继承所属要素组迁移|
|UI-0841|streamlit_app.py:5967 `_render_client_medical_archive`|expander|f'{_fmt_dt(item.reviewed_at)} · 医生反馈'|KEEP / 继承所属要素组迁移|
|UI-0842|streamlit_app.py:5970 `_render_client_medical_archive`|caption|'复核问题：' + item.question_for_doctor|KEEP / 继承所属要素组迁移|
|UI-0843|streamlit_app.py:5989 `render_client_health_hub`|radio|'健康内容'|KEEP / 继承所属要素组迁移|
|UI-0844|streamlit_app.py:6004 `render_member_client_view`|popover|'个人设置'|KEEP / 继承所属要素组迁移|
|UI-0845|streamlit_app.py:6005 `render_member_client_view`|button|'查看个人资料'|KEEP / 继承所属要素组迁移|
|UI-0846|streamlit_app.py:6024 `render_global_alert_workspace`|caption|'健康管理师 · 异常处理'|KEEP / 继承所属要素组迁移|
|UI-0847|streamlit_app.py:6025 `render_global_alert_workspace`|title|'健康异常处理工作台'|KEEP / 继承所属要素组迁移|
|UI-0848|streamlit_app.py:6026 `render_global_alert_workspace`|caption|'处理顺序：核实数据 → 关联或创建健康问题 → 医生复核 → 管理方案与执行任务 → 随访 → 已关闭。'|KEEP / 继承所属要素组迁移|
|UI-0849|streamlit_app.py:6027 `render_global_alert_workspace`|selectbox|'选择成员'|KEEP / 继承所属要素组迁移|
|UI-0850|streamlit_app.py:6050 `render_external_doctor_workspace`|radio|'外部医疗状态'|KEEP / 继承所属要素组迁移|
|UI-0851|streamlit_app.py:6079 `render_external_doctor_workspace`|expander|'登记外部医生协同'|KEEP / 继承所属要素组迁移|
|UI-0852|streamlit_app.py:6080 `render_external_doctor_workspace`|form|'external-referral-form'|KEEP / 继承所属要素组迁移|
|UI-0853|streamlit_app.py:6081 `render_external_doctor_workspace`|selectbox|'成员'|KEEP / 继承所属要素组迁移|
|UI-0854|streamlit_app.py:6083 `render_external_doctor_workspace`|selectbox|'关联内部医生复核（可选）'|KEEP / 继承所属要素组迁移|
|UI-0855|streamlit_app.py:6084 `render_external_doctor_workspace`|text_input|'外部专科 *'|KEEP / 继承所属要素组迁移|
|UI-0856|streamlit_app.py:6085 `render_external_doctor_workspace`|text_area|'转诊原因 *'|KEEP / 继承所属要素组迁移|
|UI-0857|streamlit_app.py:6086 `render_external_doctor_workspace`|text_area|'希望外部医生确认什么 *'|KEEP / 继承所属要素组迁移|
|UI-0858|streamlit_app.py:6087 `render_external_doctor_workspace`|text_input|'外部机构（可选）'|KEEP / 继承所属要素组迁移|
|UI-0859|streamlit_app.py:6088 `render_external_doctor_workspace`|text_input|'外部医生（可选）'|KEEP / 继承所属要素组迁移|
|UI-0860|streamlit_app.py:6089 `render_external_doctor_workspace`|form_submit_button|'登记外部协同'|KEEP / 继承所属要素组迁移|
|UI-0861|streamlit_app.py:6071 `render_external_doctor_workspace`|caption|f'当前状态：{_label(selected.status)} · 预约：{_fmt_dt(selected.appointment_at)}'|KEEP / 继承所属要素组迁移|
|UI-0862|streamlit_app.py:6090 `render_external_doctor_workspace`|error|'请填写专科、转诊原因和协同问题。'|KEEP / 继承所属要素组迁移|
|UI-0863|streamlit_app.py:6095 `render_external_doctor_workspace`|success|'已登记外部医生协同；请由人工完成预约与反馈录入。'|KEEP / 继承所属要素组迁移|
|UI-0864|streamlit_app.py:6100 `render_demo_story`|caption|'演示数据 · 管理故事'|KEEP / 继承所属要素组迁移|
|UI-0865|streamlit_app.py:6101 `render_demo_story`|title|'Demo Executive A：持续健康与代谢管理'|KEEP / 继承所属要素组迁移|
|UI-0866|streamlit_app.py:6104 `render_demo_story`|caption|'所有数据仅用于演示；系统不做自动诊断、处方、停药或剂量调整。'|KEEP / 继承所属要素组迁移|
|UI-0867|streamlit_app.py:6106 `render_demo_story`|button|'进入成员的完整处理记录'|KEEP / 继承所属要素组迁移|
|UI-0868|streamlit_app.py:6113 `render_data_gateway`|caption|f'需要人工复核的数据：{review_count} 条'|KEEP / 继承所属要素组迁移|
|UI-0869|streamlit_app.py:6141 `render_data_gateway`|radio|'数据设备功能'|KEEP / 继承所属要素组迁移|
|UI-0870|streamlit_app.py:6143 `render_data_gateway`|caption|'选择“数据复核”或“上传健康资料”后才会加载对应队列与表单。'|KEEP / 继承所属要素组迁移|
|UI-0871|streamlit_app.py:6136 `render_data_gateway`|caption|f"最近同步：{row['last']}"|KEEP / 继承所属要素组迁移|
|UI-0872|streamlit_app.py:6138 `render_data_gateway`|caption|f'支持数据：{supported}'|KEEP / 继承所属要素组迁移|
|UI-0873|streamlit_app.py:6139 `render_data_gateway`|caption|'医学风险由平台规则与人工判断，不由设备决定。'|KEEP / 继承所属要素组迁移|
|UI-0874|streamlit_app.py:6162 `_render_data_upload_workspace`|subheader|'需要处理的数据问题'|KEEP / 继承所属要素组迁移|
|UI-0875|streamlit_app.py:6167 `_render_data_upload_workspace`|selectbox|'接入成员'|KEEP / 继承所属要素组迁移|
|UI-0876|streamlit_app.py:6169 `_render_data_upload_workspace`|subheader|'上传健康资料'|KEEP / 继承所属要素组迁移|
|UI-0877|streamlit_app.py:6170 `_render_data_upload_workspace`|caption|'支持 CSV、Excel 和 PDF 健康资料。导入前可先预览，系统不会自动作出医疗结论。'|KEEP / 继承所属要素组迁移|
|UI-0878|streamlit_app.py:6164 `_render_data_upload_workspace`|success|'数据同步正常，当前没有需要人工处理的数据。'|KEEP / 继承所属要素组迁移|
|UI-0879|streamlit_app.py:6166 `_render_data_upload_workspace`|info|f'有 {len(records)} 条数据需要人工确认或绑定成员。请在下方处理。'|KEEP / 继承所属要素组迁移|
|UI-0880|streamlit_app.py:6173 `_render_data_upload_workspace`|file_uploader|'选择文件'|KEEP / 继承所属要素组迁移|
|UI-0881|streamlit_app.py:6174 `_render_data_upload_workspace`|checkbox|'仅预览，不写入数据库'|KEEP / 继承所属要素组迁移|
|UI-0882|streamlit_app.py:6175 `_render_data_upload_workspace`|button|'上传文件'|KEEP / 继承所属要素组迁移|
|UI-0883|streamlit_app.py:6189 `_render_data_upload_workspace`|success|f'文件导入{_label(result.status)}：新增 {result.created} 条健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0884|streamlit_app.py:6199 `_render_data_upload_workspace`|button|'同步演示 Oura 数据'|KEEP / 继承所属要素组迁移|
|UI-0885|streamlit_app.py:6204 `_render_data_upload_workspace`|button|'同步演示 Apple Health 数据'|KEEP / 继承所属要素组迁移|
|UI-0886|streamlit_app.py:6211 `_render_data_upload_workspace`|expander|'高级信息：备用导入流程'|KEEP / 继承所属要素组迁移|
|UI-0887|streamlit_app.py:6213 `_render_data_upload_workspace`|file_uploader|'选择演示用 CSV、Excel 或 PDF 文件'|KEEP / 继承所属要素组迁移|
|UI-0888|streamlit_app.py:6214 `_render_data_upload_workspace`|checkbox|'仅预览，不写入数据库'|KEEP / 继承所属要素组迁移|
|UI-0889|streamlit_app.py:6231 `_render_data_upload_workspace`|expander|'高级信息：数据同步记录'|KEEP / 继承所属要素组迁移|
|UI-0890|streamlit_app.py:6192 `_render_data_upload_workspace`|expander|'高级信息'|KEEP / 继承所属要素组迁移|
|UI-0891|streamlit_app.py:6193 `_render_data_upload_workspace`|caption|'仅用于合成演示环境。'|KEEP / 继承所属要素组迁移|
|UI-0892|streamlit_app.py:6194 `_render_data_upload_workspace`|button|'同步演示血压设备数据'|KEEP / 继承所属要素组迁移|
|UI-0893|streamlit_app.py:6203 `_render_data_upload_workspace`|success|f'同步{_label(result.status)}：新增 {result.created} 条健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0894|streamlit_app.py:6209 `_render_data_upload_workspace`|success|f'Apple Health 同步{_label(result.status)}：新增 {result.created} 条，已拦截重复 {result.duplicates} 条。'|KEEP / 继承所属要素组迁移|
|UI-0895|streamlit_app.py:6215 `_render_data_upload_workspace`|button|'验证并导入'|KEEP / 继承所属要素组迁移|
|UI-0896|streamlit_app.py:6229 `_render_data_upload_workspace`|success|f'文件导入{_label(result.status)}：收到 {result.received} 条，有效 {result.valid} 条，新增 {result.created} 条，重复 {result.duplicates} 条，无效 {result.invalid} 条。'|KEEP / 继承所属要素组迁移|
|UI-0897|streamlit_app.py:6234 `_render_data_upload_workspace`|dataframe|pd.DataFrame([{'时间': _fmt_dt(job.started_at), '数据来源': display_provider(job.source_system), '成员': member_names.get(job.patient_id, '未匹配成员'), '状态': _label(job.status), '接收记录': job.re|KEEP / 继承所属要素组迁移|
|UI-0898|streamlit_app.py:6185 `_render_data_upload_workspace`|success|'PDF 健康报告已登记，正在等待人工复核。'|KEEP / 继承所属要素组迁移|
|UI-0899|streamlit_app.py:6198 `_render_data_upload_workspace`|success|f'同步{_label(result.status)}：新增 {result.created} 条。'|KEEP / 继承所属要素组迁移|
|UI-0900|streamlit_app.py:6225 `_render_data_upload_workspace`|success|'PDF 健康报告已登记，正在等待人工复核；系统不会自动做医学结论。'|KEEP / 继承所属要素组迁移|
|UI-0901|streamlit_app.py:6244 `_render_data_review_queue`|subheader|'数据复核队列'|KEEP / 继承所属要素组迁移|
|UI-0902|streamlit_app.py:6246 `_render_data_review_queue`|success|'当前没有待核实、无效、未匹配或等待人工确认的数据。'|KEEP / 继承所属要素组迁移|
|UI-0903|streamlit_app.py:6248 `_render_data_review_queue`|expander|f'{_label(record.status)} · {display_provider(record.source_system)} · 需要人工确认'|KEEP / 继承所属要素组迁移|
|UI-0904|streamlit_app.py:6256 `_render_data_review_queue`|text_input|'更正数值'|KEEP / 继承所属要素组迁移|
|UI-0905|streamlit_app.py:6257 `_render_data_review_queue`|text_input|'更正原因'|KEEP / 继承所属要素组迁移|
|UI-0906|streamlit_app.py:6251 `_render_data_review_queue`|expander|'高级信息'|KEEP / 继承所属要素组迁移|
|UI-0907|streamlit_app.py:6252 `_render_data_review_queue`|caption|'技术详情、原始数据和解析结果仅供授权人员核对。'|KEEP / 继承所属要素组迁移|
|UI-0908|streamlit_app.py:6258 `_render_data_review_queue`|button|'人工更正'|KEEP / 继承所属要素组迁移|
|UI-0909|streamlit_app.py:6263 `_render_data_review_queue`|success|'已保留原始记录，并创建已人工修正的健康数据。'|KEEP / 继承所属要素组迁移|
|UI-0910|streamlit_app.py:6253 `_render_data_review_queue`|expander|'查看原始技术信息'|KEEP / 继承所属要素组迁移|
|UI-0911|streamlit_app.py:6268 `render_member_device_assignments`|subheader|'成员设备分配'|KEEP / 继承所属要素组迁移|
|UI-0912|streamlit_app.py:6269 `render_member_device_assignments`|caption|'“已分配”与“已连接”是不同状态；演示设备不会被显示为真实连接。'|KEEP / 继承所属要素组迁移|
|UI-0913|streamlit_app.py:6270 `render_member_device_assignments`|selectbox|'选择成员以管理设备'|KEEP / 继承所属要素组迁移|
|UI-0914|streamlit_app.py:6289 `render_member_device_assignments`|expander|'添加或更新设备分配'|KEEP / 继承所属要素组迁移|
|UI-0915|streamlit_app.py:6285 `render_member_device_assignments`|caption|f'{display_provider(item.provider)} · 已分配 · {status}'|KEEP / 继承所属要素组迁移|
|UI-0916|streamlit_app.py:6290 `render_member_device_assignments`|form|f'device-assignment-{member.id}'|KEEP / 继承所属要素组迁移|
|UI-0917|streamlit_app.py:6291 `render_member_device_assignments`|selectbox|'设备'|KEEP / 继承所属要素组迁移|
|UI-0918|streamlit_app.py:6292 `render_member_device_assignments`|radio|'设备类别'|KEEP / 继承所属要素组迁移|
|UI-0919|streamlit_app.py:6293 `render_member_device_assignments`|selectbox|'连接状态'|KEEP / 继承所属要素组迁移|
|UI-0920|streamlit_app.py:6294 `render_member_device_assignments`|text_input|'说明（可选）'|KEEP / 继承所属要素组迁移|
|UI-0921|streamlit_app.py:6295 `render_member_device_assignments`|form_submit_button|'保存设备分配'|KEEP / 继承所属要素组迁移|
|UI-0922|streamlit_app.py:6288 `render_member_device_assignments`|caption|f'{display_provider(provider)} · 未分配'|KEEP / 继承所属要素组迁移|
|UI-0923|streamlit_app.py:6303 `render_member_device_assignments`|success|'成员设备分配已保存。'|KEEP / 继承所属要素组迁移|
|UI-0924|streamlit_app.py:6308 `render_risk_rules`|title|'风险规则'|KEEP / 继承所属要素组迁移|
|UI-0925|streamlit_app.py:6309 `render_risk_rules`|caption|'规则用于健康监护与风险分流，不替代医生诊断或急救机构判断。仅已审核且启用的规则可进入风险引擎。'|KEEP / 继承所属要素组迁移|
|UI-0926|streamlit_app.py:6313 `render_risk_rules`|dataframe|pd.DataFrame([{'规则名称': rule.name, '适用数据': '日常健康设备' if rule.applicable_device_class == 'WELLNESS' else '医疗监测设备', '风险等级': _risk_text(rule.risk_level), '状态': _label(rule.review_status|KEEP / 继承所属要素组迁移|
|UI-0927|streamlit_app.py:6314 `render_risk_rules`|info|'当前仅包含明确标记为演示工作流规则的内容，不作为真实医疗临床阈值。'|KEEP / 继承所属要素组迁移|
|UI-0928|streamlit_app.py:6315 `render_risk_rules`|subheader|'生活方式管理规则'|KEEP / 继承所属要素组迁移|
|UI-0929|streamlit_app.py:6316 `render_risk_rules`|caption|'步数、运动与睡眠使用独立的健康管理信号，不生成医疗风险事件，也不会自动升级医生。只有已审核且启用的规则才会在新数据写入时运行。'|KEEP / 继承所属要素组迁移|
|UI-0930|streamlit_app.py:6318 `render_risk_rules`|dataframe|pd.DataFrame([{'规则名称': rule.name, '指标': _metric_display_name(rule.canonical_code), '状态': _label(rule.review_status), '启用': '是' if rule.is_active else '否', '路由': ROUTE_LABELS.get(ru|KEEP / 继承所属要素组迁移|
|UI-0931|streamlit_app.py:6325 `render_risk_rules`|caption|'尚无已配置的生活方式管理规则。系统不会因为步数或睡眠数据自动创建医疗风险。'|KEEP / 继承所属要素组迁移|
|UI-0932|streamlit_app.py:6343 `main`|selectbox|'查看成员'|KEEP / 继承所属要素组迁移|
|UI-0933|streamlit_app.py:6373 `main`|title|'企业高管健康运营中心'|KEEP / 继承所属要素组迁移|
|UI-0934|streamlit_app.py:6374 `main`|warning|'尚未初始化演示数据。请先完成数据库迁移和演示数据初始化。'|KEEP / 继承所属要素组迁移|
|UI-0935|streamlit_app.py:6389 `main`|warning|'[PERF] total %.1f ms'|KEEP / 继承所属要素组迁移|
|UI-0936|streamlit_app.py:6356 `main`|warning|'[PERF] total %.1f ms'|KEEP / 继承所属要素组迁移|
|UI-0937|streamlit_app.py:6360 `main`|warning|'[PERF] total %.1f ms'|KEEP / 继承所属要素组迁移|
|UI-0938|streamlit_app.py:6364 `main`|warning|'[PERF] total %.1f ms'|KEEP / 继承所属要素组迁移|
|UI-0939|streamlit_app.py:6368 `main`|warning|'[PERF] total %.1f ms'|KEEP / 继承所属要素组迁移|
|UI-0940|streamlit_app.py:6375 `main`|warning|'[PERF] total %.1f ms'|KEEP / 继承所属要素组迁移|
|UI-0941|streamlit_app.py:6381 `main`|warning|'[PERF] total %.1f ms'|KEEP / 继承所属要素组迁移|
|UI-0952|src/executive_health_ai/ui/charts/health.py:42 `render_metric_trend`|altair_chart|chart|KEEP / 继承所属要素组迁移|
|UI-0953|src/executive_health_ai/ui/charts/health.py:40 `render_metric_trend`|caption|'暂无足够数据形成趋势。'|KEEP / 继承所属要素组迁移|
|UI-0954|src/executive_health_ai/ui/charts/health.py:65 `render_compact_sparkline`|caption|'；'.join((s.comparison for s in series if s.points))|KEEP / 继承所属要素组迁移|
|UI-0955|src/executive_health_ai/ui/components/ai_citations.py:15 `_render_group`|caption|'本次没有使用成员事实。' if title == '事实依据' else '未找到可用知识依据。'|KEEP / 继承所属要素组迁移|
|UI-0956|src/executive_health_ai/ui/components/ai_citations.py:34 `_render_group`|caption|f'另有 {len(items) - 5} 条依据未展开。'|KEEP / 继承所属要素组迁移|
|UI-0957|src/executive_health_ai/ui/components/ai_citations.py:26 `_render_group`|caption|details|KEEP / 继承所属要素组迁移|
|UI-0958|src/executive_health_ai/ui/components/ai_citations.py:30 `_render_group`|warning|'该资料当前已归档或需要复核；这里保留的是回答生成时的引用记录。'|KEEP / 继承所属要素组迁移|
|UI-0959|src/executive_health_ai/ui/components/ai_citations.py:32 `_render_group`|link_button|'查看来源'|KEEP / 继承所属要素组迁移|
|UI-0960|src/executive_health_ai/ui/components/ai_citations.py:44 `render_ai_citations`|caption|f"依据状态：{status_labels.get(answer.grounded, '待确认')}"|KEEP / 继承所属要素组迁移|
|UI-0961|src/executive_health_ai/ui/components/ai_citations.py:45 `render_ai_citations`|expander|'查看依据'|KEEP / 继承所属要素组迁移|
|UI-0962|src/executive_health_ai/ui/components/ai_citations.py:49 `render_ai_citations`|caption|limitation|KEEP / 继承所属要素组迁移|
|UI-0963|src/executive_health_ai/ui/experience.py:102 `page_header`|title|title|KEEP / 继承所属要素组迁移|
|UI-0964|src/executive_health_ai/ui/experience.py:104 `page_header`|caption|description|KEEP / 继承所属要素组迁移|
|UI-0965|src/executive_health_ai/ui/experience.py:125 `empty_state`|caption|f'{title}。{action}'|KEEP / 继承所属要素组迁移|
|UI-0966|src/executive_health_ai/ui/experience.py:132 `metric_row`|metric|label|KEEP / 继承所属要素组迁移|
|UI-0967|src/executive_health_ai/ui/experience.py:140 `member_summary`|page_header|patient.display_name or '成员'|KEEP / 继承所属要素组迁移|
|UI-0968|src/executive_health_ai/ui/experience.py:141 `member_summary`|next_action|next_step|KEEP / 继承所属要素组迁移|
|UI-0969|src/executive_health_ai/ui/experience.py:194 `baseline_summary`|subheader|'年度健康基线'|KEEP / 继承所属要素组迁移|
|UI-0970|src/executive_health_ai/ui/experience.py:199 `baseline_summary`|caption|f'建立时间：{when(baseline.confirmed_at or baseline.assessed_at)} · 确认后冻结，后续变化单独记录'|KEEP / 继承所属要素组迁移|
|UI-0971|src/executive_health_ai/ui/experience.py:209 `baseline_summary`|caption|f"资料覆盖：已记录 {len(snapshot.get('key_metrics', []))} 项关键指标；缺失资料不推断为正常。"|KEEP / 继承所属要素组迁移|
|UI-0972|src/executive_health_ai/ui/experience.py:196 `baseline_summary`|empty_state|'尚未建立健康基线'|KEEP / 继承所属要素组迁移|
|UI-0973|src/executive_health_ai/ui/experience.py:208 `baseline_summary`|dataframe|pd.DataFrame(table)|KEEP / 继承所属要素组迁移|
|UI-0974|src/executive_health_ai/ui/experience.py:217 `evidence_summary`|caption|'来源：' + business_text(payload.get('source_name') or payload.get('data_source') or '待补充')|KEEP / 继承所属要素组迁移|
|UI-0975|src/executive_health_ai/ui/experience.py:221 `evidence_summary`|caption|'目前仅有整理信息。请先核对原报告，再作医学判断。'|KEEP / 继承所属要素组迁移|
|UI-0976|src/executive_health_ai/ui/pages/admin/experience.py:11 `integrations`|page_header|'集成与数据'|KEEP / 继承所属要素组迁移|
|UI-0977|src/executive_health_ai/ui/pages/admin/experience.py:23 `integrations`|button|'检查'|KEEP / 继承所属要素组迁移|
|UI-0978|src/executive_health_ai/ui/pages/admin/experience.py:22 `integrations`|work_item|title|KEEP / 继承所属要素组迁移|
|UI-0979|src/executive_health_ai/ui/pages/admin/experience.py:39 `workspace`|caption|'系统配置与运行保障'|KEEP / 继承所属要素组迁移|
|UI-0980|src/executive_health_ai/ui/pages/admin/experience.py:40 `workspace`|radio|'系统'|KEEP / 继承所属要素组迁移|
|UI-0981|src/executive_health_ai/ui/pages/admin/experience.py:44 `workspace`|page_header|'自动化运营'|KEEP / 继承所属要素组迁移|
|UI-0982|src/executive_health_ai/ui/pages/admin/experience.py:47 `workspace`|radio|'配置内容'|KEEP / 继承所属要素组迁移|
|UI-0983|src/executive_health_ai/ui/pages/admin/experience.py:50 `workspace`|page_header|'系统状态'|KEEP / 继承所属要素组迁移|
|UI-0984|src/executive_health_ai/ui/pages/admin/experience.py:59 `workspace`|info|'当前为演示角色预览；角色切换不等于登录或权限认证。'|KEEP / 继承所属要素组迁移|
|UI-0985|src/executive_health_ai/ui/pages/admin/experience.py:56 `workspace`|caption|'数据访问为本次页面查询结果；自动化异常请到自动化运营查看负责人和下一步。'|KEEP / 继承所属要素组迁移|
|UI-0986|src/executive_health_ai/ui/pages/admin/experience.py:60 `workspace`|expander|'操作记录'|KEEP / 继承所属要素组迁移|
|UI-0987|src/executive_health_ai/ui/pages/admin/experience.py:65 `workspace`|expander|'AI质量治理（高级）'|KEEP / 继承所属要素组迁移|
|UI-0988|src/executive_health_ai/ui/pages/admin/experience.py:58 `workspace`|error|'暂时无法访问数据，请由管理员检查本机服务。'|KEEP / 继承所属要素组迁移|
|UI-0989|src/executive_health_ai/ui/pages/admin/experience.py:63 `workspace`|selectbox|'选择成员'|KEEP / 继承所属要素组迁移|
|UI-0990|src/executive_health_ai/ui/pages/ai_improvement.py:26 `render_ai_improvement`|title|'AI 改进'|KEEP / 继承所属要素组迁移|
|UI-0991|src/executive_health_ai/ui/pages/ai_improvement.py:27 `render_ai_improvement`|caption|'人工反馈经审核和去标识化后，仅用于离线评测、Prompt 优化或后续模型训练；不会在线学习或修改风险规则。'|KEEP / 继承所属要素组迁移|
|UI-0992|src/executive_health_ai/ui/pages/ai_improvement.py:38 `render_ai_improvement`|metric|'反馈记录'|KEEP / 继承所属要素组迁移|
|UI-0993|src/executive_health_ai/ui/pages/ai_improvement.py:39 `render_ai_improvement`|metric|'待审核'|KEEP / 继承所属要素组迁移|
|UI-0994|src/executive_health_ai/ui/pages/ai_improvement.py:40 `render_ai_improvement`|metric|'离线数据集版本'|KEEP / 继承所属要素组迁移|
|UI-0995|src/executive_health_ai/ui/pages/ai_improvement.py:41 `render_ai_improvement`|metric|'候选 / 模型版本'|KEEP / 继承所属要素组迁移|
|UI-0996|src/executive_health_ai/ui/pages/ai_improvement.py:43 `render_ai_improvement`|subheader|'待审核与近期反馈'|KEEP / 继承所属要素组迁移|
|UI-0997|src/executive_health_ai/ui/pages/ai_improvement.py:55 `render_ai_improvement`|subheader|'离线数据集与版本门禁'|KEEP / 继承所属要素组迁移|
|UI-0998|src/executive_health_ai/ui/pages/ai_improvement.py:73 `render_ai_improvement`|info|'风险反馈只进入 Clinical Rule Review Queue；不会自动更新阈值、风险等级或 Clinical Rule。'|KEEP / 继承所属要素组迁移|
|UI-0999|src/executive_health_ai/ui/pages/ai_improvement.py:45 `render_ai_improvement`|dataframe|[{'类型': _FEEDBACK_LABELS.get(item.feedback_type, '人工反馈'), '功能': item.feature, '状态': _STATUS_LABELS.get(item.review_status, '待确认'), '是否可进入离线数据集': '是' if item.eligible_for_training a|KEEP / 继承所属要素组迁移|
|UI-1000|src/executive_health_ai/ui/pages/ai_improvement.py:53 `render_ai_improvement`|info|'暂无反馈记录。人工纠错不会自动触发训练。'|KEEP / 继承所属要素组迁移|
|UI-1001|src/executive_health_ai/ui/pages/ai_improvement.py:57 `render_ai_improvement`|dataframe|[{'数据集': item.dataset_id, '版本': f'v{item.dataset_version:03d}', '样本数': item.record_count, 'Schema': item.schema_version, '创建时间': item.created_at} for item in datasets]|KEEP / 继承所属要素组迁移|
|UI-1002|src/executive_health_ai/ui/pages/ai_improvement.py:63 `render_ai_improvement`|caption|'尚未生成经审核、去标识化的离线数据集快照。'|KEEP / 继承所属要素组迁移|
|UI-1003|src/executive_health_ai/ui/pages/ai_improvement.py:65 `render_ai_improvement`|dataframe|[{'Provider': item.provider, '版本': item.model_version, 'Prompt': item.prompt_version or '未记录', '状态': _STATUS_LABELS.get(item.status, '待确认')} for item in models]|KEEP / 继承所属要素组迁移|
|UI-1004|src/executive_health_ai/ui/pages/ai_improvement.py:71 `render_ai_improvement`|caption|'尚无候选模型版本。新版本必须通过固定评测和人工批准后才能启用。'|KEEP / 继承所属要素组迁移|
|UI-1005|src/executive_health_ai/ui/pages/baseline_visualization.py:42 `render_baseline_visualization`|caption|'这是本年度健康管理的参考起点，后续变化会与此进行比较。'|KEEP / 继承所属要素组迁移|
|UI-1006|src/executive_health_ai/ui/pages/baseline_visualization.py:44 `render_baseline_visualization`|caption|'首月 · 建立基线'|KEEP / 继承所属要素组迁移|
|UI-1007|src/executive_health_ai/ui/pages/baseline_visualization.py:46 `render_baseline_visualization`|caption|'下一步 · 阶段复盘'|KEEP / 继承所属要素组迁移|
|UI-1008|src/executive_health_ai/ui/pages/baseline_visualization.py:82 `render_baseline_visualization`|caption|'这是资料完整度，不代表健康评分。'|KEEP / 继承所属要素组迁移|
|UI-1009|src/executive_health_ai/ui/pages/baseline_visualization.py:83 `render_baseline_visualization`|altair_chart|coverage_chart(view.coverage)|KEEP / 继承所属要素组迁移|
|UI-1010|src/executive_health_ai/ui/pages/baseline_visualization.py:84 `render_baseline_visualization`|dataframe|pd.DataFrame([{'资料': item.label, '状态': item.status} for item in view.coverage])|KEEP / 继承所属要素组迁移|
|UI-1011|src/executive_health_ai/ui/pages/baseline_visualization.py:86 `render_baseline_visualization`|info|'该基线曾更新资料。当前图表使用最新有效的修订后基线。'|KEEP / 继承所属要素组迁移|
|UI-1012|src/executive_health_ai/ui/pages/baseline_visualization.py:67 `render_baseline_visualization`|caption|metric.explicit_status|KEEP / 继承所属要素组迁移|
|UI-1013|src/executive_health_ai/ui/pages/baseline_visualization.py:87 `render_baseline_visualization`|expander|'查看更新记录'|KEEP / 继承所属要素组迁移|
|UI-1014|src/executive_health_ai/ui/pages/baseline_visualization.py:70 `render_baseline_visualization`|altair_chart|chart|KEEP / 继承所属要素组迁移|
|UI-1015|src/executive_health_ai/ui/pages/baseline_visualization.py:71 `render_baseline_visualization`|caption|f"参考下限：{(metric.reference.lower if metric.reference.lower is not None else '未提供')} · 参考上限：{(metric.reference.upper if metric.reference.upper is not None else '未提供')} · 基线值：{metric.|KEEP / 继承所属要素组迁移|
|UI-1016|src/executive_health_ai/ui/pages/baseline_visualization.py:73 `render_baseline_visualization`|caption|'报告未提供可用于绘图的明确参考范围；仅显示已确认数值和来源。'|KEEP / 继承所属要素组迁移|
|UI-1017|src/executive_health_ai/ui/pages/baseline_visualization.py:90 `render_baseline_visualization`|caption|f'确认人：{amendment.confirmed_by}'|KEEP / 继承所属要素组迁移|
|UI-1018|src/executive_health_ai/ui/pages/baseline_visualization.py:93 `render_baseline_visualization`|caption|f'依据：{amendment.evidence}'|KEEP / 继承所属要素组迁移|
|UI-1019|src/executive_health_ai/ui/pages/baseline_visualization.py:110 `render_baseline_progress`|caption|'↑ / ↓ 只表示数值方向，不自动解释为改善或恶化；百分比指标的绝对差使用百分点。'|KEEP / 继承所属要素组迁移|
|UI-1020|src/executive_health_ai/ui/pages/baseline_visualization.py:127 `render_baseline_progress`|selectbox|'选择指标'|KEEP / 继承所属要素组迁移|
|UI-1021|src/executive_health_ai/ui/pages/baseline_visualization.py:128 `render_baseline_progress`|selectbox|'时间范围'|KEEP / 继承所属要素组迁移|
|UI-1022|src/executive_health_ai/ui/pages/baseline_visualization.py:107 `render_baseline_progress`|dataframe|pd.DataFrame(rows)|KEEP / 继承所属要素组迁移|
|UI-1023|src/executive_health_ai/ui/pages/baseline_visualization.py:109 `render_baseline_progress`|caption|'暂无可比较指标，已确认的定量数据会显示在这里。'|KEEP / 继承所属要素组迁移|
|UI-1024|src/executive_health_ai/ui/pages/baseline_visualization.py:124 `render_baseline_progress`|caption|'目前还没有足够的后续数据形成趋势。请由健康管理师核对并补充基线指标。'|KEEP / 继承所属要素组迁移|
|UI-1025|src/executive_health_ai/ui/pages/baseline_visualization.py:133 `render_baseline_progress`|caption|'保留年度基线作为起点；后续记录按所选时间范围展示。'|KEEP / 继承所属要素组迁移|
|UI-1026|src/executive_health_ai/ui/pages/baseline_visualization.py:136 `render_baseline_progress`|caption|'目前还没有足够的后续数据形成趋势。'|KEEP / 继承所属要素组迁移|
|UI-1027|src/executive_health_ai/ui/pages/baseline_visualization.py:137 `render_baseline_progress`|caption|'；'.join((f'{t.label} · 基线 {number_text(t.baseline_value)} {t.unit}' for t in selected))|KEEP / 继承所属要素组迁移|
|UI-1028|src/executive_health_ai/ui/pages/baseline_visualization.py:140 `render_baseline_progress`|altair_chart|chart|KEEP / 继承所属要素组迁移|
|UI-1029|src/executive_health_ai/ui/pages/baseline_visualization.py:141 `render_baseline_progress`|caption|'虚线 / 菱形：年度基线；末端圆点：当前有效记录。悬停查看日期、数值、单位和来源。'|KEEP / 继承所属要素组迁移|
|UI-1030|src/executive_health_ai/ui/pages/baseline_visualization.py:145 `render_baseline_overview`|subheader|f'{baseline.cycle_year or baseline.assessed_at.year}年度健康基线'|KEEP / 继承所属要素组迁移|
|UI-1031|src/executive_health_ai/ui/pages/baseline_visualization.py:152 `render_baseline_overview`|caption|f'已确认 · 建立时间：{confirmed:%Y/%m/%d} · 已记录 {len(view.metrics)} 项指标；缺失资料不推断为正常。'|KEEP / 继承所属要素组迁移|
|UI-1032|src/executive_health_ai/ui/pages/baseline_visualization.py:147 `render_baseline_overview`|caption|'基线尚待人工确认，确认后可比较当前变化。'|KEEP / 继承所属要素组迁移|
|UI-1033|src/executive_health_ai/ui/pages/doctor/experience.py:14 `detail`|subheader|'需要医生判断的问题'|KEEP / 继承所属要素组迁移|
|UI-1034|src/executive_health_ai/ui/pages/doctor/experience.py:16 `detail`|caption|f"{patient.display_name} · 提交于 {ux.when(review.created_at)} · {('已完成' if review.status != 'PENDING' else '待我复核')}"|KEEP / 继承所属要素组迁移|
|UI-1035|src/executive_health_ai/ui/pages/doctor/experience.py:63 `detail`|subheader|'医生结论与后续执行'|KEEP / 继承所属要素组迁移|
|UI-1036|src/executive_health_ai/ui/pages/doctor/experience.py:27 `detail`|caption|'关联关注事项：' + ux.business_text(problem.title)|KEEP / 继承所属要素组迁移|
|UI-1037|src/executive_health_ai/ui/pages/doctor/experience.py:28 `detail`|expander|'重要健康背景与年度基线'|KEEP / 继承所属要素组迁移|
|UI-1038|src/executive_health_ai/ui/pages/doctor/experience.py:39 `detail`|expander|'关键指标与当前用药'|KEEP / 继承所属要素组迁移|
|UI-1039|src/executive_health_ai/ui/pages/doctor/experience.py:44 `detail`|caption|'当前用药：' + ('；'.join((f"{r.drug_name} {r.dose or ''}{r.dose_unit or ''}" for r in meds if r.status.lower() == 'active')) or '暂无已确认记录')|KEEP / 继承所属要素组迁移|
|UI-1040|src/executive_health_ai/ui/pages/doctor/experience.py:48 `detail`|expander|'完整资料位置与核对信息'|KEEP / 继承所属要素组迁移|
|UI-1041|src/executive_health_ai/ui/pages/doctor/experience.py:50 `detail`|expander|'已采取行动'|KEEP / 继承所属要素组迁移|
|UI-1042|src/executive_health_ai/ui/pages/doctor/experience.py:56 `detail`|subheader|'医生结论'|KEEP / 继承所属要素组迁移|
|UI-1043|src/executive_health_ai/ui/pages/doctor/experience.py:58 `detail`|next_action|'健康管理师执行医生建议，并记录随访结果'|KEEP / 继承所属要素组迁移|
|UI-1044|src/executive_health_ai/ui/pages/doctor/experience.py:61 `detail`|next_action|'等待医生完成医学复核，之后由健康管理师跟进'|KEEP / 继承所属要素组迁移|
|UI-1045|src/executive_health_ai/ui/pages/doctor/experience.py:64 `detail`|form|f'ux-doctor-review-{review.id}'|KEEP / 继承所属要素组迁移|
|UI-1046|src/executive_health_ai/ui/pages/doctor/experience.py:65 `detail`|text_input|'医生姓名'|KEEP / 继承所属要素组迁移|
|UI-1047|src/executive_health_ai/ui/pages/doctor/experience.py:66 `detail`|text_input|'科室'|KEEP / 继承所属要素组迁移|
|UI-1048|src/executive_health_ai/ui/pages/doctor/experience.py:67 `detail`|text_area|'医生人工意见'|KEEP / 继承所属要素组迁移|
|UI-1049|src/executive_health_ai/ui/pages/doctor/experience.py:68 `detail`|text_area|'交给健康管理师的下一步'|KEEP / 继承所属要素组迁移|
|UI-1050|src/executive_health_ai/ui/pages/doctor/experience.py:69 `detail`|date_input|'建议跟进日期'|KEEP / 继承所属要素组迁移|
|UI-1051|src/executive_health_ai/ui/pages/doctor/experience.py:70 `detail`|caption|'执行负责人：健康管理师。提交后返回统一待办队列。'|KEEP / 继承所属要素组迁移|
|UI-1052|src/executive_health_ai/ui/pages/doctor/experience.py:71 `detail`|form_submit_button|'提交判断并交回健管'|KEEP / 继承所属要素组迁移|
|UI-1053|src/executive_health_ai/ui/pages/doctor/experience.py:33 `detail`|caption|'已有健康问题：' + ('；'.join(conditions) or '暂无已确认资料')|KEEP / 继承所属要素组迁移|
|UI-1054|src/executive_health_ai/ui/pages/doctor/experience.py:36 `detail`|caption|'手术 / 住院：' + ('；'.join(events) or '暂无已确认资料')|KEEP / 继承所属要素组迁移|
|UI-1055|src/executive_health_ai/ui/pages/doctor/experience.py:38 `detail`|caption|'尚无已确认年度基线；缺少记录不代表没有既往病史。'|KEEP / 继承所属要素组迁移|
|UI-1056|src/executive_health_ai/ui/pages/doctor/experience.py:54 `detail`|caption|'尚无已完成行动记录。'|KEEP / 继承所属要素组迁移|
|UI-1057|src/executive_health_ai/ui/pages/doctor/experience.py:80 `detail`|error|'请填写医生姓名、人工判断及后续执行说明，并确认本次复核仍待处理。'|KEEP / 继承所属要素组迁移|
|UI-1058|src/executive_health_ai/ui/pages/doctor/experience.py:85 `workspace`|page_header|'医学复核' if read_only else '待我复核'|KEEP / 继承所属要素组迁移|
|UI-1059|src/executive_health_ai/ui/pages/doctor/experience.py:95 `workspace`|caption|'复核记录未设置独立截止时间；按提交时间处理，紧急事项由健管人工联系。'|KEEP / 继承所属要素组迁移|
|UI-1060|src/executive_health_ai/ui/pages/doctor/experience.py:96 `workspace`|radio|'复核工作'|KEEP / 继承所属要素组迁移|
|UI-1061|src/executive_health_ai/ui/pages/doctor/experience.py:104 `workspace`|selectbox|'选择复核事项'|KEEP / 继承所属要素组迁移|
|UI-1062|src/executive_health_ai/ui/pages/doctor/experience.py:87 `workspace`|success|message|KEEP / 继承所属要素组迁移|
|UI-1063|src/executive_health_ai/ui/pages/doctor/experience.py:102 `workspace`|empty_state|'当前没有待复核事项' if mode == '待复核' else '暂无已完成复核'|KEEP / 继承所属要素组迁移|
|UI-1064|src/executive_health_ai/ui/pages/doctor/experience.py:113 `workspace`|next_action|'等待医生核对医学资料'|KEEP / 继承所属要素组迁移|
|UI-1065|src/executive_health_ai/ui/pages/health_visualization.py:20 `render_previews`|caption|'暂无足够数据形成趋势。'|KEEP / 继承所属要素组迁移|
|UI-1066|src/executive_health_ai/ui/pages/health_visualization.py:26 `render_previews`|caption|f'{group[0].points[0].at:%Y/%m/%d} — {group[0].points[-1].at:%Y/%m/%d} · 仅表示观察变化'|KEEP / 继承所属要素组迁移|
|UI-1067|src/executive_health_ai/ui/pages/health_visualization.py:27 `render_previews`|button|'查看趋势'|KEEP / 继承所属要素组迁移|
|UI-1068|src/executive_health_ai/ui/pages/health_visualization.py:43 `render_health_explorer`|selectbox|'选择健康指标'|KEEP / 继承所属要素组迁移|
|UI-1069|src/executive_health_ai/ui/pages/health_visualization.py:47 `render_health_explorer`|radio|'时间范围'|KEEP / 继承所属要素组迁移|
|UI-1070|src/executive_health_ai/ui/pages/health_visualization.py:60 `render_health_explorer`|caption|f'最后记录：{latest:%Y/%m/%d} · 历史数据可用不代表设备当前已连接'|KEEP / 继承所属要素组迁移|
|UI-1071|src/executive_health_ai/ui/pages/health_visualization.py:35 `render_health_explorer`|caption|'暂无已确认健康数据。上传报告或导入数据后可查看趋势。'|KEEP / 继承所属要素组迁移|
|UI-1072|src/executive_health_ai/ui/pages/health_visualization.py:66 `render_health_explorer`|expander|'数据来源与记录'|KEEP / 继承所属要素组迁移|
|UI-1073|src/executive_health_ai/ui/pages/health_visualization.py:68 `render_health_explorer`|dataframe|pd.DataFrame(records)|KEEP / 继承所属要素组迁移|
|UI-1074|src/executive_health_ai/ui/pages/health_visualization.py:53 `render_health_explorer`|info|f'时间轴选择的时间段：{start:%Y年%m月%d日} — {end:%Y年%m月%d日}'|KEEP / 继承所属要素组迁移|
|UI-1075|src/executive_health_ai/ui/pages/health_visualization.py:65 `render_health_explorer`|caption|item.label + ' · ' + item.comparison|KEEP / 继承所属要素组迁移|
|UI-1076|src/executive_health_ai/ui/pages/health_visualization.py:55 `render_health_explorer`|caption|'时间范围无效，请选择其他时间范围。'|KEEP / 继承所属要素组迁移|
|UI-1077|src/executive_health_ai/ui/pages/health_visualization.py:75 `render_report_trends`|subheader|'历次体检指标变化'|KEEP / 继承所属要素组迁移|
|UI-1078|src/executive_health_ai/ui/pages/health_visualization.py:79 `render_report_trends`|selectbox|'比较体检指标'|KEEP / 继承所属要素组迁移|
|UI-1079|src/executive_health_ai/ui/pages/health_visualization.py:83 `render_report_trends`|caption|'最近两次比较：' + recent.comparison + '；仅比较人工确认结果，不判断医学好坏。'|KEEP / 继承所属要素组迁移|
|UI-1080|src/executive_health_ai/ui/pages/health_visualization.py:77 `render_report_trends`|caption|'暂无已确认且包含检查日期的定量指标。'|KEEP / 继承所属要素组迁移|
|UI-1081|src/executive_health_ai/ui/pages/health_visualization.py:85 `render_report_trends`|caption|'横轴为实际体检日期；最后两点对应最近两次该指标的已确认检查。'|KEEP / 继承所属要素组迁移|
|UI-1082|src/executive_health_ai/ui/pages/health_visualization.py:98 `render_doctor_trend`|selectbox|'复核趋势范围'|KEEP / 继承所属要素组迁移|
|UI-1083|src/executive_health_ai/ui/pages/health_visualization.py:99 `render_doctor_trend`|caption|'按当前日期回看；所选范围没有记录时不会用旧记录冒充近期数据。'|KEEP / 继承所属要素组迁移|
|UI-1084|src/executive_health_ai/ui/pages/health_visualization.py:92 `render_doctor_trend`|caption|'本次问题暂无明确关联的可绘制指标，请先核对问题与依据。'|KEEP / 继承所属要素组迁移|
|UI-1085|src/executive_health_ai/ui/pages/health_visualization.py:96 `render_doctor_trend`|selectbox|'复核指标'|KEEP / 继承所属要素组迁移|
|UI-1086|src/executive_health_ai/ui/pages/manager/experience.py:20 `approvals`|expander|'需要您确认 · ' + ux.business_text(goal.title)|KEEP / 继承所属要素组迁移|
|UI-1087|src/executive_health_ai/ui/pages/manager/experience.py:21 `approvals`|next_action|goal.next_action or '确认后继续已有管理流程'|KEEP / 继承所属要素组迁移|
|UI-1088|src/executive_health_ai/ui/pages/manager/experience.py:22 `approvals`|caption|'确认后将执行当前等待的管理步骤；医学结论仍须医生人工复核。'|KEEP / 继承所属要素组迁移|
|UI-1089|src/executive_health_ai/ui/pages/manager/experience.py:23 `approvals`|radio|'处理决定'|KEEP / 继承所属要素组迁移|
|UI-1090|src/executive_health_ai/ui/pages/manager/experience.py:24 `approvals`|text_input|'确认说明'|KEEP / 继承所属要素组迁移|
|UI-1091|src/executive_health_ai/ui/pages/manager/experience.py:25 `approvals`|button|'确认处理'|KEEP / 继承所属要素组迁移|
|UI-1092|src/executive_health_ai/ui/pages/manager/experience.py:32 `approvals`|error|'此确认已更新或不属于当前角色，请刷新后重试。'|KEEP / 继承所属要素组迁移|
|UI-1093|src/executive_health_ai/ui/pages/manager/experience.py:37 `today`|page_header|'今日待处理'|KEEP / 继承所属要素组迁移|
|UI-1094|src/executive_health_ai/ui/pages/manager/experience.py:45 `today`|radio|'今日事项筛选'|KEEP / 继承所属要素组迁移|
|UI-1095|src/executive_health_ai/ui/pages/manager/experience.py:47 `today`|subheader|'优先处理'|KEEP / 继承所属要素组迁移|
|UI-1096|src/executive_health_ai/ui/pages/manager/experience.py:49 `today`|empty_state|'当前筛选下暂无事项'|KEEP / 继承所属要素组迁移|
|UI-1097|src/executive_health_ai/ui/pages/manager/experience.py:67 `today`|button|'处理'|KEEP / 继承所属要素组迁移|
|UI-1098|src/executive_health_ai/ui/pages/manager/experience.py:56 `today`|work_item|f'{app._member_display(member)} · {item.source_label}'|KEEP / 继承所属要素组迁移|
|UI-1099|src/executive_health_ai/ui/pages/manager/experience.py:59 `today`|caption|f'{item.status} · {ux.owner(item.owner)} · {ux.due_date(item.due_at)}'|KEEP / 继承所属要素组迁移|
|UI-1100|src/executive_health_ai/ui/pages/manager/experience.py:69 `today`|expander|f'其他 {len(visible) - 12} 项'|KEEP / 继承所属要素组迁移|
|UI-1101|src/executive_health_ai/ui/pages/manager/experience.py:76 `today`|expander|'自动跟进状态'|KEEP / 继承所属要素组迁移|
|UI-1102|src/executive_health_ai/ui/pages/manager/experience.py:71 `today`|work_item|app._member_display(patients.get(item.member_id))|KEEP / 继承所属要素组迁移|
|UI-1103|src/executive_health_ai/ui/pages/manager/experience.py:72 `today`|button|'处理'|KEEP / 继承所属要素组迁移|
|UI-1104|src/executive_health_ai/ui/pages/manager/experience.py:78 `today`|work_item|goal.title|KEEP / 继承所属要素组迁移|
|UI-1105|src/executive_health_ai/ui/pages/manager/experience.py:79 `today`|button|'处理确认'|KEEP / 继承所属要素组迁移|
|UI-1106|src/executive_health_ai/ui/pages/manager/experience.py:96 `management`|radio|'管理操作'|KEEP / 继承所属要素组迁移|
|UI-1107|src/executive_health_ai/ui/pages/manager/experience.py:86 `management`|success|message|KEEP / 继承所属要素组迁移|
|UI-1108|src/executive_health_ai/ui/pages/manager/experience.py:91 `management`|selectbox|'当前管理计划'|KEEP / 继承所属要素组迁移|
|UI-1109|src/executive_health_ai/ui/pages/manager/experience.py:94 `management`|next_action|program.main_goal|KEEP / 继承所属要素组迁移|
|UI-1110|src/executive_health_ai/ui/pages/manager/experience.py:95 `management`|caption|f'{app._label(program.status)} · {ux.when(program.start_date)} — {ux.when(program.end_date)}'|KEEP / 继承所属要素组迁移|
|UI-1111|src/executive_health_ai/ui/pages/manager/experience.py:98 `management`|checkbox|'建立新计划'|KEEP / 继承所属要素组迁移|
|UI-1112|src/executive_health_ai/ui/pages/manager/experience.py:99 `management`|form|f'ux-plan-form-{patient.id}'|KEEP / 继承所属要素组迁移|
|UI-1113|src/executive_health_ai/ui/pages/manager/experience.py:100 `management`|text_input|'计划名称'|KEEP / 继承所属要素组迁移|
|UI-1114|src/executive_health_ai/ui/pages/manager/experience.py:101 `management`|text_area|'本阶段目标'|KEEP / 继承所属要素组迁移|
|UI-1115|src/executive_health_ai/ui/pages/manager/experience.py:102 `management`|text_input|'负责人'|KEEP / 继承所属要素组迁移|
|UI-1116|src/executive_health_ai/ui/pages/manager/experience.py:103 `management`|selectbox|'计划周期'|KEEP / 继承所属要素组迁移|
|UI-1117|src/executive_health_ai/ui/pages/manager/experience.py:104 `management`|date_input|'开始日期'|KEEP / 继承所属要素组迁移|
|UI-1118|src/executive_health_ai/ui/pages/manager/experience.py:105 `management`|date_input|'结束日期'|KEEP / 继承所属要素组迁移|
|UI-1119|src/executive_health_ai/ui/pages/manager/experience.py:106 `management`|text_area|'建立依据 / 调整原因'|KEEP / 继承所属要素组迁移|
|UI-1120|src/executive_health_ai/ui/pages/manager/experience.py:107 `management`|selectbox|'首次人工评估层级（已有评估时沿用）'|KEEP / 继承所属要素组迁移|
|UI-1121|src/executive_health_ai/ui/pages/manager/experience.py:108 `management`|form_submit_button|'保存健康计划'|KEEP / 继承所属要素组迁移|
|UI-1122|src/executive_health_ai/ui/pages/manager/experience.py:121 `management`|info|'先建立当前计划，再安排有归属的随访任务。'|KEEP / 继承所属要素组迁移|
|UI-1123|src/executive_health_ai/ui/pages/manager/experience.py:123 `management`|form|f'ux-followup-{patient.id}'|KEEP / 继承所属要素组迁移|
|UI-1124|src/executive_health_ai/ui/pages/manager/experience.py:124 `management`|text_input|'随访 / 行动名称'|KEEP / 继承所属要素组迁移|
|UI-1125|src/executive_health_ai/ui/pages/manager/experience.py:125 `management`|text_area|'需要完成什么'|KEEP / 继承所属要素组迁移|
|UI-1126|src/executive_health_ai/ui/pages/manager/experience.py:126 `management`|text_input|'执行负责人'|KEEP / 继承所属要素组迁移|
|UI-1127|src/executive_health_ai/ui/pages/manager/experience.py:127 `management`|radio|'由谁执行'|KEEP / 继承所属要素组迁移|
|UI-1128|src/executive_health_ai/ui/pages/manager/experience.py:128 `management`|date_input|'截止日期'|KEEP / 继承所属要素组迁移|
|UI-1129|src/executive_health_ai/ui/pages/manager/experience.py:129 `management`|form_submit_button|'安排随访'|KEEP / 继承所属要素组迁移|
|UI-1130|src/executive_health_ai/ui/pages/manager/experience.py:142 `management`|caption|'记录观察变化；不将前后差异解释为干预造成的结果。'|KEEP / 继承所属要素组迁移|
|UI-1131|src/executive_health_ai/ui/pages/manager/experience.py:118 `management`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-1132|src/executive_health_ai/ui/pages/manager/experience.py:135 `management`|success|'随访已安排，已进入成员计划与健管工作队列。'|KEEP / 继承所属要素组迁移|
|UI-1133|src/executive_health_ai/ui/pages/manager/experience.py:140 `management`|info|'请先建立当前计划。'|KEEP / 继承所属要素组迁移|
|UI-1134|src/executive_health_ai/ui/pages/manager/experience.py:143 `management`|form|f'ux-outcome-{patient.id}'|KEEP / 继承所属要素组迁移|
|UI-1135|src/executive_health_ai/ui/pages/manager/experience.py:144 `management`|selectbox|'观察指标'|KEEP / 继承所属要素组迁移|
|UI-1136|src/executive_health_ai/ui/pages/manager/experience.py:145 `management`|text_input|'起点数值'|KEEP / 继承所属要素组迁移|
|UI-1137|src/executive_health_ai/ui/pages/manager/experience.py:146 `management`|text_input|'本次数值'|KEEP / 继承所属要素组迁移|
|UI-1138|src/executive_health_ai/ui/pages/manager/experience.py:147 `management`|text_input|'单位'|KEEP / 继承所属要素组迁移|
|UI-1139|src/executive_health_ai/ui/pages/manager/experience.py:148 `management`|text_area|'结果依据'|KEEP / 继承所属要素组迁移|
|UI-1140|src/executive_health_ai/ui/pages/manager/experience.py:149 `management`|text_input|'记录人'|KEEP / 继承所属要素组迁移|
|UI-1141|src/executive_health_ai/ui/pages/manager/experience.py:150 `management`|selectbox|'观察结果'|KEEP / 继承所属要素组迁移|
|UI-1142|src/executive_health_ai/ui/pages/manager/experience.py:151 `management`|selectbox|'下一步管理'|KEEP / 继承所属要素组迁移|
|UI-1143|src/executive_health_ai/ui/pages/manager/experience.py:152 `management`|text_area|'下一步说明'|KEEP / 继承所属要素组迁移|
|UI-1144|src/executive_health_ai/ui/pages/manager/experience.py:153 `management`|form_submit_button|'记录阶段结果并安排下一步'|KEEP / 继承所属要素组迁移|
|UI-1145|src/executive_health_ai/ui/pages/manager/experience.py:166 `management`|expander|'计划详情与已记录阶段结果'|KEEP / 继承所属要素组迁移|
|UI-1146|src/executive_health_ai/ui/pages/manager/experience.py:168 `management`|expander|'自动跟进与健康管理记录'|KEEP / 继承所属要素组迁移|
|UI-1147|src/executive_health_ai/ui/pages/manager/experience.py:137 `management`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-1148|src/executive_health_ai/ui/pages/manager/experience.py:160 `management`|success|'阶段结果已回写到计划与历程，后续行动已建立。'|KEEP / 继承所属要素组迁移|
|UI-1149|src/executive_health_ai/ui/pages/manager/experience.py:162 `management`|error|str(error)|KEEP / 继承所属要素组迁移|
|UI-1150|src/executive_health_ai/ui/pages/manager/experience.py:175 `member_detail`|button|'← 返回成员列表'|KEEP / 继承所属要素组迁移|
|UI-1151|src/executive_health_ai/ui/pages/manager/experience.py:186 `member_detail`|caption|f"医生待复核：{len(pending)} · 资料更新：{(ux.when(rows[-1].observed_at) if rows else '暂无健康数据')}"|KEEP / 继承所属要素组迁移|
|UI-1152|src/executive_health_ai/ui/pages/manager/experience.py:187 `member_detail`|radio|'成员页面'|KEEP / 继承所属要素组迁移|
|UI-1153|src/executive_health_ai/ui/pages/manager/experience.py:194 `member_detail`|subheader|'当前管理'|KEEP / 继承所属要素组迁移|
|UI-1154|src/executive_health_ai/ui/pages/manager/experience.py:196 `member_detail`|caption|'主要关注：' + ('；'.join((ux.business_text(p.title) for p in problems[:3])) or '暂无已确认关注事项')|KEEP / 继承所属要素组迁移|
|UI-1155|src/executive_health_ai/ui/pages/manager/experience.py:212 `member_detail`|button|label|KEEP / 继承所属要素组迁移|
|UI-1156|src/executive_health_ai/ui/pages/manager/experience.py:213 `member_detail`|expander|'处理开放中的健康关注事项'|KEEP / 继承所属要素组迁移|
|UI-1157|src/executive_health_ai/ui/pages/manager/experience.py:215 `member_detail`|expander|'近期服务'|KEEP / 继承所属要素组迁移|
|UI-1158|src/executive_health_ai/ui/pages/manager/experience.py:203 `member_detail`|caption|ux.owner(request.assigned_manager)|KEEP / 继承所属要素组迁移|
|UI-1159|src/executive_health_ai/ui/pages/manager/experience.py:205 `member_detail`|caption|'暂无服务安排；可从服务工作台安排。'|KEEP / 继承所属要素组迁移|
|UI-1160|src/executive_health_ai/ui/pages/member/experience.py:38 `_complete`|error|'此任务需要健康管理师核实，请联系负责人。'|KEEP / 继承所属要素组迁移|
|UI-1161|src/executive_health_ai/ui/pages/member/experience.py:43 `home`|page_header|'今日健康'|KEEP / 继承所属要素组迁移|
|UI-1162|src/executive_health_ai/ui/pages/member/experience.py:48 `home`|subheader|'今天最重要的事情'|KEEP / 继承所属要素组迁移|
|UI-1163|src/executive_health_ai/ui/pages/member/experience.py:63 `home`|subheader|f'{datetime.now(ux.LOCAL).year}年度健康管理'|KEEP / 继承所属要素组迁移|
|UI-1164|src/executive_health_ai/ui/pages/member/experience.py:77 `home`|subheader|'近期变化'|KEEP / 继承所属要素组迁移|
|UI-1165|src/executive_health_ai/ui/pages/member/experience.py:81 `home`|button|'查看健康计划'|KEEP / 继承所属要素组迁移|
|UI-1166|src/executive_health_ai/ui/pages/member/experience.py:83 `home`|button|'查看健康数据'|KEEP / 继承所属要素组迁移|
|UI-1167|src/executive_health_ai/ui/pages/member/experience.py:85 `home`|button|'上传体检报告'|KEEP / 继承所属要素组迁移|
|UI-1168|src/executive_health_ai/ui/pages/member/experience.py:45 `home`|success|message|KEEP / 继承所属要素组迁移|
|UI-1169|src/executive_health_ai/ui/pages/member/experience.py:58 `home`|empty_state|'今天没有待完成任务'|KEEP / 继承所属要素组迁移|
|UI-1170|src/executive_health_ai/ui/pages/member/experience.py:66 `home`|caption|f'{ux.owner(program.owner)} · 当前阶段：{app.display_program_phase(program.current_phase)}'|KEEP / 继承所属要素组迁移|
|UI-1171|src/executive_health_ai/ui/pages/member/experience.py:67 `home`|next_action|tasks[0].title if tasks else '等待健康管理师更新下次复盘安排'|KEEP / 继承所属要素组迁移|
|UI-1172|src/executive_health_ai/ui/pages/member/experience.py:69 `home`|next_action|'上传最近体检报告，建立年度健康基线'|KEEP / 继承所属要素组迁移|
|UI-1173|src/executive_health_ai/ui/pages/member/experience.py:73 `home`|caption|'持续管理状态：' + ux.business_text(goal.current_stage) + ' · ' + ux.business_text(goal.next_action or '负责人将更新下一步')|KEEP / 继承所属要素组迁移|
|UI-1174|src/executive_health_ai/ui/pages/member/experience.py:76 `home`|caption|f'下次服务：{ux.when(upcoming.scheduled_at)} · {ux.owner(upcoming.assigned_manager)}'|KEEP / 继承所属要素组迁移|
|UI-1175|src/executive_health_ai/ui/pages/member/experience.py:54 `home`|button|'去完成'|KEEP / 继承所属要素组迁移|
|UI-1176|src/executive_health_ai/ui/pages/member/experience.py:53 `home`|work_item|task.title|KEEP / 继承所属要素组迁移|
|UI-1177|src/executive_health_ai/ui/pages/member/experience.py:109 `overview`|subheader|'持续关注事项'|KEEP / 继承所属要素组迁移|
|UI-1178|src/executive_health_ai/ui/pages/member/experience.py:91 `overview`|button|'返回健康概览'|KEEP / 继承所属要素组迁移|
|UI-1179|src/executive_health_ai/ui/pages/member/experience.py:103 `overview`|button|'查看年度健康基线'|KEEP / 继承所属要素组迁移|
|UI-1180|src/executive_health_ai/ui/pages/member/experience.py:105 `overview`|subheader|'当前健康变化'|KEEP / 继承所属要素组迁移|
|UI-1181|src/executive_health_ai/ui/pages/member/experience.py:108 `overview`|caption|'当前健康变化已呈现在上方基线趋势中；其他指标可进入健康数据查看。'|KEEP / 继承所属要素组迁移|
|UI-1182|src/executive_health_ai/ui/pages/member/experience.py:112 `overview`|work_item|problem.title|KEEP / 继承所属要素组迁移|
|UI-1183|src/executive_health_ai/ui/pages/member/experience.py:114 `overview`|caption|'暂无已确认的持续关注事项。'|KEEP / 继承所属要素组迁移|
|UI-1184|src/executive_health_ai/ui/pages/member/experience.py:115 `overview`|expander|'重要健康背景'|KEEP / 继承所属要素组迁移|
|UI-1185|src/executive_health_ai/ui/pages/member/experience.py:116 `overview`|caption|'用药、重大病史和手术住院记录统一保存在医疗档案。'|KEEP / 继承所属要素组迁移|
|UI-1186|src/executive_health_ai/ui/pages/member/experience.py:121 `health_data`|page_header|'健康数据'|KEEP / 继承所属要素组迁移|
|UI-1187|src/executive_health_ai/ui/pages/member/experience.py:126 `plan`|page_header|'接下来我要做什么'|KEEP / 继承所属要素组迁移|
|UI-1188|src/executive_health_ai/ui/pages/member/experience.py:146 `plan`|radio|'任务分类'|KEEP / 继承所属要素组迁移|
|UI-1189|src/executive_health_ai/ui/pages/member/experience.py:163 `plan`|subheader|'近期节点'|KEEP / 继承所属要素组迁移|
|UI-1190|src/executive_health_ai/ui/pages/member/experience.py:165 `plan`|caption|' · '.join((f'{ux.when(t.due_at)} {ux.business_text(t.title)}' for t in future[:3])) or '暂无新的未来节点；逾期事项请联系负责人重新安排。'|KEEP / 继承所属要素组迁移|
|UI-1191|src/executive_health_ai/ui/pages/member/experience.py:166 `plan`|subheader|'阶段结果'|KEEP / 继承所属要素组迁移|
|UI-1192|src/executive_health_ai/ui/pages/member/experience.py:167 `plan`|caption|'仅记录观察到的前后变化，不将变化归因于某项干预。'|KEEP / 继承所属要素组迁移|
|UI-1193|src/executive_health_ai/ui/pages/member/experience.py:130 `plan`|subheader|ux.business_text(program.title)|KEEP / 继承所属要素组迁移|
|UI-1194|src/executive_health_ai/ui/pages/member/experience.py:132 `plan`|caption|f'{ux.owner(program.owner)} · {ux.when(program.start_date)} — {ux.when(program.end_date)} · {app._label(program.status)}'|KEEP / 继承所属要素组迁移|
|UI-1195|src/executive_health_ai/ui/pages/member/experience.py:145 `plan`|empty_state|'暂无当前计划'|KEEP / 继承所属要素组迁移|
|UI-1196|src/executive_health_ai/ui/pages/member/experience.py:152 `plan`|work_item|task.title|KEEP / 继承所属要素组迁移|
|UI-1197|src/executive_health_ai/ui/pages/member/experience.py:156 `plan`|caption|'此分类暂无任务。新的安排会由负责人更新。'|KEEP / 继承所属要素组迁移|
|UI-1198|src/executive_health_ai/ui/pages/member/experience.py:171 `plan`|work_item|ux.metric_name(outcome.metric)|KEEP / 继承所属要素组迁移|
|UI-1199|src/executive_health_ai/ui/pages/member/experience.py:173 `plan`|caption|'阶段复盘后，确认的结果会显示在这里。'|KEEP / 继承所属要素组迁移|
|UI-1200|src/executive_health_ai/ui/pages/member/experience.py:136 `plan`|progress|done / len(related)|KEEP / 继承所属要素组迁移|
|UI-1201|src/executive_health_ai/ui/pages/member/experience.py:137 `plan`|expander|'接受或调整当前方案'|KEEP / 继承所属要素组迁移|
|UI-1202|src/executive_health_ai/ui/pages/member/experience.py:138 `plan`|radio|'我的选择'|KEEP / 继承所属要素组迁移|
|UI-1203|src/executive_health_ai/ui/pages/member/experience.py:139 `plan`|button|'记录选择'|KEEP / 继承所属要素组迁移|
|UI-1204|src/executive_health_ai/ui/pages/member/experience.py:153 `plan`|button|'确认完成'|KEEP / 继承所属要素组迁移|
|UI-1205|src/executive_health_ai/ui/pages/member/experience.py:158 `plan`|expander|f'其他 {len(visible) - 5} 项行动'|KEEP / 继承所属要素组迁移|
|UI-1206|src/executive_health_ai/ui/pages/member/experience.py:143 `plan`|success|'已记录，健康管理师将跟进您的选择。'|KEEP / 继承所属要素组迁移|
|UI-1207|src/executive_health_ai/ui/pages/member/experience.py:160 `plan`|work_item|task.title|KEEP / 继承所属要素组迁移|
|UI-1208|src/executive_health_ai/ui/pages/member/experience.py:161 `plan`|button|'确认完成'|KEEP / 继承所属要素组迁移|
|UI-1209|src/executive_health_ai/ui/pages/member/experience.py:182 `timeline`|error|'健康历程暂时无法加载，请稍后重试。'|KEEP / 继承所属要素组迁移|
|UI-1210|src/executive_health_ai/ui/pages/member/experience.py:186 `_timeline_content`|page_header|'长期健康历程'|KEEP / 继承所属要素组迁移|
|UI-1211|src/executive_health_ai/ui/pages/member/experience.py:207 `_timeline_content`|work_item|title|KEEP / 继承所属要素组迁移|
|UI-1212|src/executive_health_ai/ui/pages/member/experience.py:209 `_timeline_content`|empty_state|'暂无重要健康事件'|KEEP / 继承所属要素组迁移|
|UI-1213|src/executive_health_ai/ui/pages/member/experience.py:210 `_timeline_content`|expander|'查看完整历程与依据'|KEEP / 继承所属要素组迁移|
|UI-1214|src/executive_health_ai/ui/pages/shell.py:29 `render_portfolio_landing`|caption|'演示数据已匿名化；风险展示仅用于工作流演示，医学判断仍由人工负责。'|KEEP / 继承所属要素组迁移|
|UI-1215|src/executive_health_ai/ui/pages/shell.py:22 `render_portfolio_landing`|button|'进入成员健康中心'|KEEP / 继承所属要素组迁移|
|UI-1216|src/executive_health_ai/ui/pages/shell.py:26 `render_portfolio_landing`|button|'进入 HealthOps 运营后台'|KEEP / 继承所属要素组迁移|
|UI-1217|src/executive_health_ai/ui/pages/shell.py:44 `render_more_workspace_shell`|page_header|'更多'|KEEP / 继承所属要素组迁移|
|UI-1218|src/executive_health_ai/ui/pages/shell.py:68 `render_more_workspace_shell`|button|'← 返回更多'|KEEP / 继承所属要素组迁移|
|UI-1219|src/executive_health_ai/ui/pages/shell.py:50 `render_more_workspace_shell`|subheader|'管理工具'|KEEP / 继承所属要素组迁移|
|UI-1220|src/executive_health_ai/ui/pages/shell.py:51 `render_more_workspace_shell`|caption|'选择一个工具后才加载对应内容。'|KEEP / 继承所属要素组迁移|
|UI-1221|src/executive_health_ai/ui/pages/shell.py:74 `render_more_workspace_shell`|subheader|'操作记录'|KEEP / 继承所属要素组迁移|
|UI-1222|src/executive_health_ai/ui/pages/shell.py:76 `render_more_workspace_shell`|selectbox|'选择成员'|KEEP / 继承所属要素组迁移|
|UI-1223|src/executive_health_ai/ui/pages/shell.py:80 `render_more_workspace_shell`|expander|'AI 质量治理（高级）'|KEEP / 继承所属要素组迁移|
|UI-1224|src/executive_health_ai/ui/pages/shell.py:63 `render_more_workspace_shell`|caption|description|KEEP / 继承所属要素组迁移|
|UI-1225|src/executive_health_ai/ui/pages/shell.py:64 `render_more_workspace_shell`|button|'查看'|KEEP / 继承所属要素组迁移|


## Product Logic V3 后续整理

本表保留UX V2的94组历史口径。本轮以 `3ba46b2` 冻结当前全部102组业务要素及1390个底层UI调用点，见 [Product Logic Preservation Map](PRODUCT_LOGIC_PRESERVATION_MAP.md)。新的归属与位置以该表为准；V2能力与高级兼容入口全部保留。


## 本轮真实健管工作流迁移

原121元素的最新入口见 [完整保留结果](REAL_WORKFLOW_ELEMENT_PRESERVATION.md)。健管“更多”的原支撑能力移至管理员高级信息的原平台工具目录；旧深链接仍兼容。管理页原功能归入“原有计划 / 任务 / 自动跟进”，没有删除。

# 产品信息架构

## 角色与导航

| 角色 | 一级导航 | 二级内容 | 核心动作 |
|---|---|---|---|
| 成员 | 首页、健康、历程、计划、服务 | 健康：概览/数据/体检/医疗档案；计划：待完成/等待他人/已完成；服务：可用/当前/历史 | 今天行动 → 确认完成；查看基线与变化；反馈计划；申请服务 |
| 健康管理师 | 今日、成员、医疗协同、服务、更多 | 成员360：概览/健康/管理/医疗/历程；其余为工作类型筛选、选中详情 | 接手事项；核对报告；建立/调整计划；安排随访；记录阶段结果 |
| 医生 | 待我复核 | 待复核/已完成，选中详情 | 核对问题、上下文、依据；提交人工判断；交回健管 |
| 管理员 | 集成与数据、自动化运营、规则与知识、系统状态 | 集成类型；规则/知识/设备；诊断折叠区 | 检查导入、连接测试；人工接手运行；查看操作记录 |

角色选择为演示预览，不是身份认证。个人设置移至成员页面右上方。一级最大5项；业务路由最大2层。详情内部的指标、时间范围、表单与折叠区是渐进披露，不形成新业务路由。

## 入口处理

| 原入口或信息 | 处理 | 新位置 / 理由 |
|---|---|---|
| 成员首页风险、数据摘要、多组快捷卡 | MERGE | 今日行动、管理状态、少量变化 |
| 年度基线 | MOVE | 健康概览第一部分；依据在详情 |
| 首页报告、用药和生活方式详情 | MOVE | 健康 → 体检 / 医疗档案 / 数据 |
| 成员个人设置 | MOVE | 右上方设置 |
| 活动/睡眠/监测的重复数据状态 | MERGE | 同一有效观测投影，按指标和时间范围选择 |
| 计划说明、任务、结果分散入口 | MERGE | 同页从目标到执行与阶段结果 |
| 健管成员详情重复汇总卡 | MERGE | 成员360：基线、开放事项、计划与下一行动 |
| 计划建立、随访、结果录入 | KEEP / 补齐入口 | 成员360 → 管理；已有业务能力的操作表单 |
| 医生复核 legacy 与风险待办列表 | MERGE | 统一待复核投影；已完成单独筛选 |
| 自动化审批只显示计数 | MOVE | 成员360管理 / 医生上下文中的确认动作 |
| Agent 技术步骤与内部状态 | HIDE | 管理员高级信息；普通视图只显示业务阶段 |
| 风险规则、集成、治理 | MOVE | 管理员；健管更多保留系统入口 |
| UUID、内部指标代码、技术类名 | HIDE | 不作为普通页面标签或叙述 |
| 过期预约作为下一次服务 | REMOVE | 历史保留，当前服务提示核实或重约 |
| 旧全量时间轴 | KEEP | 默认重要事件；完整历程与依据折叠展开 |
| 原有后端能力与事实表 | KEEP | 未删除，未创建migration |

## 关键路径与点击预算

- 成员：首页“去完成” → 计划“确认完成”（2次）；计划与健康切换各1次。
- 健管：今日“处理” → 成员360“管理” → 选择建立/调整计划、随访或结果（3次进入操作）；录入后提交。
- 医生：角色进入 → 选中复核事项 → 提交人工判断；表单录入不算导航。
- 管理员：系统 → 集成与数据 → 检查相应连接；表单测试保留同页。

## 改版前盘点

来源：本地备份分支 `backup/pre-platform-ux-redesign` 的实际代码。原主入口为运营后台 / 成员健康中心；管理员嵌在更多，医生嵌在医疗协同。

- radio：28处调用。
- tabs：0处调用。
- button：74处调用。
- expander：61处调用。
- selectbox：35处调用。
- form_submit_button：30处调用。

按钮的动态实例数取决于数据；上述为调用位置数，不能当作用户一次看到的按钮数。原二级入口及处理结果见上表。

## 全部现存 UI 控件盘点

当前代码的控件调用位置如下，动态选择属于同页详情，不新增业务路由。

| 文件 | 行 | 控件 | 标签表达式 |
|---|---:|---|---|
| streamlit_app.py | 341 | selectbox | `'查看目标'` |
| streamlit_app.py | 345 | button | `'人工接手'` |
| streamlit_app.py | 350 | button | `'恢复自动跟进'` |
| streamlit_app.py | 355 | button | `'取消目标'` |
| streamlit_app.py | 362 | expander | `'高级信息'` |
| streamlit_app.py | 388 | radio | `'工作区'` |
| streamlit_app.py | 397 | radio | `'当前视图'` |
| streamlit_app.py | 407 | radio | `'成员健康中心导航'` |
| streamlit_app.py | 504 | button | `label` |
| streamlit_app.py | 508 | button | `label` |
| streamlit_app.py | 768 | expander | `'逐项查看依据'` |
| streamlit_app.py | 791 | expander | `'查看该指标依据'` |
| streamlit_app.py | 950 | expander | `'高级信息'` |
| streamlit_app.py | 960 | button | `'查看依据'` |
| streamlit_app.py | 984 | expander | `'相关医学参考'` |
| streamlit_app.py | 1190 | button | `'记录已开始紧急处置'` |
| streamlit_app.py | 1202 | form_submit_button | `'记录结果并关闭风险事项'` |
| streamlit_app.py | 1225 | radio | `'处理方式'` |
| streamlit_app.py | 1231 | form_submit_button | `'保存并创建复核任务'` |
| streamlit_app.py | 1233 | selectbox | `'联系方式'` |
| streamlit_app.py | 1234 | selectbox | `'联系结果'` |
| streamlit_app.py | 1237 | form_submit_button | `'保存人工联系记录'` |
| streamlit_app.py | 1240 | form_submit_button | `'记录数据问题并关闭事件'` |
| streamlit_app.py | 1245 | form_submit_button | `'创建健康管理任务'` |
| streamlit_app.py | 1248 | selectbox | `'建议科室'` |
| streamlit_app.py | 1249 | form_submit_button | `'提交医生复核'` |
| streamlit_app.py | 1272 | form_submit_button | `'完成本次跟进'` |
| streamlit_app.py | 1288 | form_submit_button | `'完成跟进后关闭事件'` |
| streamlit_app.py | 1591 | button | `'处理'` |
| streamlit_app.py | 1659 | expander | `'记录随访并关闭健康问题'` |
| streamlit_app.py | 1664 | selectbox | `'关联执行任务'` |
| streamlit_app.py | 1665 | form_submit_button | `'保存随访并关闭'` |
| streamlit_app.py | 1689 | expander | `'创建执行任务'` |
| streamlit_app.py | 1693 | selectbox | `'优先级'` |
| streamlit_app.py | 1696 | form_submit_button | `'创建任务'` |
| streamlit_app.py | 1726 | radio | `'核实结果'` |
| streamlit_app.py | 1728 | selectbox | `'健康问题处理'` |
| streamlit_app.py | 1729 | form_submit_button | `'保存人工核实'` |
| streamlit_app.py | 1771 | button | `'标记完成'` |
| streamlit_app.py | 1852 | form_submit_button | `'完成医学资料复核'` |
| streamlit_app.py | 1862 | expander | `f'{confirmed_baseline.cycle_year or confirmed_baseline.assessed_at.year}年度健康基线医学摘要'` |
| streamlit_app.py | 1911 | form_submit_button | `'保存医生复核并创建跟进任务'` |
| streamlit_app.py | 1938 | form_submit_button | `'保存医生复核并创建跟进任务'` |
| streamlit_app.py | 1972 | selectbox | `'科室'` |
| streamlit_app.py | 1976 | form_submit_button | `'确认医生复核并创建管理方案与任务'` |
| streamlit_app.py | 1993 | expander | `'查看整理摘要与相关数据'` |
| streamlit_app.py | 2014 | expander | `f'{_fmt_dt(review.reviewed_at)} · {review.department} · {review.doctor_name}'` |
| streamlit_app.py | 2019 | expander | `'查看当时整理摘要'` |
| streamlit_app.py | 2054 | expander | `'查看详细记录'` |
| streamlit_app.py | 2174 | button | `'查看血糖详情'` |
| streamlit_app.py | 2193 | radio | `'动态血糖时间'` |
| streamlit_app.py | 2247 | button | `'查看步数趋势'` |
| streamlit_app.py | 2259 | button | `'查看睡眠详情'` |
| streamlit_app.py | 2348 | radio | `'睡眠趋势时间'` |
| streamlit_app.py | 2373 | radio | `'长期趋势时间'` |
| streamlit_app.py | 2397 | expander | `'查看详细趋势'` |
| streamlit_app.py | 2420 | button | `'返回默认'` |
| streamlit_app.py | 2510 | expander | `'查看全部健康数据'` |
| streamlit_app.py | 2512 | expander | `'查看监测详情'` |
| streamlit_app.py | 2648 | expander | `'确认阶段结果后的下一步'` |
| streamlit_app.py | 2649 | radio | `'后续管理决定'` |
| streamlit_app.py | 2684 | button | `'创建任务'` |
| streamlit_app.py | 2820 | button | `'处理'` |
| streamlit_app.py | 2826 | button | `'上传体检报告'` |
| streamlit_app.py | 2891 | button | `'查看成员'` |
| streamlit_app.py | 3084 | button | `'批准并允许 AI 引用'` |
| streamlit_app.py | 3093 | button | `'退回资料'` |
| streamlit_app.py | 3103 | expander | `'版本与归档'` |
| streamlit_app.py | 3118 | form_submit_button | `'保存为待审核新版本'` |
| streamlit_app.py | 3146 | expander | `'高级信息'` |
| streamlit_app.py | 3158 | expander | `'查看原始技术信息'` |
| streamlit_app.py | 3173 | selectbox | `'来源'` |
| streamlit_app.py | 3232 | button | `'查看'` |
| streamlit_app.py | 3238 | button | `'已保存'` |
| streamlit_app.py | 3239 | button | `'查看已保存资料'` |
| streamlit_app.py | 3242 | button | `'保存到知识库'` |
| streamlit_app.py | 3265 | button | `'搜索'` |
| streamlit_app.py | 3267 | button | `'配置说明'` |
| streamlit_app.py | 3278 | expander | `'添加资料'` |
| streamlit_app.py | 3279 | radio | `'添加方式'` |
| streamlit_app.py | 3283 | selectbox | `'分类 *'` |
| streamlit_app.py | 3286 | selectbox | `'资料来源类型'` |
| streamlit_app.py | 3292 | form_submit_button | `'保存草稿'` |
| streamlit_app.py | 3310 | selectbox | `'分类 *'` |
| streamlit_app.py | 3312 | selectbox | `'资料来源类型'` |
| streamlit_app.py | 3323 | form_submit_button | `'登记上传资料'` |
| streamlit_app.py | 3357 | selectbox | `'分类'` |
| streamlit_app.py | 3358 | selectbox | `'审核状态'` |
| streamlit_app.py | 3376 | button | `document.title` |
| streamlit_app.py | 3407 | button | `document.title` |
| streamlit_app.py | 3447 | radio | `'知识功能'` |
| streamlit_app.py | 3467 | button | `action_label` |
| streamlit_app.py | 3500 | selectbox | `'数据包来源'` |
| streamlit_app.py | 3509 | button | `'检查数据包'` |
| streamlit_app.py | 3538 | expander | `f'查看需要确认的项目（{len(inspection.issues)}）'` |
| streamlit_app.py | 3543 | expander | `'查看前20条'` |
| streamlit_app.py | 3557 | selectbox | `f'外部成员 {code}'` |
| streamlit_app.py | 3571 | button | `'确认导入'` |
| streamlit_app.py | 3606 | radio | `'服务类型'` |
| streamlit_app.py | 3610 | expander | `'高级设置'` |
| streamlit_app.py | 3615 | form_submit_button | `'测试连接'` |
| streamlit_app.py | 3657 | form_submit_button | `'测试连接'` |
| streamlit_app.py | 3680 | button | `'检查知识包'` |
| streamlit_app.py | 3693 | button | `'确认导入待审核区'` |
| streamlit_app.py | 3704 | expander | `'查看已审核内部规范'` |
| streamlit_app.py | 3727 | button | `'进入系统'` |
| streamlit_app.py | 3729 | expander | `'专业资料'` |
| streamlit_app.py | 3748 | radio | `'医疗协同内容'` |
| streamlit_app.py | 3772 | radio | `'服务状态筛选'` |
| streamlit_app.py | 3806 | form_submit_button | `'确认服务安排'` |
| streamlit_app.py | 3826 | form_submit_button | `'记录服务完成'` |
| streamlit_app.py | 3904 | expander | `'高级信息'` |
| streamlit_app.py | 4072 | expander | `f'需要医生复核 · 影像与检查 · {len(findings)} 项'` |
| streamlit_app.py | 4076 | expander | `f'关键健康指标 · {len(observations)} 项'` |
| streamlit_app.py | 4078 | expander | `f'主要异常与健康问题 · {len(management)} 项'` |
| streamlit_app.py | 4080 | expander | `f'建议复查 · {len(followups)} 项'` |
| streamlit_app.py | 4082 | expander | `f'需要人工核对内容 · {len(manual)} 项'` |
| streamlit_app.py | 4084 | expander | `f'一般记录 · {len(general)} 项'` |
| streamlit_app.py | 4087 | expander | `'查看全部指标'` |
| streamlit_app.py | 4091 | expander | `'查看解析详情（高级信息）'` |
| streamlit_app.py | 4115 | expander | `'查看完整文件'` |
| streamlit_app.py | 4136 | button | `'纳入当前年度基线初稿'` |
| streamlit_app.py | 4152 | button | `'生成健康基线初稿'` |
| streamlit_app.py | 4172 | expander | `'逐项查看依据'` |
| streamlit_app.py | 4180 | expander | `f'处理：{_report_candidate_label(item)}'` |
| streamlit_app.py | 4224 | expander | `'其他处理'` |
| streamlit_app.py | 4226 | button | `'忽略重复项'` |
| streamlit_app.py | 4232 | button | `'确认入档'` |
| streamlit_app.py | 4251 | expander | `'其他处理'` |
| streamlit_app.py | 4252 | button | `'忽略'` |
| streamlit_app.py | 4256 | button | `'人工修正'` |
| streamlit_app.py | 4262 | selectbox | `'对应健康指标'` |
| streamlit_app.py | 4270 | form_submit_button | `'保存修正'` |
| streamlit_app.py | 4280 | button | `'请医生复核'` |
| streamlit_app.py | 4284 | expander | `'其他处理'` |
| streamlit_app.py | 4286 | button | `'纳入健康管理'` |
| streamlit_app.py | 4290 | button | `'仅保留记录'` |
| streamlit_app.py | 4300 | button | `'创建随访任务'` |
| streamlit_app.py | 4332 | button | `'解析进行中…' if in_progress else '开始解析报告'` |
| streamlit_app.py | 4356 | radio | `'医疗内容'` |
| streamlit_app.py | 4400 | radio | `'成员健康内容'` |
| streamlit_app.py | 4446 | selectbox | `'查看年度'` |
| streamlit_app.py | 4475 | expander | `'重要健康背景'` |
| streamlit_app.py | 4497 | button | `'提交医生复核'` |
| streamlit_app.py | 4503 | button | `'确认健康基线'` |
| streamlit_app.py | 4518 | expander | `'修订已确认资料'` |
| streamlit_app.py | 4524 | form_submit_button | `'创建修订版本'` |
| streamlit_app.py | 4540 | expander | `'查看健康评估历史'` |
| streamlit_app.py | 4545 | expander | `'建立年度健康基线初稿或阶段复评'` |
| streamlit_app.py | 4547 | selectbox | `'评估类型'` |
| streamlit_app.py | 4551 | form_submit_button | `'保存初稿'` |
| streamlit_app.py | 4600 | selectbox | `'较早报告'` |
| streamlit_app.py | 4601 | selectbox | `'较新报告'` |
| streamlit_app.py | 4612 | expander | `'逐项查看依据'` |
| streamlit_app.py | 4629 | expander | `'检查结论的查看依据'` |
| streamlit_app.py | 4650 | selectbox | `'指标'` |
| streamlit_app.py | 4652 | selectbox | `'比较窗口'` |
| streamlit_app.py | 4933 | button | `label` |
| streamlit_app.py | 5077 | button | `label` |
| streamlit_app.py | 5120 | radio | `'事件筛选'` |
| streamlit_app.py | 5180 | button | `'查看当前时间范围健康数据'` |
| streamlit_app.py | 5310 | button | `'查看体检报告'` |
| streamlit_app.py | 5318 | button | `'查看完整体检'` |
| streamlit_app.py | 5323 | button | `'查看新旧报告对比'` |
| streamlit_app.py | 5333 | button | `'查看这段时间的完整健康数据'` |
| streamlit_app.py | 5349 | button | `'查看手术履历详情'` |
| streamlit_app.py | 5354 | button | `'查看用药与医疗'` |
| streamlit_app.py | 5371 | button | `'查看前后对比'` |
| streamlit_app.py | 5396 | button | `'上传并整理报告'` |
| streamlit_app.py | 5464 | expander | `'查看分类结果'` |
| streamlit_app.py | 5481 | expander | `'查看依据'` |
| streamlit_app.py | 5499 | selectbox | `'查看年度'` |
| streamlit_app.py | 5519 | expander | `'补充我的健康资料'` |
| streamlit_app.py | 5526 | form_submit_button | `'提交给健康管理团队'` |
| streamlit_app.py | 5549 | expander | `'重要健康背景'` |
| streamlit_app.py | 5573 | button | `'查看健康基线初稿'` |
| streamlit_app.py | 5579 | button | `'上传最近体检报告'` |
| streamlit_app.py | 5584 | button | `'查看完整健康基线'` |
| streamlit_app.py | 5649 | button | `label` |
| streamlit_app.py | 5657 | button | `'查看体检与检查'` |
| streamlit_app.py | 5691 | button | `'审核服务申请'` |
| streamlit_app.py | 5701 | form_submit_button | `'确认服务安排'` |
| streamlit_app.py | 5707 | button | `'记录开始服务'` |
| streamlit_app.py | 5717 | form_submit_button | `'记录服务完成'` |
| streamlit_app.py | 5744 | radio | `'服务内容'` |
| streamlit_app.py | 5797 | selectbox | `'服务分类'` |
| streamlit_app.py | 5827 | radio | `'个人设置内容'` |
| streamlit_app.py | 5873 | button | `label` |
| streamlit_app.py | 5921 | radio | `'医疗档案内容'` |
| streamlit_app.py | 5952 | expander | `f'{_fmt_dt(item.reviewed_at)} · 医生反馈'` |
| streamlit_app.py | 5974 | radio | `'健康内容'` |
| streamlit_app.py | 5989 | popover | `'个人设置'` |
| streamlit_app.py | 5990 | button | `'查看个人资料'` |
| streamlit_app.py | 6012 | selectbox | `'选择成员'` |
| streamlit_app.py | 6035 | radio | `'外部医疗状态'` |
| streamlit_app.py | 6064 | expander | `'登记外部医生协同'` |
| streamlit_app.py | 6066 | selectbox | `'成员'` |
| streamlit_app.py | 6068 | selectbox | `'关联内部医生复核（可选）'` |
| streamlit_app.py | 6074 | form_submit_button | `'登记外部协同'` |
| streamlit_app.py | 6091 | button | `'进入成员的完整处理记录'` |
| streamlit_app.py | 6126 | radio | `'数据设备功能'` |
| streamlit_app.py | 6152 | selectbox | `'接入成员'` |
| streamlit_app.py | 6160 | button | `'上传文件'` |
| streamlit_app.py | 6177 | expander | `'高级信息'` |
| streamlit_app.py | 6179 | button | `'同步演示血压设备数据'` |
| streamlit_app.py | 6184 | button | `'同步演示 Oura 数据'` |
| streamlit_app.py | 6189 | button | `'同步演示 Apple Health 数据'` |
| streamlit_app.py | 6196 | expander | `'高级信息：备用导入流程'` |
| streamlit_app.py | 6200 | button | `'验证并导入'` |
| streamlit_app.py | 6216 | expander | `'高级信息：数据同步记录'` |
| streamlit_app.py | 6233 | expander | `f'{_label(record.status)} · {display_provider(record.source_system)} · 需要人工确认'` |
| streamlit_app.py | 6236 | expander | `'高级信息'` |
| streamlit_app.py | 6238 | expander | `'查看原始技术信息'` |
| streamlit_app.py | 6243 | button | `'人工更正'` |
| streamlit_app.py | 6255 | selectbox | `'选择成员以管理设备'` |
| streamlit_app.py | 6274 | expander | `'添加或更新设备分配'` |
| streamlit_app.py | 6276 | selectbox | `'设备'` |
| streamlit_app.py | 6277 | radio | `'设备类别'` |
| streamlit_app.py | 6278 | selectbox | `'连接状态'` |
| streamlit_app.py | 6280 | form_submit_button | `'保存设备分配'` |
| streamlit_app.py | 6328 | selectbox | `'查看成员'` |
| src/executive_health_ai/ui/components/ai_citations.py | 45 | expander | `'查看依据'` |
| src/executive_health_ai/ui/pages/admin/experience.py | 23 | button | `'检查'` |
| src/executive_health_ai/ui/pages/admin/experience.py | 40 | radio | `'系统'` |
| src/executive_health_ai/ui/pages/admin/experience.py | 47 | radio | `'配置内容'` |
| src/executive_health_ai/ui/pages/admin/experience.py | 60 | expander | `'操作记录'` |
| src/executive_health_ai/ui/pages/admin/experience.py | 63 | selectbox | `'选择成员'` |
| src/executive_health_ai/ui/pages/admin/experience.py | 65 | expander | `'AI质量治理（高级）'` |
| src/executive_health_ai/ui/pages/baseline_visualization.py | 86 | selectbox | `'选择指标'` |
| src/executive_health_ai/ui/pages/baseline_visualization.py | 87 | selectbox | `'时间范围'` |
| src/executive_health_ai/ui/pages/baseline_visualization.py | 122 | expander | `'查看更新记录'` |
| src/executive_health_ai/ui/pages/doctor/experience.py | 28 | expander | `'重要健康背景与年度基线'` |
| src/executive_health_ai/ui/pages/doctor/experience.py | 39 | expander | `'关键指标与当前用药'` |
| src/executive_health_ai/ui/pages/doctor/experience.py | 46 | expander | `'完整资料位置与核对信息'` |
| src/executive_health_ai/ui/pages/doctor/experience.py | 48 | expander | `'已采取行动'` |
| src/executive_health_ai/ui/pages/doctor/experience.py | 69 | form_submit_button | `'提交判断并交回健管'` |
| src/executive_health_ai/ui/pages/doctor/experience.py | 94 | radio | `'复核工作'` |
| src/executive_health_ai/ui/pages/doctor/experience.py | 102 | selectbox | `'选择复核事项'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 20 | expander | `'需要您确认 · ' + ux.business_text(goal.title)` |
| src/executive_health_ai/ui/pages/manager/experience.py | 23 | radio | `'处理决定'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 25 | button | `'确认处理'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 45 | radio | `'今日事项筛选'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 67 | button | `'处理'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 69 | expander | `f'其他 {len(visible) - 12} 项'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 72 | button | `'处理'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 76 | expander | `'自动跟进状态'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 79 | button | `'处理确认'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 91 | selectbox | `'当前管理计划'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 96 | radio | `'管理操作'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 103 | selectbox | `'计划周期'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 107 | selectbox | `'首次人工评估层级（已有评估时沿用）'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 108 | form_submit_button | `'保存健康计划'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 127 | radio | `'由谁执行'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 129 | form_submit_button | `'安排随访'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 144 | selectbox | `'观察指标'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 150 | selectbox | `'观察结果'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 151 | selectbox | `'下一步管理'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 153 | form_submit_button | `'记录阶段结果并安排下一步'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 166 | expander | `'计划详情与已记录阶段结果'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 168 | expander | `'自动跟进与健康管理记录'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 175 | button | `'← 返回成员列表'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 187 | radio | `'成员页面'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 208 | button | `label` |
| src/executive_health_ai/ui/pages/manager/experience.py | 209 | expander | `'处理开放中的健康关注事项'` |
| src/executive_health_ai/ui/pages/manager/experience.py | 211 | expander | `'近期服务'` |
| src/executive_health_ai/ui/pages/member/experience.py | 44 | button | `'去完成'` |
| src/executive_health_ai/ui/pages/member/experience.py | 75 | button | `'查看健康计划'` |
| src/executive_health_ai/ui/pages/member/experience.py | 77 | button | `'查看健康数据'` |
| src/executive_health_ai/ui/pages/member/experience.py | 79 | button | `'上传体检报告'` |
| src/executive_health_ai/ui/pages/member/experience.py | 85 | button | `'返回健康概览'` |
| src/executive_health_ai/ui/pages/member/experience.py | 93 | button | `'查看年度健康基线'` |
| src/executive_health_ai/ui/pages/member/experience.py | 105 | expander | `'重要健康背景'` |
| src/executive_health_ai/ui/pages/member/experience.py | 119 | selectbox | `'选择健康指标'` |
| src/executive_health_ai/ui/pages/member/experience.py | 121 | radio | `'时间范围'` |
| src/executive_health_ai/ui/pages/member/experience.py | 144 | expander | `'数据来源与记录'` |
| src/executive_health_ai/ui/pages/member/experience.py | 160 | expander | `'接受或调整当前方案'` |
| src/executive_health_ai/ui/pages/member/experience.py | 161 | radio | `'我的选择'` |
| src/executive_health_ai/ui/pages/member/experience.py | 162 | button | `'记录选择'` |
| src/executive_health_ai/ui/pages/member/experience.py | 169 | radio | `'任务分类'` |
| src/executive_health_ai/ui/pages/member/experience.py | 176 | button | `'确认完成'` |
| src/executive_health_ai/ui/pages/member/experience.py | 181 | expander | `f'其他 {len(visible) - 5} 项行动'` |
| src/executive_health_ai/ui/pages/member/experience.py | 184 | button | `'确认完成'` |
| src/executive_health_ai/ui/pages/member/experience.py | 224 | expander | `'查看完整历程与依据'` |
| src/executive_health_ai/ui/pages/shell.py | 22 | button | `'进入成员健康中心'` |
| src/executive_health_ai/ui/pages/shell.py | 26 | button | `'进入 HealthOps 运营后台'` |
| src/executive_health_ai/ui/pages/shell.py | 64 | button | `'查看'` |
| src/executive_health_ai/ui/pages/shell.py | 68 | button | `'← 返回更多'` |
| src/executive_health_ai/ui/pages/shell.py | 76 | selectbox | `'选择成员'` |
| src/executive_health_ai/ui/pages/shell.py | 80 | expander | `'AI 质量治理（高级）'` |

# 角色体验改版记录

## Before → After

| 旧问题 | 新设计 / UI路径 | 实现 |
|---|---|---|
| 首页信息堆叠 | 成员 → 首页：今日行动、负责人、当前管理、2—4项变化 | ui/pages/member/experience.py |
| Yellow RiskEvent、UUID、systolic_bp进入描述 | 成员 → 健康 → 持续关注事项：业务名称、来源解释 | ui/experience.py |
| 基线不突出 | 健康概览首屏：年度、确认状态、建立日期、基线→当前、覆盖与依据 | member/experience.py |
| 不同健康页数据矛盾 | 首页、健康、医生统一查询有效观测；无当前数据与有历史记录分别表达 | ui/experience.py observations |
| 过去预约仍叫下一次 | 首页只取未来预约；服务详情提示过期安排需核实 | upcoming_service；streamlit_app.py |
| 今日医生计数与详情不一致 | 统一 pending_doctor_work，覆盖复核/基线/历史异常并去重 | ui/experience.py |
| 待复核与无待复核同时显示 | 医生 → 待复核/已完成；完成只取确认记录 | doctor/experience.py |
| 已完成区域出现待分配医生 | 完成状态过滤；未分配只用于待处理责任 | doctor/experience.py |
| Agent待审批无入口 | 成员360 → 管理 → 工作进展：同意继续/退回人工；医生同上下文 | manager/experience.py approvals |
| 缺少计划正常入口 | 成员360 → 管理 → 建立/调整计划 | care_commands.save_program |
| 缺少结果正常入口 | 成员360 → 管理 → 记录阶段结果 → 继续/调整/稳定/医生复核 | care_commands.record_outcome |
| 服务、配置与业务混杂 | 管理员独立导航，集成总览，默认不显示技术明细 | admin/experience.py |
| app文件持续增长 | 角色页面、共享投影和设计系统独立模块；保留复杂旧详情适配边界 | ui/pages/{member,manager,doctor,admin} |

## 写入一致性

阶段结果和医生复核经 care_commands 调用既有业务服务并发布同一进展事件；UI/API共用。事务由调用方一次提交。计划、任务与医生决定保留原事实模型和审计。未修改风险阈值或模型，未新增Agent工具。

## 演示与部署边界

角色切换仍为演示预览。连接已配置、测试通过与真实设备连接分别表达。连接测试表单不承诺持久保存；配置仍由部署环境管理。演示未来任务与预约在隔离demo数据库生成时使用相对日期，历史健康记录保持原采集日期。

## 验证记录

初始全量pytest：432 passed / 0 failed / 0 skipped。新增6项行为回归，覆盖状态投影、实际计划建立/调整、随访、结果写入、医生交接及成员完成任务。四条真实浏览器路径及审批已通过；实屏检查见 [UX_VISUAL_QA.md](UX_VISUAL_QA.md)。截图仅使用匿名演示数据库，业务操作验证使用隔离副本。

最终代码全量pytest：438 passed / 0 failed / 0 skipped，256.07秒；9项既有依赖弃用警告。命令：`.venv\Scripts\python.exe -m pytest -q --junitxml=.runtime/ux_complete.xml`。最后一次完整运行在全部代码修改完成后执行。

旧页面结构断言已迁移到实际角色模块，未通过删除测试或跳过测试掩盖失败。保留详细基线、报告和历程能力；streamlit_app.py 从6775行减少到6378行。

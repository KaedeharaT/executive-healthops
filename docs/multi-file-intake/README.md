# 多份健康资料 → 初始健康评估

入口：会员 → 健康档案 → 开始评估 / 继续填写 → 上传任意健康资料。
健康档案原“导入健康资料”入口也可选择辅助初评；原有单份资料确认入档流程保留。

## 实际行为

- 一批 1–20 份、总计不超过 100 MB；沿用每份 25 MB 的既有限制。
- 接收 PDF、DOCX、XLSX、CSV、TXT、JSON、PNG/JPG。旧式 DOC/XLS 请先转为 DOCX/XLSX；扫描 PDF / 图片未提供 OCR，保留原件并转人工，不伪造解析成功。
- 每份资料仍由现有 `PROFILE_INTAKE` Agent、Supervisor、Tool Registry 处理。没有第二套 Agent 框架。
- 结构化字段确定性映射。混合文件中的其余自由文本才请求现有 LocalLLMClient；服务不可用、超出处理范围或缺少逐字来源时保留规则结果并提示人工核对。
- 候选记录保留原文件、字段值、原文、PDF 页码 / Word 提取文本位置 / Excel 工作表与单元格 / JSON 字段路径。
- 同值去重但保留所有来源；跨文件值不同、与当前填写不同或否定陈述相互矛盾时标记冲突，不自动覆盖。
- 映射现有 11 个界面步骤（最近用药仍合并在当前用药步骤）；显示已填写、待确认、资料缺失、存在冲突。
- 可确定字段进入表单预填，原有填写优先；未提及不等于否认病史。未提供的症状原始分数留空，不推算。
- 每步保存后须核对来源；冲突须记录处理原因。新增资料或答案变更使相应核对凭据失效。全部核对后才能提交。
- 未读取、部分未识别及未映射到初评的报告内容需要记录人工处理；不会悄悄丢弃，也不会自动创建诊断、处方、Observation 或 Risk。
- 提交仅完成初评草稿整理，继续原有健管初评 / 医生边界。解析失败后人工接手的文件流程标为取消，不伪造成功。

## 存储与兼容

复用 Document、ReportExtractionRun、ReportExtractionCandidate、AgentGoal 和 IntakeAssessment。
`AgentGoal.context_json.intake_id` 绑定会员及具体年度初评；去重范围包含该初评。
`IntakeAssessment.review.document_intake` 保存来源指纹、填写指纹、核对人和冲突处理记录。
候选状态 `INTAKE_REVIEWED` 仅表示初评来源已核对，不等于正式健康事实 `CONFIRMED`。
不新增数据库表或迁移；保留已有档案导入、Member360 和初评提交后的业务流程。

## 验证证据

- 修改前 745 passed / 0 failed；全量回归 763 passed / 0 failed。最后的完成记录文案、待办数量及精确初评跳转修正另经 76 项针对性复测，0 failed（不重复计入全量测试数）。
- 本机 Ollama 实际请求 `parse_health_intake` 成功，2 项候选通过逐字来源核对，停在 WAITING_MANAGER；无正式医学写入。
- 最新服务已重载：Streamlit / FastAPI 均 HTTP 200，现有 worker 隐藏运行；QA 已停止，18560 端口释放。
- 修改前全量基线：`baseline/final-tests.txt`。
- 最终全量回归：`release-validation/final-tests.txt`。
- 新增持久化及医学边界测试：`tests/test_assessment_import.py`。
- Chromium 1440×900：真实上传 Word、Excel、JSON，核对睡眠冲突、预填运动/过敏/关注，完成全部步骤并提交。
- 截图及浏览器结果：`docs/images/multi-file-intake/`（5 张）。
- 可复现脚本：`scripts/qa_multi_file_intake.py`。`--prepare` 仅复制数据库到 `.runtime/multi-file-intake/qa.db` 并新增合成验收会员；浏览器服务使用端口 18560。
- 可选本地真实模型验证：`scripts/qa_intake_local_llm.py`。只允许本地 Ollama、内存数据库和合成文字；结果写入 `local-llm.json`，不保存 Prompt 或隐藏思维。

QA 服务通过现有隐藏进程管理器启动，日志、PID 与停止能力保持不变。未 push。

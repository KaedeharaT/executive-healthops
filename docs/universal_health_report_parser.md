# 通用体检报告解析与人工确认

## 目标与边界

本模块处理成员个人体检资料，不属于知识库。它将不同医院、机构和文件排版统一为可人工确认的候选资料；不自动诊断、不开处方、不修改用药，也不会让未确认内容进入风险引擎。

```text
PDF / 图片 / Excel / CSV / DOCX / TXT
  → Document Intake
  → Preflight（文件类型、Hash、文本层、页数、模板线索）
  → Generic Parser
  → 可选 Hospital Adapter / OCR / 语义兜底
  → Candidate + 页码原文证据
  → 人工确认
  → Observation / 结论处理 / 随访任务
  → 既有 HealthOps 与 Risk Engine
```

## 多医院策略

`GenericReportParser` 是默认入口，未知医院不会被拒绝。医院适配器仅可提高某个稳定模板的版式识别，不可改变候选模型或 Canonical Observation。

新增医院的步骤：

1. 取得脱敏样本，绝不提交至 Git。
2. 先运行通用解析器并统计错误类型。
3. 通用解析足够时不新增代码。
4. 仅当稳定模板反复出现同类错误时，新增 `BaseReportAdapter`。
5. Adapter 只能处理输入排版，输出仍为统一 Candidate。
6. 增加完全合成的回归夹具和测试。

## 文件与 OCR

当前支持 PDF、JPG/JPEG/PNG、XLSX、CSV、DOCX、TXT。PDF 有文本层时优先本地文本提取；CSV/XLSX 直接解析结构化表；DOCX 提取段落和表格。

扫描 PDF 或图片没有文本层时标记为 `NEEDS_OCR` / `OCR_REQUIRED`。本版本提供 `OCRProvider` 接口但不捆绑低质量 OCR；原文件保留且不会伪造解析结果。

## 候选与证据

解析输出只有四类候选：报告元数据、Observation、检查结论（Finding）和随访建议（Follow-up）。每个候选都记录来源文档、页码、原文证据、解析方法和解析置信度（高/中/低）。没有证据就不产生候选。

报告内的 `↑`、`↓`、H、L、阳性或可疑只是医院原始标记，绝不等于平台的风险等级。

## 人工确认和 HealthOps

- Observation 候选：人工确认后才写入 `Observation`，并以候选 ID 与报告页码保留来源追溯。
- Finding：人工可选择仅保留记录、纳入健康管理或交医生复核；解析器不会自动创建 HealthProblem。
- Follow-up：人工确认后才创建既有 `Task`。
- 未确认、已忽略、OCR 未完成的候选不会进入 Risk Engine。

## 隐私与 LLM

本模块遵循本地优先。默认 `ALLOW_EXTERNAL_PHI_LLM=false`。可选语义兜底仅支持本机 Ollama 的 Qwen，并且默认关闭；它只处理 Generic Parser 未可靠处理的影像、肺功能和随访自然语言片段。请求在发送前去除常见直接身份标识，限制为单页/单段，必须结构化输出页码、原文证据和置信度；不得发送完整报告或默认发送姓名、档案号、电话、身份证等信息。

真实报告仅允许本地验收：可通过 `HEALTH_REPORT_ACCEPTANCE_PATH` 由人工在本机选择，不应复制到项目、fixture、日志或 Git。应用日志仅应记录 document/run ID、页数、候选计数、耗时和错误类型。

## 未来 RAG 与适配器

报告解析不属于知识库，也不会自动调用 RAG。未来可在人工确认的个人资料与已审核知识之间生成辅助摘要，但必须保留来源并经人工复核。医院 Adapter、OCR Provider、受控语义兜底均是输入层扩展，不影响 Observation、Risk Engine、HealthProgram 或 DoctorReview 的核心模型。

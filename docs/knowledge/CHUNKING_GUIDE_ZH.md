# Knowledge Chunking Guide

原则：一个 Chunk 表达一个完整知识点，语义完整优先于长度。中文建议 150–800 字，英文建议 150–600 tokens；只有无结构超长文本才允许固定长度 fallback。

- SOP：按适用范围、步骤、Owner/Due、升级、结束条件、禁止行为分块；overlap 0–50 tokens。
- Guideline：recommendation、population、strength、evidence grade、section、year/version 同块；不得自行解释强度。
- FAQ：一问一答一块，保留问题标题。
- Table：保留表名、表头、完整逻辑行和页码，不拆开 value 与 meaning。
- Medication：标准名称/剂型与标签警示分开；保留 label/set id 和版本；不生成用药建议。
- Patient education：概念、用途、局限分别成块；overlap 50–100 tokens 仅在上下文确有必要时使用。

每块必须能追溯 `document_id`、heading/section_path、source_location、source_version、jurisdiction、language、audience、intended_use、license 和 content hash。翻译摘要必须标明生成/复核状态，不能伪装成原文。

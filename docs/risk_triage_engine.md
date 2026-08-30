# 风险分级与健康监护引擎

日常健康设备（苹果健康、Oura）归为 `WELLNESS`，用于趋势与生活方式管理；医疗监测设备（家庭血压、血糖、CGM）归为 `MEDICAL_MONITOR`。原始数据必须先完成标准化、质量检查和去重；无效数据不进入风险判断，待核实数据不直接产生紧急风险。

```text
Wellness / Medical Monitor → Data Gateway → Canonical Observation → Data Quality
→ Deterministic Risk Engine → 正常 / 需要关注 / 紧急风险 → HealthOps
```

风险等级只由已审核、启用的确定性规则决定。AI 健康监护助手只能整理趋势和生成摘要，不能改变等级、诊断、开药、停药或调整剂量。

黄色进入健康管理师审核；红色置顶并暂停健康管理计划、医疗处置优先。红色页面仅提供用户主动的 `tel:120` 入口及人工处置记录：系统不会自动拨打 120、联系真实紧急联系人或调用急救机构。当前规则均为 DEMO ONLY 工作流规则；正式临床规则必须由医生审核、附来源、版本与生效范围。

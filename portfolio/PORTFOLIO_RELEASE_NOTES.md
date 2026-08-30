# Executive HealthOps v0.9.0-portfolio

## Release purpose

用于简历、GitHub 与面试演示的研究型作品集版本。默认通过 `PORTFOLIO_DEMO=true` 启动隔离的匿名化演示故事。

## Demo story

`Demo Executive A` → 匿名化体检报告 → 结构化结果与依据 → 健康基线 → 演示风险分流 → 健康管理师 → 内部医生复核 → 健康计划与趋势 → 长期健康历程 → 医学知识治理。

## What is intentionally not claimed

- 不是真实医疗设备或临床决策系统。
- 演示风险规则不是经过临床治理的 Clinical RiskRule。
- Apple Health 仅为后端与 iOS Bridge 源码准备，真机验证尚未完成。
- 不包含真实报告、真实成员资料、密钥或生产部署配置。

## Start

```powershell
./scripts/start_portfolio_demo.ps1 -Rebuild
```

更多启动与安全边界见根目录 [README](../README.md)。

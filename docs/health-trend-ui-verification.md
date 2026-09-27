# 健康趋势 UI 验收

## 变更范围

健康数据页改为一个主容器，内部依次为筛选、摘要、图表、数据说明，使用轻分割线。
筛选显示实际可选指标数量，并将原有时间范围改为原生分段按钮。保留时间轴范围和记录明细。
摘要使用所选时间范围内的当前值、已确认年度基线、相对基线变化及最近测量时间；没有基线时明确提示。
两个时间点显示历史比较；零个或一个点不画空图，可切回全部时间。

未修改数据库、种子数据、业务 Service、趋势计算、健康基线语义、Risk Engine 或 Agent。
Deleted UI elements: 0；Missing UI elements: 0。

## 测试

执行：

```text
.venv/Scripts/python.exe -m pytest tests/test_health_trend_panel.py tests/test_health_chart_restoration.py tests/test_health_axis_visibility.py -q
44 passed / 0 failed
```

本次为相关回归测试结果，非全量测试结果。

## 真实浏览器

Streamlit + Chromium，从成员首页进入健康 → 健康数据。未注入业务状态。
可复现脚本：`scripts/qa_health_trend_panel.py`。

逐项切换并检查摘要、图表和数据说明：

| 指标 | 全部时间数据点 |
|---|---:|
| 体重 | 6 |
| BMI | 3 |
| 血压 | 7 组 / 14 个数值 |
| 心率 | 60 |
| 血糖 | 1344 |
| 糖化血红蛋白 | 2 |
| LDL-C | 4 |
| ALT | 2 |
| 步数 | 30 |
| 运动时间 | 30 |
| 活动消耗 | 30 |
| 睡眠时长 | 30 |
| 深度睡眠 | 30 |
| 快速眼动睡眠时长 | 30 |
| 清醒时间 | 30 |

以上全部使用已有合成 Demo 数据，没有新建数据点。
血压摘要验证当前 126 / 80、年度基线 132 / 86、变化 ↓6 / ↓6 mmHg。
HbA1c、ALT 显示“两次结果比较”；ALT、睡眠、步数没有年度基线时正确显示空说明。
BMI 30 天窗口只有一个点、血糖 7 天窗口没有点，均不绘制空图；“查看全部时间”恢复现有序列。

21 张截图位于 `docs/images/health-trend-ui/`，已逐张检查。
检查了 1500 × 1200、1366 × 768、1920 × 1080 桌面视口，无横向溢出。
轴、单位、时间、已有年度基线、当前标记及 Tooltip 配置保留。
摘要和记录明细沿用源记录 UTC 时间；共享图表保留既有浏览器时区显示方式。

## Git

Backup: `backup/pre-health-trend-ui`

Push: NO

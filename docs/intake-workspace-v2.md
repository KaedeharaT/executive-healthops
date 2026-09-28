# 初评资料工作区 v2 验收

页面使用：上传资料 → 看健康管理助手自动整理 → 点击待补充卡片 → 补完并核对来源 → 提交。

## 改动原因与实现

原页面把“初评预填”和“正式档案更新”两个内部处理分支直接做成资料用途单选框；健康档案主页同时渲染资料卡片与 16 行摘要表；资料处理进度分散在初评中的小表和独立运行详情中。因此用户需要理解处理路径，并多次寻找进度或填写入口。

现在健康档案和初评页使用同一个前置工作区：一个多文件上传区、固定显示的健康管理助手、七步业务进度和十张原生按钮卡片。处理结果来自现有资料导入流程、解析候选、来源审核记录和实际调用记录，没有新增 Agent 引擎、状态表或一级菜单。

- 草稿初评优先生成来源可核对的预填，同时准备既有档案比较结果；不覆盖已填写答案，不自动确认医疗事实。
- 已提交初评不会因上传而退回草稿；自动识别的新资料进入既有档案更新确认流程，医生判断入口保留。
- 混合资料中的自述病史保持自述属性，不因取消资料类型选择而自动升级成医学病史。Risk Engine、处方和医生责任边界未改动。
- 来源核对、冲突说明、未映射测量的人工处理记录以及提交校验继续执行。
- 完整档案的原有数据、16 项详情和导入历史保留在“查看完整健康档案”，主页不再重复铺表。
- 多批上传会继续显示尚在处理的资料；历史入口携带原实例选择，上传不创建用于展示的替身实例。
- AI 进行中来自真实请求发出通知；完成、未采用、不可用来自已有调用记录。无请求显示“本次未使用”。知识库不强制调用，有真实记录才显示完成。

## Chromium 实际验收

通过普通导航“会员 → Demo Intake Workspace V2 → Member360 → 健康档案”，未使用内部 URL。

验收在真实 Chromium、隔离数据库副本和合成会员上进行；生产业务数据未被验收修改。复现脚本：`scripts/qa_intake_workspace_v2.py`。浏览器记录：`images/intake-workspace-v2/browser-results.json`。

在项目根目录的 PowerShell 中复验（重建专用验收副本）：

```powershell
.venv/Scripts/python.exe scripts/service_processes.py stop --instance intake-v2
.venv/Scripts/python.exe scripts/qa_intake_workspace_v2.py --prepare
$env:LOCAL_LLM_ENABLED='false'
.venv/Scripts/python.exe scripts/service_processes.py start --instance intake-v2 --profile qa --manifest .runtime/intake-workspace-v2/manifest.json
.venv/Scripts/python.exe scripts/qa_intake_workspace_v2.py
```

一次上传体检报告、问卷与历史档案三份资料，验证顶部实时进度、候选提取、家族史/用药预填、来源核对、直接跳转和最终提交。体检测量保留为待核对候选，提交初评不自动写入正式医疗事实。

最终持久化核验：3 个原资料流程全部完成；16 项候选，其中 14 项初评字段、2 项测量。正式测量、Risk、疾病和用药计划新增均为 0。自动档案更新另有回归测试通过原确认入口写入测量，确认前为 0，确认后为 2；保留医生边界。

家族史直达第 2 步，用药通过键盘 Enter 直达第 6 步。保存基础资料后，“继续填写”进入第 2 步；所有必要步骤完成后进入提交。提交后原看板保留全部完成状态。

这组结构化合成资料不需要调用 AI 或知识库，页面明确显示“本次未使用”，没有伪造已完成调用。

## 截图

1. [健康档案主页](images/intake-workspace-v2/01-health-record-page.png)
2. [唯一上传区域](images/intake-workspace-v2/02-single-upload.png)
3. [正在处理](images/intake-workspace-v2/03-agent-running.png)
4. [整理完成、等待核对](images/intake-workspace-v2/04-agent-completed.png)
5. [十张可点击卡片](images/intake-workspace-v2/05-clickable-sections.png)
6. [家族史第 2 步](images/intake-workspace-v2/06-family-history-step.png)
7. [用药第 6 步](images/intake-workspace-v2/07-medication-step.png)
8. [主页无重复资料表](images/intake-workspace-v2/08-no-duplicate-table.png)
9. [完整档案仍可访问](images/intake-workspace-v2/09-full-archive.png)
10. [初评提交后的完成看板](images/intake-workspace-v2/10-submitted-board.png)
11. [完整工作区](images/intake-workspace-v2/11-complete-workspace.png)

## 测试与版本

新增回归测试覆盖唯一上传、取消用途选择、空状态、运行与完成状态、十类卡片、旧步骤状态清理、首个未完成步骤、完整档案访问、真实 AI/知识调用、多批处理、历史实例、医生等待和自述医学边界。既有初评和管理闭环测试继续保留。

最终全量测试：`818 passed / 0 failed`，耗时 496.86 秒。命令：`.venv/Scripts/python.exe -m pytest -q`。另有 13 条现有依赖弃用提示。先前界面路径复验为 `82 passed / 0 failed`。

| 验收项 | 结果 |
| --- | --- |
| Upload entry count | 1 |
| Purpose selector | REMOVED |
| Agent board directly visible | YES |
| Clickable assessment cards | 10 / 10 |
| Duplicate archive table | REMOVED |
| Full archive still accessible | YES |
| LLM activity visible | YES（无调用时明确未使用） |
| Knowledge activity truthful | YES |
| Actual browser | YES · Chromium 151.0.7922.34 |
| Management action loop preserved | YES |
| Tests | 818 passed / 0 failed |
| Push | NO |

备份分支：`backup/pre-intake-workspace-v2`，起点 `5fcc1fd`。

提交标题：`feat: simplify intake workspace and foreground agent progress`。不 push。

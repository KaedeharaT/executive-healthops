# Windows HealthOps 启停与 QA

双击根目录 `start_healthops.bat` 启动现有 Demo；BAT 优先调用 pwsh，未安装时使用 Windows PowerShell。Launcher 保持运行，服务进程隐藏。8000、8501 就绪且 worker 存活后才打开浏览器。

```powershell
.\scripts\start_portfolio_demo.ps1
# 或使用 .env 中的普通平台配置
.\scripts\start_platform.ps1

# 在另一个终端停止；也可以双击 stop_healthops.bat
.\scripts\stop_platform.ps1
```

Ctrl+C、关闭 Launcher 窗口、Launcher 异常退出都会触发整组服务清理。关闭网页不会停止平台。停止成功前会等待所管理进程退出及端口释放；如果外部进程占用了端口，则报告失败和进程详情，不输出成功。

普通启动只管理进程，不执行 migration、seed、责任记录写入或 Demo 重建。数据库缺失时要求显式准备；Launcher 拒绝 `-Rebuild`。截图入口同样复用现有 Demo。首次创建及后续 schema 升级是独立维护操作。

## 所有权与残留清理

- 沿用 `.runtime/processes/<instance>.json`，保存 Launcher、controller、supervisor 的 PID/创建时间、服务根 PID、真实 Python 后代、listener PID、端口与日志路径。没有第二套 PID 文件。
- 普通平台与 Demo 共用端口和 worker 生命周期。每次启动先检查外部占用，再回收这两个 profile 及确认为本项目的旧 Streamlit、FastAPI、worker。重启不会累积 worker。
- 所有权匹配解析后的 Python 入口及精确项目路径；不使用路径子串、进程名或单独端口号作为杀进程依据。终止时在同一个 Windows process handle 上重查创建时间，防止 PID 复用。
- 正常退出有 PowerShell 和 Python `finally`；隐藏 supervisor 另行监视 Launcher/controller 的 PID 与创建时间，因此控制台关闭不依赖 PowerShell `finally` 一定执行。supervisor 自身崩溃时，由 [Windows Job Object 的 KILL_ON_JOB_CLOSE](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) 释放后代。
- token 保护旧 Launcher 的延迟清理，避免它杀掉新启动的替代实例。跨实例 controller 锁串行执行清理与启动。
- 成功清理后移除 JSON 登记；崩溃后遗留的过期登记在下次启动回收。`.lock` 是同步文件，保留它不会代表服务仍在运行。
- 已在运行的外部 Ollama 不归 Launcher 所有；只有由 supervisor 启动的 Ollama 才进入其 Job Object。

日志位于 `.runtime/logs/<instance>/supervisor.log` 和各服务的 `*.stdout.log` / `*.stderr.log`。日志追加，不记录环境变量或密钥。

```powershell
.venv\Scripts\python.exe scripts/service_processes.py status --instance portfolio
# 指定 QA 组只停止该组；-All 还停止所有已登记 QA 组
.\scripts\stop_platform.ps1 -Instance visual-qa
.\scripts\stop_platform.ps1 -All
```

`-Instance` 用于登记和日志标识。普通平台 profile 重启会回收本项目已有服务；需要多个隔离版本并存时使用 QA manifest，而不是并发启动生产 profile 的多个 worker。

## 隔离验证

`-DatabasePath` 允许 Demo Launcher 使用明确指定的现有副本；默认仍是 `data/portfolio_demo.db`。

```powershell
# 要求 8000/8501 空闲；自动备份到 .runtime/launcher-validation/demo.db 后测试
.venv\Scripts\python.exe scripts/verify_launcher_lifecycle.py

.venv\Scripts\python.exe -m pytest tests/test_service_processes.py -q
```

验收脚本使用真实隐藏控制台，在 pwsh / Windows PowerShell 下测试干净启动、真实 CTRL_C_EVENT、WM_CLOSE 关闭窗口、三轮 start-stop、真实旧 FastAPI 残留回收、过期 PID、外部进程保护。每轮检查端口和 worker 后代全部释放，并比较正式 Demo 文件的 SHA-256。输出保存在 `.runtime/launcher-validation/`。

## Before / After 与 Chromium

QA snapshot 流程不变：`scripts/neumorphism_v2_setup.py` 生成源码和数据库副本及 `.runtime/neumorphism-v2/manifest.json`。

```powershell
.\scripts\start_visual_qa.ps1
.\scripts\stop_platform.ps1 -Instance visual-qa

.\scripts\start_visual_qa.ps1 `
  -CaptureScript scripts/qa_background_services.py `
  -CaptureArguments @('--url','http://127.0.0.1:18501', '--url','http://127.0.0.1:18502')

# 使用现有 Demo，完成截图后停止自己创建的服务组
.\scripts\capture_portfolio.ps1 -SkipInstall
```

底层 `service_processes.py start --profile qa` 保留自动化需要的后台模式；生产交互入口使用前台 `launch`。截图自动化的后台服务绑定其 PowerShell PID，退出时也会清理。

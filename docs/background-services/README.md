# Windows 后台服务与 QA

Streamlit、FastAPI、Agent worker 使用同一后台进程管理器，不创建可见服务终端。PowerShell 入口在当前终端运行；默认只打开一个浏览器页面，`-NoBrowser` 可关闭这一行为。业务代码、数据库结构和 Agent 状态机未修改。

## 启动与停止

```powershell
# 普通平台（端口 8000 / 8501）；自动重启同一实例中已登记的服务
.\scripts\start_platform.ps1
.\scripts\stop_platform.ps1

# 独立演示数据库；不指定 -Rebuild 时保留原有演示数据检查流程
.\scripts\start_portfolio_demo.ps1 -NoBrowser
.\scripts\stop_platform.ps1 -Instance portfolio

# 查看 PID、实际子进程、运行状态和日志路径
.venv\Scripts\python.exe scripts/service_processes.py status --instance portfolio

# 停止所有登记的服务组（不触碰未登记的外部程序）
.\scripts\stop_platform.ps1 -All
```

普通平台和演示平台默认使用相同端口，不要同时启动。需要独立实例时可指定 `-Instance`、`-ApiPort`、`-UiPort`。演示入口仍使用原有 `data/portfolio_demo.db`，改变端口不会隔离数据库。QA 多版本使用下面的独立数据库清单。

关闭浏览器或启动终端不会停止这些后台服务；请使用停止命令。启动器不会根据端口号强杀不明进程。旧版未登记进程需要先停止，之后均可通过新停止命令管理。

## 日志与清理保证

- `.runtime/logs/<instance>/supervisor.log`：后台管理器日志。
- `.runtime/logs/<instance>/<service>.stdout.log` / `stderr.log`：每个服务独立输出，重启追加。
- `.runtime/processes/<instance>.json`：管理器及服务 PID、创建时间、实际子进程、端口、日志路径；不保存环境变量或密钥。
- Windows Job Object 在管理器退出时清理整个服务树，包括 venv 启动器派生的实际 Python、worker 和其它后代。管理器崩溃也不会留下它拥有的服务。
- 启动必须通过 HTTP 就绪检查；必需服务启动失败或随后退出，会关闭同组服务。重复启动受到实例锁保护，PID 创建时间校验防止误杀复用的 PID。
- Ollama 已在运行时仅复用，不登记、不停止；如果由本次普通平台启动，则纳入该实例生命周期。

## Before / After 与 Chromium

既有 `scripts/neumorphism_v2_setup.py` 准备源码快照和数据库，输出 `.runtime/neumorphism-v2/manifest.json`。清单包含每个版本的 `source`、`database`、`port`；启动时不重建这些数据库。

```powershell
# 仅启动清单中的旧版 / 新版，保留运行供交互验收
.\scripts\start_visual_qa.ps1
.\scripts\stop_platform.ps1 -Instance visual-qa

# 启动 -> 真实无头 Chromium 验收 -> 自动停止所有版本（失败也清理）
.\scripts\start_visual_qa.ps1 `
  -CaptureScript scripts/qa_background_services.py `
  -CaptureArguments @('--url','http://127.0.0.1:18501',
                      '--url','http://127.0.0.1:18502',
                      '--url','http://127.0.0.1:18503')

# 原作品集截图入口：结束后自动停止 portfolio-capture 实例
# 保留原有 -Rebuild 行为，会重建匿名演示数据库
.\scripts\capture_portfolio.ps1 -SkipInstall
```

可用 `-Manifest <文件>` 指定另一组端口和隔离数据库。现有 QA 脚本仍使用无头 Chromium；Playwright Windows 驱动本身也设置隐藏窗口。QA 无需再打开独立 PowerShell/CMD 窗口分别启动服务。

## 本机验证记录

- 演示默认端口 8000/8501：真实 Chromium 进入“今日工作”，API `/health` 返回 `ok`。
- 普通平台隔离数据库、19000/19501：两次完整启动、浏览器访问、停止；worker 无错误输出，`--once` 完成退出码 0。
- 18501/18502/18503：三个版本全部通过真实 Chromium 检查，QA 脚本退出后端口均释放。
- 故意让截图脚本以退出码 13 失败：PowerShell `finally` 仍停止三个版本，实例状态 `stopped`。
- 在 QA 与两轮普通平台启停期间，每 50ms 枚举可见控制台窗口，新增数量 0。
- 生命周期测试覆盖：隐藏窗口、日志、重启、重复启动、外部占用端口保护、PID 复用保护、启动失败和管理器崩溃的整树清理。
- 隔离全量测试：710 passed / 0 failed（13 项既有依赖弃用警告），包含 7 项新增 Windows 进程生命周期测试。

本机 JSON、截图、逐项日志位于 `.runtime/background-qa/`。完整回归结果见 [final-tests.txt](final-tests.txt)。

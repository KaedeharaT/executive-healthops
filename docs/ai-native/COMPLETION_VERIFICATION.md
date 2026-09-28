# AI Native 主干验收记录

基线：`387e663a172e297d96cf7d47c0a4bc27c9e42907`。本轮没有改 V7 的配色、阴影、圆角或导航；没有新增聊天、知识库、设备厂商连接和商业模块。

## 同一会员的真实故事

使用隔离数据库 `.runtime/ai-native-final/browser.db`，不向正式会员写入验收资料。Chromium **151.0.7922.34**，1440 × 900，从普通首页进入，点击侧栏和表格行；没有内部页面 URL。

- 新建合成会员后已经存在唯一 MemberAgent。
- 同一次上传结构化问卷、自由文本病历、体检报告。真实业务进度观测到 **0 → 14 → 29 → 43 → 71%**；本地 AI 运行时保持当前步骤，文件数量显示 **2 / 3**。
- 结构化问卷走规则；自由文本真实调用现有本地模型，约 3 秒。初评中有来源内容自动整理，健管处理例外并提交；专业初评经健管确认。
- 识别出的体检报告衔接已有体检后管理政策。原始测量候选继续等待确认，不因衔接而直接入档。
- 同一会员提交医生判断，医生返回后恢复同一个体检后 Goal；健管确认后产生真实后续安排，Goal 达到 100%。
- 两次自然语言随访均真实调用原有本地模型（约 4–5 秒），在当前事项核对并统一保存。无医疗依据时生成协调事项；已有明确医生复查意见时生成正式 Recheck。原文、医生来源和操作记录可追溯。
- 合成到期事件唤醒原会员，关联既有事项；事项完成后核对业务结果。阶段核心事项结束后自动准备阶段复盘，等待健管；浏览器确认后创建下一阶段，原阶段 Goal 完成。

最终故事证据：[`story-evidence.json`](../images/ai-native-final/story-evidence.json)。会员身份唯一；初评与专业初评均已确认；存在正式复查和阶段复盘。测试还覆盖无业务结果时禁止宣告 Goal 成功。

合成到期日期通过明确的业务事件验证，没有假装实际等待了十六天。年度基线和阶段验收前置使用现有 Service 建立；上传、例外确认、医生判断、自然语言处理结果、阶段复盘和下一阶段通过真实浏览器操作。

## 设备与恢复

- 同一会员 **100 条**合成血压数据写入 Observation，原始数据带来的 Agent wake = **0**。
- 对同一个合成规则窗口重复判断，只有 **1** 个有意义变化事件，wake = **1**。这项规则验收不是医学诊断或新增正式风险等级。
- 实际停止并重启隔离服务进程：RUNNING 核对工作继续完成；WAITING_MANAGER、WAITING_DOCTOR、WAITING_TIME、WAITING_MEMBER、WAITING_INPUT 的原 Goal 保留，MemberAgent ID 不变。
- 单元回归额外验证过期执行租约、并发写入期间不持有模型事务、旧执行令牌不能覆盖已取消流程。

证据：[`device-evidence.json`](../images/ai-native-final/device-evidence.json)、[`restart-evidence.json`](../images/ai-native-final/restart-evidence.json)、[`same-member-doctor.json`](../images/ai-native-final/same-member-doctor.json)。

最后追加了复查语义去重验收：原文没有“随访”就不能被模型额外改写成随访安排；“复查血脂”和“血脂”按同一明确项目核对。真实模型与浏览器重跑只产生 **1 项**正式复查。使用合成到期时间处理该复查原有 TIME_DUE，进入等待健管；重复处理不新增 Goal。见 [`recheck-due-evidence.json`](../images/ai-native-final/recheck-due-evidence.json)。早期合成运行的历史输出保留用于追溯，不回写伪装成修正后的结果。

## 界面约束

| 项目 | 结果 |
|---|---|
| 健管一级菜单 | before 6 / after 6 |
| 按钮 | 历史基线约 49；本次 13 个可复现工作台页面共 44 |
| 强主 CTA | 每页最多 1 |
| 常规导航 | 一级菜单 → 工作页面 → 详情，最多 3 层 |
| 手工启动 Agent 按钮 | 0 |
| 健康资料上传 | 健康档案一个入口 |
| 自然语言处理结果 | 每个当前事项一个输入区 |
| 重复 Agent 入口 | 0 个新增或恢复 |
| 表格、五个 Member360 Tab、Soft Neumorphism | 保留 |
| 横向页面溢出 | 0 |

计数方法与既有 V7 浏览器盘点一致，记录实际渲染控件，包括返回和角色切换按钮；不把表格每行当作按钮。历史 49 与本次 44 的页面状态并不完全相同，因此不将差额宣传为“删除了 5 个按钮”。完整控件及几何数据见 [`inventory.json`](../images/ai-native-final/inventory/inventory.json)。输入队列、运行中和医生返回等动态状态另以故事截图和结构回归验证。

## 正式实例

正式数据库先使用 SQLite backup 保存到 `.runtime/ai-native-final/pre-completion-formal.db`，只迁移至 `0031_member_wait_input`，没有重建、删除或注入合成会员。

重新启动正式服务后：8501 `/_stcore/health` = 200，8000 `/health` = 200，原 worker 启动正常。真实 Chromium 已进入今日工作、Member360 管理、服务管理、年度管理；没有 Streamlit redacted error。正式页面截图不提交，避免把本地会员资料纳入仓库。

## 回归

原始基线：943 passed / 0 failed。

新增主干回归覆盖工具权限、幂等、计划边界、五类等待、来源约束、事务释放、设备、阶段闭环、档案衔接及复查候选去重。

全量最终回归：**984 passed / 0 failed**（618.56 秒）。主干定向回归：**41 passed / 0 failed**。最后的定向检查还覆盖复查到期及会员所在地日期/上午 9 点的转换，避免用服务器 UTC 日期理解“下周”等相对日期。不把重复执行的用例累加到全量数字。

最小 Eval 中的 Intake、Post-checkup、Doctor resume、Followup NLP、Recheck due、Stage review、Device meaningful change、Duplicate event、Crash resume 均包含在上述已通过的全量与定向集合中。`scripts/eval_ai_native.py` 提供独立重跑入口。

保留既有业务测试；更新的旧断言仅对应新增合法阶段 Goal、体检后衔接 Goal 和统一结果按钮文案，未放宽原始测量去重、医生确认或 Risk 的断言。

截图：[14 张主要界面](SCREENSHOTS.md)。

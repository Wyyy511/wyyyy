# WaterPulse AI Agent V7 · Visual Refresh

> 在 V6 自动化对话 Agent 基础上，仅刷新用户界面；核心数据、Baseline、Scenario 与 DeepSeek 调用逻辑保持不变。

# WaterPulse AI Agent V6 — 单对话框自动化版

本版按 2026-09-10 会议要求重构：**用户前台只看到自然对话、文件上传、模板下载和结果；Workflow/数据治理/Baseline/Scenario/日志均在后台自动执行。**

## 用户界面

没有左侧流程导航，没有“系统总览 / Baseline / Scenario / QA”等技术页面。用户只做几件事：

1. 在对话框说明想分析什么；
2. 上传 ESG/PDF/Word/Excel/CSV；如果没有数据，下载标准 Excel 模板；
3. 对非标准字段或 ESG 抽取候选值进行一次必要确认；
4. 系统自动检查数据、查询注册数据、调用 D Baseline；
5. Baseline 完成后，在对话中选择是否继续 PeakSeason / AqueductFuture / ExtremeDrought / NodeFailure；
6. DeepSeek 基于确定性 Baseline/Scenario JSON 生成风险解释、驱动分析和管理建议；
7. 在对话中下载 Word 分析报告。

每条 AI 消息下可选择展开“本次执行详情”。这里只显示可审计的工具名、状态、版本、input_hash 和警告，**不展示模型私有思维链**。

## 后台自动链路

用户问题/文件 → 意图理解 → 文件读取/候选抽取 → 字段识别 → 必要人工确认 → 数据完整性校验 → 注册数据查询（WS/DR/SV、BWD/DYS/CTS/OA）→ D Baseline → 可选 E Scenario → DeepSeek 解释 → Word 导出/日志。

- 企业私有采购字段缺失：向用户索取，不用国家均值冒充。
- 注册数据缺失：只有批准规则可用；阻断字段缺失则 insufficient/Unscored。
- Unknown 不等于 0，不静默归一化。
- PRWI、R、C、Coverage、Scenario 数字全部来自确定性程序。
- DeepSeek 负责意图理解、报告候选字段抽取和语言解释，不负责生成风险数字。

## DeepSeek API

DeepSeek API 只在后端读取环境变量：

- `DEEPSEEK_API_KEY`：启用 DeepSeek 时必填
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_MODEL=deepseek-v4-flash`（可在 Railway Variables 中替换）

如果没有配置 Key，确定性分析仍可运行，风险解释自动回退到本地安全模板。

### Railway 配置

Railway → Service → Variables：

`DEEPSEEK_API_KEY = 你的密钥`

可选：

`DEEPSEEK_MODEL = deepseek-v4-flash`

不要把 API Key 写进 `.env.example`、`static/app.js` 或 GitHub。

## 部署

1. 解压本 ZIP。
2. GitHub 仓库根目录直接上传 `server.py`、`main.py`、`requirements.txt`、`railway.json`、`static/`、`tools/`、`engines/` 等源码，**不要只上传 ZIP**。
3. Railway 从 GitHub 部署。
4. 在 Variables 添加 `DEEPSEEK_API_KEY`。
5. Networking → Generate Domain。

启动命令已经写在 `railway.json`：

`uvicorn server:app --host 0.0.0.0 --port $PORT`

健康检查：`/api/health`  
Agent 状态：`/api/agent/status`  
标准模板：`/api/template`

## 与老师会议要求对应

- 隐藏后台 Workflow：已实现
- 用户界面去技术化：已实现
- 单对话框：已实现
- 文件上传：已实现
- Excel 模板下载：已实现
- ESG/PDF/Word/Excel/CSV：已实现
- 数据完整性自动判断：已实现
- 注册数据/代理规则补充：已通过 query adapter 接入；无批准数据时停止
- Baseline 自动调用：已实现
- Scenario 在 Baseline 后链式调用：已实现
- DeepSeek API：已接入（需配置 Key）
- AI 风险解释/建议：已接入 DeepSeek，Baseline/Scenario 后自动调用，且数字锁定为确定性结果
- 报告自动导出：已实现
- 后台执行详情折叠：已实现

## 当前边界

正式 B/C 数据查询 kernel 和 E 最终情景数据仍应按团队冻结版本替换现有适配器/快照；这不会改变前台交互。会话状态当前保存在服务进程内存中，Railway 重启后旧会话不会保留，比赛演示和单次分析不受影响。

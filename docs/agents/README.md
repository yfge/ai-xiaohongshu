# Agents 设计指南

本文档阐述 AI Xiaohongshu 项目中智能体（Agent）体系的整体设计、职责划分与落地实践，便于后续扩展、协作与测试。

## 目标与原则

- **业务聚焦**：所有 Agent 都围绕小红书种草内容生产与转化漏斗展开，保持场景闭环。
- **模块化组合**：一个 Agent 只解决明确的子问题，通过编排（Orchestrator）实现串联。
- **可观测性**：每次执行都必须写入结构化日志与可复现的上下文，方便回放与调试。
- **人机共创**：默认支持人工介入节点，允许运营人员在关键环节做编辑与审批。

## Agent 拓扑

| 模块 | 角色 | 上下游 |
| --- | --- | --- |
| `ResearchAgent` | 收集竞品/热词/趋势，输出结构化洞察 | 数据源 → 研究报告 |
| `PlanningAgent` | 拆解内容主题、种草角度与发布时间表 | 研究报告 → 内容计划 |
| `CreationAgent` | 生成图文/视频脚本、标题、标签 | 内容计划 → 素材草稿 |
| `ReviewAgent` | 质量与合规审查，给出修改建议 | 素材草稿 → 待发布内容 |
| `DistributionAgent` | 生成发布排期、渠道参数与 A/B 方案 | 待发布内容 → 发布指令 |
| `AnalyticsAgent` | 汇总曝光、互动、GMV 指标，反馈给规划层 | 反馈数据 ← 指标面板 |
| `CollageAgent` | 将提示词 + 参考素材编排为 Ark 生成的组图与提示词 | CreationAgent → 视觉素材 |

Orchestrator 负责编排与状态管理，可选择「顺序工作流」或「事件驱动」两种模式：

1. 顺序模式适合冷启动：从调研到分发逐步推进；
2. 事件模式适合持续运营：当新数据到来时触发局部 Agent 重新运行。

## Orchestrator 实现

- 核心实现位于 `backend/app/services/orchestrator.py`，提供 `AgentOrchestrator` 类。
- 通过 `register(agent_id, handler)` 顺序注册需要执行的 Agent，`handler` 接收/返回上下文字典。
- 执行 `run(initial_context)` 后会依次调用每个 Agent，并将结果聚合在上下文中（键名为 Agent ID）。
- 若注入 `AgentRunRecorder`，每个步骤会自动写入 `agent_runs.jsonl`，包含 request_id、耗时与输出要点，方便复盘。
- 示例：
  ```python
  orchestrator = AgentOrchestrator(recorder=recorder)
  orchestrator.register(agent_id="ResearchAgent", handler=run_research)
  orchestrator.register(agent_id="PlanningAgent", handler=run_planning)
  context = await orchestrator.run({"brief": brief_payload})
  ```

### Agent Run API

- FastAPI 提供 `GET /api/agent-runs` 接口，支持 `limit`/`offset` 分页，并可按 `agent_id`、`status`、`since` 过滤执行记录。
- 响应中的 `metadata` 会包含生成耗时、失败的 prompt 标题等调试信息，可直接接入前端监控或 BI 系统。
- 前端页面 `/agent-runs` 提供执行记录表格，快捷筛选与排查异常。

## CollageAgent 设计要点

- 输入：创意简报（prompt）、目标数量 N、参考图列表。
- 处理：
  1. 使用 `ark_prompt_template` 构建系统提示，调用 Ark Chat 生成结构化 JSON。
  2. 对 JSON 解析完成后，针对每个提示词调用 Ark 图像生成接口，传入参考图（Base64 Data URI）。
- 输出：含 `prompts` 列表（title/prompt/description/hashtags）与 `images` 列表（url/b64/size）。
- 错误处理：若返回数量少于 N 或 Ark 报错，直接抛出并在前端提示。
- 可观测性：记录提示词 JSON、耗时、Ark request id，方便复盘。

## Prompt 与上下文规范

- 所有 Prompt 使用 Markdown 模版，包含角色、输入、输出格式三部分；
- 输入上下文限制在 3 层：`用户配置` → `历史结果` → `外部引用`，并在日志中显式标注来源；
- Agent 输出以 JSON Schema 描述，对接 FastAPI/Next.js 时可直接转换为类型定义；
- 关键参数（模型名称、温度、最大 token）统一由环境变量注入，默认读取 `backend/app/core/settings.py` 中的配置。

## 状态与数据存储

- 短期状态（单次任务）写入 Redis Stream，方便 Orchestrator 消费；
- 中长期知识库（案例、模板）存放在向量数据库，并通过 `ResearchAgent` 缓存热点；
- 所有执行日志优先写入 MySQL `agent_runs` 表（通过 `DATABASE_URL` 配置），字段包括 `agent_id`、`input_hash`、`output_ref`、`duration_ms`；如未配置数据库则退回 JSONL 存储。

## 本地开发流程

1. 在 `backend` 中实现对应的 `services/agents` 模块，定义接口协议；
2. 使用 `tests` 目录下的基准用例对核心 Agent 做离线验证；
3. 通过 `frontend` 的 `/docs/agents` 页面暴露设计稿、流程图与操作手册；
4. 利用 `pre-commit` 与 Husky 确保提交前通过格式化与静态检查；
5. 在 `docs/agents` 下补充每个 Agent 的运行示例、提示语与常见问题。

## 后续扩展

- 建立统一的指标埋点 SDK，将 Agent 结果自动同步到监控平台；
- 引入权限系统，实现不同团队角色对 Agent 操作的细粒度控制；
- 与自动化部署（如 Airflow、Temporal）集成，实现定时或事件触发的 Agent Pipeline。

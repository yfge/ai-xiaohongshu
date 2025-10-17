# Agents Handbook

> 面向研发、运营、产品的统一指南，帮助快速理解并扩展 AI Xiaohongshu 项目的智能体（Agent）体系。

---

## 1. 目标与价值

- **业务聚焦**：所有 Agent 围绕小红书种草链路（洞察 → 策划 → 产出 → 分发 → 复盘）。
- **自动化 + 可编辑**：默认支持人机协同，关键节点可人工覆写或审批。
- **可观测性**：每次执行产生结构化日志、上下文与指标，便于复现与 A/B。
- **可组合**：通过编排层（Orchestrator）自由组合多个 Agent，快速搭建新工作流。

## 2. 全局架构

```
┌──────────────────────────────────────────────────────────────┐
│                          Orchestrator                         │
│              (Workflow / Event-driven 状态机)                 │
├─────────────┬───────────────┬───────────────┬────────────────┤
│ResearchAgent│PlanningAgent  │CreationAgent  │CollageAgent     │
│   (洞察)    │   (策划)      │   (内容)      │ (营销组图)      │
├─────────────┴────┬──────────┴────┬──────────┴───────┬───────┤
│ReviewAgent       │DistributionAgent │AnalyticsAgent       │
│   (审核)         │   (分发)         │   (复盘)            │
└──────────────────┴─────────────────┴───────────────────────┘
```

- **Orchestrator**：负责任务调度、状态流转、并发/重试策略，可支持顺序与事件驱动两种模式。
- **Agent Orchestrator Skeleton**：`backend/app/services/orchestrator.py` 提供最小可用的顺序编排器，可按 `register → run` 的方式串联 Research → Planning → Creation 等 Agent，并复用 `agent_runs` 记录执行轨迹。
- **Agent Run API**：`GET /api/agent-runs` 可查询最新执行记录，为前端监控或 BI 面板提供数据源。
- **Shared Services**：
  - `backend/app/services/marketing.py`：封装 Ark 模型调用、日志与指标采集。
  - `backend/app/core/config.py`：统一管理 Prompt 模板、模型 ID、阈值。
  - `docs/agents/README.md`：团队内设计规范与流程说明。

## 3. Agent 列表与职责

| Agent | 核心输入 | 核心输出 | 备注 |
| --- | --- | --- | --- |
| `ResearchAgent` | 竞品、渠道数据、热词 | 洞察报告、用户画像 | 可连接自建数据源或外部 API |
| `PlanningAgent` | 洞察报告、业务目标 | 内容主题、发布排期 | 支持多渠道策略组合 |
| `CreationAgent` | 内容主题、品牌调性 | 图文脚本、标题、标签 | 调用文本/多模态模型生成草稿 |
| `CollageAgent` | 创意简报、参考图、生成数量 | 提示词 JSON、营销图像 | 已实现，详见下文 |
| `ReviewAgent` | 内容草稿、品牌守则 | 审核结果、修改建议 | 支持多轮交互或人工确认 |
| `DistributionAgent` | 审核通过内容、渠道配置 | 发布指令、A/B 方案 | 可对接自动化投放平台 |
| `AnalyticsAgent` | 数据仓或日志指标 | 复盘报告、策略反馈 | 结果回流至 Planning/Creation |

### 3.1 CollageAgent 详解

- **场景**：营销运营上传参考图，系统生成多组提示词与成图，支撑“种草组图”素材产出。
- **实现**：`backend/app/services/marketing.py` 中 `MarketingCollageService`。
  - 调用 Ark Chat Completions 生成结构化 JSON（`PromptGenerationPayload`），输出 2-3 句中文场景描绘，凸显营销种草语境。
  - 解析 JSON 后，将每条提示词与全部参考图送入 Ark Images API，生成图片。
- **输出结构**：
  ```json
  {
    "prompts": [ { "title": "...", "prompt": "...", "hashtags": ["..."] } ],
    "images": [ { "prompt": { ... }, "image_url": "...", "image_base64": "..." } ]
  }
  ```
- **配置项**：`ARK_PROMPT_MODEL`、`ARK_IMAGE_MODEL`、`ARK_IMAGE_SIZE`、`ARK_PROMPT_TEMPLATE` 等。
- **前端入口**：`/marketing/bundle` 页面（`frontend/app/marketing/bundle/page.tsx`）。

## 4. Prompt 策略

1. **模板化**：所有系统提示存放在 `config.py`，可根据不同业务线开启 Feature Flag。
2. **多模态输入**：参考图通过 Data URI 形式注入 Ark 提示中，确保模型接收到完整视觉上下文。
3. **结构化输出**：要求 Ark 返回 JSON + Schema，有利于校验、前端展示与二次加工。
4. **可调参数**：温度、最大 token、提示词数量上限均可通过环境变量调整。

## 5. 数据与观测

- **日志**：每个 Agent 执行应记录 request_id、输入摘要、耗时、模型响应、错误码。
- **持久化**：
  - 临时会话与工作流状态 → Redis / 内存。
  - 长期素材（图像、脚本）→ 对象存储 / CDN。
  - 指标与复盘 → PostgreSQL / BI 系统。
- **可追溯性**：统一以 `agent_runs` 表记录执行历史，字段包括 `agent_id`、`input_hash`、`output_ref`、`duration_ms`。

## 6. 流程示例：营销组图工作流

1. 运营在前端上传参考图 & 简报 → 发起 `POST /api/marketing/collage`。
2. 后端校验参数 → 触发 CollageAgent：
   - Chat 模型返回提示词 JSON。
   - Images 模型生成对应图片。
3. 返回结果给前端 → 展示提示词 + 图片预览。
4. 可选：将输出同步给 ReviewAgent / DistributionAgent 进行后续操作。

## 7. 测试与验证

- **单元测试**：`backend/tests/test_marketing_service.py` 使用 stub Ark 客户端验证：
  - 正常路径（提示词与图像生成成功）。
  - 缺少凭证 / 数量超限等错误路径。
- **健康检查**：`backend/tests/test_health.py` 验证 `/health` 接口。
- **本地联调**：
  ```bash
  cd backend && pytest
  curl http://127.0.0.1:8000/health
  curl -F 'prompt=...' -F 'count=...' -F 'images=@foo.jpg' http://127.0.0.1:8000/api/marketing/collage
  ```

## 8. 部署与运维建议

- **环境变量**：在部署环境（Docker/CI/CD）安全地注入 Ark 凭证及模型 ID。
- **扩展性**：
  - 使用任务队列（Celery/Temporal）处理耗时的图像生成请求。
  - 引入缓存/去重，避免重复生成相同提示词。
- **监控**：
  - 记录 Ark API 的成功率、耗时、错误分布。
  - 结合前端埋点，跟踪生成素材的实际使用与转化效果。

## 9. 开发规范

- **代码结构**：
  - 所有 Agent 的核心逻辑置于 `app/services`，保持纯净、易测试。
  - API 层仅做参数解析、错误映射。
  - Schema 使用 Pydantic，确保输入输出校验。
- **提交前检查**：
  ```bash
  pre-commit run --all-files
  pnpm --filter frontend lint
  ```
- **文档更新**：新增/修改 Agent 时同步更新 `docs/agents/README.md` 与本文件。

## 10. Roadmap

- 引入 **Workflow Studio**：可视化编排多个 Agent。
- 支持 **多渠道素材生成**：如抖音、微博等平台模板。
- 接入 **权限与审批流**：区分不同角色对 Agent 的操作权限。
- 构建 **评测体系**：对提示词质量、生成图片进行自动化评分。
- 深化 **数据回流**：自动根据转化数据调优 Prompt 与模型参数。

---

如需讨论新的 Agent 需求或对现有流程提出优化，请在项目 Issue 中创建 `agent-proposal`，或直接联系研发负责人。

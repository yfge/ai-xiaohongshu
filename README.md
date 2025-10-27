# AI Xiaohongshu

AI 驱动的小红书内容运营工作台，提供 FastAPI 后端、Next.js（shadcn/ui）前端与可编排的 Agent 体系基线。

## 项目结构

```
.
├── backend/                # FastAPI 服务与测试
├── frontend/               # Next.js + shadcn/ui 前端
├── docs/agents/            # Agent 设计与使用文档
├── .husky/                 # Git 钩子脚本
└── .pre-commit-config.yaml # 统一代码检查配置
```

## 快速开始

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000/health` 查看健康检查。

### 前端

```bash
cd frontend
pnpm install # 或 npm install
pnpm dev
```

打开 `http://127.0.0.1:3000` 查看首页。

前端内置：
- `/marketing/bundle` 工具页：上传参考图与创意提示词，让系统调用 Ark 生成组图。
- `/creative/covers` 工具页：上传视频并选择样式或预设，生成 9:16 与 3:4 封面预览。
  - 支持异步任务：`POST /api/creative/cover-jobs` 入队后台处理，`GET /api/creative/cover-jobs/{id}` 查询状态。

## 环境变量

在项目根目录创建 `.env`（供后端使用）并配置：

| 变量 | 说明 |
| --- | --- |
| `ARK_API_KEY` | Ark API Key，如留空需改用 `ARK_AK` + `ARK_SK` |
| `ARK_PROMPT_MODEL` | 提示词 JSON 模型端点 ID |
| `ARK_IMAGE_MODEL` | 图像生成模型端点 ID |
| `ARK_IMAGE_SIZE` | 可选，输出尺寸，默认 `1024x1024` |
| `AGENT_RUN_STORE_PATH` | 可选，Agent 执行日志 JSONL 存储路径，默认 `storage/agent_runs.jsonl` |
| `DATABASE_URL` | 可选，数据库连接串（推荐 MySQL，如 `mysql+aiomysql://user:pass@host:3306/ai_xiaohongshu`）|
| `DATABASE_ECHO` | 可选，SQLAlchemy 是否回显 SQL 语句，默认 `False` |

前端可通过环境变量 `NEXT_PUBLIC_API_BASE_URL` 指定后端地址，默认指向 `http://localhost:8000/api`。

## 开发工具

- `pre-commit`：Python/Tailwind/TypeScript 统一格式化与静态检查
- Husky：Git Hook，在提交前激活 `pre-commit` 与前端 Lint
- Commitlint：约束 Conventional Commit 信息

初始化工具：

```bash
pnpm install
pnpm run prepare
pre-commit install
```

## 营销组图说明

详见 `docs/marketing_collage.md`，包含 Ark 配置、接口说明与调试指引。

## 数据库与可观测性

- 如果配置了 `DATABASE_URL`，系统会使用 SQLAlchemy + MySQL（或任意兼容的数据库）持久化 Agent 执行记录；如未配置则回退至 JSONL 存储。
- 初始化数据库后运行迁移：
  ```bash
  cd backend
  alembic upgrade head
  ```
- CollageAgent 与 Orchestrator 会写入执行日志，可通过 `GET /api/agent-runs` 获取，支持 `agent_id`、`status`、`since` 等过滤。
- 在启用数据库模式时，会额外持久化提示词与生成图片明细至 `agent_run_prompts`、`agent_run_images` 表；使用 `GET /api/agent-runs/{request_id}` 可获取某次执行的完整详情（Prompts + Images）。
- 前端页面 `/agent-runs` 提供可视化仪表盘，支持在线筛选与分页浏览。
- 响应包含 `runs`（按时间倒序）、分页参数以及结构化的 `metadata` 字段，便于诊断 Ark 调用耗时与失败。
 - 在详情抽屉中支持「按关键词筛选 Prompt」与一键复制提示词/话题、下载图片。
- 数据流示意图与详情 API 参考：`docs/agents/README.md`。

## 认证与对外 API

- 管理端基于 HTTP Basic（配置环境变量 `AUTH_BASIC_USERNAME` 与 `AUTH_BASIC_PASSWORD_HASH` 或 `AUTH_BASIC_PASSWORD_PLAIN`）。
- API Key：
  - 管理端创建：`POST /api/admin/api-keys`，返回一次性明文 Key（格式：`<prefix>.<secret>`）。
  - 列表：`GET /api/admin/api-keys`。
  - 对外调用：在请求头携带 `X-API-Key: <prefix>.<secret>`。
  - 存储：配置了 `DATABASE_URL` 时，API Key 默认落库（`api_keys` 表）；未创建表或未配置数据库则回退到 JSONL（`API_KEY_STORE_PATH`）。
  - 作用域（scope）：`marketing:collage` 用于营销组图接口。
- 对外接口：
  - `POST /api/external/marketing/collage`（与内部一致的参数/返回）。
  - `POST /api/external/creative/covers`（与内部一致，需 scope `creative:covers`）。
  - 内部：`POST /api/creative/covers`（CPU 自动封面生成：上传视频 + 标题/副标题；支持 `style` 或 `preset_id/preset_key`；返回 9:16 与 3:4 Base64 预览）。
  - 内部异步：`POST /api/creative/cover-jobs` 入队，`GET /api/creative/cover-jobs/{id}` 查询。
- 审计：所有请求都会写入审计日志（JSONL 默认，路径由 `AUDIT_LOG_STORE_PATH` 指定）。
- 审计 SQL：配置 `DATABASE_URL` 后，审计日志将落库到 `audit_logs` 表；可通过 `GET /api/admin/audit-logs` 查看。
- 速率限制：对外 API 基于 API Key 启用全局限流，配置 `API_KEY_RATE_WINDOW_SECONDS` 与 `API_KEY_RATE_MAX_REQUESTS`（默认 60 req/60s）。超出返回 429。

### 前端管理页（开发用途）

- `/admin/api-keys`：简单的 API Key 管理界面（创建、列表、启/停），需要输入 Basic 用户名密码后操作。仅用于本地/内网环境，不建议在生产环境暴露。
- `/admin/audit-logs`：审计日志查看（可按 Actor 类型、时间、数量过滤）。
  - 支持条件：`actor_type`、`since`、`method`、`status_code`、`path_prefix`；展示耗时与请求/响应字节数。
  - 支持分页（limit/offset）、按 `request_id` 一键链路查看、导出 JSON/CSV。
- `/admin/cover-presets`：封面样式预设管理（创建、列表、编辑）。
- `/admin/cover-jobs`：封面任务列表（状态筛选、分页）。

## Agents 文档

详见 `docs/agents/README.md`，其中包含 Agent 拓扑、Prompt 规范、状态管理与本地调试流程。

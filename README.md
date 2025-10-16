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

前端内置 `/marketing/bundle` 工具页，可上传参考图与创意提示词，让系统调用 Ark 生成组图。

## 环境变量

在项目根目录创建 `.env`（供后端使用）并配置：

| 变量 | 说明 |
| --- | --- |
| `ARK_API_KEY` | Ark API Key，如留空需改用 `ARK_AK` + `ARK_SK` |
| `ARK_PROMPT_MODEL` | 提示词 JSON 模型端点 ID |
| `ARK_IMAGE_MODEL` | 图像生成模型端点 ID |
| `ARK_IMAGE_SIZE` | 可选，输出尺寸，默认 `1024x1024` |

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

## Agents 文档

详见 `docs/agents/README.md`，其中包含 Agent 拓扑、Prompt 规范、状态管理与本地调试流程。


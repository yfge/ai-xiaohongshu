# 小红书种草营销组图功能调研与任务分解

## 背景与目标
- 为运营人员提供「上传 1~M 张参考图片 + 提示词 + 目标生成数量 N」的交互。
- 基于输入调用火山引擎 Ark 相关 API：
  1. 模板包装后发送到“提示词生成”接口（文档： https://www.volcengine.com/docs/82379/1494384 ），获取结构化 JSON，里面包含 N 条提示词。
  2. 将每条提示词结合上传的所有图片，调用“图像生成”接口（文档： https://www.volcengine.com/docs/82379/1824121 ），共生成 N 张图片。
- 产出需要确保可追踪（日志）、可配置（API Key）、可测试。

## 前置问题与假设
- **鉴权方式**：是否统一采用 AK/SK + SessionToken，还是使用 STS/签名？需要确认凭证来源及配置路径。
- **上传图片存储**：临时文件放置到哪里？是上传至 S3/OSS 还是暂存本地磁盘（FastAPI `UploadFile`）？目前假设单次请求以内存/临时目录即可。
- **模板包装逻辑**：是否已有成文模板？需与产品确认 Prompt 模板格式和变量（提示词、图片描述、目标受众等）。暂假设由后端维护静态模板。
- **生成图片返回**：Ark 接口返回的是 URL、Base64 还是直接文件？需根据文档确定并规划落库策略。
- **前端交互**：单/多图上传控件、生成进度反馈、结果展示（网格/列表）需要设计。是否需要轮询、WebSocket 或批处理？初步考虑立即返回生成结果（同步），若耗时大可能需要队列/任务系统。

## 技术分层任务

### 1. 配置与基础设施
- [x] 新增 Ark API 配置项（Key/Secret/Endpoint/Template ID）至 `backend` 配置（env + pydantic settings）。
- [x] 引入 `volcengine-python-sdk[ark]` 客户端封装重用，考虑抽象 `services/ark_client.py`。
- [x] 添加依赖到 `backend/pyproject.toml`（runtime + optional tests），并更新文档。

### 2. 后端接口设计
- [x] FastAPI 新增路由（例如 `POST /marketing/campaigns/bundle-images`）。请求体：
  - `prompt` (str)
  - `images` (List[UploadFile])
  - `count` (int, N)
- [x] 编排逻辑：
  1. 保存上传图片到临时路径（或直接读取 bytes）。
  2. 构建模板 payload 并调用 Ark 提示词生成接口，解析 JSON 结构，提取 N 个提示词。
  3. 对每个提示词调用 Ark 图像生成接口，传入所有图片（可能需要 Base64/URL）。
  4. 收集生成结果（URL/Base64/meta），组装响应体。
- [x] 错误处理：API 失败重试/异常映射、超时控制、参数验证（count 与返回数量一致）。
- [x] 监控/日志：记录请求 ID、模板返回、耗时。

### 3. 后端测试
- [x] 使用 `pytest` / `respx`（或 httpx Mock）模拟 Ark 接口。
- [x] 单元测试：
  - 模板请求/响应解析
  - 图像生成循环逻辑
  - 错误路径（接口失败、返回数量不匹配）
- [x] 可能需要引入依赖 `respx` 或 `pytest-httpx`；在测试 extras 中声明。

### 4. 前端页面 & 交互
- [x] 新建页面（例如 `/marketing/bundle`）：
  - 多图上传（拖拽/点击）、提示词输入框、目标数量输入。
  - 提交按钮、加载状态、错误提示。
  - 结果展示（N 张图片 + 对应提示词）。
- [x] API 调用：使用 `fetch` 或 axios，处理 multipart/form-data。
- [x] 状态管理：可用 React hooks；必要时引入 `useTransition`/`SWR`。

### 5. 文档与开发体验
- [x] 更新 `docs/agents/README` 或新增专门文档介绍该 Agent/功能。
- [x] README 添加安装/配置步骤（Ark 凭证、环境变量）。
- [x] pre-commit/flakes：确认新依赖通过 lint/test。

## 风险与后续规划
- Ark 接口限速或耗时导致同步接口阻塞；可能需要异步任务队列或前端轮询。
- 上传图片数量大、尺寸大时的内存占用问题；可考虑限制文件大小或使用外部存储。
- 模板返回提示词质量直接影响生成效果，需要后续可调参或 A/B。

## 下一步建议
1. 确认 Ark API 鉴权、模板 ID、返回格式与使用配额。
2. 初步实现后端 Ark 客户端封装及单元测试。
3. 搭建前端页面与 UX 流程，再与产品/设计校准。
4. 集成测试整条链路，关注性能与失败兜底。

## 新增：执行详情持久化与可观测性增强

### 6. 数据结构与迁移
- [x] 设计 `agent_run_prompts`、`agent_run_images` 等表结构，记录每次 Ark 调用的提示词与生成图像详情。
- [x] 编写 Alembic 迁移脚本（在现有 `agent_runs` 基础上新增表及索引）。

### 7. 后端数据落库
- [x] 在 `MarketingCollageService` 中调用 Ark 成功后，将 prompt 与 image 详情写入新表（与 `agent_runs` 同事务）。
- [x] 扩展 `AgentRunSQLRepository` 或新增仓储，支持按 `request_id` 查询完整的 prompt/image 明细。
- [x] 新增 `GET /api/agent-runs/{request_id}` 接口返回执行详情，并补充单元/集成测试。

### 8. 前端观测面板
- [x] 在 `/agent-runs` 页面增加详情抽屉或侧滑组件，展示每条记录的提示词与图片列表。
 - [x] 支持按 prompt 关键字过滤、下载/复制等便捷操作（可逐步迭代）。

### 9. 文档更新
- [x] 更新 `README.md`、`docs/agents/README.md`、`AGENTS.md`，说明新的持久化方案、API 及前端入口。
- [x] 补充数据流示意图，说明 Ark 请求 → 数据库存储 → 前端查看的链路。

## 新增：认证、权限与对外 API

### 10. 认证与权限（Basic）
- [x] 后端引入基础认证：HTTP Basic（环境变量配置用户名/密码哈希），用于访问管理端点。
- [x] 新增 `GET /api/auth/me`，校验 Basic 并返回当前用户信息。

### 11. API Key 对外接口
- [x] 管理端新增：
  - `POST /api/admin/api-keys` 创建 API Key（返回一次性明文）。
  - `GET /api/admin/api-keys` 列表 API Key（隐藏密钥，仅展示前缀与元数据）。
- [x] 新增对外接口路由 `/api/external`，以 `X-API-Key` 鉴权：
  - `POST /api/external/marketing/collage`：与内部一致的生成功能，scope `marketing:collage`。
  - [x] 对外接口启用速率限制（全局 API Key 限流，超出 429）。
- [x] 前端管理页：`/admin/api-keys`（Basic 认证）支持创建、列表、启/停。

### 11.1 API Key 存储切换（SQL 优先）
- [x] 启用 SQL API Key Store（存在 `DATABASE_URL` 时优先使用 `api_keys` 表）。
- [x] 中间件与依赖支持 SQL/JSONL 双路径，SQL 不可用时回退 JSONL（确保兼容未迁移环境与测试）。

### 12. 审计与观测
- [x] 中间件记录审计日志（actor、路径、方法、状态码、UA、IP），默认写入 JSONL（`AUDIT_LOG_STORE_PATH`）。
- [x] 数据库落库 `audit_logs`（新增 Alembic 迁移 + 列表 API）。
- [x] 前端审计查看页：`/admin/audit-logs`（Basic 认证）。
 - [x] 审计增强：记录 `duration_ms`、`req_bytes`、`res_bytes`；列表支持 `method/status_code/path_prefix/request_id` 与 `offset` 分页；前端支持对应筛选与指标展示。

### 13. 测试与文档
- [x] 测试：
  - API Key 创建与使用外部接口成功用例；
  - 未提供/无效 Key 的拒绝用例。
- [x] 文档：README 与 Agents 文档补充认证、API Key 与审计说明（后续补充页面示例）。

## 新增：RED 自动封面 + 标题叠字（CPU）规划

### 14. 目标与范围（RED 向样式）
- [ ] 支持从视频自动抽帧选封面（清晰度/亮度/熵/字幕惩罚/人脸加分）。
- [ ] 一键导出两种比例：9:16（1080×1920）与 3:4（1080×1440）。
- [ ] 提供 3 种可选样式：
  - glass：黑色半透明圆角底板 + 白字 + 细描边 + 轻阴影。
  - gradient：红/橙系渐变长条（#FF2442 → #FF7A45）。
  - sticker：左上/右上“贴纸感”角标（如“保姆级/避坑”等）。
- [ ] 文案规范：主标题 10–18 字、副标题 10–16 字，自动换行；四周安全区 5–6%，标题区上下 3–4%。
- [ ] 开源商用字体可配置（Source Han Sans SC、Noto Sans SC、LXGW WenKai）。

### 15. 依赖与资源
- [x] 引入纯 CPU 依赖：`pillow`、`opencv-python`（后端 `pyproject.toml` 记录）。
- [ ] 字体文件落地与加载策略：`/assets/fonts` 目录 + 可配置路径；无字体时回落系统字体并告警。
- [ ] 示例视频/图片测试资源（小样本，CI 友好）。

### 16. 表结构与迁移（SQL）
- [x] `fonts`：`id`、`family`、`path`、`license`、`enabled`、`created_at`。
- [x] `cover_style_presets`：
  - 字段：`id`、`key`、`name`、`style_type`(`glass|gradient|sticker`)、
    `title_font_id`、`subtitle_font_id`、`safe_margin_pct`、`padding_pct`、
    `palette_start`、`palette_end`、`shadow`、`sticker_default_text`、`params`(JSON)、时间戳。
- [x] `cover_jobs`：
  - `id`、`request_id`、`actor_type`（admin/api_key）与标识、`title`、`subtitle`、
    `style_key/preset_id`、`sticker_text`、`video_ref`（本地/对象存储）、
    `status`（queued/running/succeeded/failed）、`duration_ms`、
    `result_9x16_url`、`result_3x4_url`、`error`、`score_meta`(JSON)。
- [x] `cover_job_scores`：`id`、`job_id`、`frame_index`、`brightness`、`laplacian_var`、`entropy`、`subtitle_penalty`、`face_area`、`score`。
- [x] Alembic 迁移脚本与索引（按 `request_id/status/created_at` 查询优化）。

### 17. 后端实现
- [x] 新建服务模块 `backend/app/services/covers.py`：
  - `pick_cover_frame`、`score_frame_for_red`、`render_cover_styles`、`make_red_covers`。
  - 支持按 `cover_style_presets` 覆盖默认参数；参数校验与回落策略。
- [ ] API：
  - [x] `POST /api/creative/covers`（内外共用）：入参 `video`、`title`、`subtitle?`、`style|preset_id|preset_key`、`sticker?`；返回两份 Base64 预览（1080×1920 与 1080×1440）。
  - [x] 管理端 `GET/POST/PATCH /api/admin/cover-presets`（Basic 认证）进行样式预设 CRUD。
  - [x] 管理端 `GET /api/admin/cover-jobs` 分页查询任务与结果。
- [ ] 鉴权与审计：
  - [x] 对外走 API Key 与速率限制（沿用现有中间件与审计日志）。
  - 统一 `X-Request-Id` 贯穿并落库 `cover_jobs.request_id`。
- [ ] CLI：`backend/bin/make_red_cover.py` 一键批量生成与本地预览；打印评分与输出路径。

### 18. 前端实现
 - [x] 新增页面 `/creative/covers`：视频上传、样式选择（glass/gradient/sticker 或 preset）、实时预览与导出。
- [x] 管理页 `/admin/cover-presets`：预设列表、创建/编辑、启停。
- [x] 管理页 `/admin/cover-jobs`：任务列表、详情（评分指标、导出链接）、按 `request_id` 链路跳转。

### 19. 同步 / 异步执行策略
- [ ] 同步：小视频（<= 60s 或帧数阈值）直接生成，接口超时保护。
- [ ] 异步：超过阈值转后台作业（FastAPI BackgroundTasks 起步；存在 `REDIS_URL` 时可切 Celery）。
- [ ] 进度与重试：任务状态轮询接口；失败可重试，支持去重（相同 `video_ref+title+style`）。

### 20. 测试计划
- [ ] 单元测试：
  - 评分函数在合成图片上的相对排序（亮度/清晰度/字幕惩罚/人脸加分）。
  - 文本换行、描边与安全区不越界的几何断言。
- [ ] 集成测试：
  - 使用短样例视频，跑通 `make_red_covers`，校验输出尺寸与返回结构。
  - API 成功/失败路径、鉴权与限流用例。
- [ ] 数据层测试：迁移正确性、`cover_jobs`/`cover_job_scores` CRUD 与查询过滤。
 - [x] API 成功路径 SQL 持久化 `cover_jobs`（通过 stub 覆盖生成、校验记录插入）。

### 21. 观测与指标
- [ ] 审计：记录 `actor/method/path/status/ip/ua/duration_ms/req_bytes/res_bytes`，与 `cover_jobs.request_id` 关联。
- [ ] 指标：成功率、平均耗时、帧评分分布；前端导出 JSON/CSV。分页展示支持 total（如数据库支持）。
- [ ] 存储：输出图片落对象存储/本地磁盘 + CDN 路径映射，记录 `size_bytes/checksum`。

### 22. 安全与合规
- [ ] 字体授权校验与声明；不带未授权商用字体进入仓库。
- [ ] 文案敏感词校验（可选开关），规避平台审核风险。
- [ ] 文件名与路径清洗，防止路径穿越/注入；大小/时长限额。

### 23. 发布与里程碑
- [ ] Phase 1（MVP）：CPU 管线 + 同步接口 + 固定默认样式；最小 E2E 自测通过。
- [ ] Phase 2：SQL 预设 CRUD + 管理页；前端创作页初版。
- [ ] Phase 3：异步任务与大视频支持；对象存储与 CDN。
- [ ] Phase 4：A/B 导出、样式自动择优；标题模板化生成（可走 CPU 关键词模板）。

### 24. Roadmap（数字人视频相关）
- [ ] 语音与字幕：ASR（faster-whisper CPU）与 TTS 接入，产出文案与节奏点。
- [ ] 数字人口播：探索 2D 驱动（口型对齐）与版式自动化，定义 `dh_jobs` 表结构。
- [ ] 与封面工作流串联：在 Orchestrator 中增加“封面 → 产出 → 发布”的可视化编排节点。
- [ ] 评测与迭代：对点击率与停留时长做 A/B 反馈闭环，优化预设参数与模板。

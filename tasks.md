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

# 营销组图功能说明

本文档详细描述 AI Xiaohongshu 项目中“小红书种草营销组图”功能的整体设计、依赖、接口及调试流程，便于后续扩展与联调。

## 功能概览

- 用户上传 1~M 张参考图片，并输入创意简报（prompt）与生成数量 `count`。
- 后端根据模板调用火山引擎 Ark：
  1. 使用 Chat Completions 生成**中文、具有场景描绘的**提示词 JSON（强调种草话术与消费动机）；
  2. 将提示词与参考图片一并传给 Ark 图像生成接口，获得最终的营销组图。
- 前端页面 `/marketing/bundle` 提供上传表单与结果展示。

## 依赖与配置

### Ark 凭证

在 `backend/.env`（或环境变量）中配置：

| 变量 | 说明 |
| --- | --- |
| `ARK_API_KEY` | 必填，Ark API Key（或使用 `ARK_AK` + `ARK_SK`） |
| `ARK_PROMPT_MODEL` | 必填，用于生成提示词 JSON 的 Ark 模型/端点 |
| `ARK_IMAGE_MODEL` | 必填，用于生成图像的 Ark 模型/端点 |
| `ARK_IMAGE_SIZE` | 可选，图像输出尺寸，默认 `1024x1024` |
| `ARK_PROMPT_TEMPLATE` | 可选，自定义系统 Prompt 模板 |
| `ARK_PROMPT_FORMAT_INSTRUCTIONS` | 可选，自定义输出格式说明 |

前端通过 `.env.local` 指定后端 API 地址：

```
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api
```

### 运行环境

```bash
# 后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend
pnpm dev # 默认会使用 3000+/3002 端口
```

## 后端接口

- 路径：`POST /api/marketing/collage`
- 请求：`multipart/form-data`
  - `prompt`：创意简报文本（中文描述，有助于生成种草画面）
  - `count`：希望生成的提示词/图片数量
  - `images`：上传的图片列表（1~M 张）
- 响应：`201 Created`
  ```json
  {
    "prompts": [
      {
        "title": "主题",
        "prompt": "英文提示词",
        "description": "中文描述",
        "hashtags": ["标签1", "标签2"]
      }
    ],
    "images": [
      {
        "prompt": { ... },
        "image_url": "https://ark...",
        "image_base64": "...",
        "size": "1024x1024"
      }
    ]
  }
  ```
- 错误处理：
  - 缺少凭证 → 500 + `Missing Ark credentials...`
  - Ark 返回不完整 → 502 + 具体提示
  - 上传文件为空 → 502 + `请至少上传一张参考图片`

## 服务结构

- `app/core/config.py`：统一管理 Ark 相关配置与模板。
- `app/services/marketing.py`：实现提示词生成与图像生成的编排逻辑。
- `app/api/routes/marketing.py`：暴露 REST API，接收表单并调用服务层。
- `app/schemas/marketing.py`：定义请求/响应的 Pydantic 模型。

## 前端交互

- 入口：`/marketing/bundle`
- 主要逻辑（`page.tsx`）：
  1. 通过 `<input type="file" multiple>` 读取图片；
  2. 使用 `FormData` 提交到后端；
  3. 处理加载、错误与结果画廊展示；
  4. 支持 `NEXT_PUBLIC_API_BASE_URL` 自定义后端地址。

## 调试建议

1. **验证后端可达**：`curl http://127.0.0.1:8000/health`。
2. **验证 Ark 调用**：用真实图片执行 `curl -F images=@file.jpg ...`，检查响应。
3. **查看日志**：`uvicorn` 控制台会输出 Ark 请求失败的异常详情。
4. **排查 CORS**：确保后端启动时绑定 `--host 0.0.0.0`，并确认响应头里存在 `Access-Control-Allow-Origin: *`。
5. **测试套件**：在 `backend` 目录执行 `pytest`，包含健康检测与服务编排的异步单元测试。

## 已知限制

- Ark 接口耗时较长时，前端当前为同步等待；可根据需求引入队列或轮询。
- 上传文件大小未做限制，建议后续在前端/后端加上大小校验与压缩策略。
- 提示词模板为默认文案，可按业务调整 `config.py` 中的模板与 placeholder。


# 本地开发运行链路与 CORS 修复测试报告

## 基本信息

- 报告日期：2026-07-14
- 测试对象：本地开发启动链路、FastAPI CORS、React/Vite 知识库页面
- 相关提交：
  - `cc80145 fix: repair local dev runtime startup and cors`
  - `05733e8 docs: record local runtime startup fix`
- 相关文件：
  - `start_dev.ps1`
  - `api/app.py`
  - `tests/api/test_app_cors.py`
  - `docs/project.md`
- 测试环境：Windows / PowerShell / 系统 Python 3.12 / Vite dev server

## 测试结论

本轮测试通过。代码层回归、非 slow 快测、脚本启动、API 健康检查、CORS 预检、Web 首页访问和知识库页面浏览器烟测均已验证通过。

本次修复后的关键效果：

1. `start_dev.ps1` 可以在 Windows PowerShell 下正常执行，并拉起 API 18080 与 Web 5173。
2. FastAPI 对本地 Vite 开发源返回正确 CORS 响应头。
3. Web 知识库页面可以加载默认 `default` 知识库，不再显示 `Network Error` / `加载失败`。
4. 空知识库时页面展示 `暂无文档`，这是预期状态；真正问答检索在无文档时仍会明确提示 `Knowledge base is empty. Please import documents first.`。

## 测试范围

| 类型 | 覆盖内容 | 结果 |
|---|---|---|
| 定向 API 回归 | CORS、Agent runtime、KB 路由、M2 多 KB | 通过 |
| 全量非 slow 快测 | 主线单元/接口测试，不含真实 PaddleOCR 慢测 | 通过 |
| 启动脚本 | `start_dev.ps1 -Stop` 与 `start_dev.ps1` | 通过 |
| API 运行时 | `GET /api/health` | 通过 |
| CORS 运行时 | `OPTIONS /api/kb` + Vite Origin | 通过 |
| 前端运行时 | `GET http://127.0.0.1:5173/` | 通过 |
| 浏览器页面烟测 | Chrome headless 打开 `/knowledge` | 通过 |

## 自动化测试记录

### 1. 定向 API 回归

命令：

```powershell
python -m pytest tests/api/test_app_cors.py tests/api/test_agent_runtime.py tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py -q
```

结果：

```text
44 passed, 2 warnings in 4.73s
```

说明：

- 新增 `tests/api/test_app_cors.py` 覆盖两个开发源：
  - `http://127.0.0.1:5173`
  - `http://localhost:5173`
- 断言 `OPTIONS /api/kb` 返回 `200`，且 `access-control-allow-origin` 精确回显请求源。
- 同时回归 Agent runtime、KB routes、M2 多知识库路径，避免 CORS 修改影响现有路由。

### 2. 全量非 slow 快测

命令：

```powershell
python -m pytest tests/ -q -m "not slow"
```

结果：

```text
88 passed, 1 deselected, 2 warnings in 5.88s
```

说明：

- `1 deselected` 是 slow marker 下的真实 PaddleOCR 慢测，本轮按快测口径排除。
- `2 warnings` 均来自 FastAPI `@app.on_event("startup")` 弃用提示，后续可迁移到 lifespan；本轮不阻断功能。

## 运行时测试记录

### 1. 一键启动脚本

命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_dev.ps1 -Stop
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_dev.ps1
```

结果：脚本返回码为 `0`。

验证点：

- 脚本可解析 UTF-8 BOM 文件中的中文注释。
- 端口清理不会因 `OwningProcess=0` 阻断。
- PATH 清理后仍保留 Node 目录，前端 `npm run dev` 可以启动。
- API 与 Web 均能监听预期端口。

### 2. API 健康检查

请求：

```text
GET http://127.0.0.1:18080/api/health
```

结果：

```text
code=0,message=ok
```

### 3. CORS 预检

请求：

```text
OPTIONS http://127.0.0.1:18080/api/kb
Origin: http://127.0.0.1:5173
Access-Control-Request-Method: GET
```

结果：

```text
status=200
Access-Control-Allow-Origin=http://127.0.0.1:5173
```

### 4. Web 首页

请求：

```text
GET http://127.0.0.1:5173/
```

结果：

```text
status=200
```

### 5. 知识库页面浏览器烟测

工具：Chrome headless。

页面：

```text
http://127.0.0.1:5173/knowledge
```

观测结果：

```text
hasKnowledgeTitle=true
hasDefaultKb=true
hasNetworkError=false
errors=[]
```

页面文本片段：

```text
知识库
ID: default
文档列表
文件上传
网页导入
删除 (0)
共 0 个文档
暂无文档
```

## 未覆盖和后续建议

1. 本轮没有执行 slow PaddleOCR 测试；该测试耗时较长，适合发布前或 OCR 专项回归时单独跑。
2. FastAPI `@app.on_event("startup")` 的弃用 warning 仍存在，建议后续单独迁移到 lifespan。
3. 当前 CORS 白名单只覆盖 Vite 本地开发源；如果后续 Electron 或打包 Web 使用不同 origin，需要补充明确的环境配置或桌面专用访问策略。

## 最终判定

本轮修复达到预期，可以认为本地开发运行链路已恢复：脚本能启动，API 能响应，浏览器跨域被允许，知识库页面能正常展示默认 KB 空列表。

# 修复本地开发运行链路启动与 CORS 问题

## 基本信息
- 类型：bug
- 日期：2026-07-14
- 相关模块：本地开发启动脚本、FastAPI 应用入口、React/Vite 知识库页面
- 相关文件：`start_dev.ps1`、`api/app.py`、`tests/api/test_app_cors.py`、`docs/project.md`

## 问题现象
前一轮 pytest 已经覆盖了多知识库和 Agent runtime 的接口逻辑，但继续做真实运行验证时发现，本地开发链路还不能稳定证明“页面可正常使用”。`start_dev.ps1` 在 Windows PowerShell 下先遇到中文注释相关的解析/编码问题；修复后又暴露端口清理尝试停止 `OwningProcess=0`、PATH 清理后找不到 `npm`/`node` 的问题。等 API 和 Web 都能启动后，浏览器打开 `http://127.0.0.1:5173/knowledge` 仍然显示加载失败，前端请求 `http://127.0.0.1:18080` 被浏览器 CORS 拦截，页面出现 `Network Error`。

## 根因分析
这次不是单一接口 bug，而是“测试通过但真实浏览器链路未打通”的组合问题：

1. `api/app.py` 只注册了业务路由和异常处理，没有注册 `CORSMiddleware`，所以 Vite 开发源 `http://127.0.0.1:5173` / `http://localhost:5173` 访问 API 时不会拿到浏览器要求的 CORS 响应头。
2. `start_dev.ps1` 是包含中文内容的 PowerShell 脚本，在当前 Windows PowerShell 环境下需要以 UTF-8 BOM 保存才能稳定解析。
3. 启动脚本为了规避 Python 3.10 / torch DLL 冲突会重写 PATH，但之前没有在清理前保存 `npm.cmd` 和 `node.exe` 的真实路径，导致后续前端启动找不到 Node 工具链。
4. 端口清理直接对 `Get-NetTCPConnection` 的 `OwningProcess` 调 `Stop-Process`，遇到 PID 0 或已失效进程时会产生不必要失败。

## 解决方案
后端侧在 `api/app.py` 中引入 `fastapi.middleware.cors.CORSMiddleware`，集中声明 `FRONTEND_DEV_ORIGINS`，只放行本地 Vite 开发源：

- `http://127.0.0.1:5173`
- `http://localhost:5173`

同时新增 `tests/api/test_app_cors.py`，用 FastAPI `TestClient` 对两个 origin 分别发起 `OPTIONS /api/kb` 预检请求，断言状态码为 `200` 且 `access-control-allow-origin` 精确回显请求源。

启动脚本侧继续保留原有“清理 Python 3.10 PATH，优先使用系统 Python 3.12”的策略，但在 PATH 清理前先解析并保存 `$NPM_CMD`、`$NODE_CMD`、`$NODE_DIR`。清理后的 PATH 额外保留 `$NODE_DIR`，前端启动改成 `Start-Process -FilePath $NPM_CMD -ArgumentList "run dev"`。端口清理逻辑增加 `OwningProcess -gt 0` 判断，并用 `-ErrorAction SilentlyContinue` 降低 stale PID 对启动链路的干扰。脚本文件保存为 UTF-8 BOM，确保 Windows PowerShell 能稳定读取中文注释。

## 为什么选这个方案
CORS 只在 FastAPI 应用入口集中配置，改动面最小，也避免每个路由分别处理跨域头。当前产品处在本地桌面/开发联调阶段，所以只放行明确的 5173 开发源，比直接 `allow_origins=["*"]` 更符合后续桌面壳和本地 API 的安全边界。

启动脚本不完全放开 PATH，而是只把真实 Node 目录补回清理后的 PATH，是为了同时满足两个约束：一方面继续规避 Python 3.10 DLL 污染 torch / onnxruntime；另一方面保证 Vite 前端能被一键脚本拉起。端口清理只跳过无效 PID，不改变“启动前清理旧端口”的既有行为，风险较低。

## 其他方案与为什么没选
- 直接在前端 Vite 里配置 proxy，把 `/api` 代理到 18080：可以绕开浏览器 CORS，但桌面/真实 API 调用路径仍然缺少后端跨域契约，不能覆盖当前 Web 直接访问 API 的真实问题。
- `allow_origins=["*"]`：实现最快，但会模糊本地 API 的访问边界；当前只需要支持 Vite 开发源，因此没有选择全放开。
- 删除 PATH 清理：能恢复 `npm`/`node`，但会回退到之前 Python 3.10 DLL 冲突风险，和已有 Windows 稳定性修复目标冲突。

## 验证与结果
已执行自动化和运行时验证：

```powershell
python -m pytest tests/api/test_app_cors.py tests/api/test_agent_runtime.py tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py -q
```

结果：`44 passed, 2 warnings in 4.73s`。

```powershell
python -m pytest tests/ -q -m "not slow"
```

结果：`88 passed, 1 deselected, 2 warnings in 5.88s`。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_dev.ps1 -Stop
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_dev.ps1
```

脚本返回码为 0。随后验证：

- `GET http://127.0.0.1:18080/api/health` 返回 `code=0,message=ok`。
- `OPTIONS http://127.0.0.1:18080/api/kb` 携带 `Origin: http://127.0.0.1:5173` 返回 `200`，`Access-Control-Allow-Origin=http://127.0.0.1:5173`。
- `GET http://127.0.0.1:5173/` 返回 `200`。
- Chrome headless 打开 `http://127.0.0.1:5173/knowledge` 后页面包含 `知识库`、`ID: default`、`暂无文档`，不包含 `Network Error` / `加载失败`，console errors 为空。

当前仍可见的 warning 是 FastAPI `@app.on_event("startup")` 弃用提示，属于后续 lifespan 迁移事项，不阻断本次运行链路。

## 面试表达版本
我在这个项目里遇到过一次“单测通过但页面不可用”的问题。接口测试都绿了以后，我继续用一键脚本和浏览器打开真实知识库页，发现启动脚本在 Windows 上有编码、PATH 和端口清理问题，而且前端访问 FastAPI 会被 CORS 拦截。我把问题拆成两层处理：后端在应用入口集中增加本地 Vite 源的 CORS 白名单并补预检测试，脚本侧则在清理 Python PATH 前保存 npm/node 路径，同时跳过无效 PID。最后我不只跑了 pytest，还验证了 API health、CORS preflight、Vite 首页和 Chrome headless 的知识库页面，确认页面显示 default 知识库且没有 Network Error。这个问题的收获是：本地桌面应用不能只看接口单测，必须覆盖从启动脚本到浏览器页面的完整链路。

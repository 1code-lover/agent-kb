# ThinkRAG Desktop 回归清单

## 目标

确保桌面版（Electron + React + Local API）在关键路径上与原 Streamlit 版本行为一致，且可持续回归。

## 覆盖范围映射

- `frontend/Document_QA.py` -> `webapp/src/pages/QueryPage.jsx`
- `frontend/KB_File.py` -> `webapp/src/pages/KbFilePage.jsx`
- `frontend/KB_Web.py` -> `webapp/src/pages/KbWebPage.jsx`
- `frontend/KB_Manage.py` -> `webapp/src/pages/KbManagePage.jsx`
- `frontend/Model_LLM.py` -> `webapp/src/pages/ModelsPage.jsx`
- `frontend/Model_Embed.py` + `frontend/Model_Rerank.py` + `frontend/Setting_Advanced.py` -> `webapp/src/pages/AdvancedPage.jsx`
- `frontend/Storage.py` -> `webapp/src/pages/StoragePage.jsx`

## 回归用例

### 1. 启动与健康检查

- [ ] 执行 `.\scripts\dev-all.ps1` 可拉起 API、Web、Desktop
- [ ] `GET /api/health` 返回 `code=0`、`data.status=ok`
- [ ] 关闭桌面窗口后无孤儿 Python 进程持续占用端口（如 18080）

### 2. Query 主链路

- [ ] 已有知识库时，输入问题后可返回答案文本
- [ ] 回答中包含来源列表（文件名/页码/文本片段）
- [ ] 空知识库时有明确错误提示，不发生前端崩溃

### 3. KB File 主链路

- [ ] 上传单文件（txt/pdf/docx）成功
- [ ] 上传多文件成功，接口返回 indexed chunk 数
- [ ] 导入后 `KB Manage` 能看到新增文档

### 4. KB Web

- [ ] 输入单 URL 可成功索引
- [ ] 输入多 URL（逐行）可批量索引
- [ ] 无法抽取正文时给出可读错误信息

### 5. KB Manage

- [ ] 文档列表可展示 name/type/path
- [ ] 勾选并删除后列表刷新
- [ ] 删除不存在文档时接口返回可追踪错误信息

### 6. Models / Settings / Advanced

- [ ] 模型候选项可加载
- [ ] 选择模型并保存后重进页面仍可读到
- [ ] `top_k/temperature/response_mode/use_reranker/top_n/system_prompt` 保存后生效

### 7. Storage

- [ ] 可看到运行环境（development/production）
- [ ] 可看到 Redis 连通状态
- [ ] 健康状态展示与 `/api/health` 一致

### 8. 构建与打包

- [ ] `cd webapp && npm run build` 通过
- [ ] `cd desktop && npm run build` 在可联网环境下通过当前平台打包
- [ ] 产物输出到 `desktop/dist`

## 建议执行顺序

1. 启动与健康检查
2. Query + KB File 主链路
3. KB Web + KB Manage
4. 模型与高级设置
5. Storage 与发布构建

## 回归记录模板

每次回归建议记录：

- 执行时间：
- 环境信息（OS / Python / Node）：
- 通过项：
- 失败项：
- 错误日志路径：
- 是否阻断发布（是/否）：

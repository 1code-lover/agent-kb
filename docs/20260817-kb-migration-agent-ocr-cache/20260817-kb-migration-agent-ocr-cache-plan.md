# 详细实施计划

## 1. 执行原则

- 严格 TDD：每个 Task 先提交失败测试，再写最小实现，再重构。
- 测试报告审核前不执行 git commit；审核通过后再按迁移、OCR、Open API、Embedding、文档验收边界组织 conventional commits。
- Python 固定使用 `/opt/miniconda3/envs/agent-kb/bin/python`。
- 保持 `llama_index==0.11.19` 和 `llama-index-core==0.11.19`。
- 新增后台任务采用依赖注入和同步核心、线程包装，避免只能通过 sleep 测试。

## 2. Task 清单

### Task 1：迁移计划扫描与摘要

**先写测试**

- 新建 `tests/api/test_kb_migration_service.py`：
  - 有效非 default 节点按 KB 分组；
  - default 节点保留；
  - 缺失、非法、未知 KB 进入 anomalies；
  - 只统计 index_struct 有效 node_id；
  - 统计 ref_doc、embedding 缺失数；
  - plan digest 稳定；
  - dry-run 前后文件树哈希一致。

**实现文件**

- 新建 `api/services/kb_migration_service.py`。
- 在 `server/utils/file.py` 增加迁移根目录安全解析函数。
- 如需要，在 `api/runtime.py` 增加移除/刷新指定 manager 的公开方法。

**命令与预期**

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_kb_migration_service.py -q
```

预期：扫描相关测试全部通过，未执行写操作。

### Task 2：迁移备份、临时重建、校验、重试和回滚

**先写测试**

- 扩展 `tests/api/test_kb_migration_service.py`：
  - 备份排除 `kbs`、`migrations`，manifest 哈希可验证；
  - 临时目录重建成功后原子进入目标；
  - 失败不暴露半成品；
  - 缺 embedding 默认阻断，显式选项才重算；
  - 目标摘要相同幂等跳过，不同则冲突；
  - 单 KB 失败后只重试失败项；
  - 回滚只隔离本批次创建目录；
  - manifest 篡改时拒绝回滚。
- 新建 `tests/api/test_kb_migration_route.py` 验证路由、409/400 和状态。
- 新建 `tests/api/test_kb_migration_integration.py`，使用 llama_index 0.11.19 的真实 SimpleVectorStore 在临时目录构造共享索引，验证持久化、重载和跨库查询不可见。

**实现文件**

- 完成 `api/services/kb_migration_service.py`。
- 新建 `api/routers/kb_migration.py`。
- 修改 `api/app.py` 注册路由。

**命令与预期**

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_kb_migration_service.py tests/api/test_kb_migration_route.py tests/api/test_kb_migration_integration.py -q
```

预期：迁移与回滚状态机、幂等和失败恢复测试全部通过。

### Task 3：迁移前端状态和操作闭环

**先写测试**

- 新建 `webapp/src/api/migration.test.js`。
- 新建 `webapp/src/domain/kbMigration.test.js`：按钮门禁、进度、冲突/异常文案、计划确认。

**实现文件**

- 新建 `webapp/src/api/migration.js`。
- 新建 `webapp/src/domain/kbMigration.js`。
- 修改 `webapp/src/pages/KnowledgePage.jsx`、`webapp/src/styles.css`。

**命令与预期**

```bash
node --test webapp/src/api/migration.test.js webapp/src/domain/kbMigration.test.js
npm run build --prefix webapp
```

预期：测试通过，Vite build 成功。

### Task 4：OCR 连续表格纯函数

**先写测试**

- 新建 `tests/readers/test_ocr_continuous_tables.py`：
  - 同页相邻块合并；
  - 普通段落硬边界；
  - 列漂移/列数不同不合并；
  - 跨页页尾/页首延续；
  - 重复表头去重；
  - 非页尾或非页首不跨页合并；
  - 诊断计数正确。

**实现文件**

- 新建 `server/readers/ocr_layout.py`。
- 修改 `server/readers/image_ocr.py` 输出结构化 blocks。
- 修改 `server/readers/pdf_ocr.py` 使用跨页合并并保留页标记。

**命令与预期**

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/readers/test_ocr_continuous_tables.py tests/readers/test_image_ocr.py tests/readers/test_pdf_ocr.py -q
```

预期：新增规则及历史 OCR 回归全部通过。

### Task 5：OCR 扫描件基准资产与评估

**先写测试**

- 新建 `tests/scripts/test_ocr_scan_benchmark.py`：manifest schema、6 类覆盖、指标、阈值失败退出码、报告确定性；校验每个资产的 `source_note`、`sha256`、`license=project-authored`。
- 新建/扩展 slow 测试验证真实 OCR runtime（缓存存在时执行）。

**实现文件**

- 新建 `tests/fixtures/ocr_real_scan/manifest.json`、小型 PNG/PDF、自制金标与固定 OCR 原始结果。
- 新建 `scripts/build_ocr_scan_benchmark.py`。
- 新建 `scripts/eval_ocr_scan_benchmark.py`。
- 报告输出到本需求 `artifacts/ocr-benchmark/`。

**命令与预期**

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_ocr_scan_benchmark.py -q
/opt/miniconda3/envs/agent-kb/bin/python scripts/eval_ocr_scan_benchmark.py --manifest tests/fixtures/ocr_real_scan/manifest.json --output docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark
```

预期：至少 6 个样本，全部指标达到 manifest 阈值并生成 JSON/Markdown。

### Task 6：只读令牌服务和管理 API/CLI

**先写测试**

- 新建 `tests/api/test_access_token_service.py`：
  - 创建只返回一次明文；
  - 存储无明文、0600、原子替换；
  - HMAC 验证使用 constant-time；
  - 过期、撤销、未知 KB；
  - last_used 更新；
  - pepper/admin key 文件权限。
- 新建 `tests/api/test_access_token_route.py`：loopback、admin key、创建/列出/撤销。
- 新建 `tests/scripts/test_manage_access_tokens.py`。

**实现文件**

- 新建 `api/services/access_token_service.py`。
- 新建 `api/routers/access_tokens.py`。
- 新建 `scripts/manage_access_tokens.py`。
- 修改 `api/app.py`。

**命令与预期**

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_access_token_service.py tests/api/test_access_token_route.py tests/scripts/test_manage_access_tokens.py -q
```

预期：令牌生命周期、管理边界和不泄密测试全部通过。

### Task 7：Open API 只读层与审计

**先写测试**

- 新建 `tests/api/test_open_api.py`：
  - Bearer 缺失/错误/过期/撤销；
  - 授权 KB 成功、越权 403、空范围拒绝；
  - KB 列表只返回授权项；
  - search/answer 固定只读范围；
  - OpenAPI 中 `/api/open/v1` 仅存在定义的路径/HTTP method；请求模型拒绝 `mode`、`tool_hint`、`command`、`path` 等额外执行字段；
  - 审计日志不含令牌、secret、完整 question。

**实现文件**

- 新建 `api/services/open_api_service.py`。
- 新建 `api/routers/open_api.py`。
- 新建 `api/services/open_api_audit.py`。
- 修改 `api/app.py`。

**命令与预期**

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_open_api.py -q
```

预期：只读授权、隔离和审计测试全部通过。

### Task 8：Embedding 空间预检、进度和取消服务

**先写测试**

- 扩展 `tests/api/test_embedding_cache_service.py`：
  - 空间不足不创建线程；
  - 边界空间计算；
  - 状态机与进度单调；
  - exact/estimated 模式；
  - 取消事件、临时清理、不触发预热；
  - cancelled/failed 后重试；
  - pre-start 并发幂等继续成立。
- 扩展 `tests/api/test_embedding_cache_route.py`：preflight、cancel、507、409。
- 新建 `tests/api/test_embedding_download_adapter.py` 验证目录采样、取消检查点、临时目录清理和完成校验；增加本地缓存存在时运行的 slow smoke。

**实现文件**

- 新建 `api/services/embedding_download_adapter.py`。
- 修改 `api/services/embedding_cache_service.py`。
- 修改 `api/routers/embedding_cache.py`。
- 修改 `scripts/prepare_embedding_model_cache.py` 支持可选回调、取消事件和受控临时目录，同时保持 CLI 兼容。

**命令与预期**

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_embedding_cache_service.py tests/api/test_embedding_cache_route.py -q
```

预期：空间、进度、取消和重试全部通过，无真实下载依赖。

### Task 9：Embedding 前端控制

**先写测试**

- 扩展 `webapp/src/api/health.test.js`。
- 扩展 `webapp/src/domain/ocrWarmup.test.js` 或新建 `embeddingDownload.test.js`：空间、estimated 文案、取消门禁、重试。

**实现文件**

- 修改 `webapp/src/api/health.js`。
- 新建 `webapp/src/domain/embeddingDownload.js`。
- 修改 `webapp/src/components/kb/KbWorkspaceHeader.jsx`、`webapp/src/pages/KnowledgePage.jsx`、`webapp/src/styles.css`。

**命令与预期**

```bash
find webapp/src -name '*.test.js' -print0 | xargs -0 node --test
npm run build --prefix webapp
```

预期：Web 全量通过、构建成功。

### Task 10：文档、测试方案、全量验收和提交

- 更新 README/README_zh/README_en、`docs/project.md` 和 API 使用说明。
- 编写并评审 `20260817-kb-migration-agent-ocr-cache-test-plan.md`。
- 执行：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"
find webapp/src -name '*.test.js' -print0 | xargs -0 node --test
npm run build --prefix webapp
(cd desktop && node --test src/*.test.js scripts/*.test.js)
git diff --check
```

- 生成覆盖率和 `20260817-kb-migration-agent-ocr-cache-test-report.md`，评审并修订。
- 调用开发故事沉淀流程，完成证据审计。
- 测试报告审核通过后，按迁移/OCR/Open API/Embedding/文档验收边界组织提交，并推送 `origin codex/desktop-agent-stage3`。

## 3. 覆盖率目标

- 新增/修改 Python 服务模块 statement coverage >= 80%。
- 新增 Web 领域/API 函数分支全部覆盖。
- 迁移、令牌和下载服务必须覆盖正常、异常、并发/幂等路径。

## 4. 完成定义

只有 RTM 每一行都有当前代码、测试输出或生成 artifact 的直接证据，且全量回归全部通过，才可标记本需求完成。

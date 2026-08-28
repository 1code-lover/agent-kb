# 历史迁移、OCR 基准、只读 Agent 与 Embedding 下载控制测试方案

## 1. 文档信息

- 需求目录：`docs/20260817-kb-migration-agent-ocr-cache/`
- 测试方案日期：2026-08-18
- 目标分支：`codex/desktop-agent-stage3`
- macOS Python：`/opt/miniconda3/envs/agent-kb/bin/python`（Python 3.12.13）
- 关键依赖：`llama-index-core==0.11.19`，以及仓库实际使用到的 LlamaIndex integration packages；runtime baseline 避免重新引入顶层 `llama_index` metapackage
- 覆盖范围：历史知识库迁移、OCR 连续表格和基准、只读 Open API 与授权令牌、Embedding 下载增强、Web/Electron 回归

## 2. 测试目标

1. 证明历史共享索引可被安全扫描、备份、重建、重载、重试和回滚，且原始索引不被改写。
2. 证明 OCR 后处理可正确识别同页和跨页连续表格，并通过离线确定性基准与真实 PaddleOCR runtime 基准。
3. 证明开放接口只允许持有效只读令牌访问授权知识库，`search` 不调用 LLM，`answer` 不记录会话，且无写路由和敏感审计泄漏。
4. 证明 Embedding 下载会先预检空间、持续报告单调进度、支持协作取消和清理，并且只有完整缓存才触发预热。
5. 证明新增/修改 Python 模块 statement coverage 不低于 80%，Web 单元测试、Vite build 和 Electron 测试无回归。

## 3. 测试边界与诚实性口径

### 3.1 常规验收范围

- Python 常规验收使用 `-m "not slow"`，不得触发真实远端模型下载。
- ModelScope 文件元数据通过依赖注入测试 exact/fallback/timeout；真实下载不是常规验收前置条件。
- OCR 离线模式消费仓库记录好的金标观测，验证评估器和质量门禁的确定性。
- OCR runtime 模式只在本机 PaddleOCR 模型缓存存在时执行，使用项目真实图片/PDF OCR 链路，不下载模型。

### 3.2 外部验收缺口

当前 manifest 中 `source_type=captured` 的三个资产是项目自制排版截图，字段 `capture_method=project_rendered_screenshot`、`physical_capture_verified=false` 已明确记录；它们不是打印后扫描件或手机/扫描仪实拍。因此：

- 可以验收代码、布局算法、合成退化、无文本层双页 PDF 和真实 PaddleOCR runtime；
- 不得把 FR-OCR-01 中“自制打印后扫描/拍摄”宣称为已满足；
- 若最终完成定义要求 FR-OCR-01 全部闭环，必须由用户/项目成员提供合法的物理扫描或拍摄资产，补充来源说明和 SHA-256 后重跑基准；
- 测试报告必须把该项列为外部资产待补，不允许用截图冒充实拍。

### 3.3 已有 runtime 证据口径

当前已生成两类 artifact：

- recorded：`docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark/`
- PaddleOCR runtime：`docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark-runtime/`

runtime 报告当前五项指标均为 `1.0`：`character_recall`、`line_order_accuracy`、`cell_recall`、`header_continuation_accuracy`、`continuous_table_merge_accuracy`。最终测试报告必须重新核验报告文件、样本成功数和命令退出码，并把结论拆成：

1. OCR 算法与本机真实 PaddleOCR runtime 是否通过；
2. FR-OCR-01 要求的物理打印扫描/手机或扫描仪实拍资产是否满足。

二者不得合并成一个含混的“全部通过”结论。

## 4. 环境与前置检查

```bash
cd /Users/zhaojianyong/python/agent-kb
git status --short
git diff --check
/opt/miniconda3/envs/agent-kb/bin/python --version
/opt/miniconda3/envs/agent-kb/bin/python - <<'PY'
import importlib.metadata
print(importlib.metadata.version("llama-index-core"))
PY
node --version
npm --version
```

预期：

- 工作目录正确，当前未提交变更均属于本需求；
- `git diff --check` 无错误；
- Python 为 3.12.x；LlamaIndex core 为 0.11.19；
- Node/npm 可执行。

## 5. 需求追踪与测试用例

### 5.1 历史知识库迁移

| 编号 | 场景 | 测试与证据 | 预期结果 |
|---|---|---|---|
| MIG-01 | 扫描节点分组、异常与 embedding 统计 | `test_scan_groups_non_default_and_reports_anomalies_and_embedding_counts` | default 保留；合法 KB 分组；未知/非法节点进入 anomalies；统计准确 |
| MIG-02 | dry-run 无副作用 | `test_dry_run_does_not_change_storage` | 扫描前后文件树哈希一致 |
| MIG-03 | 缺 embedding 门禁 | `test_missing_embedding_blocks_without_recompute` | 未显式允许重算时阻断迁移 |
| MIG-04 | 原子目标与重复执行 | `test_migration_creates_atomic_target_and_can_be_repeated` | 首次创建有效目标；重复执行标记已迁移；无半成品 |
| MIG-05 | 失败隔离与 manifest | `test_failed_kb_does_not_expose_partial_target_and_manifest_is_verifiable` | 失败 KB 不暴露目标；备份 manifest 可验证 |
| MIG-06 | 失败项重试 | `test_retry_failed_only_filters_previous_failed_kbs` | 仅重试上一批失败 KB，不重跑成功项 |
| MIG-07 | 篡改回滚拒绝 | `test_rollback_rejects_tampered_backup_manifest` | manifest/文件哈希不一致时拒绝回滚 |
| MIG-08 | 批次所有权回滚门禁 | `test_rollback_rejects_target_not_owned_by_batch` | 目标 marker 不属于批次时拒绝移动 |
| MIG-09 | 成功回滚 | `test_successful_rollback_moves_only_batch_targets_and_keeps_source_and_backup` | 仅移动本批次目标到 rollback 隔离目录；历史源和备份保持可用 |
| MIG-10 | 备份复制失败清理 | `test_backup_copy_failure_cleans_partial_backup_and_never_creates_target` | copy/write 异常时状态失败；不完整备份和目标半成品均被清理 |
| MIG-11 | 真实 LlamaIndex 持久化 | `test_real_persistence_migrates_each_kb_into_an_isolated_reloadable_index` | finance/hr 目标可真实 reload；docstore/index/vector embedding 完整；跨库不可见；历史来源不变 |
| MIG-12 | API 状态、扫描、启动、回滚和错误映射 | `tests/api/test_kb_migration_route.py` | 正常统一响应；运行冲突 409；校验错误 400 |
| MIG-13 | Web 状态和交互 | `webapp/src/api/migration.test.js`、`webapp/src/domain/kbMigration.test.js`、Vite build | 能展示扫描、迁移、失败、重试和回滚状态 |

专项命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_kb_migration_service.py \
  tests/api/test_kb_migration_route.py \
  tests/api/test_kb_migration_integration.py -q
```

### 5.2 OCR 连续表格和基准

| 编号 | 场景 | 测试与证据 | 预期结果 |
|---|---|---|---|
| OCR-01 | 资产类别、来源和哈希 | `test_benchmark_manifest_has_six_project_authored_assets` | 至少 6 个；覆盖段落、双栏、单页/跨页表格、段落边界、倾斜、低对比、噪声；license/source_note/hash 完整 |
| OCR-02 | 生成资产稳定性 | `test_benchmark_assets_are_byte_stable_across_rebuilds` | 两次构建每个资产 SHA-256 一致 |
| OCR-03 | 跨页金标落在 PDF | `test_cross_page_gold_is_attached_to_a_pdf_asset` | 表头延续和连续合并金标绑定无文本层多页 PDF |
| OCR-04 | 离线评估指标 | `test_evaluator_reports_required_metrics_deterministically` | 字符、行序、单元格、表头、连续合并五项指标稳定且范围合法 |
| OCR-05 | 阈值门禁 | `test_threshold_failure_returns_nonzero` | 低于阈值时 CLI 返回非零 |
| OCR-06 | runtime 模式不复用固定结果 | `test_runtime_mode_uses_ocr_executor_instead_of_recorded_observations` | 显式调用 OCR executor，报告 `mode=runtime` |
| OCR-07 | JSON/Markdown 报告 | `test_cli_accepts_named_manifest_and_writes_json_and_markdown` | `--manifest` 可用；输出 `report.json` 和 `report.md` |
| OCR-08 | 同页连续表格 | `test_adjacent_same_page_table_blocks_are_merged` | 结构兼容的相邻块合并 |
| OCR-09 | 段落硬边界 | `test_paragraph_is_a_hard_boundary` | 不跨普通段落合并表格 |
| OCR-10 | 列漂移/列数异常 | `test_column_count_or_center_drift_prevents_merge` | 不兼容块保持分离 |
| OCR-11 | 跨页连接范围 | `test_only_previous_tail_and_next_head_continue_across_pages` | 只连接上一页末块和下一页首块 |
| OCR-12 | 重复表头去重 | `test_repeated_header_is_removed_on_page_continuation` | 保留 `[Page N]`，第二页重复表头移除，诊断计数准确 |
| OCR-13 | 真实 PaddleOCR runtime | `test_real_paddleocr_runtime_benchmark_passes_when_cache_exists` 和 runtime artifact | 模型缓存存在时 9 个样本均 success，总分 >= 0.8，跨页 continued/header 计数为 1 |

离线命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/readers/test_ocr_continuous_tables.py \
  tests/scripts/test_ocr_scan_benchmark.py -q -m "not slow"

/opt/miniconda3/envs/agent-kb/bin/python scripts/eval_ocr_scan_benchmark.py \
  --manifest tests/fixtures/ocr_real_scan/manifest.json \
  --mode recorded \
  --output docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark \
  --min-score 0.8
```

真实 runtime 命令（本地缓存存在时）：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/scripts/test_ocr_scan_benchmark.py -q -m slow

/opt/miniconda3/envs/agent-kb/bin/python scripts/eval_ocr_scan_benchmark.py \
  --manifest tests/fixtures/ocr_real_scan/manifest.json \
  --mode runtime \
  --output docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark-runtime \
  --min-score 0.8
```

若模型目录 `~/.paddlex/official_models/PP-OCRv6_medium_det` 或 `PP-OCRv6_medium_rec` 缺失，slow 测试必须明确 skip；不得在线下载后再把下载过程算作常规回归。

### 5.3 只读 Open API 与知识库授权令牌

| 编号 | 场景 | 测试与证据 | 预期结果 |
|---|---|---|---|
| OPEN-01 | 创建仅返回一次明文 | `test_create_returns_plaintext_once_and_store_contains_only_hash` | API/CLI 创建时返回明文一次；落盘仅 HMAC hash，无 secret |
| OPEN-02 | 文件权限和稳定管理密钥 | `test_admin_key_is_stable_and_private` | token store/pepper/admin key 权限为 0600；密钥稳定 |
| OPEN-03 | scope、过期、撤销 | `test_verify_enforces_scope_expiry_and_revocation` | 未授权、过期、撤销令牌均拒绝 |
| OPEN-04 | KB 有效性 | `test_create_rejects_unknown_or_inactive_kb` | 未知或 inactive KB 不得授权 |
| OPEN-05 | 时间格式 | service/route invalid expiry tests | 非 ISO 8601 输入稳定映射 400 |
| OPEN-06 | loopback 管理边界 | `tests/api/test_access_token_route.py` | 非回环地址、缺失/错误 admin key 拒绝 |
| OPEN-07 | 管理 API 生命周期 | `test_management_api_create_list_revoke_and_open_api_rejects_revoked_token` | loopback + admin key 下 create/list/revoke 成功；列表不泄露 token/hash；撤销后 `/me` 立即 401 |
| OPEN-08 | CLI 生命周期 | `tests/scripts/test_manage_access_tokens.py` | create/list/revoke 可用；不在 list 中泄露明文 |
| OPEN-09 | Bearer 鉴权和 KB 越权 | `test_open_api_requires_bearer_and_enforces_kb_scope` | 缺失/错误 token 为 401；越权为 403；授权访问成功 |
| OPEN-10 | 请求字段白名单 | `test_open_request_models_reject_execution_fields` | mode/tool_hint/command/path 等额外执行字段 422 |
| OPEN-11 | 路由/方法白名单 | `test_open_api_schema_contains_only_readonly_paths_and_methods` | `/api/open/v1` 只含 me、knowledge-bases、search、answer；无写操作 |
| OPEN-12 | 审计无泄漏 | `test_audit_file_omits_token_secret_and_question_body` | JSONL 只含白名单字段，不含完整 token、secret、question |
| OPEN-13 | search/answer 分离 | router/service structured search tests | `/search` 使用结构化 retriever，不调用生成式 executor；`/answer` 复用只读问答 |
| OPEN-14 | 物理索引隔离 | `test_open_api_reads_only_the_authorized_physical_kb` | finance token 只能加载 finance manager，回答不出现 HR 内容；越权在查询前拒绝 |

专项命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_access_token_service.py \
  tests/api/test_access_token_route.py \
  tests/api/test_open_api.py \
  tests/api/test_open_api_service.py \
  tests/api/test_open_api_integration.py \
  tests/scripts/test_manage_access_tokens.py -q
```

### 5.4 Embedding 下载进度、空间预检和取消

| 编号 | 场景 | 测试与证据 | 预期结果 |
|---|---|---|---|
| EMB-01 | exact 元数据 | ModelScope metadata sum test | 汇总远端文件 `Size`，`progress_mode=exact` |
| EMB-02 | metadata 超时回退 | metadata timeout test | 3 秒内回退保守值，不阻塞预检 |
| EMB-03 | 空间充足/不足/边界 | adapter/service preflight tests | `free >= required + reserve` 才可启动；不足不创建线程 |
| EMB-04 | HTTP 507 | route insufficient space test | 空间不足映射 507，响应含空间诊断 |
| EMB-05 | 单调进度 | `test_progress_is_monotonic_and_never_reaches_100_before_verification` | 字节和百分比不回退，验证完成前 < 100% |
| EMB-06 | 当前文件和目录采样 | adapter prepare sampling test | 回调含当前文件、实际落盘字节、阶段 |
| EMB-07 | 协作取消和 partial 清理 | adapter/service cancel tests | Event 被检查；临时目录删除；旧完整缓存不删除；不触发预热 |
| EMB-08 | 取消/失败后重试 | service retry tests | `cancelled`/`failed` 可重新开始并最终 ready |
| EMB-09 | 并发幂等 | duplicate start/race tests | 同一时刻最多一个下载任务；重复请求不创建线程 |
| EMB-10 | 预热门禁 | success/failure/cancel tests | 仅完成校验后 reset runtime 并触发 warmup |
| EMB-11 | API 状态与冲突 | route status/preflight/prepare/cancel/409 tests | 状态机字段完整，取消幂等，冲突映射 409 |
| EMB-12 | Web 展示 | `health.test.js`、`embeddingDownload.test.js`、Vite build | 展示 exact/estimated、空间、阶段、当前文件、取消和重试 |

专项命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_embedding_download_adapter.py \
  tests/api/test_embedding_cache_service.py \
  tests/api/test_embedding_cache_route.py -q
```

## 6. 覆盖率方案

覆盖率命令同时采集核心服务、路由、OCR reader 和 CLI/基准脚本，防止新增模块被静默遗漏：

```bash
COVERAGE_FILE=/tmp/agent-kb-acceptance.coverage \
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_kb_migration_service.py \
  tests/api/test_kb_migration_route.py \
  tests/api/test_kb_migration_integration.py \
  tests/api/test_access_token_service.py \
  tests/api/test_access_token_route.py \
  tests/api/test_open_api.py \
  tests/api/test_open_api_service.py \
  tests/api/test_open_api_integration.py \
  tests/api/test_embedding_download_adapter.py \
  tests/api/test_embedding_cache_service.py \
  tests/api/test_embedding_cache_route.py \
  tests/readers/test_ocr_continuous_tables.py \
  tests/readers/test_image_ocr.py \
  tests/readers/test_pdf_ocr.py \
  tests/scripts/test_manage_access_tokens.py \
  tests/scripts/test_prepare_embedding_model_cache.py \
  tests/scripts/test_ocr_scan_benchmark.py \
  --cov=api.services.kb_migration_service \
  --cov=api.routers.kb_migration \
  --cov=api.services.access_token_service \
  --cov=api.routers.access_tokens \
  --cov=api.services.open_api_service \
  --cov=api.services.open_api_audit \
  --cov=api.routers.open_api \
  --cov=api.services.embedding_cache_service \
  --cov=api.services.embedding_download_adapter \
  --cov=api.routers.embedding_cache \
  --cov=server.readers.ocr_layout \
  --cov=server.readers.image_ocr \
  --cov=server.readers.pdf_ocr \
  --cov=scripts.build_ocr_scan_benchmark \
  --cov=scripts.eval_ocr_scan_benchmark \
  --cov=scripts.manage_access_tokens \
  --cov=scripts.prepare_embedding_model_cache \
  --cov-report=term-missing \
  -q -m "not slow"
```

验收口径：

- 迁移、授权、Open API、Embedding、OCR 布局与评估器等核心逻辑模块，各自 statement coverage 必须 `>= 80%`；
- routers 和 CLI/基准构建脚本也必须出现在 coverage 表中，并由对应路由/CLI/资产稳定性行为测试提供直接证据；
- 对纯参数转发、`if __name__ == "__main__"`、真实网络下载入口等非核心 I/O 薄层，若单模块低于 80%，测试报告必须逐一给出覆盖率、未覆盖行、直接行为测试以及不纳入核心门禁的理由，不能静默遗漏；
- 聚合 coverage 达标不能掩盖核心模块低于 80%。

## 7. 全量回归命令

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"

find webapp/src -name '*.test.js' -print0 | xargs -0 node --test

npm run build --prefix webapp

(cd desktop && node --test src/*.test.js scripts/*.test.js)

git diff --check
```

记录项：

- 每条命令的开始/结束时间、退出码、通过/失败/跳过数；
- 所有 warning 的分类，区分已知依赖 warning 与新增 warning；
- 若失败，记录失败用例、根因、修复提交前工作树差异和重跑结果；
- 不得仅重跑失败用例后宣称全量通过，修复后必须重新执行对应专项和全量命令。

## 8. 失败注入与异常路径

- 迁移：缺 embedding、目标冲突、写入异常、manifest 篡改、marker 所有权不匹配。
- Open API：缺 token、错误 token、过期、撤销、越权、非法额外字段、Embedding 未就绪、空知识库。
- Embedding：远端 metadata 失败/超时、空间不足、下载异常、取消竞态、重复启动、验证失败。
- OCR：列数漂移、列中心漂移、段落硬边界、跨页非首尾块、重复表头、runtime 依赖缺失。

## 9. 验收门禁

以下条件必须同时成立才能把测试报告评审为通过：

1. Python 非 slow 全量、Web 单测、Vite build、Electron 测试和 `git diff --check` 全部退出码 0。
2. 四组专项测试全部通过。
3. 核心新增/修改 Python 模块各自 coverage >= 80%。
4. 离线 OCR 报告生成成功且总分 >= 0.8。
5. 本机 OCR 模型缓存存在时，真实 runtime 报告生成成功且总分 >= 0.8；缓存不存在时必须记录 skip 原因。
6. RTM 每一行都有测试输出、代码位置或 artifact 直接证据。
7. FR-OCR-01 的物理扫描/拍摄资产在未提供前明确标为“外部资产待补”，不得误标完成。
8. 测试报告完成评审并按 `评审建议.txt` 修订之前，不执行 git commit/push。

## 10. 测试报告输出

输出文件：

`docs/20260817-kb-migration-agent-ocr-cache/20260817-kb-migration-agent-ocr-cache-test-report.md`

至少包含：

- 环境与版本；
- 专项和全量命令、退出码、通过率、跳过项；
- 单模块覆盖率；
- OCR recorded/runtime artifact 路径和指标；
- RTM 逐行证据；
- 失败、修复、复测记录；
- 未执行的 slow/网络测试及原因；
- FR-OCR-01 物理扫描资产缺口和最终判定；
- 是否允许进入开发故事、commit 和 push 阶段。

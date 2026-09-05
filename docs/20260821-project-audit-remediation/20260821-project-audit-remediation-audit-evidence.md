# 20260821 Project Audit Remediation Audit Evidence

## 1. 文档用途

这份材料用于承接 `issues-summary.md` 里不适合继续堆在主正文中的**审计证据附录 / 历史增量记录**。

它的职责是：

- 保存 refusal / Docker / startup alias / composite answers 等补充更新；
- 保存 release / package boundary 这类更像“证据说明”的内容；
- 给继续整改的人提供历史增量上下文。

它**不替代**：

- `20260821-project-audit-remediation-issues-summary.md` 的总表角色；
- `20260821-project-audit-remediation-interview-brief.md` 的口播主稿角色；
- `20260821-project-audit-remediation-report-script.md` 的 5 分钟汇报底稿角色。

建议阅读顺序：

1. 先看 `20260821-project-audit-remediation-issues-summary.md`；
2. 再看 `20260821-project-audit-remediation-status-matrix.md` / `20260821-project-audit-remediation-test-report.md`；
3. 只有在需要历史增量或补充证据时，再看本文。

## 2. 补充更新与审计证据

> 下列内容保留为历史增量记录与补充证据，不建议替代 `issues-summary.md` 直接拿去做口播或 5 分钟汇报。

> 下面这些“补充更新”更适合作为审计证据附录和历史增量记录，不建议替代前面的总表部分直接拿去做口播。

## 补充更新（2026-08-22 refusal contract gate）

- layered eval fixture schema 现已在 `required_refusal_categories` 之外，再补 `required_refusal_markers_by_category`。
- 当前拒答集不只校验“题型存在”，还校验 category 内是否覆盖了 `No confirmable information`、`knowledge base`、`must not fabricate` 这类关键 wording。
- 对外讲“为什么不是单纯刷 1.0”时，可以补这句：**现在 refusal harness 已开始约束 subtype 和 contract wording，而不是只看 pass_rate 或 refusal 总数。**
## 补充更新（2026-08-22 directory backlog sizing + docker eval smoke）

### 新增验证

- `python -m pytest tests/scripts/test_cleanup_local_artifacts.py -q` → `13 passed`
- `python -m pytest tests/scripts/test_repo_hygiene_contracts.py tests/scripts/test_docs_entry_contracts.py -q` → `11 passed`
- `python -m pytest tests/scripts/test_docker_smoke.py -q` → `9 passed`
- `python scripts/cleanup_local_artifacts.py --dry-run --include-directories` → `managed_count = 0`

### 新增结论

1. 根目录目录级 backlog 现在已经能输出更适合治理排序的数据：`total_size_bytes`、`size_bytes_by_category`、`largest_records`。
2. 最新 dry-run 表明：
   - 根目录目录合计约 `1159774` bytes；
   - `scratch_eval_dir = 12`，合计约 `1132776` bytes；
   - `scratch_debug_dir = 2`，合计约 `26998` bytes；
   - 当前未再看到 `scratch_temp_dir` backlog；
3. 当前最大的 5 个目录已经可直接作为人工复核优先队列：`tmp_eval_out`、`tmp_eval_out5`、`tmp_eval_debug_codex3`、`tmp_eval_debug_codex5`、`tmp_eval_out8`。
4. `scripts/docker_smoke.py` 的 helper 契约已经更准确：`eval` 模式等待容器退出码，不再误用 `/api/health`；但 live Docker build 进一步证明，真正拖慢 smoke 的主因正在收敛到 `torch` GPU transitive chain，而不是 helper 逻辑本身。
5. 当前 live build 日志已确认下载的超大依赖包括：`torch-2.13.0 (526.6 MB)`、`nvidia_cudnn_cu13 (366.2 MB)`、`nvidia_cusparselt_cu13 (170.1 MB)`、`nvidia_nccl_cu13 (206.0 MB)`、`triton-3.7.1 (197.7 MB)`、`nvidia_cublas (423.1 MB)`、`nvidia_cufft (214.1 MB)`。
6. 所以现在更准确的工程判断是：**Docker helper 已经收口，但 requirements runtime/eval baseline 仍偏重，下一步要继续评估 CPU-only / lighter embedding 安装口径，而不是再把问题归咎到 smoke helper 误判。**

### 更新后的优先级理解

- P0 里的 Docker 项已经从“修 helper”进入“压重依赖 / 补完整 smoke 证据”的阶段。
- 根目录治理项已经具备按体积和类别排序的抓手，可以先针对 `scratch_eval_dir` 与 top 5 offender 做第一批受控归档计划。

## 补充更新（2026-08-22 docker smoke lighter profile + startup retry fix）

### 新增验证

- `python -m pytest tests/scripts/test_docker_smoke.py -q` → `13 passed`
- `python -m pytest tests/test_requirements_profiles.py -q` → `9 passed`
- `python -m pip install --dry-run --ignore-installed --report temp/smoke-profile-report.json -r requirements-smoke.txt`
- 解析 dry-run 报告：`flagged=[]`，未再出现 `torch / sentence-transformers / nvidia / triton`
- `python scripts/docker_smoke.py --tag agent-kb-smoke:local --install-profile smoke --app-runtime-mode api` → 成功返回 `/api/health` JSON

### 新增结论

1. Docker 方向这轮真正落地了一个 **smoke 专用安装口径**：`requirements-smoke.txt`。
2. 它不是拍脑袋减包，而是严格保持 runtime baseline 大体一致，只去掉 `llama-index-embeddings-huggingface` 这一条会把 `sentence-transformers -> torch` 拉进来的重链；对应 contract test 也已经补齐。
3. live Docker smoke 过程中还额外暴露了两个真实兼容性问题，并已修复：
   - Windows 仓库 checkout 的 `docker-entrypoint.sh` 行尾问题会让 Linux 容器报 `no such file or directory`；
   - `/api/health` 在刚起进程时可能瞬时 `RemoteDisconnected`，原 helper 会过早失败。
4. 修完后，`python scripts/docker_smoke.py --tag agent-kb-smoke:local --install-profile smoke --app-runtime-mode api` 已经可以完整走通 build + run + healthcheck。
5. 所以当前最准确的话术应更新为：**Docker helper 与 Docker smoke profile 已经形成可执行闭环，但 runtime/eval 正式依赖口径仍比 smoke profile 更重，后续优化目标不应混淆。**

### 更新后的优先级理解

- P0 的 Docker 项不再只是“继续讨论 lighter profile”，而是可以拆成两段：
  1. 保持 `smoke` profile 作为 health / entrypoint / import smoke 的稳定轻量口径；
  2. 继续单独评估 runtime / eval baseline 是否需要 CPU-only 或更细颗粒的延迟依赖策略。
- root scratch 目录 backlog 的排序能力仍然有效，但截至最新 dry-run，file-mode / directory-mode 均已回到 `managed_count = 0`；这轮主要突破点已经转到 Docker 真实可执行收口与 cleanup 的长期防回脏机制。

## 补充更新（2026-08-22 API entry env alias symmetry）

### 新增验证

- `python -m pytest tests/test_run_api.py tests/scripts/test_dev_startup_contracts.py -q` → `18 passed`

### 新增结论

1. `run_api.py` 现在不再只对 host 兼容历史别名，而是对 port 也执行同样的优先级策略：`KB_*` 优先，legacy alias 兜底。
2. 这让 API-only 入口与 `start_dev.ps1` / `scripts/dev-all.ps1` / `desktop/src/runtime-config.js` 的端口契约更加一致。
3. 因此启动链路这条问题线可以更诚实地讲成：**主入口收口已经进入“收边角差异”的阶段，而不是还停留在“大方向完全混乱”的阶段。**


## 补充更新（2026-08-24 composite answers modularization）

### 新增验证

- `python -m pytest tests/api/test_chat_composite_answers.py tests/api/test_chat_postprocessors.py tests/api/test_chat_service.py -q` → `98 passed`
- `python -m pytest tests/api/test_chat_question_intents.py tests/api/test_chat_targeted_fact.py tests/api/test_chat_source_answers.py tests/api/test_chat_answer_repair.py -q` → `49 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_builders.py tests/test_rag_quality_fixtures.py -q` → `16 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q` → `12 passed`
- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `41 passed`

### 新增结论

1. Prompt / heuristic 方向这轮不是只继续“讲计划”，而是已经把 multi-fact merge / summary bundle 真正从 `chat_service.py` 下沉到 `api/services/chat_composite_answers.py`。
2. 现在可以更准确地对外表述为：
   - `chat_source_answers.py` 负责 source projection
   - `chat_answer_repair.py` 负责 answer repair
   - `chat_composite_answers.py` 负责 composite answers
3. `chat_service.py` 已进一步压到 `1166` 行，这说明当前重构不是横向堆新文件，而是持续把 orchestration 与纯函数 heuristic 分层。
4. 该方向的下一主要瓶颈已经收敛到 targeted-fact orchestration，以及 hook builder 逐渐分散的维护成本；后续重点不再是继续停留在 multi-fact / summary 这两个块上。
5. 结合 2026-08-25 的 v7 smoke refresh，现在更准确的话术应更新为：不仅主链路 suite 继续全绿，refusal / negative contract 也已经形成 smoke + main + hard 三层 contract 约束，其中 v7 smoke 层也显式补回了 negative contract gate。

## 补充更新（2026-08-25 contract gate 联动修复）

### 新增验证

- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `41 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_builders.py tests/test_rag_quality_fixtures.py -q` → `16 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q` → `12 passed`

### 新增结论

1. `chat_eval_runner` 不再只是把 refusal / negative contract 作为报告展示项，而是新增统一 `contract_gates`，并直接联动到最终 `run_passed`。
2. 这意味着单题 case 即便全部通过，只要 required refusal marker 或 required negative contract categories 仍存在缺口，整次运行也会被显式判为失败。
3. `_build_eval_suite_layer_summary(...)` 现在也能输出 `failed_contract_gates`，因此 layered suite markdown / semireal markdown 已可直接解释为什么某层 `run_passed = false`。
4. 对外讲“为什么不是简单刷 1.0”时，现在可以更诚实地补一句：逐题通过不等于最终评测通过，因为 refusal / boundary contract 覆盖本身就是硬门槛。

## Desktop build/package/release four-layer boundary

- `scripts/build-desktop.ps1/.sh` = local desktop build helper only.
- `npm run build:mac` + `npm run verify:package` = ad-hoc package verification; it only proves packaged runtime contents are ready.
- `npm run release:preflight` = strict Apple preflight; it only validates local Apple prerequisites, not a finished release.
- `npm run release:mac` + `npm run verify:mac-release` = formal signed/notarized distribution lane.

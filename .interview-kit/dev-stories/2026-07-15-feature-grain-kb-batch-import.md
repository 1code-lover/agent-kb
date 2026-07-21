# 粮仓知识库分批导入工具

## 基本信息

- 类型：feature
- 日期：2026-07-15
- 相关模块：粮仓知识库导入、脚本化运维、测试指南
- 相关文件：
  - `scripts/import_grain_kb_batches.py`
  - `tests/scripts/test_import_grain_kb_batches.py`
  - `docs/20260715-grain-kb-evaluation/20260715-grain-kb-evaluation-test-guide.md`
  - `docs/project.md`
  - `docs/guide/DOCS_INDEX.md`

## 需求背景

粮仓资料已经按 `data/grain-knowledge-base/docs/01-*` 到 `docs/07-*` 规范化整理，但知识库 registry 中 `grain-knowledge-base` 仍不是全量向量化状态。用户需要一个可控导入策略：先小批量验证阿里百炼配置、嵌入链路和问答效果，再逐步导入主资料，避免一次性导入 126 个主资料后难以定位失败文件、重复副本污染或 PDF/OCR 耗时问题。

## 设计与实现方案

新增 `scripts/import_grain_kb_batches.py` 作为标准库实现的批量导入工具。脚本默认 dry-run，只扫描当前 `data/grain-knowledge-base/docs/` 目录生成导入计划和 JSON 报告；只有显式传入 `--apply` 时才调用 `POST /api/kb/file/import`。扫描策略默认只包含 `01-*` 到 `07-*` 主资料目录，跳过 `98-duplicates-to-review`、`99-other` 和各目录 `README.md`，并支持按分类、扩展名、数量上限和 batch size 控制导入范围。

脚本把导入过程拆成 `discover_files()`、`build_batches()`、`build_plan()`、`_build_multipart_body()`、`post_batch()`、`run_import()`、`write_report()` 等函数，方便单测覆盖。真实 apply 时每个批次会上传 `kb_id`、`chunk_size`、`chunk_overlap` 和多个 `files` 字段；执行结果会落到 `data/grain-knowledge-base/qa/grain-kb-import-report-<timestamp>.json`，便于后续比对失败原因和导入范围。

同步更新测试指南，明确推荐流程是先 dry-run，再 DOCX smoke，再分类导入 DOCX，最后处理 PDF；并提醒不要依赖历史 `qa/import-manifest.json`。项目总览和文档索引也同步标记该脚本已可用。

## 为什么选这个方案

这个方案优先保证可回滚、可观察和低风险。相比直接在 UI 中一次性多选上传，脚本 dry-run 能提前暴露真实文件清单，JSON 报告能固定每一批导入证据；相比立即做复杂的后台导入队列，当前标准库脚本成本更低，不引入额外依赖，也能直接复用现有 FastAPI 导入接口。先 DOCX 后 PDF 的顺序，是为了先排除模型配置、kb_id 隔离和基础 chunk 入库问题，再处理更容易受 OCR、扫描质量和耗时影响的 PDF。

## 其他方案与为什么没选

- 直接 UI 全量上传：操作最快，但一旦出现 500、OCR 超时或问答召回异常，很难知道是哪一类资料、哪一批文件造成的。
- 后端新增正式异步导入任务：长期更完整，但当前目标是先让粮仓知识库进入可测试状态；新建任务系统会扩大开发范围。
- 依赖旧 `data/grain-knowledge-base/qa/import-manifest.json`：该文件可能与当前目录整理结果不一致，不能作为真实导入依据。

## 风险与权衡

脚本仍然通过已有同步接口上传文件，所以大批量 PDF 导入时仍可能遇到超时或 OCR 耗时问题；控制方式是把 PDF batch size 降到 2，并按分类逐步 apply。另一个风险是重复导入会导致索引中出现重复节点；因此文档中要求 apply 前先 dry-run，失败后保留报告，不建议盲目全量重跑。脚本默认跳过 `98` 和 `99`，这会牺牲部分资料覆盖率，但能先保证主资料质量和召回可解释性。

## 验证与结果

已执行验证：

```powershell
python -m pytest tests/scripts/test_import_grain_kb_batches.py -q
# 结果：9 passed in 0.49s / 0.57s

python -m py_compile scripts/import_grain_kb_batches.py tests/scripts/test_import_grain_kb_batches.py
# 结果：通过

git diff --check
# 结果：通过

python scripts/import_grain_kb_batches.py --limit 5 --batch-size 2
# 结果：dry-run 生成 5 个文件、3 个批次的计划报告

python scripts/import_grain_kb_batches.py --extension docx --limit 5 --batch-size 5
# 结果：dry-run 生成 5 个 DOCX、1 个批次的计划报告
```

同时复核本地 API：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:18080/api/health' -TimeoutSec 5
Invoke-RestMethod -Uri 'http://127.0.0.1:18080/api/kb' -TimeoutSec 10
Invoke-RestMethod -Uri 'http://127.0.0.1:18080/api/kb/list?kb_id=grain-knowledge-base' -TimeoutSec 10
```

结果显示 API health 正常，`grain-knowledge-base` 为 active、`doc_count=14`，但文档列表仍为空；本轮没有执行真实 `--apply` 导入，等待用户确认后再做 smoke apply。

## 面试表达版本

我当时面对的是一个已经整理好目录、但还没有全量向量化的行业知识库。为了避免一次性导入后难以定位失败，我做了一个默认 dry-run 的批量导入工具，把文件扫描、分批计划、multipart 上传和 JSON 报告都拆成可测试函数。导入策略上我选择先 DOCX smoke，再分类导入 DOCX，最后处理 PDF，因为 PDF 更容易受 OCR 和超时影响。这个方案没有引入新依赖，直接复用现有 FastAPI 导入接口，但通过报告和 batch 控制把风险降下来了。最后我补了 9 个脚本单测、语法检查、dry-run 验证和文档指南，确保用户能按步骤安全导入。


## 追加记录：2026-07-15 Grain KB 运行时烟测修复

### 触发背景

脚本化导入完成后，真实中文 HTTP 问答 smoke 暴露了两类问题：一是 LlamaIndex 在索引加载和模型读取时可能回退到默认 OpenAI 配置；二是历史 smoke/手动导入留下的陈旧向量 id 会让 `VectorIndexRetriever` 抛 `KeyError`，并且非 default 查询曾混入 `default` 来源。

### 关键改动

- `api/runtime.py`：避免读取 `Settings.llm` 触发默认 OpenAI 解析；索引加载前预热 embedding。
- `server/index.py`：兼容非字符串 `metadata["file_path"]`，避免历史 metadata 破坏导入。
- `server/retriever.py`：新增 `SafeVectorIndexRetriever`，跳过向量库残留但索引结构缺失的 stale id。
- `server/kb_filter.py` / `server/engine.py`：收紧 KB 隔离，无 `kb_id` 节点只归 `default`，并把 `kb_ids` 传入融合检索器做返回层兜底过滤。
- `tests/api/test_runtime_model_loading.py`、`tests/api/test_retriever_stale_vectors.py`、`tests/api/test_m2_multi_kb.py` 等补充回归。

### 验证结果

```powershell
python -m pytest tests/api/test_runtime_model_loading.py tests/api/test_index_manager_coverage.py tests/api/test_m2_multi_kb.py tests/api/test_retriever_stale_vectors.py tests/scripts/test_import_grain_kb_batches.py -q
# 61 passed, 2 warnings

python -m py_compile api/runtime.py server/index.py server/retriever.py server/kb_filter.py server/engine.py scripts/import_grain_kb_batches.py tests/api/test_runtime_model_loading.py tests/api/test_index_manager_coverage.py tests/api/test_m2_multi_kb.py tests/api/test_retriever_stale_vectors.py tests/scripts/test_import_grain_kb_batches.py
# 通过

git diff --check
# 退出码 0；仅 LF/CRLF 提示
```

HTTP smoke 报告：`C:\Users\ethan1.zhao\Downloads\agent-kb-main\github-agent-kb\data\grain-knowledge-base\qa\grain-kb-query-smoke-20260715T092120Z.json`。Q1-Q4 领域问答通过，Q5 实时价格越界问题未编造答案；最终 sources 均限定在 `grain-knowledge-base`。

### 权衡

`SafeVectorIndexRetriever` 只在查询时跳过陈旧向量 id，不直接改写持久化向量库；这样风险最低，不会误删历史索引数据。长期仍建议在全量导入完成后设计一次可审计的索引重建/清理流程。

## 追加记录：2026-07-15 导入功能独立 smoke

### 触发背景

粮仓知识库已经做过小批量 apply smoke，但继续在正式 `grain-knowledge-base` 上重复测试会制造重复文档和重复向量。因此本轮改用临时知识库验证导入功能本身，把“导入链路是否可用”和“粮仓资料质量评测”拆开。

### 验证链路

- 创建临时 KB：`import-smoke-20260715-192353`。
- 上传测试文件：`northagent-import-smoke_ecebbba8.txt`。
- 校验接口返回：`indexed_chunks=1`，文件带有正确 `kb_id`。
- 校验物理落盘：`C:\\Users\\ethan1.zhao\\Downloads\\agent-kb-main\\github-agent-kb\\data\\import-smoke-20260715-192353\\northagent-import-smoke_ecebbba8.txt`。
- 校验列表隔离：测试 KB 能列出该文件，`default` 不出现该文件。
- 校验问答：测试 KB 对“导入功能烟测代号是什么？”回答“蓝麦”。
- 校验负向隔离：同一问题限定 `grain-knowledge-base` 时不回答“蓝麦”，来源仍限定在粮仓 KB。

### 验证结果

报告文件：`C:\\Users\\ethan1.zhao\\Downloads\\agent-kb-main\\github-agent-kb\\data\\grain-knowledge-base\\qa\\import-function-smoke-20260715-192353.json`。

这次验证说明导入功能的最小闭环已经可用：KB 登记、文件保存、索引写入、列表查询、问答召回和 KB 隔离都能跑通。临时 KB 暂时保留，便于用户继续用前端做 UI 验收；后续清理应走文档删除和空 KB 删除链路，而不是手动删目录。

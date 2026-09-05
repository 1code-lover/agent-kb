# 粮仓知识库导入、嵌入与问答测试指南

- 主题：Grain Knowledge Base / 粮仓知识库
- 日期：2026-07-15
- 适用知识库：`grain-knowledge-base`
- 本地资料目录：`data/grain-knowledge-base/`
- 主资料范围：`data/grain-knowledge-base/docs/01-*` 至 `docs/07-*`
- 默认跳过：`data/grain-knowledge-base/docs/98-duplicates-to-review/`

## 1. 测试分工

### 1.1 Codex 先做的自动化测试

Codex 负责先跑不依赖人工判断的检查：

1. 资料目录完整性：文件数、分类数、SHA256 去重状态。
2. QA 数据结构：`qa/verified.jsonl`、`qa/draft.jsonl` 是否为合法 JSONL，证据路径是否存在。
3. API 基线：`GET /api/health`、`GET /api/kb`、`GET /api/kb/list?kb_id=grain-knowledge-base`。
4. 已有报告复核：检索报告、问答报告是否能说明当前状态。
5. 文档同步：把测试结论和下一步风险同步到 `docs/project.md`。

### 1.2 用户需要协助的人工验收

用户主要负责真实环境和主观质量验收：

1. 确认百炼/阿里云模型配置是否已经在 UI 或配置项中生效。
2. 在浏览器知识库页面发起导入，观察进度、失败提示和最终文档列表。
3. 用业务问题抽测问答质量，判断答案是否符合实际业务语境。
4. 标注不满意答案，补充到 `data/grain-knowledge-base/qa/draft.jsonl` 或后续 verified 集。

## 2. 当前基线状态

截至 2026-07-15，本地检查结果：

| 项目 | 当前结果 |
|---|---:|
| 资料文件总数 | 255 |
| PDF | 157 |
| DOCX | 98 |
| 主资料文件数 | 126 |
| 主资料唯一 SHA256 数 | 126 |
| 重复/隔离副本数 | 129 |
| 主资料重复 SHA 组 | 0 |
| verified QA | 24 条 |
| draft QA | 20 条 |
| API health | 正常 |
| registry 中 `grain-knowledge-base` | active，`doc_count=25`（含 smoke/手动重复导入副本，非全量 126 主资料） |
| `GET /api/kb/list?kb_id=grain-knowledge-base` | 当前非空；已能列出 smoke 导入和历史手动导入文档 |

结论：资料目录和 QA 骨架已准备好，DOCX 小批量导入、HTTP 问答和多知识库隔离已通过 smoke；但向量索引仍不是全量导入状态，下一步应按分类补齐主资料导入或重建索引，再做正式问答验收。

## 3. 导入前检查

### 3.1 启动服务

```powershell
cd C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb
.\start_dev.ps1
```

确认 API：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:18080/api/health' -TimeoutSec 5
```

期望：

```json
{"code":0,"message":"ok","data":{"status":"ok"}}
```

### 3.2 确认知识库存在

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:18080/api/kb' -TimeoutSec 10
```

期望：列表中有：

```text
kb_id = grain-knowledge-base
status = active
```

### 3.3 确认资料范围

优先导入这些目录：

```text
data/grain-knowledge-base/docs/01-standards-regulations/
data/grain-knowledge-base/docs/02-storage-operations/
data/grain-knowledge-base/docs/03-monitoring-analysis/
data/grain-knowledge-base/docs/04-regulation-platform/
data/grain-knowledge-base/docs/05-patents/
data/grain-knowledge-base/docs/06-research-reports/
data/grain-knowledge-base/docs/07-templates-samples/
```

暂不导入：

```text
data/grain-knowledge-base/docs/98-duplicates-to-review/
data/grain-knowledge-base/docs/99-other/
```

原因：`98` 是重复副本，会影响 chunk 排序；`99` 还需人工确认主题。

## 4. 导入测试步骤

### 4.1 小批量 smoke 导入

先不要一次性导入 126 个主资料，建议先选 5-10 个高价值文档：

```text
data/grain-knowledge-base/docs/01-standards-regulations/AAA粮油安全储存守则.docx
data/grain-knowledge-base/docs/01-standards-regulations/中央储备粮管理条例.docx
data/grain-knowledge-base/docs/01-standards-regulations/粮库安全生产守则.docx
data/grain-knowledge-base/docs/02-storage-operations/01磷化氢膜下环流熏蒸技术规程T1.docx
data/grain-knowledge-base/docs/04-regulation-platform/中储粮非直属企业“一卡通”出入库系统应用管理办法（暂行）.docx
```

在 UI 中选择知识库 `grain-knowledge-base` 后上传。

通过标准：

1. 上传不报 400/404/500。
2. 文件落盘路径仍在 `data/grain-knowledge-base/` 内。
3. 文档列表能看到对应文件。
4. `GET /api/kb` 中 `doc_count` 增加。
5. 不应污染 `default` 知识库。

### 4.2 主资料全量导入

小批量成功后，再导入 `docs/01-*` 到 `docs/07-*`。

通过标准：

1. 导入完成后文档列表能看到主资料。
2. `doc_count` 与成功导入文件数一致或有清晰失败报告。
3. 失败文件有明确错误原因，例如 OCR 超时、格式解析失败、模型调用失败。
4. 不导入 `98-duplicates-to-review`。

### 4.3 脚本化导入策略

为避免 UI 手动多选出错，本轮新增脚本：

```text
scripts/import_grain_kb_batches.py
```

脚本默认是 dry-run，只生成导入计划和 JSON 报告；只有显式加 `--apply` 才会调用 `POST /api/kb/file/import`。报告默认写入：

```text
data/grain-knowledge-base/qa/grain-kb-import-report-<timestamp>.json
```

推荐顺序：

1. 先 dry-run 查看清单，不调用 API。
2. 先导入 DOCX smoke，不急着导 PDF。
3. 每次 apply 后检查文档列表和问答效果。
4. smoke 通过后再按分类导入主资料。

常用命令：

```powershell
cd C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb

# 只看前 5 个文件计划，不调用 API
python scripts/import_grain_kb_batches.py --limit 5 --batch-size 5

# 推荐首轮：只看前 5 个 DOCX，降低 PDF/OCR 干扰
python scripts/import_grain_kb_batches.py --extension docx --limit 5 --batch-size 5

# 真实导入前 5 个 DOCX；失败即停止
python scripts/import_grain_kb_batches.py --extension docx --limit 5 --batch-size 5 --apply --stop-on-error

# 只导入标准法规分类的 DOCX
python scripts/import_grain_kb_batches.py --category 01-standards-regulations --extension docx --batch-size 5 --apply --stop-on-error

# 分类 smoke 通过后，再导入主资料全部 DOCX
python scripts/import_grain_kb_batches.py --extension docx --batch-size 5 --apply --stop-on-error

# 最后再导入 PDF；如果 OCR 慢，可按分类逐个导入
python scripts/import_grain_kb_batches.py --extension pdf --category 01-standards-regulations --batch-size 2 --apply --stop-on-error
```

注意事项：

- 不加 `--apply` 不会真实导入，适合先复核文件清单。
- 默认只扫描 `docs/01-*` 至 `docs/07-*`，跳过 `98-duplicates-to-review`、`99-other` 和各目录 `README.md`。
- 不建议直接使用历史 `data/grain-knowledge-base/qa/import-manifest.json` 作为导入依据；以当前目录扫描和脚本生成的新报告为准。
- 如果 apply 失败，先保存对应 `grain-kb-import-report-*.json`，不要立刻全量重跑，避免重复导入难以排查。

## 5. 嵌入检索质量测试

### 5.1 指标口径

| 指标 | 含义 | 建议门禁 |
|---|---|---:|
| Recall@5 | verified 用例相关文档进入 top 5 | >= 0.80 |
| MRR@5 | 相关文档排名倒数均值 | >= 0.50 |
| Top1 hit rate | 相关文档排名第 1 的比例 | 先记录基线，不强制 |
| KB isolation | 非目标 KB 不返回粮仓资料 | 100% |

### 5.2 测试集

当前已有：

```text
data/grain-knowledge-base/qa/verified.jsonl  # 24 条
data/grain-knowledge-base/qa/draft.jsonl     # 20 条
```

`verified.jsonl` 用于正式 smoke；`draft.jsonl` 用于后续扩充。

### 5.3 推荐测试问题

优先抽测：

1. 《粮油安全储存守则》制定的安全储粮方针是什么？
2. 《中央储备粮管理条例》中中央储备粮的定义是什么？
3. 粮食入仓前，仓储管理部门需要检查哪些仓房条件？
4. 《粮库安全生产守则》遵循什么安全生产方针？
5. 中储粮非直属企业“一卡通”出入库系统应用管理办法适用于什么业务场景？
6. 如果用户问实时粮食市场价格，粮仓知识库应如何处理？

通过标准：

1. top 5 证据文件包含 expected/relevant 文档。
2. 标准、条例、守则类问题优先命中原始制度文档，而不是 README 或模板文件。
3. 实时价格类问题应拒答或提醒超出知识库边界。

## 6. 问答质量人工验收

### 6.1 评分维度

每个问题按 0-2 分打分：

| 维度 | 0 分 | 1 分 | 2 分 |
|---|---|---|---|
| 准确性 | 错误或编造 | 大体正确但有遗漏 | 准确且无明显编造 |
| 证据引用 | 无证据或证据错 | 证据相关但不精确 | 引用正确文件和内容 |
| 完整性 | 答非所问 | 回答部分要点 | 覆盖主要要点 |
| 边界控制 | 越权回答 | 有提醒但不清晰 | 明确拒答/提示边界 |

建议通过线：

- 准确性平均分 >= 1.6
- 证据引用平均分 >= 1.6
- answerable=false 的拒答准确率 >= 90%

### 6.2 人工记录模板

```text
问题 ID：
问题：
答案是否可接受：是/否
准确性：0/1/2
证据引用：0/1/2
完整性：0/1/2
边界控制：0/1/2
问题说明：
建议修复：补资料 / 调 chunk / 开 reranker / 改 prompt / 改 UI / 其他
```

## 7. 常见失败与处理

| 现象 | 可能原因 | 处理建议 |
|---|---|---|
| 文档列表为空但 doc_count 不为 0 | registry 计数和当前索引/列表状态不一致 | 先重建索引或重新导入，并记录导入报告 |
| Recall@5 低 | 未导入目标文档、chunk 不合适、OCR 质量差 | 检查导入清单、调 chunk、对扫描 PDF 做 OCR |
| Top1 命中低但 Recall@5 高 | embedding 召回可用但排序弱 | 开启 reranker 或换更强 embedding 做 A/B |
| 答案编造实时价格 | prompt 边界不强或 README 未参与检索 | 加强拒答提示，补充边界用例 |
| default KB 命中粮仓资料 | kb_id metadata 或过滤失效 | 检查 query/list/delete 隔离链路 |

## 8. 本轮建议结论

建议先由 Codex 完成自动化预检和 smoke 记录；用户再按本指南做 UI 导入和问答人工验收。正式通过前，不建议把当前 `grain-knowledge-base` 视为“全量可用知识库”。



## 9. 2026-07-15 最新 smoke 执行记录

### 9.1 执行环境

- 仓库路径：`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb`
- API smoke 端口：`http://127.0.0.1:18082`
- 使用知识库：`grain-knowledge-base`
- 本轮模型配置：本地 BGE embedding + 已配置的百炼兼容 LLM（未在文档中记录或暴露密钥）
- 依赖状态：当前环境已具备 `llama-index-core==0.14.23`、`llama-index-llms-langchain==0.8.0`、`langchain==0.3.30`、`langchain-openai==0.3.35`、`langchain-community==0.3.31`。

### 9.2 导入 smoke 结果

已执行脚本化 DOCX 小批量导入：

```powershell
python scripts/import_grain_kb_batches.py --api-base-url http://127.0.0.1:18082 --extension docx --limit 5 --batch-size 5 --apply --stop-on-error
```

结果：

- 导入接口返回成功；
- 报告文件：`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\data\grain-knowledge-base\qa\grain-kb-import-report-20260715T084356Z.json`；
- 本批次成功导入 5 个 DOCX，`indexed_chunks=120`；
- `GET /api/kb` 显示 `grain-knowledge-base.doc_count=25`；
- `GET /api/kb/list?kb_id=default` 返回空 docs，未污染 default；
- 注意：本轮 smoke 前曾做过服务层直接导入，当前 `doc_count=25` 中包含若干重复副本。不要手动删除这些文件；如需清理，应先走安全删除和索引重建方案。

### 9.3 运行时问题与修复

本轮 smoke 暴露并修复了 4 类运行时问题：

1. `api/runtime.py`：`ensure_models_ready()` 改为读取 `Settings._llm` 私有缓存，避免访问 `Settings.llm` 时触发 LlamaIndex 默认 OpenAI LLM 解析。
2. `api/runtime.py`：`ensure_index_loaded()` 加载索引前先 `ensure_models_ready(require_llm=False)`，避免读取已持久化索引时触发默认 OpenAI embedding。
3. `server/index.py`：`load_files()` 对非字符串/非 pathlike 的 `metadata["file_path"]` 做安全解析，避免历史 metadata 为 dict/list 时 `Path()` 报错。
4. `server/retriever.py` / `server/kb_filter.py` / `server/engine.py`：增加 `SafeVectorIndexRetriever`，跳过向量库中存在但 `index_struct.nodes_dict` 缺失的陈旧向量 id；同时收紧 KB 过滤规则，无 `kb_id` 旧节点只归 `default`，非 default 查询不得混入 default 或旧节点。

### 9.4 HTTP 问答 smoke 结果

最终 smoke 报告：`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\data\grain-knowledge-base\qa\grain-kb-query-smoke-20260715T092120Z.json`。

| 编号 | 问题 | 结果 | 主要证据 |
|---|---|---|---|
| Q1 | 《粮油安全储存守则》制定的安全储粮方针是什么？ | 通过，回答“预防为主、综合防治” | `AAA粮油安全储存守则.docx` |
| Q2 | 《中央储备粮管理条例》中中央储备粮的定义是什么？ | 通过，回答中央政府储备用于调节供求、稳定市场和应对突发事件的粮食及食用油 | `中央储备粮管理条例.docx` |
| Q3 | 《粮库安全生产守则》遵循什么安全生产方针？ | 通过，回答“安全第一、预防为主、综合治理” | `粮库安全生产守则.docx` |
| Q4 | 政府储备粮食仓储管理办法主要规范什么内容？ | 通过，回答政府储备粮食仓储环节的数量、质量、安全和规范管理 | `政府储备粮食仓储管理办法.docx` |
| Q5 | 今天玉米现货价格是多少？ | 通过，回答上下文没有实时价格信息 | 粮仓知识库中只召回储粮资料，未编造实时价格 |

隔离检查：最终 5 个问题返回的 `sources[*].kb_id` 均为 `grain-knowledge-base`，没有混入 `default`。

质量观察：

- Q1-Q4 的事实答案准确，且首位证据基本命中目标文档。
- Q4 仍出现同库内 0 分或弱相关来源，说明融合召回在过滤后可能补位不足；正式评测时建议加入 reranker 或提高导入覆盖后重新评估。
- Q5 能拒答实时价格，说明 Prompt 能基于上下文边界约束回答，但仍会召回含“玉米”的储粮资料；这是可接受的越界问题表现。

### 9.5 本轮验证命令

```powershell
python -m pytest tests/api/test_runtime_model_loading.py tests/api/test_index_manager_coverage.py tests/api/test_m2_multi_kb.py tests/api/test_retriever_stale_vectors.py tests/scripts/test_import_grain_kb_batches.py -q
# 61 passed, 2 warnings

python -m py_compile api/runtime.py server/index.py server/retriever.py server/kb_filter.py server/engine.py scripts/import_grain_kb_batches.py tests/api/test_runtime_model_loading.py tests/api/test_index_manager_coverage.py tests/api/test_m2_multi_kb.py tests/api/test_retriever_stale_vectors.py tests/scripts/test_import_grain_kb_batches.py
# 通过

git diff --check
# 退出码 0；仅有 LF/CRLF 提示，无空白错误
```

### 9.6 用户下一步建议

1. 先用浏览器在 `http://127.0.0.1:5173/models` 确认百炼模型配置仍可用。
2. 用 `--limit 10` 到 `--limit 20` 按分类扩大 DOCX 导入范围，不建议直接全量 PDF。
3. 每批导入后固定抽测 Q1-Q5，并把不满意问题补充到 `data\grain-knowledge-base\qa\draft.jsonl`。
4. DOCX 主资料稳定后，再以 `--extension pdf --batch-size 2` 逐步导入 PDF，并重点记录 OCR/解析失败。
5. 全量主资料导入完成后，再生成正式检索/问答评测报告；当前 smoke 只能证明链路可用，不能代表最终知识库质量。

### 9.7 导入功能独立 smoke 结果

为避免继续向正式粮仓知识库重复写入测试副本，本轮另建临时知识库验证“创建 KB -> 文件导入 -> data/{kb_id}/ 落盘 -> 文档列表 -> 问答召回 -> 跨 KB 隔离”完整链路。

- 临时知识库：`import-smoke-20260715-192353`
- 测试文件：`northagent-import-smoke_ecebbba8.txt`
- 导入后落盘路径：`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\data\import-smoke-20260715-192353\northagent-import-smoke_ecebbba8.txt`
- 报告文件：`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\data\grain-knowledge-base\qa\import-function-smoke-20260715-192353.json`

验证结果：

| 检查项 | 结果 |
|---|---|
| 创建临时 KB | 通过，registry 可见且初始 `doc_count=0` |
| 调用 `POST /api/kb/file/import` | 通过，返回 `indexed_chunks=1` |
| 物理目录落盘 | 通过，文件写入 `data/import-smoke-20260715-192353/` |
| 按 KB 列表查询 | 通过，`GET /api/kb/list?kb_id=import-smoke-20260715-192353` 只返回该测试文件 |
| default 隔离 | 通过，`GET /api/kb/list?kb_id=default` 返回空 docs |
| 测试 KB 问答 | 通过，问题“导入功能烟测代号是什么？”回答“蓝麦”，来源 `kb_id=import-smoke-20260715-192353` |
| 粮仓 KB 负向隔离 | 通过，同一问题在 `grain-knowledge-base` 下未回答“蓝麦”，来源仍限定在粮仓 KB |

当前临时 KB 和测试文件保留，用于用户在前端页面继续做 UI 验收；如后续需要清理，应先通过文档删除/空 KB 删除链路处理，不建议直接手动删除文件。


## 10. 2026-07-16 用户人工验收问题记录

### Issue-01：上传前未强制确认目标知识库

- 发现时间：2026-07-16
- 发现阶段：用户在 `/knowledge` 页面执行文件导入人工验收
- 严重级别：P1
- 当前状态：代码修复、自动化测试与浏览器 smoke 已通过；真实文件上传等待用户复验

修复结果：

1. 页面初始不再选择 `default`，默认知识库也必须由用户显式选择。
2. 左侧展示后端真实知识库列表，并保留新建、重命名和删除入口。
3. 未选择 active KB 时，文档列表、文件上传和网页导入均不可执行。
4. 选择后，页面明确显示知识库名称、`kb_id` 和 `data/{kb_id}/` 目标目录。
5. 新建 active KB 后自动选中；删除当前 KB 后清空选择，不回退到 `default`。
6. 文件上传、网页导入、文档列表和删除 API 缺少 `kb_id` 时立即失败。
7. 修复统一响应体二次解包问题，知识库列表可正确显示 4 个真实 KB。

验证结果：

- Node 回归：16/16 通过。
- 本轮纯规则覆盖率：行、分支、函数均 100%，高于 80% 门禁。
- Vite 构建：通过。
- 后端 KB 定向回归：29/29 通过。
- 浏览器 smoke：初始未选择、粮仓库 14 个文档隔离、文件/网页目标提示和控制台检查全部通过。
- 详细报告：`docs/20260716-kb-upload-target-selection/20260716-kb-upload-target-selection-test-report.md`。

用户复验步骤：

1. 打开 `http://127.0.0.1:5173/knowledge`，确认初始标题是“请选择知识库”。
2. 点击“新建知识库”，创建专用空库，例如 `upload-target-smoke-20260716`，确认创建后自动选中。
3. 打开“文件上传”，确认目标卡片显示新库名称、`kb_id` 和 `data/upload-target-smoke-20260716/`。
4. 上传一个不含敏感信息的小型 TXT 或 Markdown 文件。
5. 返回文档列表，确认文件只出现在新库；再检查 `default` 与 `grain-knowledge-base` 没有出现该文件。
6. 如需清理，先删除测试文档，再删除已经为空的测试知识库。

## 9.1 2026-07-17 粮仓 QA 集扩充到 50+ 组（原文因编码问题字节级丢失，待补充完整描述）

以下为从残留片段可辨认的要点，非完整原文：

- 粮仓 QA 集扩充为 `verified=30`、`draft=26`，共 `56` 组。
- 新增分组说明文档：`data/grain-knowledge-base/qa/question-groups.md`。
- `verified` 集覆盖的主题涉及若干标准/规范类问题（具体分类描述已丢失，待补）。
- `draft` 集涉及 `03-monitoring-analysis`、`05-patents` 等主题（具体描述已丢失，待补）。
- 涉及 `question-groups.md` 中 A 组 12 个 smoke 问题与 verified 集的关系（具体结论已丢失，待补）。

> 待办：如能找到本节原始记录（例如聊天记录、其他备份），请补齐完整中文描述后删除本提示。



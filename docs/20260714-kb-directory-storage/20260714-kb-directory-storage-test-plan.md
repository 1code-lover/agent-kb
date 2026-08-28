# 多知识库目录化存储测试方案

日期：2026-07-14
阶段：阶段 4 测试方案，待评审通过后进入阶段 5 正式测试执行与测试报告生成。

---

## 1. 测试目标

验证本阶段“多知识库逻辑隔离 + 原始文件物理分目录 + 共享向量索引”的实现是否满足 PRD、FRD、RTM 与实施计划要求：

1. 文件导入前必须先校验 `kb_id` 已登记且处于 active 状态。
2. 原始文件只能落盘到 `data/{kb_id}/`，不得继续平铺到 `data/` 根目录。
3. `IndexManager.load_files()` 只接收服务层传入的明确 `file_paths`，不再二次拼接全局保存目录。
4. 文档列表和删除按 `kb_id` 严格隔离；旧无 `kb_id` 节点只归 `default`。
5. 删除知识库必须阻止非空 KB，空 KB 删除 registry 与空目录并处理一致性错误。
6. registry 写入具备原子替换、同一临界区 read-modify-write、`doc_count` 下限和并发更新保护。
7. 迁移脚本只迁移原始文件，具备 dry-run、备份、SHA256 校验、verify 与 rollback 能力。
8. QA fixture 仅做 schema 与防污染校验，不把 fixture 数据导入真实 `data/`。
9. 现有多知识库、Agent 检索、API 路由和集成测试不回归。

---

## 2. 测试范围

### 2.1 本阶段范围内

| 类别 | 覆盖点 | 代表文件 |
|---|---|---|
| 路径工具 | `kb_id` 规则、保留名、路径边界、KB 目录解析 | `tests/utils/test_file_kb_paths.py` |
| 导入链路 | 创建 KB、导入前校验、目录落盘、索引失败清理、计数更新、URL/web import 的未登记/非 active/成功计数 | `tests/api/test_kb_directory_storage.py`、`tests/api/test_kb_routes.py` |
| 索引入口 | `load_files(file_paths, ...)` 使用明确路径并写入 metadata | `tests/api/test_kb_directory_storage.py` |
| 文档隔离 | list/delete 的 default legacy 归属、非 default 严格隔离、安全删源文件 | `tests/api/test_kb_docs_isolation.py` |
| registry | 原子写入、并发计数、计数下限、不存在 KB 错误 | `tests/api/test_kb_registry.py`、`tests/api/test_kb_registry_atomic.py` |
| 迁移脚本 | dry-run、apply、manifest、verify、rollback、根目录直属文件范围 | `tests/scripts/test_migrate_kb_directory_storage.py` |
| QA fixture | draft/verified schema、ID 唯一、防止 fixture 被当作知识库数据 | `tests/test_rag_quality_fixtures.py` |
| 回归 | KB 路由、多 KB 查询、Agent KB scope、integration | `tests/api/`、`tests/integration/` |

### 2.2 本阶段不验收

1. 不验收多向量索引物理隔离；`storage/` 仍是共享索引。
2. 不验收迁移后旧索引 metadata/query 自动一致；迁移脚本只移动原始文件，索引一致性需重导或重建索引后单独验收。
3. 不验收正式嵌入质量分数；本阶段只建立 QA fixture 的结构约束与防污染校验。
4. 不默认执行真实 PaddleOCR 慢测；慢测保留单独命令和人工确认口径。

---

## 3. 测试环境

| 项 | 值 |
|---|---|
| OS | Windows，本仓库当前开发机 |
| Python | 系统 Python 3.12 |
| 工作目录 | `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb` |
| 后端框架 | FastAPI |
| RAG 核心 | LlamaIndex |
| 默认快测策略 | `pytest -m "not slow"` 排除真实 PaddleOCR 慢测 |
| 覆盖率工具 | 优先使用 `pytest-cov`；若本机未安装，需先安装或使用等价 `coverage run/report` 命令，并在测试报告中记录工具版本 |
| 覆盖率门禁 | 本阶段正式测试要求目录化存储改动相关 Python 文件总行覆盖率 >= 80%，低于 80% 视为阶段 5 阻断失败 |

测试中涉及文件落盘、registry 和迁移脚本的用例必须使用 `tmp_path` 或测试 fixture 隔离，不能写入用户真实 `data/` 内容。覆盖率统计范围覆盖本次目录化存储相关 Python 文件：`api/routers/kb.py`、`api/services/kb_service.py`、`server/index.py`、`server/kb_registry.py`、`server/kb_errors.py`、`server/utils/file.py`、`scripts/migrate_kb_directory_storage.py`、`scripts/validate_rag_quality_fixtures.py`；排除真实用户 `data/`、`storage/`、前端构建产物和测试 fixture 数据。

---

## 4. 测试用例设计

### TC-01：`kb_id` 与路径安全

- 输入：合法 ID `default`、`manual-kb`、`kb-20260714`。
- 输入：非法 ID `_bad`、`Bad`、`bad_1`、`-bad`、`bad-`、`a..b`、`CON`、`LPT1`、路径穿越片段。
- 预期：合法 ID 返回规范字符串并可解析到 `data/{kb_id}/`；非法 ID 抛 `KBValidationError`；路径边界校验不能被字符串前缀绕过。
- 命令：`python -m pytest tests/utils/test_file_kb_paths.py -q`

### TC-02：创建 KB 同步创建目录

- 步骤：创建非默认 KB。
- 预期：registry 中出现 active KB，`data/{kb_id}/` 创建成功；重复创建返回业务冲突；目录创建失败时 registry 回滚或抛 `KBConsistencyError`。
- 命令：`python -m pytest tests/api/test_kb_directory_storage.py -q`

### TC-03：导入前校验 KB，防止孤儿文件

- 步骤：向未登记 KB 或非 active KB 上传文件。
- 预期：在任何文件落盘前失败；`data/{kb_id}/` 下无新文件；HTTP 层稳定映射为：未登记 KB 返回 404，非法 `kb_id` 参数返回 400，非 active KB 返回 400。该口径覆盖旧 PRD 中“未知或非法返回 400”的早期表述，以本测试方案和当前异常类型映射为准。
- 命令：`python -m pytest tests/api/test_kb_directory_storage.py -q`

### TC-04：文件目录落盘与索引 metadata

- 步骤：向已登记 KB 上传文件，并模拟索引成功。
- 预期：文件路径位于 `data/{kb_id}/`；节点 metadata 包含 `kb_id`、`file_name`、`file_path`；`doc_count` 在索引成功后增加。
- 命令：`python -m pytest tests/api/test_kb_directory_storage.py -q`

### TC-05：索引失败清理与计数不变

- 步骤：模拟 `IndexManager.load_files()` 抛错。
- 预期：本次落盘文件被清理；registry `doc_count` 不增加；接口返回明确错误。
- 命令：`python -m pytest tests/api/test_kb_directory_storage.py -q`

### TC-06：URL/web import 的 KB 校验与计数

- 步骤：通过服务层 `import_urls()` 和路由层 `POST /api/kb/web/import` 分别覆盖未登记 KB、非 active KB、合法 KB 成功导入三类路径。
- 预期：未登记 KB 返回 404；非法 `kb_id` 参数返回 400；非 active KB 返回 400；合法 KB 成功后调用索引加载并增加对应 registry `doc_count`；请求中的 `kb_id` 必须透传到服务层，不得回退到 `default`。
- 命令：`python -m pytest tests/api/test_kb_directory_storage.py tests/api/test_kb_routes.py -q`

### TC-07：文档列表严格隔离

- 步骤：构造 `default`、非 default 和旧无 `kb_id` 节点。
- 预期：非 default 只返回 metadata 精确匹配节点；旧无 `kb_id` 节点只在 `default` 中可见。
- 命令：`python -m pytest tests/api/test_kb_docs_isolation.py -q`

### TC-08：文档删除严格隔离与源文件安全删除

- 步骤：分别删除 default、非 default、旧根目录直属文件、其他 KB 子目录文件、URL 节点。
- 预期：非 default 不能删除旧无标签节点或其他 KB 文件；default 可删除迁移前 `data/foo.pdf` 直属文件；default 不删除 `data/manual/foo.pdf`；URL 节点不触发本地文件删除。
- 命令：`python -m pytest tests/api/test_kb_docs_isolation.py -q`

### TC-09：删除知识库的非空检查和一致性处理

- 步骤：删除 default、删除不存在 KB、删除 `doc_count > 0` KB、删除 docstore 有文档 KB、删除目录非空 KB、删除空 KB。
- 预期：default 与非空删除为 409；不存在为 404；空 KB 删除 registry 与空目录；一致性/补偿失败固定映射 500。
- 命令：`python -m pytest tests/api/test_kb_directory_storage.py tests/api/test_kb_routes.py -q`

### TC-10：registry 原子写入与并发更新

- 步骤：并发 `add_doc_count()`，模拟写入时读取，设置负计数。
- 预期：JSON 文件始终可读；read-modify-write 不丢更新；`doc_count` 不为负；不存在 KB 更新抛稳定异常。
- 命令：`python -m pytest tests/api/test_kb_registry.py tests/api/test_kb_registry_atomic.py -q`

### TC-11：迁移脚本 dry-run/apply/verify/rollback

- 步骤：在临时 `data/` 中放置根目录直属旧文件和已目录化文件，执行 dry-run、apply、verify、rollback。
- 预期：dry-run 不改文件系统；apply 只移动根目录直属旧文件到 `data/default/`；生成备份和 manifest；SHA256 一致；rollback 可恢复；脚本声明不修改索引。
- 命令：`python -m pytest tests/scripts/test_migrate_kb_directory_storage.py -q`

### TC-12：QA fixture schema 与防污染

- 步骤：校验 draft/verified fixture，构造重复 ID、缺证据、fixture 路径指向 `data/` 或自身目录等负例。
- 预期：draft 与 verified 字段约束清晰；verified 必须绑定 `kb_id/file_name/evidence`；fixture 不位于 `data/`，不会被导入知识库。
- 命令：`python -m pytest tests/test_rag_quality_fixtures.py -q`

### TC-13：回归测试

- 步骤：运行 API、integration、scripts、utils 与 QA fixture 扩展回归。
- 预期：本阶段修改不破坏 KB CRUD、Agent KB scope、web import、多 KB 查询和集成测试。
- 命令：`python -m pytest tests/api tests/integration tests/scripts tests/utils tests/test_rag_quality_fixtures.py -q`

### TC-14：默认全量快测

- 步骤：运行排除真实 PaddleOCR 慢测的测试集。
- 预期：非 slow 测试全部通过；FastAPI `on_event` 弃用警告允许记录为非阻断。
- 命令：`python -m pytest tests -q -m "not slow"`

### TC-15：真实 OCR 慢测单独执行

- 步骤：在确认本机 PaddleOCR 依赖和测试 PDF 可用后执行 slow 测试。
- 预期：扫描件 OCR 结果召回关键术语。该项耗时明显高于默认测试，不作为本阶段目录化存储的阻断门禁。
- 命令：`python -m pytest tests/readers/test_pdf_ocr.py -q -m slow -s`

---

## 5. 正式执行命令清单

评审通过后，阶段 5 按以下顺序执行并生成测试报告。前几条命令用于按模块快速定位失败，最后的非 slow 全量测试与覆盖率命令作为正式门禁；如果定位命令和全量命令覆盖范围有重复，重复是为了提高失败定位效率，不代表可以跳过最终门禁。

### 5.1 依赖和上下文确认

正式测试报告必须记录以下上下文：当前分支、当前 commit、Python 版本、pytest/coverage 工具版本、测试隔离策略，以及是否执行真实 OCR 慢测。

```powershell
git branch --show-current
git rev-parse --short HEAD
python --version
python -m pytest --version
python -m coverage --version
```

若 `python -m coverage --version` 不可用，或 `python -m pytest --help` 中没有 `--cov` 参数，应先按项目依赖管理方式安装 `coverage` 与 `pytest-cov`，再进入正式测试；否则测试报告不得标记为通过。当前开发机预跑环境尚未安装 `coverage`，所以阶段 5 正式执行前必须先补齐该工具依赖。

### 5.2 文档和格式门禁

```powershell
git diff --check
$checkPaths = @(
  'docs/20260714-kb-directory-storage/*.md',
  'docs/project.md',
  'docs/guide/DOCS_INDEX.md',
  'docs/spec/knowledge_base_visibility_and_multi_kb_design.md',
  '评审建议.txt',
  'requirements-dev.txt',
  'api/routers/kb.py',
  'api/services/kb_service.py',
  'server/index.py',
  'server/kb_registry.py',
  'server/kb_errors.py',
  'server/utils/file.py',
  'scripts/migrate_kb_directory_storage.py',
  'scripts/validate_rag_quality_fixtures.py',
  'tests/api/test_kb_directory_storage.py',
  'tests/api/test_kb_docs_isolation.py',
  'tests/api/test_kb_registry_atomic.py',
  'tests/scripts/test_migrate_kb_directory_storage.py',
  'tests/test_rag_quality_fixtures.py',
  'tests/utils/test_file_kb_paths.py'
)
$existingCheckPaths = $checkPaths | Where-Object { Test-Path $_ }
$placeholderPatterns = @(('T' + 'BD'), ('TO' + 'DO'), ('后续' + '再补'), ('?' * 3))
Select-String -Path $existingCheckPaths -Pattern $placeholderPatterns -SimpleMatch -CaseSensitive
```

预期：`git diff --check` 无输出且退出码为 0；占位词检查不得命中本阶段新增/修改文件中的未处理占位内容。若命中测试数据中有意构造的字符串，测试报告必须逐条说明为何不是占位遗留。

### 5.3 功能和回归命令

```powershell
python -m pytest tests/utils/test_file_kb_paths.py tests/api/test_kb_directory_storage.py tests/api/test_kb_docs_isolation.py tests/api/test_kb_registry.py tests/api/test_kb_registry_atomic.py tests/scripts/test_migrate_kb_directory_storage.py tests/test_rag_quality_fixtures.py -q
python -m pytest tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py tests/api/test_agent_runtime.py -q
python -m pytest tests/api tests/integration tests/scripts tests/utils tests/test_rag_quality_fixtures.py -q
python -m pytest tests -q -m "not slow"
```

### 5.4 覆盖率门禁

当前开发机验证结果：`pytest-cov 7.1.0` 支持 `--cov` 参数，但 `--cov=server/kb_registry.py` 这类单文件路径会被当成模块名并产生 `No data to report`，因此阶段 5 正式覆盖率门禁使用下面的 `coverage run/report --include=...` 命令。后续如需恢复 pytest-cov 优先命令，应改为包级 `--cov=api --cov=server --cov=scripts` 并配合 omit/include 配置验证。

正式覆盖率命令：

```powershell
python -m coverage run -m pytest tests/api tests/integration tests/scripts tests/utils tests/test_rag_quality_fixtures.py -q
python -m coverage report --include="api/routers/kb.py,api/services/kb_service.py,server/index.py,server/kb_registry.py,server/kb_errors.py,server/utils/file.py,scripts/migrate_kb_directory_storage.py,scripts/validate_rag_quality_fixtures.py" --fail-under=80 --show-missing
```

预期：上述目录化存储改动相关 Python 文件的总行覆盖率 >= 80%。如果覆盖率低于 80%、覆盖率工具缺失、覆盖率报告生成失败，阶段 5 必须判定失败，并先补测试或修复工具链后重新执行。

### 5.5 真实 OCR 慢测单独执行

真实 OCR 慢测单独执行，不纳入目录化存储默认门禁；若未执行，正式测试报告必须说明原因、耗时预期和非阻断依据。

```powershell
python -m pytest tests/readers/test_pdf_ocr.py -q -m slow -s
```

---

## 6. 编码阶段预跑记录

以下结果是编码阶段用于确认实现可运行的预跑证据，不替代阶段 5 的正式测试报告。2026-07-14 在修复 `server/kb_registry.py` 缩进/中文注释恢复问题后，已重新执行以下命令。

执行上下文：工作目录 `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb`；Python 为系统 Python 3.12；测试使用 `tmp_path`、monkeypatch 或测试 fixture 隔离文件系统状态，不写入用户真实 `data/` 与 `storage/`；当前记录为编码阶段预跑，正式报告还需在阶段 5 重新记录分支、commit、pytest/coverage 版本与覆盖率。

| 时间 | 命令 | 结果 |
|---|---|---|
| 2026-07-14 | `python -m py_compile server/kb_registry.py` | `passed` |
| 2026-07-14 | `python -m pytest tests/api/test_kb_registry.py tests/api/test_kb_registry_atomic.py -q` | `18 passed in 0.80s` |
| 2026-07-14 | `python -m pytest tests/utils/test_file_kb_paths.py tests/api/test_kb_directory_storage.py tests/api/test_kb_docs_isolation.py tests/api/test_kb_registry.py tests/api/test_kb_registry_atomic.py tests/scripts/test_migrate_kb_directory_storage.py tests/test_rag_quality_fixtures.py -q` | `71 passed in 5.28s` |
| 2026-07-14 | `python -m pytest tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py tests/api/test_agent_runtime.py -q` | `45 passed, 2 warnings in 6.02s` |
| 2026-07-14 | `python -m pytest tests/api tests/integration tests/scripts tests/utils tests/test_rag_quality_fixtures.py -q` | `145 passed, 2 warnings in 6.14s` |
| 2026-07-14 | `python -m pytest tests/readers/test_pdf_ocr.py -q -m "not slow"` | `2 passed, 1 deselected in 1.79s` |
| 2026-07-14 | `python -m pytest tests -q -m "not slow"` | `149 passed, 1 deselected, 2 warnings in 10.33s` |

警告说明：2 个 warning 均来自 FastAPI `@app.on_event("startup")` 弃用提示，不影响本需求功能判断。

---

## 7. 通过标准

1. 阶段 5 正式执行命令清单全部通过，包括模块定位命令、最终非 slow 全量门禁、覆盖率门禁、文档和格式门禁。
2. 目录化新增测试和原有多 KB/Agent 回归测试均无失败。
3. 覆盖率报告成功生成，目录化存储改动相关 Python 文件总行覆盖率 >= 80%；低于 80% 时必须补测试或调整测试范围说明后重跑。
4. `git diff --check` 无空白/格式错误；占位词检查无未处理遗留。
5. 测试过程中不得污染用户真实 `data/` 文件和真实 `storage/` 索引。
6. 如果真实 OCR 慢测未执行，测试报告必须明确说明原因、耗时预期和非阻断依据。
7. 若发现失败，必须先修复阻断问题并重新执行相关命令，再生成最终测试报告。


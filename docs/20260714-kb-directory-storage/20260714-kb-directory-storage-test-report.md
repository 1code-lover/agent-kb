# 多知识库目录化存储测试报告

日期：2026-07-15
阶段：阶段 5 正式测试执行
结论：通过。目录化存储相关功能测试、回归测试、覆盖率门禁、文档/格式门禁均已通过；真实 PaddleOCR slow 测试按测试方案未纳入默认门禁。

---

## 1. 执行上下文

| 项目 | 值 |
|---|---|
| 工作目录 | `C:\Users\ethan1.zhao\Downloads\agent-kb-main\github-agent-kb` |
| 分支 | `codex/desktop-agent-stage3` |
| 基准 commit | `97d5a65` |
| Python | `Python 3.12.10` |
| pytest | `pytest 8.3.4` |
| coverage | `coverage 7.15.1` |
| pytest-cov | `pytest-cov 7.1.0` |
| 隔离策略 | 文件落盘、registry、迁移脚本相关测试均使用 `tmp_path`、`monkeypatch` 或测试 fixture 隔离，未写入用户真实 `data/` 与 `storage/` |

说明：阶段 5 执行前已确认测试方案评审放行。执行中发现 `pytest-cov --cov=server/kb_registry.py` 这类单文件路径会被当前版本识别为模块名并导致无覆盖率数据，因此正式覆盖率门禁使用 `coverage run/report --include=...`。

---

## 2. 正式命令与结果

### 2.1 Python 语法自检

```powershell
python -m py_compile server/kb_errors.py server/kb_registry.py server/index.py server/utils/file.py api/services/kb_service.py api/routers/kb.py scripts/migrate_kb_directory_storage.py scripts/validate_rag_quality_fixtures.py
```

结果：通过，退出码 0。

### 2.2 文档与格式门禁

```powershell
git diff --check
```

结果：通过，退出码 0。命令仅输出 Git 的 LF/CRLF 工作区提示，没有空白错误。项目文档同步完成后已重新执行该门禁，结果仍为通过。

```powershell
# 按测试方案第 5.2 节执行占位词检查，扫描本专题文档、代码、脚本、测试文件及项目索引文档。
```

结果：通过，无命中输出。

### 2.3 核心目录化功能测试

```powershell
python -m pytest tests/utils/test_file_kb_paths.py tests/api/test_kb_directory_storage.py tests/api/test_kb_docs_isolation.py tests/api/test_kb_registry.py tests/api/test_kb_registry_atomic.py tests/scripts/test_migrate_kb_directory_storage.py tests/test_rag_quality_fixtures.py tests/api/test_index_manager_coverage.py -q
```

结果：`90 passed in 9.36s`。

覆盖内容：`kb_id` 校验、KB 目录解析、导入前 active 校验、文件落盘到 `data/{kb_id}/`、共享索引 metadata 写入、文档列表/删除隔离、registry 原子写与并发计数、迁移脚本 dry-run/apply/verify/rollback、QA fixture schema，以及 `IndexManager` 轻量分支覆盖。

### 2.4 KB / 多 KB / Agent 定向回归

```powershell
python -m pytest tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py tests/api/test_agent_runtime.py -q
```

结果：`45 passed, 2 warnings in 3.70s`。

warning 来源：FastAPI `@app.on_event("startup")` 弃用提示，非本需求引入，不影响目录化存储功能判断。

### 2.5 扩展回归

```powershell
python -m pytest tests/api tests/integration tests/scripts tests/utils tests/test_rag_quality_fixtures.py -q
```

结果：`164 passed, 2 warnings in 5.18s`。

### 2.6 非 slow 全量门禁

```powershell
python -m pytest tests -q -m "not slow"
```

结果：`168 passed, 1 deselected, 2 warnings in 5.74s`。

说明：`1 deselected` 为 slow 标记测试，符合默认快测策略。

---

## 3. 覆盖率门禁

### 3.1 首次执行失败记录

首次正式覆盖率执行时测试本身通过，但覆盖率门禁失败：

```text
145 passed, 2 warnings in 12.01s
TOTAL 873 statements, 263 missing, 70%
Coverage failure: total of 70 is less than fail-under=80
```

原因：测试方案把整个 `server/index.py` 纳入统计，而该文件包含索引加载、目录导入、OCR、网页抓取、删除等多条旧路径；当时 `server/index.py` 覆盖率仅 34%，拉低了目录化相关文件总覆盖率。

修复动作：新增 `tests/api/test_index_manager_coverage.py`，通过 monkeypatch 隔离 LlamaIndex、OCR 与网页抓取重依赖，补齐 `IndexManager` 的索引加载、插入、目录导入、文件导入 metadata 归一化、URL fallback、删除等关键分支覆盖。

### 3.2 最终覆盖率命令

```powershell
python -m coverage erase
python -m coverage run -m pytest tests/api tests/integration tests/scripts tests/utils tests/test_rag_quality_fixtures.py -q
python -m coverage report --include="api/routers/kb.py,api/services/kb_service.py,server/index.py,server/kb_registry.py,server/kb_errors.py,server/utils/file.py,scripts/migrate_kb_directory_storage.py,scripts/validate_rag_quality_fixtures.py" --fail-under=80 --show-missing
```

测试结果：`164 passed, 2 warnings in 17.05s`。
覆盖率结果：通过，总覆盖率 `84%`，高于阶段 5 门禁 `>= 80%`。

| 文件 | Stmts | Miss | Cover |
|---|---:|---:|---:|
| `api/routers/kb.py` | 87 | 27 | 69% |
| `api/services/kb_service.py` | 227 | 30 | 87% |
| `scripts/migrate_kb_directory_storage.py` | 109 | 36 | 67% |
| `scripts/validate_rag_quality_fixtures.py` | 64 | 17 | 73% |
| `server/index.py` | 194 | 7 | 96% |
| `server/kb_errors.py` | 20 | 0 | 100% |
| `server/kb_registry.py` | 118 | 8 | 93% |
| `server/utils/file.py` | 54 | 16 | 70% |
| **TOTAL** | **873** | **141** | **84%** |

---

## 4. Slow OCR 测试说明

测试方案明确真实 OCR slow 测试不纳入目录化存储默认门禁，命令为：

```powershell
python -m pytest tests/readers/test_pdf_ocr.py -q -m slow -s
```

本次阶段 5 未执行该 slow 命令，原因：

1. 目录化存储改动目标是 KB 文件路径、registry、共享索引 metadata 与管理接口隔离，不改变 PaddleOCR 识别算法。
2. slow OCR 依赖真实 OCR 推理，耗时显著高于目录化门禁，测试方案已允许单独执行并要求在报告中说明。
3. 默认非 slow 全量门禁已通过，且 slow 用例被明确 deselect，不影响本阶段通过结论。

如后续要做 OCR 质量专项或发布前硬门禁，应单独执行上述 slow 命令并记录耗时、样本与识别质量。

---

## 5. 验收结论

| 验收项 | 结果 |
|---|---|
| 导入前校验 KB 已登记且 active | 通过 |
| 新导入原始文件保存到 `data/{kb_id}/` | 通过 |
| `IndexManager.load_files()` 使用明确 `file_paths` | 通过 |
| list/delete 按 `kb_id` 隔离，旧无 `kb_id` 节点只归 `default` | 通过 |
| 删除 KB 阻止非空，空 KB 处理 registry 与目录一致性 | 通过 |
| registry 原子写、并发更新、doc_count 下限 | 通过 |
| 迁移脚本 dry-run/apply/verify/rollback | 通过 |
| QA fixture schema 与防污染校验 | 通过 |
| KB/多 KB/Agent/API/integration 回归 | 通过 |
| 覆盖率门禁 `>= 80%` | 通过，最终 `84%` |
| 文档与格式门禁 | 通过 |

阶段 5 正式测试执行通过，可以提交给审核方评审测试报告。测试报告审核通过后，才能进入阶段 6 的开发故事沉淀、commit 与 push。

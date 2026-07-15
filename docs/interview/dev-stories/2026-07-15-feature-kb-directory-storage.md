# 多知识库原始文件目录化存储

## 基本信息
- 类型：feature
- 日期：2026-07-15
- 相关模块：知识库管理、文件导入、共享索引写入、文档列表/删除、registry、迁移脚本、QA fixture
- 相关文件：`api/services/kb_service.py`、`api/routers/kb.py`、`server/utils/file.py`、`server/index.py`、`server/kb_registry.py`、`server/kb_errors.py`、`scripts/migrate_kb_directory_storage.py`、`scripts/validate_rag_quality_fixtures.py`、`tests/api/test_kb_directory_storage.py`、`tests/api/test_kb_docs_isolation.py`、`tests/api/test_index_manager_coverage.py`、`docs/20260714-kb-directory-storage/`

## 需求背景

项目已经有 `KBRegistry`、`kb_id` metadata 和查询过滤，能够在共享索引上做最小多知识库逻辑隔离；但原始文件仍平铺在 `data/` 根目录。这会带来两个问题：第一，不同知识库上传同名文件时缺少清晰物理归属；第二，后续做迁移、删除、备份和问题排查时，很难从文件系统直接看出文件属于哪个知识库。

这次需求的目标不是一步到位做物理多索引，而是先把第一阶段边界收稳：新导入原始文件按 `data/{kb_id}/` 目录保存，向量索引仍共享，通过 metadata 继续做逻辑隔离，同时补上 registry 一致性、迁移脚本和测试/文档门禁。

## 设计与实现方案

我先按仓库流程补齐了 `docs/20260714-kb-directory-storage/` 下的 PRD、FRD、RTM、实施计划、测试方案和测试报告，把范围明确为“原始文件目录化 + 共享索引 metadata 过滤”，避免把 `data/{kb_id}/` 误描述成向量索引物理隔离。

代码层面拆成几条链路：

1. `server/utils/file.py` 增加 `kb_id` 校验、KB 数据目录解析、路径边界校验和安全文件名处理。`kb_id` 只允许小写字母、数字和中划线，且首尾必须是字母或数字。
2. `server/kb_errors.py` 定义稳定异常类型，避免服务层靠 `ValueError` 字符串判断 HTTP 状态码；`api/routers/kb.py` 负责把 validation / not found / conflict / consistency 等异常映射成 400 / 404 / 409 / 500。
3. `api/services/kb_service.py` 在导入前先校验 KB 已登记且 active，再把文件保存到 `data/{kb_id}/`，索引成功后更新 `doc_count`，索引失败则清理刚落盘的源文件。
4. `server/index.py` 的 `IndexManager.load_files()` 改为接收服务层确认过的 `file_paths`，不再二次调用全局保存目录拼路径；写入节点 metadata 时补齐 `file_path`、`file_name` 和 `kb_id`。
5. 文档列表和删除按 `kb_id` 严格隔离。旧无 `kb_id` 的节点只归 `default`，非 default 请求不能混入或误删这些旧节点。
6. `server/kb_registry.py` 把 read-modify-write 放进同一个 `RLock` 临界区，写入用临时文件、flush、fsync 和 `os.replace()`，并对 Windows `PermissionError` 做短重试；`doc_count` 更新有下限保护。
7. `scripts/migrate_kb_directory_storage.py` 提供 dry-run、apply、manifest、SHA256 verify 和 rollback，只迁移原始文件，不声称修复旧索引 metadata。
8. `tests/fixtures/rag_quality/` 与 `scripts/validate_rag_quality_fixtures.py` 建立 QA fixture schema 校验，先保证评测集结构和防污染，不把 fixture 当成真实知识库导入。

## 为什么选这个方案

我选择“共享索引不动，先目录化原始文件”的方案，是因为它把风险控制在服务层和文件系统层：既能解决当前最明显的文件归属问题，又不会在同一轮里引入多索引、多 namespace、索引迁移和查询路由重构的复杂度。

导入前先校验 KB，而不是先落盘再报错，是为了避免未登记知识库产生孤儿文件。`IndexManager.load_files()` 改成显式 `file_paths`，是为了让路径归属只由服务层做一次可信决策，避免索引层再从全局 `data/` 推断路径导致回到平铺模型。

异常类型放在 `server/kb_errors.py`，而不是放在 `api/services/`，是为了避免 `server/utils/file.py` 反向依赖 API 层。HTTP 状态码只在 router 做转换，服务层保留稳定业务异常。

registry 的改动没有只加锁 `_read()` / `_write()`，而是把 read-modify-write 整体放进临界区，因为真正的问题不是完全无锁，而是计数更新可能在两个独立锁之间丢失。

## 其他方案与为什么没选

- 直接做物理多索引 / 多 namespace：隔离更彻底，但会同时影响索引创建、加载、查询、删除、迁移和 UI 状态，不适合作为这个阶段的第一步。
- 只靠 metadata，不改原始文件目录：改动小，但无法解决用户指定的 `data/` 下多文件夹、多知识库物理归属问题，也不利于后续迁移和备份。
- 迁移脚本同时修改旧索引 metadata：看起来闭环，但风险很高，因为旧索引持久化结构和节点来源不一定能可靠反推；本阶段只迁移原始文件，并在文档里明确“查询一致性需要重导或重建索引”。

## 风险与权衡

最大权衡是：当前仍然不是物理隔离多库。新导入文件已经进入 `data/{kb_id}/`，新节点也会写入 `kb_id` metadata；但共享向量索引仍存在，历史无 `kb_id` 节点仍按兼容策略归 `default`。这适合作为过渡态，但不能对外宣称成“完全隔离”。

第二个风险是覆盖率统计把 `server/index.py` 整个文件纳入门禁后，旧路径会拖低整体覆盖率。第一次正式覆盖率只有 70%，我没有放宽门禁，而是新增 `tests/api/test_index_manager_coverage.py`，用 monkeypatch 隔离 LlamaIndex、OCR 和网页抓取重依赖，把 `IndexManager` 的关键分支补测到位，最终总覆盖率到 84%。

第三个风险是 Windows 文件系统和编码问题。registry 原子写入对 Windows `PermissionError` 做了短重试；文档和测试报告写入后也重新执行 `git diff --check` 和占位词检查，避免格式门禁在最后一步被文档同步破坏。

## 验证与结果

阶段 5 正式测试报告已生成：`docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-report.md`。

核心测试命令和结果：

```powershell
python -m pytest tests/utils/test_file_kb_paths.py tests/api/test_kb_directory_storage.py tests/api/test_kb_docs_isolation.py tests/api/test_kb_registry.py tests/api/test_kb_registry_atomic.py tests/scripts/test_migrate_kb_directory_storage.py tests/test_rag_quality_fixtures.py tests/api/test_index_manager_coverage.py -q
```

结果：

```text
90 passed in 9.36s
```

定向回归：

```powershell
python -m pytest tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py tests/api/test_agent_runtime.py -q
```

结果：

```text
45 passed, 2 warnings in 3.70s
```

扩展回归：

```powershell
python -m pytest tests/api tests/integration tests/scripts tests/utils tests/test_rag_quality_fixtures.py -q
```

结果：

```text
164 passed, 2 warnings in 5.18s
```

非 slow 全量门禁：

```powershell
python -m pytest tests -q -m "not slow"
```

结果：

```text
168 passed, 1 deselected, 2 warnings in 5.74s
```

覆盖率门禁：

```powershell
python -m coverage run -m pytest tests/api tests/integration tests/scripts tests/utils tests/test_rag_quality_fixtures.py -q
python -m coverage report --include="api/routers/kb.py,api/services/kb_service.py,server/index.py,server/kb_registry.py,server/kb_errors.py,server/utils/file.py,scripts/migrate_kb_directory_storage.py,scripts/validate_rag_quality_fixtures.py" --fail-under=80 --show-missing
```

结果：

```text
TOTAL 873 statements, 141 missing, 84%
```

最终还执行了：

```powershell
python -m py_compile server/kb_errors.py server/kb_registry.py server/index.py server/utils/file.py api/services/kb_service.py api/routers/kb.py scripts/migrate_kb_directory_storage.py scripts/validate_rag_quality_fixtures.py
git diff --check
```

结果均通过；`git diff --check` 只有 LF/CRLF 提示，无空白格式错误。提交前又补跑了排除反引号示例误伤的占位词扫描，结果无命中；并重新执行 `python -m pytest tests -q -m "not slow"`，结果为 `168 passed, 1 deselected, 2 warnings in 5.26s`。FastAPI `@app.on_event("startup")` warning 是既有弃用提示，非本需求阻断项。真实 PaddleOCR slow 测试按测试方案未纳入本阶段默认门禁。

## 面试表达版本

我把多知识库的第一阶段隔离从“只靠 metadata”推进到了“原始文件也有物理归属”。实现上没有急着拆多索引，而是让服务层在导入前校验 KB active，再把文件保存到 `data/{kb_id}/`，索引层只接收明确的 `file_paths` 并补 `kb_id` metadata。这样既满足了用户对多知识库目录化的诉求，又避免在一轮里同时重构索引架构。为了保证不是只改 happy path，我还补了 registry 原子写、旧 default 节点隔离、迁移脚本 dry-run/verify/rollback 和 QA fixture schema。测试阶段第一次覆盖率只有 70%，我没有调低门禁，而是补了 `IndexManager` 的轻量覆盖率测试，最后把目录化相关文件覆盖率提高到 84%，全量非 slow 回归也通过了。
# 多知识库目录化存储实施方案

- 日期：2026-07-14
- 专题：`20260714-kb-directory-storage`
- 状态：第三轮评审通过，P2 已修订，进入编码阶段
- 前置文档：
  - `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-prd.md`
  - `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-frd.md`
  - `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-rtm.md`
- 当前门禁：本实施方案通过评审前，不进入编码阶段。

## 1. 目标与边界

### 1.1 本阶段目标

把当前“逻辑多知识库”推进为：

```text
registry 仍是权威清单
        ↓
每个 KB 拥有独立原始文件目录 data/{kb_id}/
        ↓
导入、列表、删除、迁移均按 kb_id 严格归属
        ↓
向量索引第一阶段继续共享，通过 metadata.kb_id 过滤
```

本阶段交付后，允许：

- 创建 KB 时同步创建 `data/{kb_id}/`。
- 文件导入前先校验 `kb_id` 已登记且处于 active 状态。
- 上传文件只落盘到所属 KB 目录。
- `IndexManager.load_files()` 接收服务层确认过的 `file_paths`，不再通过全局 `get_save_dir()` 二次拼路径。
- 文档列表和删除严格按 KB 隔离；无 `kb_id` 的旧节点只归属 `default`。
- 删除 KB 时先检查非空状态，非空返回冲突错误，空 KB 才删除 registry 和空目录。
- registry 写入具备进程内锁、原子替换和 `doc_count` 下限保护。
- 提供旧 `data/` 根目录文件迁移到 `default` 的 dry-run、备份、SHA256 校验和回滚入口。
- QA fixture 本阶段只做 schema 与防污染校验，不执行完整 RAG 质量评分。

### 1.2 本阶段不做

- 不把 `storage/` 拆成每个 KB 一个向量索引。
- 不改变查询链路的共享索引本质。
- 不执行真实生产数据迁移；只交付可测试迁移脚本和 dry-run 能力。
- 不把用户提供的 Q/A 直接计入正式质量指标；缺少证据绑定时只进入 draft。
- 不提交、不推送，直到实施、测试报告和开发故事均完成并通过审核。

## 2. 当前代码事实

| 文件 | 当前事实 | 本计划处理 |
|---|---|---|
| `server/utils/file.py` | 只有全局 `get_save_dir()`、文件名清洗和保存工具 | 增加 KB ID 校验、KB 目录解析、路径边界校验 |
| `api/services/kb_service.py` | `import_files()` 使用全局 `data/`，导入后才更新 `doc_count`；`delete_kb()` 只删 registry | 改成导入前校验 KB，按 `data/{kb_id}/` 落盘，删除 KB 做非空和目录一致性检查 |
| `server/index.py` | `IndexManager.load_files()` 内部再次调用 `get_save_dir()` 并拼上传文件名 | 改成接收明确 `file_paths`，由服务层决定文件真实路径 |
| `server/kb_registry.py` | 当前已有 `_lock`，但 `_read()` 与 `_write()` 分别加锁，调用方 read-modify-write 不在同一临界区；写入不是原子替换，`doc_count` 可被减成负数 | 将 read-modify-write 收敛到同一临界区，补原子写、计数下限和并发测试 |
| `api/routers/kb.py` | 统一把服务异常映射为 400/404，删除 KB 文案仍写“级联删除” | 按稳定服务异常类型映射 400/404/409/500，修正文案 |
| `tests/fixtures/rag_quality/` | 当前不存在 | 本阶段创建 draft/verified fixture 与 schema 校验，不放入 `data/` |

## 3. 精确改动文件

### 3.1 生产代码

| 路径 | 改动类型 | 主要函数/对象 |
|---|---|---|
| `server/utils/file.py` | 修改 | `validate_kb_id()`、`get_data_root()`、`get_kb_data_dir()`、`ensure_path_within()`、`save_uploaded_file()` |
| `api/services/kb_service.py` | 修改 | `create_kb()`、`delete_kb()`、`import_files()`、`import_urls()`、`list_docs()`、`delete_docs()`、新增 `_ensure_kb_active()`、`_normalize_doc_kb_id()` |
| `server/kb_errors.py` | 新增 | `KBServiceError`、`KBValidationError`、`KBNotFoundError`、`KBConflictError`、`KBUnavailableError`、`KBConsistencyError`；作为中立异常模块，避免 `server -> api` 反向依赖 |
| `server/index.py` | 修改 | `IndexManager.load_files()`、必要时调整 `_load_documents()` metadata 处理 |
| `server/kb_registry.py` | 修改 | `_read()`、`_write()`、`create_kb()`、`delete_kb()`、`add_doc_count()`、`set_doc_count()`、新增 `is_active()` 或 `validate_active()` |
| `api/routers/kb.py` | 修改 | `create_kb()`、`import_files()`、`import_web()`、`delete_kb()` 异常状态码映射和文案 |
| `scripts/migrate_kb_directory_storage.py` | 新增 | `plan_migration()`、`apply_migration()`、`verify_manifest()`、`rollback_migration()`、CLI 参数解析 |
| `scripts/validate_rag_quality_fixtures.py` | 新增 | `validate_file()`、`validate_record()`、`main()` |

### 3.2 测试代码与测试数据

| 路径 | 改动类型 | 覆盖目标 |
|---|---|---|
| `tests/utils/test_file_kb_paths.py` | 新增 | KB ID 合法性、Windows 保留名、路径穿越、目录边界 |
| `tests/api/test_kb_directory_storage.py` | 新增 | 创建 KB 目录、导入前校验、按 KB 落盘、索引失败补偿 |
| `tests/api/test_kb_docs_isolation.py` | 新增 | list/delete 对 default、非 default、旧无 `kb_id` 节点的隔离行为 |
| `tests/api/test_kb_registry_atomic.py` | 新增 | registry 原子写、并发计数、负数下限 |
| `tests/scripts/test_migrate_kb_directory_storage.py` | 新增 | 迁移 dry-run、备份 manifest、SHA256 校验、回滚；`tests/scripts/` 当前不存在，编码阶段同步创建该目录 |
| `tests/fixtures/rag_quality/draft.jsonl` | 新增 | draft 样例，允许未绑定完整证据 |
| `tests/fixtures/rag_quality/verified.jsonl` | 新增 | verified 样例，必须绑定 KB、文件、证据片段 |
| `tests/fixtures/rag_quality/schema.json` | 新增 | fixture 结构约束 |
| `tests/test_rag_quality_fixtures.py` | 新增 | schema 校验、防污染校验、verified 负向用例 |

### 3.3 文档

| 路径 | 改动类型 | 触发时机 |
|---|---|---|
| `docs/project.md` | 修改 | 实施完成后更新进度、测试结果和已知边界 |
| `docs/guide/DOCS_INDEX.md` | 修改 | 本 plan 创建或修订后标记“实施方案待复审”；实施完成后再标记下一阶段 |
| `docs/spec/knowledge_base_visibility_and_multi_kb_design.md` | 修改 | 实施完成后更新目录化已实现/共享索引仍保留的真实状态 |
| `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-plan.md` | 新增 | 编码完成后进入测试方案阶段时创建并等待审核 |
| `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-report.md` | 新增 | 测试方案审核通过并执行测试后创建 |
| `.interview-kit/dev-stories/` 或 `docs/interview/dev-stories/` | 新增/修改 | 功能完成且测试报告审核通过后，按 `$dev-story-capture` 沉淀开发故事 |

## 4. TDD 实施顺序

### Task 1：KB 目录与路径安全工具

**目标文件**：`server/utils/file.py`

**先写失败测试**：`tests/utils/test_file_kb_paths.py`

测试用例：

1. `validate_kb_id("product-docs")` 通过。
2. `validate_kb_id("../escape")` 抛出 `KBValidationError`。
3. `validate_kb_id("bad_id")` 抛出 `KBValidationError`，确认下划线不被允许。
4. `validate_kb_id("-bad")`、`validate_kb_id("bad-")` 抛出 `KBValidationError`，确认首尾必须是字母或数字。
5. `validate_kb_id("CON")`、`validate_kb_id("nul")` 抛出 `KBValidationError`，覆盖 Windows 保留名。
6. `get_kb_data_dir("kb-a")` 返回 `data/kb-a` 的规范化绝对路径。
7. `ensure_path_within(data/kb-a, data/kb-a/file.txt)` 通过。
8. `ensure_path_within(data/kb-a, data/kb-a/../kb-b/file.txt)` 抛出 `KBValidationError`。

实现要求：

- `validate_kb_id(kb_id: str) -> str`
  - 字符集限定为小写字母、数字、中划线。
  - 禁止下划线。
  - 长度 1 到 64。
  - 必须以小写字母或数字开头和结尾。
  - 正则与 PRD/FRD 保持一致：`^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`。
  - 禁止 `.`、`..`、斜杠、反斜杠、冒号、绝对路径片段。
  - 禁止 Windows 保留名：`CON`、`PRN`、`AUX`、`NUL`、`COM1` 至 `COM9`、`LPT1` 至 `LPT9`，大小写不敏感。
- `get_data_root() -> Path`
  - 返回 `Path.cwd() / DATA_DIR` 的 resolved 路径。
- `get_kb_data_dir(kb_id: str, create: bool = False) -> Path`
  - 先调用 `validate_kb_id()`。
  - 校验 resolved 结果仍在 data 根目录内。
  - `create=True` 时创建目录。
- `ensure_path_within(base: Path, target: Path) -> Path`
  - 使用 `Path.resolve()` 和 `relative_to()` 校验边界。
- `save_uploaded_file()` 保留兼容能力，但返回最终 `Path`，并复用边界校验。
- 路径与 kb_id 校验失败统一抛出 `KBValidationError`，不再让路由层依赖错误字符串判断。

命令：

```powershell
python -m pytest tests/utils/test_file_kb_paths.py -q
```

预期：Task 1 完成后该命令通过。

### Task 2：KB 创建与导入前校验、按目录落盘

**目标文件**：`api/services/kb_service.py`、必要时 `api/routers/kb.py`

**先写失败测试**：`tests/api/test_kb_directory_storage.py`

测试用例：

1. `create_kb("kb-a", "KB A")` 成功后创建 `data/kb-a/`。
2. 重复创建 KB 返回冲突，不覆盖已有目录。
3. registry 创建成功但目录创建失败时回滚 registry。
4. 上传到不存在 KB 时，在读取上传文件内容和落盘之前失败，不产生孤儿文件。
5. 上传到 `status != "active"` 的 KB 时失败，不产生孤儿文件。
6. `status` 字段缺失的历史 registry 项按 active 兼容处理。
7. 文件上传到 `data/kb-a/{unique_filename}`，同名文件在 `kb-a` 和 `kb-b` 下互不覆盖。
8. 索引失败时删除本次新落盘文件，不增加 `doc_count`。
9. 网页导入 `import_urls()` 同样先校验 KB active，成功后才增加 `doc_count`。

实现要求：

- 新增稳定服务异常类型，放在中立模块 `server/kb_errors.py`，避免 `server/utils/file.py` 依赖 `api/services`，也避免后续靠字符串判断 HTTP 状态码：
  - `KBServiceError(message: str, *, code: str = "kb_error")`：服务层基类。
  - `KBValidationError`：参数或路径校验失败，路由映射 400。
  - `KBNotFoundError`：registry 中不存在目标 KB，路由映射 404。
  - `KBConflictError`：重复创建、非空删除、禁止删除 default 等业务冲突，路由映射 409。
  - `KBUnavailableError`：KB 存在但 `status != "active"`，路由映射 400。
  - `KBConsistencyError`：registry 与目录或文件操作出现补偿失败，路由映射 500，必要时 detail 提示人工处理。
- 新增 `_ensure_kb_active(kb_id: str) -> dict`：
  - 调用 `validate_kb_id()`；非法时抛出 `KBValidationError`。
  - registry 不存在时抛出 `KBNotFoundError`。
  - registry 中 `status` 存在且不是 `active` 时抛出 `KBUnavailableError`。
  - registry 中无 `status` 时视为 active，兼容旧数据。
- `create_kb()`：
  - 先校验 `kb_id`。
  - 创建 registry 项和目录必须具备补偿。
  - 若目录创建失败，删除刚创建的 registry 项或恢复到创建前快照。
- `import_files()`：
  - 第一行核心逻辑必须先 `_ensure_kb_active(kb_id)`，再 `runtime_state.ensure_models_ready()`，再读取文件内容。
  - 使用 `get_kb_data_dir(kb_id, create=True)` 获取目标目录。
  - 生成唯一文件名后写入 KB 目录。
  - 传给 `IndexManager.load_files()` 的必须是实际 `file_paths`，不是文件名。
  - `doc_count` 只在索引成功后增加。
  - 索引失败时删除本次新写入的文件并返回明确异常。
- `api/routers/kb.py`：
  - 不再捕获泛化 `ValueError` 并靠字符串判断业务状态。
  - `KBValidationError`、`KBUnavailableError` 映射为 400。
  - `KBNotFoundError` 映射为 404。
  - `KBConflictError` 映射为 409。
  - `KBConsistencyError` 映射为 500，并保留可排查 detail。

命令：

```powershell
python -m pytest tests/api/test_kb_directory_storage.py -q
python -m pytest tests/api/test_kb_routes.py -q
```

预期：新增目录化测试通过，已有 KB route 测试不回归。

### Task 3：IndexManager 接收明确 file_paths

**目标文件**：`server/index.py`

**先写失败测试**：`tests/api/test_kb_directory_storage.py`

测试用例：

1. `IndexManager.load_files(file_paths=[data/kb-a/a.txt], kb_id="kb-a")` 不调用 `get_save_dir()`。
2. 节点 metadata 包含：
   - `kb_id="kb-a"`
   - `file_path` 为真实绝对路径或规范化路径
   - `file_name="a.txt"`
3. 传入不在 `data/kb-a/` 下的文件路径时由服务层或工具层阻断。
4. 旧的目录加载 `load_dir()` 行为不被破坏。

实现要求：

- 将 `IndexManager.load_files()` 签名调整为：

```python
def load_files(
    self,
    file_paths: list[str | Path],
    chunk_size: int,
    chunk_overlap: int,
    kb_id: str | None = None,
) -> list[Any]:
```

- 方法内部只使用传入的 `file_paths`。
- 删除 `load_files()` 内部对 `get_save_dir()` 的依赖。
- 继续通过 `_load_documents(file_paths)` 读取文档。
- 对每个 node 写入 `kb_id`、`file_name`、`file_path` metadata。
- 若 llama reader 已产生不可 JSON 序列化 metadata，继续使用现有 `sanitize_for_json()`。

命令：

```powershell
python -m pytest tests/api/test_kb_directory_storage.py -q
python -m pytest tests/api/test_m2_multi_kb.py -q
```

预期：新增 `file_paths` 行为通过，现有多 KB metadata 测试不回归。

### Task 4：文档列表与删除严格隔离

**目标文件**：`api/services/kb_service.py`、`server/utils/file.py`

**先写失败测试**：`tests/api/test_kb_docs_isolation.py`

测试用例：

1. `list_docs(kb_id="kb-a")` 只返回 metadata `kb_id == "kb-a"` 的文档。
2. `list_docs(kb_id="default")` 返回 metadata 缺失 `kb_id` 的旧节点，并标记为 `default`。
3. `list_docs(kb_id="kb-a")` 不返回 metadata 缺失 `kb_id` 的旧节点。
4. `delete_docs(kb_id="kb-a", doc_ids=[old_doc])` 不删除无 `kb_id` 的旧节点。
5. `delete_docs(kb_id="default", doc_ids=[old_doc])` 可以删除旧节点。
6. `delete_docs(kb_id="kb-a", paths=[data/kb-b/file.txt])` 删除数为 0，不删除其他 KB 文件。
7. 删除文件节点时，只删除目标 KB 目录内的真实文件；URL 节点不执行本地文件删除。
8. 文件删除失败时，返回部分失败信息或抛出明确一致性错误，不静默吞掉。
9. `delete_docs(kb_id="default")` 可删除迁移前 `data/foo.pdf` 这种根目录直属旧文件，但不能删除 `data/kb-a/foo.pdf` 或 `data/manual/foo.pdf` 这类子目录文件。

实现要求：

- 新增 `_normalize_doc_kb_id(metadata: dict) -> str`：
  - `metadata.get("kb_id") or "default"`。
- `list_docs(kb_id)`：
  - 如果 `kb_id is None` 返回全部，但每条 doc 的 `kb_id` 都必须规范化。
  - 如果 `kb_id != "default"`，只允许精确匹配 `metadata["kb_id"] == kb_id`。
  - 如果 `kb_id == "default"`，允许 `metadata["kb_id"]` 缺失或等于 `default`。
- `delete_docs(request)`：
  - 使用同一归属判断。
  - 非 default 请求绝不能删除无 `kb_id` 的旧节点。
  - 删除源文件前使用明确的二选一边界策略，避免旧 default 文件无法删除或越权删除：
    - 非 default KB：只允许删除 resolved 路径位于 `data/{kb_id}/` 内的文件。
    - default KB：允许删除 resolved 路径位于 `data/default/` 内的文件；同时为迁移前旧无 `kb_id` 节点保留 legacy root 删除通道，但必须满足 `metadata.kb_id` 缺失或等于 `default`、resolved 路径的父目录正好是 `data/` 根目录、目标是普通文件、目标文件名与 doc metadata 记录的文件名一致。
    - default KB 不递归删除 `data/` 根目录下的子目录文件，避免误删 `data/{other_kb}/` 或手工目录；不满足边界的旧节点只删除 docstore 记录并返回文件删除跳过/部分失败信息，提示先执行迁移。
  - URL 节点和无本地 `file_path` 的节点不执行本地文件删除。
  - registry `doc_count` 只对成功删除的目标 KB docstore 记录扣减，文件物理删除失败时需返回部分失败信息或抛出 `KBConsistencyError`。

命令：

```powershell
python -m pytest tests/api/test_kb_docs_isolation.py -q
python -m pytest tests/api/test_m2_multi_kb.py -q
```

预期：旧节点只归 default，非 default 删除不会误删旧节点或其他 KB 文件。

### Task 5：删除 KB 的非空检查、空目录删除与回滚

**目标文件**：`api/services/kb_service.py`、`api/routers/kb.py`

**先写失败测试**：`tests/api/test_kb_directory_storage.py`

测试用例：

1. 删除不存在 KB 返回 404。
2. 删除有索引文档的 KB 返回 409，不删除 registry，不删除目录。
3. `doc_count=0` 但 `data/{kb_id}/` 下仍有文件时返回 409 或一致性错误，不删除 registry。
4. 删除空 KB 成功后 registry 项消失，空目录消失。
5. registry 删除成功但目录删除失败时，恢复 registry 项并返回一致性错误。
6. 目录不存在但 registry 为空 KB 时，删除 registry 成功，并在结果中说明目录已缺失。
7. `default` KB 删除策略需显式决定：第一阶段禁止删除 `default`，返回 409。

实现要求：

- `delete_kb(kb_id)` 不再直接调用 registry 删除。
- 删除流程：

```text
validate_kb_id
读取 registry 项
禁止删除 default
按 list_docs(kb_id) 做真实非空检查
检查 data/{kb_id}/ 是否为空
保存 registry 项快照
删除 registry 项
删除空目录或确认目录不存在
如果目录删除失败，恢复 registry 项并抛出一致性错误
```

- `api/routers/kb.py`：
  - 非空 KB 删除映射为 409。
  - 不存在 KB 映射为 404。
  - 一致性或补偿失败固定映射为 500，并在 detail 中说明需人工处理；业务冲突如非空删除、重复创建、禁止删除 default 固定映射为 409。

命令：

```powershell
python -m pytest tests/api/test_kb_directory_storage.py -q
python -m pytest tests/api/test_kb_routes.py -q
```

预期：删除 KB 不再静默级联，非空和不一致状态均可见。

### Task 6：registry 原子写入、并发更新和 doc_count 下限

**目标文件**：`server/kb_registry.py`

**先写失败测试**：`tests/api/test_kb_registry_atomic.py`

测试用例：

1. `_write()` 写入期间异常时，原 `kb_registry.json` 仍是合法 JSON。
2. 多线程并发 `add_doc_count("kb-a", 1)` 后计数等于实际成功次数。
3. 多线程并发 `add_doc_count("kb-a", -1)` 不会把计数减到 0 以下。
4. `set_doc_count("kb-a", -10)` 被钳制为 0 或抛出 `ValueError`，计划采用钳制为 0。
5. 对不存在 KB 的计数更新不静默成功，改为返回 False 或抛出 `ValueError`；计划采用抛出 `ValueError`，由调用方决定是否忽略。

实现要求：

- `KBRegistry` 当前已有实例级 `_lock`，但 `_read()` 和 `_write()` 各自加锁导致调用方 read-modify-write 可交错；本任务将其调整为实例级 `threading.RLock` 或等价方案。
- 所有 read-modify-write 方法必须在同一临界区内完成；必要时新增 `_read_unlocked()`、`_write_unlocked()`，避免同一方法内重复锁导致死锁。
- `_write()` 改为临时文件 + `os.replace()` 原子替换：

```text
kb_registry.json.tmp-{pid}-{thread}
write + flush + fsync
os.replace(tmp, kb_registry.json)
```

- `doc_count` 更新使用 `max(0, old + delta)`。
- `create_kb()` 默认写入 `status: "active"`；读取旧项时无 status 仍按 active 兼容。

命令：

```powershell
python -m pytest tests/api/test_kb_registry.py tests/api/test_kb_registry_atomic.py -q
```

预期：registry 原有测试和新增原子性测试均通过。

### Task 7：旧 data 根目录迁移 dry-run 脚本

**目标文件**：`scripts/migrate_kb_directory_storage.py`

**先写失败测试**：`tests/scripts/test_migrate_kb_directory_storage.py`

CLI 设计：

```powershell
# 只生成计划，不改文件
python scripts/migrate_kb_directory_storage.py --dry-run --source data --target-kb default

# 执行文件迁移，先备份，再校验，再移动；这只迁移原始文件，不代表向量索引 metadata/file_path 已同步迁移完成
python scripts/migrate_kb_directory_storage.py --apply --source data --target-kb default --backup-dir backups/kb-directory-storage

# 校验迁移 manifest
python scripts/migrate_kb_directory_storage.py --verify --manifest backups/kb-directory-storage/<timestamp>/manifest.json

# 按 manifest 回滚
python scripts/migrate_kb_directory_storage.py --rollback --manifest backups/kb-directory-storage/<timestamp>/manifest.json
```

测试用例：

1. dry-run 只输出待迁移根目录文件，不创建、不移动、不删除。
2. 已在 `data/{kb_id}/` 子目录内的文件不会被当作根目录旧文件迁移。
3. apply 前为每个旧文件计算 SHA256，并写入 manifest。
4. apply 先复制到备份目录，再移动到 `data/default/`。
5. 移动后再次计算 SHA256，与 manifest 一致才算成功。
6. SHA256 不一致时中止并保留备份。
7. rollback 根据 manifest 将文件恢复到迁移前位置。
8. 脚本不直接修改 `storage/` 向量索引；`--apply` 成功只代表原始文件迁移完成，不代表索引迁移完成，执行结果必须提示需要重导或重建索引以同步 `file_path` 与 `kb_id` metadata。

实现要求：

- manifest 至少包含：
  - `source_path`
  - `target_path`
  - `backup_path`
  - `sha256_before`
  - `sha256_after`
  - `size`
  - `migrated_at`
  - `target_kb`
- 默认目标 KB 是 `default`。
- 如果 `default` 不存在，脚本提示先创建或通过参数允许创建 registry 项；本阶段计划采用“提示先创建”，避免脚本越权写 registry。
- 脚本不得删除 `storage/`，不得自动重建向量索引。
- `tests/scripts/` 当前不存在；编码阶段创建 `tests/scripts/` 并放置迁移脚本测试，不复用 API 测试目录。

命令：

```powershell
python -m pytest tests/scripts/test_migrate_kb_directory_storage.py -q
```

预期：迁移脚本具备可审计 dry-run、备份、校验和回滚能力。

### Task 8：QA fixture schema 与基础校验

**目标文件**：

- `tests/fixtures/rag_quality/schema.json`
- `tests/fixtures/rag_quality/draft.jsonl`
- `tests/fixtures/rag_quality/verified.jsonl`
- `scripts/validate_rag_quality_fixtures.py`
- `tests/test_rag_quality_fixtures.py`

**先写失败测试**：`tests/test_rag_quality_fixtures.py`

数据结构：

```json
{
  "id": "qa-0001",
  "query": "问题文本",
  "search_kb_ids": ["default"],
  "expected_answer": "参考答案",
  "relevant_documents": [
    {
      "kb_id": "default",
      "file_name": "example.md",
      "file_path": "data/default/example.md",
      "evidence": "原文证据片段"
    }
  ],
  "answerable": true,
  "difficulty": "medium",
  "tags": ["kb-directory-storage"],
  "status": "draft"
}
```

verified 额外要求：

- `status` 必须是 `verified`。
- `search_kb_ids` 非空。
- `relevant_documents` 非空。
- 每个 `relevant_documents[]` 必须包含 `kb_id`、`file_name`、`evidence`；如提供 `file_path`，必须通过安全路径校验。
- `relevant_documents[].file_path` 不允许位于 `tests/fixtures/rag_quality/`，fixture 文件本身也不允许进入 `data/`。

测试用例：

1. `draft.jsonl` 允许缺少证据，但必须有 `id`、`query`、`expected_answer`、`status=draft`。
2. `verified.jsonl` 缺少证据时校验失败。
3. 重复 `id` 校验失败。
4. fixture 文件路径不在 `data/` 下。
5. `relevant_documents[].file_path` 指向 `data/{kb_id}/` 或迁移前旧路径时只作为引用，不把 fixture 自身索引进知识库。

实现要求：

- 本阶段只做 fixture/schema 校验。
- 不执行嵌入质量评分。
- 不把用户后续提供的 Q/A 强行标记为 verified。
- 后续完整质量评测继续使用独立测试方案和测试报告承接。

命令：

```powershell
python scripts/validate_rag_quality_fixtures.py tests/fixtures/rag_quality/draft.jsonl tests/fixtures/rag_quality/verified.jsonl
python -m pytest tests/test_rag_quality_fixtures.py -q
```

预期：fixture 可被自动校验，且不会污染 `data/` 知识库内容。

### Task 9：文档、测试报告与开发故事

**目标文件**：

- `docs/project.md`
- `docs/guide/DOCS_INDEX.md`
- `docs/spec/knowledge_base_visibility_and_multi_kb_design.md`
- `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-plan.md`
- `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-report.md`
- `.interview-kit/dev-stories/` 或 `docs/interview/dev-stories/`

执行顺序：

1. 编码完成后，先创建 `20260714-kb-directory-storage-test-plan.md`，列出单元、集成、迁移、回归、人工验证用例，等待审核。
2. 测试方案审核通过后执行测试，并生成 `20260714-kb-directory-storage-test-report.md`。
3. 测试报告审核通过后，更新 `docs/project.md` 和 `docs/spec/knowledge_base_visibility_and_multi_kb_design.md` 的真实状态。
4. commit 前按仓库规则运行 `$dev-story-capture`，沉淀开发故事。
5. 开发故事完成后再进入 git stage/commit/push。

文档必须写清：

- `data/{kb_id}/` 已实现的范围。
- 向量索引仍是共享索引。
- 旧根目录文件迁移需要 dry-run、备份、校验和人工确认。
- QA fixture schema 已实现，但完整 RAG 质量指标仍需后续独立评测集成熟后执行。

## 5. 总测试命令

### 5.1 分任务命令

```powershell
python -m pytest tests/utils/test_file_kb_paths.py -q
python -m pytest tests/api/test_kb_directory_storage.py -q
python -m pytest tests/api/test_kb_docs_isolation.py -q
python -m pytest tests/api/test_kb_registry.py tests/api/test_kb_registry_atomic.py -q
python -m pytest tests/scripts/test_migrate_kb_directory_storage.py -q
python -m pytest tests/test_rag_quality_fixtures.py -q
```

### 5.2 现有多知识库回归

```powershell
python -m pytest tests/api/test_kb_registry.py tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py tests/api/test_agent_runtime.py -q
```

预期：现有 `55 passed` 基线不回归；如测试数量增加，以新增后的实际通过数为准。

### 5.3 后端全量回归

```powershell
python -m pytest tests -q
```

预期：全量通过；FastAPI `on_event` 弃用警告可记录为非阻断 warning。

### 5.4 文档和格式自检

```powershell
git diff --check
$blocked = @('TO' + 'DO', 'T' + 'BD', '??' + '??')
$paths = @('docs/20260714-kb-directory-storage/*.md', 'docs/project.md', 'docs/guide/DOCS_INDEX.md', 'docs/spec/knowledge_base_visibility_and_multi_kb_design.md', '评审建议.txt')
Get-ChildItem -Path $paths | Select-String -Pattern $blocked -SimpleMatch -CaseSensitive:$false
```

预期：`git diff --check` 无错误；禁用占位词检查无结果。

## 6. 验收标准

| 编号 | 验收项 | 标准 |
|---|---|---|
| AC-01 | KB 目录创建 | `POST /api/kb` 成功后存在 `data/{kb_id}/` |
| AC-02 | 导入前校验 | 未登记或 inactive KB 上传失败，且不产生落盘文件 |
| AC-03 | 文件归属 | 每个上传文件只出现在所属 `data/{kb_id}/` 中 |
| AC-04 | 索引路径 | `IndexManager.load_files()` 不再调用全局 `get_save_dir()` 拼路径 |
| AC-05 | metadata 完整 | 新节点包含正确 `kb_id`、`file_path`、`file_name` |
| AC-06 | 列表隔离 | 非 default KB 不显示旧无 `kb_id` 节点或其他 KB 文档 |
| AC-07 | 删除隔离 | 非 default 删除请求不能删除旧节点或其他 KB 文件 |
| AC-08 | KB 删除 | 非空 KB 返回 409；空 KB 删除 registry 和空目录 |
| AC-09 | registry 稳定性 | 并发更新不丢失，JSON 始终合法，`doc_count >= 0` |
| AC-10 | 迁移安全 | dry-run、备份、SHA256 校验、rollback 均有自动化测试；`--apply` 明确只迁移原始文件，不宣称索引迁移完成 |
| AC-11 | QA 防污染 | fixture 位于 `tests/fixtures/rag_quality/`，不会进入 `data/` |
| AC-12 | 回归测试 | 新增测试和现有多 KB 定向回归均通过 |

## 7. 风险与补偿

| 风险 | 影响 | 补偿 |
|---|---|---|
| 服务层落盘成功但索引失败 | 产生孤儿文件 | `import_files()` 捕获索引失败并删除本次新文件，`doc_count` 不增加 |
| registry 删除成功但目录删除失败 | KB 状态不一致 | 删除前保存 registry 项快照，目录删除失败则恢复 registry 并抛出一致性错误 |
| doc_count 与实际 docstore 不一致 | 误判非空状态 | 删除 KB 时以 `list_docs(kb_id)` 的实时 docstore 结果为主，`doc_count` 作为展示和辅助指标 |
| JSON registry 并发写覆盖 | 计数丢失或文件损坏 | 进程内锁 + 临时文件 + `os.replace()` |
| 旧节点无 `kb_id` | 污染非 default KB | 统一归入 default，非 default 列表/删除必须跳过 |
| 迁移时哈希不一致 | 数据损坏 | apply 后校验 SHA256；不一致中止并保留备份 |
| QA 范围过大 | 阶段延期 | 本阶段只做 fixture/schema 校验，完整质量评分另走测试方案 |

## 8. 执行门禁

1. 本实施方案评审通过后，才能进入编码。
2. 编码阶段必须按 Task 先写失败测试，再写实现。
3. Task 1 至 Task 8 全部完成后，才能创建测试方案。
4. 测试方案审核通过后，才能执行完整测试并生成测试报告。
5. 测试报告审核通过后，才能运行 `$dev-story-capture`、stage、commit、push。

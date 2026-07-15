# 多知识库目录化存储 FRD

- 日期：2026-07-14
- 状态：待评审
- 对应 PRD：`20260714-kb-directory-storage-prd.md`

## 1. 当前代码事实

| 能力 | 当前实现 | 代码位置 |
|---|---|---|
| KB 目录 | JSON registry | `server/kb_registry.py` |
| 创建/查询/更新/删除 KB | 已有 API | `api/routers/kb.py`、`api/services/kb_service.py` |
| 原始文件保存 | 全部写入 `data/` 根目录 | `server/utils/file.py`、`api/services/kb_service.py` |
| 索引管理 | 单个 `IndexManager`、单共享存储上下文 | `api/runtime.py`、`server/index.py` |
| 文档归属 | 节点 metadata 写入 `kb_id` | `server/index.py` |
| 范围查询 | `kb_ids` 传入后置过滤器 | `api/runtime.py`、`server/engine.py`、`server/kb_filter.py` |
| 当前文件布局 | 不按 KB 分目录 | `data/` |

因此，本需求不是从零实现多知识库，而是在已有逻辑多库基础上补齐原始文件目录归属和一致性约束。

## 2. 架构决策

### ADR-01 registry 仍是权威来源

`storage/kb_registry.json` 决定一个 `kb_id` 是否有效。`data/` 下即使出现手工创建目录，也不能自动成为知识库。

### ADR-02 一个知识库一个原始文件目录

目录固定为：

```text
data/{kb_id}/
```

目录名只能由服务端从校验后的 `kb_id` 生成。

### ADR-03 第一阶段继续共享向量索引

本阶段不创建多个 `IndexManager`，也不把 `storage/` 拆成多个 namespace。检索仍依靠 `kb_id` metadata；测试报告必须继续标注这是过渡架构。

### ADR-04 不静默级联删除非空知识库

删除非空知识库返回 409。原因是当前 registry、文件、docstore、vector store 之间没有数据库事务，静默级联容易产生无法恢复的半删除状态。

### ADR-05 正式问答集必须绑定证据

只有“问题 + 答案”不足以判断 RAG 是否正确。正式用例还必须绑定目标 KB、目标文件和证据片段；未完成绑定的记录只作为草稿。

## 3. 模块设计

### 3.1 `server/utils/file.py`

新增或调整以下职责：

```python
def validate_kb_id(kb_id: str) -> str:
    """校验并返回规范化的知识库 ID。"""


def get_kb_save_dir(kb_id: str) -> Path:
    """返回 data/{kb_id} 的安全绝对路径。"""


def ensure_kb_save_dir(kb_id: str) -> Path:
    """校验后创建知识库目录。"""


def resolve_kb_file_path(kb_id: str, filename: str) -> Path:
    """生成位于目标 KB 目录内的安全文件路径。"""
```

路径校验规则：

- `kb_id` 正则建议使用：`^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`。
- 拒绝 `.`、`..`、斜杠、反斜杠、盘符、UNC 路径和 Windows 保留名称。
- 使用 `Path.resolve()` 后确认最终路径属于 `DATA_ROOT / kb_id`。

### 3.2 `api/services/kb_service.py`

#### 创建知识库

```text
校验 kb_id
  -> registry 检查重复
  -> 创建 data/{kb_id}/
  -> 写入 registry
  -> 任一步失败则回滚本次创建的空目录或 registry 项
```

目录只允许删除本次调用创建的空目录，不允许递归删除。

#### 文件导入

```text
校验 registry 中 kb_id 存在且 active
  -> 获取 data/{kb_id}/
  -> 校验文件大小和安全文件名
  -> 写入唯一文件名
  -> 调用 IndexManager 读取明确的 file_paths
  -> 索引成功后更新 doc_count
```

需要把当前 `get_save_dir()` 的全局根目录依赖改为显式 KB 目录，避免 `kb_service` 保存到一个目录、`IndexManager` 又从另一个目录拼接路径。

#### 删除知识库

```text
registry 不存在 -> 404
文档数或文件目录非空 -> 409
空库 -> 删除 registry 项 -> 删除空目录
```

如果 registry 删除成功但空目录删除失败，应恢复 registry 或返回需要人工修复的一致性错误，不能假装成功。

### 3.3 `server/index.py`

当前 `load_files()` 会再次调用全局 `get_save_dir()` 并拼接上传文件名。建议改为接收服务层已经确定的文件路径：

```python
def load_files(
    self,
    file_paths: list[str | Path],
    chunk_size: int,
    chunk_overlap: int,
    kb_id: str,
):
    ...
```

节点 metadata 至少保证：

```json
{
  "kb_id": "product-docs",
  "file_name": "product-guide.pdf",
  "file_path": ".../data/product-docs/product-guide_xxxxxxxx.pdf"
}
```

### 3.4 `server/kb_registry.py`

registry 保持纯目录数据职责，不直接承担文件内容删除。建议补充：

- `status` 校验；
- 原子写入：先写临时文件，再替换正式 JSON；
- `doc_count` 不得降到负数；
- 同一逻辑事务内避免 `_read()` / `_write()` 分别加锁造成并发更新丢失。

### 3.5 `api/routers/kb.py`

错误映射要求：

| 场景 | HTTP 状态 |
|---|---:|
| 非法 `kb_id` | 400 |
| 未登记知识库导入 | 400 |
| 重复创建 | 409 |
| 查询不存在知识库 | 404 |
| 删除非空知识库 | 409 |
| 嵌入模型不可用 | 503 |
| 文件过大 | 400 |

### 3.6 文档列表和删除

严格归属规则：

```python
doc_kb_id = metadata.get("kb_id") or "default"
if requested_kb_id is not None and doc_kb_id != requested_kb_id:
    continue
```

这意味着无 `kb_id` 的旧数据只兼容归入 `default`，不能在任意非默认库查询时继续被保留。

删除文档分为两个动作：

1. 从索引/docstore 删除对应 ref doc；
2. 在安全路径校验通过后删除源文件。

第一阶段实现计划必须明确两个动作失败时的补偿和报告方式，不能只删除 registry 计数。

## 4. 查询链路边界

当前链路：

```text
QueryRequest.kb_ids
  -> RuntimeState.build_query_engine(kb_ids)
  -> SimpleFusionRetriever 在共享语料中取 top_k
  -> KBIdFilter 后置过滤
  -> LLM 生成答案
```

已知风险：如果目标知识库的候选在共享语料全局 `top_k` 之外，后置过滤可能把其他库结果删掉后留下过少甚至零个节点。

本需求第一阶段不把目录化改造包装成检索隔离修复。测试必须单独记录：

- 单库检索命中率；
- 多库联合查询命中率；
- 过滤后的候选数量；
- 是否出现“目标库有相关文档，但全局 top_k 后置过滤未召回”的情况。

若该风险在真实样本中出现，下一阶段在以下方案中评审选择：

1. 检索前 metadata filter；
2. 按 KB 建立候选 docstore/BM25 范围；
3. `storage/kbs/{kb_id}/` 独立索引。

## 5. 存量迁移设计

### 5.1 迁移前检查

- 备份 `data/`、`storage/`、`storage/kb_registry.json`。
- 输出根目录文件清单、大小和 SHA256。
- 输出当前 docstore 中 `file_path`、`kb_id` 分布。
- dry-run 只生成计划，不移动文件。

### 5.2 首选迁移

开发环境优先采用完整重建：

1. 创建并确认 `data/default/`；
2. 将现有根目录原始文件纳入默认库重导清单；
3. 重建索引，使 metadata 使用新路径和 `kb_id=default`；
4. 验证文档数、节点数、文件哈希和固定查询；
5. 人工确认后再处理旧索引和旧文件。

任何递归移动或删除操作都必须先单独评审目标绝对路径和回滚方案。

## 6. 问答评测集设计

### 6.1 两级状态

- `draft`：用户已提供问题/参考答案，但证据尚未绑定或未复核。
- `verified`：目标 KB、目标文件、证据片段、可回答性都已人工确认。

### 6.2 固定存储位置与防污染规则

评测数据固定保存在仓库测试 fixture 中：

```text
tests/fixtures/rag_quality/
  draft.jsonl
  verified.jsonl
```

- `draft.jsonl`：保存用户已提供但尚未完成证据绑定或人工确认的记录。
- `verified.jsonl`：只保存目标 KB、目标文件、证据片段和可回答性均已确认的正式回归记录。
- 评测集**不得放入** `data/{kb_id}/`、知识库上传目录或任何会被导入器扫描的位置。
- 评测运行时只能把 `query` 作为查询输入，不能把 `expected_answer` 或 `evidence` 注入被测知识库，避免答案泄漏和测试集污染。
- fixture 必须版本化；临时运行输出、模型回答和指标报告应写入测试报告约定的输出目录，不回写 verified ground truth。

### 6.3 用例类型

| 类型 | 目标 |
|---|---|
| 单库可回答 | 验证指定 KB 的检索和回答 |
| 多库可回答 | 验证跨多个 KB 聚合证据 |
| 错库干扰 | 验证相似内容不会越库 |
| 无答案 | 验证拒答而不是编造 |
| 同名文件 | 验证不同 KB 的相同文件名不冲突 |
| 长文档/跨段 | 验证分块边界和多片段组合 |

### 6.4 指标分层

检索层：

- Recall@1、Recall@3、Recall@5；
- MRR；
- 正确证据 KB 命中率；
- 跨库污染率；
- 过滤后候选数。

生成层：

- 关键事实正确率；
- 答案完整性；
- 引用文件和 KB 正确率；
- 无答案拒答率；
- 人工复核结论。

## 7. 异常与一致性

| 失败点 | 处理原则 |
|---|---|
| 目录创建失败 | 不写 registry |
| registry 写入失败 | 删除本次新建的空目录 |
| 文件写入失败 | 不调用索引，不更新计数 |
| 索引失败 | 返回失败，不更新计数；保留或隔离源文件并记录状态 |
| registry 计数更新失败 | 导入结果标记部分成功并记录修复信息 |
| 文档删除后文件删除失败 | 报告部分失败，保留可恢复证据 |
| 非法路径 | 立即拒绝，不触碰文件系统 |

## 8. 完成定义

本阶段方案评审通过后，实施计划必须给出：

1. 精确改动文件和函数；
2. 先写哪些失败测试；
3. 存量迁移脚本的 dry-run 和备份命令；
4. API、服务层、文件系统和端到端测试命令；
5. 正常路径与异常路径的预期结果；
6. 如何验证不同 KB 同名文件、未知 KB、非空 KB 删除和旧数据归属；
7. 如何更新 `docs/project.md`、设计文档、测试报告和开发故事。

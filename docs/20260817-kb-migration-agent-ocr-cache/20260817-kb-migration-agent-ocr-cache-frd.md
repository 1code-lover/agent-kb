# 历史迁移、OCR 基准、只读 Agent 与 Embedding 下载控制 FRD

## 1. 总体架构

新增四组边界清晰的模块：

- `api/services/kb_migration_service.py` + `api/routers/kb_migration.py`
- `server/readers/ocr_layout.py`（从现有 OCR 后处理抽取可测试的连续表格逻辑）及 OCR 基准工具
- `api/services/access_token_service.py` + `api/services/open_api_service.py` + `api/routers/open_api.py`
- 扩展 `api/services/embedding_cache_service.py` 和 `api/routers/embedding_cache.py`

前端在知识库页增加“升级与模型”区域，包含迁移卡片、令牌管理卡片和 Embedding 下载控制。

## 2. 历史迁移设计

### 2.1 持久化目录

```text
storage/
  docstore.json                         # 历史/default
  kbs/{kb_id}/                          # 新物理隔离索引
  migrations/
    migration-state.json                # 当前及历史批次摘要
    backups/{batch_id}/storage/         # 历史索引备份
    backups/{batch_id}/manifest.json    # SHA-256 清单与本批次创建目录
    plans/{batch_id}.json               # 迁移计划与校验结果
    work/{batch_id}/{kb_id}/             # 同文件系统临时重建目录
    rollback/{batch_id}/{kb_id}/         # 回滚隔离目录
```

备份复制时排除 `storage/kbs/` 和 `storage/migrations/`，避免递归复制。

### 2.2 扫描算法

1. 使用默认 `IndexManager` 加载历史索引。
2. 从 `index.index_struct.nodes_dict` 获得有效节点 ID，避免迁移 docstore 陈旧节点。
3. 对每个节点读取 metadata：
   - `kb_id == default`：保留；
   - 合法且 KB registry 中 active：进入分组；
   - 缺失/非法/未知：进入 anomalies。
4. 以 `ref_doc_id` 统计文档数；统计 `embedded_node_count` 与 `missing_embedding_count`；对按 node_id 排序后的 `node_id + text hash + metadata canonical json` 生成源摘要。
5. 缺失 embedding 时计划标记 `blocked_missing_embeddings`；只有请求明确传入 `recompute_missing_embeddings=true` 才进入重算模式。
6. 检查目标目录是否已有有效索引和目标摘要。

### 2.3 执行算法

- 执行前重新扫描并校验 `plan_digest`，防止来源在预览后发生变化。
- 创建备份和 manifest，验证复制后的哈希。
- 每个 KB：
  1. 目标为空时，在 `storage/migrations/work/{batch_id}/{kb_id}` 创建独立 manager；
  2. 复制节点对象并保留 embedding；缺 embedding 且未允许重算时拒绝该 KB，允许重算时由目标 manager 重新生成 embedding；
  3. 调用 `insert_nodes(..., persist=False)`，最后单次 `persist_storage()`；
  4. 从临时目录重新加载目标并计算校验摘要；
  5. 摘要一致后在同一文件系统原子 rename 到 `storage/kbs/{kb_id}`，并把创建目录写入 manifest；
  6. 任一步失败都隔离临时目录，不留下可被 runtime 加载的半成品。
- 目标已有完全相同摘要时标记 `already_migrated`；非空但不一致时标记冲突并拒绝覆盖。
- 状态落盘后再更新内存状态。历史来源不删除、不改写。回滚将本批次创建的目标目录移动到 `rollback/{batch_id}`，而不是覆盖历史来源。

### 2.4 API

- `GET /api/kb/migration/status`
- `POST /api/kb/migration/scan`
- `POST /api/kb/migration/start`：`plan_digest`、可选 `kb_ids`、`retry_failed_only`、`recompute_missing_embeddings`
- `POST /api/kb/migration/rollback`：`batch_id`

迁移为后台串行任务，状态字段包括 `state`、`batch_id`、`plan_digest`、`current_kb_id`、`completed_kb_count`、`total_kb_count`、`results`、`anomalies`、`last_error`。

## 3. OCR 连续表格与基准设计

### 3.1 统一布局对象

OCR 行标准化为：

```python
{
  "text": str,
  "confidence": float | None,
  "box": {"x1": float, "y1": float, "x2": float, "y2": float},
  "page": int,
}
```

表格块包含列中心、列数、行、页码和是否含表头。

### 3.2 合并规则

- 同页：列数相等、列中心归一化距离小于阈值、垂直间距不超过中位行高的配置倍数时合并；检测到普通段落即建立硬边界。
- 跨页：仅比较上一页页尾表格与下一页页首表格；列数相等、列中心匹配；下一页首行与上一页表头标准化文本相似时去除重复表头。
- 任一候选行跨列宽度异常或与列中心不匹配时，按普通文本输出，防止段落被并入。
- `[Page N]` 标记保留在每页边界；跨页表格在下一页标记后继续输出数据行。

### 3.3 基准

- `tests/fixtures/ocr_real_scan/manifest.json` 保存样本、来源类型（`captured` 或 `synthetic_degradation`）、金标、阈值。
- 仓库纳入小型自制扫描/拍摄资产；`scripts/build_ocr_scan_benchmark.py` 另从本仓库自制文本/表格生成带噪声、倾斜、低对比 PNG/PDF。
- `scripts/eval_ocr_scan_benchmark.py` 可使用记录好的 OCR 原始结果离线评估后处理，也可显式选择真实 OCR runtime。
- 默认测试不依赖 PaddleOCR 模型下载，使用固定 OCR 行结果验证布局算法；slow 标记执行真实 runtime 基准。

## 4. 开放接口与令牌设计

### 4.1 令牌格式

明文格式：`nak_ro_<token_id>_<random_secret>`。`token_id` 便于定位记录，`random_secret` 使用 `secrets.token_urlsafe(32)`。

磁盘记录：

```json
{
  "token_id": "...",
  "name": "...",
  "secret_hash": "HMAC-SHA256",
  "prefix": "nak_ro_abc...",
  "kb_ids": ["finance"],
  "status": "active",
  "created_at": "...",
  "expires_at": "...",
  "revoked_at": null,
  "last_used_at": null
}
```

摘要密钥从 `THINKRAG_TOKEN_PEPPER` 获取；桌面运行时若未设置则在运行数据目录生成 `token-pepper` 文件（`0600`）。比较使用 `hmac.compare_digest`。

### 4.2 管理鉴权

管理路由位于 `/api/access-tokens`，要求请求来自 loopback 且 `X-ThinkRAG-Admin-Key` 与 `THINKRAG_ADMIN_KEY` 或本地生成的管理密钥匹配。管理密钥不会返回到 Web 内容；桌面主进程通过启动环境注入前端安全桥接所需的一次性会话值。开发模式允许通过环境固定值测试。

长期管理员密钥不得进入普通 Web 渲染器。本阶段提供 `scripts/manage_access_tokens.py` 通过 loopback 管理 API 或直接本地服务创建、列出、撤销令牌；Web 仅展示开放 API 是否启用及安全说明，不保存或发送管理员密钥。

### 4.3 开放路由

- `GET /api/open/v1/me`
- `GET /api/open/v1/knowledge-bases`
- `POST /api/open/v1/search`
- `POST /api/open/v1/answer`

鉴权依赖解析 Bearer token，并把授权上下文注入路由。请求必须显式传一个 `kb_id`。`search` 返回结构化命中与证据；`answer` 复用现有只读知识问答服务，但固定知识范围，忽略任何命令/文件模式。

### 4.4 审计

追加 JSONL 到运行数据目录 `logs/open-api-audit.jsonl`，仅记录 token_id、路由、kb_id、status_code、duration_ms、request_id 和时间。日志写入锁保护。

## 5. Embedding 下载控制设计

### 5.1 下载适配器

将现有脚本调用封装为可注入的 `EmbeddingDownloadAdapter`：

- `resolve_target(model_name)`：返回缓存目录和预估字节；
- `prepare(..., progress_callback, cancel_event, temp_dir)`：分阶段报告进度并在安全检查点检查取消；
- 成功后原子移动临时结果或验证第三方下载结果。

ModelScope 适配器优先读取远端模型文件元数据总大小；无法获得时使用配置保守值 `THINKRAG_EMBED_REQUIRED_BYTES`，默认 2 GiB。预检要求 `free_bytes >= required_bytes + max(required_bytes * 0.2, 512 MiB)`。

### 5.2 状态机

```text
idle -> checking_space -> downloading -> verifying -> ready
                         -> cancelling -> cancelled
                         -> failed
```

状态增加：`phase`、`bytes_downloaded`、`bytes_total`、`progress_percent`、`progress_mode`、`current_file`、`free_bytes`、`required_bytes`、`cancel_requested`、`updated_at`。下载期间周期采样缓存/临时目录实际落盘字节；总量来自远端元数据时为 `exact`，来自保守配置时为 `estimated`，完成校验前不得报告 100%。

### 5.3 API

- `GET /api/embedding/cache`
- `POST /api/embedding/cache/preflight`
- `POST /api/embedding/cache/prepare`
- `POST /api/embedding/cache/cancel`

取消接口幂等；非运行状态返回当前状态和 `cancel_requested=false`。

## 6. 前端设计

- 新增 API 模块与纯领域函数测试。
- Embedding 卡片显示空间检查、阶段、进度条、文件名、取消/重试。
- 知识库迁移卡片仅在扫描发现候选或历史批次存在时显示，必须先预览计划再允许执行。
- 迁移执行前明确提示已备份但可能占用额外磁盘空间。

## 7. 错误处理与安全

- `400`：参数/计划不匹配；`401`：开放令牌无效；`403`：KB 越权或管理鉴权失败；`409`：任务冲突/目标索引冲突；`507`：磁盘空间不足；`503`：模型或索引 runtime 不可用。
- 所有路径通过现有 `validate_kb_id` 和受控根目录解析。
- 不接受任意 URL、provider、备份路径、缓存目标路径或 shell 命令。

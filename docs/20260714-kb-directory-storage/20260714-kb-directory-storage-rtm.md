# 多知识库目录化存储 RTM

- 日期：2026-07-14
- 状态：第三轮评审通过，P2 已修订，进入编码阶段
- 对应 PRD：`20260714-kb-directory-storage-prd.md`
- 对应 FRD：`20260714-kb-directory-storage-frd.md`

## 1. 需求追踪

| 需求 ID | 需求 | 计划实现入口 | 验证方式 | 验收结果 |
|---|---|---|---|---|
| FR-01 | 创建 KB 时创建 `data/{kb_id}/` | `api/services/kb_service.py`、`server/utils/file.py` | 服务层测试、API 测试 | registry 和目录同时存在 |
| FR-01 | 默认 KB 目录初始化 | `api/runtime.py`、`api/services/kb_service.py` | 启动测试 | `data/default/` 存在 |
| FR-01 | 删除空 KB 时删除空目录 | `api/services/kb_service.py` | 服务层测试、API 测试 | registry 项和空目录同时删除 |
| FR-01 | 非空 KB 禁止删除 | `api/services/kb_service.py`、`api/routers/kb.py` | API 异常测试 | 返回 409，文件和 registry 不变 |
| FR-02 | `kb_id` 路径安全校验 | `api/schemas/kb.py`、`server/utils/file.py` | 参数化单元测试 | 路径穿越和保留名称被拒绝 |
| FR-02 | 最终路径边界检查 | `server/utils/file.py` | 单元测试 | 文件不能写出 `data/{kb_id}/` |
| FR-03 | 导入前检查 KB 有效状态 | `api/services/kb_service.py` | API 测试 | 未登记/停用 KB 返回 400 |
| FR-03 | 文件保存到 KB 独立目录 | `api/services/kb_service.py`、`server/index.py` | 集成测试 | 文件路径含正确 `kb_id` 目录 |
| FR-03 | 节点 metadata 完整 | `server/index.py` | 索引单元/集成测试 | `kb_id/file_name/file_path` 正确 |
| FR-03 | 索引失败不增加计数 | `api/services/kb_service.py` | 故障注入测试 | `doc_count` 不变，返回明确错误 |
| FR-04 | 文档列表严格按 KB 隔离 | `api/services/kb_service.py` | API 测试 | 不跨库，不把旧无标签节点混入非默认库 |
| FR-04 | 文档删除限制 KB 范围 | `api/services/kb_service.py` | API 测试 | 不能删除其他 KB 的文档 |
| FR-04 | 安全删除源文件 | `api/services/kb_service.py`、`server/utils/file.py` | 文件系统测试 | 只删除目标 KB 内文件 |
| FR-05 | registry/目录创建失败回滚 | `api/services/kb_service.py` | 故障注入测试 | 无半创建状态 |
| FR-05 | registry 原子写入与计数下限 | `server/kb_registry.py` | 并发/单元测试 | JSON 始终合法，计数不为负 |
| FR-06 | 根目录旧文件迁移到 default | `scripts/migrate_kb_directory_storage.py` | dry-run、迁移测试 | 本阶段验收原始文件迁移安全：计划、备份、SHA256、移动和 rollback 一致；索引 metadata/query 一致性需在重导或重建索引后作为后续验收 |
| FR-07 | 问答草稿数据结构 | `tests/fixtures/rag_quality/draft.jsonl` 和校验脚本 | schema 校验测试 | 必填字段完整、ID 唯一 |
| FR-07 | 正式用例必须绑定证据 | `tests/fixtures/rag_quality/verified.jsonl` 和校验脚本 | 负向测试 | 无证据记录不能标记 verified |
| FR-07 | 评测集与知识库数据隔离 | fixture 路径校验 | 目录与配置测试 | fixture 不位于 `data/`，不会被导入索引 |
| FR-07 | 多知识库质量指标 | 后续评估脚本 | 固定数据集回归 | 输出检索、答案、跨库污染指标 |

## 2. 场景用例

| 用例 ID | 场景 | 前置条件 | 操作 | 预期结果 |
|---|---|---|---|---|
| TC-01 | 创建第一个 KB | registry 无 `product-docs` | `POST /api/kb` | 返回成功，创建 `data/product-docs/` |
| TC-02 | 重复创建 KB | KB 已存在 | 再次创建同 ID | 返回 409，不改变目录 |
| TC-03 | 非法 KB ID | 无 | 创建 `../escape` | 返回 400，不在 `data/` 外创建路径 |
| TC-04 | 两库上传同名文件 | `kb-a`、`kb-b` 已存在 | 各上传 `guide.pdf` | 文件分别位于两个目录，不覆盖 |
| TC-05 | 未登记 KB 上传 | KB 不存在 | 上传文件 | 返回 400，不产生文件和索引节点 |
| TC-06 | 索引失败 | 嵌入调用故障注入 | 上传文件 | 返回失败，`doc_count` 不增加 |
| TC-07 | 单库文档列表 | 两库都有文档 | 查询 `kb-a` | 只返回 `kb-a` 文档 |
| TC-08 | 越库删除 | 文档属于 `kb-b` | 用 `kb-a` 范围删除 | 删除数为 0，文件和节点保留 |
| TC-09 | 删除非空 KB | KB 有文档 | `DELETE /api/kb/{kb_id}` | 返回 409，不删除任何数据 |
| TC-10 | 删除空 KB | KB 无文档且目录为空 | 删除 KB | registry 和空目录消失 |
| TC-11 | 旧无标签数据 | 旧节点无 `kb_id` | 查询非 default KB | 旧节点不进入结果 |
| TC-12 | 单库检索 | 两库有相近内容 | 指定 `kb_ids=[kb-a]` | 来源只包含 `kb-a` |
| TC-13 | 多库联合检索 | 两库各含一个必要事实 | 指定 `kb_ids=[kb-a,kb-b]` | 两库正确证据均可召回 |
| TC-14 | 错库干扰 | `kb-b` 有高度相似干扰项 | 仅查询 `kb-a` | 无 `kb-b` 来源 |
| TC-15 | 问答草稿入集 | 用户仅提供 Q/A | 转换为 draft | 允许保存，但不能标记 verified |
| TC-16 | 问答证据确认 | 已绑定 KB、文件、片段 | 标记 verified | schema 校验通过，可进入回归 |
| TC-17 | 无答案问题 | 目标库无证据 | 执行问答 | 拒答，不生成虚构来源 |

## 3. 质量门槛建议

正式门槛需在真实数据达到至少 50 条后评审确认。初始建议监控：

| 维度 | 指标 |
|---|---|
| 目录一致性 | registry 与 KB 目录一致率 100% |
| 路径安全 | 路径穿越用例阻断率 100% |
| 单库隔离 | 跨库来源污染率 0% |
| 检索召回 | Recall@1、Recall@3、Recall@5、MRR |
| 多库检索 | 目标 KB 命中率、过滤后候选数 |
| 答案正确性 | 关键事实正确率、完整性 |
| 引用正确性 | KB、文件、证据片段匹配率 |
| 无答案能力 | 拒答率、虚构来源率 |

## 4. 阶段追踪

| 阶段 | 产物 | 当前状态 |
|---|---|---|
| 开发方案 | PRD、FRD、RTM | 已评审，要求补齐实施方案 |
| 实施方案 | Plan | 已按第二轮评审修订，待复审 |
| 编码 | TDD 实现 | 未开始 |
| 测试方案 | Test Plan | 未开始 |
| 测试执行 | Test Report | 未开始 |
| 提交推送 | commit / push | 未开始 |

基线说明：2026-07-14 已执行

```powershell
python -m pytest tests/api/test_kb_registry.py tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py tests/api/test_agent_runtime.py -q
```

结果为 `55 passed, 2 warnings in 4.54s`。该结果只证明**当前 registry + 共享索引 + `kb_id` metadata 过滤的逻辑多库链路**没有回归，不代表 `data/{kb_id}/`、严格文件归属、迁移或正式 QA fixture 已经实现和测试通过。

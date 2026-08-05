# 本地多知识库知识助手平台 v0.2 测试方案（Stage 5，扩展 QA 基线）

日期：2026-07-31  
版本：v0.6  
对应测试报告：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-report.md`

## 1. 文档目的
本方案用于把“本地多知识库知识助手”当前 P0 基础链路的测试范围、执行顺序、质量指标、通过门槛和报告要求写清楚，确保后续不只是看到 `pytest passed`，而是能系统回答下面四个问题：
1. Markdown / PDF / 图片 OCR 的导入与问答链路是否可执行；
2. 单库问答范围契约是否稳定，是否仍坚持 default-deny；
3. evidence / preview / 资产对象 / 文件夹路径这些关键对象是否有回归保护；
4. 本轮测试是否产出可复核的指标、覆盖率快照和测试报告。

## 2. 固定产品口径
本轮测试基于以下冻结决议设计，不能再回退到旧口径：
1. 多知识库现状仍是**共享单索引 + `metadata["kb_id"]` 逻辑过滤**，不是物理隔离；
2. chat 查询范围契约采用 **default-deny**：未声明 `kb_ids` = 拒绝；
3. KB 是授权边界，folder 只是组织层，不是授权边界；
4. 图片策略当前只验证 **OCR 提取 + 图片资产入库**，不把深度图像理解 / VQA / 流程图语义理解纳入本轮结论；
5. 当前 QA 结论只证明“基础链路可回归、可评测”，不等价于真实 embedding 检索效果或真实大模型最终回答质量已完成评测。

## 3. 测试目标
### 3.1 P0 基础链路目标
1. 文档可被导入知识库，并保留 KB 内部文件夹层级；
2. 单库范围问答可命中正确文档，并返回 evidence；
3. preview 可依据 evidence 回跳到正确文档片段；
4. 无证据时可拒答且不伪造来源；
5. 图片 OCR / PDF OCR 至少具备可观测的解析质量下限；
6. QA 结果可通过 suite 指标、覆盖率快照和测试报告持续追踪。
7. 疑似 follow-up 问题在同 session 下至少具备最小 history-grounded 检索能力，且不破坏 scope 契约。

### 3.2 不在本轮证明范围内
1. 多知识库物理隔离；
2. 外部 Agent 接入后的完整授权模型；
3. 真实 embedding 召回率对比；
4. 真实多模态图像理解质量；
5. 多用户组织权限系统。

## 4. 测试分层与文件清单
| 分层 | 文件 | 关注点 |
|---|---|---|
| Contract | `tests/api/test_chat_scope_contract.py` | default-deny、单库 scope echo、KB active 校验 |
| Contract | `tests/api/test_chat_evidence_contract.py` | evidence 结构、`doc_id`、`preview_locator` 契约 |
| Contract | `tests/api/test_chat_service.py` | 最小 follow-up、source 归一化、问答后处理 |
| Contract | `tests/api/test_session_store.py` | `session_id` 落盘安全、评测 session 持久化 |
| Contract | `tests/api/test_health_route.py` | 基础服务健康检查 |
| Infra | `tests/test_logging_utils.py` | `session.log` 句柄释放、临时目录清理 |
| Import / Storage | `tests/api/test_kb_directory_storage.py` | KB 内部 `folder_path / relative_path` 持久化与回显 |
| Import / Storage | `tests/api/test_image_asset_import.py` | 图片资产登记、OCR 文本入库、receipt 结构 |
| Smoke QA | `tests/api/test_chat_single_kb_qa_smoke.py` | 单库问答最小闭环 |
| Semi-real QA | `tests/api/test_chat_markdown_qa_semireal.py` | Markdown 导入 -> 问答 -> evidence -> preview |
| Semi-real QA | `tests/api/test_chat_pdf_semireal.py` | PDF text-layer 导入 -> 问答 -> evidence -> preview |
| Semi-real QA | `tests/api/test_chat_image_ocr_semireal.py` | 图片 OCR 文本入库 -> 问答 -> evidence -> preview |
| Metrics | `tests/api/chat_qa_metrics.py` | QA case report 与 suite summary 计算 |
| Metrics | `tests/api/test_chat_qa_metrics.py` | 指标计算正确性 |
| Fixture Governance | `tests/test_rag_quality_fixtures.py` | semireal fixture schema、类别分布、no-evidence 约束 |
| Reader | `tests/readers/test_image_ocr.py` | image OCR 成功 / 无文本 / 缺依赖 / 运行失败 / warmup |
| Reader | `tests/readers/test_pdf_ocr.py` | PDF text-layer、OCR fallback、blank、scanned slow-path |

## 5. 套件规模与覆盖维度
### 5.1 QA case 总规模
本轮 QA 层共维护 **23 个问答 case**：
- Smoke QA：6 个
- Markdown semi-real：8 个
- PDF semi-real：5 个
- image OCR semi-real：4 个

### 5.2 QA 类别分布
23 个 case 的类别分布如下：
- `fact`：4
- `architecture`：4
- `policy`：3
- `no-evidence`：3
- `metrics`：3
- `positive`：3
- `summary`：1
- `roadmap`：1
- `negative-policy`：1

### 5.3 测试维度
每个 suite 至少从以下维度看结果：
1. **范围正确性**：scope echo 是否正确、是否仍 default-deny；
2. **事实覆盖**：回答是否覆盖 `expected_keypoints`；
3. **证据可追溯**：是否命中期望来源，是否返回 `doc_id` 与 `preview_locator`；
4. **预览可解析**：需要 preview 的 case 能否实际解析到证据片段；
5. **拒答纪律**：无证据时是否拒答，是否避免出现禁止词；
6. **解析稳定性**：OCR / PDF reader 在缺依赖、无文本、fallback、blank 等路径是否可观测；
7. **会话稳定性**：follow-up 历史注入、Windows `session_id` 文件名兼容、日志句柄释放是否可靠。

## 6. 质量指标与门槛
### 6.1 Suite 级指标
本轮报告必须输出以下指标：
- `pass_rate`
- `scope_pass_rate`
- `average_keypoint_coverage`
- `evidence_hit_rate`
- `preview_resolvable_rate`（只对需要 preview 的 case 计算）
- `source_count_match_rate`
- `forbidden_term_clean_rate`
- `category_breakdown`

### 6.2 通过门槛
1. Contract / Import / Storage / Reader 层：测试必须全部通过；
2. QA suite summary：
   - `pass_rate = 1.0`
   - `scope_pass_rate = 1.0`
   - `average_keypoint_coverage = 1.0`
   - `evidence_hit_rate = 1.0`
   - `source_count_match_rate = 1.0`
   - `forbidden_term_clean_rate = 1.0`
3. 对 evidence-backed case，`preview_resolvable_rate = 1.0`；
4. 允许存在已知非阻断 warning / skip，但必须在测试报告中单独说明原因与影响；
5. 覆盖率快照必须进入测试报告，至少记录总快照和核心链路文件覆盖率。

## 7. 详细执行方案
### 7.1 单独验证新增 suite
#### 7.1.1 PDF semi-real
命令：
`python -m pytest tests/api/test_chat_pdf_semireal.py -q`

预期：
1. 8 个测试全部通过；
2. PDF text-layer 文本可被导入并命中；
3. 无证据问题可稳定拒答；
4. suite summary 为 1.0。

#### 7.1.2 image OCR semi-real
命令：
`python -m pytest tests/api/test_chat_image_ocr_semireal.py -q`

预期：
1. 7 个测试全部通过；
2. OCR 文本入库后可被问答命中；
3. 资产对象与 evidence / preview 契约一致；
4. 无证据问题可稳定拒答；
5. suite summary 为 1.0。

#### 7.1.3 follow-up / session 稳定性
命令：
`python -X utf8 -m pytest tests/test_logging_utils.py tests/api/test_session_store.py tests/api/test_chat_service.py tests/api/test_chat_eval_runner.py -q`

预期：
1. 所有测试通过，当前基线为 **33 passed**；
2. 疑似 follow-up 问题会使用同 session 最近历史补足检索问句；
3. `eval::...` 等 Windows 非法文件名字符不会导致 session 落盘失败；
4. `session.log` 不持有长期文件句柄，临时评测目录可被正常清理。

### 7.2 扩展回归总套件
命令：
`python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_markdown_qa_semireal.py tests/api/test_chat_single_kb_qa_smoke.py tests/api/test_chat_pdf_semireal.py tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py tests/api/test_health_route.py tests/api/test_image_asset_import.py tests/api/test_kb_directory_storage.py tests/test_rag_quality_fixtures.py tests/readers/test_image_ocr.py tests/readers/test_pdf_ocr.py -q`

预期：
1. 全部阻断性测试通过；
2. 允许 1 条 scanned-PDF slow-path skip；
3. 允许 2 条 FastAPI `on_event` deprecation warning；
4. 不允许新增 error / xfail / flaky retry；
5. 总结果应稳定落在当前基线 **124 passed, 1 skipped, 2 warnings**。

### 7.3 覆盖率快照
命令：
`python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_markdown_qa_semireal.py tests/api/test_chat_single_kb_qa_smoke.py tests/api/test_chat_pdf_semireal.py tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py tests/api/test_health_route.py tests/api/test_image_asset_import.py tests/api/test_kb_directory_storage.py tests/test_rag_quality_fixtures.py tests/readers/test_image_ocr.py tests/readers/test_pdf_ocr.py --cov=api/services --cov=api/routers --cov=server/readers --cov-report=term`

预期：
1. 总快照进入报告，不把单一总覆盖率当作唯一门槛；
2. 重点观察核心链路文件：`query_scope.py`、`chat_service.py`、`kb_service.py`、`asset_service.py`、`evidence_service.py`、`health.py`、`image_ocr.py`、`pdf_ocr.py`；
3. 报告中必须解释“为什么总覆盖率 62% 不能单独解读”；
4. 若核心链路覆盖率明显回退，必须在报告中列为风险项。

## 8. 结果记录要求
### 8.1 测试报告必须包含
1. 执行环境（Python / pytest / 插件 / 工作目录）；
2. 实际执行命令与真实结果；
3. 按文件列出的 collected 数量；
4. Smoke / Markdown / PDF / image OCR 四个 suite 的 summary 指标表；
5. Reader 层结论、skip / warning 说明；
6. 覆盖率总快照与核心文件覆盖率表；
7. 风险、边界和下一步建议；
8. 最终结论必须明确说明“证明了什么，没有证明什么”。

### 8.2 报告判定口径
测试报告写作时，必须遵守以下原则：
1. 只写**真实执行结果**，不能写计划数字；
2. 区分“基础链路可回归”与“最终检索/问答效果优秀”；
3. 不把逻辑隔离写成物理隔离；
4. 不把 OCR 支持写成完整图像理解；
5. 不把 deterministic semi-real QA 写成真实生产效果基准。

## 9. 当前结论预期
如果本方案全部执行通过，则可以合理得出以下阶段性结论：
1. 本地知识库助手已经具备 Markdown / PDF text-layer / 图片 OCR 的最小可回归导入与问答链路；
2. 单库问答的范围契约、evidence 契约和 preview 契约已经有系统级保护；
3. 文件夹层级、图片资产、Reader 解析层和 QA 指标层已经被纳入统一测试基线；
4. 项目已经不再只是“能跑起来”，而是开始形成**可持续回归、可追踪质量、可扩展到后续 Agent 接入**的知识底座测试体系。

## 10. eval_v3 正式弱信号评测补充

### 10.1 目标
- 把已有 targeted semireal 弱信号能力沉淀成**正式数据集 + runner diagnostic 模式 + artifact 产物**。
- 明确 `eval_v2` 与 `eval_v3` 的职责分层：
  - `eval_v2`：healthy 主评测，要求全量通过。
  - `eval_v3`：weak-signal diagnostic，要求“预期失败/预期通过”与系统实际结果完全匹配。

### 10.2 用例矩阵
| case_id | modality | weak_signal_tags | expected_case_passed | expected_failure_stage |
| --- | --- | --- | --- | --- |
| `eval-v3-img-001` | `image_ocr` | `ocr_no_text` | `false` | `quality_gate` |
| `eval-v3-img-002` | `image_ocr` | `ocr_failed` | `false` | `quality_gate` |
| `eval-v3-pdf-001` | `pdf` | `nodes_without_embedding` | `false` | `quality_gate` |
| `eval-v3-pdf-002` | `pdf` | `[]` | `true` | `null` |

### 10.3 本轮新增测试
- `tests/test_rag_quality_eval_dataset_v3.py`
  - 校验 `schema.json` / `cases.json` / `summarize_eval_cases(...)` 输出。
- `tests/api/test_chat_eval_runner.py`
  - 新增 `build_diagnostic_summary(...)` 单测。
  - 新增 `evaluate_diagnostic_gates(...)` 单测。
  - 新增 `run_eval_v1_semireal(... eval_v3 ...)` 真 runner 测试，校验 JSON / Markdown artifact。

### 10.4 通过标准
- `weak_signal_case_count = 3`
- `required_signal_tags` 必须至少覆盖 `ocr_no_text`、`ocr_failed`、`nodes_without_embedding`
- `case_expectation_match_rate = 1.0`
- `weak_signal_kb_count >= 2`
- `weak_signal_modality_count >= 2`
- JSON / Markdown 报告必须成功落盘，并出现 `diagnostic`、`Diagnostic Gate` 与三类弱信号标签

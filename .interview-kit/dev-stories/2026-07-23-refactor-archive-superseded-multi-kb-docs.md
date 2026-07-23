# 归档被本地多知识库正式基线取代的旧文档

## 基本信息
- 类型：refactor
- 日期：2026-07-23
- 相关模块：文档治理、docs 主索引、正式基线切换、历史方案归档
- 相关文件：`docs/guide/DOCS_INDEX.md`、`docs/project.md`、`docs/archive/superseded-20260722-local-multi-kb-assistant/README.md`、`docs/archive/superseded-20260722-local-multi-kb-assistant/agent_v1_execution_plan.md`、`docs/archive/superseded-20260722-local-multi-kb-assistant/agent_v1_prd.md`、`docs/archive/superseded-20260722-local-multi-kb-assistant/agent_v1_frd.md`、`docs/archive/superseded-20260722-local-multi-kb-assistant/agent_v1_rtm.md`、`docs/archive/superseded-20260722-local-multi-kb-assistant/knowledge_agent_product_plan.md`、`docs/archive/superseded-20260722-local-multi-kb-assistant/knowledge_base_visibility_and_multi_kb_design.md`

## 背景
仓库已经形成新的正式需求基线：`docs/20260722-local-multi-kb-assistant/`。但旧的 `agent_v1`、`knowledge_agent_product_plan` 和 `knowledge_base_visibility_and_multi_kb_design` 系列文档仍散落在 `docs/spec/` 和 `docs/plan/` 下，容易让后续实现阶段误把历史方案当成当前主线。

## 主要改动
1. 新建归档目录 `docs/archive/superseded-20260722-local-multi-kb-assistant/`，集中保存被当前正式基线取代的旧文档。
2. 将以下旧文档迁移到归档目录，并在文件头增加“已归档”说明，明确它们只保留历史追溯价值：
   - `agent_v1_execution_plan.md`
   - `agent_v1_prd.md`
   - `agent_v1_frd.md`
   - `agent_v1_rtm.md`
   - `knowledge_agent_product_plan.md`
   - `knowledge_base_visibility_and_multi_kb_design.md`
3. 新增归档目录 README，说明归档原因、当前正式基线位置和已归档文件清单。
4. 更新 `docs/project.md`，将“文档需要联动维护”的对象和文档导航切换到 `docs/20260722-local-multi-kb-assistant/` 当前基线。
5. 更新 `docs/guide/DOCS_INDEX.md`，把 3.1/3.2/4.1/使用建议中的主入口统一改为当前正式基线，并明确旧入口已归档。

## 为什么这样做
- 不删除旧文档，可以保留历史设计决策和审阅脉络。
- 不继续把旧文档放在主路径下，可以减少实现阶段的认知分叉。
- 通过 `project.md + DOCS_INDEX.md` 双入口切换，可以把“当前正式基线”明确到目录级，而不是靠团队口头约定。

## 其他方案与为什么没选
- 直接删除旧文档：历史可追溯性太差，不利于后续 FRD/实施阶段回看架构演进。
- 保留原位不动，只在新目录补一句说明：主索引仍会把读者导向旧文档，风险没有真正消除。
- 等编码阶段一起整理：会让 Stage 3 的实现和历史文档治理混在一起，增加提交噪音。

## 验证与结果
- `git status --short`：已识别为 6 个 rename、1 个归档目录 README、新的索引/导航文档修改，且未混入 `server/index.py`、`tests/api/test_index_manager_coverage.py` 等无关代码改动。
- 读取归档后的 `docs/archive/superseded-20260722-local-multi-kb-assistant/agent_v1_prd.md` 文件头，确认已追加“已归档（2026-07-23）”说明。
- 使用 `rg` 检查 `docs/project.md` 与 `docs/guide/DOCS_INDEX.md`，确认主线入口已切换到 `docs/20260722-local-multi-kb-assistant/`。
- 本次为文档治理改动，未执行代码测试。

## 面试表达版本
我做过一次文档基线治理：项目已经形成新的“本地多知识库知识助手”正式方案，但旧的 PRD/FRD/Plan 还停留在主路径里，团队很容易把历史方案当现行方案。我没有直接删文档，而是把被取代的文档统一归档，给每份旧文档加了废弃说明，再把 `project.md` 和 `DOCS_INDEX.md` 全部切到新的正式基线。这样既保留了历史追溯能力，也减少了后续开发阶段的认知分叉。

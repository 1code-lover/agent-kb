# 为本地知识库问答补齐 evidence 契约与最小预览链路

## 基本信息
- 类型：feature
- 日期：2026-07-24
- 相关模块：Chat 问答契约、证据归一化、知识库预览 API、AgentPage 证据侧栏
- 相关文件：`api/services/evidence_service.py`、`api/services/chat_service.py`、`api/services/kb_service.py`、`api/routers/kb.py`、`api/schemas/__init__.py`、`api/services/agent_tools.py`、`tests/api/test_chat_evidence_contract.py`、`tests/api/test_kb_preview_route.py`、`webapp/src/api/evidence.js`、`webapp/src/api/chat.test.js`、`webapp/src/components/kb/KbEvidencePreview.jsx`、`webapp/src/pages/AgentPage.jsx`

## 需求背景
P0-1 已经把 Chat 入口收紧成单知识库 default-deny，但回答结果仍然以旧的 `sources` 字段主。这导致前端只能展示“命中来源”，却拿不到稳定的 `doc_id`、`preview_locator` 和可供后续工具复用的 evidence 对象。如果不先把证据建模补齐，“知识库是可引用的本地知识对象”这个产品承诺就站不住。

## 设计与实现方案
1. 新建 `api/services/evidence_service.py`，统一 source node 到 API 证据对象的映射，集中处理 `doc_id` 恢复、`preview_locator` 生成、`evidence_id` 编解码和 `excerpt` 截断。
2. 更新 `api/services/chat_service.py`，在保留旧 `sources` 的同时追加正式 `evidence` 字段，避免一次性 breaking change。
3. 更新 `api/services/agent_tools.py`，让旧的 `normalize_evidence()` 直接委托给 `evidence_service`，消除 `file/text` 与 `title/source/excerpt` 两套字段漂移。
4. 扩展 `api/schemas/__init__.py` 中的 `EvidenceItem`，新增 `doc_id`、`preview_locator`，并补充 `PreviewRequest` / `PreviewItem`，把证据与预览明确成 API 契约。
5. 在 `api/services/kb_service.py` 和 `api/routers/kb.py` 中新增 `/api/kb/preview`，支持通过 `doc_id` 或 `evidence_id` 请求最小文本预览，并复用 KB active 校验和知识库归属校验。
6. 前端新增 `webapp/src/api/evidence.js` 和 `webapp/src/components/kb/KbEvidencePreview.jsx`，在 `webapp/src/pages/AgentPage.jsx` 里让问答来源区升级为 evidence 面板，支持点击证据查看预览。
7. 用 `tests/api/test_chat_evidence_contract.py`、`tests/api/test_kb_preview_route.py` 和 `webapp/src/api/chat.test.js` 补齐契约与前端封装回归。

## 为什么选这个方案
我这次选择“新增 formal evidence 契约 + 保留 `sources` 兼容层”的做法，是因为 P0-2 的目标是先把证据对象立住，而不是制造一次全面 breaking change。把映射逻辑抽到 `evidence_service` 之后，Chat、Agent、Preview 三个入口可以共用同一套对象契约，后面接 PDF 预览、图片资产或 Agent 接口授权时也更好扩展。

## 其他方案与为什么没选
- 方案一：直接把 `sources` 原地改成新结构。没选，因为这会同时影响聊天页、Agent 工具结果和历史兼容逻辑，改动面过大。
- 方案二：前端自己根据旧 `sources` 拼 evidence。没选，因为 `doc_id` 恢复和 `preview_locator` 生成属于后端知识契约，不应该在不同调用方重复实现。
- 方案三：等完整多模态资产模型一起做。没选，因为 P0 当前最需要验证的是“证据对象是不是一等对象”，而不是预览样式有多完整。

## 风险与权衡
- 后端回归：`python -m pytest tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py tests/api/test_m2_multi_kb.py -q`
- 结果：`44 passed`
- 前端测试：`node --test webapp/src/domain/agentExperience.test.js webapp/src/api/chat.test.js`
- 结果：`9 passed`
- 前端构建：`npm --prefix webapp run build`
- 后端回归：`python -m pytest tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py tests/api/test_m2_multi_kb.py -q`
- 结果：`44 passed`
- 前端测试：`node --test webapp/src/domain/agentExperience.test.js webapp/src/api/chat.test.js`
- 结果：`9 passed`
- 前端构建：`npm --prefix webapp run build`
- 结果：构建成功，且已修复本轮编辑引入的 UTF-8/BOM/问号污染问题。

## 面试表达版本
我在做本地知识库助手时，发现“能回答”还不够，更重要的是回答里的证据要能被当成一等对象去引用和回看。所以我把 Chat 返回里的证据模型单独抽成 `evidence_service`，统一补齐 `doc_id`、`preview_locator` 和可反解的 `evidence_id`，同时保留旧 `sources` 作为兼容层。后端我补了 `/api/kb/preview` 这条最小链路，前端则把 AgentPage 的命中来源升级为可点击预览的 evidence 面板。这样做的价值是，在不制造大规模 breaking change 的前提下，先把“证据对象”和“可预览闭环”立住，为后面的多模态资产和 Agent 接口扩展打基础。

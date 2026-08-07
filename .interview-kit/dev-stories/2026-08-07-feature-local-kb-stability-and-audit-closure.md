# 本地知识库稳定性和前端依赖安全收口

## 基本信息
- 类型：feature
- 日期：2026-08-07
- 相关模块：KB 文件导入、检索过滤、粮仓 QA 评测、PaddleOCR 运行时、OCR 诊断脚本、Web 前端路由、项目进度文档
- 相关文件：
  - `api/routers/kb.py`
  - `api/services/kb_service.py`
  - `server/retriever.py`
  - `server/readers/image_ocr.py`
  - `scripts/run_grain_qa_eval.py`
  - `scripts/diag_image_ocr_roundtrip.py`
  - `scripts/diag_pdf_scan_roundtrip.py`
  - `scripts/diag_mixed_batch_roundtrip.py`
  - `webapp/src/router.jsx`
  - `webapp/src/App.jsx`
  - `webapp/package.json`
  - `webapp/package-lock.json`
  - `tests/readers/test_image_ocr.py`
  - `tests/scripts/test_run_grain_qa_eval.py`
  - `docs/project.md`
  - `docs/dev/changelog/2026-08-07.md`

## 需求背景
用户要求认真 review 最近修改但没有 push 的代码，并把能修的问题和优化建议尽可能处理好。盘点后，真正影响交付可信度的点集中在四处：macOS 环境容易误用 base Python；文件导入、BM25 和粮仓 QA 评测仍有边界可信度问题；PaddleOCR 在本机依赖和模块污染上不稳定；前端依赖 audit 仍有路由库安全公告。

## 设计与实现方案
1. 先确认 macOS 下可用环境是 `/opt/miniconda3/envs/agent-kb/bin/python`，并把环境说明写入 `AGENTS.md` 和 `docs/project.md`。
2. 在 KB 导入和检索层做小范围修复：文件导入从真实 multipart form 读取 `relative_paths`，BM25 只用纯正文判断可检索节点，Office 类型只承诺已验证的 `.docx`。
3. 在粮仓 QA 评测脚本里补充 `cases_sha256`、运行参数、来源数量和 `kb_id` 缺失计数，让“引用来源缺少 kb_id”不再被误判为隔离通过。
4. 在 OCR 运行时设置 PaddleX 默认 ModelScope 源，并在初始化前修复 `langchain.text_splitter` 兼容桥，解决“先 OCR 后问答”会 400 的顺序问题。
5. 对 OCR 诊断脚本补 macOS/Linux/Windows 字体候选，并把扫描 PDF 样本字号调大，避免诊断样本因为 PIL 默认字体导致 OCR 文本失真。
6. 前端不再继续在 React Router 7 与 6 之间切换，而是根据当前只使用基础路由能力的事实，新增项目内轻量 router 并移除 `react-router-dom` 依赖，让 `npm audit` 归零。

## 为什么选这个方案
这些改动都沿着现有系统边界做局部收口，没有重写 RAG 主链路。导入、检索和 QA 脚本只补证据可信度；OCR 修复只处理运行时默认值和模块污染；前端 router 替换则是因为项目实际只需要顶层页面切换、链接和 replace 导航，保留第三方路由库反而持续引入当前不使用能力的安全公告。

## 其他方案与为什么没选
- 直接把 React Router 降回 v6：试过后 high 变成 moderate，但 v6 的 open redirect 公告反而更贴近当前 `Link/useNavigate` 用法，所以没有保留。
- 全局把问答 `TOP_K` 调成 1 来减少 sources：没选，因为这会伤害召回，并且现有测试明确把正常命中时保留多来源作为契约之一。
- 把 mixed batch 多 sources 强行裁剪成 1 条：没选，因为这涉及产品层证据返回契约，应该先明确“一问一证据”还是“多候选证据”。

## 风险与权衡
1. 项目内轻量 router 只覆盖当前用到的能力，不等价于完整 React Router；如果后续要 loader、action、嵌套路由参数或复杂匹配，需要重新评估。
2. OCR 当前验证重点是成功提取、入库、问答和 preview 命中，还没有扩展到 CER、表格结构和版面顺序。
3. mixed batch 真实 roundtrip 仍会返回多个候选 sources，当前记录为产品策略风险而不是后端 bug。
4. 多知识库仍是共享索引 + metadata 过滤的逻辑隔离，不是物理隔离。

## 验证与结果
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest -q`：`677 passed, 35 warnings`
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`75 passed`
- `cd webapp && npm run build`：通过
- `cd webapp && npm audit --json`：`0 vulnerabilities`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pip check`：`No broken requirements found.`
- `git diff --check`：通过
- 图片 OCR API roundtrip：`ocr_attempted=true`、`indexed_from_ocr=true`，问答和 preview 命中。
- 扫描 PDF API roundtrip：源文件和保存文件 hash 一致，PDF 无文字层，`ocr_status=success`、`indexed_from_ocr=true`、`ocr_text_length=293`，问答、source、evidence 和 preview 均命中。
- mixed batch API roundtrip：`run_passed=true`，嵌入图片 OCR、独立图片 OCR、PDF 文本层、资产注册和无证据拒答核心 gate 均通过。
- 临时 Vite HTTP smoke：`/agent?experience=knowledge` 返回 200，`webapp/src/router.jsx` 可由 Vite 正常转译加载。

## 面试表达版本
我这轮做的是一次本地知识库助手的稳定性和安全收口。先把 macOS 真实可用的 conda 环境固定下来，再修导入、检索和 QA 评测里会让结果不可信的边界问题。OCR 方面，我解决了 PaddleX 默认模型源和 `langchain.text_splitter` 被污染导致“先 OCR 后问答”失败的问题，并用图片、扫描 PDF、mixed batch 三条真实 roundtrip 验证。前端方面，我发现项目只用到了很基础的路由能力，所以移除了会持续带来 audit 公告的 `react-router-dom`，用一个项目内轻量 router 替代，最后把 `npm audit` 做到 0。整个过程我保留了剩余风险，比如多 sources 的证据返回策略和逻辑隔离边界，没有把测试通过包装成系统已经没有限制。

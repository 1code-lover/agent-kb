# 20260821 Project Audit Remediation Spec

## 1. 文档目标

这份文档用于把 2026-08-21 ~ 2026-08-22 这轮“继续检查并迭代整个项目”的结论收口成一份**真实、可复述、可继续执行**的项目审计说明，重点回答：

1. 当前项目到底哪些地方已经修到可讲；
2. 哪些问题仍然存在，而且会影响启动链路、工程治理或对外叙事；
3. 当前最新、可信的评测与回归基线是多少；
4. 接下来最值得继续投入的整改方向是什么。

## 2. 本轮审计依据

### 2.1 当前代码与配置抽样

- `webapp/src/domain/agentExperience.js`
- `webapp/src/domain/chatWorkflow.js`
- `webapp/src/pages/AgentPage.jsx`
- `api/schemas/__init__.py`
- `api/services/chat_service.py`
- `api/services/evidence_service.py`
- `api/services/kb_service.py`
- `start_all.ps1`
- `start_dev.ps1`
- `scripts/dev-all.ps1`
- `desktop/src/runtime-config.js`
- `desktop/src/python-process.js`
- `desktop/src/preload.js`
- `desktop/src/renderer-entry.js`
- `webapp/src/api/client.js`
- `README.md`
- `README_zh.md`
- `README_en.md`
- `docs/project.md`
- `scripts/cleanup_local_artifacts.py`
- `tests/scripts/test_cleanup_local_artifacts.py`

### 2.2 本轮实际验证

- `python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_service.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q` → `114 passed`
- `python scripts/run_chat_eval.py --suite tests/fixtures/rag_quality/eval_layered_suite.json --output-dir temp/eval-layered-suite-20260821-targeted-fact-fix-r5` → `153 / 153`
- `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_requirements_profiles.py tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q` → `83 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_builders.py tests/test_rag_quality_fixtures.py -q` → `16 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q` → `12 passed`
- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `41 passed`
- `chat_eval_runner` 当前已把 refusal / negative contract 的 contract gate 直接联动到最终 `run_passed`，不再只是报告摘要展示
- `python -m pytest tests/scripts/test_cleanup_local_artifacts.py -q` → `13 passed`
- `node --test desktop/src/csp.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js desktop/scripts/verify-release-config.test.js` → `19 passed`
- `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/api/client.test.js` → `16 passed`
- `python -m pytest tests/ -q -m "not slow"` → `1299 passed, 4 deselected`
- `python scripts/cleanup_local_artifacts.py --apply --recommended-action archive_or_delete` → 归档 `63` 个日志类对象
- `python scripts/cleanup_local_artifacts.py --apply --category scratch_ocr_script` → 归档 `18` 个 OCR 草稿脚本
- `python scripts/cleanup_local_artifacts.py --apply --category temp_probe` → 归档 `19` 个临时探针 / 一次性产物
- `python scripts/cleanup_local_artifacts.py --dry-run` → `managed_count = 0`
- `python scripts/cleanup_local_artifacts.py --dry-run --include-directories` → `managed_count = 0`

### 2.3 当前量化证据

- layered suite 最新产物：`temp/eval-layered-suite-20260821-targeted-fact-fix-r5/local_multi_kb_eval_v8_layered_suite-suite-report.json`
- refusal / negative case 覆盖统计：
  - `eval_v7`：`24` 题，其中 refusal `3` 条（`no_evidence = 3`）+ negative contract `6` 条（`process_boundary = 3`、`scope_contract = 3`）
  - `eval_v8_main`：`90` 题，其中 refusal `23` 条（`no_evidence = 14`、`hard_refusal = 6`、`scope_contract = 3`）+ negative contract `19` 条（`process_boundary = 12`、`scope_contract = 7`）
  - `eval_v8_hard`：`36` 题，其中 refusal `6` 条（`evidence_insufficient = 6`）+ negative contract `6` 条（`scope_isolation_trap = 6`）
- 根目录治理量化证据：
  - 第一轮 manifest：`temp/root-artifacts/20260821-235858/manifest.json`
  - 第二轮 manifest：`temp/root-artifacts/20260822-000325/manifest.json`
  - 第三轮 manifest：`temp/root-artifacts/20260822-000326/manifest.json`
  - 累计归档对象：`100`
  - 当前 file-mode dry-run：`managed_count = 0`
  - 当前 directory-mode dry-run：`managed_count = 0`

## 3. 最新总体判断

一句话结论：

> **项目的主能力链路已经闭环，并且当前 semireal layered suite 已经做到 `153 / 153`；工程完成度仍未完全收尾，但根目录临时产物治理已经从“发现问题”推进到“完成三轮实际 apply，并让 file-mode / directory-mode 均已回到 `managed_count = 0`”。当前真正剩余的尾巴，主要集中在启动/文档口径漂移、legacy 入口残留，以及 prompt-heuristic 依赖偏重。**

这意味着以后对外讲项目，应该显式区分两层：

### 3.1 能力完成度：可以比较放心讲

- 多知识库 `single_kb` / active KB 契约已经明确；
- evidence / preview / scope / source-count 已进入评测体系；
- `QueryRequest` 的请求级检索参数已进入 chat 主链路；
- query 成功不再因为 history 写回失败而被前端整体判成失败；
- 当前 layered eval 主路径已经全绿；
- 根目录治理能力已经建立起来；文件模式与目录模式都已清到 `managed_count = 0`，后续重点转为防回脏与定期巡检。

### 3.2 工程完成度：仍在继续收口

- `app.py`、`frontend/`、`.streamlit/` 仍在仓库内保留，主入口已统一但历史入口还未彻底治理；
- README 已基本统一到 `FastAPI + React + Electron`，但 `docs/project.md` 等历史文档仍保留较多历史数字和 legacy 叙事；
- 默认端口 `18080` 仍大量出现在 README / docs / runtime 默认值中，说明“可配置”已做到，但“默认口径统一 + 历史文档彻底收敛”还没完全做完；
- `api/services/chat_service.py` 中仍有多组 `_maybe_*` 后处理函数，说明 prompt 契约还不够硬、规则修补仍偏重；
- Docker 默认语义已收敛到 `INSTALL_PROFILE=runtime` + API 模式；runtime build 变慢的关键根因之一已经定位为顶层 `llama_index` metapackage，最新 dry-run 不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index`，但完整 build/run smoke 与默认 baseline 体重问题仍待继续收口。

## 4. 当前可信基线

以 `temp/eval-layered-suite-20260821-targeted-fact-fix-r5/` 下产物为准：

- 总体：`153 / 153`，`pass_rate = 1.0`
- Smoke：`24 / 24`
- Main：`90 / 90`
- Hard：`36 / 36`

这个结果说明：

1. 当前 semireal layered suite 已全部通过；
2. 之前围绕 targeted fact、preview excerpt hygiene、negative contract、forbidden term 误判的主要问题已被修复；
3. 根目录治理也已经被真实执行，而不是停留在文档层；
4. 现在项目最需要继续讲清楚的，不再是“为什么 hard 还没过”，而是“为什么评测全绿不等于工程已经 100% 收尾”。

## 5. 12 个问题的当前结论

### 5.1 已修或基本收敛

1. **basic 模式和后端 `single_kb` 约束冲突**：已修
2. **项目主入口不统一**：主入口基本收敛到 `FastAPI + React + Electron`
3. **请求级 `QueryRequest` 参数没有完整打进 chat 主链路**：已修
4. **前端把 query 成功和 history 成功绑死**：已修
5. **评测 hard case 当前无法通过**：本轮已修到 `153 / 153`
6. **仓库根目录临时文件、日志、调试脚本较多**：cleanup 能力已经建立起来，当前 file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化
7. **日志与临时产物治理需要规范化**：能力已建立并经过真实执行验证

### 5.2 仍然成立、但已从“功能阻塞”转成“工程整改”的问题

1. **启动链路 / 桌面链路存在硬编码**：部分收敛，仍有默认端口与历史路径口径残留
2. **评测 harness 对 refusal / negative contract 覆盖不足**：比之前明显增强，但 OCR / preview hygiene 负向题还可以继续补强
3. **Prompt 契约偏弱，后处理 heuristic 太重**：仍成立
4. **Docker / requirements / 端口 / 启动脚本存在配置漂移**：部分收敛，仍需继续统一文档与默认值口径
5. **文档闭环不够满**：仍成立
6. **面试表述需要主动区分“能力完成度”和“工程完成度”**：本轮已整理出可讲口径，但仍需要统一引用入口

## 6. 现在最合理的项目定位

> **这是一个“主能力闭环和评测闭环都已经做出来，且仓库根目录治理已收敛到 file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为后续重点转为防回脏、定期巡检与受控 apply 预案固化，工程治理、文档统一和长期维护体验仍在继续收口”的本地知识库助手项目。**

这样讲的好处是：

- 不会因为当前 `153 / 153` 就显得在吹“系统已经完美”；
- 也不会把项目讲成“还有很多问题所以不成熟”；
- 能把你的贡献聚焦在真正完成的能力闭环上，同时诚实保留工程尾巴。

## 7. 下一步最值得继续投入的整改方向

### 7.1 P0：工程主入口和运行治理

1. 继续清理 legacy 入口叙事：`docs/project.md`、历史 runbook、旧 README 引用
2. 明确 `app.py` / `frontend/` / `.streamlit/` 的保留策略：只读归档、兼容入口，还是后续移出主仓库
3. 统一端口配置口径：默认端口保留 `18080` 可以，但要减少散落文档的硬编码描述
4. 把根目录治理流程写进固定 runbook / 提交流程，并把目录治理重点切到巡检、防回脏与受控 apply 预案；当前 file-mode / directory-mode 均已回到 `managed_count = 0`

### 7.2 P1：质量体系与契约硬化

1. 继续扩 refusal / negative contract 在 OCR / preview hygiene 上的负向集
2. 优先减少 `chat_service.py` 对 `_maybe_*` 规则链的依赖
3. 保留当前 `153 / 153` layered suite 作为回归门禁，而不是只当一次性结果
4. 给 desktop / startup / Docker 增加真实执行型 smoke，而不只做字符串契约测试

### 7.3 P2：对外叙事统一

1. 统一面试材料引用：优先引用 20260821 审计文档 + 当前 layered suite 产物
2. 把“能力完成度 vs 工程完成度”沉淀成固定话术
3. 明确“根目录治理已收敛，但需持续守住”的表达方式

## 8. 最终结论

当前最真实的说法应该是：

> **项目现在已经可以讲，而且可以讲得更稳：能力和评测都已成型，仓库治理也开始真收口；下一阶段的重点，不是证明“还能再答对几题”，而是把启动链路、配置统一、文档闭环和规则后处理职责继续做实。**


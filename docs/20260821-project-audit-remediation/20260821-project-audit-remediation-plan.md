# 20260821 Project Audit Remediation Plan

## 1. 目标

在当前 `153 / 153` layered suite 的基础上，把项目继续往“**工程完成度也匹配能力完成度**”的方向推进，而不是停留在“评测全绿就结束”。

## 2. 当前阶段判断

当前阶段已经不是“先救主能力”的状态，而是：

1. **主能力闭环已成型**：scope / evidence / preview / targeted fact / refusal 主路径已过当前 semireal suite；
2. **工程口径仍有漂移**：启动链路、端口默认值、legacy 入口和历史文档还不完全统一；
3. **仓库整洁度已明显改善，但还要防回脏**：根目录日志、临时探针、OCR 草稿脚本已经完成三轮实际归档，file-mode / directory-mode 均已归零；
4. **代码结构仍偏 heuristic**：`chat_service.py` 中规则链仍重，后续维护成本偏高。

## 3. 优先级路线

### 3.1 P0：工程主线统一

#### Task 1：统一主入口叙事
- 目标：把所有高可见度文档统一到 `FastAPI + React + Electron`
- 重点文件：
  - `README.md`
  - `README_zh.md`
  - `README_en.md`
  - `docs/project.md`
  - `docs/guide/desktop_runbook.md`
  - `docs/desktop_runbook.md`
- 验收：历史 Streamlit / legacy 入口只保留兼容说明，不再出现在“默认启动方式”里

#### Task 2：统一端口 / API base / Docker / requirements 口径
- 目标：减少默认 `18080`、API base、runtime profile 的散落描述差异
- 重点文件：
  - `start_dev.ps1`
  - `start_all.ps1`
  - `scripts/dev-all.ps1`
  - `desktop/src/runtime-config.js`
  - `Dockerfile`
  - `requirements-*.txt`
  - `docs/project.md`
- 验收：端口配置与 profile 使用方式文档化一致；Docker 默认语义清晰可讲

#### Task 3：明确 legacy 入口保留策略
- 目标：给 `app.py` / `frontend/` / `.streamlit/` 明确地位
- 方案候选：
  1. 只读保留并明确标记 legacy；
  2. 后续迁移到 archive 目录；
  3. 若确无依赖则移除。
- 验收：仓库内不再出现“主入口到底是哪条”的歧义

### 3.2 P1：质量体系与代码结构硬化

#### Task 4：降低 `chat_service.py` 对规则后处理的依赖
- 目标：逐步把 targeted fact / preview / boundary 答案生成从规则修补，迁回更清晰的契约与 prompt
- 重点文件：
  - `api/services/chat_service.py`
  - `tests/api/test_chat_service.py`
  - `tests/api/chat_qa_metrics.py`
- 验收：`_maybe_*` 链路数量或职责复杂度显著下降，当前 eval 继续保持全绿

#### Task 5：补 refusal / negative contract 的 OCR 与 preview hygiene 负向集
- 目标：让 hard 全绿不只是当前题集巧合，而是对负向边界有更稳约束
- 重点文件：
  - `tests/fixtures/rag_quality/eval_v8_hard/cases.json`
  - `tests/fixtures/rag_quality/eval_v8_main/cases.json`
  - `tests/api/test_chat_qa_metrics.py`
- 验收：新增负向题后仍能稳定通过，或至少能精准暴露新增边界

#### Task 6：给 desktop / startup / Docker 增加真实 smoke
- 目标：让主链路验证不只停留在字符串契约测试
- 重点文件：
  - `tests/scripts/test_dev_startup_contracts.py`
  - `tests/test_requirements_profiles.py`
  - `scripts/docker-entrypoint.sh`
  - `Dockerfile`
- 验收：至少有一条真实执行型 startup / Docker smoke 被纳入常规验证口径

### 3.3 P2：工程治理与对外表达

#### Task 7：根目录临时文件和日志治理
- 目标：把根目录 `tmp_*` / 日志 / OCR 草稿脚本纳入正式治理，且形成可复用规则
- 重点文件：
  - 仓库根目录临时文件
  - `scripts/cleanup_local_artifacts.py`
  - `tests/scripts/test_cleanup_local_artifacts.py`
- 当前完成情况：
  1. `python scripts/cleanup_local_artifacts.py --apply --recommended-action archive_or_delete`
     - 归档 `63` 个日志类对象到 `temp/root-artifacts/20260821-235858/manifest.json`
  2. 人工评审 `_test_ocr*.py`
     - 结论：18 个脚本都是历史 OCR scratch/probe，能力已被 `tests/api/test_chat_image_ocr_semireal.py`、`tests/api/test_chat_pdf_semireal.py`、`tests/api/test_chat_mixed_batch_semireal.py` 及 `scripts/diag_*` 正式脚本覆盖，不需要转正
     - 执行：`python scripts/cleanup_local_artifacts.py --apply --category scratch_ocr_script`
     - manifest：`temp/root-artifacts/20260822-000325/manifest.json`
  3. 人工评审 `temp_probe`
     - 结论：`tmp_diag_*.json`、`tmp_eval_v4_probe.json`、`tmp_run_api_18081.py`、`tmp_recovered_test_chat_eval_runner.py`、`tmp_manual_diag.pdf`、`tmp_ocr_bench.png`、`temp_test_view.txt` 都属于一次性诊断产物或临时探针，正式能力已由 `scripts/diag_*`、`tests/api/*semireal*.py` 与 `docs/.../artifacts/` 承接
     - 执行：`python scripts/cleanup_local_artifacts.py --apply --category temp_probe`
     - manifest：`temp/root-artifacts/20260822-000326/manifest.json`
  4. 当前 file-mode dry-run：`python scripts/cleanup_local_artifacts.py --dry-run` → `managed_count = 0`
  5. 当前 directory-mode dry-run：`python scripts/cleanup_local_artifacts.py --dry-run --include-directories` → `managed_count = 0`
- 当前真实结论：根目录治理已从“有方案”推进到“已三轮实际执行并完成文件级收敛”；累计归档对象 `100` 个，但仍有 `14` 个 root scratch 目录 backlog 待继续评审
- 下一步：把这套规则沉淀成固定 runbook，并持续用脚本守住根目录整洁度

#### Task 8：统一面试与汇报材料引用
- 目标：明确“哪份文档是当前对外主引用”
- 推荐顺序：
  1. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md`
  2. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-guide.md`
  3. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-report-script.md`
  4. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md`
- 验收：不再混用旧分数与旧结论

## 4. 当前建议的执行顺序

1. 文档与主入口统一
2. 端口 / Docker / requirements 统一
3. legacy 入口策略明确
4. heuristic 降权 + 负向评测补强
5. 把 directory-mode backlog 做分类治理
6. 把根目录治理规则写成固定 runbook / 门禁说明

## 5. 当前完成标准

这一轮不再以“把当前 suite 从 140/150 拉到 150/150”为完成标准，因为这一步已经完成；接下来的完成标准应当是：

- 文档主入口叙事统一；
- legacy 入口角色明确；
- 启动 / 端口 / profile 口径统一；
- 根目录治理持续可复用，而不是靠一次性人工清理；
- file-mode 已收敛、directory-mode backlog 有明确治理路径；
- 评测全绿能够稳定复用，而不是只停留在单次结果。

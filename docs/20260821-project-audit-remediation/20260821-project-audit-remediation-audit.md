# 20260821-project-audit-remediation-audit

## 审计说明

- 审计日期：2026-08-24
- 审计方式：继续沿“全仓扫描 + 关键文件复核 + 关键测试复跑”推进，按 30 个检查轮次记录问题与优化点。
- 审计目标：不是宣称“项目已全部完成”，而是识别当前仍然存在的工程风险、维护成本和下一轮最值得做的优化。

## 本轮实际复跑验证

```powershell
python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_service.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q
# 114 passed

python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_requirements_profiles.py tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q
# 83 passed

python -m pytest tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_builders.py tests/test_rag_quality_fixtures.py -q
# 16 passed

python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q
# 12 passed

python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q
# 31 passed, 2 warnings

python -m pytest tests/scripts/test_cleanup_local_artifacts.py -q
# 13 passed

node --test desktop/src/csp.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js desktop/scripts/verify-release-config.test.js
# 19 passed

node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/api/client.test.js
# 16 passed

python -m pytest tests/ -q -m "not slow"
# 1299 passed, 4 deselected

python scripts/cleanup_local_artifacts.py --dry-run --include-directories
# managed_count = 0
# scratch_eval_dir = 12 / scratch_debug_dir = 2
```

## 30 轮审计结论

| 轮次 | 检查点 | 结论 | 优先级 |
| --- | --- | --- | --- |
| 01 | 工作树状态 | 当前 `git status --short` 仍然很脏，文档、脚本、后端、桌面端、评测数据集同时在变，更适合继续审计和分批收口，不适合一次性大提交。 | P0 |
| 02 | 审计资料归档 | `docs/20260821-project-audit-remediation/` 已形成较完整材料集，但目录仍处于未追踪状态，说明“材料已经成型”和“材料已纳入版本管理”还是两件事。 | P1 |
| 03 | 根目录整洁度 | file-mode / directory-mode 均已回到 `managed_count = 0`，说明 root scratch backlog 已从‘需要清理’切到‘需要防回脏’；后续重点转为防回脏、定期巡检与受控 apply 预案固化。 | P0 |
| 04 | cleanup 覆盖范围 | `scripts/cleanup_local_artifacts.py` 已支持 `--include-directories` 与显式 `--dry-run`，治理能力本身已经补齐；当前状态是 file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化。 | P0 |
| 05 | cleanup 指标解释 | 现在必须把 file-mode 和 directory-mode 分开讲：file-mode `0` 只能说明根目录文件已收敛，directory-mode `0` 才能反映 root scratch backlog。 | P0 |
| 06 | cleanup backlog 结构 | `14` 个目录里有 `37` 个评测 scratch、`4` 个 debug scratch、`4` 个 temp scratch，说明当前 backlog 主要不是运行日志，而是历史 eval/debug 工作区。 | P1 |
| 07 | tracked artifacts 体量 | `git ls-files` 显示 `docs/20260722-local-multi-kb-assistant/artifacts/` 下已有大量历史产物，文档型证据充分，但仓库噪声和 diff 成本也明显升高。 | P1 |
| 08 | legacy 入口现实状态 | README / runbook 已把 `app.py + frontend/` 标记为 legacy；`app.py` 现在已改成默认禁用、需显式设置 `KB_ALLOW_LEGACY_STREAMLIT=1` 等环境变量才允许进入的 compatibility shim，且 `streamlit` 已延迟导入；不过 `frontend/` 仍是完整代码路径，legacy 退场尚未真正完成。 | P1 |
| 09 | 主入口叙事 | 当前主入口叙事已经基本统一到 `start_all.ps1 -> start_dev.ps1 -> scripts/dev-all.ps1`，这是优点；现在旧入口已从“默认可跑”收口成“显式 opt-in 的兼容入口”，误导风险已下降，但新增材料仍需持续避免把 legacy 路径写成主线。 | P1 |
| 10 | API host 可配置性 | `run_api.py` 已支持 `KB_API_HOST` 优先于 legacy alias 的 host 覆盖，默认仍回落到 `127.0.0.1`；当前问题不再是 host 被写死，而是如何把这套可配置契约继续统一到文档、脚本和部署口径。 | P2 |
| 11 | Docker 默认安装 profile | 已收敛到 `Dockerfile` 默认 `ARG INSTALL_PROFILE=runtime`，这比之前的评测默认更符合产品镜像语义；剩余重点不再是默认值本身，而是如何用完整 build/run smoke 证明 runtime baseline 真的稳定。 | P1 |
| 12 | Docker 默认运行行为 | 已收敛到 entrypoint 默认 API 模式，`eval` / `prod` 需要显式声明；当前剩余问题不再是默认跑错进程，而是完整容器 smoke 证据还不够。 | P1 |
| 13 | runtime 依赖根因定位 | Docker 默认 profile 已切回 `runtime`，`requirements-minimal.txt` 退回本地兼容 alias；进一步确认 runtime build 变慢的关键根因之一，是 `requirements-runtime.txt` 曾引入顶层 `llama_index` metapackage，额外拉起 `llama-parse / llama-cloud-services / llama-cloud`。当前 runtime baseline 已改成 `llama-index-core==0.11.19` + 显式 integrations，并显式 pin `langchain-core==0.3.63` / `langchain-text-splitters==0.3.8`，最新 dry-run 已确认不再出现这些回流依赖。 | P0 |
| 14 | 启动脚本测试方式 | `tests/scripts/test_dev_startup_contracts.py` 主要是字符串契约测试，能防回退，但不能替代真实 PowerShell 启动、端口探活、Stop 行为验证。 | P1 |
| 15 | 文档契约测试方式 | `tests/scripts/test_docs_entry_contracts.py` 也是文本存在性断言，能防口径漂移，但不验证文档命令真的可执行。 | P1 |
| 16 | Docker 测试方式 | `tests/test_requirements_profiles.py` 会检查 Dockerfile/entrypoint 的字符串与 profile 映射，但并没有真正执行 `docker build` 或容器启动。 | P1 |
| 17 | chat_service 体量 | `api/services/chat_service.py` 当前约 `1166` 行，是当前最明显的维护热点之一。 | P0 |
| 18 | heuristic 后处理链 | `chat_service.py` 里仍保留大量 `_maybe_*` 后处理函数，并在 `_apply_source_answer_postprocessors(...)` 里串联调用，说明 prompt / contract 和 heuristic 的职责还没完全收紧。 | P0 |
| 19 | kb_service 体量 | `api/services/kb_service.py` 约 `2954` 行，已经是另一个明显的高耦合热点；后续若继续叠加迁移、导入、资产逻辑，维护成本会继续上升。 | P1 |
| 20 | 前端页面体量 | `webapp/src/pages/AgentPage.jsx` 当前约 `792` 行，问答 workflow 已抽到 `useAgentChatWorkspace.js`（`251` 行），展示层也已拆成 `QaWorkbench.jsx`（`281` 行）+ 三个叶子组件；后续更适合继续压 `AgentRuntimePanel`。 | P1 |
| 21 | 测试文件体量 | `tests/api/test_chat_service.py` 当前约 `2097` 行，虽然覆盖强，但可读性与维护成本都很高，适合继续按题型/契约分拆。 | P1 |
| 22 | 评测 runner 体量 | `tests/api/chat_eval_runner.py` 当前约 `2742` 行，已经接近“框架级脚本”，建议再拆 case adapter / metrics aggregator / report formatter。 | P1 |
| 23 | 命名债务 | 桌面端仍同时兼容 `NorthAgent / ThinkRAG / Foxglove` 三套 bridge / env 命名，说明历史命名债务尚未完全清理。 | P1 |
| 24 | preload 暴露面 | `desktop/src/preload.js` 同时暴露 `northAgentDesktop`、`foxgloveDesktop`、`thinkragDesktop`，兼容性强，但也增加了认知负担和长期维护面。 | P1 |
| 25 | renderer 配置别名 | `desktop/src/renderer-entry.js` 同时读取 `NORTHAGENT_WEB_URL`、`FOXGLOVE_WEB_URL`、`THINKRAG_WEB_URL`；这类别名在过渡期合理，但现在已经值得收口。 | P1 |
| 26 | Web 端 bridge 别名 | `webapp/src/api/client.js` 与 `webapp/src/pages/AgentPage.jsx` 也同时兼容三套 desktop bridge 名称，命名债务已经从桌面层渗透到前端层。 | P1 |
| 27 | packaged verify 的外部前提 | `desktop/scripts/verify-package.js` 明确要求 `localmodels/BAAI/bge-small-zh-v1.5/...` 这些 embedding 文件存在，说明打包校验仍与本机缓存状态强耦合。 | P1 |
| 28 | 评测集规模 | 当前 layered suite 结构为 `24 + 90 + 36 = 150` 个样本，主集和 hard 集已经比之前更有说服力；但从工程视角看，仍需要继续扩真实扫描、负向拒答、preview hygiene 类题目。 | P1 |
| 29 | schema 可读性 | 三套 schema 现在已经显式补齐 `allowed_judge_dimensions`、`rubric_dimensions` 与 `minimum_cases_per_judge_dimension`，比早期版本更可读；但弱信号样本目前主要集中在 v8 main，v7 / hard 对这类边界覆盖仍偏少，后续最好补更多 dimension-to-case 示例与跨层分布说明。 | P2 |
| 30 | 项目总体判断 | 现在项目已经不是“主链路不通”的状态，而是“主能力稳定、材料可讲、但工程收口仍未结束”的状态；后续最值钱的不是再堆 1.0，而是继续降 heuristic、收命名债务、清大文件耦合，并把 runtime baseline 已收口、完整 Docker smoke 仍待补齐，以及 cleanup 的 file/directory 边界讲诚实。 | 总结 |

## 当前最值得继续做的 8 项优化

### P0
1. 拆 `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/api/services/chat_service.py`：先把 targeted fact / preview / boundary / exact term repair 从一个长文件里拆出去。
2. 对 `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb` 根目录下 `45` 个 scratch 目录做人工分批评审，再谨慎使用 `python scripts/cleanup_local_artifacts.py --apply --include-directories`。
3. 继续补 `runtime` baseline 的真实 Docker smoke，并评估是否进一步收紧 `sentence-transformers / torch` 这类重依赖的默认安装口径。

### P1
4. 拆 `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/api/services/kb_service.py`。
5. 拆 `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/webapp/src/pages/AgentPage.jsx`。
6. 收口 `foxglove` / `thinkrag` 兼容别名，给“何时删旧名”定明确阶段目标。
7. 给 requirements / 启动脚本 / Docker 各补一条真实执行型 smoke，而不只是文本契约。
8. 在材料里持续强调 file-mode `0` 与 directory-mode `0` 的区别，避免对外误讲成“仓库已经彻底清空临时产物”。

## 结论

如果以“能不能面试讲”来判断，这个项目已经可以讲；如果以“工程上是否完全收尾”来判断，还没有。当前最真实的状态是：

- 主能力：能讲，且有测试和评测支撑；
- 材料层：已经比较完整；
- 工程层：仍有几块很明显的收口工作，尤其是 heuristic、命名债务、大文件拆分、Docker profile 语义，以及临时产物治理边界说明。

## 补充更新（2026-08-22 API entry env alias symmetry）

### 新增验证

```powershell
python -m pytest tests/test_run_api.py tests/scripts/test_dev_startup_contracts.py -q
# 18 passed
```

### 这轮新增真实结论

1. `run_api.py` 现在对 **port / host** 都按同一套优先级读取环境变量：优先 `KB_*`，再兼容 `NORTHAGENT_*` / `THINKRAG_*` / `FOXGLOVE_*`。
2. 这意味着 `start_dev.ps1`、`scripts/dev-all.ps1`、`desktop-dev.ps1` 已经注入的历史端口别名，不会在 API-only 入口里静默失效；过去“host 支持 alias、port 只认 `KB_API_PORT`”的隐性分叉已经收口。
3. `_get_port()` 的报错也从只会泛化成 `KB_API_PORT`，改成能指出真正出错的环境变量名，排查桌面联调或历史脚本残留配置时更直接。
4. 这轮属于小改动但高信号：它没有再重写启动脚本，而是把 `run_api.py` 与桌面端 `desktop/src/runtime-config.js` 已有的 alias 契约真正对齐。


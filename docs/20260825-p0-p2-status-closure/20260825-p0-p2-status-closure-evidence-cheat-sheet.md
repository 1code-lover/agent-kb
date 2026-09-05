# 20260825 P0/P2 Status Closure Evidence Cheat Sheet

## 1. 这份文档怎么用

这份 `evidence-cheat-sheet` 不是长讲稿，而是给你在面试前 3 分钟、被追问某一条问题、或者临时需要核对“我到底改了什么 / 怎么证明”的时候快速翻的证据索引。

使用原则：

1. **先看问题编号**：确认是 1~12 里的哪一条；
2. **只记 1~2 个关键文件**：不要一口气背一串路径；
3. **只记 1 条最关键测试命令**：够证明主链路就行；
4. **如果要最新数字**：统一回看 `20260825-p0-p2-status-closure-status-report.md` 的“2.1 本轮实际执行的命令”。

---

## 2. 12 个问题的最短证据索引

| 编号 | 当前状态 | 最该提的文件 | 最该提的测试 / 命令 | 面试时一句话怎么说 |
| --- | --- | --- | --- | --- |
| 1 | 已收口 | `webapp/src/domain/agentExperience.js`、`api/services/query_scope.py` | `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/api/client.test.js`；`python -m pytest tests/api/test_chat_scope_contract.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py tests/api/test_chat_service.py tests/api/test_chat_routes.py -q` | 我把前端模式语义和后端 `single_kb` 约束对齐了，`basic / knowledge` 都必须绑定 active KB。 |
| 2 | 部分完成 | `start_frontend.ps1`、`tests/scripts/test_dev_startup_contracts.py` | `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/test_legacy_streamlit_entry.py -q` | 旧绝对路径、固定端口和 legacy 引导已经被兼容层收住，但兼容层还没完全退场。 |
| 3 | 大体收口 | `README.md`、`docs/project.md` | `python -m pytest tests/scripts/test_docs_entry_contracts.py -q` | 现在主入口口径已经统一成 FastAPI + React(Vite) + Electron，Streamlit 只是 opt-in legacy。 |
| 4 | 已收口 | `api/runtime.py`、`api/services/open_api_service.py` | `python -m pytest tests/api/test_runtime_model_loading.py -k "request or overrides_config_store_defaults" -q` | QueryRequest 请求级参数已经真正打进 runtime query engine，不再只是前端假透传。 |
| 5 | 已收口 | `webapp/src/domain/chatWorkflow.js`、`webapp/src/domain/chatWorkflow.test.js` | `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/api/client.test.js` | query 成功和 history 写回已经解耦，history 慢一拍不会再把成功结果覆盖掉。 |
| 6 | 大体收口 | `tests/api/test_chat_eval_runner.py`、`scripts/validate_rag_quality_fixtures.py` | `python -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_eval_contracts.py tests/test_rag_quality_eval_dataset_v8.py -q` | refusal / negative contract 已经进入正式套件，而且 hard 集的 history-grounded refusal 与 main 集的 answerable follow-up 都已经有正式 gate；但更大规模 semireal hard negative 还要继续补。 |
| 7 | 部分完成 | `api/services/chat_targeted_fact.py`、`api/services/chat_source_selection.py`、`api/services/model_service.py`、`api/services/chat_query_flow.py` | `python -m pytest tests/api/test_chat_query_flow.py tests/api/test_chat_service.py tests/api/test_model_service.py -q` | 我先把 targeted-fact 评分和 targeted-fact orchestration 拆成可回归 helper，接着把 source minimization 拆成 should-minimize / mentioned-source / support-map / greedy-cover helper，再把 signals / structural bonus helper 化，也把 `attempt_model_fallback(...)` 拆成显式 helper；这轮继续把 `chat_service.query(...)` 里的 fallback retry、result assembly，以及 identifier-gap / refusal pruning / postprocessor 尾段分支下沉到 `chat_query_flow.py`，并用 113 passed 的 query-flow/chat-service/model-service 组合回归兜住语义。 |
| 8 | 大体收口 | `scripts/docker_smoke.py`、`requirements-runtime.txt` | `python -m pytest tests/scripts/test_docker_smoke.py tests/test_requirements_profiles.py tests/scripts/test_dev_startup_contracts.py -q` | Docker / requirements / startup 已经有自动化 gate，但历史脚本和文档还没完全统一。 |
| 9 | 部分完成 | `scripts/cleanup_local_artifacts.py`、`tests/scripts/test_repo_hygiene_contracts.py` | `python -m pytest tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q` | cleanup 和 repo hygiene 规则已经建立，但仓库 inventory 减法还没彻底做完。 |
| 10 | 部分完成 | `scripts/build_audit_metrics_snapshot.py`、`docs/20260821-project-audit-remediation/20260821-project-audit-remediation-guide.md` | `python -m pytest tests/scripts/test_build_audit_metrics_snapshot.py tests/scripts/test_docs_entry_contracts.py -q` | 文档闭环已经从“手工维护”进一步收口到可同步、可回归，但历史文档代际仍然偏多。 |
| 11 | 部分完成 | `scripts/cleanup_local_artifacts.py`、`docs/project.md` | `python -m pytest tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q` | 日志和临时产物已经开始规范化，但输出目录、命名和长期归档策略还可以继续收。 |
| 12 | 已整理 | `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`、`docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-pack.md` | `python -m pytest tests/scripts/test_docs_entry_contracts.py -q` | 我会主动区分“能力完成度”和“工程完成度”，不会把项目讲成所有问题都已经清零。 |

---

## 3. 面试时最值得优先记住的 6 条命令

> 原则：你不需要把全套命令都背下来，只要记住最能代表主链路的 6 条。

1. `python -m pytest tests/api/test_chat_scope_contract.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py tests/api/test_chat_service.py tests/api/test_chat_routes.py -q`
   - 用来证明：scope / open api / chat 主链路已经稳定收口。
2. `python -m pytest tests/api/test_runtime_model_loading.py -k "request or overrides_config_store_defaults" -q`
   - 用来证明：请求级 QueryRequest 参数确实会覆盖 runtime 默认配置。
3. `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/api/client.test.js`
   - 用来证明：前端 active KB 语义和 query/history 状态一致性已经补到位。
4. `python -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_eval_contracts.py tests/test_rag_quality_eval_dataset_v8.py -q`
   - 用来证明：refusal / negative contract 已进入正式评测套件，且 history-grounded refusal / answerable follow-up 覆盖都不会被静默删掉。
5. `python -m pytest tests/scripts/test_docker_smoke.py tests/test_requirements_profiles.py tests/scripts/test_dev_startup_contracts.py -q`
   - 用来证明：Docker / requirements / startup 已经有工程 gate，而不是靠口头约定。
6. `python -m pytest tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q`
   - 用来证明：cleanup / repo hygiene 已经开始变成可执行规则。

---

## 4. 被追问时的固定答法

### 4.1 如果对方问“你到底动了哪几个文件？”

优先只说每条问题最关键的 1~2 个：

- scope / `single_kb`：`webapp/src/domain/agentExperience.js`、`api/services/query_scope.py`
- QueryRequest：`api/runtime.py`、`api/services/open_api_service.py`
- 前端一致性：`webapp/src/domain/chatWorkflow.js`
- refusal / eval：`tests/api/test_chat_eval_runner.py`、`scripts/validate_rag_quality_fixtures.py`、`tests/test_rag_quality_eval_dataset_v8.py`
- startup / docker：`start_frontend.ps1`、`scripts/docker_smoke.py`
- prompt / heuristic：`api/services/chat_targeted_fact.py`、`api/services/chat_source_selection.py`
- cleanup / hygiene：`scripts/cleanup_local_artifacts.py`

不要一次抛十几个路径，不然会显得你在堆文件名而不是讲主链路。

### 4.2 如果对方问“你怎么证明不是口头说修好了？”

固定按这三个层次回答：

1. **主链路契约测试**：scope / open api / chat 主链路；
2. **请求与交互一致性测试**：QueryRequest override、前端 query/history；
3. **工程治理测试**：startup / docker / cleanup / repo hygiene。

这样回答比直接背一串 pass 数更像你真的知道系统是怎么被验证的。

### 4.3 如果对方问“还有什么没做完？”

建议固定落在三条：

1. semireal hard negative 还可以继续做深；
2. prompt / heuristic 复杂度还没完全收干净；
3. cleanup / 文档 / 历史兼容层还在继续收口。

---

## 5. 最后一条提醒

这份 cheat sheet 的目标不是让你把材料背成文档管理员，而是让你在面试时能做到三件事：

1. **说得出改了什么**；
2. **说得出怎么证明**；
3. **说得出还剩什么没做完**。

只要这三件事能稳定讲出来，这份材料就已经起作用了。

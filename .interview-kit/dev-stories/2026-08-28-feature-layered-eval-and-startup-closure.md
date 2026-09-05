# 三层评测、启动编排与交付材料的一次性收口

## 基本信息
- 类型：feature
- 日期：2026-08-28
- 相关模块：layered RAG eval、chat orchestration、Docker / startup 链路、Desktop bootstrap、Web QA 工作台、项目审计与面试材料
- 相关文件：`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\scripts\build_eval_v7_holdout.py`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\scripts\build_eval_v8_layered.py`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\tests\api\chat_eval_runner.py`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\api\services\chat_service.py`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\api\services\chat_targeted_fact.py`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\api\services\chat_query_flow.py`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\desktop\src\desktop-bootstrap.js`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\desktop\src\runtime-config.js`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\webapp\src\pages\agent-page\QaWorkbench.jsx`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\Dockerfile`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\requirements-eval.txt`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260820-layered-rag-eval-refresh\20260820-layered-rag-eval-refresh-test-report.md`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260820-docker-rag-eval-refresh\20260820-docker-rag-eval-refresh-test-report.md`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260821-project-audit-remediation\20260821-project-audit-remediation-test-report.md`、`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260828-project-interview-closure\20260828-project-interview-closure-test-report.md`

## 需求背景
这批改动不是单点修 bug，而是把项目从“功能大体能跑”往“评测口径、启动链路、桌面编排、文档证据、面试说法能对上”推进一大步。之前最大的风险不是某一处接口 500，而是不同层面的事实彼此漂移：builder 和 checked-in fixture 可能不一致，Hard case 可能 case pass 了但 run gate 还没闭环，Desktop / start_dev 链路有契约测试但缺少真实 smoke，面试材料里的数字也可能落后于当前测试集合。这个窗口的目标，本质上是把这些分散能力收拢成一个可交付、可解释、可继续演进的工程基线。

## 设计与实现方案
1. 我先把评测资产按 Smoke / Main / Hard 三层重建：用 `scripts/build_eval_v7_holdout.py` 和 `scripts/build_eval_v8_layered.py` 统一生成 `tests/fixtures/rag_quality/eval_v7`、`eval_v8_main`、`eval_v8_hard` 与 `eval_layered_suite.json`，再在 `tests/test_rag_quality_eval_dataset_v7.py`、`tests/test_rag_quality_eval_dataset_v8.py`、`tests/test_rag_quality_eval_builders.py` 里把 schema、coverage gate、builder 对齐关系锁死。
2. 在问答主链路上，我没有继续把逻辑堆回 `chat_service.py`，而是把 targeted-fact、source selection、source reconciliation、negative-contract、exact answer repair、follow-up context 等能力拆到 `api/services/chat_targeted_fact.py`、`chat_query_flow.py`、`chat_source_selection.py`、`chat_answer_repair.py` 等模块，并补上对应单测，降低主服务继续失控膨胀的风险。
3. 在 semireal 运行层，我继续加强 `tests/api/chat_eval_runner.py` 和相关 contract 测试，让 case pass 与最终 `run_passed` 不再是同一件事；scope、evidence、preview、source-count、forbidden-term、negative-contract marker 等 gate 都会参与最终结论。
4. 在 Desktop / 启动链路上，我补了 `desktop/src/desktop-bootstrap.js`、`desktop/src/runtime-config.js`、`desktop/src/python-runtime-resolution.js`、`webapp/src/pages/agent-page/*` 等配套模块，把启动配置、桥接契约、renderer 入口和 QA 工作台的职责拆开，并用 Node 单测和 Windows smoke 去覆盖真实启动过程。
5. 在交付侧，我新增 `Dockerfile`、`requirements-eval.txt`、`requirements-runtime.txt`、`requirements-smoke.txt`，把评测镜像、运行时依赖和 smoke 依赖拆分；同时用 `scripts/build_audit_metrics_snapshot.py`、`scripts/cleanup_local_artifacts.py` 以及多份 test report，把审计、面试、项目总览文档里的数字和当前工作树重新同步。

## 为什么选这个方案
我选“分层收口 + 模块拆分 + 证据同步”这条路，而不是继续追一个单点 1.0 指标，主要是因为当前项目的问题已经不是纯算法问题，而是工程口径一致性问题。评测、启动、文档、桌面桥接如果各自为战，单点优化再漂亮也很难 push 出一个可信基线。把 builder、fixture、contract gate、startup smoke、交付文档一起收口，短期看改动面大，但长期能明显降低“代码说一套、测试跑一套、文档写一套”的维护成本，也更适合面试时解释我到底是怎么把一个原型项目推进到可交付状态的。

## 其他方案与为什么没选
1. 只修 chat 主链路、暂时不动评测与文档：没选，因为当时最大的风险恰恰是评测口径和材料数字漂移，单修代码会继续制造“本地觉得对、对外讲不清”的问题。
2. 继续把规则堆回 `chat_service.py`：没选，因为这个文件已经非常重，再把 targeted-fact、negative-contract、source reconciliation 都塞进去，后续每次修一条 heuristics 都会牵一大片回归。
3. 先把所有工程尾巴都做到完全收尾再提交：没选，因为当前更合理的做法是先形成一个可验证的阶段性基线，把 Smoke / Main / Hard、Desktop startup、Docker eval、文档快照先稳定下来，再继续做下一轮减重和 hard case 深挖。

## 风险与权衡
这批提交最大的风险是“范围太大”，既有 API、测试、Desktop、Web，又有大量文档和报告。为控制这个风险，我采用的方式不是宣称“全项目彻底完成”，而是把每个子域都补上对应的 contract / smoke / report 证据，并在材料里明确哪些已经闭环、哪些仍然要保守讲。另一个权衡是 layered eval 与 interview docs 里确实存在大量 1.0 指标，这很容易被质疑成刷分，所以我没有把结论写成“系统完美”，而是保留了 case pass、run gate、工程完成度三者分离的叙事：即使当前 suite 全绿，也不代表可以停止做 Docker runtime、heuristic 减重和长期维护治理。

## 验证与结果
本次 push 前我**没有再额外重跑一整轮统一回归**；下面记录的是这批提交中已经纳入仓库、且可复核到 test report / 测试文件的真实验证结果：
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260820-layered-rag-eval-refresh\20260820-layered-rag-eval-refresh-test-report.md`：记录了 `python scripts/build_eval_v8_layered.py`、fixture validation、`python -m pytest tests/test_rag_quality_eval_builders.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_contracts.py tests/test_rag_quality_fixtures.py -q`、`python -m pytest tests/api/test_chat_eval_contracts.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_runner.py -q` 等验证；报告结论是 Smoke `24 / 24`、Main `93 / 93`、Hard `36 / 36`，且 `run_passed = true`。
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260820-docker-rag-eval-refresh\20260820-docker-rag-eval-refresh-test-report.md`：记录了 Docker 内 `pytest tests/test_rag_quality_eval_dataset_v7.py -q` 得到 `3 passed in 1.29s`，以及 `run_chat_eval.py` 在 `eval_v7` 上 `24 / 24 passed`、`run_passed=true`。
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260821-project-audit-remediation\20260821-project-audit-remediation-test-report.md`：汇总了 `114 passed`、`83 passed`、`20 passed`、`108 passed`、`npm --prefix desktop test -> 136 passed` 等多组 API / startup / docker helper / desktop / web 回归。
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260828-project-interview-closure\20260828-project-interview-closure-test-report.md`：补充了 `tests/scripts/test_dev_startup_contracts.py -q -> 16 passed`、`tests/scripts/test_start_dev_smoke.py -q -> 1 passed`、`tests/scripts/test_dev_all_smoke.py -q -> 1 passed`、`node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js -> 22 pass` 等最新启动链路与面试材料同步证据。

综合来看，这批改动已经把三层评测、Docker 评测环境、Desktop 启动编排、前端 QA 工作台和项目材料同步推进到了同一个阶段性基线，但不应被表述成“工程已经彻底收尾”。

## 面试表达版本
我这轮做的不是单点提分，而是把项目的评测、启动、桌面编排和对外材料一起收口。具体来说，我先把 RAG 评测拆成 Smoke/Main/Hard 三层，并用 builder、fixture、contract gate 和 semireal runner 把数据集口径锁住；然后把 chat 主链路里过重的 targeted-fact、negative-contract、source 选择逻辑拆成独立模块，避免继续堆在一个超大服务文件里。再往外一层，我把 Desktop bootstrap、runtime config、Web QA 工作台和 Docker eval profile 也补齐了测试与说明文档，所以这次能讲的不只是“分数变好了”，而是“项目已经从原型走到了一个可交付、可验证、可解释的阶段性基线”。同时我也会主动说明，当前 suite 全绿不等于工程完全结束，后面还要继续做 runtime 体重、规则减重和长期维护治理。

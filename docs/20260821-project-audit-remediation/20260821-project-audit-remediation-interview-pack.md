# 20260821 Project Audit Remediation Interview Pack

## 1. 文档定位

这份 `interview-pack` 是把 **1~12 项核心问题 + 30 轮审计结论 + 面试/汇报话术** 压成一份更聚合的成稿，目标是解决三个现实问题：

- `interview-brief` 更像口播主稿，但对“为什么这么判断”仍然偏短；
- `report-script` 更适合 5 分钟汇报，但对面试场景又略重；
- `issues-summary / status-matrix / test-report` 很完整，但临场不适合逐份切换。

所以，这份文档现在承担的是：

1. **一份文件看全局**：快速掌握项目真实进度；
2. **一份文件能开口讲**：30 秒 / 2 分钟 / 5 分钟都能直接用；
3. **一份文件能应对追问**：把“为什么很多指标是 1.0”“为什么还说工程没收完”这类核心追问先压成统一口径。

如果只允许你在面试前再看 **一份** 材料，优先看本文；如果还允许补一份证据文档，再看 `20260821-project-audit-remediation-test-report.md`。

## 2. 一句话结论

> 这个项目已经把 **多知识库 scope isolation、evidence / preview 返回、layered eval 分层评测** 做成了主能力闭环，当前 semireal layered suite 是 `153 / 153`；但工程完成度仍低于能力完成度，剩余重点主要集中在 legacy 入口与历史文档收口、Docker runtime / eval 完整 smoke，以及 cleanup 侧已经做到 file-mode / directory-mode 均已回到 `managed_count = 0` 之后的防回脏巡检，还有 `chat_service.py` 中剩余的 targeted-fact orchestration / hook builder 收口。

## 3. 当前最可信的验证口径

### 3.1 核心结果

- Layered suite：`153 / 153`
- Smoke：`24 / 24`
- Main：`90 / 90`
- Hard：`36 / 36`
- Chat 关键回归：`114 passed`
- 全量非慢测：`1299 passed, 4 deselected`

### 3.2 本轮材料整理时额外确认的口径

- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `41 passed`
- `python -m pytest tests/api/test_runtime_model_loading.py tests/api/test_chat_hook_builders.py tests/api/test_chat_source_answers.py tests/api/test_chat_answer_repair.py tests/api/test_chat_composite_answers.py tests/api/test_chat_targeted_fact.py -q` → `62 passed, 2 warnings`

这组附加验证说明三件事：

1. 上一轮把 refusal / negative contract / `run_passed` 相关纯函数从 `tests/api/chat_eval_runner.py` 抽到 `tests/api/chat_eval_contracts.py` 之后，主回归没有被拆坏；
2. contract gate 的结构化解释字段现在也有了独立测试约束，不再只靠 runner 大文件顺带覆盖；
3. `RuntimeState.build_query_engine(...)` 的 effective config 与 chat_service 当前模块化装配也已经有单独回归锚点，说明 P1-4 / P1-5 更适合进入“保守维护、防止回退”阶段。

### 3.3 这些数字应该怎么讲

不要把这些数字讲成“系统已经没有问题”，更准确的说法是：

- **这些数字证明主能力闭环已经打通**；
- **这些数字不等于工程尾巴已经收完**；
- **现在继续投入的重点，已经从做题过关转向工程收口与长期维护体验。**

## 4. 12 项核心问题压缩版

| # | 问题 | 当前状态 | 面试最短讲法 |
| --- | --- | --- | --- |
| 1 | basic 模式和 single_kb 约束冲突 | 已修 | `basic` / `knowledge` 都显式绑定 active KB，不再伪装成全局检索 |
| 2 | 启动链路 / 桌面链路硬编码 | 基本收敛 | 主路径已不依赖旧绝对路径，端口与 runtime root 可配置，剩余主要在历史文档与 artifact |
| 3 | 项目主入口不统一 | 基本收敛 | README / runbook / 主脚本主线已统一到 `FastAPI + React + Electron`，legacy Streamlit 已退成兼容入口 |
| 4 | QueryRequest 参数未完整打入 chat 主链路 | 已修并补强 | 现在已有 schema → route → query engine → semireal smoke → frontend API 的闭环证据；`test_runtime_model_loading.py` 还额外证明 effective config 会真实传给 `create_query_engine(...)` |
| 5 | 前端把 query 成功和 history 成功绑死 | 已修 | query 成功优先，history 失败只做 notice，不再整次判错；当前已形成 `chatWorkflow.js` → `useAgentChatWorkspace.js` → `QaWorkbench` 的稳定透传 |
| 6 | 评测 harness 对 refusal / negative contract 覆盖不足 | 持续补强 | smoke / main / hard 三层都已有 refusal + negative contract，且 contract gate 已直接联动 `run_passed` |
| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | 部分收敛 | source projection、answer repair、composite answers 已模块化，剩余重点是 targeted-fact orchestration；更真实的风险是 `chat_targeted_fact.py` 也在继续长大 |
| 8 | Docker / requirements / 启动脚本漂移 | 持续收敛 | runtime baseline 与 smoke helper 已明显收口，但完整 `docker build + docker run` smoke 仍待补 |
| 9 | 根目录临时文件、日志、调试脚本较多 | 部分收敛 | file-mode / directory-mode 均已归零 |
| 10 | 文档闭环不够满 | 部分收敛 | 审计目录已经能统一引用，但历史长文、旧 artifact 和旧叙事仍待继续收口 |
| 11 | 日志与临时产物治理需要规范化 | 已收敛 | 治理能力与单测已建立，当前 file-mode / directory-mode 均已回到 `managed_count = 0`，重点转为后续重点转为防回脏、定期巡检与受控 apply 预案固化 |
| 12 | 面试表述要区分能力完成度与工程完成度 | 已整理 | 现在已经有 brief / report / issues / guide / test-report 的统一材料体系 |

## 5. 30 轮审计压缩成 6 个主题，该怎么讲

### 5.1 主题 A：项目已经不处在“答不对题”的阶段

当前 layered suite `153 / 153`，说明 scope、evidence、preview、cross-source fact 这些主能力已经闭环。也就是说，这个项目的主矛盾已经不是“系统会不会答”，而是“工程层怎么把已经做出来的能力讲清楚、守住并继续维护”。

### 5.2 主题 B：工程完成度落后于能力完成度

最真实的对外说法不是“项目 fully finished”，而是：

> **能力完成度高于工程完成度。**

能力层可以讲：多 KB scope、evidence / preview、分层评测、拒答与边界契约。
工程层要诚实讲：legacy 入口、Docker smoke、目录级 backlog、命名债务、大文件债务仍在继续收口。

### 5.3 主题 C：cleanup 已经从“发现问题”进入“真实执行治理”

现在不是只会说“根目录有点乱”，而是已经有：

- dry-run；
- apply；
- 回归测试；
- file-mode 与 directory-mode 的分层口径。

所以这部分可以讲成“我不只是指出工程问题，也开始建立可重复执行的治理能力”。

### 5.4 主题 D：Docker / requirements 的问题已从“语义漂移”变成“构建确定性待继续补强”

这里最值得讲的是定位过程：

- 先发现 `minimal` / `runtime` 语义不稳定；
- 再定位到顶层 `llama_index` metapackage 会把云侧依赖链拉回来；
- 再把 baseline 收回 `llama-index-core==0.11.19` + 显式 integrations；
- 再补 smoke helper 的 host-port 自分配。

这类讲法更能体现工程判断力，而不是只说“我改了 requirements”。

### 5.5 主题 E：大文件和命名债务是长期维护成本来源

`chat_service.py` 虽已明显收敛，但 targeted-fact orchestration 和 hook builder 还没有完全拆净；当前复杂度热点已经比较明确：`chat_service.py` `1166` 行、`chat_targeted_fact.py` `838` 行、`kb_service.py` `2954` 行、`AgentPage.jsx` `792` 行。再叠加 `ThinkRAG / NorthAgent / Foxglove` 多套命名并存，会让文档、脚本和面试叙事都变重。

### 5.6 主题 F：材料层已经基本闭环，但必须统一引用入口

现在最危险的不是“没材料”，而是“材料太多、口径混用”。所以这一轮整理的核心动作之一，就是把材料压成更稳定的“一主多从”：

- 主入口：本文 `interview-pack`
- 口播主稿：`interview-brief`
- 长讲稿：`report-script`
- 证据与指标：`test-report`
- 总表与整改路线：`issues-summary / status-matrix / plan`

## 6. 面试 / 汇报直接可用话术

### 6.1 30 秒版本

我做的不是一个简单的文档问答 demo，而是把 **多知识库边界、证据返回、preview 预览和分层评测** 做成系统能力。现在主能力已经闭环，当前 semireal layered suite 是 `153 / 153`。但我不会把它讲成“项目已经完全 finished”，因为工程侧还在继续收口，比如 legacy 入口、目录级 backlog、Docker 完整 smoke，以及 chat 主链里剩余的 targeted-fact orchestration。

### 6.2 2 分钟版本

我这轮主要做了三件事。第一，把主能力做成闭环：多知识库 scope isolation、evidence / preview 返回、以及 Smoke / Main / Hard 的 layered eval。第二，把关键契约做对：`basic` / `knowledge` 现在都要求显式 active KB，请求级 QueryRequest 参数也已经真正打进 route、query engine、semireal smoke 和 frontend API 链路，runtime 侧也有 `create_query_engine(...)` effective config 的回归证据；前端 query 成功也不会再因为 history 写回失败而被整体判错。第三，用测试、评测和治理来证明这些改动不是拍脑袋：当前 layered suite `153 / 153`，chat 关键回归 `114 passed`，全量非慢测 `1299 passed, 4 deselected`。所以我会把项目定义成：主能力闭环已经成型，但工程完成度还在继续补齐。

### 6.3 5 分钟版本提纲

1. 先讲项目定位：本地知识库助手，不是简单文档问答 demo；
2. 再讲三条主能力：多 KB scope、evidence / preview、layered eval；
3. 再讲 4 个已经修通的问题：basic/single_kb、QueryRequest 主链路、query/history 解耦、主评测闭环；
4. 再讲 4 个正在收口的问题：启动入口统一、legacy 清理、Docker baseline、targeted-fact orchestration；
5. 最后强调：能力完成度高于工程完成度，下一步重点是工程收尾而不是重新证明能答题。

## 7. 高频追问统一回答

### 7.1 为什么现在很多指标是 1.0？

因为当前 semireal layered suite 的主能力题已经全部通过，说明我定义的主能力闭环打通了。但这不等于真实世界所有问题都完美，更不等于工程尾巴已经没了。现在的数据更适合被解释成“主链路稳定”，不是“系统已经绝对正确”。

### 7.2 如果都 1.0 了，为什么还说工程没完成？

因为评测全绿只证明主能力通过了，不代表 legacy 入口、Docker smoke、文档口径、目录治理、大文件拆分这些工程问题都已经收尾。这个项目现在最真实的状态就是：**能力先成型，工程后追平。**

### 7.3 你具体是怎么把分数做上去的？

不是靠刷 prompt 一把梭，而是靠三层动作叠加：

1. 把 scope、evidence、preview 这些 contract 做实；
2. 把 targeted fact、answer repair、composite answers 做成更清晰的模块边界；
3. 把评测从一套大杂烩拆成 layered suite，再补 refusal / negative contract / hard case gate。

### 7.4 OCR 指标重要不重要？

不是所有场景都同等重要，但不能因为主业务更看重 QA 准确率，就完全忽略 OCR。因为 OCR 一旦错，preview 落点、evidence 命中和拒答边界都会一起受影响。所以更准确的说法是：**OCR 不是唯一核心指标，但它会影响证据链可信度。**

## 8. 下一步该怎么讲，才显得靠谱

如果面试官问“下一步你还会做什么”，优先讲这四件事：

1. 继续拆 `chat_targeted_fact.py` 与 `chat_service.py` 交界处剩余的 targeted-fact orchestration，并整理 hook builder / dependency registry；
2. 把目录治理重点切到防回脏、定期巡检与受控 apply 预案；当前 file-mode / directory-mode 均已回到 `managed_count = 0`；
3. 补 Docker runtime / eval 的真实 `docker build + docker run` smoke；
4. 继续补 OCR / preview hygiene / source_count 的负向评测题。

## 9. 推荐搭配阅读顺序

### 9.1 面试前 10 分钟

1. 本文 `20260821-project-audit-remediation-interview-pack.md`
2. `20260821-project-audit-remediation-test-report.md`
3. `docs/interview/ThinkRAG_面试问答.md`

### 9.2 做 5 分钟汇报

1. 本文第 6 节
2. `20260821-project-audit-remediation-report-script.md`
3. `20260821-project-audit-remediation-test-report.md`

### 9.3 继续整改代码

1. `20260821-project-audit-remediation-issues-summary.md`
2. `20260821-project-audit-remediation-status-matrix.md`
3. `20260821-project-audit-remediation-plan.md`

## 10. 最后一段收口话术

> 我会把这个项目定义成：一个已经把多知识库 scope、evidence / preview 和 layered eval 做成闭环的本地知识库助手。现在最值得继续投入的，不是追求表面上的“更多 1.0”，而是把启动链路、legacy 入口、目录治理、Docker smoke，以及 prompt/heuristic 的职责边界继续做实。这样讲既能体现我做出了东西，也能体现我对系统边界和工程完成度有真实判断。


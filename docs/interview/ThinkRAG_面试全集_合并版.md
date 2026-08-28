# ThinkRAG 面试全集合并版（当前导航版）

> 这份文件现在只负责**导航和跳转**，不再承载长问答正文。
>
> 当前主线请统一按 **FastAPI + React + Electron + LlamaIndex** 来讲；
> 当前入口请优先切到 `docs/20260825-p0-p2-status-closure/` 这组收口材料。
>
> 推荐阅读顺序：
> 1. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md`
> 2. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-complete-guide.md`
> 3. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`
> 4. `docs/interview/ThinkRAG_面试问答.md`
> 5. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`

## 1. 这份文档怎么用

如果你时间很紧，只记两件事：

- **先定当前口径**：项目已经收口成 `FastAPI + React(Vite) + Electron + LlamaIndex` 主线；
- **再定边界表达**：主能力闭环已经形成，但工程完成度仍在继续追赶。

如果你想把这批材料**一次性整理完成**，最稳的顺序是：

1. 先看 `20260825-p0-p2-status-closure-master-guide.md` 第 2、4、5 节；
2. 再看 `20260825-p0-p2-status-closure-interview-complete-guide.md`；
3. 再看 `20260825-p0-p2-status-closure-status-report.md` 和 `20260825-p0-p2-status-closure-rounds-rollup.md`。

## 2. 30 秒版本

我做的不是一个简单的本地问答 demo，而是一个已经把**知识库作用域约束、evidence / preview、QueryRequest 主链路、layered eval**做成闭环的本地知识库助手。当前主线是 **FastAPI + React + Electron**；我更愿意把它讲成“主能力闭环已经打通，但工程治理仍在继续收尾”的系统，而不是“所有问题都已经清零”的 finished 项目。

## 3. 2 分钟版本

面试里建议按“三层结构 + 三类改进”来讲：

### 3.1 三层结构
1. **交互层**：React Knowledge Workspace + Agent Workspace，由 Electron 复用；
2. **服务层**：FastAPI 提供知识库、预览、问答、健康检查等接口；
3. **能力层**：LlamaIndex 负责摄取、索引与查询编排，配合 evidence / preview / scope 契约。

### 3.2 三类改进
1. **边界改进**：`basic` / `knowledge` 都显式绑定 active KB，不再伪装成全局盲查；
2. **链路改进**：QueryRequest 参数真正打进 route + runtime query engine，query/history 也已解耦；
3. **验证改进**：layered eval、contract test、overlap matrix 让“为什么我说当前主路径更稳”有真实依据。

## 4. 最好背下来的 4 句话

1. 当前主线不是旧 Streamlit 入口，而是 **FastAPI + React + Electron**。
2. 当前最大的亮点不是“模型很强”，而是 **scope / evidence / preview / request-contract / layered eval 形成闭环**。
3. 当前最大的瓶颈不是“功能做不通”，而是 **工程治理和长期维护体验还在收尾**。
4. 所以面试里要主动区分 **能力完成度** 和 **工程完成度**。

## 5. 常见追问索引

- 想看统一总入口：看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md`；
- 想先把 12 项问题、30 轮主题和最新验证口径一次性整理清楚：先看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md` 第 4、5 节；
- 想先一次性过完整讲稿总览：看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-complete-guide.md`；
- 想讲 30 秒 / 2 分钟 / 5 分钟稳定话术：看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`；
- 想解释为什么很多指标会到 1.0：看 `docs/interview/ThinkRAG_面试问答.md` 第五、六、七节；
- 想把追问稿里‘1~30 轮问题压成 6 个主题’和‘临场压成 5 分钟补充说法’一起看：看 `docs/interview/ThinkRAG_面试问答.md` 第十三、十四节；
- 想讲 1~30 轮问题怎么压缩成 6 个主题：看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-rounds-rollup.md`；
- 想看 12 项问题当前状态：看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`；
- 想看最近真实 heuristic 收口案例：看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-overlap-matrix.md`；
- 想追更深的审计证据：再去看 `docs/20260821-project-audit-remediation/`，尤其是 `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md`。

## 6. 说明

旧版合并稿里大量 `Streamlit`、`app.py`、`frontend/state.py`、`session_state` 等表述描述的是**历史阶段材料**。为了避免继续误导当前面试口径，本文件不再保留那套旧大纲，统一收敛到上述当前导航路径。

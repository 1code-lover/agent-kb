# 20260828 Project Interview Closure Spec

## 1. 这份文档解决什么问题

这份文档用于把当前仓库里已经存在的多套审计、状态、面试材料整理成一个 **2026-08-28 仍然可直接使用的统一导航入口**，避免继续在 `docs/20260821-project-audit-remediation/`、`docs/20260825-p0-p2-status-closure/`、`docs/interview/` 之间来回跳。

适用场景：

1. 面试前快速复习“项目定位 / 亮点 / 指标 / 边界”；
2. 汇报时需要一份“先讲结论，再讲证据，最后讲未完成项”的总入口；
3. 继续按 P0 / P1 / P2 做代码整改前，需要先知道哪些问题已收口，哪些仍是工程尾巴。

## 2. 当前统一口径

截至 **2026-08-28**，建议统一这样描述项目：

- **项目定位**：本地优先知识库助手；
- **主线架构**：FastAPI + React(Vite) + Electron + LlamaIndex；
- **能力亮点**：single-kb scope、evidence / preview、请求级 QueryRequest 参数生效、query / history 解耦、layered eval；
- **状态表述**：**能力完成度高于工程完成度**；
- **当前 P0 新进展**：开发启动链路的 Web/Desktop 共享 helper 已补齐 headless smoke，`start_dev.ps1` 与 `scripts/dev-all.ps1` 的 Windows smoke 当前都能通过。

不建议再用下面这些口径：

- “只是一个简单 RAG demo”；
- “现在所有工程问题都彻底做完了”；
- “主要价值就是把指标刷到 1.0”；
- “OCR 不重要，所以相关链路不用讲”。

## 3. 现在看哪几份材料最有用

### 3.1 如果只想 5 分钟整理完

按这个顺序读：

1. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260828-project-interview-closure\20260828-project-interview-closure-spec.md`
2. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260828-project-interview-closure\20260828-project-interview-closure-test-report.md`
3. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-rounds-rollup.md`
4. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-interview-script.md`
5. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\interview\ThinkRAG_面试问答.md`

### 3.2 如果要核对“1~30 轮问题到底收口到哪里了”

优先看：

1. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-status-report.md`
2. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-rounds-rollup.md`
3. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260821-project-audit-remediation\20260821-project-audit-remediation-issues-summary.md`

### 3.3 如果要回答“为什么很多指标是 1.0”

优先看：

1. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260820-layered-rag-eval-refresh\20260820-layered-rag-eval-refresh-test-report.md`
2. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260820-rag-interview-eval\20260820-rag-interview-eval-test-report.md`
3. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\interview\ThinkRAG_面试问答.md`

## 4. 面试时建议固定讲的四层结构

### 4.1 第一层：项目是什么

> 这是一个本地优先知识库助手，不是简单把模型接到文档上的 demo。主线已经统一到 FastAPI + React(Vite) + Electron + LlamaIndex。

### 4.2 第二层：我具体补了什么

建议固定讲这五点：

1. 把 `basic / knowledge` 模式和后端 `single_kb` 约束统一；
2. 把 QueryRequest 的请求级参数真正打进 runtime query engine；
3. 把 query 成功和 history 回写解耦；
4. 把 evidence / preview / scope 做成可验证的契约；
5. 把 layered eval、startup contract、docs contract、repo hygiene 做成可复跑证据。

### 4.3 第三层：我怎么证明不是嘴上说说

当前推荐先报三组数字：

- layered suite：`153 / 153`；
- chat 主链路与 eval contract：看 `docs/20260825-p0-p2-status-closure/` 里的状态报告；
- 启动 / 文档 / legacy / cleanup / repo hygiene：本轮已更新到最新快照，口径以 `docs/project.md` 和 `docs/20260821-project-audit-remediation/` 为准。

### 4.4 第四层：我会主动承认什么还没做完

当前仍适合坦诚讲的工程尾巴：

1. compatibility wrapper 和历史脚本还在继续收口；
2. prompt 契约与 heuristic 复杂度治理还没彻底结束；
3. refusal / hard negative / semireal follow-up 还能继续扩样本；
4. 根目录临时产物、日志和历史文档仍在持续治理。

## 5. 2026-08-28 这轮新增的整理价值

这轮除了继续做 P0 启动链路修复，还补了两件对“材料可用性”直接有帮助的事：

1. **把 audit metrics 快照重新同步到了文档**：`docs/20260821-project-audit-remediation/`、`docs/project.md`、`docs/interview/ThinkRAG_面试问答.md` 等材料里的 bundle 计数已更新到当前工作树对应的最新值；
2. **验证 docs entry contract 重新回绿**：说明面试材料和项目基线数字没有继续漂移。

## 6. 下一步继续推进时的推荐顺序

如果接下来继续 Route A（真实改代码），建议顺序还是：

1. 继续统一启动入口和 helper；
2. 继续减少 legacy / compatibility wrapper；
3. 继续补 prompt / heuristic 减重；
4. 继续扩 refusal / negative contract / semireal hard negative。

如果切 Route B（准备面试表达），建议顺序是：

1. 先背 30 秒版本；
2. 再背 2 分钟版本；
3. 再看“为什么都是 1.0”与“是不是都做完了”的固定回答；
4. 最后只保留 2~3 个最能讲出工程价值的真实修复案例。

# 20260828 Project Interview Closure Test Report

## 1. 本轮做了什么

本轮不是再写一份“感觉没问题”的总结，而是基于 **当前工作树** 做了两类真实整理：

1. 继续核实 P0 启动链路当前是否真的可用；
2. 把面试 / 审计 / 项目基线材料中的 bundle 计数同步到当前测试集合，避免旧数字继续误导后续汇报。

## 2. 本轮实际执行的命令与结果

### 2.1 P0 启动链路 / 桌面链路

- `python -m pytest tests/scripts/test_dev_startup_contracts.py -q` → `16 passed`
- `python -m pytest tests/scripts/test_webapp_contracts.py -q` → `8 passed`
- `python -m pytest tests/scripts/test_start_dev_smoke.py -q` → `1 passed`
- `python -m pytest tests/scripts/test_dev_all_smoke.py -q` → `1 passed`

结论：

- `start_dev.ps1` 当前 Windows smoke 已通过；
- `scripts/dev-all.ps1` 的 headless desktop smoke 当前已通过；
- 说明共享 helper 收口后，P0 启动链路不再停留在文本 contract，通过了实际运行态验证。

### 2.2 单知识库 / 请求级参数 / 前端状态一致性

- `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js` → `22 pass`
- `python -m pytest tests/api/test_runtime_model_loading.py -k "request or overrides_config_store_defaults" -q` → `2 passed, 32 deselected`
- `python -m pytest tests/api/test_chat_eval_contracts.py tests/test_rag_quality_eval_dataset_v8.py -q` → `31 passed`

结论：

- `basic / knowledge` 模式显式绑定 KB 的前端契约仍在；
- QueryRequest 请求级 override 仍有后端回归保护；
- eval contract 与 dataset v8 基础约束仍可通过。

### 2.3 文档 / 入口 / 审计材料同步

- `python scripts/build_audit_metrics_snapshot.py --sync-docs` → 已更新 `docs/20260821-project-audit-remediation/`、`docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`、`docs/interview/ThinkRAG_面试问答.md`、`docs/project.md`
- `python -m pytest tests/scripts/test_docs_entry_contracts.py tests/test_legacy_streamlit_entry.py -q` → `31 passed`

结论：

- 之前由于新增测试文件，审计文档里的 bundle 数字已经落后于当前集合；
- 本轮已用 snapshot 同步脚本把数字更新回当前状态；
- docs entry contract 重新回绿，说明“面试口径”和“当前工作树的测试集合”重新对齐。

## 3. 当前更适合对外讲的结论

### 3.1 可以稳讲的

1. 项目主线口径仍是 **FastAPI + React(Vite) + Electron + LlamaIndex**；
2. `single_kb` scope、QueryRequest runtime override、query / history 解耦、layered eval 当前都能在现有材料中找到测试证据；
3. 启动链路当前不仅有契约测试，也有实际 smoke 证明；
4. 审计和面试文档已经重新同步到当前 bundle 计数，不再继续引用旧的 `80 passed` / `17 passed` 等过时数字。

### 3.2 仍然要保守讲的

1. layered suite `153 / 153` 只说明当前 semireal / layered 边界内全绿；
2. prompt 契约和 heuristic 复杂度治理还在继续；
3. legacy 入口、兼容 wrapper、根目录产物治理并没有因为几轮文档同步就彻底结束；
4. 面试时仍应主动区分“能力完成度”和“工程完成度”。

## 4. 本轮整理后，最推荐看的四份文件

1. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260828-project-interview-closure\20260828-project-interview-closure-spec.md`
2. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-rounds-rollup.md`
3. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-interview-script.md`
4. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\interview\ThinkRAG_面试问答.md`

## 5. 本轮后的推荐使用方式

### 5.1 面试前 10 分钟

按顺序看：

1. 本文；
2. `20260828-project-interview-closure-spec.md`；
3. `20260825-p0-p2-status-closure-interview-script.md`；
4. `ThinkRAG_面试问答.md` 中“为什么很多指标是 1.0”和“是不是都做完了”这两段。

### 5.2 继续做代码整改前

先看：

1. `20260825-p0-p2-status-closure-status-report.md`；
2. `20260821-project-audit-remediation-issues-summary.md`；
3. 再决定继续做 P0 启动链路收口，还是转去 P1 的 heuristic 减重与负向评测扩样本。

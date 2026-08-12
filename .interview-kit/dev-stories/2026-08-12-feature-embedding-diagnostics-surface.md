# Embedding Diagnostics Surface

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：Knowledge Workspace、roundtrip 诊断脚本、runtime health
- 相关文件：`scripts/diag_roundtrip_support.py`、`webapp/src/domain/ocrWarmup.js`、`webapp/src/pages/KnowledgePage.jsx`、`webapp/src/components/kb/KbWorkspaceHeader.jsx`

## 需求背景
上一轮已经让 runtime 在本地 embedding 缓存缺失时快速失败，避免桌面/API 启动卡在 HuggingFace 远程下载。但如果诊断只停留在 `/api/health` 原始 JSON，用户和评测脚本仍然只能看到笼统的 `embedding_warmup` 阻塞，不容易判断下一步该准备本地模型缓存还是检查其他问题。

## 设计与实现方案
`scripts/diag_roundtrip_support.py` 增加 `blocker_details`，当 runtime 未 ready 时把 `embedding_diagnostics.local_path_exists`、`allow_remote_download`、`local_path` 和 `hf_endpoint` 写进 timeout 错误消息。所有依赖 `wait_for_runtime_ready()` 的 roundtrip 脚本都会继承这个解释力。

前端侧复用 Knowledge Workspace 头部已有的运行时状态块，新增 `buildEmbeddingWarmupSummary()`，从完整 `/api/health` 里同时生成 Embedding 和 OCR 两条摘要。缓存缺失且运行时禁止远程下载时，界面直接显示“Embedding 缓存缺失”，并提示需要准备的本地路径。

## 为什么选这个方案
roundtrip 脚本和 Knowledge Workspace 是当前最靠近用户与真实验证的两个入口。把诊断放到这两处，比只写文档或只保留后端字段更能减少误判：自动化报告能直接说明阻塞原因，桌面/Web 用户也能在导入前看到 runtime 是否真正可用。

## 风险与权衡
前端这次只展示诊断，不提供一键下载模型缓存。因为下载依赖 HuggingFace mirror 和本地代理状态，直接在 UI 里触发会重新引入不可控长等待。后续可以在有稳定模型源后再做显式的缓存准备动作。

## 验证与结果
`node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`88 passed`。

`cd webapp && npm run build`：通过。

`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/test_diag_roundtrip_support.py tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`40 passed, 1 warning`。

## 面试表达版本
我做了一个诊断体验的补强：后端已经能判断 embedding 本地缓存缺失，但脚本和页面原来只会告诉你 runtime 没 ready。我把 health 里的 embedding diagnostics 接进 roundtrip timeout 和知识库页面头部，让报告和用户界面都能直接看到本地缓存路径、远程下载是否禁用，以及下一步该准备模型缓存。这类改动不复杂，但能显著减少排查时间。

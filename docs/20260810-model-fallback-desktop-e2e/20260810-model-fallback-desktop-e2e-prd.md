# 20260810 Model Fallback Desktop E2E PRD

## 背景

粮仓知识库检索质量已收口，当前真实风险转向模型配置韧性和桌面端真实工作流。此前完整 QA 评估曾因 `AllocationQuota.FreeTierOnly` 中途失败，说明只依赖人工切换模型会让长评估和桌面问答不稳定。

## 目标

1. 自动识别模型额度耗尽、HTTP 403、HTTP 401、模型不可用等错误。
2. 当前模型失败时，自动切换到已配置且可用的候选模型。
3. API 返回当前模型健康状态，前端可展示健康状态和最近 fallback 信息。
4. 粮仓 QA 评测脚本支持断点续跑，避免长评估中途失败后全部重跑。
5. 完成桌面端真实工作流 E2E 验证：启动、模型配置、问答、引用、preview、跨 KB 隔离。
6. 收口 macOS 正式发布入口：签名、公证、stapling、CSP 和安装后校验；公证支持 Apple ID、App Store Connect API Key、Keychain profile 三种凭证策略，并保证每个 app 只提交一次公证。

## 范围

### 本轮包含

- 后端模型错误分类、候选模型枚举、fallback 选择和状态持久化。
- Agent 高级模式直连聊天支持 Ollama，并在当前模型不可用时复用同一套自动 fallback。
- `/api/model/options` 或新增 API 输出模型健康状态。
- 前端模型页/Agent 页显示当前模型健康状态。
- `scripts.run_grain_qa_eval` 支持恢复已有报告并跳过已完成用例。
- 桌面端启动和真实链路验证脚本/报告。
- Electron CSP、hardened runtime、entitlements、Developer ID 签名检查、notarytool 公证和 Gatekeeper/stapler 后置校验。
- Apple ID、App Store Connect API Key、Keychain profile 三种 notarization 凭证策略；本地发布优先推荐 Keychain profile。
- 显式关闭 electron-builder 内建自动公证，由严格 afterSign hook 单次提交，避免重复公证。
- 更新 `docs/project.md` 最近提交和下一阶段目标。

### 本轮不包含

- 新增第三方模型供应商注册 UI 大改。
- 改造 LLM SDK 底层调用协议。
- 重做检索排序或粮仓 QA 题集。

## 验收标准

- 单元测试覆盖 401、403、额度耗尽、模型不可用的分类与 fallback 选择。
- 模型 fallback 后 `current_llm_info` 更新为可用模型，健康状态记录最近错误和切换结果。
- 基础问答、知识库问答和 Agent 直连聊天均能在可恢复模型错误后自动切换并重试一次；Agent 直连 Ollama 不要求 API Key。
- API 能返回模型健康状态，前端能显示健康状态文本。
- QA eval 支持 `--resume`，已有报告中成功用例不会重复请求 API。
- 桌面端 E2E 报告覆盖模型配置、KB 问答、引用来源、preview、跨 KB 隔离。
- `release:preflight` 接受三种完整公证凭证策略中的任意一种，对部分配置输出缺失字段，并始终要求有效 Developer ID Application 身份和 notarytool。
- macOS 构建只执行一次公证提交；release config verifier 必须确认自定义 afterSign hook 已启用且 electron-builder 内建 notarization 已关闭。
- 正式 `release:mac` 产物通过 codesign、Gatekeeper、stapler、包内容和安装后工作流验证。
- 全量非 slow 测试通过，前端 Node 测试和构建通过。

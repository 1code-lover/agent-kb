# 自动 fallback 后问答页状态滞后的修复

## 基本信息
- 类型：bug
- 日期：2026-08-14
- 相关模块：聊天服务、桌面 Web 问答页、模型健康状态
- 相关文件：`api/services/chat_service.py`、`webapp/src/pages/AgentPage.jsx`、`tests/api/test_chat_service.py`、`webapp/src/api/chat.test.js`

## 问题现象
模型请求失败并自动切换到候选模型后，后端已经更新了当前模型和 `fallback_applied` 健康状态，但 Agent 问答页可能继续显示旧模型和旧提示，直到模型 options 的 60 秒缓存过期或页面重新触发查询。用户因此无法在当前问答完成后立即确认自动切换是否生效。

## 根因分析
问答接口只返回答案、来源和 evidence，没有返回本次请求结束时的 `model_health` 快照。前端的模型状态来自独立的 `/api/model/options` 查询，该查询设置了 60 秒 `staleTime`；聊天成功回调只刷新会话历史，没有主动刷新模型 options。服务端状态已经正确持久化，但前端没有及时重新读取它。

## 解决方案
1. 在聊天服务的正常回答、无相关来源拒答和 fallback 重试成功路径中统一加入 `model_service.get_model_health()` 返回值。
2. 在 `AgentPage.jsx` 的聊天 mutation 成功回调中保留历史刷新，并主动调用 `modelOptionsQuery.refetch()`，让当前模型名称、健康状态和自动切换提示立即同步。
3. 用 API 透传测试和聊天服务三条路径测试固定响应契约，确保后续不会只修前端而遗漏服务端状态。

## 为什么选这个方案
服务端是健康状态的权威来源，直接在 query 响应中返回快照可以让接口调用方获得本次请求的明确结果；前端主动 refetch 的改动范围小，不需要重做 React Query 缓存键或引入新的全局状态，也能同步 `current_llm_info` 和完整 provider 列表。保留原有单次 fallback 重试、候选排序和知识库处理，降低回归风险。

## 其他方案与为什么没选
1. **只把 `staleTime` 改为 0（推断）**：仍不能保证 mutation 成功后立即重新请求，且会增加普通页面渲染的网络请求。
2. **只在前端根据错误文本猜测已切换（推断）**：前端无法可靠知道最终选中的 provider/model，也会与服务端持久化状态产生漂移。

## 验证与结果
- TDD 红灯：新增契约断言后，原实现的 `tests/api/test_chat_service.py` 出现 2 个 `KeyError: model_health` 失败。
- 修复后：
  - `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_chat_service.py -q -m 'not slow'`：`43 passed`。
  - `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m 'not slow'`：`783 passed, 1 deselected, 35 warnings`。
  - `cd webapp && node --test src/domain/*.test.js src/api/*.test.js src/store/*.test.js`：`89 passed`。
  - `cd webapp && npm run build`：通过。
  - `cd desktop && node --test src/*.test.js scripts/*.test.js`：`64 passed`。
- 本轮没有 Apple Developer 证书或公证凭证，因此正式签名、公证、stapling 和安装后回归仍未完成。

## 面试表达版本
我发现模型自动 fallback 虽然已经在后端生效，但问答页的模型状态来自一个 60 秒缓存的独立接口，所以用户看到的仍可能是旧模型。我的修复是让聊天接口直接返回请求结束时的 `model_health`，并在前端问答成功后主动刷新模型 options。这样既同步了最终 provider/model，也保留了已有的 fallback 候选策略和知识库隔离逻辑。最后我用先失败后通过的契约测试、全量 Python 测试、Web 测试/build 和 Electron 测试验证了这次修复。

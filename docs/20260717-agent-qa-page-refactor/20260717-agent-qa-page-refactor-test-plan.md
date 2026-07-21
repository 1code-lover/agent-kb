# 20260717-agent-qa-page-refactor-test-plan

## 1. 目标

验证 `/agent` 问答页重构后：
1. 基础问答可正常发送与展示回答；
2. 知识库问答必须显式选择 KB 且可按 KB 范围返回结果；
3. Agent 高级模式仍可进入；
4. 构建与文档门禁通过。

## 2. 覆盖范围

- 纯规则测试：问答模式与 payload 拼装
- 构建测试：Vite 打包
- 手工烟测：浏览器页面交互
- 文档/格式：`git diff --check`

## 3. 用例

### TC-01 基础问答 payload
- 输入：基础问答 + 普通问题
- 预期：不传 `kb_ids`

### TC-02 知识库问答 payload
- 输入：知识库问答 + `kb_id=grain-knowledge-base`
- 预期：传 `kb_ids=[grain-knowledge-base]`

### TC-03 知识库未选择保护
- 输入：切到知识库问答但不选 KB
- 预期：发送按钮禁用或提交时报错提示

### TC-04 问答页结构
- 输入：打开 `/agent`
- 预期：可见三个入口、范围说明、聊天主区

### TC-05 Agent 高级模式回归
- 输入：切到高级模式
- 预期：原 timeline / input / details 仍在

## 4. 正式命令

```powershell
node --test webapp/src/domain/agentExperience.test.js webapp/src/api/response.test.js webapp/src/domain/kbSelection.test.js
cd webapp; npm run build; cd ..
git diff --check
```

## 5. 通过标准

- 自动化命令全部通过
- 手工烟测 5/5 通过
- 无新增格式错误

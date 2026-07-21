# Markdown 上传 400 排查计划

## 目标
定位“实习知识库”上传 Markdown 返回 HTTP 400 的真实原因；如确认是代码缺陷，按仓库阶段流程补文档、TDD 修复、测试和报告。

## 范围
- 当前 React 页面 `/knowledge` 与 FastAPI `/api/kb/file/import`
- 文件扩展名、multipart、KB 校验、文件落盘、索引加载和错误响应
- 不重复上传用户文件，不清理现有工作区改动

## 阶段

### Phase 1：只读证据采集
Status: in_progress
- 浏览器页面错误信息与控制台
- access/backend 日志、registry、目标目录
- 上传后端与前端错误处理代码

### Phase 2：确定根因与影响范围
Status: pending
- 锁定具体 400 分支
- 判断是否包含独立的错误展示或编码问题

### Phase 3：按规范补齐 bugfix 文档并评审
Status: pending
- 在 `docs/20260716-markdown-upload-400/` 建立需求、计划、测试方案
- 如需编码，先写失败测试

### Phase 4：最小修复与验证
Status: pending
- 实施最小修复
- 定向回归、全量门禁、覆盖率和格式检查

### Phase 5：测试报告与开发故事
Status: pending
- 更新项目文档、测试报告和开发故事

## 安全约束
- 不 reset/clean，不覆盖无关未提交改动
- 不使用用户个人 Markdown 文件做自动复现
- 浏览器只读检查，未经确认不触发上传

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|

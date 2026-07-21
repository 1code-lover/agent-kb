# Findings

## Confirmed before implementation
- 工作区写入探针成功，当前不是只读环境。
- 已批准的多知识库前端 PRD/FRD 要求“先选知识库，再上传”。
- 当前 KbContext 将 selectedKbId 初始化为 default，导致静默选择。
- KbSidebar 已有知识库列表与 CRUD，但创建后未自动选择新 KB。
- KbUpload 依赖上下文 selectedKbId，但没有显式的必选目标保护。
- Grain KB 人工测试指南已记录 Issue-01 为 P1。

## Confirmed after implementation
- 上传与网页导入必须绑定用户显式选择的 active KB，`default` 不再自动选中。
- Axios 拦截器已经返回 `response.data`，前端组件必须通过统一的 `readApiData()` 兼容单层响应，不能再次读取 `res.data.data`。
- 浏览器 smoke 确认粮仓库 14 个文档均保持 `grain-knowledge-base` 隔离；真实上传留给临时 smoke KB，避免污染正式数据。

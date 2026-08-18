# 需求追踪矩阵（RTM）

| 需求 | 设计模块 | 计划测试 | 验收证据 |
|---|---|---|---|
| FR-MIG-01/02 扫描与 dry-run | `kb_migration_service.py` | 历史节点分组、异常、无文件变更测试 | dry-run 文件树哈希前后一致 |
| FR-MIG-03 备份 | migration backup/manifest | 排除递归目录、SHA-256 校验、权限失败 | 备份 manifest 与验证结果 |
| FR-MIG-04/06 重建校验 | `IndexManager.insert_nodes` 适配 | 多 KB 迁移、重载、摘要一致、跨库不可见 | 专项集成测试 |
| FR-MIG-05/07 幂等重试 | 状态机与 plan digest | 重复执行、目标冲突、单 KB 注入失败后重试 | 状态结果和测试日志 |
| FR-MIG-08 回滚 | rollback API | 非工具备份拒绝、清单篡改拒绝、成功恢复 | 回滚集成测试 |
| FR-MIG-09 状态/UI | router + Web 卡片 | API 状态、领域函数与渲染状态测试 | Web 测试/build |
| FR-OCR-01/02 资产金标 | fixture manifest + generator | manifest schema、资产可生成、哈希稳定 | 基准清单 |
| FR-OCR-03 评估 | eval 脚本 | 指标计算与阈值退出码 | JSON/Markdown 报告 |
| FR-OCR-04 同页合并 | OCR layout 后处理 | 合并、段落隔离、列漂移异常 | 单元测试 |
| FR-OCR-05 跨页延续 | PDF OCR page merge | 表头去重、页标记、列不匹配不合并 | PDF OCR 测试 |
| FR-OCR-06 诊断 | layout diagnostics | 计数字段准确性 | 导入回执/测试断言 |
| FR-OPEN-01/02 创建与存储 | token service | 单次明文、无明文落盘、0600、原子写 | token store 测试 |
| FR-OPEN-03/04 鉴权授权 | FastAPI dependency | 缺失/错误/过期/撤销/KB 越权 | 路由测试 |
| FR-OPEN-05 只读层 | open router/service | OpenAPI 路径白名单、无写路由 | schema 审计测试 |
| FR-OPEN-06 审计 | JSONL audit | 无 token/问题泄漏、字段完整 | 日志测试 |
| FR-OPEN-07 撤销 | management route | 撤销即时拒绝 | 路由测试 |
| FR-OPEN-08 管理安全 | loopback + admin key | 非本机、缺密钥、错密钥拒绝 | 管理 API 测试 |
| FR-EMB-01 预检 | download adapter/service | 空间充足/不足/边界 | service/route 测试 |
| FR-EMB-02 进度 | callback/status | 单调进度、总字节和阶段 | 并发状态测试 |
| FR-EMB-03/04 取消清理 | Event + temp dir | 取消中、取消后不预热、临时清理 | service 测试 |
| FR-EMB-05 幂等重试 | service lock/state | 并发开始、取消后重试 | 并发回归测试 |
| FR-EMB-06 预热门禁 | runtime bridge | 仅 ready 调用 reset/warmup | mock 断言 |
| FR-EMB-07 UI | health API/domain/page | 进度/空间/取消/重试纯函数与 UI build | Web 测试/build |
| 全量回归 | Python/Web/Desktop | 非 slow、Web、Vite、Electron | 测试报告 |

# Task Plan: KB目录化存储开发方案完善

## Goal
实现多知识库目录化存储第一阶段：新导入原始文件按 `data/{kb_id}/` 保存，保留共享向量索引，通过 `metadata.kb_id` 做逻辑隔离；按仓库流程维护 PRD/FRD/RTM/Plan/Test Plan、测试记录和项目文档。

## Phase 1: 恢复上下文与核验现状
Status: complete
- [x] 读取评审建议、方案文档、项目进度与文档索引
- [x] 核验工作区状态和相关代码事实

## Phase 2: 落实开发方案评审意见
Status: complete
- [x] PRD 增加现状/目标能力对照
- [x] FRD 固定评测集路径并声明不得放入 data
- [x] RTM 注明编码前基线测试只证明现状链路

## Phase 3: 同步项目文档
Status: complete
- [x] 更新 `docs/guide/DOCS_INDEX.md`
- [x] 更新 `docs/project.md`
- [x] 同步多知识库设计文档，并只描述拟推进状态

## Phase 4: 补齐实施方案
Status: complete
- [x] 将用户评审意见覆盖写入 `评审建议.txt`
- [x] 新增 `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-plan.md`
- [x] 落实导入前 KB active 校验、file_paths 索引入口、旧节点 default 归属、删除 KB 回滚、registry 原子写、迁移 dry-run、QA fixture schema 范围
- [x] 第三轮评审无 P1，P2 已修订，进入编码

## Phase 5: 编码实现与预跑验证
Status: complete
- [x] 新增 `server/kb_errors.py` 稳定异常类型，避免 server -> api 反向依赖
- [x] 实现 `server/utils/file.py` 的 `kb_id` 校验、KB 目录解析和路径边界校验
- [x] 实现 `api/services/kb_service.py` 目录化导入、文档隔离、删除 KB 非空检查与一致性处理
- [x] 修改 `server/index.py`，让 `IndexManager.load_files()` 接收明确 `file_paths`
- [x] 修改 `server/kb_registry.py` 原子写、并发更新和计数下限
- [x] 新增迁移脚本和 QA fixture schema 校验
- [x] 预跑新增测试、回归测试和非 slow 全量快测

## Phase 6: 测试方案与正式测试报告
Status: in_progress
- [x] 新增 `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-plan.md`
- [ ] 等待测试方案评审通过
- [ ] 阶段 5 执行正式测试并生成 `20260714-kb-directory-storage-test-report.md`
- [ ] 审核通过后再进入 dev story、commit 和 push

## Boundaries
- 不迁移或删除用户真实 `data/` 根目录文件。
- 不改变 `storage/` 索引持久化结构。
- 测试方案和测试报告审核通过前不 commit、不 push。

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
| Windows 终端向 Python 管道传递中文内容时变成问号 | 1 | 改用 Node REPL 写入 UTF-8 文档与中文注释 |
| 全量 `python -m pytest tests -q` 会包含真实 PaddleOCR slow 测试，耗时不可控 | 1 | 默认门禁改用 `python -m pytest tests -q -m "not slow"`，真实 OCR 慢测单独记录 |

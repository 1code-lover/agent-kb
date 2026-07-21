# Progress

## 2026-07-14
- 初始化本任务的文件化计划。
- 已读取 `评审建议.txt`、PRD/FRD/RTM、`docs/project.md`、`DOCS_INDEX.md` 和关键代码入口。
- 已确认编码前 `data/` 仍平铺，目录化存储尚未实现。
- 已逐项落实开发方案评审意见，更新 PRD/FRD/RTM。
- 已同步 `DOCS_INDEX.md`、`docs/project.md` 和多知识库设计文档。
- 编码前现状多 KB 回归：`55 passed, 2 warnings in 4.54s`；该结果只作为共享索引逻辑多库链路基线。
- 收到第一轮实施方案评审：缺少 `20260714-kb-directory-storage-plan.md`，已补齐实施方案。
- 收到第二轮实施方案评审：P1 包括 kb_id 规则冲突、异常类型不稳定、旧 default 根文件删除策略不闭环、registry 事实描述不准确；已修订 Plan/RTM。
- 收到第三轮实施方案评审：无新的 P1，允许进入编码；3 个 P2 已修订后实施。
- 已完成目录化存储编码：新增 `server/kb_errors.py`，修改 `server/utils/file.py`、`api/services/kb_service.py`、`api/routers/kb.py`、`server/index.py`、`server/kb_registry.py`，新增迁移脚本和 QA fixture 校验脚本。
- 已新增/更新测试：`tests/utils/test_file_kb_paths.py`、`tests/api/test_kb_directory_storage.py`、`tests/api/test_kb_docs_isolation.py`、`tests/api/test_kb_registry_atomic.py`、`tests/scripts/test_migrate_kb_directory_storage.py`、`tests/test_rag_quality_fixtures.py`，并调整旧的 KB 路由/多 KB 语义测试。
- 编码阶段预跑结果已刷新：修复 `server/kb_registry.py` 缩进/中文注释恢复问题后，`python -m py_compile server/kb_registry.py` 通过；registry 定向测试 `18 passed in 0.80s`；核心新增测试 `71 passed in 5.28s`；KB/多 KB/Agent 定向回归 `45 passed, 2 warnings in 6.02s`；API + integration + scripts + utils + QA fixture 扩展回归 `145 passed, 2 warnings in 6.14s`；PDF OCR 非 slow `2 passed, 1 deselected in 1.79s`；非 slow 全量快测 `149 passed, 1 deselected, 2 warnings in 10.33s`。
- 已新增阶段 4 测试方案 `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-plan.md`，并同步 `docs/project.md`、`DOCS_INDEX.md`、多知识库设计文档；下一步等待测试方案评审，通过后再生成正式测试报告。
- 测试方案首轮评审暂不通过：P1 为缺少覆盖率门禁、遗漏文档/格式自检；已覆盖更新 `评审建议.txt`，并修订 `20260714-kb-directory-storage-test-plan.md`，补齐覆盖率目标 >= 80%、pytest-cov/coverage 依赖、覆盖率命令、`git diff --check`、占位词检查、URL/web import 用例、404/400 异常口径、预跑上下文和重复命令目的说明；同时修复实施计划中 `评审建议.txt` 路径被乱码写成问号导致占位词门禁误命中的问题。

- 2026-07-15 阶段 5 正式测试执行已完成：覆盖率首次 70% 未过，补充 tests/api/test_index_manager_coverage.py 后最终达到 84%；核心目录化 90 passed，扩展回归 164 passed，非 slow 全量 168 passed；已生成测试报告，下一步等待测试报告评审。

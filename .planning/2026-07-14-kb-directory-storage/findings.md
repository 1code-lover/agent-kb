# Findings

- 当前任务事实和待办来自仓库文件与本线程已执行的测试证据，所有结论仍需以当前工作区复核为准。
- `data/` 当前仍全部为根目录文件，没有 `data/{kb_id}/` 子目录。
- `kb_service.create_kb()` / `delete_kb()` 目前只操作 registry；`import_files()` 调用无参 `get_save_dir()`，原始文件仍写入共享根目录。
- `RuntimeState` 仍只维护一个 `IndexManager`；`KBIdFilter` 对无 `kb_id` 旧节点继续放行。
- 已有 20 条合成语义烟测及指标报告，但不是固定仓库正式 QA 评测集；正式 draft/verified 数据需要存放在 tests/fixtures/rag_quality/，不得放入 data/。
- 现有定向多 KB 回归 55 passed 只验证当前逻辑多库链路，不能作为目录化新需求通过证据。
- 方案文档目录和统一前缀符合 `docs/YYYYMMDD-topic/` 规范，PRD 的 FR-01 至 FR-07 均已在 RTM 追踪。
- 用户后续提供的“问题 + 参考答案”可以先结构化进入 draft；未绑定目标 KB、来源文件和证据片段时，不得计入 verified 指标。
- 当前 `tests/fixtures/rag_quality/` 尚未创建；需在开发方案审核通过后的实施阶段按 TDD 建立 schema、draft/verified fixture 和校验测试。
- 用户最新评审结论是实施方案暂不通过，原因是 `20260714-kb-directory-storage-plan.md` 缺失；本轮已补齐该文件并等待再次评审。
- 实施计划明确把 QA 评测集收敛为本阶段 fixture/schema 校验，完整嵌入质量和问答质量评分拆到测试方案与成熟评测集阶段。
- 实施计划明确 `IndexManager.load_files()` 必须接收服务层确认的 `file_paths`，不得继续二次调用全局 `get_save_dir()` 拼路径。

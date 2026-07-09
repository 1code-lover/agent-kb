# AGENTS.md - 项目开发规范

## 标准开发工作流

每个功能开发必须严格遵循以下流程，每一步都需要审核通过后才能进入下一步：

```text
1. 开发方案（PRD/需求文档）    -> 审核通过
2. 实施方案（详细开发计划）    -> 审核通过
3. 编写代码
4. 测试方案                   -> 审核通过
5. 执行测试 -> 生成测试报告    -> 审核通过
6. 提交代码 -> 远程推送
```

## 各阶段要求

### 评审规范

每次评审必须遵循以下流程：

1. **输出评审建议**：评审完成后，将评审建议写入 `评审建议.txt` 文件（仓库根目录）
2. **文件格式**：使用纯文本格式，包含优点、需要改进的地方、具体建议
3. **修改依据**：后续修改文档/代码时，必须读取 `评审建议.txt` 作为修改依据
4. **覆盖更新**：每次新评审会覆盖更新 `评审建议.txt`，保留最新评审意见

```text
评审流程：
1. 审核文档/代码
2. 生成评审建议 -> 写入 评审建议.txt
3. 读取 评审建议.txt -> 逐项落实修改
4. 完成修改 -> 通知审核方确认
```

### 阶段 1：开发方案
- 输出文档：PRD（需求文档）、FRD（功能设计）、RTM（需求追踪矩阵）
- 文档目录：`docs/YYYYMMDD-topic/`
- 审核要点：需求完整性、范围合理性、验收标准明确

### 阶段 2：实施方案
- 输出文档：详细开发计划（含代码、测试命令、预期结果）
- 文档目录：`docs/YYYYMMDD-topic/`
- 审核要点：任务粒度、文件路径准确、代码可执行、测试覆盖

### 阶段 3：编码
- 严格按实施方案执行
- 每个 Task 完成后提交一次
- 遵循 TDD：先写测试，再写实现

### 阶段 4：测试方案
- 输出：单元测试、集成测试用例
- 覆盖率目标：>= 80%
- 包含正常路径和异常路径

### 阶段 5：测试执行
- 运行全量测试套件
- 输出测试报告（通过率、覆盖率、失败项）
- 所有阻断问题必须修复

### 阶段 6：提交推送
- 测试报告审核通过后才能 commit
- commit message 遵循 conventional commits
- 推送到远程仓库

## 代码规范

- 中文注释：文件头和函数文档使用中文
- 测试优先：先写失败测试，再写最小实现
- 无占位符：不允许 `TBD`、`TODO`、`后续再补`

## 全局文档组织规范

本规范是仓库级全局默认规范，适用于后续所有新增需求。以后每个需求的所有文档必须放在同一个独立文件夹下，禁止同一需求的 PRD、设计、计划、测试方案、测试报告散落在 `docs/` 根目录或多个目录中。

### 目录命名

- 统一格式：`docs/YYYYMMDD-topic/`
- `YYYYMMDD`：需求立项或文档创建日期，例如 `20260706`
- `topic`：有语义的英文主题，使用小写字母、数字和中划线，长度 2-6 个单词，能让人一看就明白需求内容，例如 `multi-kb-frontend-refactor`、`desktop-file-upload`（而不是模糊的 `kb-v2`、`update`）

### 文件命名

- 同一需求下的所有文档必须使用统一前缀：`YYYYMMDD-topic-`
- 文件统一格式：`YYYYMMDD-topic-type.md`
- `type` 必须使用明确语义后缀，推荐值如下：
  - `prd`
  - `frd`
  - `rtm`
  - `spec`
  - `plan`
  - `test-plan`
  - `test-report`

### 标准结构

```text
docs/
  20260706-multi-kb-frontend-refactor/
    20260706-multi-kb-frontend-refactor-prd.md
    20260706-multi-kb-frontend-refactor-frd.md
    20260706-multi-kb-frontend-refactor-rtm.md
    20260706-multi-kb-frontend-refactor-spec.md
    20260706-multi-kb-frontend-refactor-plan.md
    20260706-multi-kb-frontend-refactor-test-plan.md
    20260706-multi-kb-frontend-refactor-test-report.md
```

### 执行要求

- 新需求开始时，先创建对应的 `docs/YYYYMMDD-topic/` 文件夹，再新增文档
- 同一需求后续补充文档时，必须继续放在原需求目录下，不得新开平级散落文件
- 如果当前需求只需要其中部分文档，也必须沿用同一目录和统一前缀命名
- 历史文档可以逐步迁移；新需求从本规范生效后必须严格遵守
- 审核 PRD、计划、测试方案、测试报告时，默认同时检查目录和命名是否符合本规范

## 开发故事沉淀

- 每次完成 bugfix、feature 或值得复盘的重构后，默认调用 `$dev-story-capture` 沉淀一份开发故事文档
- `git commit` 前，必须先检查当前 `working tree / index` 是否存在尚未沉淀的本次改动；若有，优先沉淀本次未提交改动，再检查 `last_generated_hash` 之后的历史遗漏提交
- `git push` 前，必须再次检查自 `last_generated_hash` 之后到当前 `HEAD` 是否仍有未沉淀窗口
- 成功生成后，状态文件必须同步推进到完整成功态；跳过时只能记录跳过态，不能推进已生成边界
- 用户显式指定输出路径时，优先使用该路径；否则按 `.interview-kit/dev-stories/`、`docs/interview/dev-stories/` 顺序回退
- 首次运行或状态文件异常时，按 `docs/ai-skills/dev-story-capture.md` 的 `bootstrap / repair` 规则处理
- 沉淀内容必须基于真实改动、真实验证和真实权衡，不允许编造
- 对不支持 Codex skill 机制、但会扫描仓库说明文件的 AI，统一参考 `docs/ai-skills/dev-story-capture.md`

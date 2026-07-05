# ThinkRAG 文档目录说明

## 目录结构

```
docs/
├── specs/          # 需求和规范
├── plans/          # 设计方案
├── implementation/ # 执行计划
├── architecture/   # 架构文档
├── standards/      # 开发规范
├── operations/     # 运维文档
├── getting-started/# 快速开始
└── images/        # 图片资源
```

## 各目录说明

### specs/ - 需求和规范
- 包含PRD（产品需求文档）
- 定义功能需求、用户场景、验收标准
- 示例：`kb_agent_prd.md`

### plans/ - 设计方案
- 包含FRD（功能设计）、技术设计方案、架构设计
- 定义模块职责、数据结构、接口设计
- 示例：`kb_agent_design.md`、`kb_agent_frd.md`

### implementation/ - 执行计划
- 包含任务分解、时间排期、开发计划
- 定义每个Task的验收标准和预计时间
- 示例：`kb_agent_plan.md`

### architecture/ - 架构文档
- 包含系统架构、模块关系图
- 定义技术选型、部署方案

### standards/ - 开发规范
- 包含代码规范、注释规范、提交规范
- 定义开发流程、代码审查标准

### operations/ - 运维文档
- 包含部署手册、运维手册、故障处理
- 定义监控方案、备份策略

### getting-started/ - 快速开始
- 包含环境搭建、快速入门指南
- 定义开发环境配置

## 文档命名规范

- 时间戳：所有文档文件名必须以时间戳开头，格式：`YYYY-MM-DD_文档名.md`
- 需求文档：`YYYY-MM-DD_{功能名}_prd.md`
- 设计文档：`YYYY-MM-DD_{功能名}_design.md`
- 功能设计：`YYYY-MM-DD_{功能名}_frd.md`
- 执行计划：`YYYY-MM-DD_{功能名}_plan.md`

## 文档更新流程（新功能开发）

1. **需求阶段**：编写PRD，放入 `specs/` 目录
2. **设计阶段**：编写FRD和技术设计，放入 `plans/` 目录
3. **计划阶段**：编写执行计划，放入 `implementation/` 目录
4. **开发阶段**：按计划执行，完成Task后更新状态
5. **测试阶段**：编写测试用例，更新测试报告
6. **发布阶段**：更新运维文档

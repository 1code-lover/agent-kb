# 文档组织规范

## 适用范围

本规范是仓库级全局文档规范，适用于后续所有新增需求文档。凡是属于同一个需求的 PRD、设计、计划、测试方案、测试报告，都必须遵守同目录、同前缀、同命名规则。

## 文档目录结构

每个需求必须使用独立的文件夹，按以下结构组织：

```
docs/
  YYYYMMDD-topic/                  # 需求文件夹，按时间戳-主题命名
    YYYYMMDD-topic-prd.md          # 需求文档
    YYYYMMDD-topic-frd.md          # 功能设计文档
    YYYYMMDD-topic-rtm.md          # 需求追踪矩阵
    YYYYMMDD-topic-spec.md         # 需求补充规格说明
    YYYYMMDD-topic-plan.md         # 实施计划
    YYYYMMDD-topic-test-plan.md    # 测试方案
    YYYYMMDD-topic-test-report.md  # 测试报告
```

### 命名规范

- 文件夹：`YYYYMMDD-topic/`
  - `YYYYMMDD`：文档创建日期（如 `20260706`）
  - `topic`：简短英文主题，小写字母 + 连字符（如 `kb-v2`、`pdf-parser`）
- 文件：`YYYYMMDD-topic-type.md`
  - `type` 取值：`prd`、`frd`、`rtm`、`spec`、`plan`、`test-plan`、`test-report`

### 示例

```
docs/
  20260706-kb-v2/
    20260706-kb-v2-prd.md
    20260706-kb-v2-frd.md
    20260706-kb-v2-rtm.md
    20260706-kb-v2-spec.md
    20260706-kb-v2-plan.md
    20260706-kb-v2-test-plan.md
    20260706-kb-v2-test-report.md
```

### 公共目录用途

以下目录仍保留，用于非特定需求的文档：

- `docs/guide/`：运行说明、环境配置
- `docs/dev/`：开发规范（本文件所在位置）
- `docs/images/`：文档配图
- `docs/archive/`：历史归档
- `docs/interview/`：面试材料

以上公共目录仅用于通用资料，不用于承载某个具体需求的成套交付文档。

## 文档类型说明

| 类型 | 说明 | 主要章节 |
|------|------|----------|
| PRD | 需求文档 | 项目背景、目标、场景、功能需求、非功能需求、验收口径 |
| FRD | 功能设计 | 模块划分、页面设计、交互规则、异常处理、DoD |
| RTM | 需求追踪矩阵 | 需求ID->实现入口->测试->验收映射 |
| Spec | 需求补充规格 | 状态约束、边界条件、接口补充、专项约束 |
| Plan | 实施计划 | 分阶段任务、文件路径、预期结果、测试命令 |
| Test Plan | 测试方案 | 测试范围、用例（正常路径+异常路径）、覆盖率目标 |
| Test Report | 测试报告 | 执行结果、通过率、覆盖率、失败项分析 |

## 工作流程

每个需求遵循以下阶段，每个阶段产出对应文档：

```
需求分析 → PRD
功能设计 → FRD + RTM
实施计划 → Plan
编码
测试方案 → Test Plan
测试执行 → Test Report
提交推送
```

每个阶段完成后需审核通过才能进入下一阶段。

## 生效规则

- 本规范对后续新增需求立即生效
- 历史文档暂不强制一次性迁移
- 历史需求如继续迭代，新增文档应优先整理到对应的 `docs/YYYYMMDD-topic/` 目录下

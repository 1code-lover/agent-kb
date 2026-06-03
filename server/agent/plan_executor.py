"""
模块功能：
- 实现 PlanExecutor 计划执行器
- 负责按拓扑排序执行计划步骤，处理依赖和失败

执行逻辑：
1. 对步骤进行拓扑排序，确保执行顺序合法
2. 按排序后的顺序执行步骤
3. 检查依赖是否满足（包括失败依赖）
4. 记录跳过和失败的步骤

关键依赖：
- server.agent.plan_models: 数据模型
- collections.defaultdict: 拓扑排序依赖图
"""

import logging
from collections import defaultdict
from typing import Any, Callable

from server.agent.plan_models import Plan, StepPlan, RiskLevel

logger = logging.getLogger(__name__)


class PlanExecutor:
    """
    功能：
    计划执行器，与 AgentService 解耦
    负责按拓扑排序执行计划步骤，处理依赖关系和失败情况

    使用方式：
    executor = PlanExecutor(tool_handlers={
        "kb_search": my_kb_search_handler,
        "read_file": my_read_file_handler,
    })
    result = executor.execute(plan, session_id)
    """

    def __init__(self, tool_handlers: dict[str, Callable]):
        """
        功能：
        初始化执行器

        输入：
        - tool_handlers(dict): 工具处理函数映射 {tool_name: handler}
            每个 handler 的签名应为: handler(session_id: str, **kwargs) -> dict

        执行逻辑：
        1. 保存工具处理函数映射
        2. 后续执行时通过 tool 名称查找对应的 handler
        """
        self.tool_handlers = tool_handlers

    def topological_sort(self, steps: list[StepPlan]) -> list[StepPlan]:
        """
        功能：
        对步骤进行拓扑排序，确保执行顺序合法
        使用 Kahn 算法实现

        输入：
        - steps(list[StepPlan]): 步骤列表

        输出：
        - list[StepPlan]: 排序后的步骤列表

        执行逻辑：
        1. 构建依赖图和入度表
        2. 使用 Kahn 算法进行拓扑排序
        3. 按原始顺序稳定排序（相同入度的步骤保持原始顺序）
        4. 检测循环依赖，发现时返回原始顺序并记录警告

        设计决策：
        - 使用 Kahn 算法而非 DFS，因为更容易实现稳定排序
        - 检测循环依赖时返回原始顺序而非抛出异常，保证可用性
        """
        # 构建依赖图
        graph = defaultdict(list)
        in_degree = {step.id: 0 for step in steps}
        step_map = {step.id: step for step in steps}

        for step in steps:
            for dep in step.depends_on:
                graph[dep].append(step.id)
                in_degree[step.id] += 1

        # 拓扑排序（Kahn 算法）
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        sorted_ids = []

        while queue:
            # 按原始顺序稳定排序
            queue.sort(key=lambda x: next(i for i, s in enumerate(steps) if s.id == x))
            current = queue.pop(0)
            sorted_ids.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查是否有循环依赖
        if len(sorted_ids) != len(steps):
            logger.warning("Circular dependency detected, returning original order")
            return steps

        return [step_map[sid] for sid in sorted_ids]

    def execute(self, plan: Plan, session_id: str) -> dict[str, Any]:
        """
        功能：
        执行计划，返回执行结果

        输入：
        - plan(Plan): 任务计划
        - session_id(str): 会话 ID

        输出：
        - dict: 执行结果，包含以下字段：
            - steps_results(dict): 步骤执行结果 {step_id: result}
            - skipped_steps(list): 跳过的步骤 [{step_id, reason}]
            - failed_steps(list): 失败的步骤 [{step_id, error}]

        执行逻辑：
        1. 对步骤进行拓扑排序
        2. 按排序后的顺序执行步骤
        3. 检查依赖是否满足（包括未满足依赖和失败依赖）
        4. 依赖未满足时记录跳过原因，继续执行其他步骤
        5. 步骤执行失败时记录失败原因，继续执行其他独立步骤

        设计决策：
        - 失败后 continue 而非 break，允许独立步骤继续执行
        - 同时检查未满足依赖和失败依赖，避免遗漏
        - 使用 failed_step_ids 集合跟踪失败步骤，支持依赖检查
        """
        # 拓扑排序
        sorted_steps = self.topological_sort(plan.steps)

        steps_results = {}
        skipped_steps = []
        failed_steps = []
        failed_step_ids = set()

        for step in sorted_steps:
            # 检查依赖是否满足
            unsatisfied_deps = [dep for dep in step.depends_on if dep not in steps_results]
            failed_deps = [dep for dep in step.depends_on if dep in failed_step_ids]

            if unsatisfied_deps or failed_deps:
                # 记录跳过原因
                reason_parts = []
                if unsatisfied_deps:
                    reason_parts.append(f"Unsatisfied dependencies: {unsatisfied_deps}")
                if failed_deps:
                    reason_parts.append(f"Failed dependencies: {failed_deps}")

                skipped_steps.append({
                    "step_id": step.id,
                    "reason": "; ".join(reason_parts),
                })
                logger.warning(f"Skipping step {step.id}: {'; '.join(reason_parts)}")
                continue

            # 执行步骤
            try:
                handler = self.tool_handlers.get(step.tool)
                if not handler:
                    raise ValueError(f"Unknown tool: {step.tool}")

                result = handler(session_id=session_id, **step.input)
                steps_results[step.id] = result
            except Exception as e:
                # 记录失败原因
                failed_steps.append({
                    "step_id": step.id,
                    "error": str(e),
                })
                failed_step_ids.add(step.id)
                logger.error(f"Step {step.id} failed: {e}")
                steps_results[step.id] = {"error": str(e)}
                continue  # 失败后继续执行其他独立步骤

        return {
            "steps_results": steps_results,
            "skipped_steps": skipped_steps,
            "failed_steps": failed_steps,
        }

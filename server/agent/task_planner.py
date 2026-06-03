"""
模块功能：
- 实现 TaskPlanner 任务规划器
- 将用户自然语言任务分解为可执行步骤

执行逻辑：
1. 接收用户任务描述
2. 构建 Prompt 调用 LLM
3. 解析 LLM 输出为 Plan 对象
4. 验证计划有效性
5. 失败时返回回退计划

关键依赖：
- llama_index.core: LLM 调用
- server.agent.plan_models: 数据模型
- server.agent.prompts: Prompt 模板
"""

import json
import logging
import re
from typing import Optional

from llama_index.core import Settings

from server.agent.plan_models import Plan, StepPlan, StepType, RiskLevel, VALID_TOOLS
from server.agent.prompts import TASK_PLANNER_SYSTEM_PROMPT, TASK_PLANNER_USER_PROMPT

logger = logging.getLogger(__name__)


class TaskPlanner:
    """
    功能：
    任务规划器，将自然语言任务分解为可执行步骤
    通过依赖注入管理 LLM 实例，避免全局单例的线程安全问题

    使用方式：
    planner = TaskPlanner(llm=my_llm, timeout=30)
    plan = planner.plan("给 main.py 添加日志功能")
    """

    def __init__(self, llm=None, timeout: int = 30):
        """
        功能：
        初始化任务规划器

        输入：
        - llm: LLM 实例，默认使用 Settings.llm
        - timeout(int): LLM 调用超时时间（秒），默认 30 秒

        执行逻辑：
        1. 设置 LLM 实例（支持依赖注入）
        2. 设置超时时间
        """
        self.llm = llm or Settings.llm
        self.timeout = timeout

    def plan(self, task: str) -> Plan:
        """
        功能：
        将任务分解为可执行步骤

        输入：
        - task(str): 用户的自然语言任务描述

        输出：
        - Plan: 完整的任务计划

        执行逻辑：
        1. 构建 Prompt（系统提示词 + 用户提示词）
        2. 调用 LLM（带超时控制）
        3. 解析 LLM 输出为 Plan 对象
        4. 验证计划有效性
        5. 失败时返回回退计划

        异常：
        - LLM 调用失败时返回回退计划，不抛出异常
        """
        # 1. 构建 Prompt
        user_prompt = TASK_PLANNER_USER_PROMPT.format(task=task)
        full_prompt = f"{TASK_PLANNER_SYSTEM_PROMPT}\n\n{user_prompt}"

        # 2. 调用 LLM（带超时控制）
        try:
            response = self.llm.complete(full_prompt, timeout=self.timeout)
            response_text = response.text
        except TimeoutError:
            logger.error(f"LLM call timeout after {self.timeout}s for task: {task}")
            return self._create_fallback_plan(task)
        except Exception as e:
            logger.error(f"LLM call failed: {e}, task: {task}")
            return self._create_fallback_plan(task)

        # 3. 解析输出
        try:
            plan = self._parse_response(task, response_text)
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}, response: {response_text[:500]}")
            return self._create_fallback_plan(task)

        # 4. 验证计划
        plan = self._validate_plan(plan)

        return plan

    def _extract_json(self, text: str) -> str:
        """
        功能：
        从 LLM 输出中提取 JSON 字符串
        优先识别 Markdown 代码块中的 JSON，回退到字符串截取

        输入：
        - text(str): LLM 输出文本

        输出：
        - str: 提取的 JSON 字符串

        异常：
        - ValueError: 无法提取有效 JSON

        执行逻辑：
        1. 尝试提取 Markdown 代码块中的 JSON（re.DOTALL 确保多行匹配）
        2. 回退到字符串截取（find("{") 到 rfind("}")）
        3. 验证 JSON 完整性（json.loads 必须成功）
        """
        # 1. 尝试提取 Markdown 代码块中的 JSON
        # re.DOTALL 使 . 匹配换行符，确保多行 JSON 能正确提取
        code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if code_block_match:
            json_str = code_block_match.group(1).strip()
            # 验证是否为有效 JSON
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                pass  # 代码块中的内容不是有效 JSON，继续尝试其他方法

        # 2. 回退到字符串截取
        json_start = text.find("{")
        json_end = text.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in response")

        json_str = text[json_start:json_end]

        # 3. 验证 JSON 完整性
        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON extracted: {e}")

        return json_str

    def _parse_response(self, task: str, response_text: str) -> Plan:
        """
        功能：
        解析 LLM 输出为 Plan 对象

        输入：
        - task(str): 原始任务描述
        - response_text(str): LLM 输出文本

        输出：
        - Plan: 解析后的计划对象

        异常：
        - ValueError: JSON 提取或解析失败
        - ValidationError: Pydantic 验证失败

        执行逻辑：
        1. 提取 JSON 字符串
        2. 解析 JSON 为字典
        3. 使用 Pydantic 验证并构建 Plan 对象
        """
        # 提取 JSON
        json_str = self._extract_json(response_text)

        # 解析 JSON
        data = json.loads(json_str)

        # 使用 Pydantic 验证
        plan = Plan.model_validate({
            "task": task,
            "steps": data.get("steps", []),
            "estimated_seconds": data.get("estimated_seconds", 0),
            "notes": data.get("notes", ""),
        })

        return plan

    def _validate_plan(self, plan: Plan) -> Plan:
        """
        功能：
        验证计划的有效性，修复发现的问题

        输入：
        - plan(Plan): 原始计划

        输出：
        - Plan: 验证后的计划（可能修正了某些问题）

        执行逻辑：
        1. 检查步骤 ID 唯一性，重复时生成新 ID
        2. 检查依赖关系的有效性，移除无效依赖
        3. 修复 tool 为空或无效的情况
        4. 确保至少有一个步骤
        """
        # 检查步骤 ID 唯一性
        step_ids = set()
        for i, step in enumerate(plan.steps):
            if step.id in step_ids:
                # 生成新的 ID
                new_id = f"{step.id}-{i}"
                step = step.model_copy(update={"id": new_id})
                plan.steps[i] = step
            step_ids.add(step.id)

        # 检查依赖关系的有效性
        for i, step in enumerate(plan.steps):
            valid_deps = [dep for dep in step.depends_on if dep in step_ids]
            if len(valid_deps) != len(step.depends_on):
                step = step.model_copy(update={"depends_on": valid_deps})
                plan.steps[i] = step

        # 修复 tool 为空或无效的情况
        for i, step in enumerate(plan.steps):
            if not step.tool or step.tool not in VALID_TOOLS:
                # 根据 type 推断 tool
                inferred_tool = self._infer_tool_from_type(step.type)
                step = step.model_copy(update={"tool": inferred_tool})
                plan.steps[i] = step
                logger.warning(f"Fixed empty/invalid tool for step {step.id}, inferred: {inferred_tool}")

        # 确保至少有一个步骤
        if not plan.steps:
            plan.steps = [
                StepPlan(
                    id="step-1",
                    type=StepType.KB_SEARCH,
                    title="检索知识库",
                    description="检索知识库获取相关信息",
                    tool="kb_search",
                    input={"query": plan.task},
                    depends_on=[],
                    risk_level=RiskLevel.LOW,
                    expected_output="相关文档列表",
                )
            ]

        return plan

    def _infer_tool_from_type(self, step_type: StepType) -> str:
        """
        功能：
        根据步骤类型推断工具名称

        输入：
        - step_type(StepType): 步骤类型

        输出：
        - str: 推断的工具名称
        """
        type_to_tool = {
            StepType.READ_FILE: "read_file",
            StepType.WRITE_FILE: "read_file",
            StepType.RUN_CMD: "run_cmd",
            StepType.KB_SEARCH: "kb_search",
            StepType.ANALYZE: "analyze",
            StepType.SUMMARIZE: "summarize",
        }
        return type_to_tool.get(step_type, "kb_search")

    def _create_fallback_plan(self, task: str) -> Plan:
        """
        功能：
        创建回退计划（当 LLM 调用失败时使用）

        输入：
        - task(str): 任务描述

        输出：
        - Plan: 简单的回退计划

        设计决策：
        - 回退计划使用 kb_search + summarize 两步
        - 确保即使 LLM 失败也能给出基本响应
        """
        return Plan(
            task=task,
            steps=[
                StepPlan(
                    id="step-1",
                    type=StepType.KB_SEARCH,
                    title="检索知识库",
                    description="检索知识库获取相关信息",
                    tool="kb_search",
                    input={"query": task},
                    depends_on=[],
                    risk_level=RiskLevel.LOW,
                    expected_output="相关文档列表",
                ),
                StepPlan(
                    id="step-2",
                    type=StepType.SUMMARIZE,
                    title="汇总结果",
                    description="基于检索结果生成回答",
                    tool="summarize",
                    input={},
                    depends_on=["step-1"],
                    risk_level=RiskLevel.LOW,
                    expected_output="最终回答",
                ),
            ],
            estimated_seconds=60,
            notes="回退计划（LLM 调用失败）",
        )

    def replan(
        self,
        task: str,
        original_plan: Plan,
        step_results: dict[str, dict],
        failed_step_ids: set[str] = None,
    ) -> Plan:
        """
        功能：
        根据执行结果重新规划剩余步骤

        输入：
        - task(str): 原始任务描述
        - original_plan(Plan): 原始计划
        - step_results(dict): 已执行步骤的结果 {step_id: result_dict}
        - failed_step_ids(set): 失败的步骤 ID 集合

        输出：
        - Plan: 新的计划

        执行逻辑：
        1. 限制步骤结果的文本长度（单条不超过 500 字符）
        2. 构建简化的计划摘要（包含完成/失败步骤信息）
        3. 调用 LLM 重新规划
        4. 失败时返回原始计划

        设计决策：
        - 截断所有类型的值（使用 str(value) 转换），不仅限于字符串
        - 传入 completed_step_ids 和 failed_step_ids，避免重复已完成步骤
        - 不传入完整计划，减少 Token 消耗
        """
        failed_step_ids = failed_step_ids or set()
        completed_step_ids = set(step_results.keys()) - failed_step_ids

        # 限制步骤结果的文本长度（覆盖所有类型）
        truncated_results = {}
        for step_id, result in step_results.items():
            truncated = {}
            for key, value in result.items():
                value_str = str(value)
                if len(value_str) > 500:
                    truncated[key] = value_str[:500] + f"... (truncated, original length: {len(value_str)})"
                else:
                    truncated[key] = value
            truncated_results[step_id] = truncated

        # 构建简化的计划摘要（包含完成/失败步骤信息）
        plan_summary = {
            "task": original_plan.task,
            "total_steps": len(original_plan.steps),
            "completed_step_ids": list(completed_step_ids),
            "failed_step_ids": list(failed_step_ids),
        }

        # 构建重新规划的 Prompt
        replan_prompt = f"""
原始任务：{task}

计划摘要：{json.dumps(plan_summary, ensure_ascii=False)}

已执行步骤的结果：
{json.dumps(truncated_results, indent=2, ensure_ascii=False)}

请根据已执行的结果，重新规划剩余步骤。不要重复已完成的步骤。直接输出 JSON，不要使用代码块标记。
"""

        # 调用 LLM 重新规划
        try:
            response = self.llm.complete(TASK_PLANNER_SYSTEM_PROMPT + "\n\n" + replan_prompt, timeout=self.timeout)
            new_plan = self._parse_response(task, response.text)
            return self._validate_plan(new_plan)
        except Exception as e:
            logger.error(f"Replan failed: {e}")
            return original_plan

/**
 * 文件功能：
 * - 提供 Agent 工作台状态的纯函数工具，便于复用和测试。
 *
 * 执行逻辑：
 * 1. 生成工作台默认状态结构。
 * 2. 统一追加时间线事件并分配顺序号。
 * 3. 将后端 runAgent 结果映射为前端时间线事件。
 */

/**
 * 创建 Agent 工作台默认状态。
 *
 * 输出：
 * - object: 初始工作台状态对象。
 */
export function createWorkspaceState() {
  return {
    taskGoal: "",
    runState: "idle",
    timeline: [],
    plan: [],
    evidence: [],
    taskState: null,
    pendingActions: [],
    approvalMessage: ""
  };
}

/**
 * 向时间线追加单条事件并写入顺序号。
 *
 * 输入：
 * - timeline(array): 当前时间线数组。
 * - event(object): 待追加事件。
 *
 * 输出：
 * - array: 追加后的新时间线数组。
 */
export function appendTimelineEvent(timeline, event) {
  const nextSeq = timeline.length + 1;
  return [...timeline, { ...event, seq: nextSeq }];
}

/**
 * 将 Agent 运行结果映射为工作台时间线事件。
 *
 * 输入：
 * - question(string): 用户输入问题。
 * - runData(object): runAgent 返回数据。
 *
 * 执行逻辑：
 * 1. 先追加用户输入事件。
 * 2. 追加助手回答事件。
 * 3. 将 steps 数组映射为 step 事件列表。
 *
 * 输出：
 * - array: 可直接渲染的时间线事件数组。
 */
export function mapAgentRunToTimeline(question, runData) {
  const events = [
    { type: "user", content: question },
    { type: "assistant", content: runData?.answer || "" }
  ];

  const steps = runData?.steps || [];
  for (const step of steps) {
    events.push({
      type: "step",
      content: step?.summary || step?.title || step?.step || "unknown-step",
      meta: {
        name: step?.step,
        title: step?.title,
        status: step?.status,
        riskLevel: step?.risk_level,
        receiptId: step?.receipt_id,
        evidenceIds: step?.evidence_ids || []
      }
    });
  }
  return events;
}

/**
 * 文件功能：
 * - 封装智能体执行相关 API 调用。
 *
 * 执行逻辑：
 * 1. 提供任务执行接口（run）。
 * 2. 提供执行回执、待审批动作查询接口。
 * 3. 提供审批提交接口。
 */

import client from "./client";

/**
 * 功能：发起一次智能体执行请求。
 * 输入：payload(object) - 包含会话、问题与运行配置等参数。
 * 输出：Promise<object> - 后端返回的运行结果。
 */
export async function runAgent(payload) {
  return client.post("/api/agent/run", payload);
}

/**
 * 功能：查询指定会话的智能体执行回执。
 * 输入：
 * - sessionId(string): 会话 ID。
 * - limit(number): 回执条数上限。
 * 输出：Promise<object> - 回执列表与分页信息。
 */
export async function getAgentReceipts(sessionId = "default", limit = 50) {
  return client.get("/api/agent/receipts", {
    params: {
      session_id: sessionId,
      limit
    }
  });
}

/**
 * 功能：查询当前会话待审批动作。
 * 输入：sessionId(string) - 会话 ID。
 * 输出：Promise<object> - 待审批动作列表。
 */
export async function getPendingActions(sessionId = "default") {
  return client.get("/api/agent/pending", {
    params: {
      session_id: sessionId
    }
  });
}

/**
 * 功能：提交智能体动作审批结果。
 * 输入：payload(object) - 审批动作 ID、审批结论等数据。
 * 输出：Promise<object> - 审批处理结果。
 */
export async function approveAgentAction(payload) {
  return client.post("/api/agent/approvals", payload);
}

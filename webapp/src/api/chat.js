/**
 * 文件功能：
 * - 封装聊天问答相关 API 调用。
 *
 * 执行逻辑：
 * 1. 提供单次问答查询接口。
 * 2. 提供会话历史查询接口。
 */

import client from "./client";

/**
 * 功能：提交问答请求并获取响应。
 * 输入：payload(object) - 会话参数和用户问题。
 * 输出：Promise<object> - 问答结果。
 */
export async function queryChat(payload) {
  return client.post("/api/chat/query", payload);
}

/**
 * 功能：获取指定会话历史记录。
 * 输入：sessionId(string) - 会话 ID。
 * 输出：Promise<object> - 历史消息数据。
 */
export async function getHistory(sessionId = "default") {
  return client.get("/api/chat/history", { params: { session_id: sessionId } });
}

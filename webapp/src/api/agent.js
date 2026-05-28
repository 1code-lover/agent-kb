import client from "./client";

function unwrapEnvelope(response) {
  if (response?.code !== 0) {
    throw new Error(response?.message || "Request failed");
  }
  return response?.data ?? {};
}

export async function runAgent(payload) {
  const response = await client.post("/api/agent/run", payload);
  return unwrapEnvelope(response);
}

export async function getAgentReceipts(sessionId = "desktop-default", limit = 50) {
  const response = await client.get("/api/agent/receipts", {
    params: {
      session_id: sessionId,
      limit
    }
  });
  return unwrapEnvelope(response);
}

export async function getPendingActions(sessionId = "desktop-default") {
  const response = await client.get("/api/agent/pending", {
    params: {
      session_id: sessionId
    }
  });
  return unwrapEnvelope(response);
}

export async function approveAgentAction(payload) {
  const response = await client.post("/api/agent/approvals", payload);
  return unwrapEnvelope(response);
}

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

export async function getAgentSession(sessionId = "desktop-default") {
  const response = await client.get("/api/agent/session", {
    params: {
      session_id: sessionId
    }
  });
  return unwrapEnvelope(response);
}

export async function updateAgentSession(payload) {
  const response = await client.put("/api/agent/session", payload);
  return unwrapEnvelope(response);
}

export async function resetAgentSession(sessionId = "desktop-default") {
  const response = await client.post("/api/agent/session/reset", {
    session_id: sessionId
  });
  return unwrapEnvelope(response);
}

export async function getAgentSkills() {
  const response = await client.get("/api/agent/skills");
  return unwrapEnvelope(response);
}

export async function uploadFilesToKnowledge(formData) {
  const response = await client.post("/api/kb/file/import", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return unwrapEnvelope(response);
}


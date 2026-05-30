import client from "./client";

function unwrapEnvelope(response) {
  if (response?.code !== 0) {
    throw new Error(response?.message || "Request failed");
  }
  return response?.data ?? {};
}

export async function getModelOptions() {
  const response = await client.get("/api/model/options");
  return unwrapEnvelope(response);
}

export async function selectModel(payload) {
  const response = await client.post("/api/model/select", payload);
  return unwrapEnvelope(response);
}

export async function addCustomProvider(payload) {
  const response = await client.post("/api/model/providers", payload);
  return unwrapEnvelope(response);
}

export async function testCustomProvider(payload) {
  const response = await client.post("/api/model/providers/test", payload);
  return unwrapEnvelope(response);
}

export async function deleteCustomProvider(name) {
  const response = await client.delete(`/api/model/providers/${encodeURIComponent(name)}`);
  return unwrapEnvelope(response);
}

export async function exportProviderConfig() {
  const response = await client.get("/api/model/providers/export");
  return unwrapEnvelope(response);
}

export async function importProviderConfig(payload) {
  const response = await client.post("/api/model/providers/import", payload);
  return unwrapEnvelope(response);
}

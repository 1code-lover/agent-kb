/**
 * 文件功能：
 * - 封装证据预览相关 API 调用。
 */

import client from "./client.js";
import { requireKbTarget } from "../domain/kbSelection.js";

/** 按 evidence_id 请求后端预览对象。 */
export async function previewEvidence(payload) {
  const targetKbId = requireKbTarget(payload?.kb_id);
  const requestBody = {
    kb_id: targetKbId,
    evidence_id: payload?.evidence_id,
  };
  if (payload?.preview_locator) {
    requestBody.preview_locator = payload.preview_locator;
  }
  return client.post("/api/kb/preview", requestBody);
}

/** 按 doc_id 请求后端预览对象。 */
export async function previewDoc(kbId, docId, previewLocator = null) {
  const requestBody = {
    kb_id: requireKbTarget(kbId),
    doc_id: docId,
  };
  if (previewLocator) {
    requestBody.preview_locator = previewLocator;
  }
  return client.post("/api/kb/preview", requestBody);
}

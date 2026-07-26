/**
 * 文件功能：
 * - 封装证据预览与资产预览相关 API 调用。
 * - 统一“资产 > 文档 > evidence_id”的预览优先级。
 */

import client from "./client.js";
import { requireKbTarget } from "../domain/kbSelection.js";

function appendPreviewLocator(requestBody, previewLocator) {
  if (previewLocator) {
    requestBody.preview_locator = previewLocator;
  }
  return requestBody;
}

/**
 * 根据证据项构造预览请求。
 * 优先级：asset_id > doc_id > evidence_id。
 */
export function buildPreviewRequest(item, fallbackKbId = null) {
  const targetKbId = requireKbTarget(item?.kb_id || fallbackKbId);

  if (item?.asset_id) {
    return {
      kind: "asset",
      kb_id: targetKbId,
      asset_id: item.asset_id,
    };
  }

  if (item?.doc_id) {
    return appendPreviewLocator(
      {
        kind: "doc",
        kb_id: targetKbId,
        doc_id: item.doc_id,
      },
      item?.preview_locator || null,
    );
  }

  return appendPreviewLocator(
    {
      kind: "evidence",
      kb_id: targetKbId,
      evidence_id: item?.id,
    },
    item?.preview_locator || null,
  );
}

/** 按 evidence_id 请求后端预览对象。 */
export async function previewEvidence(payload) {
  const targetKbId = requireKbTarget(payload?.kb_id);
  return client.post(
    "/api/kb/preview",
    appendPreviewLocator(
      {
        kb_id: targetKbId,
        evidence_id: payload?.evidence_id,
      },
      payload?.preview_locator || null,
    ),
  );
}

/** 按 doc_id 请求后端预览对象。 */
export async function previewDoc(kbId, docId, previewLocator = null) {
  return client.post(
    "/api/kb/preview",
    appendPreviewLocator(
      {
        kb_id: requireKbTarget(kbId),
        doc_id: docId,
      },
      previewLocator,
    ),
  );
}

/** 按 asset_id 请求后端资产预览对象。 */
export async function previewAsset(kbId, assetId) {
  return client.get(`/api/kb/assets/${encodeURIComponent(assetId)}`, {
    params: {
      kb_id: requireKbTarget(kbId),
    },
  });
}

/** 按统一优先级执行预览请求。 */
export async function previewItem(item, fallbackKbId = null) {
  const request = buildPreviewRequest(item, fallbackKbId);
  if (request.kind === "asset") {
    return previewAsset(request.kb_id, request.asset_id);
  }
  if (request.kind === "doc") {
    return previewDoc(request.kb_id, request.doc_id, request.preview_locator || null);
  }
  return previewEvidence(request);
}

/**
 * 文件功能：
 * - 定义前端知识库目标选择的纯规则，供状态管理、导入 API 与回归测试复用。
 */

export const EMPTY_KB_SELECTION = "";
export const DEFAULT_KNOWLEDGE_SCOPE = Object.freeze({
  kb_id: "default",
  kb_name: "默认知识库",
});

function buildKnowledgeScope(kbId, kbName) {
  return {
    kb_id: kbId,
    kb_name: kbName || kbId,
  };
}

export function resolveKnowledgeScope({ selectedKb, selectedKbId, fallbackScope } = {}) {
  if (selectedKb?.kb_id) {
    return buildKnowledgeScope(selectedKb.kb_id, selectedKb.kb_name);
  }

  const normalizedSelectedKbId = typeof selectedKbId === "string" ? selectedKbId.trim() : "";
  if (normalizedSelectedKbId) {
    const fallbackName = fallbackScope?.kb_id === normalizedSelectedKbId ? fallbackScope?.kb_name : "";
    return buildKnowledgeScope(normalizedSelectedKbId, fallbackName);
  }

  return { ...DEFAULT_KNOWLEDGE_SCOPE };
}

export function isActiveKb(kb) {
  return Boolean(kb?.kb_id) && kb.status === "active";
}

export function canUseKbTarget(kbList, kbId) {
  if (!kbId) return false;
  return kbList.some((kb) => kb.kb_id === kbId && isActiveKb(kb));
}

export function reconcileKbSelection(kbList, selectedKbId) {
  return canUseKbTarget(kbList, selectedKbId) ? selectedKbId : EMPTY_KB_SELECTION;
}

export function selectionAfterCreate(createdKb) {
  return isActiveKb(createdKb) ? createdKb.kb_id : EMPTY_KB_SELECTION;
}

export function selectionAfterDelete(selectedKbId, deletedKbId) {
  return selectedKbId === deletedKbId ? EMPTY_KB_SELECTION : selectedKbId;
}

export function requireKbTarget(kbId) {
  if (typeof kbId !== "string" || !kbId.trim()) {
    throw new Error("必须先选择目标知识库");
  }
  return kbId.trim();
}

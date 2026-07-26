/**
 * 文件功能：
 * - 定义 Knowledge Workspace 与 Agent 页面之间的导航意图，确保跨页时仍显式携带知识库范围。
 */

import { EMPTY_KB_SELECTION } from './kbSelection.js';

function normalizeKbId(kbId) {
  return typeof kbId === 'string' ? kbId.trim() : '';
}

export function buildKnowledgeAgentLink(kbId) {
  const params = new URLSearchParams();
  params.set('experience', 'knowledge');

  const normalizedKbId = normalizeKbId(kbId);
  if (normalizedKbId) {
    params.set('kb_id', normalizedKbId);
  }

  return '/agent?' + params.toString();
}

export function buildKnowledgeWorkspaceLink(kbId) {
  const normalizedKbId = normalizeKbId(kbId);
  if (!normalizedKbId) {
    return '/knowledge';
  }

  const params = new URLSearchParams();
  params.set('kb_id', normalizedKbId);
  return '/knowledge?' + params.toString();
}

export function parseKnowledgeAgentEntry(search) {
  const params = new URLSearchParams(typeof search === 'string' ? search : '');
  const requestedKbId = normalizeKbId(params.get('kb_id'));
  const requestedExperience =
    params.get('experience') === 'knowledge' || requestedKbId
      ? 'knowledge'
      : '';

  return {
    requestedKbId: requestedKbId || EMPTY_KB_SELECTION,
    requestedExperience,
  };
}

export function parseKnowledgeWorkspaceEntry(search) {
  const params = new URLSearchParams(typeof search === 'string' ? search : '');
  const requestedKbId = normalizeKbId(params.get('kb_id'));

  return {
    requestedKbId: requestedKbId || EMPTY_KB_SELECTION,
  };
}

/**
 * 文件功能：
 * - 定义 Knowledge Workspace 与 Agent 页面之间的导航意图，确保跨页时仍显式携带知识库范围。
 */

import { EMPTY_KB_SELECTION } from './kbSelection.js';

function normalizeKbId(kbId) {
  return typeof kbId === 'string' ? kbId.trim() : '';
}

function normalizeAgentExperience(experience) {
  if (experience === 'basic' || experience === 'knowledge') {
    return experience;
  }
  return '';
}

export function buildAgentWorkbenchLink({ experience, kbId } = {}) {
  const normalizedExperience = normalizeAgentExperience(experience);
  const normalizedKbId = normalizeKbId(kbId);
  const params = new URLSearchParams();

  if (normalizedExperience === 'knowledge') {
    params.set('experience', 'knowledge');
  } else if (normalizedExperience === 'basic' && normalizedKbId) {
    params.set('experience', 'basic');
  }

  if (normalizedKbId) {
    params.set('kb_id', normalizedKbId);
  }

  const query = params.toString();
  return query ? '/agent?' + query : '/agent';
}

export function buildKnowledgeAgentLink(kbId) {
  return buildAgentWorkbenchLink({ experience: 'knowledge', kbId });
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

export function parseAgentWorkbenchEntry(search) {
  const params = new URLSearchParams(typeof search === 'string' ? search : '');
  const requestedKbId = normalizeKbId(params.get('kb_id'));
  const requestedExperience = normalizeAgentExperience(params.get('experience')) || (requestedKbId ? 'knowledge' : '');

  return {
    requestedKbId: requestedKbId || EMPTY_KB_SELECTION,
    requestedExperience,
  };
}

export function parseKnowledgeAgentEntry(search) {
  return parseAgentWorkbenchEntry(search);
}

export function parseKnowledgeWorkspaceEntry(search) {
  const params = new URLSearchParams(typeof search === 'string' ? search : '');
  const requestedKbId = normalizeKbId(params.get('kb_id'));

  return {
    requestedKbId: requestedKbId || EMPTY_KB_SELECTION,
  };
}

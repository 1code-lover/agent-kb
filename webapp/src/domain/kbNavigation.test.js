/**
 * 文件功能：
 * - 验证 Knowledge Workspace 与 Agent 页之间的导航意图，避免丢失显式知识库范围。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildKnowledgeAgentLink,
  buildKnowledgeWorkspaceLink,
  parseKnowledgeAgentEntry,
  parseKnowledgeWorkspaceEntry,
} from './kbNavigation.js';

test('buildKnowledgeAgentLink 会携带 knowledge 体验与当前 kb_id', () => {
  assert.equal(
    buildKnowledgeAgentLink('grain-knowledge-base'),
    '/agent?experience=knowledge&kb_id=grain-knowledge-base',
  );
});

test('buildKnowledgeAgentLink 在未传 kb_id 时仍固定到 knowledge 体验', () => {
  assert.equal(buildKnowledgeAgentLink(''), '/agent?experience=knowledge');
});

test('buildKnowledgeWorkspaceLink 会在管理页路由上保留当前 kb_id', () => {
  assert.equal(
    buildKnowledgeWorkspaceLink('grain-knowledge-base'),
    '/knowledge?kb_id=grain-knowledge-base',
  );
});

test('buildKnowledgeWorkspaceLink 在未传 kb_id 时回退到基础知识库页', () => {
  assert.equal(buildKnowledgeWorkspaceLink(''), '/knowledge');
});

test('parseKnowledgeAgentEntry 会从 query string 中提取显式范围', () => {
  assert.deepEqual(
    parseKnowledgeAgentEntry('?experience=knowledge&kb_id=grain-knowledge-base'),
    {
      requestedKbId: 'grain-knowledge-base',
      requestedExperience: 'knowledge',
    },
  );
});

test('parseKnowledgeAgentEntry 在仅传 kb_id 时也应落到 knowledge 体验', () => {
  assert.deepEqual(
    parseKnowledgeAgentEntry('?kb_id=grain-knowledge-base'),
    {
      requestedKbId: 'grain-knowledge-base',
      requestedExperience: 'knowledge',
    },
  );
});

test('parseKnowledgeAgentEntry 会对空查询安全回退', () => {
  assert.deepEqual(parseKnowledgeAgentEntry(''), {
    requestedKbId: '',
    requestedExperience: '',
  });
});

test('parseKnowledgeWorkspaceEntry 会提取知识库管理页的预选范围', () => {
  assert.deepEqual(parseKnowledgeWorkspaceEntry('?kb_id=grain-knowledge-base'), {
    requestedKbId: 'grain-knowledge-base',
  });
});

test('parseKnowledgeWorkspaceEntry 对空查询回退为空选择', () => {
  assert.deepEqual(parseKnowledgeWorkspaceEntry(''), {
    requestedKbId: '',
  });
});

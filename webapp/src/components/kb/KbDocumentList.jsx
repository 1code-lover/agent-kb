/**
 * 知识库文档列表
 * - 按知识库加载文档对象，支持搜索、分页与批量删除。
 * - 文档列表会先应用目录范围过滤，再做搜索、分组和分页。
 */

import { Fragment, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';

import { deleteDocs, listDocs } from '../../api/kb';
import { readApiData } from '../../api/response';
import { ALL_FOLDER_SCOPE, matchesFolderScope } from '../../domain/folderNavigation.js';
import { buildFolderGroups, getFolderPathFromObjectPath } from '../../domain/folderTree';
import { useKb } from './KbContext';

const PAGE_SIZE = 20;

function resolveDocumentDisplayPath(doc) {
  return doc?.relative_path || doc?.path || '';
}

function resolveDocumentFolderPath(doc) {
  return doc?.folder_path || getFolderPathFromObjectPath(resolveDocumentDisplayPath(doc));
}

function toDocumentSelection(doc, fallbackKbId) {
  return {
    key: 'document:' + (doc.id || doc.path || 'unknown'),
    type: 'document',
    id: doc.id,
    name: doc.name,
    path: resolveDocumentDisplayPath(doc),
    relativePath: doc.relative_path || '',
    folderPath: resolveDocumentFolderPath(doc),
    sourcePath: doc.path || '',
    docType: doc.type,
    kbId: doc.kb_id || fallbackKbId,
    raw: doc,
  };
}

function buildDocumentSearchText(doc) {
  return [doc?.name, doc?.relative_path, doc?.path, doc?.folder_path, doc?.type]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

export default function KbDocumentList({
  onSelectDocument,
  onDocumentsChanged,
  selectedDocumentId = '',
  refreshVersion = 0,
  selectedFolderPath = ALL_FOLDER_SCOPE,
  selectedFolderLabel = '全部目录',
}) {
  const { selectedKbId, selectedKb, hasSelectedKb } = useKb();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState(new Set());

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['docs', selectedKbId, refreshVersion],
    queryFn: () => listDocs(selectedKbId),
    enabled: hasSelectedKb,
  });

  const deleteMutation = useMutation({
    mutationFn: (payload) => deleteDocs(payload),
    onSuccess: () => {
      setSelected(new Set());
      refetch();
      onDocumentsChanged?.();
    },
  });

  useEffect(() => {
    setSearch('');
    setPage(0);
    setSelected(new Set());
  }, [selectedKbId]);

  useEffect(() => {
    setPage(0);
    setSelected(new Set());
  }, [selectedFolderPath]);

  const docs = readApiData(data)?.docs || [];
  const scopedDocs = useMemo(
    () => docs.filter((doc) => matchesFolderScope(resolveDocumentFolderPath(doc), selectedFolderPath)),
    [docs, selectedFolderPath],
  );

  const filtered = useMemo(() => {
    if (!search.trim()) {
      return scopedDocs;
    }
    const query = search.toLowerCase();
    return scopedDocs.filter((doc) => buildDocumentSearchText(doc).includes(query));
  }, [scopedDocs, search]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount - 1));
  }, [pageCount]);

  const pageDocs = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const groupedPageDocs = useMemo(() => buildFolderGroups(pageDocs, {
    resolvePath: (doc) => resolveDocumentDisplayPath(doc),
    resolveName: (doc) => doc?.name || '',
    resolveKey: (doc) => doc?.id || doc?.path || 'document',
  }), [pageDocs]);

  const toggleSelect = (id) => {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === pageDocs.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(pageDocs.map((doc) => doc.id)));
    }
  };

  const handleDeleteSelected = () => {
    if (!hasSelectedKb || selected.size === 0) {
      return;
    }
    if (!confirm(`确认删除知识库「${selectedKb.kb_name}」中的 ${selected.size} 个文档吗？`)) {
      return;
    }
    deleteMutation.mutate({ doc_ids: Array.from(selected), kb_id: selectedKbId });
  };

  const handleInspectDocument = (doc) => {
    if (!onSelectDocument) {
      return;
    }
    onSelectDocument(toDocumentSelection(doc, selectedKbId));
  };

  if (!hasSelectedKb) {
    return <div className='kb-selection-empty'>请先在左侧选择一个知识库。</div>;
  }
  if (isLoading) {
    return <p>正在加载 {selectedKb.kb_name} 的文档...</p>;
  }
  if (error) {
    return <p className='error' role='alert'>加载失败: {error.message}</p>;
  }

  const emptyMessage = docs.length === 0
    ? '当前知识库还没有文档。'
    : `当前目录范围「${selectedFolderLabel}」下没有文档。`;

  return (
    <div className='kb-doc-list'>
      <div className='kb-doc-toolbar'>
        <input
          className='kb-search-input'
          aria-label='搜索文档'
          placeholder='按名称或路径搜索...'
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(0);
          }}
        />
        <button
          type='button'
          className='kb-btn-danger'
          disabled={selected.size === 0 || deleteMutation.isPending}
          onClick={handleDeleteSelected}
        >
          删除已选 ({selected.size})
        </button>
        <span className='kb-doc-count'>{selectedKb.kb_name} · {selectedFolderLabel} · 共 {filtered.length} 项</span>
      </div>

      <table className='kb-doc-table'>
        <thead>
          <tr>
            <th>
              <input
                aria-label='全选当前页文档'
                type='checkbox'
                checked={selected.size === pageDocs.length && pageDocs.length > 0}
                onChange={toggleAll}
              />
            </th>
            <th>名称</th>
            <th>类型</th>
            <th>路径</th>
            <th>知识库</th>
          </tr>
        </thead>
        <tbody>
          {pageDocs.length === 0 ? (
            <tr><td colSpan={5} className='kb-empty'>{emptyMessage}</td></tr>
          ) : (
            groupedPageDocs.map((group) => (
              <Fragment key={group.key}>
                <tr className='kb-doc-group-row'>
                  <td colSpan={5}>
                    <div className='kb-doc-group-label'>
                      <span>目录</span>
                      <strong>{group.label}</strong>
                      <span>{group.itemCount} 项</span>
                    </div>
                  </td>
                </tr>
                {group.items.map((entry) => {
                  const doc = entry.item;
                  const isBulkSelected = selected.has(doc.id);
                  const isInspectSelected = selectedDocumentId === doc.id;
                  const rowClassName = (isBulkSelected ? 'selected ' : '') + (isInspectSelected ? 'kb-doc-row-active' : '');
                  const displayPath = entry.displayPath || resolveDocumentDisplayPath(doc);
                  return (
                    <tr
                      key={doc.id}
                      className={rowClassName.trim()}
                      aria-selected={isInspectSelected}
                      onClick={() => handleInspectDocument(doc)}
                    >
                      <td>
                        <input
                          aria-label={'选择 ' + doc.name}
                          type='checkbox'
                          checked={isBulkSelected}
                          onClick={(event) => event.stopPropagation()}
                          onChange={() => toggleSelect(doc.id)}
                        />
                      </td>
                      <td>{doc.name}</td>
                      <td>{doc.type}</td>
                      <td className='kb-doc-path' title={doc.path || displayPath}>{displayPath || doc.path}</td>
                      <td>{doc.kb_id || 'default'}</td>
                    </tr>
                  );
                })}
              </Fragment>
            ))
          )}
        </tbody>
      </table>

      <div className='kb-pagination'>
        <button type='button' disabled={page === 0} onClick={() => setPage((current) => current - 1)}>上一页</button>
        <span>{page + 1} / {pageCount}</span>
        <button type='button' disabled={page >= pageCount - 1} onClick={() => setPage((current) => current + 1)}>下一页</button>
      </div>
      {deleteMutation.error ? <p className='error' role='alert'>{deleteMutation.error.message}</p> : null}
    </div>
  );
}
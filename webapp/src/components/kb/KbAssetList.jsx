/**
 * 知识库资产列表
 * - 用于 Knowledge Workspace 资产视图，展示独立资产与内嵌资产对象。
 * - 资产列表会先按目录范围过滤，再按目录分组浏览与查看 OCR 诊断。
 */

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { listAssets } from '../../api/kb';
import { readApiData } from '../../api/response';
import { ALL_FOLDER_SCOPE, matchesFolderScope } from '../../domain/folderNavigation.js';
import { buildFolderGroups, getFolderPathFromObjectPath } from '../../domain/folderTree';
import { useKb } from './KbContext';

function getAssetStatusLabel(status) {
  if (status === 'active') {
    return '正常';
  }
  if (status === 'missing') {
    return '缺失';
  }
  if (status === 'orphaned') {
    return '孤立';
  }
  return status || '未知';
}

function getOcrStatusLabel(status) {
  if (status === 'success') {
    return '成功';
  }
  if (status === 'failed') {
    return '失败';
  }
  if (status === 'no_text') {
    return '无文本';
  }
  if (status === 'skipped') {
    return '已跳过';
  }
  return status || '未记录';
}

function toSafeNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getAssetDisplayName(asset) {
  if (asset?.title) {
    return asset.title;
  }
  const displayPath = asset?.relative_path || asset?.path || '';
  return displayPath ? displayPath.split('/').at(-1) : '未命名资产';
}

function resolveAssetDisplayPath(asset) {
  return asset?.relative_path || asset?.source_doc_relative_path || '';
}

function resolveAssetFolderPath(asset) {
  return getFolderPathFromObjectPath(resolveAssetDisplayPath(asset) || asset?.path || '');
}

function toAssetSelection(asset, fallbackKbId) {
  const relativePath = asset?.relative_path || '';
  const displayPath = relativePath || asset?.path || '';
  const ocrDiagnostics = asset?.ocr_diagnostics || {};

  return {
    key: 'asset:' + (asset?.asset_id || displayPath || 'unknown'),
    type: 'asset',
    id: asset?.asset_id || '',
    name: getAssetDisplayName(asset),
    path: displayPath,
    relativePath,
    folderPath: resolveAssetFolderPath(asset),
    sourcePath: asset?.path || '',
    kbId: asset?.kb_id || fallbackKbId,
    mimeType: asset?.mime_type || '',
    status: asset?.status || 'unknown',
    assetRole: asset?.asset_role || '',
    sourceDocRelativePath: asset?.source_doc_relative_path || '',
    referencedPath: asset?.locator?.referenced_path || '',
    indexedChunks: toSafeNumber(asset?.indexed_chunks),
    indexedFromOcr: Boolean(asset?.indexed_from_ocr || ocrDiagnostics.indexed_from_ocr),
    ocrStatus: asset?.ocr_status || ocrDiagnostics.ocr_status || '',
    ocrTextLength: toSafeNumber(asset?.ocr_text_length ?? ocrDiagnostics.ocr_text_length),
    ocrError: asset?.ocr_error || ocrDiagnostics.ocr_error || '',
    ocrEngine: asset?.ocr_engine || ocrDiagnostics.ocr_engine || '',
    assetRegistered: asset?.asset_registered !== false,
    raw: asset,
  };
}

function buildAssetSearchText(asset) {
  return [
    asset?.title,
    asset?.relative_path,
    asset?.source_doc_relative_path,
    asset?.asset_id,
    asset?.mime_type,
    asset?.asset_role,
    asset?.ocr_status,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

function AssetCard({ asset, entry, selectedKbId, selectedAssetId, onSelectAsset }) {
  const selection = toAssetSelection(asset, selectedKbId);
  const isActive = selectedAssetId === selection.id;

  return (
    <button
      type='button'
      className={'kb-asset-card' + (isActive ? ' is-active' : '')}
      onClick={() => onSelectAsset?.(selection)}
    >
      <div className='kb-asset-main'>
        <strong>{selection.name}</strong>
        <span className='kb-import-item-status'>{getAssetStatusLabel(selection.status)}</span>
      </div>
      <div className='kb-asset-meta'>
        <span>{entry.displayPath || selection.sourcePath || '未命名资产'}</span>
        <span>{selection.assetRole || '未标记角色'}</span>
        <span>{selection.mimeType || '未知 MIME'}</span>
        <span>宿主：{selection.sourceDocRelativePath || '独立资产'}</span>
        <span>OCR：{getOcrStatusLabel(selection.ocrStatus)}</span>
        <span>{selection.indexedFromOcr ? '来自 OCR 入索引' : '非 OCR 入索引'}</span>
        {selection.referencedPath ? <span>引用：{selection.referencedPath}</span> : null}
        {selection.ocrError ? <span>错误：{selection.ocrError}</span> : null}
      </div>
    </button>
  );
}

export default function KbAssetList({
  onSelectAsset,
  selectedAssetId = '',
  refreshVersion = 0,
  selectedFolderPath = ALL_FOLDER_SCOPE,
  selectedFolderLabel = '全部目录',
}) {
  const { selectedKbId, selectedKb, hasSelectedKb } = useKb();
  const [search, setSearch] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['assets', selectedKbId, refreshVersion],
    queryFn: () => listAssets(selectedKbId),
    enabled: hasSelectedKb,
  });

  useEffect(() => {
    setSearch('');
  }, [selectedKbId]);

  const assets = readApiData(data)?.items || [];
  const scopedAssets = useMemo(
    () => assets.filter((asset) => matchesFolderScope(resolveAssetFolderPath(asset), selectedFolderPath)),
    [assets, selectedFolderPath],
  );

  const filteredAssets = useMemo(() => {
    if (!search.trim()) {
      return scopedAssets;
    }
    const query = search.trim().toLowerCase();
    return scopedAssets.filter((asset) => buildAssetSearchText(asset).includes(query));
  }, [scopedAssets, search]);

  const assetGroups = useMemo(() => buildFolderGroups(filteredAssets, {
    resolvePath: (asset) => resolveAssetDisplayPath(asset),
    resolveName: (asset) => getAssetDisplayName(asset),
    resolveKey: (asset) => asset?.asset_id || asset?.path || asset?.title || 'asset',
  }), [filteredAssets]);

  if (!hasSelectedKb) {
    return <div className='kb-selection-empty'>请先在左侧选择一个知识库。</div>;
  }
  if (isLoading) {
    return <p>正在加载 {selectedKb.kb_name} 的资产...</p>;
  }
  if (error) {
    return <p className='error' role='alert'>加载失败: {error.message}</p>;
  }

  const emptyMessage = assets.length === 0
    ? '当前知识库还没有资产对象。'
    : `当前目录范围「${selectedFolderLabel}」下没有资产对象。`;

  return (
    <div className='kb-asset-list'>
      <div className='kb-doc-toolbar'>
        <input
          className='kb-search-input'
          aria-label='搜索资产'
          placeholder='按路径、类型或 OCR 状态搜索...'
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <span className='kb-doc-count'>{selectedKb.kb_name} · {selectedFolderLabel} · 共 {filteredAssets.length} 项</span>
      </div>

      {filteredAssets.length === 0 ? (
        <div className='kb-empty-state-panel'>{emptyMessage}</div>
      ) : (
        <div className='kb-asset-group-list'>
          {assetGroups.map((group) => (
            <section className='kb-folder-section' key={group.key}>
              <div className='kb-folder-section-head'>
                <div>
                  <span className='kb-folder-section-eyebrow'>目录</span>
                  <strong>{group.label}</strong>
                </div>
                <span className='kb-object-explorer-meta'>{group.itemCount} 项</span>
              </div>
              <div className='kb-folder-card-list'>
                {group.items.map((entry) => (
                  <AssetCard
                    key={entry.key}
                    asset={entry.item}
                    entry={entry}
                    selectedKbId={selectedKbId}
                    selectedAssetId={selectedAssetId}
                    onSelectAsset={onSelectAsset}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
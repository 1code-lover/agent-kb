/**
 * 知识库对象区
 * - 按 Knowledge Workspace 的 viewMode 渲染文档、资产、最近导入等对象浏览面板。
 * - 文档/资产视图接入目录范围浏览，目录只承担组织与筛选职责，不承担安全边界。
 */

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { listFolders } from '../../api/kb';
import { readApiData } from '../../api/response';
import {
  ALL_FOLDER_SCOPE,
  buildFolderOptions,
  getFolderScopeLabel,
  hasFolderOption,
  matchesFolderScope,
} from '../../domain/folderNavigation.js';
import { KB_WORKSPACE_VIEW_MODES, getWorkspaceViewMeta } from '../../domain/knowledgeWorkspace';
import KbAssetList from './KbAssetList';
import KbDocumentList from './KbDocumentList';
import KbReceiptSummary from './KbReceiptSummary';

function WorkspacePlaceholder({ title, description }) {
  return (
    <div className='kb-view-placeholder'>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

function getObjectStatusLabel(status) {
  if (status === 'indexed') {
    return '已索引';
  }
  if (status === 'empty') {
    return '空结果';
  }
  if (status === 'failed') {
    return '失败';
  }
  if (status === 'ready') {
    return '就绪';
  }
  if (status === 'missing') {
    return '缺失';
  }
  if (status === 'invalid') {
    return '无效';
  }
  return status || '未知';
}

function getEmptyReasonLabel(reason) {
  if (reason === 'ocr_failed') {
    return 'OCR 执行失败';
  }
  if (reason === 'ocr_skipped') {
    return '当前文件未执行 OCR';
  }
  if (reason === 'no_extractable_text') {
    return '未提取到可索引文本';
  }
  if (reason === 'embedded_ocr_failed') {
    return '内嵌图片 OCR 失败';
  }
  if (reason === 'embedded_no_extractable_text') {
    return '内嵌图片未提取到文本';
  }
  if (reason === 'embedded_ocr_no_nodes') {
    return '内嵌图片 OCR 有结果但未生成节点';
  }
  if (reason === 'no_nodes_generated') {
    return '没有生成任何可索引节点';
  }
  if (reason === 'shadowed_by_embedded_asset') {
    return '被内嵌资产接管';
  }
  return reason || '';
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

function isSelectedObject(selectedObject, item) {
  return Boolean(selectedObject && item && selectedObject.type === item.type && selectedObject.key === item.key);
}

function ReceiptAssetRow({ asset, selectedObject, onSelectObject }) {
  const active = isSelectedObject(selectedObject, asset);
  return (
    <button
      type='button'
      className={'kb-import-asset-button' + (active ? ' is-active' : '')}
      onClick={() => onSelectObject?.(asset)}
    >
      <div className='kb-import-item-main'>
        <strong>{asset.name}</strong>
        <span className='kb-import-item-status'>{getObjectStatusLabel(asset.status)}</span>
      </div>
      <div className='kb-import-item-meta'>
        <span>{asset.path || '未命名资产'}</span>
        <span>{asset.ocrStatus ? 'OCR=' + getOcrStatusLabel(asset.ocrStatus) : '未记录 OCR 状态'}</span>
        <span>{asset.indexedFromOcr ? '来自 OCR 入索引' : '非 OCR 入索引'}</span>
      </div>
      {asset.ocrError ? <p className='kb-import-item-hint'>OCR 错误：{asset.ocrError}</p> : null}
    </button>
  );
}

function ReceiptFileRow({ item, selectedObject, onSelectObject }) {
  const active = isSelectedObject(selectedObject, item);
  const embeddedAssets = Array.isArray(item.embeddedAssets) ? item.embeddedAssets : [];
  const emptyReasonLabel = getEmptyReasonLabel(item.emptyReason);

  return (
    <div className='kb-import-item-card'>
      <button
        type='button'
        className={'kb-import-item-button' + (active ? ' is-active' : '')}
        onClick={() => onSelectObject?.(item)}
      >
        <div className='kb-import-item-main'>
          <strong>{item.name}</strong>
          <span className='kb-import-item-status'>{getObjectStatusLabel(item.status)}</span>
        </div>
        <div className='kb-import-item-meta'>
          <span>{item.path || '未命名文件'}</span>
          <span>{item.docType || item.fileKind || '未知类型'}</span>
          <span>{item.indexedChunks} 个分块</span>
          <span>{embeddedAssets.length} 个资产</span>
        </div>
      </button>

      {emptyReasonLabel ? <p className='kb-import-item-hint'>空结果原因：{emptyReasonLabel}</p> : null}
      {item.message ? <p className='kb-import-item-hint'>结果说明：{item.message}</p> : null}
      {item.assetWarningCount > 0 ? <p className='kb-import-item-hint'>资产告警：{item.assetWarningCount} 项</p> : null}
      {item.ocrStatus ? <p className='kb-import-item-hint'>OCR 状态：{getOcrStatusLabel(item.ocrStatus)}</p> : null}
      {item.skipStandaloneAsset ? (
        <p className='kb-import-item-hint'>该独立图片已被同批内嵌资产接管，不再重复执行独立 OCR 与索引。</p>
      ) : null}
      {item.stageTimingSummaryText ? <p className='kb-import-item-hint'>阶段耗时：{item.stageTimingSummaryText}</p> : null}

      {embeddedAssets.length > 0 ? (
        <div className='kb-import-asset-list'>
          {embeddedAssets.map((asset) => (
            <ReceiptAssetRow
              key={asset.key}
              asset={asset}
              selectedObject={selectedObject}
              onSelectObject={onSelectObject}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ReceiptUrlRow({ item, selectedObject, onSelectObject }) {
  const active = isSelectedObject(selectedObject, item);
  return (
    <div className='kb-import-item-card'>
      <button
        type='button'
        className={'kb-import-item-button' + (active ? ' is-active' : '')}
        onClick={() => onSelectObject?.(item)}
      >
        <div className='kb-import-item-main'>
          <strong>{item.name}</strong>
          <span className='kb-import-item-status'>{getObjectStatusLabel(item.status)}</span>
        </div>
        <div className='kb-import-item-meta'>
          <span>{item.url || '未命名 URL'}</span>
          <span>{item.indexedChunks} 个分块</span>
        </div>
      </button>
      {item.message ? <p className='kb-import-item-hint'>结果说明：{item.message}</p> : null}
    </div>
  );
}

function RecentImportExplorer({ receiptSummary, selectedObject, onSelectObject }) {
  if (!receiptSummary) {
    return (
      <WorkspacePlaceholder
        title='暂无导入回执'
        description='请先执行文件导入或网页导入，完成后这里会展示最近一次回执与对象列表。'
      />
    );
  }

  const items = Array.isArray(receiptSummary.items) ? receiptSummary.items : [];

  return (
    <div className='kb-import-receipt-stack'>
      <KbReceiptSummary receiptSummary={receiptSummary} />
      {items.length > 0 ? (
        <div className='kb-import-item-list'>
          {items.map((item) => {
            if (item.type === 'import-url') {
              return (
                <ReceiptUrlRow
                  key={item.key}
                  item={item}
                  selectedObject={selectedObject}
                  onSelectObject={onSelectObject}
                />
              );
            }
            return (
              <ReceiptFileRow
                key={item.key}
                item={item}
                selectedObject={selectedObject}
                onSelectObject={onSelectObject}
              />
            );
          })}
        </div>
      ) : (
        <p className='kb-detail-empty-text'>当前导入回执里没有 file_results / url_results 明细。</p>
      )}
    </div>
  );
}

function supportsFolderBrowsing(viewMode) {
  return viewMode === KB_WORKSPACE_VIEW_MODES.DOCUMENTS || viewMode === KB_WORKSPACE_VIEW_MODES.ASSETS;
}

function shouldKeepSelectionInScope(viewMode, selectedObject, selectedFolderScope) {
  if (!selectedObject) {
    return true;
  }
  if (viewMode === KB_WORKSPACE_VIEW_MODES.DOCUMENTS) {
    if (selectedObject.type !== 'document') {
      return true;
    }
    return matchesFolderScope(selectedObject.folderPath || '', selectedFolderScope);
  }
  if (viewMode === KB_WORKSPACE_VIEW_MODES.ASSETS) {
    if (selectedObject.type !== 'asset') {
      return true;
    }
    return matchesFolderScope(selectedObject.folderPath || '', selectedFolderScope);
  }
  return true;
}

function FolderScopeBar({
  folderOptions,
  selectedFolderScope,
  selectedFolderLabel,
  onChangeFolderScope,
  isFetching,
  error,
}) {
  const folderCount = folderOptions.filter((item) => item.kind === 'folder').length;

  return (
    <div className='kb-folder-scope-bar'>
      <label className='kb-folder-scope-label' htmlFor='kb-folder-scope-select'>目录范围</label>
      <select
        id='kb-folder-scope-select'
        className='kb-folder-scope-select'
        value={selectedFolderScope}
        onChange={(event) => onChangeFolderScope(event.target.value)}
      >
        {folderOptions.map((option) => (
          <option key={option.key} value={option.value}>{option.label}</option>
        ))}
      </select>
      <span className='kb-folder-scope-hint'>当前：{selectedFolderLabel}</span>
      <span className='kb-folder-scope-hint'>共 {folderCount} 个目录</span>
      {isFetching ? <span className='kb-folder-scope-hint'>目录刷新中...</span> : null}
      {error ? <span className='error kb-folder-scope-error'>目录加载失败：{error.message}</span> : null}
    </div>
  );
}

export default function KbObjectExplorer({
  hasSelectedKb,
  selectedKb,
  viewMode,
  receiptSummary,
  refreshVersion,
  selectedObject,
  onSelectObject,
}) {
  const viewMeta = getWorkspaceViewMeta(viewMode);
  const selectedKbId = selectedKb?.kb_id || '';
  const folderBrowseEnabled = hasSelectedKb && supportsFolderBrowsing(viewMode);
  const [selectedFolderScope, setSelectedFolderScope] = useState(ALL_FOLDER_SCOPE);
  const [folderRefreshVersion, setFolderRefreshVersion] = useState(0);

  const folderQuery = useQuery({
    queryKey: ['kb-folders', selectedKbId, refreshVersion, folderRefreshVersion],
    queryFn: () => listFolders(selectedKbId),
    enabled: folderBrowseEnabled && Boolean(selectedKbId),
  });

  const folderOptions = useMemo(
    () => buildFolderOptions(readApiData(folderQuery.data)?.folders || []),
    [folderQuery.data],
  );
  const selectedFolderLabel = useMemo(
    () => getFolderScopeLabel(folderOptions, selectedFolderScope),
    [folderOptions, selectedFolderScope],
  );

  useEffect(() => {
    setSelectedFolderScope(ALL_FOLDER_SCOPE);
    setFolderRefreshVersion(0);
  }, [selectedKbId]);

  useEffect(() => {
    if (!folderBrowseEnabled) {
      return;
    }
    if (!hasFolderOption(folderOptions, selectedFolderScope)) {
      setSelectedFolderScope(ALL_FOLDER_SCOPE);
    }
  }, [folderBrowseEnabled, folderOptions, selectedFolderScope]);

  useEffect(() => {
    if (!folderBrowseEnabled || !onSelectObject) {
      return;
    }
    if (!shouldKeepSelectionInScope(viewMode, selectedObject, selectedFolderScope)) {
      onSelectObject(null);
    }
  }, [folderBrowseEnabled, onSelectObject, selectedFolderScope, selectedObject, viewMode]);

  let content = null;
  if (!hasSelectedKb) {
    content = <div className='kb-selection-empty'>请先选择一个已启用的知识库，再浏览对象区内容。</div>;
  } else if (viewMode === KB_WORKSPACE_VIEW_MODES.DOCUMENTS) {
    content = (
      <KbDocumentList
        onSelectDocument={onSelectObject}
        onDocumentsChanged={() => setFolderRefreshVersion((current) => current + 1)}
        selectedDocumentId={selectedObject?.type === 'document' ? selectedObject.id : ''}
        refreshVersion={refreshVersion}
        selectedFolderPath={selectedFolderScope}
        selectedFolderLabel={selectedFolderLabel}
      />
    );
  } else if (viewMode === KB_WORKSPACE_VIEW_MODES.ASSETS) {
    content = (
      <KbAssetList
        onSelectAsset={onSelectObject}
        selectedAssetId={selectedObject?.type === 'asset' ? selectedObject.id : ''}
        refreshVersion={refreshVersion}
        selectedFolderPath={selectedFolderScope}
        selectedFolderLabel={selectedFolderLabel}
      />
    );
  } else if (viewMode === KB_WORKSPACE_VIEW_MODES.RECENT_IMPORTS) {
    content = (
      <RecentImportExplorer
        receiptSummary={receiptSummary}
        selectedObject={selectedObject}
        onSelectObject={onSelectObject}
      />
    );
  } else {
    content = <WorkspacePlaceholder title={viewMeta.label} description={viewMeta.description} />;
  }

  return (
    <section className='kb-object-explorer'>
      <div className='kb-object-explorer-head'>
        <div>
          <p className='kb-detail-eyebrow'>对象区</p>
          <h2>{viewMeta.label}</h2>
          <p className='kb-workspace-description'>{selectedKb?.kb_name ? viewMeta.description : '请选择知识库'}</p>
        </div>
        {folderBrowseEnabled ? (
          <FolderScopeBar
            folderOptions={folderOptions}
            selectedFolderScope={selectedFolderScope}
            selectedFolderLabel={selectedFolderLabel}
            onChangeFolderScope={setSelectedFolderScope}
            isFetching={folderQuery.isFetching}
            error={folderQuery.error}
          />
        ) : null}
      </div>
      <div className='kb-object-explorer-body'>{content}</div>
    </section>
  );
}

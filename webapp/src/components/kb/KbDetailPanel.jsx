/**
 * Knowledge Workspace 详情区
 * - 展示知识库概览、最近回执、当前对象元信息与证据预览
 */

import { useEffect, useMemo, useState } from 'react';

import KbReceiptSummary from './KbReceiptSummary';
import KbEvidencePreview from './KbEvidencePreview';
import { previewItem } from '../../api/evidence';
import { readApiData } from '../../api/response';

function MetaRow({ label, value }) {
  return (
    <div className='kb-detail-row'>
      <span className='kb-detail-label'>{label}</span>
      <span className='kb-detail-value'>{value}</span>
    </div>
  );
}

function formatFolderValue(folderPath) {
  if (folderPath === '') {
    return '根目录';
  }
  return folderPath || '-';
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
  return reason || '-';
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

function getBooleanLabel(value) {
  return value ? '是' : '否';
}

function buildPreviewTarget(selectedObject, selectedKbId) {
  if (!selectedObject) {
    return null;
  }
  const kbId = selectedObject.kbId || selectedKbId;
  if (!kbId) {
    return null;
  }
  if (selectedObject.type === 'asset' && selectedObject.id) {
    return { kb_id: kbId, asset_id: selectedObject.id };
  }
  if (selectedObject.type === 'document' && selectedObject.id) {
    return { kb_id: kbId, doc_id: selectedObject.id };
  }
  return null;
}

function renderObjectMeta(selectedObject, selectedKbId) {
  if (!selectedObject) {
    return (
      <p className='kb-detail-empty-text'>
        请选择左侧对象，右侧会展示对象元数据、导入诊断信息，以及可预览对象的证据内容。
      </p>
    );
  }

  if (selectedObject.type === 'asset') {
    return (
      <div className='kb-detail-stack'>
        <MetaRow label='对象类型' value='asset' />
        <MetaRow label='资产 ID' value={selectedObject.id || '-'} />
        <MetaRow label='名称' value={selectedObject.name || '-'} />
        <MetaRow label='资产角色' value={selectedObject.assetRole || '-'} />
        <MetaRow label='相对路径' value={selectedObject.relativePath || selectedObject.path || '-'} />
        <MetaRow label='文件夹' value={formatFolderValue(selectedObject.folderPath)} />
        <MetaRow label='来源路径' value={selectedObject.sourcePath || selectedObject.raw?.path || '-'} />
        <MetaRow label='MIME' value={selectedObject.mimeType || '-'} />
        <MetaRow label='状态' value={selectedObject.status || '-'} />
        <MetaRow label='来源文档' value={selectedObject.sourceDocRelativePath || '-'} />
        <MetaRow label='引用路径' value={selectedObject.referencedPath || '-'} />
        <MetaRow label='OCR 状态' value={getOcrStatusLabel(selectedObject.ocrStatus)} />
        <MetaRow label='OCR 文本长度' value={String(selectedObject.ocrTextLength ?? 0)} />
        <MetaRow label='OCR 引擎' value={selectedObject.ocrEngine || '-'} />
        <MetaRow label='OCR 错误' value={selectedObject.ocrError || '-'} />
        <MetaRow label='由 OCR 入索引' value={getBooleanLabel(selectedObject.indexedFromOcr)} />
        <MetaRow label='切片数' value={String(selectedObject.indexedChunks ?? 0)} />
        <MetaRow label='知识库' value={selectedObject.kbId || selectedKbId || '-'} />
      </div>
    );
  }

  if (selectedObject.type === 'import-file') {
    return (
      <div className='kb-detail-stack'>
        <MetaRow label='对象类型' value='import-file' />
        <MetaRow label='名称' value={selectedObject.name || '-'} />
        <MetaRow label='对象路径' value={selectedObject.path || '-'} />
        <MetaRow label='相对路径' value={selectedObject.relativePath || '-'} />
        <MetaRow label='文件夹' value={formatFolderValue(selectedObject.folderPath)} />
        <MetaRow label='落盘路径' value={selectedObject.sourcePath || '-'} />
        <MetaRow label='导入状态' value={selectedObject.status || '-'} />
        <MetaRow label='错误信息' value={selectedObject.message || '-'} />
        <MetaRow label='文档 MIME' value={selectedObject.docType || '-'} />
        <MetaRow label='文件类型' value={selectedObject.fileKind || '-'} />
        <MetaRow label='空导入原因' value={getEmptyReasonLabel(selectedObject.emptyReason)} />
        <MetaRow label='OCR 状态' value={getOcrStatusLabel(selectedObject.ocrStatus)} />
        <MetaRow label='OCR 文本长度' value={String(selectedObject.ocrTextLength ?? 0)} />
        <MetaRow label='OCR 引擎' value={selectedObject.ocrEngine || '-'} />
        <MetaRow label='OCR 错误' value={selectedObject.ocrError || '-'} />
        <MetaRow label='由 OCR 入索引' value={getBooleanLabel(selectedObject.indexedFromOcr)} />
        <MetaRow label='已登记为资产' value={getBooleanLabel(selectedObject.assetRegistered)} />
        <MetaRow label='独立资产候选' value={getBooleanLabel(selectedObject.standaloneAssetCandidate)} />
        <MetaRow label='独立图片已跳过' value={getBooleanLabel(selectedObject.skipStandaloneAsset)} />
        <MetaRow label='\u89e3\u6790\u6587\u6863\u6570' value={String(selectedObject.documentCount ?? 0)} />
        <MetaRow label='\u7a7a\u6587\u6863\u6570' value={String(selectedObject.emptyDocumentCount ?? 0)} />
        <MetaRow label='\u8f93\u5165\u6587\u672c\u5b57\u7b26\u6570' value={String(selectedObject.inputTextChars ?? 0)} />
        <MetaRow label='\u8282\u70b9\u6570' value={String(selectedObject.nodeCount ?? 0)} />
        <MetaRow label='\u542b\u5411\u91cf\u8282\u70b9\u6570' value={String(selectedObject.nodesWithEmbeddingCount ?? 0)} />
        <MetaRow label='\u65e0\u5411\u91cf\u8282\u70b9\u6570' value={String(selectedObject.nodesWithoutEmbeddingCount ?? 0)} />
        <MetaRow label='阶段耗时' value={selectedObject.stageTimingSummaryText || '-'} />
        <MetaRow label='\u7d22\u5f15\u7ec6\u5206\u8017\u65f6' value={selectedObject.indexStageSummaryText || '-'} />
        <MetaRow label='切片数' value={String(selectedObject.indexedChunks ?? 0)} />
        <MetaRow label='内嵌资产数' value={String(selectedObject.embeddedAssetCount ?? 0)} />
        <MetaRow label='内嵌资产就绪' value={String(selectedObject.embeddedAssetReadyCount ?? 0)} />
        <MetaRow label='内嵌资产缺失' value={String(selectedObject.embeddedAssetMissingCount ?? 0)} />
        <MetaRow label='内嵌资产无效' value={String(selectedObject.embeddedAssetInvalidCount ?? 0)} />
        <MetaRow label='内嵌 OCR 尝试' value={String(selectedObject.embeddedOcrAttemptedCount ?? 0)} />
        <MetaRow label='内嵌 OCR 成功' value={String(selectedObject.embeddedOcrSuccessCount ?? 0)} />
        <MetaRow label='内嵌 OCR 无文本' value={String(selectedObject.embeddedOcrNoTextCount ?? 0)} />
        <MetaRow label='内嵌 OCR 失败' value={String(selectedObject.embeddedOcrFailedCount ?? 0)} />
        <MetaRow label='内嵌 OCR 入索引' value={String(selectedObject.embeddedIndexedFromOcrCount ?? 0)} />
        <MetaRow label='资产告警数' value={String(selectedObject.assetWarningCount ?? 0)} />
        <MetaRow label='知识库' value={selectedObject.kbId || selectedKbId || '-'} />
      </div>
    );
  }

  if (selectedObject.type === 'import-url') {
    return (
      <div className='kb-detail-stack'>
        <MetaRow label='对象类型' value='import-url' />
        <MetaRow label='URL' value={selectedObject.url || selectedObject.path || '-'} />
        <MetaRow label='导入状态' value={selectedObject.status || '-'} />
        <MetaRow label='切片数' value={String(selectedObject.indexedChunks ?? 0)} />
        <MetaRow label='错误信息' value={selectedObject.message || '-'} />
        <MetaRow label='知识库' value={selectedObject.kbId || selectedKbId || '-'} />
      </div>
    );
  }

  return (
    <div className='kb-detail-stack'>
      <MetaRow label='对象类型' value={selectedObject.type} />
      <MetaRow label='名称' value={selectedObject.name || '-'} />
      <MetaRow label='对象 ID' value={selectedObject.id || '-'} />
      <MetaRow label='相对路径' value={selectedObject.relativePath || selectedObject.path || '-'} />
      <MetaRow label='文件夹' value={formatFolderValue(selectedObject.folderPath)} />
      <MetaRow label='来源路径' value={selectedObject.sourcePath || selectedObject.raw?.path || '-'} />
      <MetaRow label='文档类型' value={selectedObject.docType || '-'} />
      <MetaRow label='知识库' value={selectedObject.kbId || selectedKbId || '-'} />
    </div>
  );
}

export default function KbDetailPanel({
  hasSelectedKb,
  selectedKb,
  selectedKbId,
  receiptSummary,
  selectedObject,
}) {
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewTarget = useMemo(() => buildPreviewTarget(selectedObject, selectedKbId), [selectedObject, selectedKbId]);

  useEffect(() => {
    let cancelled = false;

    if (!previewTarget) {
      setPreview(null);
      setPreviewError('');
      setPreviewLoading(false);
      return () => {
        cancelled = true;
      };
    }

    async function loadPreview() {
      setPreviewLoading(true);
      setPreviewError('');
      try {
        const response = await previewItem(previewTarget, selectedKbId);
        if (cancelled) {
          return;
        }
        setPreview(readApiData(response) || null);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setPreview(null);
        setPreviewError(error?.message || '加载证据预览失败。');
      } finally {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      }
    }

    loadPreview();
    return () => {
      cancelled = true;
    };
  }, [previewTarget, selectedKbId]);

  if (!hasSelectedKb) {
    return (
      <aside className='kb-detail-panel'>
        <div className='kb-detail-card kb-detail-empty'>
          <h3>详情区</h3>
          <p>请先选择 active 知识库，右侧才会展示知识库概览、对象详情与预览。</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className='kb-detail-panel'>
      <section className='kb-detail-card'>
        <div className='kb-detail-card-head'>
          <div>
            <p className='kb-detail-eyebrow'>知识库</p>
            <h3>{selectedKb?.kb_name}</h3>
          </div>
          <span className='kb-status-pill'>active</span>
        </div>
        <MetaRow label='kb_id' value={selectedKbId} />
        <MetaRow label='存储目录' value={'data/' + selectedKbId + '/'} />
        <MetaRow label='文档数' value={typeof selectedKb?.doc_count === 'number' ? selectedKb.doc_count : '-'} />
      </section>

      <section className='kb-detail-card'>
        <div className='kb-detail-card-head'>
          <div>
            <p className='kb-detail-eyebrow'>回执</p>
            <h3>最近导入</h3>
          </div>
        </div>
        <KbReceiptSummary
          receiptSummary={receiptSummary}
          emptyMessage='当前知识库还没有最近导入回执。'
        />
      </section>

      <section className='kb-detail-card'>
        <div className='kb-detail-card-head'>
          <div>
            <p className='kb-detail-eyebrow'>对象</p>
            <h3>{selectedObject ? '对象详情' : '等待选择对象'}</h3>
          </div>
        </div>
        {renderObjectMeta(selectedObject, selectedKbId)}
      </section>

      <section className='kb-detail-card'>
        <div className='kb-detail-card-head'>
          <div>
            <p className='kb-detail-eyebrow'>预览</p>
            <h3>{previewTarget ? '证据预览' : '暂无预览'}</h3>
          </div>
        </div>
        {previewTarget ? (
          <KbEvidencePreview preview={preview} loading={previewLoading} error={previewError} />
        ) : (
          <p className='kb-detail-empty-text'>当前对象不支持直接预览，请选择文档或资产对象查看证据内容。</p>
        )}
      </section>
    </aside>
  );
}

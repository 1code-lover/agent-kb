/**
 * 文件功能：
 * - 文件 / 目录导入组件，强制绑定已明确选择的目标知识库。
 * - 前端显式补齐 import_mode 与 relative_paths，接通后端目录化导入契约。
 */

import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { importFiles } from '../../api/kb';
import { readApiData } from '../../api/response';
import {
  buildImportPayload,
  buildUploadEntries,
  getUploadEntryLabel,
  KB_IMPORT_MODES,
} from '../../domain/uploadImport';
import { useKb } from './KbContext';

function formatFileSize(file) {
  return `${(file.size / 1024).toFixed(1)} KB`;
}

export default function KbUpload({ onSuccess }) {
  const { selectedKb, selectedKbId, hasSelectedKb } = useKb();
  const [uploadEntries, setUploadEntries] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [importMode, setImportMode] = useState(KB_IMPORT_MODES.FLATTEN);
  const fileInputRef = useRef(null);
  const directoryInputRef = useRef(null);

  const resetSelection = () => {
    setUploadEntries([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (directoryInputRef.current) directoryInputRef.current.value = '';
  };

  const uploadMutation = useMutation({
    mutationFn: ({ formData, kbId, options }) => importFiles(formData, kbId, options),
    onSuccess: (response) => {
      resetSelection();
      if (onSuccess) onSuccess(readApiData(response) || {});
    },
  });

  useEffect(() => {
    if (!hasSelectedKb) {
      resetSelection();
    }
  }, [hasSelectedKb]);

  const addFiles = (list) => {
    if (!hasSelectedKb || !list?.length) return;
    const nextEntries = buildUploadEntries(list);
    setUploadEntries((previous) => [...previous, ...nextEntries]);
  };

  const removeFile = (index) => {
    setUploadEntries((previous) => previous.filter((_, fileIndex) => fileIndex !== index));
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragOver(false);
    if (!hasSelectedKb) return;
    addFiles(event.dataTransfer.files);
  };

  const handleUpload = () => {
    if (!hasSelectedKb || uploadEntries.length === 0) return;
    const payload = buildImportPayload(uploadEntries, importMode);
    const formData = new FormData();
    payload.files.forEach((file) => formData.append('files', file));
    uploadMutation.mutate({
      formData,
      kbId: selectedKbId,
      options: {
        importMode: payload.importMode,
        relativePaths: payload.relativePaths,
      },
    });
  };

  const openPicker = () => {
    if (!hasSelectedKb) return;
    if (importMode === KB_IMPORT_MODES.PRESERVE_TREE) {
      directoryInputRef.current?.click();
      return;
    }
    fileInputRef.current?.click();
  };

  const helperText = importMode === KB_IMPORT_MODES.PRESERVE_TREE
    ? '保留目录模式会提交 relative_paths。点击下方区域后请选择目录；若拖拽普通文件，将按知识库根目录对象导入。'
    : '平铺模式会显式发送 import_mode=flatten，并忽略原始目录层级。';

  return (
    <div className='kb-upload'>
      <section className={`kb-target-card ${hasSelectedKb ? 'ready' : 'missing'}`} aria-live='polite'>
        <strong>{hasSelectedKb ? '当前上传目标' : '尚未选择目标知识库'}</strong>
        {hasSelectedKb ? (
          <>
            <span>{selectedKb.kb_name}</span>
            <code>kb_id: {selectedKbId}</code>
            <code>落盘目录: data/{selectedKbId}/</code>
          </>
        ) : (
          <span>请先在左侧知识库列表中选择一个 active 知识库，或新建知识库。</span>
        )}
      </section>

      <section className='kb-upload-mode-card' aria-labelledby='kb-upload-mode-title'>
        <div>
          <p id='kb-upload-mode-title' className='kb-upload-mode-title'>导入模式</p>
          <p className='kb-upload-mode-hint'>{helperText}</p>
        </div>
        <div className='kb-upload-mode-options' role='radiogroup' aria-label='知识库导入模式'>
          <label className={`kb-upload-mode-option ${importMode === KB_IMPORT_MODES.FLATTEN ? 'selected' : ''}`}>
            <input
              type='radio'
              name='kb-import-mode'
              value={KB_IMPORT_MODES.FLATTEN}
              checked={importMode === KB_IMPORT_MODES.FLATTEN}
              onChange={() => {
                setImportMode(KB_IMPORT_MODES.FLATTEN);
                resetSelection();
              }}
            />
            <span>平铺导入</span>
            <small>适合散文件上传，前端固定发送 flatten。</small>
          </label>
          <label className={`kb-upload-mode-option ${importMode === KB_IMPORT_MODES.PRESERVE_TREE ? 'selected' : ''}`}>
            <input
              type='radio'
              name='kb-import-mode'
              value={KB_IMPORT_MODES.PRESERVE_TREE}
              checked={importMode === KB_IMPORT_MODES.PRESERVE_TREE}
              onChange={() => {
                setImportMode(KB_IMPORT_MODES.PRESERVE_TREE);
                resetSelection();
              }}
            />
            <span>保留目录</span>
            <small>适合知识库内分层资料，前端会逐项回传 relative_paths。</small>
          </label>
        </div>
      </section>

      <div
        className={`kb-dropzone ${dragOver ? 'drag-over' : ''} ${hasSelectedKb ? '' : 'disabled'}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (hasSelectedKb) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={openPicker}
        onKeyDown={(event) => {
          if (hasSelectedKb && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            openPicker();
          }
        }}
        role='button'
        tabIndex={hasSelectedKb ? 0 : -1}
        aria-disabled={!hasSelectedKb}
      >
        <input
          ref={fileInputRef}
          type='file'
          multiple
          hidden
          disabled={!hasSelectedKb}
          onChange={(event) => {
            addFiles(event.target.files);
            event.target.value = '';
          }}
        />
        <input
          ref={directoryInputRef}
          type='file'
          multiple
          hidden
          webkitdirectory=''
          directory=''
          disabled={!hasSelectedKb}
          onChange={(event) => {
            addFiles(event.target.files);
            event.target.value = '';
          }}
        />
        <p>
          {hasSelectedKb
            ? importMode === KB_IMPORT_MODES.PRESERVE_TREE
              ? '点击选择目录，或拖拽文件作为知识库根目录对象导入'
              : '拖拽文件到此处，或点击选择文件'
            : '选择目标知识库后才能添加文件'}
        </p>
      </div>

      {uploadEntries.length > 0 ? (
        <ul className='kb-file-list'>
          {uploadEntries.map((entry, index) => (
            <li key={`${entry.file.name}-${entry.file.size}-${entry.file.lastModified}-${index}`}>
              <div className='kb-file-list-meta'>
                <span>{getUploadEntryLabel(entry)} ({formatFileSize(entry.file)})</span>
                {importMode === KB_IMPORT_MODES.PRESERVE_TREE ? (
                  <code>{entry.relativePath || entry.file.name}</code>
                ) : null}
              </div>
              <button
                type='button'
                className='kb-btn-icon'
                aria-label={`移除 ${entry.file.name}`}
                onClick={() => removeFile(index)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <button
        type='button'
        className='kb-upload-btn'
        disabled={!hasSelectedKb || uploadEntries.length === 0 || uploadMutation.isPending}
        onClick={handleUpload}
      >
        {uploadMutation.isPending
          ? '上传并索引中...'
          : `上传到 ${selectedKb?.kb_name || '未选择知识库'} (${uploadEntries.length})`}
      </button>

      {uploadMutation.error ? <p className='error' role='alert'>{uploadMutation.error.message}</p> : null}
    </div>
  );
}
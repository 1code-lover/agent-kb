/**
 * 文件功能：
 * - 文件拖拽/点击上传组件，强制绑定已明确选择的目标知识库。
 */

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { importFiles } from "../../api/kb";
import { readApiData } from "../../api/response";
import { useKb } from "./KbContext";

export default function KbUpload({ onSuccess }) {
  const { selectedKb, selectedKbId, hasSelectedKb } = useKb();
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const uploadMutation = useMutation({
    mutationFn: ({ formData, kbId }) => importFiles(formData, kbId),
    onSuccess: (response) => {
      setFiles([]);
      if (inputRef.current) inputRef.current.value = "";
      if (onSuccess) onSuccess(readApiData(response) || {});
    },
  });

  const addFiles = (list) => {
    if (!hasSelectedKb || !list?.length) return;
    setFiles((previous) => [...previous, ...Array.from(list)]);
  };

  const removeFile = (index) => {
    setFiles((previous) => previous.filter((_, fileIndex) => fileIndex !== index));
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragOver(false);
    if (!hasSelectedKb) return;
    addFiles(event.dataTransfer.files);
  };

  const handleUpload = () => {
    if (!hasSelectedKb || files.length === 0) return;
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    uploadMutation.mutate({ formData, kbId: selectedKbId });
  };

  return (
    <div className="kb-upload">
      <section className={`kb-target-card ${hasSelectedKb ? "ready" : "missing"}`} aria-live="polite">
        <strong>{hasSelectedKb ? "当前上传目标" : "尚未选择目标知识库"}</strong>
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

      <div
        className={`kb-dropzone ${dragOver ? "drag-over" : ""} ${hasSelectedKb ? "" : "disabled"}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (hasSelectedKb) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => { if (hasSelectedKb) inputRef.current?.click(); }}
        onKeyDown={(event) => {
          if (hasSelectedKb && (event.key === "Enter" || event.key === " ")) {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={hasSelectedKb ? 0 : -1}
        aria-disabled={!hasSelectedKb}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          disabled={!hasSelectedKb}
          onChange={(event) => addFiles(event.target.files)}
        />
        <p>{hasSelectedKb ? "拖拽文件到此处，或点击选择文件" : "选择目标知识库后才能添加文件"}</p>
      </div>

      {files.length > 0 ? (
        <ul className="kb-file-list">
          {files.map((file, index) => (
            <li key={`${file.name}-${file.size}-${file.lastModified}-${index}`}>
              <span>{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
              <button type="button" className="kb-btn-icon" aria-label={`移除 ${file.name}`} onClick={() => removeFile(index)}>✕</button>
            </li>
          ))}
        </ul>
      ) : null}

      <button
        type="button"
        className="kb-upload-btn"
        disabled={!hasSelectedKb || files.length === 0 || uploadMutation.isPending}
        onClick={handleUpload}
      >
        {uploadMutation.isPending ? "上传并索引中..." : `上传到 ${selectedKb?.kb_name || "未选择知识库"} (${files.length})`}
      </button>

      {uploadMutation.error && <p className="error" role="alert">{uploadMutation.error.message}</p>}
    </div>
  );
}

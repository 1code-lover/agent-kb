/**
 * 文件功能：
 * - 文件拖拽/点击上传组件，支持多文件、进度反馈。
 */

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { importFiles } from "../../api/kb";
import { useKb } from "./KbContext";

export default function KbUpload({ onSuccess }) {
  const { selectedKbId } = useKb();
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const uploadMutation = useMutation({
    mutationFn: ({ formData, kbId }) => importFiles(formData, kbId),
    onSuccess: () => {
      setFiles([]);
      if (onSuccess) onSuccess();
    },
  });

  const addFiles = (list) => {
    setFiles((prev) => [...prev, ...Array.from(list)]);
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  const handleUpload = () => {
    if (files.length === 0) return;
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    uploadMutation.mutate({ formData, kbId: selectedKbId });
  };

  return (
    <div className="kb-upload">
      <div
        className={`kb-dropzone ${dragOver ? "drag-over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => addFiles(e.target.files)}
        />
        <p>拖拽文件到此处，或点击选择文件</p>
      </div>

      {files.length > 0 && (
        <ul className="kb-file-list">
          {files.map((f, i) => (
            <li key={i}>
              <span>{f.name} ({(f.size / 1024).toFixed(1)} KB)</span>
              <button className="kb-btn-icon" onClick={() => removeFile(i)}>✕</button>
            </li>
          ))}
        </ul>
      )}

      <button
        className="kb-upload-btn"
        disabled={files.length === 0 || uploadMutation.isPending}
        onClick={handleUpload}
      >
        {uploadMutation.isPending ? "上传中..." : `上传 (${files.length})`}
      </button>

      {uploadMutation.error && <p className="error">{uploadMutation.error.message}</p>}
      {uploadMutation.data && <p className="success">导入成功！</p>}
    </div>
  );
}

/**
 * 文件功能：
 * - 网页导入组件，支持多行 URL 输入和折叠高级参数。
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { importWeb } from "../../api/kb";
import { useKb } from "./KbContext";

export default function KbWebImport({ onSuccess }) {
  const { selectedKbId } = useKb();
  const [urls, setUrls] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [chunkSize, setChunkSize] = useState(2048);
  const [chunkOverlap, setChunkOverlap] = useState(512);

  const mutation = useMutation({
    mutationFn: (payload) => importWeb(payload),
    onSuccess: () => {
      setUrls("");
      if (onSuccess) onSuccess();
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    const urlList = urls.split("\n").map((u) => u.trim()).filter(Boolean);
    if (urlList.length === 0) return;
    mutation.mutate({ urls: urlList, chunk_size: chunkSize, chunk_overlap: chunkOverlap, kb_id: selectedKbId });
  };

  return (
    <form className="kb-web-import" onSubmit={handleSubmit}>
      <label>请输入网页 URL（每行一个）</label>
      <textarea
        rows={6}
        placeholder="https://example.com"
        value={urls}
        onChange={(e) => setUrls(e.target.value)}
      />

      <button type="button" className="kb-toggle-advanced" onClick={() => setShowAdvanced(!showAdvanced)}>
        {showAdvanced ? "收起" : "展开"}高级参数
      </button>

      {showAdvanced && (
        <div className="kb-advanced-params">
          <div className="kb-param-row">
            <label>Chunk Size</label>
            <input type="number" value={chunkSize} onChange={(e) => setChunkSize(Number(e.target.value))} min={512} max={8192} />
          </div>
          <div className="kb-param-row">
            <label>Chunk Overlap</label>
            <input type="number" value={chunkOverlap} onChange={(e) => setChunkOverlap(Number(e.target.value))} min={0} max={2048} />
          </div>
        </div>
      )}

      <button type="submit" disabled={!urls.trim() || mutation.isPending}>
        {mutation.isPending ? "导入中..." : "导入网页"}
      </button>

      {mutation.error && <p className="error">{mutation.error.message}</p>}
      {mutation.data && <p className="success">网页导入成功！</p>}
    </form>
  );
}

/**
 * 文件功能：
 * - 网页导入组件，支持多行 URL 输入和折叠高级参数，并强制绑定目标知识库。
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { importWeb } from "../../api/kb";
import { readApiData } from "../../api/response";
import { useKb } from "./KbContext";

export default function KbWebImport({ onSuccess }) {
  const { selectedKb, selectedKbId, hasSelectedKb } = useKb();
  const [urls, setUrls] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [chunkSize, setChunkSize] = useState(2048);
  const [chunkOverlap, setChunkOverlap] = useState(512);

  const mutation = useMutation({
    mutationFn: (payload) => importWeb(payload),
    onSuccess: (response) => {
      setUrls("");
      if (onSuccess) onSuccess(readApiData(response) || {});
    },
  });

  const handleSubmit = (event) => {
    event.preventDefault();
    const urlList = urls.split("\n").map((url) => url.trim()).filter(Boolean);
    if (!hasSelectedKb || urlList.length === 0) return;
    mutation.mutate({
      urls: urlList,
      chunk_size: chunkSize,
      chunk_overlap: chunkOverlap,
      kb_id: selectedKbId,
    });
  };

  return (
    <form className="kb-web-import" onSubmit={handleSubmit}>
      <section className={`kb-target-card ${hasSelectedKb ? "ready" : "missing"}`} aria-live="polite">
        <strong>{hasSelectedKb ? "当前网页导入目标" : "尚未选择目标知识库"}</strong>
        {hasSelectedKb ? (
          <>
            <span>{selectedKb.kb_name}</span>
            <code>kb_id: {selectedKbId}</code>
          </>
        ) : (
          <span>请先在左侧知识库列表中选择一个 active 知识库，或新建知识库。</span>
        )}
      </section>

      <label htmlFor="kb-web-urls">请输入网页 URL（每行一个）</label>
      <textarea
        id="kb-web-urls"
        rows={6}
        placeholder="https://example.com"
        value={urls}
        disabled={!hasSelectedKb}
        onChange={(event) => setUrls(event.target.value)}
      />

      <button
        type="button"
        className="kb-toggle-advanced"
        disabled={!hasSelectedKb}
        aria-expanded={showAdvanced}
        onClick={() => setShowAdvanced((current) => !current)}
      >
        {showAdvanced ? "收起" : "展开"}高级参数
      </button>

      {showAdvanced ? (
        <div className="kb-advanced-params">
          <div className="kb-param-row">
            <label htmlFor="kb-chunk-size">Chunk Size</label>
            <input
              id="kb-chunk-size"
              type="number"
              value={chunkSize}
              onChange={(event) => setChunkSize(Number(event.target.value))}
              min={512}
              max={8192}
            />
          </div>
          <div className="kb-param-row">
            <label htmlFor="kb-chunk-overlap">Chunk Overlap</label>
            <input
              id="kb-chunk-overlap"
              type="number"
              value={chunkOverlap}
              onChange={(event) => setChunkOverlap(Number(event.target.value))}
              min={0}
              max={2048}
            />
          </div>
        </div>
      ) : null}

      <button type="submit" disabled={!hasSelectedKb || !urls.trim() || mutation.isPending}>
        {mutation.isPending ? "导入并索引中..." : `导入到 ${selectedKb?.kb_name || "未选择知识库"}`}
      </button>

      {mutation.error && <p className="error" role="alert">{mutation.error.message}</p>}
    </form>
  );
}

/**
 * 文件功能：
 * - 支持通过 URL 批量导入网页内容到知识库。
 *
 * 执行逻辑：
 * 1. 解析多行 URL 输入并过滤空行。
 * 2. 按 chunk 参数提交导入请求。
 * 3. 展示导入结果和错误信息。
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { importWeb } from "../api/kb";

/**
 * 网页导入页面组件。
 *
 * Returns:
 * - JSX.Element: KB Web 页面 UI。
 */
export default function KbWebPage() {
  const [urlsText, setUrlsText] = useState("");
  const [chunkSize, setChunkSize] = useState(2048);
  const [chunkOverlap, setChunkOverlap] = useState(512);

  const importMutation = useMutation({
    mutationFn: (payload) => importWeb(payload)
  });

  /**
   * 提交 URL 列表执行导入。
   *
   * 输入：
   * - event: 表单提交事件。
   *
   * 输出：
   * - 无返回值，通过 mutation 异步处理请求。
   */
  const onSubmit = (event) => {
    event.preventDefault();
    const urls = urlsText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    if (urls.length === 0) {
      return;
    }
    importMutation.mutate({ urls, chunk_size: chunkSize, chunk_overlap: chunkOverlap });
  };

  return (
    <section>
      <h2>KB Web</h2>
      <form onSubmit={onSubmit}>
        <textarea
          rows={6}
          value={urlsText}
          onChange={(e) => setUrlsText(e.target.value)}
          placeholder={"每行一个 URL，例如:\nhttps://example.com/article"}
        />
        <div className="setting-row">
          <label>Chunk Size</label>
          <input type="number" value={chunkSize} onChange={(e) => setChunkSize(Number(e.target.value))} />
          <label>Chunk Overlap</label>
          <input type="number" value={chunkOverlap} onChange={(e) => setChunkOverlap(Number(e.target.value))} />
        </div>
        <button type="submit" disabled={importMutation.isPending}>
          {importMutation.isPending ? "Importing..." : "Import URLs"}
        </button>
      </form>
      {importMutation.error && <p className="error">{importMutation.error.message}</p>}
      {importMutation.data && (
        <p>
          已处理 {importMutation.data.data.urls.length} 个 URL，索引切片 {importMutation.data.data.indexed_chunks} 个。
        </p>
      )}
    </section>
  );
}

/**
 * 文件功能：
 * - 展示知识证据的最小预览结果。
 */

export default function KbEvidencePreview({ preview, loading, error }) {
  if (loading) {
    return <div className="qa-inline-tip">正在加载证据预览…</div>;
  }

  if (error) {
    return <div className="banner-info banner-danger">{error}</div>;
  }

  if (!preview) {
    return <div className="qa-inline-tip">点击证据项上的“预览”后，这里会显示最小文本预览。</div>;
  }

  const locator = preview.locator || {};
  const pageText = locator.page ? "第 " + locator.page + " 页" : "未返回页级定位";

  return (
    <section className="qa-surface-card qa-source-card">
      <div className="qa-section-head">
        <div>
          <p className="qa-section-eyebrow">证据预览</p>
          <h2>{preview.title || preview.doc_id || "未命名证据"}</h2>
        </div>
        <span className="toolbar-pill subtle">{preview.preview_type || "text_excerpt"}</span>
      </div>
      <div className="qa-summary-list">
        <div className="qa-summary-item">
          <span>知识库</span>
          <strong>{preview.kb_id || "default"}</strong>
        </div>
        <div className="qa-summary-item">
          <span>文档 ID</span>
          <strong>{preview.doc_id || "-"}</strong>
        </div>
        <div className="qa-summary-item">
          <span>定位</span>
          <strong>{pageText}</strong>
        </div>
      </div>
      <p className="qa-source-excerpt">{preview.excerpt || "未返回可预览文本。"}</p>
    </section>
  );
}

/**
 * 文件功能：
 * - 展示知识证据或资产对象的最小预览结果。
 */

function renderAssetPreview(preview) {
  const locator = preview.locator || {};
  const referencedPath = locator.referenced_path || "-";
  const occurrenceIndex =
    locator.occurrence_index === 0 || locator.occurrence_index
      ? String(locator.occurrence_index)
      : "-";

  return (
    <>
      <div className="qa-summary-list">
        <div className="qa-summary-item">
          <span>知识库</span>
          <strong>{preview.kb_id || "default"}</strong>
        </div>
        <div className="qa-summary-item">
          <span>资产 ID</span>
          <strong>{preview.asset_id || "-"}</strong>
        </div>
        <div className="qa-summary-item">
          <span>MIME</span>
          <strong>{preview.mime_type || "-"}</strong>
        </div>
        <div className="qa-summary-item">
          <span>角色</span>
          <strong>{preview.asset_role || "-"}</strong>
        </div>
        <div className="qa-summary-item">
          <span>相对路径</span>
          <strong>{preview.relative_path || preview.path || "-"}</strong>
        </div>
        <div className="qa-summary-item">
          <span>状态</span>
          <strong>{preview.status || "-"}</strong>
        </div>
      </div>
      <div className="qa-summary-list">
        <div className="qa-summary-item">
          <span>宿主文档</span>
          <strong>{preview.source_doc_relative_path || "独立资产"}</strong>
        </div>
        <div className="qa-summary-item">
          <span>引用路径</span>
          <strong>{referencedPath}</strong>
        </div>
        <div className="qa-summary-item">
          <span>出现序号</span>
          <strong>{occurrenceIndex}</strong>
        </div>
      </div>
      <p className="qa-source-excerpt">
        {preview.source_doc_relative_path
          ? "该资产来自宿主文档，可作为独立知识对象被引用与回溯。"
          : "该资产为独立导入对象，当前预览先展示基础元数据。"}
      </p>
    </>
  );
}

function renderTextPreview(preview) {
  const locator = preview.locator || {};
  const pageText = locator.page ? "第 " + locator.page + " 页" : "未返回页级定位";

  return (
    <>
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
    </>
  );
}

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

  const isAssetPreview = Boolean(preview.asset_id);
  const pillText = preview.preview_type || (isAssetPreview ? "asset_metadata" : "text_excerpt");
  const title = preview.title || preview.doc_id || preview.asset_id || "未命名证据";

  return (
    <section className="qa-surface-card qa-source-card">
      <div className="qa-section-head">
        <div>
          <p className="qa-section-eyebrow">证据预览</p>
          <h2>{title}</h2>
        </div>
        <span className="toolbar-pill subtle">{pillText}</span>
      </div>
      {isAssetPreview ? renderAssetPreview(preview) : renderTextPreview(preview)}
    </section>
  );
}

import KbEvidencePreview from "../../components/kb/KbEvidencePreview";

function formatScore(score) {
  return typeof score === "number" ? score.toFixed(3) : "-";
}

export default function SourceList({
  sources,
  evidence,
  onPreview,
  preview,
  previewLoading,
  previewError,
}) {
  const items =
    evidence.length > 0
      ? evidence
      : sources.map((item, index) => ({
          id: item.id || (item.file || "source") + "-" + index,
          title: item.file || "未命名来源",
          source: item.file || "未命名来源",
          page: item.page,
          score: item.score,
          excerpt: item.excerpt || item.text || "",
          kb_id: item.kb_id || "default",
          doc_id: item.doc_id || null,
          preview_locator: item.preview_locator || null,
          asset_id: item.asset_id || null,
        }));

  return (
    <section className="qa-surface-card qa-source-card">
      <div className="qa-section-head">
        <div>
          <p className="qa-section-eyebrow">证据</p>
          <h2>命中来源</h2>
        </div>
        <span className="toolbar-pill subtle">{items.length} 条</span>
      </div>

      {items.length === 0 ? (
        <div className="empty-block">
          当前还没有可展示的证据；发送问题后，命中的文档片段会出现在这里。
        </div>
      ) : (
        <div className="qa-source-list">
          {items.map((item, index) => (
            <article key={(item.id || item.title || "source") + "-" + index} className="qa-source-item">
              <div className="qa-source-title-row">
                <strong>{item.title || item.source || "未命名来源"}</strong>
                <span>{"score " + formatScore(item.score)}</span>
              </div>
              <p className="stack-subtle">
                {"kb_id=" + (item.kb_id || "default")}
                {item.page && item.page !== "N/A" ? " / 页码 " + item.page : ""}
              </p>
              {item.asset_id ? <p className="stack-subtle">{"关联资产：" + item.asset_id}</p> : null}
              <p className="qa-source-excerpt">{item.excerpt || "未返回摘录"}</p>
              {item.asset_id || item.doc_id || item.id ? (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => onPreview(item)}
                  disabled={previewLoading}
                >
                  {previewLoading ? "加载中" : "预览"}
                </button>
              ) : null}
            </article>
          ))}
        </div>
      )}

      <KbEvidencePreview
        preview={preview}
        loading={previewLoading}
        error={previewError}
      />
    </section>
  );
}

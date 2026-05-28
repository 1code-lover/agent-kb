export default function AgentEvidencePanel({ evidence }) {
  return (
    <section className="agent-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">Evidence</p>
          <h3>Evidence Panel</h3>
        </div>
      </div>

      {evidence.length === 0 && <div className="empty-block">No evidence returned.</div>}
      <div className="stack-list">
        {evidence.map((item) => (
          <article key={item.id} className="stack-card">
            <div className="stack-title-row">
              <strong>{item.title || item.id}</strong>
              <span>{item.score != null ? `score ${item.score}` : item.kb_id}</span>
            </div>
            <p className="stack-subtle">
              {item.source}
              {item.page && item.page !== "N/A" ? ` / p.${item.page}` : ""}
            </p>
            <p>{item.excerpt || "No excerpt"}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

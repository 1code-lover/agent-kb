export default function AgentEvidencePanel({ evidence }) {
  return (
    <section className="agent-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">证据</p>
          <h3>知识检索返回</h3>
        </div>
      </div>

      {evidence.length === 0 ? <div className="empty-block">这一轮没有返回知识证据。</div> : null}
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
            <p>{item.excerpt || "无摘要"}</p>
          </article>
        ))}
      </div>
    </section>
  );
}


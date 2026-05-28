function renderMeta(meta) {
  if (!meta) {
    return null;
  }

  const pairs = [];
  if (meta.title) pairs.push(meta.title);
  if (meta.status) pairs.push(meta.status);
  if (meta.riskLevel) pairs.push(`risk=${meta.riskLevel}`);
  if (meta.evidenceIds?.length) pairs.push(`evidence=${meta.evidenceIds.join(", ")}`);
  if (meta.reviewReason) pairs.push(`reason=${meta.reviewReason}`);

  if (pairs.length === 0) {
    return null;
  }

  return <p className="timeline-meta">{pairs.join(" / ")}</p>;
}

export default function AgentTimeline({ timeline }) {
  return (
    <section className="agent-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">Timeline</p>
          <h3>Execution Timeline</h3>
        </div>
      </div>

      <div className="timeline-list">
        {timeline.length === 0 && <div className="empty-block">No execution events yet.</div>}
        {timeline.map((item) => (
          <article key={item.seq} className={`timeline-card timeline-${item.type}`}>
            <div className="timeline-card-head">
              <span className="timeline-seq">#{item.seq}</span>
              <span className="timeline-type">{item.type}</span>
            </div>
            <p className="timeline-content">{item.content}</p>
            {renderMeta(item.meta)}
          </article>
        ))}
      </div>
    </section>
  );
}

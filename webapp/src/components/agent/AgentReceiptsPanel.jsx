function renderOutput(output) {
  if (output == null) {
    return "-";
  }
  if (typeof output === "string") {
    return output;
  }
  return JSON.stringify(output, null, 2);
}

export default function AgentReceiptsPanel({ receipts }) {
  return (
    <section className="agent-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">回执</p>
          <h3>运行细节</h3>
        </div>
      </div>

      {receipts.length === 0 ? <div className="empty-block">当前还没有工具回执。</div> : null}
      <div className="stack-list">
        {receipts.map((receipt) => (
          <article key={receipt.id} className="stack-card">
            <div className="stack-title-row">
              <strong>{receipt.tool_name}</strong>
              <span>{receipt.status}</span>
            </div>
            <p className="stack-subtle">{receipt.created_at || "-"}</p>
            <pre className="receipt-code">{renderOutput(receipt.output)}</pre>
          </article>
        ))}
      </div>
    </section>
  );
}


function defaultReason(approve) {
  return approve ? "Risk reviewed. Execution allowed." : "Execution rejected.";
}

export default function AgentApprovalPanel({ pendingActions, approvalMessage, disabled, onReview }) {
  return (
    <section className="agent-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">Approvals</p>
          <h3>Approval Panel</h3>
        </div>
      </div>

      {approvalMessage && <div className="banner-info">{approvalMessage}</div>}
      {pendingActions.length === 0 && <div className="empty-block">No pending actions.</div>}

      <div className="stack-list">
        {pendingActions.map((action) => (
          <article key={action.action_id} className="stack-card warning-card">
            <div className="stack-title-row">
              <strong>{action.command}</strong>
              <span>{action.risk_level}</span>
            </div>
            <p className="stack-subtle">
              action_id: {action.action_id} / created_at: {action.created_at}
            </p>
            <div className="action-row">
              <button
                type="button"
                className="primary-button"
                disabled={disabled}
                onClick={() => {
                  const reason = window.prompt("Approval reason", defaultReason(true)) || "";
                  onReview({ action_id: action.action_id, approve: true, reason, approver: "desktop-user" });
                }}
              >
                Approve
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={disabled}
                onClick={() => {
                  const reason = window.prompt("Reject reason", defaultReason(false)) || "";
                  onReview({ action_id: action.action_id, approve: false, reason, approver: "desktop-user" });
                }}
              >
                Reject
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

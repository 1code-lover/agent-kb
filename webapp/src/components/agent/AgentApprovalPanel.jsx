function defaultReason(approve) {
  return approve ? "风险已确认，允许执行。" : "本次操作不执行。";
}

export default function AgentApprovalPanel({ pendingActions, approvalMessage, disabled, onReview }) {
  return (
    <section className="agent-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">审批</p>
          <h3>待确认操作</h3>
        </div>
      </div>

      {approvalMessage ? <div className="banner-info">{approvalMessage}</div> : null}
      {pendingActions.length === 0 ? <div className="empty-block">当前没有待审批操作。</div> : null}

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
                  const reason = window.prompt("审批原因", defaultReason(true)) || "";
                  onReview({ action_id: action.action_id, approve: true, reason, approver: "desktop-user" });
                }}
              >
                允许执行
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={disabled}
                onClick={() => {
                  const reason = window.prompt("拒绝原因", defaultReason(false)) || "";
                  onReview({ action_id: action.action_id, approve: false, reason, approver: "desktop-user" });
                }}
              >
                拒绝
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}


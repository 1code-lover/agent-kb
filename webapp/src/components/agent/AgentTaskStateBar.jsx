const STATE_LABELS = {
  idle: "Idle",
  running: "Running",
  completed: "Completed",
  waiting_approval: "Waiting Approval",
  failed: "Failed"
};

export default function AgentTaskStateBar({
  sessionId,
  runState,
  taskGoal,
  taskState,
  approvalCount,
  currentModelLabel
}) {
  return (
    <section className="agent-statebar">
      <div className="state-pill-group">
        <div className="state-pill">
          <span>Session</span>
          <strong>{sessionId}</strong>
        </div>
        <div className={`state-pill tone-${runState}`}>
          <span>Status</span>
          <strong>{STATE_LABELS[runState] || runState}</strong>
        </div>
        <div className="state-pill">
          <span>Pending</span>
          <strong>{approvalCount}</strong>
        </div>
        <div className="state-pill">
          <span>Task State</span>
          <strong>{taskState?.status || "not started"}</strong>
        </div>
        <div className="state-pill">
          <span>Current Model</span>
          <strong>{currentModelLabel || "not selected"}</strong>
        </div>
      </div>
      <p className="state-goal">{taskGoal || "No active task yet."}</p>
    </section>
  );
}

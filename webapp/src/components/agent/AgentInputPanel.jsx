import { AGENT_MODES, buildReadFileTemplate } from "../../store/agentState";

function modeHint(mode) {
  if (mode === "read_file") {
    return "Paste a local Windows path. Example: C:\\path\\to\\file.txt";
  }
  if (mode === "run_cmd") {
    return "Low-risk commands run directly. High-risk commands enter approval.";
  }
  if (mode === "kb_search") {
    return "Ask a knowledge question against foxglove_beifen.";
  }
  return "Describe the task and let the agent route it.";
}

export default function AgentInputPanel({
  question,
  mode,
  knowledgeScope,
  disabled,
  onQuestionChange,
  onModeChange,
  onSubmit
}) {
  return (
    <section className="agent-panel agent-panel-input">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">Task Intake</p>
          <h3>Run Target</h3>
        </div>
        <div className="scope-badge">
          <span>{knowledgeScope.kb_name}</span>
          <small>{knowledgeScope.kb_id}</small>
        </div>
      </div>

      <form className="agent-form" onSubmit={onSubmit}>
        <label className="field-label" htmlFor="agent-question">
          Goal
        </label>
        <textarea
          id="agent-question"
          rows={5}
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="Describe the task for the agent, or enter a search query, file path, or command."
        />
        <p className="simple-note">{modeHint(mode)}</p>

        {mode === "read_file" && (
          <div className="helper-row">
            <button
              type="button"
              className="secondary-button"
              onClick={() => onQuestionChange(buildReadFileTemplate())}
            >
              Insert path template
            </button>
          </div>
        )}

        <div className="agent-form-row">
          <div className="mode-switcher">
            {AGENT_MODES.map((item) => (
              <button
                key={item.value}
                type="button"
                className={item.value === mode ? "mode-chip active" : "mode-chip"}
                onClick={() => onModeChange(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <button type="submit" className="primary-button" disabled={disabled}>
            {disabled ? "Running..." : "Run Task"}
          </button>
        </div>
      </form>
    </section>
  );
}

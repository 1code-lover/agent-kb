import { useRef, useState } from "react";
import { AGENT_MODES, buildReadFileTemplate } from "../../store/agentState";

function formatSkill(skillId) {
  if (skillId === "planner") return "规划";
  if (skillId === "file_context") return "文件";
  if (skillId === "safe_command") return "安全";
  if (skillId === "receipt_trace") return "回执";
  return skillId;
}

function ModeSelector({ mode, onModeChange, disabled, showAdvancedModes, onToggleAdvanced }) {
  const visibleModes = showAdvancedModes
    ? AGENT_MODES
    : AGENT_MODES.filter((item) => item.value === "agent" || item.value === "kb_search");

  return (
    <div className="mode-selector-block">
      <div className="agent-form-row mode-row-header">
        <span className="agent-mini-label">运行模式</span>
        <button type="button" className="secondary-button subtle-button" onClick={onToggleAdvanced}>
          {showAdvancedModes ? "收起高级模式" : "展开更多模式"}
        </button>
      </div>
      <div className="mode-switcher">
        {visibleModes.map((item) => (
          <button
            key={item.value}
            type="button"
            disabled={disabled}
            className={mode === item.value ? "mode-chip active" : "mode-chip"}
            onClick={() => onModeChange(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function AgentInputPanel(props) {
  const {
    question,
    mode,
    disabled,
    providerOptions,
    modelOptions,
    attachedFiles,
    enabledSkills,
    uploadBusy,
    onQuestionChange,
    onModeChange,
    onProviderChange,
    onModelChange,
    onSubmit,
    onPickLocalFiles,
    onUploadFiles,
    onRemoveAttachedFile,
  } = props;

  const [showAdvancedModes, setShowAdvancedModes] = useState(false);
  const uploadInputRef = useRef(null);

  return (
    <section className="agent-panel composer-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">任务输入</p>
          <h3>Agent 控制台</h3>
        </div>
      </div>

      <form className="agent-form" onSubmit={onSubmit}>
        <ModeSelector
          mode={mode}
          onModeChange={onModeChange}
          disabled={disabled}
          showAdvancedModes={showAdvancedModes}
          onToggleAdvanced={() => setShowAdvancedModes((current) => !current)}
        />

        <div className="agent-form-grid">
          <label className="agent-field">
            <span className="agent-mini-label">模型提供商</span>
            <select
              className="compact-select"
              value={providerOptions.value}
              disabled={providerOptions.disabled}
              onChange={(event) => onProviderChange(event.target.value)}
            >
              {providerOptions.items.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="agent-field">
            <span className="agent-mini-label">模型</span>
            <select
              className="compact-select"
              value={modelOptions.value}
              disabled={modelOptions.disabled}
              onChange={(event) => onModelChange(event.target.value)}
            >
              {modelOptions.items.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <textarea
          className="agent-chat-input compact"
          value={question}
          rows={5}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder={
            mode === "read_file"
              ? "例如：" + buildReadFileTemplate()
              : "直接输入任务。例如：帮我梳理这个知识库里有哪些核心主题。"
          }
        />

        <div className="agent-composer-helper-row">
          <div className="agent-mini-group">
            <span className="agent-mini-label">文件</span>
            <button type="button" className="secondary-button subtle-button" onClick={onPickLocalFiles}>
              选择本地文件
            </button>
            <button
              type="button"
              className="secondary-button subtle-button"
              disabled={uploadBusy}
              onClick={() => uploadInputRef.current?.click()}
            >
              {uploadBusy ? "上传中…" : "上传并导入"}
            </button>
            <input
              ref={uploadInputRef}
              type="file"
              multiple
              hidden
              onChange={(event) => {
                const files = Array.from(event.target.files || []);
                if (files.length > 0) {
                  onUploadFiles(files);
                }
                event.target.value = "";
              }}
            />
          </div>

          <div className="agent-mini-group">
            <span className="agent-mini-label">Skills</span>
            <div className="agent-skill-pills">
              {(enabledSkills || []).map((skillId) => (
                <span key={skillId} className="agent-skill-pill">
                  {formatSkill(skillId)}
                </span>
              ))}
            </div>
          </div>
        </div>

        {attachedFiles.length > 0 ? (
          <div className="attached-file-list">
            {attachedFiles.map((file) => (
              <article key={file.id} className="attached-file-card">
                <div>
                  <strong>{file.name}</strong>
                  <p className="stack-subtle">{file.path || file.source}</p>
                </div>
                <button type="button" className="secondary-button subtle-button" onClick={() => onRemoveAttachedFile(file.id)}>
                  移除
                </button>
              </article>
            ))}
          </div>
        ) : null}

        <div className="agent-form-row submit-row">
          <span className="simple-note">Agent 模式支持工具、审批与回执；知识检索模式更适合受控问答。</span>
          <button type="submit" className="primary-button" disabled={disabled || !question.trim()}>
            提交任务
          </button>
        </div>
      </form>
    </section>
  );
}

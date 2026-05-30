import { useEffect, useId, useRef, useState } from "react";
import { AGENT_MODES, buildReadFileTemplate } from "../../store/agentState";

function CompactPicker({ label, value, options, disabled, emptyLabel, onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const listboxId = useId();
  const currentOption = options.find((item) => item.value === value);

  useEffect(() => {
    function handlePointerDown(event) {
      if (!rootRef.current?.contains(event.target)) {
        setOpen(false);
      }
    }

    function handleEscape(event) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, []);

  useEffect(() => {
    if (disabled || options.length === 0) {
      setOpen(false);
    }
  }, [disabled, options.length]);

  return (
    <div ref={rootRef} className={open ? "compact-picker open" : "compact-picker"}>
      <button
        type="button"
        className="compact-picker-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-label={`${label}选择器`}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="compact-picker-label">{label}</span>
        <span className="compact-picker-value">{currentOption?.label || emptyLabel}</span>
        <span className="compact-picker-arrow" aria-hidden="true">
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open ? (
        <div id={listboxId} className="compact-picker-menu" role="listbox" aria-label={label}>
          {options.map((item) => (
            <button
              key={item.value}
              type="button"
              role="option"
              aria-selected={item.value === value}
              className={item.value === value ? "compact-picker-item active" : "compact-picker-item"}
              onClick={() => {
                onChange(item.value);
                setOpen(false);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function formatSkill(skillId) {
  if (skillId === "planner") return "规划";
  if (skillId === "file_context") return "文件";
  if (skillId === "safe_command") return "安全";
  if (skillId === "receipt_trace") return "回执";
  return skillId;
}

export default function AgentInputPanel({
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
  onRemoveAttachedFile
}) {
  const [showAdvancedModes, setShowAdvancedModes] = useState(false);
  const uploadInputRef = useRef(null);

  return (
    <section className="agent-composer-shell">
      <form className="agent-composer-bar" onSubmit={onSubmit}>
        <textarea
          className="agent-chat-input compact"
          value={question}
          rows={3}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="直接输入任务。例如：帮我梳理这个项目下一步该怎么做。"
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
              {uploadBusy ? "上传中" : "上传并导入"}
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
          <div className="agent-attachment-strip">
            {attachedFiles.map((file) => (
              <span key={file.id || file.path || file.name} className="agent-attachment-chip">
                <span className="agent-attachment-name">{file.name}</span>
                <span className="agent-attachment-meta">{file.status === "imported" ? "已入库" : "本地文件"}</span>
                <button type="button" className="agent-attachment-remove" onClick={() => onRemoveAttachedFile(file.id)}>
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}

        <div className="agent-composer-bottom">
          <div className="agent-composer-left">
            <button
              type="button"
              className="secondary-button subtle-button"
              aria-expanded={showAdvancedModes}
              aria-label="切换工具模式"
              onClick={() => setShowAdvancedModes((current) => !current)}
            >
              工具
            </button>
            {showAdvancedModes ? (
              <div className="mode-switcher inline-mode-switcher">
                {AGENT_MODES.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    className={item.value === mode ? "mode-chip active" : "mode-chip"}
                    onClick={() => {
                      onModeChange(item.value);
                      if (item.value === "read_file" && !question.trim()) {
                        onQuestionChange(buildReadFileTemplate());
                      }
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <div className="agent-composer-right agent-composer-right-stacked">
            <CompactPicker
              label="供应商"
              value={providerOptions.value}
              options={providerOptions.items}
              disabled={providerOptions.disabled}
              emptyLabel="未配置"
              onChange={onProviderChange}
            />

            <CompactPicker
              label="模型"
              value={modelOptions.value}
              options={modelOptions.items}
              disabled={modelOptions.disabled}
              emptyLabel="未配置"
              onChange={onModelChange}
            />

            <button type="submit" className="primary-button agent-send-button" disabled={disabled}>
              {disabled ? "处理中" : "发送"}
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}


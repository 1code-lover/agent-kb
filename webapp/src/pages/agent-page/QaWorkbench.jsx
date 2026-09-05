import { Link } from "../../router";
import { buildKnowledgeWorkspaceLink } from "../../domain/kbNavigation";
import {
  AGENT_EXPERIENCES,
  CHAT_REQUEST_LIMITS,
  CHAT_RESPONSE_MODES,
  buildExperienceSummary,
  experienceRequiresKb,
} from "../../domain/agentExperience";
import KnowledgeScopeSelector from "./KnowledgeScopeSelector.jsx";
import QaConversation from "./QaConversation.jsx";
import SourceList from "./SourceList.jsx";

export default function QaWorkbench(props) {
  const {
    experience,
    selectedKb,
    selectedKbId,
    kbList,
    kbLoading,
    onSelectKb,
    currentModelLabel,
    modelHealthSummary,
    modelReady,
    question,
    onQuestionChange,
    requestOptions,
    requestOptionsLoading,
    onRequestOptionsChange,
    onRequestOptionsReset,
    onSubmit,
    messages,
    sources,
    evidence,
    pendingQuestion,
    error,
    chatNotice,
    historyLoading,
    chatBusy,
    preview,
    previewLoading,
    previewError,
    onPreviewEvidence,
  } = props;

  const summary = buildExperienceSummary({ experience, selectedKb });
  const requiresKbSelection = experienceRequiresKb(experience);
  const submitDisabled =
    chatBusy ||
    !question.trim() ||
    !modelReady ||
    (requiresKbSelection && !selectedKbId);

  return (
    <div className="qa-page-shell">
      <header className="qa-hero-card">
        <div className="qa-hero-content">
          <div className="qa-hero-copy">
            <span className="qa-eyebrow">问答工作台</span>
            <h1>先问答，再决定是否进入 Agent 高级模式</h1>
            <p>{summary}</p>
          </div>
          <div className="qa-hero-meta">
            <span className="qa-badge">{"当前模型：" + currentModelLabel}</span>
            <span className="qa-badge">{modelHealthSummary?.chipLabel || "状态未知"}</span>
            <span className="qa-badge">
              {"当前范围：" + (requiresKbSelection ? (selectedKb?.kb_name || "未选择知识库") : "Agent 运行时")}
            </span>
            <span className="qa-badge">{"可用知识库：" + kbList.length + " 个"}</span>
          </div>
          <p className="qa-inline-tip">{modelHealthSummary?.actionHint || "问答会沿用当前模型配置。"}</p>
        </div>
        <div className="qa-hero-actions">
          <Link className="secondary-button link-button" to={buildKnowledgeWorkspaceLink(selectedKbId)}>
            管理知识库
          </Link>
          <Link className="secondary-button link-button" to="/models">
            模型配置
          </Link>
        </div>
      </header>

      <div className="qa-layout">
        <div className="qa-main-column">
          {requiresKbSelection ? (
            <KnowledgeScopeSelector
              experience={experience}
              selectedKbId={selectedKbId}
              selectedKb={selectedKb}
              kbList={kbList}
              kbLoading={kbLoading}
              onSelectKb={onSelectKb}
            />
          ) : null}

          <section className="qa-surface-card qa-compose-card">
            <div className="qa-section-head">
              <div>
                <p className="qa-section-eyebrow">立即提问</p>
                <h2>{experience === "knowledge" ? "知识库定向问答" : "基础问答"}</h2>
              </div>
              <span className="toolbar-pill subtle">{modelReady ? currentModelLabel : "尚未配置模型"}</span>
            </div>

            <form className="qa-compose-form" onSubmit={onSubmit}>
              <textarea
                className="qa-compose-input"
                rows={5}
                value={question}
                onChange={(event) => onQuestionChange(event.target.value)}
                placeholder={
                  experience === "knowledge"
                    ? "例如：这份知识库里对实习要求是怎么描述的？"
                    : "例如：帮我总结一下这个知识库里有哪些主题。"
                }
              />
              <div className="qa-compose-actions">
                <div className="qa-inline-tip">
                  {requiresKbSelection && !selectedKbId
                    ? "请先在上方选择知识库后再发送问题。"
                    : "问答会保留独立会话历史，方便你连续追问。"}
                </div>
                <button type="submit" className="primary-button" disabled={submitDisabled}>
                  {chatBusy ? "回答生成中…" : "发送问题"}
                </button>
              </div>
            </form>

            {chatNotice ? <div className="banner-info">{chatNotice}</div> : null}
            {error ? <div className="banner-info banner-danger">{error}</div> : null}
            {!modelReady ? (
              <div className="banner-info">
                还没有可用模型，请先前往模型配置页完成提供商与模型选择。
              </div>
            ) : null}
          </section>

          <section className="qa-surface-card qa-compose-card">
            <div className="qa-section-head">
              <div>
                <p className="qa-section-eyebrow">请求级 RAG 参数</p>
                <h2>当前问答临时覆盖</h2>
              </div>
              <button
                type="button"
                className="secondary-button subtle-button"
                onClick={onRequestOptionsReset}
                disabled={requestOptionsLoading}
              >
                恢复全局默认
              </button>
            </div>

            <div className="qa-inline-tip">
              这些参数只作用于当前问答工作台，不会写回系统设置页面；发送问题时会随本次 `QueryRequest` 一起提交。
            </div>

            <div className="qa-summary-list">
              <label className="qa-summary-item">
                <span>Top K</span>
                <input
                  type="number"
                  min={CHAT_REQUEST_LIMITS.topKMin}
                  max={CHAT_REQUEST_LIMITS.topKMax}
                  value={requestOptions?.top_k ?? ""}
                  onChange={(event) => onRequestOptionsChange((current) => ({
                    ...current,
                    top_k: event.target.value,
                  }))}
                />
              </label>
              <label className="qa-summary-item">
                <span>Response Mode</span>
                <select
                  value={requestOptions?.response_mode || ""}
                  onChange={(event) => onRequestOptionsChange((current) => ({
                    ...current,
                    response_mode: event.target.value,
                  }))}
                >
                  <option value="">跟随当前全局设置</option>
                  {CHAT_RESPONSE_MODES.map((mode) => (
                    <option key={mode} value={mode}>
                      {mode}
                    </option>
                  ))}
                </select>
              </label>
              <label className="qa-summary-item">
                <span>Use Reranker</span>
                <input
                  type="checkbox"
                  checked={Boolean(requestOptions?.use_reranker)}
                  onChange={(event) => onRequestOptionsChange((current) => ({
                    ...current,
                    use_reranker: event.target.checked,
                  }))}
                />
              </label>
              <label className="qa-summary-item">
                <span>Top N</span>
                <input
                  type="number"
                  min={CHAT_REQUEST_LIMITS.topNMin}
                  max={CHAT_REQUEST_LIMITS.topNMax}
                  value={requestOptions?.top_n ?? ""}
                  onChange={(event) => onRequestOptionsChange((current) => ({
                    ...current,
                    top_n: event.target.value,
                  }))}
                />
              </label>
              <label className="qa-summary-item">
                <span>Reranker Model</span>
                <input
                  type="text"
                  maxLength={CHAT_REQUEST_LIMITS.rerankerModelMaxLength}
                  value={requestOptions?.reranker_model ?? ""}
                  onChange={(event) => onRequestOptionsChange((current) => ({
                    ...current,
                    reranker_model: event.target.value,
                  }))}
                  placeholder="例如：bge-reranker-v2-m3"
                />
              </label>
            </div>
          </section>

          <QaConversation
            messages={messages}
            pendingQuestion={pendingQuestion}
            historyLoading={historyLoading}
            chatBusy={chatBusy}
          />
        </div>

        <aside className="qa-side-column">
          <section className="qa-surface-card qa-summary-card">
            <div className="qa-section-head">
              <div>
                <p className="qa-section-eyebrow">当前状态</p>
                <h2>工作台概览</h2>
              </div>
            </div>
            <div className="qa-summary-list">
              <div className="qa-summary-item">
                <span>体验模式</span>
                <strong>{AGENT_EXPERIENCES.find((item) => item.value === experience)?.label}</strong>
              </div>
              <div className="qa-summary-item">
                <span>模型状态</span>
                <strong>{modelHealthSummary?.title || (modelReady ? "已就绪" : "待配置")}</strong>
              </div>
              <div className="qa-summary-item">
                <span>健康详情</span>
                <strong>{modelHealthSummary?.detail || (modelReady ? "最近未发现异常" : "请先配置模型")}</strong>
              </div>
              <div className="qa-summary-item">
                <span>切换提示</span>
                <strong>{modelHealthSummary?.transitionLabel || modelHealthSummary?.actionHint || "暂无自动切换"}</strong>
              </div>
              <div className="qa-summary-item">
                <span>知识库范围</span>
                <strong>{requiresKbSelection ? (selectedKb?.kb_name || "未选择") : "Agent 运行时"}</strong>
              </div>
            </div>
          </section>

          <SourceList
            sources={sources}
            evidence={evidence}
            onPreview={onPreviewEvidence}
            preview={preview}
            previewLoading={previewLoading}
            previewError={previewError}
          />
        </aside>
      </div>
    </div>
  );
}

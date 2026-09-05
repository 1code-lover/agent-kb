function formatMessageTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function QaConversation({
  messages,
  pendingQuestion,
  historyLoading,
  chatBusy,
}) {
  const hasMessages = (messages || []).length > 0;

  return (
    <section className="qa-surface-card qa-conversation-card">
      <div className="qa-section-head">
        <div>
          <p className="qa-section-eyebrow">会话记录</p>
          <h2>问答线程</h2>
        </div>
        {historyLoading ? <span className="toolbar-pill subtle">正在同步历史…</span> : null}
      </div>

      <div className="qa-conversation-thread">
        {!hasMessages && !pendingQuestion ? (
          <div className="empty-block">还没有对话记录，先输入一个问题试试。</div>
        ) : null}

        {(messages || []).map((item, index) => {
          const role = item.role === "user" ? "user" : "assistant";
          return (
            <article
              key={item.id || role + "-" + index}
              className={
                role === "user"
                  ? "qa-message-row qa-message-row-user"
                  : "qa-message-row qa-message-row-assistant"
              }
            >
              <div className={role === "user" ? "qa-message qa-message-user" : "qa-message qa-message-assistant"}>
                <div className="qa-message-meta">
                  <span>{role === "user" ? "你" : "助手"}</span>
                  <span>{formatMessageTime(item.created_at)}</span>
                </div>
                <div className="qa-message-body">{item.content}</div>
              </div>
            </article>
          );
        })}

        {pendingQuestion ? (
          <>
            <article className="qa-message-row qa-message-row-user">
              <div className="qa-message qa-message-user pending">
                <div className="qa-message-meta">
                  <span>你</span>
                  <span>刚刚</span>
                </div>
                <div className="qa-message-body">{pendingQuestion}</div>
              </div>
            </article>
            <article className="qa-message-row qa-message-row-assistant">
              <div className="qa-message qa-message-assistant pending">
                <div className="qa-message-meta">
                  <span>助手</span>
                  <span>{chatBusy ? "生成中" : "排队中"}</span>
                </div>
                <div className="qa-message-body">正在检索并组织回答，请稍候…</div>
              </div>
            </article>
          </>
        ) : null}
      </div>
    </section>
  );
}

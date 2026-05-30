function getBubbleType(type) {
  if (type === "user") return "user";
  if (type === "assistant") return "assistant";
  if (type === "error") return "error";
  return "system";
}

function getRoleLabel(type) {
  if (type === "user") return "你";
  if (type === "assistant") return "Agent";
  if (type === "error") return "错误";
  return "系统";
}

export default function AgentTimeline({ timeline }) {
  const normalizedTimeline = timeline.filter((item) => item?.content);

  return (
    <section className="agent-chat-thread">
      {normalizedTimeline.length === 0 ? (
        <div className="chat-row chat-row-assistant">
          <article className="chat-bubble chat-bubble-assistant">
            <div className="chat-bubble-label">Agent</div>
            <div className="chat-bubble-content">直接输入任务就行，我会按当前模型开始处理。</div>
          </article>
        </div>
      ) : null}

      {normalizedTimeline.map((item) => {
        const bubbleType = getBubbleType(item.type);
        return (
          <div
            key={item.seq}
            className={bubbleType === "user" ? "chat-row chat-row-user" : "chat-row chat-row-assistant"}
          >
            <article className={`chat-bubble chat-bubble-${bubbleType}`}>
              <div className="chat-bubble-label">{getRoleLabel(bubbleType)}</div>
              <div className="chat-bubble-content">{item.content}</div>
            </article>
          </div>
        );
      })}
    </section>
  );
}


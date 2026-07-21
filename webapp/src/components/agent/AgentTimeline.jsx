function getBubbleType(type) {
  if (type === "user") return "user";
  if (type === "assistant") return "assistant";
  if (type === "error") return "error";
  return "system";
}

function getRoleLabel(type) {
  if (type === "user") return "你";
  if (type === "assistant") return "助手";
  if (type === "error") return "错误";
  return "状态";
}

export default function AgentTimeline({ timeline }) {
  const normalizedTimeline = timeline || [];

  return (
    <section className="agent-panel timeline-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">执行过程</p>
          <h3>任务时间线</h3>
        </div>
      </div>

      {normalizedTimeline.length === 0 ? (
        <div className="empty-block">还没有任务记录，提交一次 Agent 请求后会在这里显示过程。</div>
      ) : null}

      <div className="timeline-list">
        {normalizedTimeline.map((item) => {
          const bubbleType = getBubbleType(item.type);
          return (
            <div
              key={item.seq}
              className={bubbleType === "user" ? "chat-row chat-row-user" : "chat-row chat-row-assistant"}
            >
              <article className={"chat-bubble chat-bubble-" + bubbleType}>
                <div className="chat-bubble-label">{getRoleLabel(bubbleType)}</div>
                <div className="chat-bubble-content">{item.content}</div>
              </article>
            </div>
          );
        })}
      </div>
    </section>
  );
}

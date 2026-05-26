/**
 * 文件功能：
 * - Agent 工作台主页面，承载任务输入、执行时间线和上下文面板。
 *
 * 执行逻辑：
 * 1. 默认使用 Agent 模式执行任务，并维护 runState。
 * 2. 提交任务后同步更新时间线、回执和待审批动作。
 * 3. 审批动作完成后刷新右侧上下文面板信息。
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { queryChat } from "../api/chat";
import { approveAgentAction, getAgentReceipts, getPendingActions, runAgent } from "../api/agent";
import useAppStore from "../store/appStore";

/**
 * Agent 工作台页面组件。
 *
 * Returns:
 * - JSX.Element: 工作台 UI。
 */
export default function QueryPage() {
  const sessionId = useAppStore((s) => s.sessionId);
  const taskGoal = useAppStore((s) => s.taskGoal);
  const runState = useAppStore((s) => s.runState);
  const timeline = useAppStore((s) => s.timeline);
  const plan = useAppStore((s) => s.plan);
  const evidence = useAppStore((s) => s.evidence);
  const taskState = useAppStore((s) => s.taskState);
  const pendingActions = useAppStore((s) => s.pendingActions);
  const approvalMessage = useAppStore((s) => s.approvalMessage);
  const setTaskGoal = useAppStore((s) => s.setTaskGoal);
  const setRunState = useAppStore((s) => s.setRunState);
  const setPendingActions = useAppStore((s) => s.setPendingActions);
  const setApprovalMessage = useAppStore((s) => s.setApprovalMessage);
  const appendTimeline = useAppStore((s) => s.appendTimeline);
  const appendTimelineBatch = useAppStore((s) => s.appendTimelineBatch);
  const hydrateFromAgentRun = useAppStore((s) => s.hydrateFromAgentRun);

  const [question, setQuestion] = useState("");
  const [useAgentMode, setUseAgentMode] = useState(true);
  const [agentReceipts, setAgentReceipts] = useState([]);

  const askMutation = useMutation({
    mutationFn: (payload) => queryChat(payload),
    onSuccess: (res) => {
      const data = res.data;
      appendTimeline({ type: "user", content: question });
      appendTimeline({ type: "assistant", content: data.answer });
      setQuestion("");
    }
  });

  const agentMutation = useMutation({
    mutationFn: (payload) => runAgent(payload),
    onSuccess: async (res) => {
      const data = res.data;
      hydrateFromAgentRun(question, data);

      const receiptsRes = await getAgentReceipts(sessionId, 20);
      setAgentReceipts(receiptsRes.data.receipts || []);

      const pendingRes = await getPendingActions(sessionId);
      setPendingActions(pendingRes.data.pending_actions || []);

      setRunState((pendingRes.data.pending_actions || []).length > 0 ? "waiting_approval" : "completed");
      setQuestion("");
      setTaskGoal("");
    },
    onError: () => {
      setRunState("failed");
    }
  });

  const approvalMutation = useMutation({
    mutationFn: (payload) => approveAgentAction(payload),
    onSuccess: async (res) => {
      const data = res.data;
      setApprovalMessage(`审批结果：${data.status}`);
      appendTimeline({
        type: "approval",
        content: `命令审批：${data.status}，原因：${data.review_reason || "无"}`
      });
      const receiptsRes = await getAgentReceipts(sessionId, 20);
      setAgentReceipts(receiptsRes.data.receipts || []);
      const pendingRes = await getPendingActions(sessionId);
      setPendingActions(pendingRes.data.pending_actions || []);
      setRunState((pendingRes.data.pending_actions || []).length > 0 ? "waiting_approval" : "running");
    }
  });

  /**
   * 提交任务并触发执行链路。
   *
   * 输入：
   * - event: 表单提交事件。
   *
   * 执行逻辑：
   * 1. 校验输入不为空。
    * 2. 记录任务目标并写入时间线。
   * 3. Agent 模式调用 runAgent；普通模式调用 queryChat。
   *
   * 输出：
   * - 无返回值，通过 mutation 更新页面状态。
   */
  const onSubmit = (event) => {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }
    setTaskGoal(question.trim());
    setRunState("running");
    appendTimelineBatch([
      { type: "task", content: `任务目标：${question.trim()}` },
      { type: "status", content: "任务开始执行" }
    ]);
    if (useAgentMode) {
      agentMutation.mutate({ question, session_id: sessionId, mode: "auto" });
    } else {
      askMutation.mutate({ question, session_id: sessionId });
    }
  };

  /**
   * 渲染回执输出内容。
   *
   * 输入：
   * - receipt(object): 单条执行回执。
   *
   * 输出：
   * - JSX.Element: 格式化后的回执展示节点。
   */
  const renderReceiptOutput = (receipt) => {
    const output = receipt.output;
    if (receipt.tool_name === "run_cmd_approval" && output && typeof output === "object") {
      return (
        <div className="audit-log">
          <div>审批结果：{receipt.status}</div>
          <div>审批人：{receipt.input?.approver || "unknown"}</div>
          <div>审批理由：{output.review_reason || "无"}</div>
          <div>说明：{output.message || "-"}</div>
          <div>时间：{receipt.created_at || "-"}</div>
        </div>
      );
    }
    return <div className="receipt-output">{typeof output === "string" ? output : JSON.stringify(output)}</div>;
  };

  const isPending = askMutation.isPending || agentMutation.isPending;

  return (
    <section className="workspace-page">
      <header className="workspace-header">
        <div>
          <h2>Agent Workspace</h2>
          <p className="workspace-meta">
            Session: {sessionId} | 状态: <strong>{runState}</strong>
          </p>
        </div>
        <div className="setting-row">
          <label>Agent 模式</label>
          <input type="checkbox" checked={useAgentMode} onChange={(e) => setUseAgentMode(e.target.checked)} />
        </div>
      </header>

      <form onSubmit={onSubmit} className="query-form">
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="描述你的开发任务目标..." />
        <button type="submit" disabled={isPending}>
          {isPending ? "Running..." : "Run Task"}
        </button>
      </form>
      {taskGoal && <p className="workspace-goal">当前目标：{taskGoal}</p>}
      {askMutation.error && <p className="error">{askMutation.error.message}</p>}
      {agentMutation.error && <p className="error">{agentMutation.error.message}</p>}

      <div className="workspace-layout">
        <div className="workspace-timeline">
          <h3>执行时间线</h3>
          {timeline.length === 0 && <p>暂无执行事件，先输入一个任务目标。</p>}
          {timeline.map((item) => (
            <div key={item.seq} className={`message ${item.type}`}>
              <div className="role">
                #{item.seq} / {item.type}
              </div>
              <div>{item.content}</div>
              {item.meta && (
                <div className="agent-steps">
                  <span>{item.meta.title || item.meta.name}</span>
                  {item.meta.status && <span> / {item.meta.status}</span>}
                  {item.meta.riskLevel && <span> / risk: {item.meta.riskLevel}</span>}
                  {item.meta.evidenceIds?.length > 0 && <span> / evidence: {item.meta.evidenceIds.join(", ")}</span>}
                </div>
              )}
            </div>
          ))}
        </div>

        <aside className="receipt-panel">
          <h3>智能知识体上下文</h3>
          {taskState && (
            <div className="context-block">
              <h4>任务状态</h4>
              <p>
                {taskState.status} / 待审批 {taskState.pending_approval_count || 0}
              </p>
            </div>
          )}
          <div className="context-block">
            <h4>执行计划</h4>
            {plan.length === 0 && <p>暂无计划</p>}
            {plan.map((item) => (
              <div key={item.id} className={`plan-item ${item.status}`}>
                <span>{item.title}</span>
                <strong>{item.status}</strong>
              </div>
            ))}
          </div>
          {approvalMessage && <p>{approvalMessage}</p>}
          {pendingActions.length > 0 && (
            <div className="context-block">
              <h4>待审批命令</h4>
              {pendingActions.map((action) => (
                <div key={action.action_id} className="pending-action">
                  <div>
                    <strong>{action.command}</strong>
                  </div>
                  <div>风险等级：{action.risk_level}</div>
                  <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                    <button
                      disabled={approvalMutation.isPending}
                      onClick={() => {
                        const reason = window.prompt("请输入批准理由（可选）", "确认安全，允许执行") || "";
                        approvalMutation.mutate({
                          action_id: action.action_id,
                          approve: true,
                          reason,
                          approver: "desktop-user"
                        });
                      }}
                    >
                      批准
                    </button>
                    <button
                      disabled={approvalMutation.isPending}
                      onClick={() => {
                        const reason = window.prompt("请输入拒绝理由", "命令风险较高，拒绝执行") || "";
                        approvalMutation.mutate({
                          action_id: action.action_id,
                          approve: false,
                          reason,
                          approver: "desktop-user"
                        });
                      }}
                    >
                      拒绝
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="context-block">
            <h4>知识证据</h4>
            {evidence.length === 0 && <p>暂无证据</p>}
            {evidence.map((item) => (
              <div key={item.id} className="evidence-item">
                <div>
                  <strong>{item.id}</strong> / {item.title}
                </div>
                <div className="evidence-meta">
                  {item.source} {item.page && item.page !== "N/A" ? `/ p.${item.page}` : ""}
                </div>
                <p>{item.excerpt || "无摘要"}</p>
              </div>
            ))}
          </div>
          <h4>工具回执</h4>
          {agentReceipts.length === 0 && <p>暂无回执</p>}
          {agentReceipts.map((receipt) => (
            <div key={receipt.id} className="receipt-item">
              <div>
                <strong>{receipt.tool_name}</strong> / {receipt.status}
              </div>
              {renderReceiptOutput(receipt)}
            </div>
          ))}
        </aside>
      </div>
    </section>
  );
}

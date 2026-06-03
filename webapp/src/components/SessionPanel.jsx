/**
 * 文件功能：
 * - 左栏会话列表组件，显示历史会话并支持新建会话。
 *
 * 执行逻辑：
 * 1. 从 appStore 读取会话列表。
 * 2. 点击会话切换当前 sessionId。
 * 3. 新建会话时生成唯一 ID。
 */

import { useState } from "react";
import useAppStore from "../store/appStore";

/**
 * 功能：
 * 生成简单的唯一 ID
 *
 * 输出：
 * - string: 唯一标识符
 */
function generateId() {
  return "session-" + Date.now() + "-" + Math.random().toString(36).substr(2, 9);
}

/**
 * 功能：
 * 会话列表面板组件
 *
 * 输出：
 * - JSX.Element: 会话列表 UI
 */
export default function SessionPanel() {
  const sessionId = useAppStore((s) => s.sessionId);
  const setSessionId = useAppStore((s) => s.setSessionId);
  const resetWorkspace = useAppStore((s) => s.resetWorkspace);

  const [sessions, setSessions] = useState([
    { id: "desktop-default", title: "默认会话", time: new Date().toLocaleTimeString() }
  ]);

  /**
   * 功能：
   * 创建新会话
   *
   * 执行逻辑：
   * 1. 生成新会话 ID
   * 2. 添加到会话列表
   * 3. 切换到新会话
   * 4. 重置工作台状态
   */
  const handleNewSession = () => {
    const newId = generateId();
    const newSession = {
      id: newId,
      title: `会话 ${sessions.length + 1}`,
      time: new Date().toLocaleTimeString()
    };
    setSessions((prev) => [newSession, ...prev]);
    setSessionId(newId);
    resetWorkspace();
  };

  /**
   * 功能：
   * 切换到指定会话
   *
   * 输入：
   * - id(string): 目标会话 ID
   *
   * 执行逻辑：
   * 1. 更新 sessionId
   * 2. 重置工作台状态（后续可加载历史数据）
   */
  const handleSwitchSession = (id) => {
    setSessionId(id);
    resetWorkspace();
  };

  return (
    <div className="session-panel">
      <h3>会话列表</h3>
      <div className="session-list">
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`session-item ${session.id === sessionId ? "active" : ""}`}
            onClick={() => handleSwitchSession(session.id)}
          >
            <div className="session-title">{session.title}</div>
            <div className="session-time">{session.time}</div>
          </div>
        ))}
      </div>
      <button className="new-session-btn" onClick={handleNewSession}>
        + 新建会话
      </button>
    </div>
  );
}

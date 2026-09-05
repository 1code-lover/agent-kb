from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_PAGE = REPO_ROOT / "webapp" / "src" / "pages" / "AgentPage.jsx"
CHAT_WORKSPACE_HOOK = REPO_ROOT / "webapp" / "src" / "pages" / "useAgentChatWorkspace.js"
QA_WORKBENCH = REPO_ROOT / "webapp" / "src" / "pages" / "agent-page" / "QaWorkbench.jsx"
WEBAPP_DEV_SERVER = REPO_ROOT / "webapp" / "scripts" / "dev-server.mjs"
VITE_CONFIG = REPO_ROOT / "webapp" / "vite.config.js"


def test_agent_page_threads_chat_notice_into_qa_workbench() -> None:
    """QaWorkbench 渲染 chatNotice 横幅时，外层页面必须显式透传该 prop。"""
    content = AGENT_PAGE.read_text(encoding="utf-8")

    assert "chatNotice={chatWorkspace.chatNotice}" in content
    assert "useAgentChatWorkspace" in content
    assert "resolveKnowledgeScope" in content
    assert "knowledge_scope: resolvedKnowledgeScope" in content
    assert "selectedKbId || knowledgeScope?.kb_id || DEFAULT_KNOWLEDGE_SCOPE.kb_id" not in content


def test_agent_page_preview_uses_evidence_kb_scope_when_available() -> None:
    """证据预览应优先使用证据自带 kb_id，避免切换选中知识库后误打到错误范围。"""
    content = CHAT_WORKSPACE_HOOK.read_text(encoding="utf-8")

    assert "const targetKbId = item?.kb_id || selectedKbId;" in content
    assert "previewItem(item, targetKbId)" in content


def test_qa_workbench_keeps_kb_selector_and_submit_guard_for_kb_scoped_modes() -> None:
    """需要 KB 的体验模式必须同时保留范围选择器与发送禁用保护。"""
    content = QA_WORKBENCH.read_text(encoding="utf-8")

    assert "const requiresKbSelection = experienceRequiresKb(experience);" in content
    assert "{requiresKbSelection ? (" in content
    assert "<KnowledgeScopeSelector" in content
    assert "(requiresKbSelection && !selectedKbId)" in content
    assert 'disabled={submitDisabled}' in content


def test_qa_workbench_renders_notice_and_error_banners_independently() -> None:
    """history notice 与 query error 需要独立渲染，避免其中一个覆盖另一个。"""
    content = QA_WORKBENCH.read_text(encoding="utf-8")

    assert '{chatNotice ? <div className="banner-info">{chatNotice}</div> : null}' in content
    assert '{error ? <div className="banner-info banner-danger">{error}</div> : null}' in content


def test_chat_workspace_keeps_local_fallback_until_history_catches_up() -> None:
    """history 返回旧快照时，工作台不应直接覆盖 query 成功后的本地 fallback 消息。"""
    content = CHAT_WORKSPACE_HOOK.read_text(encoding="utf-8")

    assert "optimisticHistoryResult" in content
    assert "resolveHistoryMessages({" in content
    assert "historyIncludesOptimisticResult({" in content


def test_chat_workspace_clears_messages_when_session_scope_changes() -> None:
    """切换 session / KB 范围时应立即清空旧消息，避免上一知识库问答短暂残留。"""
    content = CHAT_WORKSPACE_HOOK.read_text(encoding="utf-8")

    assert "setChatMessages([]);" in content
    assert "}, [chatSessionId, experience]);" in content


def test_webapp_dev_server_uses_inline_vite_config_and_aliases_for_broken_windows_node_modules() -> None:
    """Windows dev smoke 应固定 webapp root，并对关键依赖做 alias，绕开当前安装态解析漂移。"""
    content = WEBAPP_DEV_SERVER.read_text(encoding="utf-8")

    assert "createServer({" in content
    assert "configFile: false" in content
    assert 'root: webappRoot' in content
    assert 'base: "./"' in content
    assert 'esbuild: {' in content
    assert 'jsx: "automatic"' in content
    assert 'jsxImportSource: "react"' in content
    assert 'resolveNodeModuleEntry(relativePath)' in content
    assert 'const alias = [' in content
    assert '{ find: "react/jsx-dev-runtime", replacement: resolveNodeModuleEntry("react/jsx-dev-runtime.js") }' in content
    assert '{ find: "react/jsx-runtime", replacement: resolveNodeModuleEntry("react/jsx-runtime.js") }' in content
    assert '{ find: "react-dom/client", replacement: resolveNodeModuleEntry("react-dom/client.js") }' in content
    assert '{ find: "@tanstack/react-query", replacement: resolveNodeModuleEntry("@tanstack/react-query/build/modern/index.js") }' in content
    assert '{ find: "@tanstack/query-core", replacement: resolveNodeModuleEntry("@tanstack/query-core/build/modern/index.js") }' in content
    assert '{ find: "zustand", replacement: resolveNodeModuleEntry("zustand/esm/index.mjs") }' in content
    assert '{ find: "zustand/vanilla", replacement: resolveNodeModuleEntry("zustand/esm/vanilla.mjs") }' in content
    assert 'replacement: resolveNodeModuleEntry("use-sync-external-store/shim/with-selector.js")' in content
    assert 'optimizeDeps: {' in content
    assert 'noDiscovery: true' in content
    assert 'include: []' in content
    assert 'strictPort: true' in content


def test_vite_config_uses_kb_webapp_env_defaults() -> None:
    """直接走 vite 配置时，也应复用 KB_WEBAPP_HOST/PORT 契约，避免与 helper 漂移。"""
    content = VITE_CONFIG.read_text(encoding="utf-8")

    assert 'loadEnv' in content
    assert 'KB_WEBAPP_HOST' in content
    assert 'KB_WEBAPP_PORT' in content
    assert 'const host = env.KB_WEBAPP_HOST || "127.0.0.1";' in content
    assert 'const port = Number(env.KB_WEBAPP_PORT || "5173");' in content

/**
 * 文件功能：
 * - 知识库统一管理页面，集成显式知识库选择、文档列表、文件上传和网页导入。
 */

import { useState } from "react";
import { KbProvider, useKb } from "../components/kb/KbContext";
import KbSidebar from "../components/kb/KbSidebar";
import KbDocumentList from "../components/kb/KbDocumentList";
import KbUpload from "../components/kb/KbUpload";
import KbWebImport from "../components/kb/KbWebImport";

const TABS = [
  { key: "docs", label: "文档列表" },
  { key: "upload", label: "文件上传" },
  { key: "web", label: "网页导入" },
];

function buildImportNotice(result, sourceLabel) {
  const itemCount = Array.isArray(result.files)
    ? result.files.length
    : (Array.isArray(result.urls) ? result.urls.length : 0);
  const indexedChunks = Number(result.indexed_chunks || 0);
  return {
    kbId: result.kb_id,
    message: `${sourceLabel}成功：目标 kb_id=${result.kb_id}，导入 ${itemCount} 项，生成 ${indexedChunks} 个索引分块。`,
  };
}

function KnowledgeContent() {
  const { selectedKbId, selectedKb, hasSelectedKb } = useKb();
  const [tab, setTab] = useState("docs");
  const [notice, setNotice] = useState(null);

  const handleImportSuccess = (result, sourceLabel) => {
    setNotice(buildImportNotice(result, sourceLabel));
    setTab("docs");
  };

  const visibleNotice = notice?.kbId === selectedKbId ? notice : null;

  return (
    <div className="knowledge-layout">
      <KbSidebar />
      <main className="knowledge-main">
        <div className="knowledge-header">
          <h2>{selectedKb?.kb_name || "请选择知识库"}</h2>
          <span className="kb-meta">
            {hasSelectedKb ? `ID: ${selectedKbId} · data/${selectedKbId}/` : "从左侧选择或新建知识库后开始管理资料"}
          </span>
        </div>

        {visibleNotice ? <p className="success kb-page-notice" role="status">{visibleNotice.message}</p> : null}

        <div className="kb-tabs" role="tablist" aria-label="知识库管理功能">
          {TABS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={tab === item.key}
              disabled={!hasSelectedKb}
              className={`kb-tab ${tab === item.key ? "active" : ""}`}
              onClick={() => setTab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="kb-tab-content">
          {!hasSelectedKb ? <div className="kb-selection-empty">请先在左侧知识库列表中选择一个 active 知识库。默认知识库也需要显式选择。</div> : null}
          {hasSelectedKb && tab === "docs" ? <KbDocumentList /> : null}
          {hasSelectedKb && tab === "upload" ? <KbUpload onSuccess={(result) => handleImportSuccess(result, "文件上传")} /> : null}
          {hasSelectedKb && tab === "web" ? <KbWebImport onSuccess={(result) => handleImportSuccess(result, "网页导入")} /> : null}
        </div>
      </main>
    </div>
  );
}

export default function KnowledgePage() {
  return (
    <KbProvider>
      <KnowledgeContent />
    </KbProvider>
  );
}

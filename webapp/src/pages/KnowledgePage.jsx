/**
 * 文件功能：
 * - 知识库统一管理页面，集成侧边栏、文档列表、文件上传、网页导入。
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listDocs } from "../api/kb";
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

function KnowledgeContent() {
  const { selectedKbId, kbList } = useKb();
  const [tab, setTab] = useState("docs");
  const currentKb = kbList.find((k) => k.kb_id === selectedKbId);

  return (
    <div className="knowledge-layout">
      <KbSidebar />
      <div className="knowledge-main">
        <div className="knowledge-header">
          <h2>{currentKb?.kb_name || "知识库管理"}</h2>
          <span className="kb-meta">ID: {selectedKbId}</span>
        </div>

        <div className="kb-tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`kb-tab ${tab === t.key ? "active" : ""}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="kb-tab-content">
          {tab === "docs" && <KbDocumentList />}
          {tab === "upload" && <KbUpload onSuccess={() => setTab("docs")} />}
          {tab === "web" && <KbWebImport onSuccess={() => setTab("docs")} />}
        </div>
      </div>
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

/**
 * 文件功能：
 * - 知识库文档列表组件，支持严格按所选知识库展示、搜索、分页和批量删除。
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { deleteDocs, listDocs } from "../../api/kb";
import { readApiData } from "../../api/response";
import { useKb } from "./KbContext";

const PAGE_SIZE = 20;

export default function KbDocumentList() {
  const { selectedKbId, selectedKb, hasSelectedKb } = useKb();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState(new Set());

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["docs", selectedKbId],
    queryFn: () => listDocs(selectedKbId),
    enabled: hasSelectedKb,
  });

  const deleteMutation = useMutation({
    mutationFn: (payload) => deleteDocs(payload),
    onSuccess: () => {
      setSelected(new Set());
      refetch();
    },
  });

  useEffect(() => {
    setSearch("");
    setPage(0);
    setSelected(new Set());
  }, [selectedKbId]);

  const docs = readApiData(data)?.docs || [];

  const filtered = useMemo(() => {
    if (!search.trim()) return docs;
    const query = search.toLowerCase();
    return docs.filter((doc) => doc.name?.toLowerCase().includes(query));
  }, [docs, search]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageDocs = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const toggleSelect = (id) => {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === pageDocs.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(pageDocs.map((doc) => doc.id)));
    }
  };

  const handleDeleteSelected = () => {
    if (!hasSelectedKb || selected.size === 0) return;
    if (!confirm(`确定从“${selectedKb.kb_name}”删除 ${selected.size} 个文档？`)) return;
    deleteMutation.mutate({ doc_ids: Array.from(selected), kb_id: selectedKbId });
  };

  if (!hasSelectedKb) {
    return <div className="kb-selection-empty">请先在左侧选择知识库，再查看该库文档。</div>;
  }
  if (isLoading) return <p>正在加载“{selectedKb.kb_name}”的文档列表...</p>;
  if (error) return <p className="error" role="alert">加载失败: {error.message}</p>;

  return (
    <div className="kb-doc-list">
      <div className="kb-doc-toolbar">
        <input
          className="kb-search-input"
          aria-label="搜索文档名称"
          placeholder="搜索文档名称..."
          value={search}
          onChange={(event) => { setSearch(event.target.value); setPage(0); }}
        />
        <button
          type="button"
          className="kb-btn-danger"
          disabled={selected.size === 0 || deleteMutation.isPending}
          onClick={handleDeleteSelected}
        >
          删除 ({selected.size})
        </button>
        <span className="kb-doc-count">{selectedKb.kb_name} · 共 {filtered.length} 个文档</span>
      </div>

      <table className="kb-doc-table">
        <thead>
          <tr>
            <th><input aria-label="选择本页全部文档" type="checkbox" checked={selected.size === pageDocs.length && pageDocs.length > 0} onChange={toggleAll} /></th>
            <th>名称</th>
            <th>类型</th>
            <th>路径</th>
            <th>知识库</th>
          </tr>
        </thead>
        <tbody>
          {pageDocs.length === 0 ? (
            <tr><td colSpan={5} className="kb-empty">该知识库暂无文档</td></tr>
          ) : (
            pageDocs.map((doc) => (
              <tr key={doc.id} className={selected.has(doc.id) ? "selected" : ""}>
                <td><input aria-label={`选择 ${doc.name}`} type="checkbox" checked={selected.has(doc.id)} onChange={() => toggleSelect(doc.id)} /></td>
                <td>{doc.name}</td>
                <td>{doc.type}</td>
                <td className="kb-doc-path">{doc.path}</td>
                <td>{doc.kb_id || "default"}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <div className="kb-pagination">
        <button type="button" disabled={page === 0} onClick={() => setPage((current) => current - 1)}>上一页</button>
        <span>{page + 1} / {pageCount}</span>
        <button type="button" disabled={page >= pageCount - 1} onClick={() => setPage((current) => current + 1)}>下一页</button>
      </div>
      {deleteMutation.error && <p className="error" role="alert">{deleteMutation.error.message}</p>}
    </div>
  );
}

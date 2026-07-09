/**
 * 文件功能：
 * - 知识库文档列表组件，支持表格展示、搜索过滤、分页、批量删除。
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { deleteDocs, listDocs } from "../../api/kb";
import { useKb } from "./KbContext";

const PAGE_SIZE = 20;

export default function KbDocumentList() {
  const { selectedKbId } = useKb();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState(new Set());

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["docs", selectedKbId],
    queryFn: () => listDocs(selectedKbId),
  });

  const deleteMutation = useMutation({
    mutationFn: (payload) => deleteDocs(payload),
    onSuccess: () => {
      setSelected(new Set());
      refetch();
    },
  });

  const docs = data?.data?.docs || [];

  const filtered = useMemo(() => {
    if (!search.trim()) return docs;
    const q = search.toLowerCase();
    return docs.filter((d) => d.name?.toLowerCase().includes(q));
  }, [docs, search]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageDocs = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === pageDocs.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(pageDocs.map((d) => d.id)));
    }
  };

  const handleDeleteSelected = () => {
    if (selected.size === 0) return;
    if (!confirm(`确定删除 ${selected.size} 个文档？`)) return;
    deleteMutation.mutate({ doc_ids: Array.from(selected), kb_id: selectedKbId });
  };

  if (isLoading) return <p>加载文档列表...</p>;
  if (error) return <p className="error">加载失败: {error.message}</p>;

  return (
    <div className="kb-doc-list">
      <div className="kb-doc-toolbar">
        <input
          className="kb-search-input"
          placeholder="搜索文档名称..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
        />
        <button
          className="kb-btn-danger"
          disabled={selected.size === 0 || deleteMutation.isPending}
          onClick={handleDeleteSelected}
        >
          删除 ({selected.size})
        </button>
        <span className="kb-doc-count">共 {filtered.length} 个文档</span>
      </div>

      <table className="kb-doc-table">
        <thead>
          <tr>
            <th><input type="checkbox" checked={selected.size === pageDocs.length && pageDocs.length > 0} onChange={toggleAll} /></th>
            <th>名称</th>
            <th>类型</th>
            <th>路径</th>
            <th>知识库</th>
          </tr>
        </thead>
        <tbody>
          {pageDocs.length === 0 ? (
            <tr><td colSpan={5} className="kb-empty">暂无文档</td></tr>
          ) : (
            pageDocs.map((doc) => (
              <tr key={doc.id} className={selected.has(doc.id) ? "selected" : ""}>
                <td><input type="checkbox" checked={selected.has(doc.id)} onChange={() => toggleSelect(doc.id)} /></td>
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
        <button disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</button>
        <span>{page + 1} / {pageCount}</span>
        <button disabled={page >= pageCount - 1} onClick={() => setPage(page + 1)}>下一页</button>
      </div>
    </div>
  );
}

/**
 * 文件功能：
 * - 提供知识库文档管理能力（选择并删除文档）。
 *
 * 执行逻辑：
 * 1. 拉取文档清单并渲染可勾选表格。
 * 2. 汇总选中项并调用删除接口。
 * 3. 删除成功后刷新列表并重置勾选状态。
 */

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { deleteDocs, listDocs } from "../api/kb";

/**
 * 知识库文档管理页面组件。
 *
 * Returns:
 * - JSX.Element: KB Manage 页面 UI。
 */
export default function KbManagePage() {
  const docsQuery = useQuery({ queryKey: ["docs-manage"], queryFn: listDocs });
  const [selected, setSelected] = useState({});

  const deleteMutation = useMutation({
    mutationFn: (payload) => deleteDocs(payload),
    onSuccess: () => {
      setSelected({});
      docsQuery.refetch();
    }
  });

  const docs = docsQuery.data?.data?.docs || [];
  const selectedIds = Object.keys(selected).filter((id) => selected[id]);

  return (
    <section>
      <h2>KB Manage</h2>
      {docsQuery.isLoading && <p>Loading...</p>}
      {docsQuery.error && <p className="error">{docsQuery.error.message}</p>}
      <table className="simple-table">
        <thead>
          <tr>
            <th />
            <th>Name</th>
            <th>Type</th>
            <th>Path</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((doc) => (
            <tr key={doc.id}>
              <td>
                <input
                  type="checkbox"
                  checked={Boolean(selected[doc.id])}
                  onChange={(e) => setSelected((prev) => ({ ...prev, [doc.id]: e.target.checked }))}
                />
              </td>
              <td>{doc.name}</td>
              <td>{doc.type}</td>
              <td>{doc.path}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        disabled={selectedIds.length === 0 || deleteMutation.isPending}
        onClick={() => deleteMutation.mutate({ doc_ids: selectedIds, paths: [] })}
      >
        {deleteMutation.isPending ? "Deleting..." : `Delete Selected (${selectedIds.length})`}
      </button>
      {deleteMutation.error && <p className="error">{deleteMutation.error.message}</p>}
    </section>
  );
}

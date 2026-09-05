/**
 * 文件功能：
 * - 提供本地文件导入知识库能力，并展示当前文档列表。
 *
 * 执行逻辑：
 * 1. 选择文件后组装 FormData。
 * 2. 调用导入接口并在成功后刷新文档列表。
 * 3. 显示导入状态与错误信息。
 */

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { importFiles, listDocs } from "../api/kb";

/**
 * 知识库文件导入页面。
 *
 * Returns:
 * - JSX.Element: KB File 页面 UI。
 */
export default function KbFilePage() {
  const [files, setFiles] = useState([]);
  const [kbId, setKbId] = useState("default");
  const docsQuery = useQuery({ queryKey: ["docs", kbId], queryFn: () => listDocs(kbId) });

  const uploadMutation = useMutation({
    mutationFn: ({ formData, id }) => importFiles(formData, id),
    onSuccess: () => docsQuery.refetch()
  });

  const fileCount = files.length;

  const onUpload = (event) => {
    event.preventDefault();
    if (files.length === 0) return;
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    formData.append("chunk_size", "2048");
    formData.append("chunk_overlap", "512");
    uploadMutation.mutate({ formData, id: kbId });
  };

  return (
    <section>
      <h2>KB File</h2>
      <div className="setting-row">
        <label>知识库 ID</label>
        <input value={kbId} onChange={(e) => setKbId(e.target.value)} placeholder="default" />
      </div>
      <form onSubmit={onUpload} className="upload-form">
        <input type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files || []))} />
        <button type="submit" disabled={uploadMutation.isPending}>
          {uploadMutation.isPending ? "Importing..." : `Import (${fileCount})`}
        </button>
      </form>
      {uploadMutation.error && <p className="error">{uploadMutation.error.message}</p>}

      <h3>Documents</h3>
      {docsQuery.isLoading && <p>Loading docs...</p>}
      {docsQuery.error && <p className="error">{docsQuery.error.message}</p>}
      <ul>
        {(docsQuery.data?.data?.docs || []).map((doc) => (
          <li key={doc.id}>
            {doc.name} - {doc.type}
          </li>
        ))}
      </ul>
    </section>
  );
}

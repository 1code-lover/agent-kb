/**
 * 文件功能：
 * - 知识库侧边栏，展示列表、切换、新建、编辑名称、删除。
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { createKb as apiCreateKb, updateKb as apiUpdateKb, deleteKb as apiDeleteKb } from "../../api/kb";
import { useKb } from "./KbContext";

export default function KbSidebar() {
  const { kbList, selectedKbId, selectKb, refreshKbs } = useKb();
  const [showCreate, setShowCreate] = useState(false);
  const [newKbId, setNewKbId] = useState("");
  const [newKbName, setNewKbName] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");

  const createMutation = useMutation({
    mutationFn: (data) => apiCreateKb(data),
    onSuccess: () => {
      setShowCreate(false);
      setNewKbId("");
      setNewKbName("");
      refreshKbs();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ kbId, data }) => apiUpdateKb(kbId, data),
    onSuccess: () => {
      setEditingId(null);
      refreshKbs();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (kbId) => apiDeleteKb(kbId),
    onSuccess: () => {
      if (selectedKbId === editingId) selectKb("default");
      refreshKbs();
    },
  });

  const handleCreate = (e) => {
    e.preventDefault();
    if (!newKbId.trim() || !newKbName.trim()) return;
    createMutation.mutate({ kb_id: newKbId.trim(), kb_name: newKbName.trim() });
  };

  const startEdit = (kb) => {
    setEditingId(kb.kb_id);
    setEditName(kb.kb_name);
  };

  const saveEdit = (kbId) => {
    if (!editName.trim()) return;
    updateMutation.mutate({ kbId, data: { kb_name: editName.trim() } });
  };

  return (
    <aside className="kb-sidebar">
      <div className="kb-sidebar-header">
        <h3>知识库</h3>
        <button className="kb-sidebar-add" onClick={() => setShowCreate(true)} title="新建知识库">+</button>
      </div>

      {showCreate && (
        <form className="kb-create-form" onSubmit={handleCreate}>
          <input placeholder="ID" value={newKbId} onChange={(e) => setNewKbId(e.target.value)} />
          <input placeholder="名称" value={newKbName} onChange={(e) => setNewKbName(e.target.value)} />
          <div className="kb-create-actions">
            <button type="submit" disabled={createMutation.isPending}>创建</button>
            <button type="button" className="kb-btn-cancel" onClick={() => setShowCreate(false)}>取消</button>
          </div>
          {createMutation.error && <p className="error">{createMutation.error.message}</p>}
        </form>
      )}

      <div className="kb-list">
        {kbList.map((kb) => (
          <div
            key={kb.kb_id}
            className={`kb-item ${selectedKbId === kb.kb_id ? "active" : ""}`}
            onClick={() => selectKb(kb.kb_id)}
          >
            {editingId === kb.kb_id ? (
              <div className="kb-item-edit" onClick={(e) => e.stopPropagation()}>
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") saveEdit(kb.kb_id); if (e.key === "Escape") setEditingId(null); }}
                  autoFocus
                />
                <button onClick={() => saveEdit(kb.kb_id)} size="small">保存</button>
                <button className="kb-btn-cancel" onClick={() => setEditingId(null)} size="small">取消</button>
              </div>
            ) : (
              <>
                <span className="kb-item-name">{kb.kb_name}</span>
                <span className="kb-item-id">{kb.kb_id}</span>
                <div className="kb-item-actions" onClick={(e) => e.stopPropagation()}>
                  <button className="kb-btn-icon" title="重命名" onClick={() => startEdit(kb)}>✎</button>
                  {kb.kb_id !== "default" && (
                    <button
                      className="kb-btn-icon kb-btn-icon-danger"
                      title="删除"
                      onClick={() => { if (confirm(`删除知识库"${kb.kb_name}"？`)) deleteMutation.mutate(kb.kb_id); }}
                    >✕</button>
                  )}
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}

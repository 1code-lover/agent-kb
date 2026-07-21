/**
 * 文件功能：
 * - 知识库侧边栏，展示列表、切换、新建、编辑名称、删除。
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { createKb as apiCreateKb, updateKb as apiUpdateKb, deleteKb as apiDeleteKb } from "../../api/kb";
import { readApiData } from "../../api/response";
import { selectionAfterCreate, selectionAfterDelete } from "../../domain/kbSelection";
import { useKb } from "./KbContext";

export default function KbSidebar() {
  const { kbList, selectedKbId, selectKb, refreshKbs, loading } = useKb();
  const [showCreate, setShowCreate] = useState(false);
  const [newKbId, setNewKbId] = useState("");
  const [newKbName, setNewKbName] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");

  const createMutation = useMutation({
    mutationFn: (data) => apiCreateKb(data),
    onSuccess: async (response) => {
      const createdKb = readApiData(response);
      setShowCreate(false);
      setNewKbId("");
      setNewKbName("");
      await refreshKbs();
      selectKb(selectionAfterCreate(createdKb));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ kbId, data }) => apiUpdateKb(kbId, data),
    onSuccess: async () => {
      setEditingId(null);
      await refreshKbs();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (kbId) => apiDeleteKb(kbId),
    onSuccess: async (_response, deletedKbId) => {
      selectKb(selectionAfterDelete(selectedKbId, deletedKbId));
      await refreshKbs();
    },
  });

  const handleCreate = (event) => {
    event.preventDefault();
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
    <aside className="kb-sidebar" aria-label="知识库列表">
      <div className="kb-sidebar-header">
        <h3>知识库</h3>
        <button
          type="button"
          className="kb-sidebar-add"
          onClick={() => setShowCreate(true)}
          title="新建知识库"
          aria-label="新建知识库"
        >+</button>
      </div>

      <p className="kb-sidebar-hint">请先选择或新建目标知识库，再导入资料。</p>

      {showCreate ? (
        <form className="kb-create-form" onSubmit={handleCreate}>
          <label htmlFor="new-kb-id">知识库 ID</label>
          <input
            id="new-kb-id"
            placeholder="例如 grain-qa"
            value={newKbId}
            onChange={(event) => setNewKbId(event.target.value)}
            pattern="[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?"
            title="仅允许小写字母、数字和中划线，首尾必须为字母或数字"
            autoComplete="off"
            required
          />
          <label htmlFor="new-kb-name">知识库名称</label>
          <input
            id="new-kb-name"
            placeholder="例如 粮仓问答测试库"
            value={newKbName}
            onChange={(event) => setNewKbName(event.target.value)}
            autoComplete="off"
            required
          />
          <div className="kb-create-actions">
            <button type="submit" disabled={createMutation.isPending}>创建并选中</button>
            <button type="button" className="kb-btn-cancel" onClick={() => setShowCreate(false)}>取消</button>
          </div>
          {createMutation.error ? <p className="error" role="alert">{createMutation.error.message}</p> : null}
        </form>
      ) : null}

      <div className="kb-list">
        {loading && kbList.length === 0 ? <p className="kb-sidebar-status">正在加载知识库...</p> : null}
        {!loading && kbList.length === 0 ? <p className="kb-sidebar-status">暂无知识库，请先新建。</p> : null}
        {kbList.map((kb) => {
          const isActive = kb.status === "active";
          const isSelected = selectedKbId === kb.kb_id;
          return (
            <div
              key={kb.kb_id}
              className={`kb-item ${isSelected ? "active" : ""} ${isActive ? "" : "disabled"}`}
            >
              {editingId === kb.kb_id ? (
                <div className="kb-item-edit">
                  <input
                    aria-label={`${kb.kb_name}的新名称`}
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") saveEdit(kb.kb_id);
                      if (event.key === "Escape") setEditingId(null);
                    }}
                    autoFocus
                  />
                  <button type="button" disabled={updateMutation.isPending} onClick={() => saveEdit(kb.kb_id)}>保存</button>
                  <button type="button" className="kb-btn-cancel" onClick={() => setEditingId(null)}>取消</button>
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    className="kb-item-select"
                    disabled={!isActive}
                    aria-pressed={isSelected}
                    onClick={() => selectKb(kb.kb_id)}
                  >
                    <span className="kb-item-name">{kb.kb_name}</span>
                    <span className="kb-item-id">{kb.kb_id}{isActive ? "" : " · 非 active"}</span>
                  </button>
                  <div className="kb-item-actions" aria-label={`${kb.kb_name}操作`}>
                    <button type="button" className="kb-btn-icon" title="重命名" aria-label={`重命名 ${kb.kb_name}`} onClick={() => startEdit(kb)}>✎</button>
                    {kb.kb_id !== "default" ? (
                      <button
                        type="button"
                        className="kb-btn-icon kb-btn-icon-danger"
                        title="删除"
                        aria-label={`删除 ${kb.kb_name}`}
                        disabled={deleteMutation.isPending}
                        onClick={() => {
                          if (confirm(`删除知识库“${kb.kb_name}”？`)) deleteMutation.mutate(kb.kb_id);
                        }}
                      >✕</button>
                    ) : null}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
      {deleteMutation.error ? <p className="error" role="alert">{deleteMutation.error.message}</p> : null}
    </aside>
  );
}

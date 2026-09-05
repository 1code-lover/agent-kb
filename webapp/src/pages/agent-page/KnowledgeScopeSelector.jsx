export default function KnowledgeScopeSelector({
  experience,
  selectedKbId,
  selectedKb,
  kbList,
  kbLoading,
  onSelectKb,
}) {
  return (
    <section className="qa-surface-card qa-kb-target-card">
      <div className="qa-section-head">
        <div>
          <p className="qa-section-eyebrow">知识库范围</p>
          <h2>选择问答目标</h2>
        </div>
      </div>

      <div className="qa-kb-bar">
        <label className="qa-field-label" htmlFor="knowledge-kb-select">
          Active 知识库
        </label>
        <select
          id="knowledge-kb-select"
          className="qa-select"
          value={selectedKbId || ""}
          disabled={kbLoading}
          onChange={(event) => onSelectKb(event.target.value)}
        >
          <option value="">请选择知识库</option>
          {kbList.map((kb) => (
            <option key={kb.kb_id} value={kb.kb_id}>
              {(kb.kb_name || kb.kb_id) + "（" + kb.kb_id + "）"}
            </option>
          ))}
        </select>
      </div>

      <div className="qa-inline-tip">
        {selectedKb
          ? "当前问答将严格限定在“" + (selectedKb.kb_name || selectedKb.kb_id) + "”（kb_id=" + selectedKb.kb_id + "）范围内。"
          : ((experience === "basic"
            ? "基础问答也必须先显式选择一个 active 知识库，避免误用默认库。"
            : "知识库问答必须先显式选择一个 active 知识库，避免误用默认库。"))}
      </div>
    </section>
  );
}

import { Link } from "react-router-dom";

export default function KnowledgePage() {
  return (
    <section className="agent-workspace">
      <header className="page-header">
        <div>
          <p className="hero-eyebrow">Knowledge</p>
          <h2>知识库会作为 NorthAgent 的下一阶段能力接入</h2>
          <p className="hero-copy">
            当前这一版先把桌面 Agent 的主链路打顺：模型配置、任务输入、执行过程、审批和回执。知识库不会单独喧宾夺主，而是以后作为
            `kb_search` 工具接入。
          </p>
        </div>
      </header>

      <div className="knowledge-roadmap-grid">
        <section className="agent-panel knowledge-hero-panel">
          <div className="panel-heading">
            <div>
              <p className="panel-eyebrow">当前阶段</p>
              <h3>先把 Agent 做到顺手、稳定、可扩展</h3>
            </div>
          </div>

          <div className="stack-list">
            <article className="stack-card">
              <strong>现在优先做什么</strong>
              <p className="stack-subtle">先保证模型配置、Agent 对话、供应商切换、审批流和回执链路可用。</p>
            </article>
            <article className="stack-card">
              <strong>知识库以后怎么接</strong>
              <p className="stack-subtle">后续把知识库作为 `kb_search` 工具接入 Agent，而不是单独做成主入口。</p>
            </article>
            <article className="stack-card">
              <strong>为什么先不做重</strong>
              <p className="stack-subtle">如果 Agent 主链路还没打顺，先堆上传、入库和检索页面，只会让产品更复杂。</p>
            </article>
          </div>
        </section>

        <section className="agent-panel knowledge-side-panel">
          <div className="panel-heading">
            <div>
              <p className="panel-eyebrow">下一步</p>
              <h3>知识库接入路线</h3>
            </div>
          </div>

          <div className="stack-list">
            <article className="stack-card">
              <strong>1. 接检索工具</strong>
              <p className="stack-subtle">先提供稳定的 `kb_search` 工具能力，让 Agent 可以在对话里调知识库。</p>
            </article>
            <article className="stack-card">
              <strong>2. 再做导入入口</strong>
              <p className="stack-subtle">等工具层稳定后，再补文件导入、网页入库和索引管理页面。</p>
            </article>
            <article className="stack-card">
              <strong>3. 最后做体验整合</strong>
              <p className="stack-subtle">把证据引用、知识来源和检索范围控制融到 Agent 工作区里。</p>
            </article>
          </div>

          <div className="agent-form-row">
            <Link className="primary-button link-button" to="/agent">
              回到 Agent
            </Link>
            <Link className="secondary-button link-button" to="/models">
              先去配置模型
            </Link>
          </div>
        </section>
      </div>
    </section>
  );
}

/**
 * 文件功能：
 * - Knowledge Workspace 过滤条，承载对象视图切换与当前视图说明。
 */

import { getWorkspaceViewMeta, listWorkspaceViews } from '../../domain/knowledgeWorkspace';

const VIEW_ITEMS = listWorkspaceViews();

export default function KbWorkspaceFilterBar({ hasSelectedKb, viewMode, onChangeViewMode }) {
  const activeView = getWorkspaceViewMeta(viewMode);

  return (
    <section className='kb-workspace-filter-bar'>
      <div className='kb-workspace-filter-tabs' role='tablist' aria-label='知识对象视图切换'>
        {VIEW_ITEMS.map((item) => (
          <button
            key={item.key}
            type='button'
            role='tab'
            aria-selected={viewMode === item.key}
            disabled={!hasSelectedKb}
            className={'kb-filter-chip' + (viewMode === item.key ? ' active' : '')}
            onClick={() => onChangeViewMode(item.key)}
          >
            {item.label}
            {!item.implemented ? <span className='kb-filter-chip-hint'>即将支持</span> : null}
          </button>
        ))}
      </div>

      <p className='kb-workspace-filter-help'>
        {hasSelectedKb ? activeView.description : '未选中知识库时，页面保持默认拒绝心智：不导入、不浏览、不跨库兜底。'}
      </p>
    </section>
  );
}

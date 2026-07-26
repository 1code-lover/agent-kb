/**
 * 文件功能：
 * - 知识管理主入口，重构为 Knowledge Workspace：统一承载对象浏览、导入动作与详情摘要。
 * - 支持最近导入回执的持久化回显，避免刷新页面后丢失最近一次导入结果。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { getHealthStatus } from '../api/health';
import { getLatestImportReceipt } from '../api/kb';
import { readApiData } from '../api/response';
import { KbProvider, useKb } from '../components/kb/KbContext';
import KbSidebar from '../components/kb/KbSidebar';
import KbUpload from '../components/kb/KbUpload';
import KbWebImport from '../components/kb/KbWebImport';
import KbDetailPanel from '../components/kb/KbDetailPanel';
import KbObjectExplorer from '../components/kb/KbObjectExplorer';
import KbWorkspaceFilterBar from '../components/kb/KbWorkspaceFilterBar';
import KbWorkspaceHeader from '../components/kb/KbWorkspaceHeader';
import {
  buildImportNotice,
  buildPersistedImportReceiptSummary,
  resolveVisibleReceiptSummary,
} from '../domain/importSummary';
import { buildOcrWarmupSummary } from '../domain/ocrWarmup';
import { canUseKbTarget } from '../domain/kbSelection';
import {
  buildKnowledgeWorkspaceLink,
  parseKnowledgeWorkspaceEntry,
} from '../domain/kbNavigation';
import {
  KB_WORKSPACE_ACTION_MODES,
  KB_WORKSPACE_VIEW_MODES,
  getWorkspaceActionMeta,
} from '../domain/knowledgeWorkspace';

function ActionPanel({ actionMode, onClose, onImportSuccess }) {
  const actionMeta = getWorkspaceActionMeta(actionMode);

  if (actionMode === KB_WORKSPACE_ACTION_MODES.NONE) {
    return null;
  }

  let content = null;
  if (actionMode === KB_WORKSPACE_ACTION_MODES.UPLOAD) {
    content = <KbUpload onSuccess={(result) => onImportSuccess(result, '文件上传')} />;
  } else if (actionMode === KB_WORKSPACE_ACTION_MODES.WEB_IMPORT) {
    content = <KbWebImport onSuccess={(result) => onImportSuccess(result, '网页导入')} />;
  } else {
    content = (
      <div className='kb-selection-empty'>
        目录导入会在下一阶段以“目录扫描 + 入库回执”的形式接入本工作区，当前先保留入口位。
      </div>
    );
  }

  return (
    <section className='kb-action-panel'>
      <div className='kb-action-panel-head'>
        <div>
          <p className='kb-action-panel-eyebrow'>当前动作</p>
          <h3>{actionMeta.title}</h3>
          <p className='kb-action-panel-description'>{actionMeta.description}</p>
        </div>
        <button type='button' className='kb-btn-cancel' onClick={onClose}>关闭面板</button>
      </div>
      <div className='kb-action-panel-body'>{content}</div>
    </section>
  );
}

function pickDefaultReceiptObject(receiptSummary) {
  const items = Array.isArray(receiptSummary?.items) ? receiptSummary.items : [];
  for (const fileItem of items) {
    if (Array.isArray(fileItem.embeddedAssets) && fileItem.embeddedAssets.length > 0) {
      return fileItem.embeddedAssets[0];
    }
  }
  return items[0] || null;
}

function KnowledgeContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const routeIntentAppliedRef = useRef('');
  const {
    kbList,
    loading: kbLoading,
    selectedKbId,
    selectedKb,
    hasSelectedKb,
    selectKb,
  } = useKb();
  const routeIntent = useMemo(() => parseKnowledgeWorkspaceEntry(location.search), [location.search]);
  const isRouteIntentPending = Boolean(location.search) && routeIntentAppliedRef.current !== location.search;
  const [viewMode, setViewMode] = useState(KB_WORKSPACE_VIEW_MODES.DOCUMENTS);
  const [actionMode, setActionMode] = useState(KB_WORKSPACE_ACTION_MODES.NONE);
  const [notice, setNotice] = useState(null);
  const [receiptSummary, setReceiptSummary] = useState(null);
  const [selectedObject, setSelectedObject] = useState(null);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const latestReceiptQuery = useQuery({
    queryKey: ['kb-latest-import-receipt', selectedKbId, refreshVersion],
    enabled: hasSelectedKb && Boolean(selectedKbId),
    retry: false,
    queryFn: async () => {
      const response = await getLatestImportReceipt(selectedKbId);
      return readApiData(response)?.receipt || null;
    },
  });

  const persistedReceiptSummary = useMemo(
    () => buildPersistedImportReceiptSummary(latestReceiptQuery.data),
    [latestReceiptQuery.data],
  );

  const healthQuery = useQuery({
    queryKey: ['health', 'ocr-warmup'],
    retry: false,
    refetchInterval: (query) => (query.state.data?.state === 'warming' ? 3000 : false),
    queryFn: async () => {
      const response = await getHealthStatus();
      return readApiData(response)?.ocr_warmup || null;
    },
  });

  const ocrWarmupSummary = useMemo(() => {
    if (healthQuery.isLoading && !healthQuery.data) {
      return {
        state: 'loading',
        tone: 'muted',
        title: 'OCR 状态加载中',
        summary: '正在读取后台 OCR 预热状态，稍后会自动刷新。',
        detail: '等待 /api/health 返回',
        isReady: false,
      };
    }

    if (healthQuery.error) {
      return buildOcrWarmupSummary({
        state: 'failed',
        last_error: healthQuery.error.message,
      });
    }

    return buildOcrWarmupSummary(healthQuery.data);
  }, [healthQuery.data, healthQuery.error, healthQuery.isLoading]);

  useEffect(() => {
    if (!isRouteIntentPending) {
      return;
    }
    if (kbLoading) {
      return;
    }

    if (routeIntent.requestedKbId && canUseKbTarget(kbList, routeIntent.requestedKbId)) {
      selectKb(routeIntent.requestedKbId);
    }

    routeIntentAppliedRef.current = location.search;
  }, [isRouteIntentPending, kbList, kbLoading, location.search, routeIntent, selectKb]);

  useEffect(() => {
    if (isRouteIntentPending) {
      return;
    }

    const target = buildKnowledgeWorkspaceLink(selectedKbId);
    const current = location.pathname + location.search;
    if (target !== current) {
      navigate(target, { replace: true });
    }
  }, [isRouteIntentPending, location.pathname, location.search, navigate, selectedKbId]);

  useEffect(() => {
    setViewMode(KB_WORKSPACE_VIEW_MODES.DOCUMENTS);
    setActionMode(KB_WORKSPACE_ACTION_MODES.NONE);
    setNotice(null);
    setReceiptSummary(null);
    setSelectedObject(null);
  }, [selectedKbId]);

  const handleToggleActionMode = (nextActionMode) => {
    if (!hasSelectedKb) {
      return;
    }
    setActionMode((current) => (
      current === nextActionMode ? KB_WORKSPACE_ACTION_MODES.NONE : nextActionMode
    ));
  };

  const handleImportSuccess = (result, sourceLabel) => {
    const nextNotice = buildImportNotice(result, sourceLabel);
    setNotice(nextNotice);
    setReceiptSummary(nextNotice.receiptSummary);
    setViewMode(KB_WORKSPACE_VIEW_MODES.RECENT_IMPORTS);
    setActionMode(KB_WORKSPACE_ACTION_MODES.NONE);
    setSelectedObject(pickDefaultReceiptObject(nextNotice.receiptSummary));
    setRefreshVersion((current) => current + 1);
  };

  const visibleNotice = notice?.kbId === selectedKbId ? notice : null;
  const visibleReceiptSummary = useMemo(
    () => resolveVisibleReceiptSummary(selectedKbId, receiptSummary, persistedReceiptSummary),
    [persistedReceiptSummary, receiptSummary, selectedKbId],
  );

  useEffect(() => {
    if (!visibleReceiptSummary || selectedObject) {
      return;
    }
    setSelectedObject(pickDefaultReceiptObject(visibleReceiptSummary));
  }, [selectedObject, visibleReceiptSummary]);

  return (
    <div className='knowledge-layout'>
      <KbSidebar />
      <main className='knowledge-main knowledge-workspace-main'>
        <KbWorkspaceHeader
          selectedKb={selectedKb}
          selectedKbId={selectedKbId}
          hasSelectedKb={hasSelectedKb}
          actionMode={actionMode}
          onToggleActionMode={handleToggleActionMode}
          ocrWarmupSummary={ocrWarmupSummary}
        />

        {visibleNotice ? <p className='success kb-page-notice' role='status'>{visibleNotice.message}</p> : null}

        <KbWorkspaceFilterBar
          hasSelectedKb={hasSelectedKb}
          viewMode={viewMode}
          onChangeViewMode={setViewMode}
        />

        {hasSelectedKb ? (
          <ActionPanel
            actionMode={actionMode}
            onClose={() => setActionMode(KB_WORKSPACE_ACTION_MODES.NONE)}
            onImportSuccess={handleImportSuccess}
          />
        ) : null}

        <div className='kb-workspace-body'>
          <KbObjectExplorer
            hasSelectedKb={hasSelectedKb}
            selectedKb={selectedKb}
            viewMode={viewMode}
            receiptSummary={visibleReceiptSummary}
            refreshVersion={refreshVersion}
            selectedObject={selectedObject}
            onSelectObject={setSelectedObject}
          />

          <KbDetailPanel
            hasSelectedKb={hasSelectedKb}
            selectedKb={selectedKb}
            selectedKbId={selectedKbId}
            receiptSummary={visibleReceiptSummary}
            selectedObject={selectedObject}
          />
        </div>
      </main>
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

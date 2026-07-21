/**
 * 文件功能：
 * - 全局知识库状态管理，提供列表、显式目标选择和刷新能力。
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer } from "react";
import { listKbs as apiListKbs } from "../../api/kb";
import { readApiData } from "../../api/response";
import {
  EMPTY_KB_SELECTION,
  canUseKbTarget,
  reconcileKbSelection,
} from "../../domain/kbSelection";

const KbContext = createContext(null);

const initialState = {
  kbList: [],
  selectedKbId: EMPTY_KB_SELECTION,
  loading: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_KB_LIST":
      return {
        ...state,
        kbList: action.payload,
        selectedKbId: reconcileKbSelection(action.payload, state.selectedKbId),
        loading: false,
      };
    case "SELECT_KB":
      return {
        ...state,
        selectedKbId: action.payload === EMPTY_KB_SELECTION
          ? EMPTY_KB_SELECTION
          : (canUseKbTarget(state.kbList, action.payload) ? action.payload : EMPTY_KB_SELECTION),
      };
    case "SET_LOADING":
      return { ...state, loading: action.payload };
    default:
      return state;
  }
}

export function KbProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const refreshKbs = useCallback(async () => {
    dispatch({ type: "SET_LOADING", payload: true });
    try {
      const res = await apiListKbs();
      const items = readApiData(res)?.items || [];
      dispatch({ type: "SET_KB_LIST", payload: items });
      return items;
    } catch {
      dispatch({ type: "SET_KB_LIST", payload: [] });
      return [];
    }
  }, []);

  const selectKb = useCallback((kbId) => {
    dispatch({ type: "SELECT_KB", payload: kbId || EMPTY_KB_SELECTION });
  }, []);

  useEffect(() => {
    refreshKbs();
  }, [refreshKbs]);

  const selectedKb = state.kbList.find(
    (kb) => kb.kb_id === state.selectedKbId && kb.status === "active",
  ) || null;

  const value = useMemo(() => ({
    kbList: state.kbList,
    selectedKbId: state.selectedKbId,
    selectedKb,
    hasSelectedKb: Boolean(selectedKb),
    loading: state.loading,
    selectKb,
    refreshKbs,
  }), [state.kbList, state.selectedKbId, state.loading, selectedKb, selectKb, refreshKbs]);

  return <KbContext.Provider value={value}>{children}</KbContext.Provider>;
}

export function useKb() {
  const ctx = useContext(KbContext);
  if (!ctx) throw new Error("useKb must be used within KbProvider");
  return ctx;
}

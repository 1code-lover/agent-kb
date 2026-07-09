/**
 * 文件功能：
 * - 全局知识库状态管理，提供 kbList、selectedKbId、selectKb、refreshKbs。
 */

import { createContext, useCallback, useContext, useEffect, useReducer } from "react";
import { listKbs as apiListKbs } from "../../api/kb";

const KbContext = createContext(null);

const initialState = {
  kbList: [],
  selectedKbId: "default",
  loading: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_KB_LIST":
      return { ...state, kbList: action.payload, loading: false };
    case "SELECT_KB":
      return { ...state, selectedKbId: action.payload };
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
      dispatch({ type: "SET_KB_LIST", payload: res.data?.data?.items || [] });
    } catch {
      dispatch({ type: "SET_KB_LIST", payload: [] });
    }
  }, []);

  const selectKb = useCallback((kbId) => {
    dispatch({ type: "SELECT_KB", payload: kbId });
  }, []);

  useEffect(() => {
    refreshKbs();
  }, [refreshKbs]);

  const value = {
    kbList: state.kbList,
    selectedKbId: state.selectedKbId,
    loading: state.loading,
    selectKb,
    refreshKbs,
  };

  return <KbContext.Provider value={value}>{children}</KbContext.Provider>;
}

export function useKb() {
  const ctx = useContext(KbContext);
  if (!ctx) throw new Error("useKb must be used within KbProvider");
  return ctx;
}

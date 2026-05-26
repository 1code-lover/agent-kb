/**
 * 文件功能：
 * - 提供高级配置页面（response mode、reranker、system prompt）。
 *
 * 执行逻辑：
 * 1. 拉取后端设置并映射到本地状态。
 * 2. 用户修改高级参数后提交保存。
 * 3. 保存成功后回拉数据保证展示与后端一致。
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { getSettings, updateSettings } from "../api/settings";

const RESPONSE_MODE = [
  "compact",
  "refine",
  "tree_summarize",
  "simple_summarize",
  "accumulate",
  "compact_accumulate"
];

/**
 * 高级设置页面组件。
 *
 * Returns:
 * - JSX.Element: Advanced 页面 UI。
 */
export default function AdvancedPage() {
  const settingsQuery = useQuery({ queryKey: ["advanced-settings"], queryFn: getSettings });
  const [state, setState] = useState(null);

  useEffect(() => {
    const settings = settingsQuery.data?.data?.settings;
    if (settings) {
      setState(settings);
    }
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (payload) => updateSettings(payload),
    onSuccess: () => settingsQuery.refetch()
  });

  if (!state) {
    return <p>Loading...</p>;
  }

  return (
    <section>
      <h2>Advanced</h2>
      <div className="setting-row">
        <label>Response Mode</label>
        <select value={state.response_mode} onChange={(e) => setState((s) => ({ ...s, response_mode: e.target.value }))}>
          {RESPONSE_MODE.map((mode) => (
            <option key={mode} value={mode}>
              {mode}
            </option>
          ))}
        </select>
      </div>
      <div className="setting-row">
        <label>Use Reranker</label>
        <input
          type="checkbox"
          checked={state.use_reranker}
          onChange={(e) => setState((s) => ({ ...s, use_reranker: e.target.checked }))}
        />
      </div>
      <div className="setting-row">
        <label>Top N</label>
        <input type="number" min={1} value={state.top_n} onChange={(e) => setState((s) => ({ ...s, top_n: Number(e.target.value) }))} />
      </div>
      <div className="setting-row">
        <label>System Prompt</label>
      </div>
      <textarea rows={6} value={state.system_prompt} onChange={(e) => setState((s) => ({ ...s, system_prompt: e.target.value }))} />
      <button onClick={() => saveMutation.mutate(state)} disabled={saveMutation.isPending}>
        Save Advanced Settings
      </button>
      {saveMutation.error && <p className="error">{saveMutation.error.message}</p>}
    </section>
  );
}

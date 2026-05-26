/**
 * 文件功能：
 * - 提供基础系统参数配置页（Top K、Temperature）。
 *
 * 执行逻辑：
 * 1. 首次加载拉取后端设置并同步到本地表单状态。
 * 2. 用户修改后提交更新接口。
 * 3. 保存成功后重新拉取后端设置保持一致性。
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { getSettings, updateSettings } from "../api/settings";

/**
 * 基础设置页面组件。
 *
 * Returns:
 * - JSX.Element: Settings 页面 UI。
 */
export default function SettingsPage() {
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const [localSettings, setLocalSettings] = useState(null);

  useEffect(() => {
    if (settingsQuery.data?.data?.settings) {
      setLocalSettings(settingsQuery.data.data.settings);
    }
  }, [settingsQuery.data]);

  const updateMutation = useMutation({
    mutationFn: (payload) => updateSettings(payload),
    onSuccess: () => settingsQuery.refetch()
  });

  if (!localSettings) {
    return <p>Loading settings...</p>;
  }

  return (
    <section>
      <h2>Settings</h2>
      <div className="setting-row">
        <label>Top K</label>
        <input
          type="number"
          min={1}
          max={100}
          value={localSettings.top_k}
          onChange={(e) => setLocalSettings((s) => ({ ...s, top_k: Number(e.target.value) }))}
        />
      </div>
      <div className="setting-row">
        <label>Temperature</label>
        <input
          type="number"
          min={0}
          max={1}
          step={0.1}
          value={localSettings.temperature}
          onChange={(e) => setLocalSettings((s) => ({ ...s, temperature: Number(e.target.value) }))}
        />
      </div>
      <button onClick={() => updateMutation.mutate(localSettings)} disabled={updateMutation.isPending}>
        Save Settings
      </button>
      {updateMutation.error && <p className="error">{updateMutation.error.message}</p>}
    </section>
  );
}

/**
 * 文件功能：
 * - 提供模型选择和自定义 Provider 管理能力。
 *
 * 执行逻辑：
 * 1. 拉取 provider 与模型列表供用户选择。
 * 2. 支持新增、测试、删除自定义 provider。
 * 3. 支持将选中的 provider/model 应用为当前运行配置。
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  addCustomProvider,
  deleteCustomProvider,
  getModelOptions,
  selectModel,
  testCustomProvider
} from "../api/models";

/**
 * 模型与提供商管理页面组件。
 *
 * Returns:
 * - JSX.Element: Models 页面 UI。
 */
export default function ModelsPage() {
  const modelQuery = useQuery({ queryKey: ["model-options"], queryFn: getModelOptions });
  const providers = useMemo(() => modelQuery.data?.data?.providers || {}, [modelQuery.data]);
  const customProviderNames = useMemo(() => modelQuery.data?.data?.custom_provider_names || [], [modelQuery.data]);
  const providerNames = useMemo(() => Object.keys(providers), [providers]);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [customName, setCustomName] = useState("");
  const [customBaseUrl, setCustomBaseUrl] = useState("");
  const [customApiKey, setCustomApiKey] = useState("");
  const [customModelsText, setCustomModelsText] = useState("");
  const [testModel, setTestModel] = useState("");
  const [deleteSuccessMessage, setDeleteSuccessMessage] = useState("");

  const selectMutation = useMutation({
    mutationFn: (payload) => selectModel(payload),
    onSuccess: () => modelQuery.refetch()
  });
  const addProviderMutation = useMutation({
    mutationFn: (payload) => addCustomProvider(payload),
    onSuccess: () => {
      setCustomName("");
      setCustomBaseUrl("");
      setCustomApiKey("");
      setCustomModelsText("");
      modelQuery.refetch();
    }
  });
  const testProviderMutation = useMutation({
    mutationFn: (payload) => testCustomProvider(payload)
  });
  const deleteProviderMutation = useMutation({
    mutationFn: (name) => deleteCustomProvider(name),
    onSuccess: (resp) => {
      setDeleteSuccessMessage(`删除成功：${resp.data.name}`);
      setTimeout(() => setDeleteSuccessMessage(""), 2000);
      modelQuery.refetch();
    }
  });

  const currentModels = provider ? providers[provider]?.models || [] : [];

  return (
    <section>
      <h2>Models</h2>
      <div className="setting-row">
        <label>Provider</label>
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="">请选择</option>
          {providerNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>
      <div className="setting-row">
        <label>Model</label>
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="">请选择</option>
          {currentModels.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>
      <button
        disabled={!provider || !model || selectMutation.isPending}
        onClick={() => selectMutation.mutate({ service_provider: provider, model })}
      >
        Apply
      </button>
      {selectMutation.error && <p className="error">{selectMutation.error.message}</p>}

      <hr />
      <h3>新增自定义 Provider（公益站 / OpenAI 兼容站）</h3>
      <div className="setting-row">
        <label>名称</label>
        <input value={customName} onChange={(e) => setCustomName(e.target.value)} placeholder="例如：公益站A" />
      </div>
      <div className="setting-row">
        <label>Base URL</label>
        <input
          value={customBaseUrl}
          onChange={(e) => setCustomBaseUrl(e.target.value)}
          placeholder="https://example.com/v1"
        />
      </div>
      <div className="setting-row">
        <label>API Key</label>
        <input value={customApiKey} onChange={(e) => setCustomApiKey(e.target.value)} placeholder="sk-..." />
      </div>
      <div className="setting-row">
        <label>模型列表</label>
        <textarea
          rows={3}
          value={customModelsText}
          onChange={(e) => setCustomModelsText(e.target.value)}
          placeholder={"每行一个模型，例如:\nqwen-plus\ngpt-4o-mini"}
        />
      </div>
      <button
        disabled={
          !customName.trim() ||
          !customBaseUrl.trim() ||
          !customModelsText.trim() ||
          addProviderMutation.isPending
        }
        onClick={() =>
          addProviderMutation.mutate({
            name: customName.trim(),
            api_base: customBaseUrl.trim(),
            api_key: customApiKey,
            models: customModelsText
              .split("\n")
              .map((item) => item.trim())
              .filter(Boolean)
          })
        }
      >
        {addProviderMutation.isPending ? "Saving..." : "保存自定义 Provider"}
      </button>
      {addProviderMutation.error && <p className="error">{addProviderMutation.error.message}</p>}
      {addProviderMutation.data && <p>已保存：{addProviderMutation.data.data.name}</p>}

      <div className="setting-row">
        <label>已保存自定义 Provider</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {customProviderNames.length === 0 && <span>暂无</span>}
          {customProviderNames.map((name) => (
            <button
              key={name}
              onClick={() => {
                const confirmed = window.confirm(`确认删除自定义 Provider「${name}」吗？`);
                if (confirmed) {
                  deleteProviderMutation.mutate(name);
                }
              }}
              disabled={deleteProviderMutation.isPending}
              title={`删除 ${name}`}
            >
              {deleteProviderMutation.isPending ? "Deleting..." : `删除 ${name}`}
            </button>
          ))}
        </div>
      </div>
      {deleteProviderMutation.error && <p className="error">{deleteProviderMutation.error.message}</p>}
      {deleteSuccessMessage && <p>{deleteSuccessMessage}</p>}

      <hr />
      <h3>连接测试</h3>
      <div className="setting-row">
        <label>测试模型</label>
        <input value={testModel} onChange={(e) => setTestModel(e.target.value)} placeholder="填写可用模型名" />
      </div>
      <button
        disabled={!customBaseUrl.trim() || !customApiKey.trim() || !testModel.trim() || testProviderMutation.isPending}
        onClick={() =>
          testProviderMutation.mutate({
            api_base: customBaseUrl.trim(),
            api_key: customApiKey,
            model: testModel.trim()
          })
        }
      >
        {testProviderMutation.isPending ? "Testing..." : "测试连接"}
      </button>
      {testProviderMutation.error && <p className="error">{testProviderMutation.error.message}</p>}
      {testProviderMutation.data && (
        <p>测试结果：{testProviderMutation.data.data.reachable ? "可连接" : "连接失败（请检查 base_url/api_key/model）"}</p>
      )}
    </section>
  );
}

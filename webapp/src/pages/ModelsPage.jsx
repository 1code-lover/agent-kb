import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  addCustomProvider,
  deleteCustomProvider,
  getModelOptions,
  selectModel,
  testCustomProvider
} from "../api/models";

function normalizeModels(text) {
  return text
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function ModelsPage() {
  const modelQuery = useQuery({ queryKey: ["model-options"], queryFn: getModelOptions });
  const payload = modelQuery.data?.data || {};
  const providers = payload.providers || {};
  const currentInfo = payload.current_llm_info || null;
  const providerNames = useMemo(() => Object.keys(providers), [providers]);
  const customProviderNames = payload.custom_provider_names || [];

  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [testResult, setTestResult] = useState("");

  const [customName, setCustomName] = useState("");
  const [customBaseUrl, setCustomBaseUrl] = useState("");
  const [customApiKey, setCustomApiKey] = useState("");
  const [customModelsText, setCustomModelsText] = useState("");

  useEffect(() => {
    if (!currentInfo) {
      return;
    }
    setProvider(currentInfo.service_provider || "");
    setModel(currentInfo.model || "");
    setApiBase(currentInfo.api_base || "");
    setApiKey(currentInfo.api_key || "");
  }, [currentInfo]);

  const availableModels = provider ? providers[provider]?.models || [] : [];

  useEffect(() => {
    if (!provider) {
      return;
    }
    const providerInfo = providers[provider] || {};
    if (!availableModels.includes(model)) {
      setModel(availableModels[0] || "");
    }
    if (!currentInfo || currentInfo.service_provider !== provider) {
      setApiBase(providerInfo.api_base || "");
      setApiKey("");
    }
  }, [provider, availableModels, model, providers, currentInfo]);

  const selectMutation = useMutation({
    mutationFn: (requestPayload) => selectModel(requestPayload),
    onSuccess: async () => {
      setTestResult("Current model saved.");
      await modelQuery.refetch();
    }
  });

  const testMutation = useMutation({
    mutationFn: (requestPayload) => testCustomProvider(requestPayload),
    onSuccess: (response) => {
      const result = response.data;
      setTestResult(result.reachable ? "Connection test passed." : `Connection test failed: ${result.detail}`);
    }
  });

  const addProviderMutation = useMutation({
    mutationFn: (requestPayload) => addCustomProvider(requestPayload),
    onSuccess: async () => {
      setCustomName("");
      setCustomBaseUrl("");
      setCustomApiKey("");
      setCustomModelsText("");
      await modelQuery.refetch();
    }
  });

  const deleteProviderMutation = useMutation({
    mutationFn: (name) => deleteCustomProvider(name),
    onSuccess: async () => {
      await modelQuery.refetch();
    }
  });

  return (
    <section className="agent-workspace">
      <header className="workspace-hero">
        <div>
          <p className="hero-eyebrow">Model Control</p>
          <h2>LLM Runtime Settings</h2>
          <p className="hero-copy">
            Test connections, save custom OpenAI-compatible providers, and switch the current model
            for the next agent run.
          </p>
        </div>
      </header>

      <div className="agent-main-grid">
        <div className="agent-primary-column">
          <section className="agent-panel">
            <div className="panel-heading">
              <div>
                <p className="panel-eyebrow">Current Runtime</p>
                <h3>Active Model</h3>
              </div>
            </div>

            <div className="agent-form">
              <div className="setting-row">
                <label className="field-label">Provider</label>
                <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                  <option value="">Select provider</option>
                  {providerNames.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="setting-row">
                <label className="field-label">Model</label>
                <select value={model} onChange={(event) => setModel(event.target.value)}>
                  <option value="">Select model</option>
                  {availableModels.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="setting-row">
                <label className="field-label">Base URL</label>
                <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} placeholder="https://example.com/v1" />
              </div>

              <div className="setting-row">
                <label className="field-label">API Key</label>
                <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="sk-..." />
              </div>

              <div className="agent-form-row">
                <button
                  type="button"
                  className="secondary-button"
                  disabled={!apiBase || !apiKey || !model || testMutation.isPending}
                  onClick={() =>
                    testMutation.mutate({
                      api_base: apiBase.trim(),
                      api_key: apiKey,
                      model: model.trim()
                    })
                  }
                >
                  {testMutation.isPending ? "Testing..." : "Test Connection"}
                </button>
                <button
                  type="button"
                  className="primary-button"
                  disabled={!provider || !model || selectMutation.isPending}
                  onClick={() =>
                    selectMutation.mutate({
                      service_provider: provider,
                      model,
                      api_base: apiBase.trim(),
                      api_key: apiKey
                    })
                  }
                >
                  {selectMutation.isPending ? "Saving..." : "Save Current Model"}
                </button>
              </div>

              {currentInfo && (
                <p className="simple-note">
                  Current saved runtime: {currentInfo.service_provider || "-"} / {currentInfo.model || "-"}
                </p>
              )}
              {testResult && <p className="simple-note">{testResult}</p>}
              {selectMutation.error && <p className="error">{selectMutation.error.message}</p>}
              {testMutation.error && <p className="error">{testMutation.error.message}</p>}
            </div>
          </section>
        </div>

        <div className="agent-secondary-column">
          <section className="agent-panel">
            <div className="panel-heading">
              <div>
                <p className="panel-eyebrow">Custom Provider</p>
                <h3>Saved Endpoints</h3>
              </div>
            </div>

            <div className="agent-form">
              <div className="setting-row">
                <label className="field-label">Provider Name</label>
                <input value={customName} onChange={(event) => setCustomName(event.target.value)} placeholder="My OpenAI Compatible API" />
              </div>

              <div className="setting-row">
                <label className="field-label">Base URL</label>
                <input value={customBaseUrl} onChange={(event) => setCustomBaseUrl(event.target.value)} placeholder="https://example.com/v1" />
              </div>

              <div className="setting-row">
                <label className="field-label">API Key</label>
                <input value={customApiKey} onChange={(event) => setCustomApiKey(event.target.value)} placeholder="sk-..." />
              </div>

              <div className="setting-row">
                <label className="field-label">Models</label>
                <textarea
                  rows={4}
                  value={customModelsText}
                  onChange={(event) => setCustomModelsText(event.target.value)}
                  placeholder={"gpt-4o-mini\nqwen-plus"}
                />
              </div>

              <div className="agent-form-row">
                <button
                  type="button"
                  className="secondary-button"
                  disabled={!customBaseUrl || !customApiKey || normalizeModels(customModelsText).length === 0 || testMutation.isPending}
                  onClick={() =>
                    testMutation.mutate({
                      api_base: customBaseUrl.trim(),
                      api_key: customApiKey,
                      model: normalizeModels(customModelsText)[0]
                    })
                  }
                >
                  {testMutation.isPending ? "Testing..." : "Test Before Save"}
                </button>
                <button
                  type="button"
                  className="primary-button"
                  disabled={!customName || !customBaseUrl || normalizeModels(customModelsText).length === 0 || addProviderMutation.isPending}
                  onClick={() =>
                    addProviderMutation.mutate({
                      name: customName.trim(),
                      api_base: customBaseUrl.trim(),
                      api_key: customApiKey,
                      models: normalizeModels(customModelsText)
                    })
                  }
                >
                  {addProviderMutation.isPending ? "Saving..." : "Save Provider"}
                </button>
              </div>

              {addProviderMutation.error && <p className="error">{addProviderMutation.error.message}</p>}
            </div>

            <div className="stack-list">
              {customProviderNames.length === 0 && <div className="empty-block">No saved custom providers.</div>}
              {customProviderNames.map((name) => (
                <article key={name} className="stack-card">
                  <div className="stack-title-row">
                    <strong>{name}</strong>
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={deleteProviderMutation.isPending}
                      onClick={() => deleteProviderMutation.mutate(name)}
                    >
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

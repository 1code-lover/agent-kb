import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  addCustomProvider,
  deleteCustomProvider,
  exportProviderConfig,
  getModelOptions,
  importProviderConfig,
  selectModel,
  testCustomProvider
} from "../api/models";

const DASHSCOPE_PRESET = {
  name: "阿里百炼",
  apiBase: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  models: ["qwen-plus", "qwen-flash"],
  defaultModel: "qwen-plus"
};

function normalizeModels(text) {
  return text
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function classifyTestDetail(detail) {
  const text = (detail || "").toLowerCase();
  if (text.includes("401") || text.includes("invalid api key") || text.includes("incorrect api key")) {
    return "当前 API Key 很可能无效，或者与这个 Base URL 不匹配。";
  }
  if (text.includes("404") || text.includes("model_not_found")) {
    return "当前模型名或接口路径不对，请检查 Base URL 和模型名。";
  }
  if (text.includes("connection refused") || text.includes("timed out") || text.includes("name or service not known")) {
    return "当前无法连接接口地址，请检查网络、代理或服务状态。";
  }
  if (text.includes("api_key is required")) {
    return "当前没有可用的 API Key，请先填写后再测试。";
  }
  return "";
}

function buildImportPreview(text) {
  if (!text.trim()) {
    return { count: 0, modeReady: false, error: "" };
  }

  try {
    const parsed = JSON.parse(text);
    const count = Array.isArray(parsed.custom_llm_providers) ? parsed.custom_llm_providers.length : 0;
    return { count, modeReady: true, error: "" };
  } catch (error) {
    return { count: 0, modeReady: false, error: `JSON 解析失败：${error.message}` };
  }
}

export default function ModelsPage() {
  const modelQuery = useQuery({
    queryKey: ["model-options"],
    queryFn: getModelOptions,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30000
  });

  const payload = modelQuery.data || {};
  const providers = payload.providers || {};
  const customProviderNames = payload.custom_provider_names || [];
  const currentInfo = payload.current_llm_info || null;
  const savedProviders = customProviderNames.map((name) => providers[name]).filter(Boolean);

  const [customName, setCustomName] = useState(DASHSCOPE_PRESET.name);
  const [customBaseUrl, setCustomBaseUrl] = useState(DASHSCOPE_PRESET.apiBase);
  const [customApiKey, setCustomApiKey] = useState("");
  const [customModelInput, setCustomModelInput] = useState(DASHSCOPE_PRESET.defaultModel);
  const [customModelsText, setCustomModelsText] = useState(DASHSCOPE_PRESET.models.join("\n"));
  const [draftActiveModel, setDraftActiveModel] = useState(DASHSCOPE_PRESET.defaultModel);
  const [feedback, setFeedback] = useState("");
  const [testDetail, setTestDetail] = useState(null);
  const [exportText, setExportText] = useState("");
  const [importText, setImportText] = useState("");

  const draftModels = useMemo(() => normalizeModels(customModelsText), [customModelsText]);
  const editedProvider = useMemo(
    () => savedProviders.find((provider) => provider.name === customName.trim()) || null,
    [savedProviders, customName]
  );
  const importPreview = useMemo(() => buildImportPreview(importText), [importText]);

  useEffect(() => {
    if (!draftModels.length) {
      setDraftActiveModel("");
      return;
    }

    if (!draftModels.includes(draftActiveModel)) {
      setDraftActiveModel(draftModels[0]);
    }
  }, [draftModels, draftActiveModel]);

  function clearMessages() {
    setFeedback("");
    setTestDetail(null);
  }

  function applyPreset() {
    setCustomName(DASHSCOPE_PRESET.name);
    setCustomBaseUrl(DASHSCOPE_PRESET.apiBase);
    setCustomApiKey("");
    setCustomModelInput(DASHSCOPE_PRESET.defaultModel);
    setCustomModelsText(DASHSCOPE_PRESET.models.join("\n"));
    setDraftActiveModel(DASHSCOPE_PRESET.defaultModel);
    clearMessages();
    setFeedback("已恢复阿里百炼预设。");
  }

  function fillDraft(provider) {
    if (!provider) {
      return;
    }

    setCustomName(provider.name || "");
    setCustomBaseUrl(provider.api_base || "");
    setCustomApiKey("");
    setCustomModelInput("");
    setCustomModelsText((provider.models || []).join("\n"));
    setDraftActiveModel((provider.models || [])[0] || "");
    clearMessages();
    setFeedback(`已载入 ${provider.name}，留空 API Key 时会复用已保存密钥。`);
  }

  function replaceDraftModels(nextModels) {
    setCustomModelsText(nextModels.join("\n"));
  }

  function appendDraftModel(modelName) {
    const normalized = modelName.trim();
    if (!normalized) {
      return;
    }
    if (draftModels.includes(normalized)) {
      setFeedback(`模型 ${normalized} 已存在。`);
      return;
    }
    replaceDraftModels([...draftModels, normalized]);
    setDraftActiveModel((current) => current || normalized);
    setCustomModelInput("");
  }

  function removeDraftModel(modelName) {
    const nextModels = draftModels.filter((item) => item !== modelName);
    replaceDraftModels(nextModels);
    if (draftActiveModel === modelName) {
      setDraftActiveModel(nextModels[0] || "");
    }
  }

  const testMutation = useMutation({
    mutationFn: (requestPayload) => testCustomProvider(requestPayload),
    onSuccess: (result) => {
      setTestDetail(result);
      setFeedback(result.reachable ? "测试通过。" : `测试失败：${result.detail}`);
    },
    onError: (error) => {
      setFeedback(error.message || "测试失败。");
    }
  });

  const saveProviderMutation = useMutation({
    mutationFn: (requestPayload) => addCustomProvider(requestPayload),
    onSuccess: async (result) => {
      setTestDetail(null);
      setFeedback(
        result.api_key_saved
          ? `已保存供应商：${result.name}`
          : `已保存供应商：${result.name}，但当前没有可用 API Key`
      );
      await modelQuery.refetch();
    },
    onError: (error) => {
      setFeedback(error.message || "保存失败。");
    }
  });

  const saveAndUseMutation = useMutation({
    mutationFn: async (requestPayload) => {
      const saved = await addCustomProvider(requestPayload);
      await selectModel({
        service_provider: requestPayload.name,
        model: draftActiveModel,
        api_base: requestPayload.api_base,
        api_key: requestPayload.api_key || undefined
      });
      return saved;
    },
    onSuccess: async (result) => {
      setFeedback(`已启用：${result.name} / ${draftActiveModel}`);
      await modelQuery.refetch();
    },
    onError: (error) => {
      setFeedback(error.message || "启用失败。");
    }
  });

  const quickUseMutation = useMutation({
    mutationFn: ({ providerName, modelName, apiBase }) =>
      selectModel({
        service_provider: providerName,
        model: modelName,
        api_base: apiBase
      }),
    onSuccess: async (_, variables) => {
      setFeedback(`当前模型已切换：${variables.providerName} / ${variables.modelName}`);
      await modelQuery.refetch();
    },
    onError: (error) => {
      setFeedback(error.message || "模型切换失败。");
    }
  });

  const deleteProviderMutation = useMutation({
    mutationFn: (name) => deleteCustomProvider(name),
    onSuccess: async (_, deletedName) => {
      setFeedback(`已删除供应商：${deletedName}`);
      await modelQuery.refetch();
    },
    onError: (error) => {
      setFeedback(error.message || "删除失败。");
    }
  });

  const exportMutation = useMutation({
    mutationFn: exportProviderConfig,
    onSuccess: (result) => {
      setExportText(JSON.stringify(result, null, 2));
      setFeedback(`已导出 ${result.custom_llm_providers?.length || 0} 个供应商配置。`);
    },
    onError: (error) => {
      setFeedback(error.message || "导出失败。");
    }
  });

  const importMutation = useMutation({
    mutationFn: ({ mode, parsed }) =>
      importProviderConfig({
        mode,
        custom_llm_providers: parsed.custom_llm_providers || [],
        current_llm_info: parsed.current_llm_info || null
      }),
    onSuccess: async (result, variables) => {
      setFeedback(`导入完成：${variables.mode === "merge" ? "合并" : "覆盖"} ${result.provider_count} 个供应商。`);
      await modelQuery.refetch();
      const latest = await exportProviderConfig();
      setExportText(JSON.stringify(latest, null, 2));
    },
    onError: (error) => {
      setFeedback(error.message || "导入失败。");
    }
  });

  const canTest = Boolean(customBaseUrl.trim() && draftActiveModel && (customApiKey.trim() || editedProvider));
  const canSave = Boolean(customName.trim() && customBaseUrl.trim() && draftModels.length > 0);
  const canSaveAndUse = canSave && Boolean(draftActiveModel);
  const testHint = classifyTestDetail(testDetail?.detail);
  const configFilePath = "storage/config_store.json";
  const exampleFilePath = "storage/config_store.example.json";

  function handleImport(mode) {
    try {
      const parsed = JSON.parse(importText);
      importMutation.mutate({ mode, parsed });
    } catch (error) {
      setFeedback(`导入失败：${error.message}`);
    }
  }

  return (
    <section className="agent-workspace">
      <header className="page-header">
        <div>
          <p className="hero-eyebrow">模型配置</p>
          <h2>管理供应商、模型和本地配置</h2>
          <p className="hero-copy">
            每个供应商都可以保存自己的 Base URL、API Key 和模型列表。配置会写入本地 JSON，重启后仍会保留。
          </p>
        </div>
      </header>

      <section className="agent-topbar-simple">
        <div className="agent-current-model">
          <p className="panel-eyebrow">当前启用</p>
          <h3>
            {currentInfo?.service_provider && currentInfo?.model
              ? `${currentInfo.service_provider} / ${currentInfo.model}`
              : "还没有启用模型"}
          </h3>
          <p className="simple-note">{currentInfo?.api_base || "先在下面保存一个供应商。"}</p>
        </div>
        <div className="agent-topbar-actions">
          <button type="button" className="secondary-button" onClick={applyPreset}>
            恢复阿里百炼预设
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={async () => {
              await modelQuery.refetch();
              setFeedback("已从配置文件重新加载。");
            }}
          >
            从配置文件刷新
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
          >
            {exportMutation.isPending ? "导出中..." : "导出当前配置"}
          </button>
          <span className="prototype-status">推荐流程：填 Base URL / Key，测试，保存，再启用。</span>
        </div>
      </section>

      <div className="model-config-grid">
        <section className="agent-panel">
          <div className="panel-heading">
            <div>
              <p className="panel-eyebrow">供应商表单</p>
              <h3>新增或编辑一个供应商</h3>
            </div>
          </div>

          <div className="agent-form">
            <div className="setting-col">
              <label className="field-label">供应商名称</label>
              <input
                value={customName}
                onChange={(event) => setCustomName(event.target.value)}
                placeholder="例如：阿里百炼 / 我的代理 / 备用站"
              />
            </div>

            <div className="setting-col">
              <label className="field-label">Base URL</label>
              <input
                value={customBaseUrl}
                onChange={(event) => setCustomBaseUrl(event.target.value)}
                placeholder={DASHSCOPE_PRESET.apiBase}
              />
            </div>

            <div className="setting-col">
              <label className="field-label">API Key</label>
              <input
                value={customApiKey}
                onChange={(event) => setCustomApiKey(event.target.value)}
                placeholder="填写你的 API Key，编辑已保存供应商时可留空"
              />
              {editedProvider?.api_key && !customApiKey ? (
                <p className="simple-note">当前供应商已保存 API Key，留空时会继续复用。</p>
              ) : null}
            </div>

            <div className="setting-col">
              <label className="field-label">模型名称</label>
              <div className="agent-form-row">
                <input
                  value={customModelInput}
                  onChange={(event) => setCustomModelInput(event.target.value)}
                  placeholder="例如：qwen-plus / qwen-flash / gpt-4.1 / claude-sonnet-4-20250514"
                />
                <button type="button" className="secondary-button" onClick={() => appendDraftModel(customModelInput)}>
                  添加模型
                </button>
              </div>
              <p className="simple-note">
                示例模型名：`qwen-plus`、`qwen-flash`、`gpt-4.1-mini`、`claude-sonnet-4-20250514`
              </p>
            </div>

            <div className="setting-col">
              <label className="field-label">已添加模型</label>
              {draftModels.length === 0 ? <div className="empty-block">先添加至少一个模型。</div> : null}
              {draftModels.length > 0 ? (
                <div className="saved-model-list">
                  {draftModels.map((modelName) => {
                    const isActive = modelName === draftActiveModel;
                    return (
                      <div key={modelName} className={isActive ? "selected-model-chip active" : "selected-model-chip"}>
                        <button type="button" className="selected-model-name" onClick={() => setDraftActiveModel(modelName)}>
                          {modelName}
                          {isActive ? "（默认）" : ""}
                        </button>
                        <button
                          type="button"
                          className="selected-model-remove"
                          onClick={() => removeDraftModel(modelName)}
                          aria-label={`移除 ${modelName}`}
                        >
                          ×
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </div>

            <div className="setting-col">
              <label className="field-label">默认启用模型</label>
              <select value={draftActiveModel} onChange={(event) => setDraftActiveModel(event.target.value)}>
                <option value="">暂不指定默认模型</option>
                {draftModels.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>

            <div className="agent-form-row">
              <button
                type="button"
                className="secondary-button"
                disabled={!canTest || testMutation.isPending}
                onClick={() =>
                  testMutation.mutate({
                    api_base: customBaseUrl.trim(),
                    api_key: customApiKey.trim(),
                    provider_name: customName.trim() || undefined,
                    model: draftActiveModel
                  })
                }
              >
                {testMutation.isPending ? "测试中..." : "测试当前模型"}
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={!canSave || saveProviderMutation.isPending}
                onClick={() =>
                  saveProviderMutation.mutate({
                    name: customName.trim(),
                    api_base: customBaseUrl.trim(),
                    api_key: customApiKey.trim(),
                    models: draftModels
                  })
                }
              >
                {saveProviderMutation.isPending ? "保存中..." : "仅保存配置"}
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={!canSaveAndUse || saveAndUseMutation.isPending}
                onClick={() =>
                  saveAndUseMutation.mutate({
                    name: customName.trim(),
                    api_base: customBaseUrl.trim(),
                    api_key: customApiKey.trim(),
                    models: draftModels
                  })
                }
              >
                {saveAndUseMutation.isPending ? "启用中..." : "保存并启用"}
              </button>
            </div>

            {feedback ? <div className="banner-info">{feedback}</div> : null}
            <div className="empty-block">
              配置文件路径：`{configFilePath}`
              <br />
              示例模板：`{exampleFilePath}`
              <br />
              你也可以直接编辑 `storage/config_store.json`，然后点击上方“从配置文件刷新”。
            </div>

            {testDetail ? (
              <div className="test-detail-card">
                <strong>测试详情</strong>
                <p className="stack-subtle">trace_id: {testDetail.trace_id || "-"}</p>
                <p className="stack-subtle">log_file: {testDetail.log_file || "-"}</p>
                <p className="stack-subtle">api_base: {testDetail.api_base || "-"}</p>
                <p className="stack-subtle">model: {testDetail.model || "-"}</p>
                {testHint ? <p className="stack-subtle">{testHint}</p> : null}
                <pre className="receipt-code">{testDetail.detail || "-"}</pre>
              </div>
            ) : null}
          </div>
        </section>

        <section className="agent-panel">
          <div className="panel-heading">
            <div>
              <p className="panel-eyebrow">已保存供应商</p>
              <h3>快速切换区</h3>
            </div>
          </div>

          {savedProviders.length === 0 ? <div className="empty-block">还没有保存任何供应商。</div> : null}

          <div className="stack-list">
            {savedProviders.map((provider) => (
              <article key={provider.name} className="stack-card">
                <div className="stack-title-row">
                  <strong>{provider.name}</strong>
                  <span>{currentInfo?.service_provider === provider.name ? "当前使用中" : "已保存"}</span>
                </div>
                <p className="stack-subtle">{provider.api_base}</p>
                <p className="stack-subtle">{provider.api_key ? "API Key 已保存" : "API Key 未保存"}</p>

                <div className="saved-model-list">
                  {(provider.models || []).map((modelName) => (
                    <button
                      key={modelName}
                      type="button"
                      className={
                        currentInfo?.service_provider === provider.name && currentInfo?.model === modelName
                          ? "mode-chip active"
                          : "mode-chip"
                      }
                      disabled={quickUseMutation.isPending}
                      onClick={() =>
                        quickUseMutation.mutate({
                          providerName: provider.name,
                          modelName,
                          apiBase: provider.api_base
                        })
                      }
                    >
                      启用 {modelName}
                    </button>
                  ))}
                </div>

                <div className="agent-form-row">
                  <button type="button" className="secondary-button" onClick={() => fillDraft(provider)}>
                    载入编辑
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={testMutation.isPending}
                    onClick={() =>
                      testMutation.mutate({
                        api_base: provider.api_base,
                        api_key: "",
                        provider_name: provider.name,
                        model: provider.models?.[0] || ""
                      })
                    }
                  >
                    测试第一个模型
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={deleteProviderMutation.isPending}
                    onClick={() => deleteProviderMutation.mutate(provider.name)}
                  >
                    删除
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>

      <div className="model-config-grid">
        <section className="agent-panel">
          <div className="panel-heading">
            <div>
              <p className="panel-eyebrow">导出配置</p>
              <h3>复制当前 JSON</h3>
            </div>
          </div>
          <div className="agent-form">
            <textarea
              className="config-json-area"
              rows={16}
              value={exportText}
              onChange={(event) => setExportText(event.target.value)}
              placeholder="点击上方“导出当前配置”后，这里会生成完整 JSON。"
            />
          </div>
        </section>

        <section className="agent-panel">
          <div className="panel-heading">
            <div>
              <p className="panel-eyebrow">导入配置</p>
              <h3>粘贴 JSON 后导入</h3>
            </div>
          </div>
          <div className="agent-form">
            <textarea
              className="config-json-area"
              rows={16}
              value={importText}
              onChange={(event) => setImportText(event.target.value)}
              placeholder="粘贴 config_store.json 的内容，或使用导出的 JSON。"
            />
            <p className="simple-note">
              {importPreview.error || `当前检测到 ${importPreview.count} 个供应商。可选择“合并导入”或“覆盖导入”。`}
            </p>
            <div className="agent-form-row">
              <button
                type="button"
                className="secondary-button"
                disabled={!importPreview.modeReady || importMutation.isPending}
                onClick={() => handleImport("merge")}
              >
                {importMutation.isPending ? "导入中..." : "合并导入"}
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={!importPreview.modeReady || importMutation.isPending}
                onClick={() => handleImport("replace")}
              >
                {importMutation.isPending ? "导入中..." : "覆盖导入"}
              </button>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}

# ThinkRAG Desktop API Contract

## Scope

This document records how the current desktop product surface maps to backend APIs.

- **Primary product path**: FastAPI + React (Vite) + Electron.
- **Legacy compatibility path**: `app.py` + `frontend/*.py` Streamlit pages are retained only as an opt-in shim/reference path.
- **Legacy entry gate**: Streamlit compatibility mode must be explicitly enabled with `KB_ALLOW_LEGACY_STREAMLIT=1`; it is not the default startup path.

## Product Surface to API Mapping

### React / Electron QA Workspace

- `POST /api/chat/query`
  - Input: `question`, `session_id`, required single-kb `kb_ids`, optional retrieval params (`top_k`, `top_n`, `response_mode`, `use_reranker`, `reranker_model`)
  - Output: answer text, normalized source list, evidence list, and scope echo fields
- `GET /api/chat/history`
  - Input: `session_id`
  - Output: chat message array
- `DELETE /api/chat/history`
  - Input: `session_id`
  - Output: cleared flag

### Knowledge Base Workspace

- `POST /api/kb`
  - Input: `kb_id`, `kb_name`
  - Output: created knowledge base metadata
- `GET /api/kb`
  - Output: knowledge base list
- `GET /api/kb/{kb_id}`
  - Output: one knowledge base detail
- `PUT /api/kb/{kb_id}`
  - Input: `kb_name`
  - Output: updated knowledge base metadata
- `DELETE /api/kb/{kb_id}`
  - Output: deleted flag
- `GET /api/kb/list`
  - Input: optional `kb_id`
  - Output: deduplicated knowledge items inside the selected knowledge base
- `GET /api/kb/folders`
  - Input: `kb_id`
  - Output: folder nodes for the selected knowledge base
- `POST /api/kb/file/import`
  - Input: multipart file list, `chunk_size`, `chunk_overlap`, `kb_id`, optional `relative_paths`, `import_mode`
  - Output: imported file metadata and indexed chunk count
- `POST /api/kb/web/import`
  - Input: `urls`, `chunk_size`, `chunk_overlap`, `kb_id`
  - Output: indexed chunk count and normalized URL list
- `DELETE /api/kb/docs`
  - Input: `doc_ids` or `paths`, plus `kb_id`
  - Output: deleted count
- `GET /api/kb/import-receipt/latest`
  - Input: `kb_id`
  - Output: latest import receipt summary
- `POST /api/kb/preview`
  - Input: `kb_id`, plus `doc_id` or `evidence_id`, optional `preview_locator`
  - Output: normalized preview payload
- `GET /api/kb/assets`
  - Input: `kb_id`
  - Output: asset list inside the selected knowledge base
- `GET /api/kb/assets/{asset_id}`
  - Input: `kb_id`
  - Output: one asset preview payload

### Agent Runtime Workspace

- `POST /api/agent/run`
  - Input: task question, session state, runtime mode, knowledge scope
  - Output: answer, plan, evidence, receipts, pending approvals, runtime state
- `GET /api/agent/session`
  - Input: `session_id`
  - Output: saved agent workspace snapshot
- `PUT /api/agent/session`
  - Input: `session_id`, workspace/ui state snapshot
  - Output: persisted snapshot metadata
- `POST /api/agent/session/reset`
  - Input: `session_id`
  - Output: reset confirmation
- `GET /api/agent/receipts`
  - Input: `session_id`, optional `limit`
  - Output: execution receipt list
- `GET /api/agent/pending`
  - Input: `session_id`
  - Output: pending approval actions
- `POST /api/agent/approvals`
  - Input: `action_id`, `approve`, optional `reason`
  - Output: updated approval/result payload
- `GET /api/agent/skills`
  - Output: available skill list

### Model / Settings

- `GET /api/model/options`
  - Output: provider, model, embedding, reranker candidates
- `GET /api/model/health`
  - Output: current model and runtime health summary
- `POST /api/model/select`
  - Input: provider/model selection and optional endpoint/key values
  - Output: current model snapshot
- `POST /api/model/providers`
  - Input: custom provider definition
  - Output: created provider metadata
- `DELETE /api/model/providers/{provider_name}`
  - Output: deleted flag
- `POST /api/model/providers/test`
  - Input: provider connection payload
  - Output: connectivity test result
- `GET /api/model/providers/export`
  - Output: exportable provider config
- `POST /api/model/providers/import`
  - Input: provider config import payload
  - Output: imported provider config summary
- `GET /api/settings`
  - Output: storage mode and current runtime settings
- `PUT /api/settings`
  - Input: `temperature`, `system_prompt`, `top_k`, `response_mode`, `use_reranker`, `top_n`, `embedding_model`, `reranker_model`
  - Output: persisted settings snapshot
- `GET /api/storage/info`
  - Output: storage/runtime compatibility information
- `GET /api/health`
  - Output: service readiness and capability checks

### Open Readonly API

- `GET /api/open/v1/me`
  - Output: current token identity
- `GET /api/open/v1/knowledge-bases`
  - Output: authorized active knowledge bases
- `POST /api/open/v1/search`
  - Input: `kb_id`, `question`, optional `top_k`
  - Output: structured hits and normalized evidence
- `POST /api/open/v1/answer`
  - Input: `kb_id`, `question`, optional readonly retrieval params (`top_k`, `top_n`, `response_mode`, `use_reranker`, `reranker_model`)
  - Output: readonly answer, evidence, and scope fields

## Runtime URL Resolution Notes

| Surface | Inputs / Priority |
|---|---|
| React renderer (browser) | `kbDesktop.apiBaseUrl` preload bridge -> `VITE_API_BASE_URL` -> `http://127.0.0.1:18080` |
| Electron main / packaged runtime (Node) | `KB_API_BASE_URL` -> legacy base URL aliases -> `KB_API_PORT` -> legacy port aliases -> default `18080` |
| Python API / diagnostic scripts | `KB_API_BASE_URL` -> legacy base URL aliases -> `KB_API_PORT` -> legacy port aliases -> default `18080` |

The browser renderer does **not** read Python/Node `process.env` aliases directly. If frontend dev server needs a non-default backend port, pass it through the preload bridge or set `VITE_API_BASE_URL`.

When `KB_API_BASE_URL` (or a legacy base URL alias) is explicitly set to a non-loopback remote service, Electron main only performs health checks against that remote API. It must **not** silently auto-start or fall back to a local `run_api.py` process; a failed health check should surface as an explicit remote API boot failure.

## Unified Response Envelope

All endpoints return:

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "uuid"
}
```

`code != 0` indicates failure; errors must still preserve this shape.

## Compatibility Notes

- Keep the existing Python RAG core (`server/*`) as-is where possible.
- Persist settings through current `CONFIG_STORE` keys to preserve behavior compatibility.
- `app.py` + `frontend/` remain available only as a legacy compatibility/reference path, not as the default product entry.
- Default local startup should go through `start_all.ps1` or `start_dev.ps1`, which boot FastAPI + React (Vite); use the legacy Streamlit shim only when `KB_ALLOW_LEGACY_STREAMLIT=1` is explicitly set.

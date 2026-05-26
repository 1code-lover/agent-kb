# ThinkRAG Desktop API Contract (Baseline)

## Scope

This document maps current Streamlit pages to desktop API contracts for the Electron + React migration.

## Page-to-API Mapping

### Query (`frontend/Document_QA.py`)

- `POST /api/chat/query`
  - Input: `question`, `session_id`, optional retrieval params (`top_k`, `top_n`, `response_mode`, `use_reranker`, `reranker_model`)
  - Output: answer text and normalized source list
- `GET /api/chat/history`
  - Input: `session_id`
  - Output: chat message array
- `DELETE /api/chat/history`
  - Input: `session_id`
  - Output: cleared flag

### KB File (`frontend/KB_File.py`)

- `POST /api/kb/file/import`
  - Input: multipart file list, `chunk_size`, `chunk_overlap`
  - Output: imported file metadata and indexed chunk count
- `GET /api/kb/list`
  - Output: deduplicated knowledge items

### KB Web (`frontend/KB_Web.py`)

- `POST /api/kb/web/import`
  - Input: `urls`, `chunk_size`, `chunk_overlap`
  - Output: indexed chunk count and normalized URL list

### KB Manage (`frontend/KB_Manage.py`)

- `DELETE /api/kb/docs`
  - Input: `doc_ids` or `paths`
  - Output: deleted count

### LLM / Embedding / Rerank (`frontend/Model_*.py`)

- `GET /api/model/options`
  - Output: provider, model, embedding, reranker candidates
- `POST /api/model/select`
  - Input: provider/model selection and optional endpoint/key values
  - Output: current model snapshot
- `PUT /api/settings`
  - Input: `temperature`, `system_prompt`, `top_k`, `response_mode`, `use_reranker`, `top_n`, `embedding_model`, `reranker_model`
  - Output: persisted settings snapshot

### Storage / Advanced (`frontend/Storage.py`, `frontend/Setting_Advanced.py`)

- `GET /api/settings`
  - Output: storage mode, current runtime settings, compatibility info
- `GET /api/health`
  - Output: service readiness and capability checks

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
- Keep `streamlit run app.py` as fallback during migration.

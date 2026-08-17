# NorthAgent / ThinkRAG

NorthAgent is a local-first knowledge assistant for macOS and Windows. The current product path uses **FastAPI + React + Electron + LlamaIndex**; `ThinkRAG` remains in several repository and Python package names for compatibility.

## Current capabilities

- Multiple local knowledge bases with explicit selection and default-deny query scope.
- Physical index isolation: the legacy `default` knowledge base remains under `storage/`, while non-default knowledge bases persist independent doc/index/vector stores under `storage/kbs/{kb_id}/`.
- File, Markdown, PDF, image OCR, and web import workflows with import receipts and evidence metadata.
- Embedding health diagnostics in `/api/health`; when the local BGE cache is missing, Knowledge Workspace can prepare it from the allow-listed ModelScope provider and automatically restart warmup.
- PaddleOCR geometry-aware reading order, PDF page markers, heuristic Markdown table reconstruction, and OCR quality metrics for keyword recall, line order, and table cells.
- React Knowledge Workspace and Agent Workspace packaged by Electron as **NorthAgent**.

## Development environment (macOS)

Use the verified conda environment. Do not use the Windows-created `.venv` on macOS.

```bash
conda activate agent-kb
# For non-interactive commands, prefer the absolute interpreter:
/opt/miniconda3/envs/agent-kb/bin/python --version
/opt/miniconda3/envs/agent-kb/bin/python -m pip install -r requirements.txt
```

The supported dependency baseline includes Python 3.12, `llama_index==0.11.19`, and `llama-index-core==0.11.19`.

## Run locally

### API

```bash
/opt/miniconda3/envs/agent-kb/bin/python run_api.py
```

The default endpoint is `http://127.0.0.1:18080` and health diagnostics are available at `/api/health`.

### Web UI

```bash
cd webapp
npm install
npm run dev
```

### Electron desktop

```bash
cd desktop
npm install
NORTHAGENT_PYTHON=/opt/miniconda3/envs/agent-kb/bin/python npm run dev
```

## Prepare the embedding cache

The UI exposes **Use ModelScope to prepare cache** when `/api/health` reports that the configured local embedding path is absent and runtime remote download is disabled.

CLI alternatives:

```bash
/opt/miniconda3/envs/agent-kb/bin/python scripts/prepare_embedding_model_cache.py \
  --model bge-small-zh-v1.5 --download --provider modelscope
```

The API recovery operation is intentionally restricted to the `modelscope` allow-list entry; it does not execute arbitrary shell commands or accept credentials.

## Verification

```bash
# Python, excluding explicitly slow cases
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"

# Web unit tests and production build
node --test webapp/src/**/*.test.js
npm run build --prefix webapp

# Electron tests
cd desktop
node --test src/*.test.js scripts/*.test.js
```

## Packaging status

Unsigned/ad-hoc local builds can be used for development verification. A formal macOS distribution still requires Apple Developer signing credentials, notarization, and installation regression checks; those external release gates are not considered complete in this repository state.

## Documentation

- [Chinese README](./README_zh.md)
- [Project status and commands](./docs/project.md)
- [Local multi-KB product documents](./docs/20260722-local-multi-kb-assistant/)

## License

[MIT](./LICENSE)

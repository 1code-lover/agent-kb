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
/opt/miniconda3/envs/agent-kb/bin/python -m pip install -r requirements-runtime.txt
# If you need full local OCR / legacy extras:
/opt/miniconda3/envs/agent-kb/bin/python -m pip install -r requirements.txt
```

The supported runtime baseline includes Python 3.12 and a LlamaIndex 0.11.19 stack centered on `llama-index-core==0.11.19` plus the explicit integration packages used by this repo. `requirements-runtime.txt` intentionally avoids the top-level `llama_index` metapackage because it drags OpenAI / LlamaCloud / LlamaParse extras into the default API image; `requirements.txt` is the fuller local profile that keeps OCR, Streamlit-era compatibility packages, and other heavier extras.

The shared runtime/test baseline also pins `httpx==0.27.2`. This is intentional: FastAPI 0.104 / Starlette 0.27 `TestClient` is not compatible with `httpx 0.28+`. If local pytest collection or API tests fail with `Client.__init__() got an unexpected keyword argument 'app'`, reinstall the selected profile (`python -m pip install -r requirements-runtime.txt`) or minimally run `python -m pip install httpx==0.27.2`.

## Run locally

### Windows unified dev entry

```powershell
powershell -File .\start_all.ps1
powershell -File .\start_all.ps1 -BackendPort 18095 -FrontendPort 5176
powershell -File .\start_all.ps1 -Stop
```

`start_all.ps1` delegates to `start_dev.ps1` and treats **FastAPI + React (Vite)** as the default development path. The legacy `app.py` + `frontend/` path remains in the repository only for compatibility/reference and is no longer the primary entry. If you really need the historical Streamlit UI, first install `requirements.txt`, then set `KB_ALLOW_LEGACY_STREAMLIT=1` before running `python -m streamlit run app.py`.

### Install desktop dev dependencies via script

```powershell
powershell -File .\scripts\dev-all.ps1 -InstallDeps
powershell -File .\scripts\dev-all.ps1 -InstallDeps -InstallProfile full
```

By default these scripts install `requirements-runtime.txt`; use `-InstallProfile full` only when you explicitly need the heavier local profile.

### Docker runtime / eval profiles

```bash
docker build -t agent-kb-api --build-arg INSTALL_PROFILE=runtime .
docker run --rm -p 18080:18080 agent-kb-api

docker build -t agent-kb-eval --build-arg INSTALL_PROFILE=eval .
docker run --rm -e APP_RUNTIME_MODE=eval -v "${PWD}:/app" agent-kb-eval
```

`INSTALL_PROFILE` now controls which dependency set is baked into the image (`runtime`, `full`, `dev`, `prod`, or `eval`). `APP_RUNTIME_MODE` controls which process the container starts (`api`, `prod`, or `eval`). The default is `INSTALL_PROFILE=runtime` + API mode so Docker matches the local FastAPI baseline; `eval` remains available for semireal regression images. `requirements-minimal.txt` is kept only as a deprecated local compatibility alias and is not a Docker install profile.

`docker run -p 18080:18080` above is only a fixed-port manual example. For repeatable smoke/regression runs, prefer `python scripts/docker_smoke.py --install-profile smoke --app-runtime-mode api`: by default it asks Docker to assign a loopback host port and then resolves it via `docker port`, so the helper does not turn `18080` into an implied source of truth. Pass `--host-port` only when you explicitly need a fixed published host port.

### macOS / manual API entry

```bash
/opt/miniconda3/envs/agent-kb/bin/python run_api.py
```

The default local fallback endpoint is `http://127.0.0.1:18080` and health diagnostics are available at `/api/health`. For client-side probes, diagnostic scripts, and eval harnesses, prefer `KB_API_BASE_URL`; if you only need to change the local port, set `KB_API_PORT`. `run_api.py` itself still accepts `NORTHAGENT_API_PORT` / `THINKRAG_API_PORT` / `FOXGLOVE_API_PORT` for compatibility.

### Web UI

```bash
cd webapp
npm install
npm run dev
```

When the frontend is started independently, export `VITE_API_BASE_URL` if the backend does not use the default fallback `18080` port. The browser renderer does **not** read Python/Node-side `KB_API_BASE_URL` aliases directly.

### Electron desktop

```bash
cd desktop
npm install
NORTHAGENT_PYTHON=/opt/miniconda3/envs/agent-kb/bin/python npm run dev
```

For a single-command desktop dev workflow on Windows, use `scripts/dev-all.ps1 -BackendPort <api_port> -FrontendPort <web_port>` so Electron, web, and API stay on the same runtime contract. The script now delegates API/web startup to `start_dev.ps1`, manages a dedicated desktop PID under `.dev-runtime/desktop.pid`, and supports `powershell -File .\scripts\dev-all.ps1 -Stop` for one-shot shutdown.

If you only want to launch Web + Electron without booting FastAPI, use:

```powershell
powershell -File .\scripts\desktop-dev.ps1
powershell -File .\scripts\desktop-dev.ps1 -BackendPort 18095 -FrontendPort 5176
powershell -File .\scripts\desktop-dev.ps1 -ApiBaseUrl https://api.example.com:18443 -FrontendPort 5176
powershell -File .\scripts\desktop-dev.ps1 -Stop
powershell -File .\scripts\desktop-dev.ps1 -InstallDeps
powershell -File .\scripts\desktop-dev.ps1 -InstallDeps -InstallProfile full
```

`desktop-dev.ps1` now accepts `-BackendPort/-FrontendPort`, `-ApiBaseUrl`, and `-Stop` as well. It aligns `VITE_API_BASE_URL`, `KB_API_BASE_URL` / `KB_API_PORT`, `KB_WEB_URL`, the `NORTHAGENT_*` / `THINKRAG_*` / `FOXGLOVE_*` compatibility aliases, and the desktop Python runtime overrides to the same contract, manages helper-specific PID/log files under `.dev-runtime/` and `logs/`, and can point the compatibility helper workflow at an explicit remote API such as `https://api.example.com:18443`. An explicit `-ApiBaseUrl` must be an absolute `http(s)` URL; invalid values are rejected before the helper starts Web / Electron. It still does **not** start FastAPI for you; prefer `scripts/dev-all.ps1` for the unified primary path.

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
# Startup / requirements profile contracts
python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_requirements_profiles.py tests/scripts/test_cleanup_local_artifacts.py -q

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

Unsigned/ad-hoc local builds can be used for development verification. The packaged desktop runtime now bundles `requirements-runtime.txt` as its dependency baseline. A formal macOS distribution still requires Apple Developer signing credentials, notarization, and installation regression checks; those external release gates are not considered complete in this repository state.

- Local desktop build helpers: `powershell -File .\scripts\build-desktop.ps1 -InstallDeps` and `bash ./scripts/build-desktop.sh --install-deps`. They prefer `KB_PYTHON`, default to the `runtime` install profile, and only prepare `webapp/dist` plus the Electron bundle for local verification. They do **not** replace the formal release lane.
- Current formal mac packaging / release lane: `cd desktop && npm run build:mac && npm run verify:package` for ad-hoc local package verification; `cd desktop && npm run release:preflight && npm run release:mac` for the strict notarization-required lane. `release:mac` is the current source of truth for signed mac distribution because it chains `build:preflight`, strict `release:preflight`, `verify:package`, and `verify:mac-release`.
- `scripts/package-python-runtime.ps1` remains an API-only PyInstaller compatibility helper, not the primary Electron desktop packaging lane.

## Documentation

- [Chinese README](./README_zh.md)
- [Project status and commands](./docs/project.md)

Historical ledgers under `docs/2026.../` intentionally keep the exact commands, ports, and output paths used during those runs (including many `--api-base http://127.0.0.1:18080` examples). Treat them as evidence snapshots, not the current source of truth for runtime contracts.
- [Local multi-KB product documents](./docs/20260722-local-multi-kb-assistant/)

## License

[MIT](./LICENSE)

## Migration, read-only Agent API, and OCR/cache operations

The current local API also provides:

- `GET/POST /api/kb/migration/{status,scan,start,rollback}` for dry-run inspection, verified backups, retrying failed items, and batch rollback.
- Read-only Agent API: `GET /api/open/v1/me`, `GET /api/open/v1/knowledge-bases`, `POST /api/open/v1/search`, and `POST /api/open/v1/answer`. Bearer tokens are scoped to active KB IDs, and token management is loopback-only.
- Token CLI: `scripts/manage_access_tokens.py create|list|revoke`. Plaintext is returned only at creation; the store keeps only an HMAC digest. Never inject the local administrator key into the renderer or frontend bundle.
- Embedding cache operations: `GET /api/embedding/cache`, `POST /api/embedding/cache/preflight`, `POST /api/embedding/cache/prepare`, and `POST /api/embedding/cache/cancel`. Insufficient disk space returns HTTP `507`; status includes phase, byte progress, estimated/exact mode, and cancellation state.
- OCR benchmark tools: `scripts/build_ocr_scan_benchmark.py` and `scripts/eval_ocr_scan_benchmark.py`. The checked-in assets are an offline deterministic baseline; real PaddleOCR execution is a separate slow/runtime check.

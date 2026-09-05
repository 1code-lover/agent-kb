# HowToDownloadModels（compatibility redirect）

## Current status

This file is kept only as a **root-level compatibility redirect** so historical links do not continue treating it as the current model download guide.

- **Current source of truth**: `docs/guide/HowToDownloadModels.md`
- **Current default model root**: `localmodels/` under the repo root unless `KB_MODEL_ROOT` (or desktop runtime aliases) overrides it
- **Recommended path today**: use `python -m scripts.prepare_embedding_model_cache` first instead of copying old ad-hoc HuggingFace shell snippets back into this file

## What to read instead

If you need the current embedding cache workflow, provider choices, or manual fallback commands, go directly to:

- `docs/guide/HowToDownloadModels.md`

That guide now covers:

1. the recommended `scripts.prepare_embedding_model_cache` workflow;
2. the default `localmodels/BAAI/...` cache layout;
3. HuggingFace / ModelScope provider options;
4. when to use manual `huggingface-cli download` as a fallback.

## Why this file still exists

1. historical docs and old indexes may still point to `docs/HowToDownloadModels.md`;
2. deleting it outright would break those links and add more docs-root noise;
3. therefore it is intentionally reduced to a redirect instead of another drifting duplicate.

## Boundary

- do **not** restore the old root-level download instructions here;
- do **not** treat this file as the current canonical guide;
- if the model download or cache contract changes, update `docs/guide/HowToDownloadModels.md`.

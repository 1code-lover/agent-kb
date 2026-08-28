# HowToUsePythonVirtualEnv（compatibility redirect）

## Current status

This file is kept only as a **root-level compatibility redirect** so that historical links do not keep serving an outdated Streamlit-first setup guide.

- **Current source of truth**: `docs/guide/HowToUsePythonVirtualEnv.md`
- **Current primary local entry**: FastAPI + React (Vite)
- **Recommended Python profile**: `requirements-runtime.txt`
- **Legacy Streamlit path**: allowed only when `KB_ALLOW_LEGACY_STREAMLIT=1` is explicitly set

## What to use now

If you want the current project setup flow, open:

- `docs/guide/HowToUsePythonVirtualEnv.md`

That guide contains the maintained instructions for:

1. creating and activating a virtual environment;
2. installing `requirements-runtime.txt` first, then `requirements.txt` only when full local extras are needed;
3. starting the current local stack through `start_all.ps1` / `start_dev.ps1` or `python run_api.py`;
4. opting into the historical Streamlit UI only with `KB_ALLOW_LEGACY_STREAMLIT=1`.

## Why this file still exists

1. historical docs and external links may still point to `docs/HowToUsePythonVirtualEnv.md`;
2. deleting it outright would create broken links and more ambiguity;
3. keeping it as a redirect prevents the old “install everything then run Streamlit” workflow from drifting back into the default narrative.

## Explicit boundary

- Do **not** treat this file as the maintained environment guide;
- do **not** restore `python -m streamlit run app.py` as the default startup path here;
- if the environment/setup contract changes, update `docs/guide/HowToUsePythonVirtualEnv.md` instead of copying full instructions back into this file.

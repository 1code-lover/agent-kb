# ThinkRAG Multi-Industry Knowledge Base Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Transform ThinkRAG from single KB to multi-industry isolated KB system.

**Architecture:** Industry namespace as core. IndexManager loads independent indexes per industry. Frontend adds industry selector. Storage dirs isolated by industry. New industries via config only.

**Tech Stack:** LlamaIndex 0.11.19, Streamlit 1.39.0, Python 3.10+

---

## File Change Overview

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | config.py | Add INDUSTRIES config, STORAGE_ROOT, DATA_ROOT |
| Create | server/industry_manager.py | Industry CRUD manager |
| Modify | server/index.py | IndexManager industry param |
| Modify | server/engine.py | industry param in query engine |
| Modify | server/prompt.py | industry-specific prompt templates |
| Modify | server/utils/file.py | get_save_dir(industry) |
| Modify | frontend/state.py | industry state + switch_industry() |
| Modify | frontend/KB_File.py | industry context |
| Modify | frontend/KB_Manage.py | industry indicator |
| Modify | frontend/KB_Web.py | industry context |
| Modify | frontend/Document_QA.py | industry in query engine |
| Create | frontend/KB_Industry.py | industry management page |
| Modify | app.py | register KB_Industry page + industry sidebar |

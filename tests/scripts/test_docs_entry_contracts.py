from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import subprocess

from scripts.build_audit_metrics_snapshot import (
    CHAT_REGRESSION_ARGS,
    DOCS_CONTRACT_ARGS,
    DOCKER_BUNDLE_ARGS,
    DOCKER_HELPER_ARGS,
    FULL_NON_SLOW_ARGS,
    PROMPT_BUNDLE_1_ARGS,
    PROMPT_BUNDLE_2_ARGS,
    PROMPT_BUNDLE_3_ARGS,
)
from scripts.validate_rag_quality_fixtures import summarize_eval_cases

REPO_ROOT = Path(__file__).resolve().parents[2]
SEMIREAL_FOLLOW_UP_ARGS = (
    "tests/api/test_chat_service.py tests/api/test_chat_markdown_qa_semireal.py "
    "tests/api/test_chat_pdf_semireal.py tests/api/test_chat_image_ocr_semireal.py"
)


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")



def test_readmes_keep_fastapi_react_as_primary_entry() -> None:
    english_paths = ("README.md", "README_en.md")
    for relative_path in english_paths:
        content = _read(relative_path)
        assert "start_all.ps1" in content
        assert "start_dev.ps1" in content
        assert "FastAPI + React (Vite)" in content
        assert "app.py` + `frontend/`" in content
        assert "no longer the primary entry" in content
        assert "KB_ALLOW_LEGACY_STREAMLIT=1" in content
        assert "desktop-dev.ps1 -Stop" in content
        assert "desktop-dev.ps1 -ApiBaseUrl https://api.example.com:18443 -FrontendPort 5176" in content
        assert "KB_API_BASE_URL" in content
        assert "KB_WEB_URL" in content
        assert "absolute `http(s)` URL" in content
        assert "compatibility helper" in content

    zh_content = _read("README_zh.md")
    assert "start_all.ps1" in zh_content
    assert "start_dev.ps1" in zh_content
    assert "FastAPI + React（Vite）" in zh_content
    assert "app.py` + `frontend/`" in zh_content
    assert "不再是当前主入口" in zh_content
    assert "KB_ALLOW_LEGACY_STREAMLIT=1" in zh_content
    assert "desktop-dev.ps1 -Stop" in zh_content
    assert "desktop-dev.ps1 -ApiBaseUrl https://api.example.com:18443 -FrontendPort 5176" in zh_content
    assert "KB_API_BASE_URL" in zh_content
    assert "KB_WEB_URL" in zh_content
    assert "绝对 `http(s)` URL" in zh_content
    assert "兼容 helper" in zh_content



def test_project_and_runbooks_mark_legacy_entry_as_non_primary() -> None:
    project_content = _read("docs/project.md")
    assert "FastAPI + React" in project_content
    assert "app.py + frontend/ (旧 Streamlit 入口，保留)" in project_content
    assert "仅保留为 legacy 参考入口" in project_content
    assert "KB_ALLOW_LEGACY_STREAMLIT=1" in project_content
    assert "scripts/dev-all.ps1" in project_content
    assert "storage/kbs/{kb_id}/" in project_content
    assert "managed_count = 0" in project_content
    assert "根目录文件模式" in project_content
    assert "当前面试 / 汇报口播主稿" in project_content
    assert "当前整改优先级 / Route A 与 Route B 切换总览" in project_content
    assert "当前完整面试总览稿（串联讲稿 / 状态 / 证据 / 边界）" in project_content
    assert "当前扩展问答主稿（追问 / 指标 / 反质疑回答）" in project_content
    assert "当前导航版（只负责跳转，不再承载长正文）" in project_content
    assert "--include-directories" in project_content
    assert "多知识库仍是逻辑隔离，不是物理多索引隔离" not in project_content
    assert "README 与实际主线有代际差异" not in project_content

    root_runbook = _read("docs/desktop_runbook.md")
    assert "兼容跳转页" in root_runbook
    assert "docs/guide/desktop_runbook.md" in root_runbook
    assert "source of truth" in root_runbook
    assert "dev-all.ps1" in root_runbook
    assert "desktop-dev.ps1 -Stop" in root_runbook
    assert "兼容 helper" in root_runbook
    assert "app.py` + `frontend/` 仍保留为 legacy" in root_runbook
    assert "KB_ALLOW_LEGACY_STREAMLIT=1" in root_runbook

    guide_runbook = _read("docs/guide/desktop_runbook.md")
    assert "当前 source of truth" in guide_runbook
    assert "docs/desktop_runbook.md` 仅保留为根目录兼容跳转页" in guide_runbook
    assert "dev-all.ps1" in guide_runbook
    assert "desktop-dev.ps1" in guide_runbook
    assert "desktop-dev.ps1 -Stop" in guide_runbook
    assert "desktop-dev.ps1 -ApiBaseUrl https://api.example.com:18443 -FrontendPort 5176" in guide_runbook
    assert "KB_WEB_URL" in guide_runbook
    assert "绝对 `http(s)` URL" in guide_runbook
    assert "兼容 helper" in guide_runbook
    assert "app.py` + `frontend/` 仍保留为 legacy" in guide_runbook
    assert "KB_ALLOW_LEGACY_STREAMLIT=1" in guide_runbook

    root_download = _read("docs/HowToDownloadModels.md")
    assert "compatibility redirect" in root_download
    assert "docs/guide/HowToDownloadModels.md" in root_download
    assert "scripts.prepare_embedding_model_cache" in root_download
    assert "localmodels/BAAI/" in root_download

    guide_download = _read("docs/guide/HowToDownloadModels.md")
    assert "当前 source of truth" in guide_download
    assert "python -m scripts.prepare_embedding_model_cache" in guide_download
    assert "--provider modelscope" in guide_download
    assert "localmodels/BAAI/bge-small-zh-v1.5" in guide_download
    assert "huggingface-cli download --resume-download BAAI/bge-small-zh-v1.5" in guide_download
    assert "KB_MODEL_ROOT" in guide_download


def test_desktop_api_contract_marks_react_electron_as_primary_and_streamlit_as_opt_in_legacy() -> None:
    content = _read("docs/spec/desktop_api_contract.md")

    assert "FastAPI + React (Vite) + Electron" in content
    assert "app.py` + `frontend/*.py`" in content
    assert "KB_ALLOW_LEGACY_STREAMLIT=1" in content
    assert "not the default startup path" in content
    assert "start_all.ps1" in content
    assert "start_dev.ps1" in content
    assert "POST /api/agent/run" in content
    assert "POST /api/open/v1/answer" in content
    assert "required single-kb `kb_ids`" in content
    assert "React renderer (browser)" in content
    assert "Electron main / packaged runtime (Node)" in content
    assert "Python API / diagnostic scripts" in content
    assert "The browser renderer does **not** read Python/Node `process.env` aliases directly." in content
    assert "Keep `streamlit run app.py` as fallback during migration" not in content



def test_root_desktop_api_contract_is_only_a_compatibility_redirect() -> None:
    content = _read("docs/desktop_api_contract.md")

    assert "兼容跳转说明" in content
    assert "docs/spec/desktop_api_contract.md" in content
    assert "source of truth" in content
    assert "FastAPI + React (Vite) + Electron" in content
    assert "KB_ALLOW_LEGACY_STREAMLIT=1" in content
    assert "current Streamlit pages" not in content
    assert "frontend/Document_QA.py" not in content
    assert "Keep `streamlit run app.py` as fallback during migration" not in content



def test_docs_explain_port_and_api_base_contract() -> None:
    for relative_path in ("README.md", "README_en.md", "README_zh.md", "docs/project.md"):
        content = _read(relative_path)
        assert "18080" in content
        assert "VITE_API_BASE_URL" in content
        assert "KB_API_BASE_URL" in content

    project_content = _read("docs/project.md")
    assert "浏览器端只认 Electron preload bridge 注入的 `apiBaseUrl` 与 `VITE_API_BASE_URL`" in project_content
    assert "scripts/dev-runtime-helpers.ps1" in project_content
    assert "frontend loopback URL" in project_content

    for relative_path in ("docs/desktop_runbook.md", "docs/guide/desktop_runbook.md"):
        content = _read(relative_path)
        assert "18080" in content
        assert "5173" in content
        assert "KB_API_BASE_URL" in content
        assert "KB_API_PORT" in content
        assert "-BackendPort" in content
        assert "-FrontendPort" in content

    guide_runbook = _read("docs/guide/desktop_runbook.md")
    assert "-ApiBaseUrl" in guide_runbook
    assert "https://api.example.com:18443" in guide_runbook
    assert "scripts/dev-runtime-helpers.ps1" in guide_runbook
    assert "优先改 helper" in guide_runbook



def test_project_doc_separates_current_status_from_history_ledgers() -> None:
    content = _read("docs/project.md")

    assert "快速阅读建议：如果只想了解当前主线" in content
    assert "## 4. 当前主线状态（快速阅读）" in content
    assert "### 4.0 2026-08-24 当前可信快照" in content
    assert "## 5. 历史测试与验证账本" in content
    assert "## 8. 历史提交账本" in content
    assert "以下 8.1 / 8.2 仅保留阶段性归档纪要" in content
    assert "### 8.1 2026-08-17：物理隔离、Embedding 缓存恢复与 OCR 版面增强" in content
    assert "### 8.2 2026-08-18：迁移、只读开放接口、OCR 基准和 Embedding 缓存" in content
    assert "不应回推成当前唯一 source of truth" in content
    assert "当前唯一有效口径" in content
    assert "\n## 2026-08-17" not in content
    assert "\n## 2026-08-18" not in content



def test_runbooks_do_not_hardcode_default_ports_as_the_only_dev_all_outcome() -> None:
    for relative_path in ("docs/desktop_runbook.md", "docs/guide/desktop_runbook.md"):
        content = _read(relative_path)
        assert "This starts:" not in content
        assert "如果传入 `-BackendPort 18095 -FrontendPort 5176`" in content
        assert "不是唯一有效口径" in content



def test_project_and_runbooks_document_docker_smoke_port_contract() -> None:
    project_content = _read("docs/project.md")
    assert "scripts/docker_smoke.py" in project_content
    assert "Docker 分配 loopback host port" in project_content or "Docker 自分配 loopback host port" in project_content
    assert "docker run -p 18080:18080" in project_content

    for relative_path in ("docs/desktop_runbook.md", "docs/guide/desktop_runbook.md"):
        content = _read(relative_path)
        assert "scripts/docker_smoke.py" in content
        assert "docker port" in content
        assert "18080:18080" in content



def test_readmes_document_docker_install_profile_vs_runtime_mode() -> None:
    for relative_path in ("README.md", "README_en.md"):
        content = _read(relative_path)
        assert "INSTALL_PROFILE=runtime" in content
        assert "APP_RUNTIME_MODE=eval" in content
        assert "INSTALL_PROFILE` now controls which dependency set is baked into the image" in content
        assert "requirements-minimal.txt" in content
        assert "not a Docker install profile" in content
        assert "scripts/docker_smoke.py" in content
        assert "Docker to assign a loopback host port" in content
        assert "--host-port" in content

    zh_content = _read("README_zh.md")
    assert "INSTALL_PROFILE=runtime" in zh_content
    assert "APP_RUNTIME_MODE=eval" in zh_content
    assert "INSTALL_PROFILE` 用来决定镜像里安装哪套依赖" in zh_content
    assert "requirements-minimal.txt" in zh_content
    assert "不再作为 Docker install profile" in zh_content
    assert "scripts/docker_smoke.py" in zh_content
    assert "Docker 自动分配一个 loopback host port" in zh_content
    assert "--host-port" in zh_content



def test_readmes_and_project_explain_local_build_vs_formal_release_lanes() -> None:
    for relative_path in ("README.md", "README_en.md"):
        content = _read(relative_path)
        assert "build-desktop.ps1" in content
        assert "scripts/build-desktop.sh" in content
        assert "KB_PYTHON" in content
        assert "release:mac" in content
        assert "verify:package" in content
        assert "scripts/package-python-runtime.ps1" in content
        assert "current source of truth" in content

    zh_content = _read("README_zh.md")
    assert "build-desktop.ps1" in zh_content
    assert "scripts/build-desktop.sh" in zh_content
    assert "KB_PYTHON" in zh_content
    assert "release:mac" in zh_content
    assert "verify:package" in zh_content
    assert "scripts/package-python-runtime.ps1" in zh_content
    assert "当前 source of truth" in zh_content

    project_content = _read("docs/project.md")
    assert "scripts/build-desktop.ps1" in project_content
    assert "scripts/build-desktop.sh" in project_content
    assert "requirements-runtime.txt" in project_content
    assert "KB_PYTHON" in project_content
    assert "desktop/package.json" in project_content
    assert "build:mac" in project_content
    assert "release:mac" in project_content
    assert "scripts/package-python-runtime.ps1" in project_content



def test_desktop_design_and_release_checklist_keep_runtime_release_boundary() -> None:
    root_design = _read("docs/desktop_project_design.md")
    assert "兼容跳转页" in root_design
    assert "docs/spec/desktop_project_design.md" in root_design
    assert "source of truth" in root_design
    assert "本地 desktop build helper" in root_design
    assert "requirements-runtime.txt" in root_design
    assert "release:mac" in root_design
    assert "verify:package" in root_design
    assert "API-only PyInstaller 兼容 helper" in root_design
    assert "llama-index-core==0.11.19" in root_design
    assert "顶层 `llama_index` metapackage" in root_design

    spec_design = _read("docs/spec/desktop_project_design.md")
    assert "运行手册：`docs/guide/desktop_runbook.md`" in spec_design
    assert "回归清单：`docs/test/desktop_regression_checklist.md`" in spec_design
    assert "release:mac" in spec_design
    assert "verify:package" in spec_design

    checklist = _read("docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-release-checklist.md")
    assert "llama-index-core=0.11.19" in checklist
    assert "llama-index=0.11.19" not in checklist
    assert "requirements-runtime.txt" in checklist
    assert "KB_API_BASE_URL" in checklist
    assert "http://127.0.0.1:18080" in checklist
    assert "固定示例" in checklist


def test_20260817_requirement_docs_use_current_runtime_baseline_language() -> None:
    for relative_path in (
        "docs/20260817-kb-migration-agent-ocr-cache/20260817-kb-migration-agent-ocr-cache-prd.md",
        "docs/20260817-kb-migration-agent-ocr-cache/20260817-kb-migration-agent-ocr-cache-plan.md",
        "docs/20260817-kb-migration-agent-ocr-cache/20260817-kb-migration-agent-ocr-cache-test-plan.md",
    ):
        content = _read(relative_path)
        assert "llama-index-core==0.11.19" in content
        assert "llama_index==0.11.19" not in content
        assert "top-level `llama_index` metapackage" in content or "顶层 `llama_index` metapackage" in content



def test_interview_docs_point_to_current_product_path() -> None:
    brief_doc = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md")
    assert "这是当前**面试 / 汇报口播主稿**" in brief_doc
    assert "30 秒 / 2 分钟回答优先看本文" in brief_doc
    assert "docs/interview/ThinkRAG_面试问答.md" in brief_doc
    assert "20260821-project-audit-remediation-status-matrix.md" in brief_doc

    current_qa = _read("docs/interview/ThinkRAG_面试问答.md")
    assert "本文角色：**扩展问答主稿**" in current_qa
    assert "20260825-p0-p2-status-closure-interview-complete-guide.md" in current_qa
    assert "20260821-project-audit-remediation-interview-brief.md" in current_qa
    assert "20260821-project-audit-remediation-report-script.md" in current_qa
    assert "需要先一次性过完整讲稿时" in current_qa
    assert "需要 30 秒 / 2 分钟口播时" in current_qa
    assert "需要标准 5 分钟固定汇报时" in current_qa
    assert "本文更适合作为**追问稿 / 指标解释稿**，不是标准 5 分钟汇报底稿" in current_qa
    assert "FastAPI + React + Electron + LlamaIndex" in current_qa
    assert "能力完成度高于工程完成度" in current_qa
    assert f"{_pytest_collected_test_count(CHAT_REGRESSION_ARGS)} passed" in current_qa
    assert f"{_pytest_collected_test_count(DOCS_CONTRACT_ARGS)} passed" in current_qa
    assert "refusal_summary" in current_qa
    assert "Refusal 覆盖摘要" in current_qa
    assert "三层闭环" in current_qa
    assert "## 一、追问场景下的 1 分钟项目介绍" in current_qa
    assert "这一节保留给“请你先快速介绍一下项目”这类追问场景使用" in current_qa
    assert "## 二、追问场景下的 3 分钟项目介绍" in current_qa
    assert "这一节适合在面试追问里做展开说明" in current_qa
    assert "## 十三、如果要把 1~30 轮问题压缩成 6 个主题" in current_qa
    assert "主题 A：主能力已经闭环" in current_qa
    assert "主题 F：材料层已经基本闭环，但引用口径必须统一" in current_qa
    assert "## 十四、如果临场被要求把追问稿压成 5 分钟补充说法" in current_qa
    assert "我已经把主能力闭环做出来了" in current_qa
    assert "93 passed" not in current_qa
    assert "22 passed" not in current_qa
    assert "LlamaIndex + Streamlit" not in current_qa

    closure_master = _read("docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md")
    assert "20260825-p0-p2-status-closure-plan.md" in closure_master
    assert "20260825-p0-p2-status-closure-interview-complete-guide.md" in closure_master
    assert "先用 complete-guide 一次性过完整讲稿" in closure_master
    assert "需要决定“下一步先改什么、后改什么”" in closure_master

    closure_plan = _read("docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-plan.md")
    assert "Route A 继续做工程收口，Route B 负责稳定表达" in closure_plan
    assert "A1 heuristic 降复杂度 → A2 refusal hard negatives → A3 startup/docker/配置统一 → A4 root backlog 减法" in closure_plan
    assert "managed_count = 0" in closure_plan

    nav_doc = _read("docs/interview/ThinkRAG_面试全集_合并版.md")
    assert "当前导航版" in nav_doc
    assert "只负责**导航和跳转**" in nav_doc
    assert "20260825-p0-p2-status-closure-interview-complete-guide.md" in nav_doc
    assert "先一次性过完整讲稿总览" in nav_doc
    assert "FastAPI + React + Electron + LlamaIndex" in nav_doc
    assert "历史阶段材料" in nav_doc
    assert "20260821-project-audit-remediation-status-matrix.md" in nav_doc
    assert "第十三、十四节" in nav_doc

    compatibility_doc = _read("docs/ThinkRAG_面试问答.md")
    assert "兼容跳转说明" in compatibility_doc
    assert "docs/interview/ThinkRAG_面试问答.md" in compatibility_doc
    assert "FastAPI + React + Electron + LlamaIndex" in compatibility_doc

    material_pack = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-material-pack.md")
    assert "如果你只想打开 **一份审计入口文件**" in material_pack
    assert "它更适合作为**审计 / 复盘 / 维护入口包**" in material_pack
    assert "不再重复维护长段口播正文" in material_pack
    assert "详细口播优先看 `interview-brief` 与 `report-script`" in material_pack

    issues_summary = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md")
    assert "本文是 **1~12 项问题总表 + 30 轮审计压缩索引**" in issues_summary
    assert "如果需要 5 分钟长讲法，优先看 `20260821-project-audit-remediation-report-script.md`" in issues_summary
    assert "统一收口到 `20260821-project-audit-remediation-audit-evidence.md`" in issues_summary
    assert "## 补充更新（2026-08-22 refusal contract gate）" not in issues_summary

    audit_evidence = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-audit-evidence.md")
    assert "审计证据附录 / 历史增量记录" in audit_evidence
    assert "20260821-project-audit-remediation-issues-summary.md" in audit_evidence
    assert "## 补充更新（2026-08-22 refusal contract gate）" in audit_evidence
    assert "## Desktop build/package/release four-layer boundary" in audit_evidence

    closure_script = _read("docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md")
    assert "20260825-p0-p2-status-closure-interview-complete-guide.md" in closure_script
    assert "先一次性过完整讲稿" in closure_script

    interview_pack = _read("docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-pack.md")
    assert "20260825-p0-p2-status-closure-interview-complete-guide.md" in interview_pack
    assert "配套阅读顺序建议" in interview_pack

    interview_brief = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md")
    assert "docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md" in interview_brief

    report_script = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-report-script.md")
    assert "这份材料是当前**长讲法 / 5 分钟汇报底稿**" in report_script
    assert "如果只需要 30 秒 / 2 分钟口播，优先看 `20260821-project-audit-remediation-interview-brief.md`" in report_script
    assert "不要反过来拿本文替代 `20260821-project-audit-remediation-issues-summary.md`" in report_script
    assert "如果要单独讲“1~30 轮问题最终怎么收口”" in report_script
    assert "docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md" in report_script
    assert "docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md" in report_script
    assert "如果汇报结束后进入追问，统一跳转 `docs/interview/ThinkRAG_面试问答.md`" in report_script
    assert "本文只保留**标准汇报稿**，不再重复维护 Q1 / Q2 / Q3 / Q4 的完整长答案" in report_script
    assert "1. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md`" in report_script
    assert "### Q1：为什么现在指标都是 1.0？是不是题太水？" not in report_script
    assert "推荐回答：" not in report_script

    guide_doc = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-guide.md")
    assert "不再重复维护长口播正文，更适合先发给需要快速看全局状态的人" in guide_doc
    assert "当前**口播主稿**" in guide_doc
    assert "docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md" in guide_doc
    assert "docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md" in guide_doc
    assert "### 2.10 `20260821-project-audit-remediation-audit-evidence.md`" in guide_doc
    assert "### 2.12 `../20260825-p0-p2-status-closure/`（目录外补充收口材料）" in guide_doc
    assert "最短证据索引、关键文件和最值得记住的命令" in guide_doc
    assert "审计证据附录 / 历史增量记录" in guide_doc
    assert "### 3.1 面试前 10 分钟快速复习" in guide_doc
    assert "1. `20260821-project-audit-remediation-interview-brief.md`" in guide_doc
    assert "2. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`" in guide_doc
    assert "3. `docs/interview/ThinkRAG_面试问答.md`" in guide_doc
    assert "4. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md`" in guide_doc
    assert "4. `20260821-project-audit-remediation-audit-evidence.md`" in guide_doc
    assert "### 3.5 如果被要求单独讲“1~30 轮问题最后怎么收口”" in guide_doc



def test_project_and_audit_docs_describe_refusal_as_three_layer_contract() -> None:
    project_content = _read("docs/project.md")
    assert "refusal / negative contract 已形成三层闭环" in project_content
    assert "minimum_refusal_cases_per_modality" in project_content
    assert "required_refusal_markers_by_category" in project_content
    assert "refusal_summary" in project_content
    assert "Refusal 覆盖摘要" in project_content

    audit_brief = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md")
    assert "refusal / negative contract 也已经形成三层闭环" in audit_brief
    assert "refusal_summary" in audit_brief
    assert "Refusal 覆盖摘要" in audit_brief



def test_audit_docs_keep_current_metrics_and_runtime_root_cause() -> None:
    chat_pass_label = f"{_pytest_collected_test_count(CHAT_REGRESSION_ARGS)} passed"
    docs_contract_pass_label = f"{_pytest_collected_test_count(DOCS_CONTRACT_ARGS)} passed"
    full_non_slow_selected, full_non_slow_deselected = _pytest_collection_summary(FULL_NON_SLOW_ARGS)
    full_non_slow_label = f"{full_non_slow_selected} passed, {full_non_slow_deselected} deselected"

    metric_docs = (
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-guide.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-material-pack.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-report-script.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-spec.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md",
    )
    for relative_path in metric_docs:
        content = _read(relative_path)
        assert "153 / 153" in content
        assert chat_pass_label in content
        assert docs_contract_pass_label in content
        assert full_non_slow_label in content
        assert "29 passed" not in content
        assert "顶层 `llama_index` metapackage" in content
        assert "llama-parse" in content

    guide = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-guide.md")
    assert "INSTALL_PROFILE=runtime" in guide
    assert "能力完成度高于工程完成度" in guide

    report = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md")
    assert "requirements-minimal.txt` 现在只是本地兼容 alias" in report
    assert "完整 `docker build + docker run` smoke 还没补完" in report





def test_audit_docs_include_follow_up_coverage_summary() -> None:
    eval_summary = _eval_v8_main_summary()
    history_grounded_count = int(eval_summary["history_grounded_case_count"])
    history_grounded_breakdown = dict(eval_summary["history_grounded_modality_breakdown"])
    semireal_follow_up_pass_label = f"{_pytest_collected_test_count(SEMIREAL_FOLLOW_UP_ARGS)} passed"

    report = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md")
    assert "follow-up 覆盖摘要" in report
    assert f"`history_grounded_case_count = {history_grounded_count}`" in report
    assert f"`markdown = {history_grounded_breakdown['markdown']}`" in report
    assert f"`pdf = {history_grounded_breakdown['pdf']}`" in report
    assert f"`image_ocr = {history_grounded_breakdown['image_ocr']}`" in report
    assert semireal_follow_up_pass_label in report
    assert "Markdown / PDF / Image OCR" in report
    assert "正式 gate 已同时覆盖 answerable follow-up 与 refusal follow-up" in report

    report_script = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-report-script.md")
    assert "follow-up 覆盖摘要" in report_script
    assert f"`history_grounded_case_count = {history_grounded_count}`" in report_script
    assert semireal_follow_up_pass_label in report_script
    assert "answerable follow-up + refusal follow-up 都有正式证据" in report_script

def test_audit_docs_describe_legacy_streamlit_as_opt_in_compatibility_shim() -> None:
    audited_paths = (
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-audit.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md",
    )
    for relative_path in audited_paths:
        content = _read(relative_path)
        assert "KB_ALLOW_LEGACY_STREAMLIT=1" in content
        assert "默认禁用" in content
        assert "显式 opt-in" in content or "显式设置" in content

    audit_content = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-audit.md")
    assert "app.py` 仍直接依赖 `streamlit`" not in audit_content
    assert "run_api.py` 仍把 host 固定为 `127.0.0.1`" not in audit_content



def test_virtualenv_guide_points_to_current_entry_and_opt_in_legacy_streamlit() -> None:
    content = _read("docs/guide/HowToUsePythonVirtualEnv.md")

    assert "requirements-runtime.txt" in content
    assert "start_all.ps1" in content
    assert "start_dev.ps1" in content
    assert "KB_ALLOW_LEGACY_STREAMLIT=1" in content
    assert "python -m streamlit run app.py" in content
    assert "当前项目主线已经不是直接运行 Streamlit" in content
    assert "KB_API_BASE_URL" in content
    assert "VITE_API_BASE_URL" in content


def test_root_virtualenv_doc_is_only_a_compatibility_redirect() -> None:
    content = _read("docs/HowToUsePythonVirtualEnv.md")

    assert "compatibility redirect" in content
    assert "docs/guide/HowToUsePythonVirtualEnv.md" in content
    assert "requirements-runtime.txt" in content
    assert "FastAPI + React (Vite)" in content
    assert "KB_ALLOW_LEGACY_STREAMLIT=1" in content
    assert "do **not** restore `python -m streamlit run app.py` as the default startup path" in content
    assert "Run your Streamlit app" not in content
    assert "pip3 install -r requirements.txt" not in content


def test_runtime_docs_capture_testclient_httpx_troubleshooting() -> None:
    readme_paths = ("README.md", "README_en.md", "README_zh.md")
    for relative_path in readme_paths:
        content = _read(relative_path)
        assert "requirements-runtime.txt" in content
        assert "httpx==0.27.2" in content
        assert "TestClient" in content
        assert "Client.__init__() got an unexpected keyword argument 'app'" in content

    runbook_paths = (
        "docs/desktop_runbook.md",
        "docs/guide/desktop_runbook.md",
        "docs/guide/HowToUsePythonVirtualEnv.md",
    )
    for relative_path in runbook_paths:
        content = _read(relative_path)
        assert "requirements-runtime.txt" in content
        assert "httpx==0.27.2" in content
        assert "Client.__init__() got an unexpected keyword argument 'app'" in content


@lru_cache(maxsize=1)
def _desktop_npm_test_pass_count() -> int:
    completed = subprocess.run(
        "npm --prefix desktop test",
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        timeout=120,
        check=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(r"\bpass\s+(\d+)\b", output)
    assert match is not None, output
    return int(match.group(1))



def _line_with(content: str, needle: str) -> str:
    for line in content.splitlines():
        if needle in line:
            return line
    raise AssertionError(f"missing line with {needle!r}")


def _following_prefixed_lines(content: str, anchor: str, prefix: str) -> list[str]:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if anchor in line:
            collected: list[str] = []
            for candidate in lines[index + 1 :]:
                if candidate.startswith(prefix):
                    collected.append(candidate)
                    continue
                if candidate == "":
                    break
                break
            return collected
    raise AssertionError(f"missing anchor {anchor!r}")



@lru_cache(maxsize=1)
def _eval_v8_main_summary() -> dict[str, object]:
    return summarize_eval_cases(
        "tests/fixtures/rag_quality/eval_v8_main/cases.json",
        schema_path="tests/fixtures/rag_quality/eval_v8_main/schema.json",
    )


@lru_cache(maxsize=None)
def _pytest_collection_summary(pytest_args: str) -> tuple[int, int]:
    completed = subprocess.run(
        f"python -m pytest {pytest_args} --collect-only -q",
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        timeout=120,
        check=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"

    deselected_match = re.search(r"(\d+)/(\d+) tests collected \((\d+) deselected\)", output)
    if deselected_match is not None:
        return int(deselected_match.group(1)), int(deselected_match.group(3))

    match = re.search(r"(\d+) tests collected", output)
    assert match is not None, output
    return int(match.group(1)), 0


@lru_cache(maxsize=None)
def _pytest_collected_test_count(pytest_args: str) -> int:
    return _pytest_collection_summary(pytest_args)[0]



def test_audit_docs_capture_full_desktop_node_suite_and_release_lane_boundary() -> None:
    latest_pass_count = _desktop_npm_test_pass_count()
    latest_pass_label = f"{latest_pass_count} passed"

    summary = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md")
    assert "npm --prefix desktop test" in summary
    assert latest_pass_label in _line_with(summary, "npm --prefix desktop test")

    audit_evidence = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-audit-evidence.md")
    assert "ad-hoc package verification" in audit_evidence
    assert "release:mac" in audit_evidence

    status = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md")
    assert "npm --prefix desktop test" in status
    assert latest_pass_label in _line_with(status, "npm --prefix desktop test")
    assert "strict Apple preflight" in status
    assert "signed/notarized distribution lane" in status

    report = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md")
    assert "npm --prefix desktop test" in report
    assert latest_pass_label in _line_with(report, "npm --prefix desktop test")
    assert "Desktop build/package/release four-layer boundary" in report
    assert "verify:package" in report
    assert "verify:mac-release" in report

def test_audit_docs_capture_current_startup_and_desktop_smoke_suite_count() -> None:
    command = (
        "tests/scripts/test_dev_startup_contracts.py "
        "tests/scripts/test_start_dev_smoke.py "
        "tests/scripts/test_dev_all_smoke.py"
    )
    latest_pass_label = f"{_pytest_collected_test_count(command)} passed"
    command_label = (
        "python -m pytest tests/scripts/test_dev_startup_contracts.py "
        "tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py -q"
    )

    summary = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md")
    assert latest_pass_label in _line_with(summary, command_label)

    status = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md")
    assert latest_pass_label in _line_with(status, command_label)

    report = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md")
    assert latest_pass_label in _line_with(report, command_label)


def test_audit_docs_capture_current_pytest_bundle_counts() -> None:
    chat_pass_label = f"{_pytest_collected_test_count(CHAT_REGRESSION_ARGS)} passed"
    docs_contract_pass_label = f"{_pytest_collected_test_count(DOCS_CONTRACT_ARGS)} passed"
    docker_helper_pass_label = f"{_pytest_collected_test_count(DOCKER_HELPER_ARGS)} passed"
    docker_bundle_pass_label = f"{_pytest_collected_test_count(DOCKER_BUNDLE_ARGS)} passed"
    prompt_bundle_1_pass_label = f"{_pytest_collected_test_count(PROMPT_BUNDLE_1_ARGS)} passed"
    prompt_bundle_2_pass_label = f"{_pytest_collected_test_count(PROMPT_BUNDLE_2_ARGS)} passed"
    prompt_bundle_3_pass_label = f"{_pytest_collected_test_count(PROMPT_BUNDLE_3_ARGS)} passed"
    full_non_slow_selected, full_non_slow_deselected = _pytest_collection_summary(FULL_NON_SLOW_ARGS)
    full_non_slow_label = f"{full_non_slow_selected} passed, {full_non_slow_deselected} deselected"

    summary = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md")
    assert chat_pass_label in _line_with(summary, "chat 关键回归")
    assert docs_contract_pass_label in _line_with(summary, "启动 / 文档入口 / requirements / cleanup / repo hygiene 契约")
    assert docker_helper_pass_label in _line_with(summary, "tests/scripts/test_docker_smoke.py -q")
    assert docker_bundle_pass_label in _line_with(summary, "startup / docker helper / repo hygiene bundle")
    assert full_non_slow_label in _line_with(summary, "全量非慢测")

    status = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md")
    assert chat_pass_label in _line_with(status, "tests/api/test_chat_qa_metrics.py")
    assert docs_contract_pass_label in _line_with(status, "tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py")
    assert docker_helper_pass_label in _line_with(status, "python -m pytest tests/scripts/test_docker_smoke.py -q")
    assert docker_bundle_pass_label in _line_with(status, "startup / docker helper / repo hygiene 回归 bundle")
    assert prompt_bundle_1_pass_label in _line_with(status, "tests/api/test_chat_composite_answers.py")
    assert prompt_bundle_2_pass_label in _line_with(status, "tests/api/test_chat_question_intents.py")
    assert prompt_bundle_3_pass_label in _line_with(status, "tests/api/test_chat_eval_runner.py")
    assert full_non_slow_label in _line_with(status, 'python -m pytest tests/ -q -m "not slow"')

    report = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md")
    assert chat_pass_label in _line_with(report, "targeted fact / preview / metrics 回归")
    assert docs_contract_pass_label in _line_with(report, "启动 / 文档入口 / requirements / cleanup / repo hygiene 契约")
    assert docker_helper_pass_label in _line_with(report, "Docker smoke helper 契约")
    assert docker_bundle_pass_label in _line_with(report, "startup / docker helper / repo hygiene 回归 bundle")
    assert prompt_bundle_1_pass_label in report
    assert prompt_bundle_2_pass_label in report
    assert prompt_bundle_3_pass_label in report
    assert full_non_slow_label in _line_with(report, "全量非慢测回归")

    audit = _read("docs/20260821-project-audit-remediation/20260821-project-audit-remediation-audit.md")
    assert f"# {chat_pass_label}" in audit
    assert f"# {docs_contract_pass_label}" in audit
    assert f"# {full_non_slow_label}" in audit


def test_project_doc_current_baseline_points_to_latest_audit_counts() -> None:
    chat_pass_label = f"{_pytest_collected_test_count(CHAT_REGRESSION_ARGS)} passed"
    docs_contract_pass_label = f"{_pytest_collected_test_count(DOCS_CONTRACT_ARGS)} passed"
    docker_helper_pass_label = f"{_pytest_collected_test_count(DOCKER_HELPER_ARGS)} passed"
    docker_bundle_pass_label = f"{_pytest_collected_test_count(DOCKER_BUNDLE_ARGS)} passed"
    full_non_slow_selected, full_non_slow_deselected = _pytest_collection_summary(FULL_NON_SLOW_ARGS)
    full_non_slow_label = f"{full_non_slow_selected} passed, {full_non_slow_deselected} deselected"

    project_content = _read("docs/project.md")
    baseline_line = _line_with(project_content, "当前可信评测基线")
    assert "2026-08-24 复跑结果" in baseline_line
    assert chat_pass_label in baseline_line
    assert docs_contract_pass_label in baseline_line
    assert docker_helper_pass_label in baseline_line
    assert docker_bundle_pass_label in baseline_line
    assert full_non_slow_label in baseline_line


def test_closure_master_guide_maps_original_12_items_to_current_materials() -> None:
    master = _read("docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md")
    assert "如果你只想“把这些整理完成”" in master
    assert "按原始 12 项问题怎么定位到当前材料" in master
    assert "basic 模式和后端 single_kb 约束冲突" in master
    assert "前端把 query 成功和 history 成功绑死" in master
    assert "当前最新真实基线" in master
    assert "Route A：继续做工程收口" in master
    assert "Route B：准备面试表达" in master
    assert "主能力闭环已经做实" in master

    nav_doc = _read("docs/interview/ThinkRAG_面试全集_合并版.md")
    assert "一次性整理完成" in nav_doc
    assert "master-guide.md" in nav_doc
    assert "第 4、5 节" in nav_doc



def test_closure_docs_keep_machine_tags_and_block_structure() -> None:
    status_report = _read("docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md")
    assert "<!-- audit-sync:closure-status-command-lines -->" in status_report
    assert "## 3. 12 个问题状态矩阵" in status_report
    assert status_report.count("| 1 | basic 模式和后端 single_kb 约束冲突 |") == 1
    command_lines = _following_prefixed_lines(
        status_report,
        "<!-- audit-sync:closure-status-command-lines -->",
        "- `",
    )
    assert len(command_lines) == 7

    interview_script = _read("docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md")
    assert "<!-- audit-sync:closure-interview-validation-lines -->" in interview_script
    assert "<!-- audit-sync:closure-report-validation-lines -->" in interview_script
    validation_lines = _following_prefixed_lines(
        interview_script,
        "<!-- audit-sync:closure-interview-validation-lines -->",
        "- ",
    )
    report_lines = _following_prefixed_lines(
        interview_script,
        "<!-- audit-sync:closure-report-validation-lines -->",
        "- ",
    )
    assert len(validation_lines) == 7
    assert len(report_lines) == 7
    assert validation_lines[0].startswith("- scope / open api / chat 主链路相关测试：`")
    assert report_lines[0].startswith("- scope / open api / chat 主链路相关测试是 `")




def test_layered_eval_docs_sync_latest_hard_contract_closure() -> None:
    report = _read("docs/20260820-layered-rag-eval-refresh/20260820-layered-rag-eval-refresh-test-report.md")
    assert "temp/eval-v8-hard-20260827-r15/local_multi_kb_eval_v8_layered_hard-semireal-report.json" in report
    assert "| Hard | 36 | true | 36 / 36 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |" in report
    assert "required_negative_contract_modality_markers" in report
    assert "9 / 9" in report
    assert "36 条，34 / 36 通过" not in report

    plan = _read("docs/20260820-layered-rag-eval-refresh/20260820-layered-rag-eval-refresh-test-plan.md")
    assert "不强制 `run_passed` 必须为 `false`" in plan
    assert "若 `run_passed = true`，也必须能证明 challenge 分布与 contract gate 没有被削弱" in plan

    current_qa = _read("docs/interview/ThinkRAG_面试问答.md")
    assert "更新时间：2026-08-27" in current_qa
    assert "Hard：最新可复核快照为 `36 / 36`，且 `run_passed = true`" in current_qa
    assert "Hard 最新可复核快照为 `36 / 36`，并且 hard contract gate 已闭环" in current_qa
    assert "Hard `34 / 36`" not in current_qa

    rollup = _read("docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-rounds-rollup.md")
    assert "Hard 最新可复核快照 `36 / 36`，且 `run_passed = true`" in rollup

    complete = _read("docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-complete-guide.md")
    assert "Hard `36 / 36`" in complete
    assert "negative-contract modality marker" in complete

    project_content = _read("docs/project.md")
    baseline_line = _line_with(project_content, "当前可信评测基线")
    assert "layered suite `153 / 153`（Smoke `24 / 24`、Main `93 / 93`、Hard `36 / 36`）" in baseline_line
    assert "当前 layered suite 已到 `153 / 153`" in project_content

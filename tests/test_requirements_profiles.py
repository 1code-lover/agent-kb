from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _meaningful_lines(relative_path: str) -> list[str]:
    path = REPO_ROOT / relative_path
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _package_names(relative_path: str) -> set[str]:
    names: set[str] = set()
    for line in _meaningful_lines(relative_path):
        if line.startswith("-r "):
            continue
        marker = len(line)
        for token in ("==", ">=", "<=", "~=", "<", ">"):
            token_index = line.find(token)
            if token_index != -1:
                marker = min(marker, token_index)
        names.add(line[:marker].strip().lower())
    return names


def test_runtime_profile_covers_api_runtime_dependencies() -> None:
    packages = _package_names("requirements-runtime.txt")

    assert "llama-index-core" in packages
    assert "llama-index-readers-file" in packages
    assert "llama-index-embeddings-huggingface" in packages
    assert "llama-index-llms-langchain" in packages
    assert "langchain" in packages
    assert "langchain_openai" in packages
    assert "langchain-core" in packages
    assert "langchain-text-splitters" in packages


def test_runtime_profile_avoids_llama_index_metapackage() -> None:
    packages = _package_names("requirements-runtime.txt")
    runtime_content = (REPO_ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")

    assert "llama_index" not in packages
    assert "llama-index" not in packages
    assert "avoid the top-level `llama_index` metapackage" in runtime_content


def test_runtime_profile_pins_langchain_resolution_hotspots() -> None:
    runtime_content = (REPO_ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")

    assert "langchain-core==0.3.63" in runtime_content
    assert "langchain-text-splitters==0.3.8" in runtime_content
    assert "reduce resolver backtracking" in runtime_content


def test_runtime_and_eval_profiles_pin_testclient_compatible_httpx() -> None:
    runtime_content = (REPO_ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
    smoke_content = (REPO_ROOT / "requirements-smoke.txt").read_text(encoding="utf-8")
    eval_content = (REPO_ROOT / "requirements-eval.txt").read_text(encoding="utf-8")

    assert "httpx==0.27.2" in runtime_content
    assert "TestClient" in runtime_content
    assert "httpx==0.27.2" in smoke_content
    assert "httpx==0.27.2" in eval_content


def test_desktop_runtime_verifier_tracks_runtime_core_lock_without_metapackage() -> None:
    verifier = (REPO_ROOT / "desktop" / "scripts" / "verify-python-runtime.js").read_text(encoding="utf-8")

    assert '"llama-index-core": "0.11.19"' in verifier
    assert '"llama-index": "0.11.19"' not in verifier
    assert '"llama_index"' in verifier


def test_smoke_profile_is_runtime_minus_embedding_heavy_chain() -> None:
    runtime_packages = _package_names("requirements-runtime.txt")
    smoke_packages = _package_names("requirements-smoke.txt")
    smoke_content = (REPO_ROOT / "requirements-smoke.txt").read_text(encoding="utf-8")

    assert runtime_packages - smoke_packages == {"llama-index-embeddings-huggingface"}
    assert smoke_packages - runtime_packages == set()
    assert "llama-index-embeddings-huggingface" not in smoke_packages
    assert "Docker-only lighter smoke profile" in smoke_content
    assert "sentence-transformers -> torch" in smoke_content
    assert "Unsupported scope: runtime retrieval, embedding initialization, semireal eval." in smoke_content


def test_full_profile_keeps_heavy_local_only_extras_outside_runtime_baseline() -> None:
    runtime_packages = _package_names("requirements-runtime.txt")
    full_packages = _package_names("requirements.txt")

    for heavy_package in ("streamlit", "paddleocr", "paddlepaddle", "langchain-community"):
        assert heavy_package not in runtime_packages
        assert heavy_package in full_packages


def test_prod_profile_extends_runtime_instead_of_full_local_profile() -> None:
    prod_lines = _meaningful_lines("requirements-prod.txt")
    prod_packages = _package_names("requirements-prod.txt")

    assert "-r requirements-runtime.txt" in prod_lines
    assert "-r requirements.txt" not in prod_lines
    assert {"redis", "gunicorn"}.issubset(prod_packages)


def test_minimal_requirements_file_is_deprecated_compat_alias() -> None:
    minimal_lines = _meaningful_lines("requirements-minimal.txt")
    minimal_content = (REPO_ROOT / "requirements-minimal.txt").read_text(encoding="utf-8")

    assert "-r requirements-runtime.txt" in minimal_lines
    assert "Deprecated compatibility alias" in minimal_content
    assert "NOT a supported Docker INSTALL_PROFILE" in minimal_content


def test_dockerfile_supports_runtime_smoke_full_dev_prod_and_eval_profiles() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert 'ARG INSTALL_PROFILE=runtime' in dockerfile
    assert 'INSTALL_PROFILE=${INSTALL_PROFILE}' in dockerfile
    assert 'APP_RUNTIME_MODE=api' in dockerfile
    assert 'requirements-smoke.txt' in dockerfile
    assert 'runtime) pip install -r requirements-runtime.txt' in dockerfile
    assert 'smoke) pip install -r requirements-smoke.txt' in dockerfile
    assert 'full) pip install -r requirements.txt' in dockerfile
    assert 'dev) pip install -r requirements-dev.txt' in dockerfile
    assert 'prod) pip install -r requirements-prod.txt' in dockerfile
    assert 'eval) pip install -r requirements-eval.txt' in dockerfile
    assert 'requirements-minimal.txt' not in dockerfile
    assert 'minimal) pip install -r requirements-minimal.txt' not in dockerfile
    assert "sed -i 's/\\r$//' /app/scripts/docker-entrypoint.sh" in dockerfile
    assert 'ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]' in dockerfile
    assert 'CMD []' in dockerfile


def test_docker_entrypoint_separates_runtime_mode_from_install_profile() -> None:
    entrypoint = (REPO_ROOT / "scripts" / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert 'install_profile="${INSTALL_PROFILE:-runtime}"' in entrypoint
    assert 'profile="${APP_RUNTIME_MODE:-}"' in entrypoint
    assert 'port="${PORT:-18080}"' in entrypoint
    assert 'case "$install_profile" in' in entrypoint
    assert 'profile="api"' in entrypoint
    assert 'profile="eval"' in entrypoint
    assert 'profile="prod"' in entrypoint
    assert 'api|dev|runtime|full|smoke)' in entrypoint
    assert 'minimal|' not in entrypoint
    assert 'export KB_API_HOST="${KB_API_HOST:-0.0.0.0}"' in entrypoint
    assert 'export KB_API_PORT="${KB_API_PORT:-$port}"' in entrypoint
    assert 'exec python run_api.py' in entrypoint
    assert 'prod)' in entrypoint
    assert 'gunicorn' in entrypoint
    assert 'eval)' in entrypoint
    assert 'python scripts/run_chat_eval.py' in entrypoint


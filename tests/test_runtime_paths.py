"""Packaged runtime data/model root isolation tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _inspect_isolated_runtime(env_overrides: dict[str, str], cwd: Path) -> dict[str, str]:
    script = r'''
import json
import config
from api.services import fallback_store, session_store
from server.models import embedding
from server.stores import config_store
from server.utils.model_loader import resolve_model_path

diagnostics = embedding.get_embedding_model_diagnostics()
resolved_model = resolve_model_path(
    config.DEFAULT_EMBEDDING_MODEL,
    config.EMBEDDING_MODEL_PATH,
    allow_remote=False,
)
print(json.dumps({
    "storage_dir": config.STORAGE_DIR,
    "data_dir": config.DATA_DIR,
    "model_dir": config.MODEL_DIR,
    "config_store": config_store.PERSISIT_PATH,
    "session_dir": str(session_store._SESSION_DIR),
    "fallback_store": str(fallback_store._STORE_FILE),
    "embedding_path": diagnostics["local_path"],
    "resolved_model": resolved_model,
}))
'''
    env = os.environ.copy()
    env.update(env_overrides)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout.strip())


def _expected_runtime_snapshot(data_root: Path, model_root: Path) -> dict[str, str]:
    default_model = model_root / "BAAI" / "bge-small-zh-v1.5"
    return {
        "storage_dir": str(data_root / "storage"),
        "data_dir": str(data_root / "data"),
        "model_dir": str(model_root),
        "config_store": str(data_root / "storage" / "config_store.json"),
        "session_dir": str(data_root / "storage" / "sessions"),
        "fallback_store": str(data_root / "storage" / "config_store.json"),
        "embedding_path": str(default_model),
        "resolved_model": str(default_model),
    }


def test_packaged_runtime_uses_absolute_data_and_model_roots(tmp_path: Path) -> None:
    data_root = tmp_path / "user-data" / "runtime"
    model_root = tmp_path / "resources" / "localmodels"
    (model_root / "BAAI" / "bge-small-zh-v1.5").mkdir(parents=True)
    data_root.parent.mkdir(parents=True)

    result = _inspect_isolated_runtime(
        {
            "KB_DATA_ROOT": str(data_root),
            "KB_MODEL_ROOT": str(model_root),
        },
        data_root.parent,
    )

    assert result == _expected_runtime_snapshot(data_root, model_root)


def test_packaged_runtime_keeps_thinkrag_and_foxglove_root_aliases_compatible(tmp_path: Path) -> None:
    data_root = tmp_path / "user-data" / "runtime-alias"
    model_root = tmp_path / "resources" / "localmodels-alias"
    (model_root / "BAAI" / "bge-small-zh-v1.5").mkdir(parents=True)
    data_root.parent.mkdir(parents=True)

    result = _inspect_isolated_runtime(
        {
            "THINKRAG_DATA_ROOT": str(data_root),
            "FOXGLOVE_MODEL_ROOT": str(model_root),
        },
        data_root.parent,
    )

    assert result == _expected_runtime_snapshot(data_root, model_root)

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.scripts._startup_smoke_lock import acquire_startup_smoke_lock

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_acquire_startup_smoke_lock_times_out_while_another_process_holds_it(tmp_path: Path) -> None:
    helper = "\n".join(
        [
            "from pathlib import Path",
            "import sys",
            "import time",
            "sys.path.insert(0, sys.argv[1])",
            "from tests.scripts._startup_smoke_lock import acquire_startup_smoke_lock",
            "repo_root = Path(sys.argv[2])",
            "with acquire_startup_smoke_lock(repo_root, timeout_seconds=5, poll_interval_seconds=0.05):",
            "    print('locked', flush=True)",
            "    time.sleep(1.2)",
        ]
    )
    proc = subprocess.Popen(
        [sys.executable, '-c', helper, str(REPO_ROOT), str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        cwd=REPO_ROOT,
    )
    try:
        assert proc.stdout is not None
        ready_line = proc.stdout.readline().strip()
        assert ready_line == 'locked'

        started = time.monotonic()
        with pytest.raises(TimeoutError):
            with acquire_startup_smoke_lock(tmp_path, timeout_seconds=0.2, poll_interval_seconds=0.05):
                raise AssertionError('lock should not be acquired while helper process still holds it')
        assert time.monotonic() - started >= 0.15
    finally:
        proc.wait(timeout=5)
        assert proc.returncode == 0, (proc.stdout.read() if proc.stdout else '') + (proc.stderr.read() if proc.stderr else '')

    with acquire_startup_smoke_lock(tmp_path, timeout_seconds=0.5, poll_interval_seconds=0.05):
        pass

def test_acquire_startup_smoke_lock_uses_temp_directory_under_repo_root(tmp_path: Path) -> None:
    with acquire_startup_smoke_lock(tmp_path, timeout_seconds=0.5, poll_interval_seconds=0.05) as lock_path:
        assert lock_path == tmp_path / "temp" / "pytest-locks" / "startup-smoke.lock"
        assert lock_path.parent.exists()
        assert lock_path.parent.parent == tmp_path / "temp"
        assert not (tmp_path / ".pytest-locks").exists()


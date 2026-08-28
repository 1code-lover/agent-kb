"""为 startup/dev-all smoke 提供跨进程串行锁，避免并行抢占端口窗口。"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import time
from typing import Iterator

if os.name == 'nt':
    import msvcrt
else:
    import fcntl


_LOCK_DIR_RELATIVE = Path('temp') / 'pytest-locks'
_LOCK_FILE_NAME = 'startup-smoke.lock'


def _try_lock(handle) -> bool:
    try:
        handle.seek(0)
        if os.name == 'nt':
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle) -> None:
    handle.seek(0)
    if os.name == 'nt':
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def acquire_startup_smoke_lock(
    repo_root: Path,
    *,
    timeout_seconds: float = 180.0,
    poll_interval_seconds: float = 0.2,
) -> Iterator[Path]:
    """串行化 startup/dev-all smoke，避免两个用例同时抢同一端口区间。"""
    lock_dir = Path(repo_root) / _LOCK_DIR_RELATIVE
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / _LOCK_FILE_NAME
    deadline = time.monotonic() + timeout_seconds

    with lock_path.open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()

        while not _try_lock(handle):
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Timed out acquiring startup smoke lock: {lock_path}')
            time.sleep(poll_interval_seconds)

        try:
            handle.seek(0)
            handle.write(str(os.getpid()).encode('utf-8'))
            handle.truncate()
            handle.flush()
            yield lock_path
        finally:
            handle.seek(0)
            handle.write(b'0')
            handle.truncate()
            handle.flush()
            _unlock(handle)

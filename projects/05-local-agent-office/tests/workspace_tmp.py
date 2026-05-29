from __future__ import annotations

import shutil
import gc
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


TEST_TMP_ROOT = Path(__file__).resolve().parent / "_tmp"


@contextmanager
def workspace_tmp_dir(prefix: str = "test") -> Iterator[Path]:
    """Create a test temp directory inside the workspace, not Windows global temp."""
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TEST_TMP_ROOT / f"{prefix}-{uuid.uuid4().hex}"
    path.mkdir()

    try:
        yield path
    finally:
        root = TEST_TMP_ROOT.resolve()
        target = path.resolve()
        if target == root or root not in target.parents:
            raise RuntimeError(f"Refusing to remove path outside test tmp root: {target}")
        for attempt in range(5):
            gc.collect()
            try:
                shutil.rmtree(target)
                break
            except FileNotFoundError:
                break
            except PermissionError:
                if attempt == 4:
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    time.sleep(0.05)
        try:
            TEST_TMP_ROOT.rmdir()
        except OSError:
            pass

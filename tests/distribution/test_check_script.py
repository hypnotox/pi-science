from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_check_uses_and_cleans_external_temporary_directory(tmp_path: Path) -> None:
    marker = tmp_path / "tmpdir"
    shim_directory = tmp_path / "bin"
    shim_directory.mkdir()
    uv = shim_directory / "uv"
    uv.write_text(
        '#!/bin/sh\nprintf "%s" "$TMPDIR" >"$CHECK_TMP_MARKER"\nexit 23\n',
        encoding="utf-8",
    )
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)
    cache_home = tmp_path / "cache"
    env = {
        **os.environ,
        "PATH": f"{shim_directory}{os.pathsep}{os.environ['PATH']}",
        "XDG_CACHE_HOME": str(cache_home),
        "CHECK_TMP_MARKER": str(marker),
    }
    env.pop("TMPDIR", None)

    completed = subprocess.run(
        ["bash", "scripts/check"],
        cwd=REPOSITORY_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 23
    check_tmp = Path(marker.read_text(encoding="utf-8"))
    assert check_tmp.parent == cache_home / "pi-science"
    assert check_tmp.name.startswith("check.")
    assert not check_tmp.exists()

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_release_snapshot_accepts_clean_worktree(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(REPOSITORY_ROOT), str(checkout)],
        check=True,
    )
    shutil.copy2(REPOSITORY_ROOT / "scripts" / "check-release", checkout / "scripts")
    subprocess.run(["git", "add", "scripts/check-release"], cwd=checkout, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=release-test",
            "-c",
            "user.email=release-test@example.invalid",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "test snapshot",
        ],
        cwd=checkout,
        check=True,
    )

    shim_directory = tmp_path / "bin"
    shim_directory.mkdir()
    uv = shim_directory / "uv"
    uv.write_text("#!/bin/sh\necho release-test-reached-uv >&2\nexit 23\n")
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)
    env = {**os.environ, "PATH": f"{shim_directory}{os.pathsep}{os.environ['PATH']}"}
    completed = subprocess.run(
        ["bash", "scripts/check-release"],
        cwd=checkout,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 23, completed.stderr
    assert "release-test-reached-uv" in completed.stderr

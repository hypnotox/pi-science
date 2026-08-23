from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPOSITORY_ROOT / "packages" / "py-science-formula"


def _run(*args: str, cwd: Path = REPOSITORY_ROOT, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, (
        f"command failed ({completed.returncode}): {' '.join(args)}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )


def test_built_distribution_is_standalone_namespace_package(tmp_path: Path) -> None:
    wheel_directory = tmp_path / "wheel"
    wheel_directory.mkdir()
    _run(
        "uv",
        "build",
        "--package",
        "py-science-formula",
        "--wheel",
        "--out-dir",
        str(wheel_directory),
    )

    wheels = list(wheel_directory.glob("*.whl"))
    assert len(wheels) == 1
    wheel = wheels[0]

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert any(name.startswith("py_science/formula/") for name in names)
        assert "py_science/__init__.py" not in names
        assert not any(name.startswith("pi_science/") for name in names)
        license_names = [name for name in names if name.endswith(".dist-info/licenses/LICENSE")]
        assert len(license_names) == 1
        assert archive.read(license_names[0]) == (REPOSITORY_ROOT / "LICENSE").read_bytes()

    environment = tmp_path / "environment"
    _run("uv", "venv", "--python", "3.13", str(environment))
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run("uv", "pip", "install", "--python", str(python), str(wheel))

    other_namespace = tmp_path / "other-namespace"
    other_package = other_namespace / "py_science" / "other"
    other_package.mkdir(parents=True)
    (other_package / "__init__.py").write_text("MARKER = 'other'\n", encoding="utf-8")

    probe_directory = tmp_path / "probe"
    probe_directory.mkdir()
    probe = """
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1])))
from py_science import other
from py_science.formula import AnalysisRequest, AnalysisSuccess, FormulaSyntax, analyze
from py_science.formula.contracts import (
    common, comparison, dominance, evidence, optimization, queries, reports, requests
)
from py_science.formula.contracts._base import StructuredModel

assert other.MARKER == "other"
assert all(module.__name__.startswith("py_science.formula.contracts.") for module in (
    common, comparison, dominance, evidence, optimization, queries, reports, requests
))
assert StructuredModel.__module__ == "py_science.formula.contracts._base"
outcome = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="n + 1"))
assert isinstance(outcome, AnalysisSuccess)
assert outcome.operation_counts.additions == 1
try:
    import pi_science
except ModuleNotFoundError:
    pass
else:
    raise AssertionError("legacy pi_science namespace is importable")
print("PACKAGE_PROBE_OK")
"""
    completed = subprocess.run(
        [str(python), "-c", probe, str(other_namespace)],
        cwd=probe_directory,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        check=False,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, (
        f"package probe failed ({completed.returncode})\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout.strip() == "PACKAGE_PROBE_OK"


def test_package_license_matches_repository_license() -> None:
    assert (PACKAGE_ROOT / "LICENSE").read_bytes() == (REPOSITORY_ROOT / "LICENSE").read_bytes()

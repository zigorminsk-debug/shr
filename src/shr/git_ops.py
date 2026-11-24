"""Локальные Git-операции через subprocess (git CLI)."""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Optional


def _run(args: list[str], cwd: Optional[Path] = None, timeout: int = 120) -> tuple[int, str]:
    proc = subprocess.run(["git"] + args, cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def git_version() -> str:
    code, out = _run(["--version"])
    return out.strip() if code == 0 else "git не найден"


def clone(url: str, dest: Path, depth: int = 0) -> tuple[int, str]:
    args = ["clone"]
    if depth:
        args += ["--depth", str(depth)]
    args += [url, str(dest)]
    return _run(args)


def pull(cwd: Path) -> tuple[int, str]:
    return _run(["pull"], cwd=cwd)


def push(cwd: Path, branch: str = "") -> tuple[int, str]:
    args = ["push"]
    if branch:
        args += ["origin", branch]
    return _run(args, cwd=cwd)


def status(cwd: Path) -> str:
    _, out = _run(["status", "--short", "--branch"], cwd=cwd)
    return out


def branch_list(cwd: Path) -> list[str]:
    _, out = _run(["branch", "--all"], cwd=cwd)
    return [l.strip().lstrip("* ").strip() for l in out.splitlines() if l.strip()]


def log(cwd: Path, n: int = 20) -> str:
    _, out = _run(["log", f"-{n}", "--oneline", "--decorate"], cwd=cwd)
    return out


def checkout(cwd: Path, branch: str) -> tuple[int, str]:
    return _run(["checkout", branch], cwd=cwd)


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()

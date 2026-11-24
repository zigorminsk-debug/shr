"""Тесты менеджера runner'а."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shr.runner_manager import detect_runner_asset, is_runner_installed


def test_detect_asset():
    asset = detect_runner_asset()
    assert asset.startswith("actions-runner-")
    assert asset.endswith((".zip", ".tar.gz"))


def test_not_installed(tmp_path):
    assert not is_runner_installed(tmp_path / "nonexistent")


def test_installed(tmp_path):
    (tmp_path / "run.cmd").write_text("@echo hi")
    assert is_runner_installed(tmp_path)

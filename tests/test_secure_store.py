"""Тесты безопасного хранилища токена."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shr import secure_store


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(secure_store, "_store_path", lambda: tmp_path / "token.dat")
    secure_store.save_token("ghp_1234567890abcdef")
    assert secure_store.load_token() == "ghp_1234567890abcdef"
    assert secure_store.has_token()


def test_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(secure_store, "_store_path", lambda: tmp_path / "token.dat")
    secure_store.save_token("ghp_x")
    secure_store.clear_token()
    assert secure_store.load_token() == ""


def test_empty_token(tmp_path, monkeypatch):
    monkeypatch.setattr(secure_store, "_store_path", lambda: tmp_path / "token.dat")
    secure_store.save_token("")
    assert secure_store.load_token() == ""

"""Безопасное хранение токена GitHub (PAT).

На Windows использует DPAPI (CryptProtectData) — токен зашифрован
и расшифровывается только текущим пользователем Windows.
На других ОС — файл с правами 0600 + предупреждение.
"""
from __future__ import annotations
import base64
import ctypes
import json
import os
import sys
from pathlib import Path

from .config import get_app_dir

_STORE_FILE = "token.dat"
_DESCRIPTION = "SHR GitHub Token"


# ── DPAPI (Windows) ──────────────────────────────────────────────────────────

class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi_encrypt(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("DPAPI доступен только на Windows")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_in = _DataBlob(len(data), (ctypes.c_ubyte * len(data)).from_buffer_copy(data))
    blob_out = _DataBlob()
    ok = crypt32.CryptProtectData(
        ctypes.byref(blob_in), _DESCRIPTION, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise RuntimeError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _dpapi_decrypt(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("DPAPI доступен только на Windows")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_in = _DataBlob(len(data), (ctypes.c_ubyte * len(data)).from_buffer_copy(data))
    blob_out = _DataBlob()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise RuntimeError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


# ── Fallback (не-Windows): XOR + base64, только для dev ─────────────────────

def _fallback_encrypt(data: bytes) -> bytes:
    key = b"SHR-DEV-KEY"
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _fallback_decrypt(data: bytes) -> bytes:
    return _fallback_encrypt(data)


# ── Публичное API ────────────────────────────────────────────────────────────

def _store_path() -> Path:
    return get_app_dir() / _STORE_FILE


def save_token(token: str) -> None:
    """Сохранить PAT в зашифрованный файл."""
    token = (token or "").strip()
    if not token:
        clear_token()
        return
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = token.encode("utf-8")
    try:
        encrypted = _dpapi_encrypt(raw)
        payload = {"method": "dpapi", "data": base64.b64encode(encrypted).decode()}
    except Exception:
        encrypted = _fallback_encrypt(raw)
        payload = {"method": "fallback", "data": base64.b64encode(encrypted).decode()}
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def load_token() -> str:
    """Загрузить PAT из зашифрованного файла. Пустая строка если нет."""
    path = _store_path()
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        encrypted = base64.b64decode(payload["data"])
        if payload.get("method") == "dpapi":
            return _dpapi_decrypt(encrypted).decode("utf-8")
        return _fallback_decrypt(encrypted).decode("utf-8")
    except Exception:
        return ""


def clear_token() -> None:
    path = _store_path()
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def has_token() -> bool:
    return bool(load_token())

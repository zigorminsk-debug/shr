"""Клиент GitHub REST API.

Обёртка над requests с обработкой ошибок, пагинации и rate limit.
Все вызовы идут через ApprovalQueue — см. app.py (RequestExecutor).
"""
from __future__ import annotations
import base64
import time
from typing import Any, Optional

import requests

API_BASE = "https://api.github.com"


class GitHubAPIError(Exception):
    def __init__(self, status: int, message: str, url: str = ""):
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status
        self.message = message
        self.url = url


class GitHubClient:
    """Низкоуровневый клиент. Не вызывает API напрямую без очереди —
    используйте методы execute_* через ApprovalQueue в app.py."""

    def __init__(self, token: str = "", api_base: str = API_BASE):
        self.token = token.strip()
        self.api_base = api_base.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SHR/1.0",
        })
        self.rate_limit_remaining: Optional[int] = None
        self.rate_limit_reset: Optional[int] = None

    def set_token(self, token: str) -> None:
        self.token = (token or "").strip()

    def _headers(self, extra: Optional[dict] = None) -> dict:
        h = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if extra:
            h.update(extra)
        return h

    def _update_rate_limit(self, resp: requests.Response) -> None:
        try:
            self.rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", -1))
            self.rate_limit_reset = int(resp.headers.get("X-RateLimit-Reset", 0))
        except Exception:
            pass

    def request(self, method: str, url: str, payload: Optional[dict] = None,
                params: Optional[dict] = None, headers: Optional[dict] = None,
                timeout: int = 30) -> Any:
        """Выполнить HTTP-запрос к GitHub API. Бросает GitHubAPIError."""
        full_url = url if url.startswith("http") else f"{self.api_base}{url}"
        try:
            resp = self.session.request(
                method.upper(), full_url,
                json=payload, params=params,
                headers=self._headers(headers), timeout=timeout,
            )
        except requests.RequestException as e:
            raise GitHubAPIError(0, f"Сеть: {e}", full_url)
        self._update_rate_limit(resp)
        if resp.status_code == 204:
            return None
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        if resp.status_code >= 400:
            msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
            raise GitHubAPIError(resp.status_code, msg, full_url)
        return data

    def get(self, url: str, params: Optional[dict] = None) -> Any:
        return self.request("GET", url, params=params)

    def post(self, url: str, payload: Optional[dict] = None) -> Any:
        return self.request("POST", url, payload=payload)

    def put(self, url: str, payload: Optional[dict] = None) -> Any:
        return self.request("PUT", url, payload=payload)

    def patch(self, url: str, payload: Optional[dict] = None) -> Any:
        return self.request("PATCH", url, payload=payload)

    def delete(self, url: str) -> Any:
        return self.request("DELETE", url)

    def get_all_pages(self, url: str, params: Optional[dict] = None,
                      max_pages: int = 10) -> list:
        """GET с пагинацией (Link header)."""
        params = dict(params or {})
        params.setdefault("per_page", 100)
        results: list = []
        page = 1
        while page <= max_pages:
            params["page"] = page
            data = self.get(url, params=params)
            if isinstance(data, list):
                results.extend(data)
                if len(data) < params["per_page"]:
                    break
            else:
                results.append(data)
                break
            page += 1
        return results

    # ── Удобные методы ──────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Проверить токен: GET /user."""
        return self.get("/user")

    def get_rate_limit(self) -> dict:
        return self.get("/rate_limit")

    def list_repos(self, owner: str = "", per_page: int = 100) -> list:
        if owner:
            return self.get_all_pages(f"/users/{owner}/repos")
        return self.get_all_pages("/user/repos", params={"affiliation": "owner"})

    def get_repo(self, owner: str, repo: str) -> dict:
        return self.get(f"/repos/{owner}/{repo}")

    def list_runners_repo(self, owner: str, repo: str) -> list:
        data = self.get(f"/repos/{owner}/{repo}/actions/runners")
        return data.get("runners", []) if isinstance(data, dict) else []

    def list_runners_org(self, org: str) -> list:
        data = self.get(f"/orgs/{org}/actions/runners")
        return data.get("runners", []) if isinstance(data, dict) else []

    def create_registration_token_repo(self, owner: str, repo: str) -> dict:
        return self.post(f"/repos/{owner}/{repo}/actions/runners/registration-token")

    def create_registration_token_org(self, org: str) -> dict:
        return self.post(f"/orgs/{org}/actions/runners/registration-token")

    def create_jit_token_repo(self, owner: str, repo: str, labels: list[str]) -> dict:
        return self.post(f"/repos/{owner}/{repo}/actions/runners/generate-jitconfig",
                         payload={"name": "", "labels": labels})

    def remove_runner_repo(self, owner: str, repo: str, runner_id: int) -> None:
        self.delete(f"/repos/{owner}/{repo}/actions/runners/{runner_id}")

    def list_workflows(self, owner: str, repo: str) -> list:
        data = self.get(f"/repos/{owner}/{repo}/actions/workflows")
        return data.get("workflows", []) if isinstance(data, dict) else []

    def list_workflow_runs(self, owner: str, repo: str, workflow_id: Any = None,
                           per_page: int = 30) -> list:
        if workflow_id:
            data = self.get(f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs",
                            params={"per_page": per_page})
        else:
            data = self.get(f"/repos/{owner}/{repo}/actions/runs",
                            params={"per_page": per_page})
        return data.get("workflow_runs", []) if isinstance(data, dict) else []

    def trigger_workflow(self, owner: str, repo: str, workflow_id: Any,
                         ref: str = "main", inputs: Optional[dict] = None) -> None:
        self.post(f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
                  payload={"ref": ref, "inputs": inputs or {}})

    def cancel_workflow_run(self, owner: str, repo: str, run_id: int) -> None:
        self.post(f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel")

    def rerun_failed_jobs(self, owner: str, repo: str, run_id: int) -> None:
        self.post(f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs")

    def list_issues(self, owner: str, repo: str, state: str = "open") -> list:
        return self.get_all_pages(f"/repos/{owner}/{repo}/issues",
                                  params={"state": state, "per_page": 50})

    def list_prs(self, owner: str, repo: str, state: str = "open") -> list:
        return self.get_all_pages(f"/repos/{owner}/{repo}/pulls",
                                  params={"state": state, "per_page": 50})

    def list_secrets_repo(self, owner: str, repo: str) -> list:
        data = self.get(f"/repos/{owner}/{repo}/actions/secrets")
        return data.get("secrets", []) if isinstance(data, dict) else []

    def get_public_key_repo(self, owner: str, repo: str) -> dict:
        return self.get(f"/repos/{owner}/{repo}/actions/secrets/public-key")

    def list_releases(self, owner: str, repo: str) -> list:
        return self.get_all_pages(f"/repos/{owner}/{repo}/releases")

    def get_latest_runner_release(self) -> dict:
        """Последний релиз actions/runner."""
        return self.get("/repos/actions/runner/releases/latest")

    def encrypt_secret(self, public_key_b64: str, plaintext: str) -> str:
        """Зашифровать секрет по схеме GitHub (NaCl sealed box)."""
        from nacl.public import PublicKey, SealedBox
        from nacl.encoding import RawEncoder
        key = PublicKey(base64.b64decode(public_key_b64), encoder=RawEncoder)
        box = SealedBox(key)
        encrypted = box.encrypt(plaintext.encode("utf-8"))
        return base64.b64encode(encrypted).decode()

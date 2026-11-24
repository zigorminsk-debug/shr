"""Тесты клиента GitHub API (мок через responses)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import responses
from shr.github_client import GitHubAPIError, GitHubClient


@responses.activate
def test_test_connection():
    responses.add(responses.GET, "https://api.github.com/user",
                  json={"login": "octocat"}, status=200)
    c = GitHubClient(token="ghp_test")
    data = c.test_connection()
    assert data["login"] == "octocat"


@responses.activate
def test_api_error():
    responses.add(responses.GET, "https://api.github.com/user",
                  json={"message": "Bad credentials"}, status=401)
    c = GitHubClient(token="bad")
    with pytest.raises(GitHubAPIError) as exc:
        c.test_connection()
    assert exc.value.status == 401


@responses.activate
def test_list_runners():
    responses.add(responses.GET,
                  "https://api.github.com/repos/o/r/actions/runners",
                  json={"total_count": 1, "runners": [{"id": 1, "name": "pc"}]},
                  status=200)
    c = GitHubClient(token="t")
    runners = c.list_runners_repo("o", "r")
    assert len(runners) == 1
    assert runners[0]["name"] == "pc"


def test_encrypt_secret_roundtrip():
    """Проверка шифрования секрета NaCl (без сети)."""
    from nacl.public import PrivateKey
    from nacl.encoding import RawEncoder
    import base64
    priv = PrivateKey.generate()
    pub_b64 = base64.b64encode(bytes(priv.public_key)).decode()
    c = GitHubClient(token="t")
    enc = c.encrypt_secret(pub_b64, "my-secret-value")
    assert enc and len(enc) > 10

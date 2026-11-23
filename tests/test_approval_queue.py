"""Тесты очереди запросов."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shr.approval_queue import ApprovalQueue, RequestStatus


def test_submit_pending():
    q = ApprovalQueue()
    req = q.submit("Test", "GET", "/user", is_safe=True)
    assert req.status == RequestStatus.PENDING
    assert q.pending_count() == 1


def test_approve():
    q = ApprovalQueue()
    req = q.submit("Test", "GET", "/user")
    assert q.approve(req.id)
    assert req.status == RequestStatus.APPROVED
    nxt = q.next_approved()
    assert nxt is not None and nxt.id == req.id
    assert nxt.status == RequestStatus.EXECUTING


def test_reject():
    q = ApprovalQueue()
    req = q.submit("Test", "POST", "/x")
    assert q.reject(req.id)
    assert req.status == RequestStatus.REJECTED


def test_auto_approve_get():
    q = ApprovalQueue(auto_approve_get=True)
    req = q.submit("Test", "GET", "/user", is_safe=True)
    assert req.status == RequestStatus.APPROVED


def test_complete_callback():
    q = ApprovalQueue()
    results = []
    req = q.submit("Test", "GET", "/user",
                   on_complete=lambda r, e: results.append((r, e)))
    q.approve(req.id)
    q.next_approved()
    q.complete(req.id, result={"login": "octocat"})
    assert req.status == RequestStatus.DONE
    assert results == [({"login": "octocat"}, "")]


def test_approve_all_safe():
    q = ApprovalQueue()
    q.submit("A", "GET", "/a", is_safe=True)
    q.submit("B", "POST", "/b", is_safe=False)
    assert q.approve_all_safe() == 1

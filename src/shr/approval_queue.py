"""Очередь запросов на подтверждение (Approval Queue).

Каждая операция к GitHub API создаёт запрос. Пользователь вручную
разрешает/отклоняет его в GUI. Только разрешённые запросы исполняются.
Это ключевая защита: приложение никогда не выполняет действия
без явного согласия пользователя (кроме опциональных авто-разрешений).
"""
from __future__ import annotations
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class RequestStatus(Enum):
    PENDING = "pending"       # ждёт решения пользователя
    APPROVED = "approved"     # разрешён, в очереди на исполнение
    REJECTED = "rejected"     # отклонён пользователем
    EXECUTING = "executing"   # исполняется
    DONE = "done"             # успешно исполнен
    FAILED = "failed"         # ошибка исполнения
    EXPIRED = "expired"       # истёк срок ожидания


@dataclass
class ApprovalRequest:
    """Один запрос на выполнение операции."""
    id: str
    title: str                    # человекочитаемое описание
    method: str                   # GET / POST / PUT / PATCH / DELETE
    url: str                      # полный URL API
    description: str = ""         # подробности для пользователя
    payload: Optional[dict] = None
    headers: Optional[dict] = None
    params: Optional[dict] = None
    is_safe: bool = False         # безопасная операция (GET)
    is_destructive: bool = False  # деструктивная (DELETE и т.п.)
    created_at: float = field(default_factory=time.time)
    status: RequestStatus = RequestStatus.PENDING
    result: Any = None
    error: str = ""
    on_complete: Optional[Callable] = None  # callback(result, error)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def to_display(self) -> dict:
        return {
            "id": self.id[:8],
            "title": self.title,
            "method": self.method,
            "status": self.status.value,
            "safe": self.is_safe,
            "destructive": self.is_destructive,
            "age": f"{self.age_seconds:.0f}с",
        }


class ApprovalQueue:
    """Потокобезопасная очередь запросов с подтверждением."""

    def __init__(self, auto_approve_get: bool = False, auto_approve_safe: bool = False,
                 ttl_seconds: int = 300):
        self._lock = threading.Lock()
        self._requests: dict[str, ApprovalRequest] = {}
        self._order: list[str] = []
        self.auto_approve_get = auto_approve_get
        self.auto_approve_safe = auto_approve_safe
        self.ttl_seconds = ttl_seconds
        self._listeners: list[Callable[[ApprovalRequest], None]] = []

    def add_listener(self, fn: Callable[[ApprovalRequest], None]) -> None:
        self._listeners.append(fn)

    def _notify(self, req: ApprovalRequest) -> None:
        for fn in list(self._listeners):
            try:
                fn(req)
            except Exception:
                pass

    def submit(self, title: str, method: str, url: str, description: str = "",
               payload: Optional[dict] = None, headers: Optional[dict] = None,
               params: Optional[dict] = None, is_safe: bool = False,
               is_destructive: bool = False,
               on_complete: Optional[Callable] = None) -> ApprovalRequest:
        """Создать запрос. Если авто-разрешение включено — сразу APPROVED."""
        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            title=title, method=method.upper(), url=url,
            description=description, payload=payload, headers=headers,
            params=params, is_safe=is_safe, is_destructive=is_destructive,
            on_complete=on_complete,
        )
        # Авто-разрешение безопасных операций
        if (is_safe and self.auto_approve_get) or (self.auto_approve_safe and not is_destructive):
            req.status = RequestStatus.APPROVED
        with self._lock:
            self._requests[req.id] = req
            self._order.append(req.id)
        self._notify(req)
        return req

    def approve(self, request_id: str) -> bool:
        with self._lock:
            req = self._requests.get(request_id)
            if not req or req.status != RequestStatus.PENDING:
                return False
            req.status = RequestStatus.APPROVED
        self._notify(req)
        return True

    def reject(self, request_id: str) -> bool:
        with self._lock:
            req = self._requests.get(request_id)
            if not req or req.status != RequestStatus.PENDING:
                return False
            req.status = RequestStatus.REJECTED
        self._notify(req)
        return True

    def approve_all_safe(self) -> int:
        """Разрешить все безопасные ожидающие запросы."""
        count = 0
        with self._lock:
            for rid in self._order:
                req = self._requests[rid]
                if req.status == RequestStatus.PENDING and req.is_safe:
                    req.status = RequestStatus.APPROVED
                    count += 1
                    self._notify(req)
        return count

    def reject_all(self) -> int:
        count = 0
        with self._lock:
            for rid in self._order:
                req = self._requests[rid]
                if req.status == RequestStatus.PENDING:
                    req.status = RequestStatus.REJECTED
                    count += 1
                    self._notify(req)
        return count

    def next_approved(self) -> Optional[ApprovalRequest]:
        """Взять следующий разрешённый запрос на исполнение."""
        with self._lock:
            for rid in self._order:
                req = self._requests[rid]
                if req.status == RequestStatus.APPROVED:
                    req.status = RequestStatus.EXECUTING
                    self._notify(req)
                    return req
        return None

    def complete(self, request_id: str, result: Any = None, error: str = "") -> None:
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                return
            if error:
                req.status = RequestStatus.FAILED
                req.error = error
            else:
                req.status = RequestStatus.DONE
                req.result = result
            cb = req.on_complete
        self._notify(req)
        if cb:
            try:
                cb(result, error)
            except Exception:
                pass

    def expire_old(self) -> int:
        """Пометить просроченные PENDING как EXPIRED."""
        now = time.time()
        count = 0
        with self._lock:
            for rid in self._order:
                req = self._requests[rid]
                if req.status == RequestStatus.PENDING and (now - req.created_at) > self.ttl_seconds:
                    req.status = RequestStatus.EXPIRED
                    count += 1
                    self._notify(req)
        return count

    def list_all(self) -> list[ApprovalRequest]:
        with self._lock:
            return [self._requests[rid] for rid in self._order]

    def list_pending(self) -> list[ApprovalRequest]:
        with self._lock:
            return [self._requests[rid] for rid in self._order
                    if self._requests[rid].status == RequestStatus.PENDING]

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        with self._lock:
            return self._requests.get(request_id)

    def pending_count(self) -> int:
        return len(self.list_pending())

    def clear_finished(self) -> int:
        """Удалить завершённые запросы из списка."""
        with self._lock:
            keep = []
            removed = 0
            for rid in self._order:
                req = self._requests[rid]
                if req.status in (RequestStatus.DONE, RequestStatus.FAILED,
                                  RequestStatus.REJECTED, RequestStatus.EXPIRED):
                    del self._requests[rid]
                    removed += 1
                else:
                    keep.append(rid)
            self._order = keep
            return removed

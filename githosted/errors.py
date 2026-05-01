"""Typed error classes and Connect error detail parsing."""

from __future__ import annotations

from typing import Any


class ConnectError(Exception):
    """A Connect RPC error with a code, message, and optional details."""

    def __init__(
        self, code: str, message: str, details: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or []


class NotFoundError(Exception):
    """The requested resource (repo, file, branch, ...) does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class RepoBusyError(Exception):
    """Repo is being mutated by another operation. Auto-retried before raising."""

    def __init__(self, repo_id: str, operation: str) -> None:
        super().__init__(
            f"Repository {repo_id} is currently being updated by "
            f"another operation ({operation})"
        )
        self.repo_id = repo_id
        self.operation = operation


class StaleHeadError(Exception):
    """Branch tip moved past expected_head. Never auto-retried."""

    def __init__(
        self, repo_id: str, ref: str, expected_head: str, actual_head: str
    ) -> None:
        super().__init__(
            f"Branch {ref} has moved: expected {expected_head}, actual {actual_head}"
        )
        self.repo_id = repo_id
        self.ref = ref
        self.expected_head = expected_head
        self.actual_head = actual_head


def map_connect_error(err: ConnectError) -> Exception:
    """Map a ConnectError to a typed SDK error if it matches a known error detail.

    Parses the ``debug`` field on each Connect error detail (the JSON
    representation the Go server includes alongside the binary ``value``).
    Returns the original ConnectError if no known detail is found.
    """
    if err.code == "not_found":
        return NotFoundError(str(err) or "not found")

    if err.code == "aborted":
        for detail in err.details:
            if detail.get("type") == "githosted.v1.RepoBusyDetail":
                debug = detail.get("debug", {})
                return RepoBusyError(
                    repo_id=debug.get("repoId", ""),
                    operation=debug.get("operation", ""),
                )

    if err.code == "failed_precondition":
        for detail in err.details:
            if detail.get("type") == "githosted.v1.StaleHeadDetail":
                debug = detail.get("debug", {})
                return StaleHeadError(
                    repo_id=debug.get("repoId", ""),
                    ref=debug.get("ref", ""),
                    expected_head=debug.get("expectedHead", ""),
                    actual_head=debug.get("actualHead", ""),
                )

    return err


def is_not_found_error(err: BaseException) -> bool:
    """Check if an error is a NotFoundError."""
    return isinstance(err, NotFoundError)


def is_repo_busy_error(err: BaseException) -> bool:
    """Check if an error is a RepoBusyError (suitable for auto-retry)."""
    return isinstance(err, RepoBusyError)


def is_stale_head_error(err: BaseException) -> bool:
    """Check if an error is a StaleHeadError (requires caller intervention)."""
    return isinstance(err, StaleHeadError)

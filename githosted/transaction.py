"""Transaction context manager — atomic multi-file writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .retry import with_retry
from .types import WriteResult

if TYPE_CHECKING:
    from .repo import Repo


@dataclass
class _FileChange:
    path: str
    action: str  # "write" or "delete"
    content: bytes = b""


class Transaction:
    """Collects file changes in memory, then commits them.

    Use as a context manager via :meth:`Repo.transaction`::

        with repo.transaction("Refactor auth module") as tx:
            tx.write("src/auth.py", new_auth)
            tx.write("src/config.py", new_config)
            tx.delete("src/old_auth.py")

    On exit, all changes are committed. If ``BatchWrite`` is available on
    the server, they are committed atomically in a single commit. Until
    then, changes are committed sequentially via individual ``WriteFile``
    calls.
    """

    def __init__(
        self,
        repo: Repo,
        message: str,
        *,
        ref: str = "",
        expected_head: str = "",
    ) -> None:
        self._repo = repo
        self._message = message
        self._ref = ref
        self._expected_head = expected_head
        self._changes: list[_FileChange] = []
        self._committed = False

    def write(self, path: str, content: str | bytes) -> None:
        """Stage a file write in this transaction."""
        if self._committed:
            raise RuntimeError("Transaction already committed")
        if isinstance(content, str):
            content = content.encode("utf-8")
        self._changes.append(_FileChange(path=path, action="write", content=content))

    def delete(self, path: str) -> None:
        """Stage a file deletion in this transaction."""
        if self._committed:
            raise RuntimeError("Transaction already committed")
        self._changes.append(_FileChange(path=path, action="delete"))

    def _commit(self) -> WriteResult:
        """Commit all staged changes.

        Called automatically on context manager exit.
        """
        if self._committed:
            raise RuntimeError("Transaction already committed")
        if not self._changes:
            raise RuntimeError("Transaction has no changes")
        self._committed = True

        # BatchWrite fallback: sequential WriteFile calls.
        def _do_commit() -> WriteResult:
            last_result = WriteResult(commit_sha="")
            for change in self._changes:
                if change.action == "write":
                    last_result = self._repo.write(
                        change.path,
                        change.content,
                        self._message,
                        ref=self._ref,
                        expected_head=self._expected_head,
                    )
                elif change.action == "delete":
                    last_result = self._repo.delete(
                        change.path,
                        self._message,
                        ref=self._ref,
                        expected_head=self._expected_head,
                    )
            return last_result

        return with_retry(_do_commit)

    def __enter__(self) -> Transaction:
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        if exc_type is None and not self._committed and self._changes:
            self._commit()

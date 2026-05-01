"""Repo class — filesystem (Level 3) and git (Level 2) APIs."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from .errors import ConnectError, map_connect_error
from .retry import with_retry
from .transaction import Transaction
from .types import (
    CommitEntry,
    DiffResult,
    FileEntry,
    FileResult,
    RepoInfo,
    WriteResult,
    _parse_commit,
)

if TYPE_CHECKING:
    from .client import Client


class Repo:
    """A handle to a githosted repo.

    Provides the Level 3 (filesystem) and Level 2 (git) APIs.

    Created via :meth:`Client.repo` or :meth:`Client.create_repo`.
    """

    def __init__(
        self,
        client: Client,
        repo_ref: str,
        info: RepoInfo | None = None,
    ) -> None:
        self._client = client
        self._repo_ref = repo_ref
        self.info = info
        """Repo metadata, populated after :meth:`Client.create_repo`."""

    @property
    def id(self) -> str | None:
        """The stable repo ID if available."""
        if self.info is not None:
            return self.info.id
        if self._repo_ref.startswith("rp_"):
            return self._repo_ref
        return None

    # ── Level 3: Filesystem API ──

    def ls(self, path: str = "", *, ref: str = "") -> list[FileEntry]:
        """List files and directories at *path*."""
        try:
            res = self._client._transport.call(
                "RepoService",
                "ListFiles",
                {
                    "workspaceRef": "",
                    "repoRef": self._repo_ref,
                    "ref": ref,
                    "path": path,
                },
            )
        except ConnectError as exc:
            raise map_connect_error(exc) from None

        return [
            FileEntry(
                name=e.get("name", ""),
                type="directory" if e.get("type") == "tree" else "file",
            )
            for e in res.get("entries", [])
        ]

    def read(self, path: str, *, ref: str = "") -> FileResult:
        """Read a file's content and metadata.

        Returns :attr:`FileResult.head_sha` for use in subsequent writes
        with optimistic concurrency.
        """
        try:
            res = self._client._transport.call(
                "RepoService",
                "ReadFile",
                {
                    "workspaceRef": "",
                    "repoRef": self._repo_ref,
                    "ref": ref,
                    "path": path,
                },
            )
        except ConnectError as exc:
            raise map_connect_error(exc) from None

        # content is base64-encoded bytes in Connect JSON
        raw = base64.b64decode(res.get("content", ""))
        return FileResult(
            content=raw.decode("utf-8", errors="replace"),
            raw_content=raw,
            head_sha=res.get("headSha", ""),
            blob_sha=res.get("sha", ""),
        )

    def write(
        self,
        path: str,
        content: str | bytes,
        message: str,
        *,
        ref: str = "",
        expected_head: str = "",
    ) -> WriteResult:
        """Write a file. Creates a commit on the target branch.

        Pass *expected_head* for optimistic concurrency (requires server
        support for the ``expected_head`` field on ``WriteFileRequest``).
        """
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content
        content_b64 = base64.b64encode(content_bytes).decode("ascii")

        def _do_write() -> WriteResult:
            try:
                res = self._client._transport.call(
                    "RepoService",
                    "WriteFile",
                    {
                        "workspaceRef": "",
                        "repoRef": self._repo_ref,
                        "branch": ref,
                        "path": path,
                        "content": content_b64,
                        "message": message,
                        "authorName": "",
                        "authorEmail": "",
                    },
                )
            except ConnectError as exc:
                raise map_connect_error(exc) from None
            return WriteResult(commit_sha=res.get("commit", ""))

        return with_retry(_do_write)

    def delete(
        self,
        path: str,
        message: str,
        *,
        ref: str = "",
        expected_head: str = "",
    ) -> WriteResult:
        """Delete a file.

        .. note::
           ``DeleteFile`` is a planned RPC. Until it ships, this writes
           empty content as a placeholder.
        """
        return self.write(path, b"", message, ref=ref, expected_head=expected_head)

    def transaction(
        self,
        message: str,
        *,
        ref: str = "",
        expected_head: str = "",
    ) -> Transaction:
        """Start a transaction — multiple file changes committed together.

        Use as a context manager::

            with repo.transaction("Refactor auth module") as tx:
                tx.write("src/auth.py", new_auth)
                tx.write("src/config.py", new_config)
                tx.delete("src/old_auth.py")

        .. note::
           Until ``BatchWrite`` ships on the server, the transaction falls
           back to sequential ``WriteFile`` calls. This loses atomicity but
           is functionally correct for single-writer scenarios.
        """
        return Transaction(self, message, ref=ref, expected_head=expected_head)

    # ── Level 2: Git API ──

    def log(
        self,
        path: str = "",
        *,
        ref: str = "",
        limit: int = 0,
    ) -> list[CommitEntry]:
        """Get the commit log for the repo, optionally filtered to *path*."""
        try:
            res = self._client._transport.call(
                "RepoService",
                "Log",
                {
                    "workspaceRef": "",
                    "repoRef": self._repo_ref,
                    "ref": ref,
                    "path": path,
                    "limit": limit,
                },
            )
        except ConnectError as exc:
            raise map_connect_error(exc) from None

        return [_parse_commit(c) for c in res.get("commits", [])]

    def diff(self, base_ref: str, head_ref: str) -> DiffResult:
        """Get a diff between two refs."""
        try:
            res = self._client._transport.call(
                "RepoService",
                "Diff",
                {
                    "workspaceRef": "",
                    "repoRef": self._repo_ref,
                    "base": base_ref,
                    "head": head_ref,
                    "path": "",
                },
            )
        except ConnectError as exc:
            raise map_connect_error(exc) from None

        return DiffResult(patch=res.get("patch", ""))

    # ── Level 2: Branch/merge (stubs — require server RPCs) ──

    def create_branch(self, name: str, *, from_ref: str = "") -> None:
        """Create a new branch.

        Raises :class:`NotImplementedError` until the ``CreateBranch``
        RPC ships on the server.
        """
        raise NotImplementedError("create_branch not yet implemented on the server")

    def list_branches(self) -> list[dict[str, str]]:
        """List branches.

        Raises :class:`NotImplementedError` until the ``ListBranches``
        RPC ships on the server.
        """
        raise NotImplementedError("list_branches not yet implemented on the server")

    def merge(self, source: str, *, into: str, message: str = "") -> None:
        """Merge a branch into another.

        Raises :class:`NotImplementedError` until the ``MergeBranch``
        RPC ships on the server.
        """
        raise NotImplementedError("merge not yet implemented on the server")

"""Client class — entry point for all SDK operations."""

from __future__ import annotations

import os
from typing import Union

from .errors import ConnectError, NotFoundError, map_connect_error
from .repo import Repo
from .transport import ConnectTransport
from .types import (
    CreateTokenResult,
    ListReposResult,
    ListTokensResult,
    RepoInfo,
    _TOKEN_KIND_TO_PROTO,
    _PERMISSION_TO_PROTO,
    _parse_repo,
    _parse_token,
)

DEFAULT_BASE_URL = "https://api.githosted.dev"

RepoRef = Union[str, dict[str, str]]
"""Reference to a repo — either a slug string or ``{"id": "rp_xxx"}``."""


def _resolve_token(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    return os.environ.get("GITHOSTED_TOKEN")


class Client:
    """The githosted client. Entry point for all SDK operations.

    The client is workspace-scoped — the workspace is determined by the token.
    It creates internal transports for both RepoService (file/git operations)
    and ApiService (control-plane: list repos, manage tokens).

    Auto-reads ``GITHOSTED_TOKEN`` from the environment if no token is provided.

    Usage::

        from githosted import Client

        client = Client()                          # reads GITHOSTED_TOKEN from env
        client = Client(token="gw_xxx")            # explicit token
        client = Client(base_url="http://localhost:8080")  # custom base URL
    """

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        client_name: str = "sdk-python",
        on_telemetry: object | None = None,
    ) -> None:
        self.base_url = base_url or DEFAULT_BASE_URL
        self.token = _resolve_token(token)
        self._transport = ConnectTransport(
            self.base_url,
            self.token,
            client_name=client_name,
            on_telemetry=on_telemetry,
        )

    def repo(
        self,
        slug: str | None = None,
        *,
        id: str | None = None,
    ) -> Repo:
        """Get a Repo handle for an existing repo.

        Pass a slug (``"my-project"``) or a stable ID
        (``id="rp_xxx"``).  Workspace is inferred from the token.
        """
        if id is not None:
            return Repo(self, repo_ref=id)
        if slug is not None:
            return Repo(self, repo_ref=slug)
        raise ValueError("Either slug or id must be provided")

    def get_or_create_repo(
        self,
        slug: str,
        *,
        name: str | None = None,
    ) -> Repo:
        """Return a :class:`Repo` handle for *slug*, creating the repo if
        it does not already exist.

        Safe to call concurrently — if two callers race the creation, the
        loser catches ``already_exists`` and falls back to looking up the
        winner's repo.

        *name* defaults to *slug* when omitted.
        """
        repo = self.repo(slug)
        try:
            repo.ls("")
            return repo
        except NotFoundError:
            pass
        try:
            return self.create_repo(name or slug, slug=slug)
        except ConnectError as exc:
            if exc.code != "already_exists":
                raise
        return self.repo(slug)

    def create_repo(
        self,
        name: str,
        *,
        slug: str = "",
    ) -> Repo:
        """Create a new repo in the current workspace.

        Returns a :class:`Repo` handle with a stable ID.
        """
        try:
            res = self._transport.call(
                "RepoService",
                "CreateRepo",
                {
                    "workspaceRef": "",
                    "name": name,
                    "slug": slug,
                },
            )
        except ConnectError as exc:
            raise map_connect_error(exc) from None

        repo_data = res.get("repo")
        if not repo_data:
            raise RuntimeError("CreateRepo returned no repo")
        info = _parse_repo(repo_data)
        return Repo(self, repo_ref=info.id, info=info)

    def list_repos(
        self,
        *,
        page_size: int = 0,
        page_token: str = "",
    ) -> ListReposResult:
        """List repos in the current workspace.

        Requires a workspace token (``gw_``). Repo tokens are rejected.
        """
        try:
            res = self._transport.call(
                "ApiService",
                "ListRepos",
                {
                    "organizationRef": "",
                    "workspaceRef": "",
                    "pageSize": page_size,
                    "pageToken": page_token,
                },
            )
        except ConnectError as exc:
            raise map_connect_error(exc) from None

        return ListReposResult(
            repos=[_parse_repo(r) for r in res.get("repos", [])],
            next_page_token=res.get("nextPageToken") or None,
        )

    def list_tokens(
        self,
        *,
        page_size: int = 0,
        page_token: str = "",
    ) -> ListTokensResult:
        """List tokens in the current workspace.

        Requires a workspace token (``gw_``). Repo tokens are rejected.
        """
        try:
            res = self._transport.call(
                "ApiService",
                "ListTokens",
                {
                    "organizationRef": "",
                    "workspaceRef": "",
                    "pageSize": page_size,
                    "pageToken": page_token,
                },
            )
        except ConnectError as exc:
            raise map_connect_error(exc) from None

        return ListTokensResult(
            tokens=[_parse_token(t) for t in res.get("tokens", [])],
            next_page_token=res.get("nextPageToken") or None,
        )

    def create_token(
        self,
        name: str,
        *,
        kind: str = "workspace",
        permission: str = "write",
        repo_allowlist: list[str] | None = None,
        ttl_hours: int = 0,
    ) -> CreateTokenResult:
        """Create a new token in the current workspace.

        Requires a workspace token (``gw_``) with write permission.

        The returned ``token`` value is only available at creation time —
        store it immediately.

        Args:
            name: Human-readable label for the token.
            kind: ``"workspace"`` or ``"repo"``.
            permission: ``"read"`` or ``"write"``.
            repo_allowlist: Repo slugs this token can access (repo tokens only).
            ttl_hours: Time-to-live in hours. 0 means no expiry.
        """
        try:
            res = self._transport.call(
                "ApiService",
                "CreateToken",
                {
                    "organizationRef": "",
                    "workspaceRef": "",
                    "name": name,
                    "kind": _TOKEN_KIND_TO_PROTO.get(kind, "TOKEN_KIND_WORKSPACE"),
                    "permission": _PERMISSION_TO_PROTO.get(permission, "PERMISSION_WRITE"),
                    "repoAllowlist": repo_allowlist or [],
                    "ttlHours": ttl_hours,
                },
            )
        except ConnectError as exc:
            raise map_connect_error(exc) from None

        record_data = res.get("record")
        if not record_data:
            raise RuntimeError("CreateToken returned no record")

        return CreateTokenResult(
            token=res.get("token", ""),
            record=_parse_token(record_data),
        )

    def exchange_token(
        self,
        *,
        repo_allowlist: list[str],
        permission: str = "read",
        ttl_seconds: int = 0,
        subject: str = "",
    ) -> CreateTokenResult:
        """Issue a short-lived, narrowly-scoped ``gr_`` token on behalf of
        an end-user session.

        Intended for the "customer backend mints a per-user token" pattern:
        the backend authenticates the user itself, calls this with its
        ``gw_`` token in its environment, and hands the returned ``gr_``
        back to the browser. The browser then talks to githosted directly
        without ever seeing the ``gw_``.

        Requires a workspace (``gw_``) token with write permission.

        Args:
            repo_allowlist: Repos the issued token may access. Required —
                exchange tokens are always narrow-scoped.
            permission: ``"read"`` (default) or ``"write"``. Cannot exceed
                the parent token's permission.
            ttl_seconds: TTL in seconds. 0 picks the server default
                (1 hour). Clamped to the server max (24 hours).
            subject: Optional opaque identifier for the end user/session;
                stored on the token record for auditing.
        """
        if not repo_allowlist:
            raise ValueError("repo_allowlist must contain at least one repo")
        try:
            res = self._transport.call(
                "ApiService",
                "ExchangeToken",
                {
                    "repoAllowlist": list(repo_allowlist),
                    "permission": _PERMISSION_TO_PROTO.get(
                        permission, "PERMISSION_READ"
                    ),
                    "ttlSeconds": ttl_seconds,
                    "subject": subject,
                },
            )
        except ConnectError as exc:
            raise map_connect_error(exc) from None

        record_data = res.get("record")
        if not record_data:
            raise RuntimeError("ExchangeToken returned no record")

        return CreateTokenResult(
            token=res.get("token", ""),
            record=_parse_token(record_data),
        )

    def close(self) -> None:
        """Close the underlying HTTP transport."""
        self._transport.close()

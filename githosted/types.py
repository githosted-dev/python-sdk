"""Data types returned by the SDK."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# File API types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileEntry:
    """A file or directory returned by :meth:`Repo.ls`."""

    name: str
    type: str  # "file" or "directory"


@dataclass(frozen=True)
class FileResult:
    """Result of reading a file, including content and metadata."""

    content: str
    """UTF-8 decoded file content."""
    raw_content: bytes
    """Raw file content as bytes."""
    head_sha: str
    """Branch tip at read time. Pass back as *expected_head* on writes."""
    blob_sha: str
    """Content-addressable blob hash."""


@dataclass(frozen=True)
class WriteResult:
    """Result of a write operation."""

    commit_sha: str
    """SHA of the commit created by the write."""


# ---------------------------------------------------------------------------
# Git API types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CommitEntry:
    """A commit from the log."""

    hash: str
    author_name: str
    author_email: str
    committed_at: datetime
    subject: str


@dataclass(frozen=True)
class DiffResult:
    """A diff patch result."""

    patch: str


# ---------------------------------------------------------------------------
# Repo / Token metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RepoInfo:
    """Repo metadata returned by create_repo / list_repos."""

    id: str
    workspace_id: str
    name: str
    slug: str
    default_branch: str
    created_at: datetime


@dataclass(frozen=True)
class TokenInfo:
    """Token metadata returned by list_tokens / create_token."""

    id: str
    prefix: str
    name: str
    kind: str  # "workspace" or "repo"
    organization_id: str
    workspace_id: str
    permission: str  # "read" or "write"
    repo_allowlist: list[str]
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    created_by_user_id: str = ""
    created_by_name: str = ""
    created_by_token_prefix: str = ""


@dataclass(frozen=True)
class CreateTokenResult:
    """Result of creating a token — includes the raw token value (shown once)."""

    token: str
    """The raw token string (gw_ or gr_ prefix). Only returned at creation time."""
    record: TokenInfo


@dataclass(frozen=True)
class ListReposResult:
    """Paginated list of repos."""

    repos: list[RepoInfo]
    next_page_token: str | None = None


@dataclass(frozen=True)
class ListTokensResult:
    """Paginated list of tokens."""

    tokens: list[TokenInfo]
    next_page_token: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_timestamp(value: Any) -> datetime:
    """Parse a protobuf JSON timestamp (RFC 3339) into a datetime."""
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if isinstance(value, str):
        # Handle both "2024-01-15T10:30:00Z" and "2024-01-15T10:30:00.000Z"
        s = value.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _parse_optional_timestamp(value: Any) -> datetime | None:
    """Parse an optional protobuf JSON timestamp."""
    if not value:
        return None
    return _parse_timestamp(value)


_TOKEN_KIND_MAP = {
    "TOKEN_KIND_WORKSPACE": "workspace",
    "TOKEN_KIND_REPO": "repo",
}

_PERMISSION_MAP = {
    "PERMISSION_READ": "read",
    "PERMISSION_WRITE": "write",
}

_TOKEN_KIND_TO_PROTO = {v: k for k, v in _TOKEN_KIND_MAP.items()}
_PERMISSION_TO_PROTO = {v: k for k, v in _PERMISSION_MAP.items()}


def _parse_repo(data: dict[str, Any]) -> RepoInfo:
    return RepoInfo(
        id=data.get("id", ""),
        workspace_id=data.get("workspaceId", ""),
        name=data.get("name", ""),
        slug=data.get("slug", ""),
        default_branch=data.get("defaultBranch", ""),
        created_at=_parse_timestamp(data.get("createdAt")),
    )


def _parse_token(data: dict[str, Any]) -> TokenInfo:
    return TokenInfo(
        id=data.get("id", ""),
        prefix=data.get("prefix", ""),
        name=data.get("name", ""),
        kind=_TOKEN_KIND_MAP.get(data.get("kind", ""), "workspace"),
        organization_id=data.get("organizationId", ""),
        workspace_id=data.get("workspaceId", ""),
        permission=_PERMISSION_MAP.get(data.get("permission", ""), "write"),
        repo_allowlist=data.get("repoAllowlist", []),
        created_at=_parse_timestamp(data.get("createdAt")),
        expires_at=_parse_optional_timestamp(data.get("expiresAt")),
        revoked_at=_parse_optional_timestamp(data.get("revokedAt")),
        last_used_at=_parse_optional_timestamp(data.get("lastUsedAt")),
        created_by_user_id=data.get("createdByUserId", ""),
        created_by_name=data.get("createdByName", ""),
        created_by_token_prefix=data.get("createdByTokenPrefix", ""),
    )


def _parse_commit(data: dict[str, Any]) -> CommitEntry:
    return CommitEntry(
        hash=data.get("hash", ""),
        author_name=data.get("authorName", ""),
        author_email=data.get("authorEmail", ""),
        committed_at=_parse_timestamp(data.get("committedAt")),
        subject=data.get("subject", ""),
    )

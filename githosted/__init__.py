"""githosted — Python SDK for git-backed file storage for AI agents.

Usage::

    from githosted import Client

    client = Client()  # auto-reads GITHOSTED_TOKEN from env
    repo = client.repo("my-project")

    files = repo.ls("src/")
    file = repo.read("src/main.py")
    repo.write("src/main.py", new_content, message="Fix bug")
"""

from .client import Client
from .errors import (
    ConnectError,
    NotFoundError,
    RepoBusyError,
    StaleHeadError,
    is_not_found_error,
    is_repo_busy_error,
    is_stale_head_error,
)
from .repo import Repo
from .transaction import Transaction
from .types import (
    CommitEntry,
    CreateTokenResult,
    DiffResult,
    FileEntry,
    FileResult,
    ListReposResult,
    ListTokensResult,
    RepoInfo,
    TokenInfo,
    WriteResult,
)

__all__ = [
    # Core
    "Client",
    "Repo",
    "Transaction",
    # Errors
    "ConnectError",
    "NotFoundError",
    "RepoBusyError",
    "StaleHeadError",
    "is_not_found_error",
    "is_repo_busy_error",
    "is_stale_head_error",
    # Types
    "CommitEntry",
    "CreateTokenResult",
    "DiffResult",
    "FileEntry",
    "FileResult",
    "ListReposResult",
    "ListTokensResult",
    "RepoInfo",
    "TokenInfo",
    "WriteResult",
]

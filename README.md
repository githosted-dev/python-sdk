# githosted

Python SDK for [githosted](https://githosted.dev) — read, write, and diff files in versioned Git repos without shelling out.

`githosted` exposes a small, typed surface for the operations you actually do against a repo: read a file, commit a change, list history, diff two refs. Real Git underneath; you're not talking to a custom blob store.

## Install

```sh
pip install githosted
```

Requires Python 3.10+.

## Quick start

```python
from githosted import Client

repo = Client(token="gw_…").repo("my-agent")

# Write a file (creates a commit). `message` is positional.
repo.write("output.json", b'{"status": "ok"}', "Run #42")

# Read it back. `content` is the UTF-8-decoded string;
# `raw_content` is the original bytes.
result = repo.read("output.json")
print(result.content)

# Walk recent history.
for commit in repo.log(limit=5):
    print(commit.hash[:7], commit.subject)

# Diff between two refs.
delta = repo.diff("HEAD~1", "HEAD")
print(delta.patch)
```

## Authentication

Tokens are scoped to a workspace. Mint one at [app.githosted.dev → Tokens](https://app.githosted.dev), then pass it to `Client(token=…)`.

| Token prefix | Scope |
|---|---|
| `gw_…` | Read + write |
| `gr_…` | Read-only |

For local development, set `GITHOSTED_TOKEN` and use `Client.from_env()`.

## Errors

The SDK raises typed exceptions you can match on:

```python
from githosted import (
    Client,
    NotFoundError,
    RepoBusyError,
    StaleHeadError,
)

try:
    repo.read("missing.txt")
except NotFoundError:
    ...
```

`RepoBusyError` and `StaleHeadError` are retryable — `with_retry()` is included for the common backoff loop.

## Documentation

- [Quickstart](https://docs.githosted.dev/welcome/quickstart/)
- [Python SDK reference](https://docs.githosted.dev/sdks/python/)
- [HTTP API](https://docs.githosted.dev/reference/http-api/)

## License

MIT.

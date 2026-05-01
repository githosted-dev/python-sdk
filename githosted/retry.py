"""Jittered exponential backoff for RepoBusyError."""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from .errors import is_repo_busy_error

T = TypeVar("T")

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY_MS = 100


def with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay_ms: float = DEFAULT_BASE_DELAY_MS,
    on_retry: Callable[[int], None] | None = None,
) -> T:
    """Call *fn*, retrying on RepoBusyError with exponential backoff.

    Only retries on ``RepoBusyError``; all other exceptions propagate
    immediately.
    """
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            if not is_repo_busy_error(exc) or attempt >= max_retries:
                raise
            if on_retry is not None:
                on_retry(attempt + 1)
            jitter = random.uniform(0.75, 1.25)
            delay_s = (base_delay_ms * (2**attempt) * jitter) / 1000
            time.sleep(delay_s)
    raise RuntimeError("unreachable")  # pragma: no cover

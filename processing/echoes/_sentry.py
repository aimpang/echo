"""Optional Sentry integration for the processing worker.

No-op unless ``SENTRY_DSN`` is set AND ``sentry_sdk`` is installed — keeping
the dep optional so CI/local dev don't need it, while production deployments
can opt in by installing ``sentry-sdk`` and setting the DSN.
"""

from __future__ import annotations

import logging
import os

LOG = logging.getLogger(__name__)

_initialised = False


def init_sentry_if_configured() -> None:
    """Initialise sentry_sdk exactly once; safe to call from multiple places."""
    global _initialised
    if _initialised:
        return
    _initialised = True

    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return

    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError:
        LOG.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed — skipping."
        )
        return

    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        environment=os.environ.get("SENTRY_ENV", "worker"),
    )
    LOG.info("Sentry initialised.")


def capture_exception(err: BaseException) -> None:
    """Send ``err`` to Sentry if configured; otherwise a no-op.

    Always safe to call — the worker's failure paths use this so we don't
    silently swallow crashes even if Sentry isn't wired up.
    """
    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError:
        return
    sentry_sdk.capture_exception(err)

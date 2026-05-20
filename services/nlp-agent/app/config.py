"""Process-level configuration and startup safety checks.

The dev-only escape hatches `SKIP_JWT_VALIDATION` and `DEV_USER_BANK_CUSTOMER_ID` must
never be active in production. `assert_safety_or_exit()` enforces that at startup.
"""

import os
import sys


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def assert_safety_or_exit() -> None:
    """Exit with code 2 if `SKIP_JWT_VALIDATION=true` while `ENV=production`."""
    env = os.getenv("ENV", "dev").lower()
    skip_jwt = env_bool("SKIP_JWT_VALIDATION", default=False)
    if env == "production" and skip_jwt:
        sys.stderr.write(
            "FATAL: SKIP_JWT_VALIDATION=true is not allowed when ENV=production. "
            "Refusing to start.\n"
        )
        raise SystemExit(2)

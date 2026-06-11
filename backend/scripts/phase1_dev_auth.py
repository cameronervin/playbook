"""Seed local Phase 1 validation users and mint app JWTs.

This module is intentionally local-development tooling. It creates throwaway
users in the configured backend database so Swagger and curl can exercise
role-protected endpoints without requiring real OAuth providers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import sys
from pathlib import Path
from typing import Literal

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.infrastructure.db.session import (  # noqa: E402
    cleanup_db_engine,
    get_session_factory,
)
from app.services.dev_auth_service import (  # noqa: E402
    ROLE_TARGET_KEY,
    DevAuthService,
    SeededPrincipal,
)


async def seed_phase1_users(
    session: AsyncSession,
    settings: Settings | None = None,
) -> dict[str, SeededPrincipal]:
    """Create or normalize throwaway users used by manual endpoint validation."""
    return await DevAuthService(session, settings=settings or get_settings()).seed_users()


def render_shell_exports(seeded: dict[str, SeededPrincipal]) -> str:
    """Render shell exports consumable by eval/source."""
    athlete = seeded["athlete"]
    admin = seeded["admin"]
    super_admin = seeded["super_admin"]
    role_target = seeded[ROLE_TARGET_KEY]
    exports = {
        "ATHLETE_TOKEN": athlete.token,
        "ADMIN_TOKEN": admin.token,
        "SUPER_TOKEN": super_admin.token,
        "ROLE_TARGET_ID": str(role_target.user_id),
        "ROLE_TARGET_EMAIL": role_target.email,
    }
    return "\n".join(
        f"export {name}={shlex.quote(value)}" for name, value in exports.items()
    )


def render_json(seeded: dict[str, SeededPrincipal]) -> str:
    """Render seeded principals as JSON for inspection or automation."""
    payload = {
        key: {
            "email": principal.email,
            "role": principal.role,
            "user_id": str(principal.user_id),
            "token": principal.token,
        }
        for key, principal in seeded.items()
    }
    return json.dumps(payload, indent=2, sort_keys=True)


async def _run(format_name: Literal["shell", "json"]) -> str:
    settings = get_settings()
    async with get_session_factory(settings)() as session:
        seeded = await seed_phase1_users(session, settings)
    await cleanup_db_engine()
    if format_name == "json":
        return render_json(seeded)
    return render_shell_exports(seeded)


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Seed Phase 1 local validation users and print app JWT exports.",
    )
    parser.add_argument(
        "--format",
        choices=("shell", "json"),
        default="shell",
        help="Output format. Use shell with eval, or json for inspection.",
    )
    args = parser.parse_args()
    print(asyncio.run(_run(args.format)))


if __name__ == "__main__":
    main()

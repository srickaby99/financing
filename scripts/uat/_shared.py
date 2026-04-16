"""Shared helpers for UAT scripts — database session and state file management."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure project root is importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

STATE_FILE = Path(__file__).parent / "uat_state.json"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def make_engine():
    return create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)


def make_session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(data: dict) -> None:
    current = load_state()
    current.update(data)
    STATE_FILE.write_text(json.dumps(current, indent=2))


def require_state(*keys: str) -> dict:
    state = load_state()
    missing = [k for k in keys if k not in state]
    if missing:
        print(f"\n  ERROR: Missing state keys: {', '.join(missing)}")
        print(f"  Have you run the previous steps? Check {STATE_FILE}")
        sys.exit(1)
    return state


def clear_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def header(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print()


def field(label: str, value) -> None:
    print(f"  {label:<28} {value}")


def sql_hint(query: str) -> None:
    print()
    print("  Verify in PostgreSQL:")
    print(f"    {query}")
    print()

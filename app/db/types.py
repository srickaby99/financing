"""Custom SQLAlchemy column types for cross-dialect compatibility."""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator


class DialectJSON(TypeDecorator):
    """Uses JSONB on PostgreSQL; falls back to JSON for other dialects (e.g. SQLite in tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())

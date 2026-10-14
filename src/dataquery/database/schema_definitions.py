"""Dynamic database schema discovery, reflection, and sensitivity filtering.

Inspects PostgreSQL tables dynamically at runtime via SQLAlchemy reflection.
Removes static hardcoded schemas so any newly added, altered, or dropped tables
are automatically discovered without manual code changes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from dataquery.database.connection import get_engine, test_db_connection
from dataquery.schemas.database import ColumnSchema, RelationshipSchema, TableSchema
from dataquery.sql.policy import BLOCKED_TABLES, is_column_sensitive

logger = logging.getLogger(__name__)

_SCHEMA_CACHE_LOCK = threading.RLock()
_CACHED_SAFE_TABLES: dict[str, TableSchema] | None = None
_LAST_INSPECTED_AT: float = 0.0
_CACHE_TTL_SECONDS: float = 300.0


def _generate_table_description(table_name: str, comment: str | None, columns: list[dict[str, Any]]) -> str:
    """Generate a clean business description from database comments or column structure."""
    if comment and comment.strip():
        return comment.strip()

    col_names = [c["name"].lower() for c in columns]
    name_clean = table_name.replace("_", " ")

    if "user" in table_name and ("email" in col_names or "plan" in col_names):
        return f"User accounts, authentication details, and profiles ({name_clean})."
    if "payment" in table_name or "transaction" in table_name:
        return f"Payment records, transactions, billing plans, and revenue metrics ({name_clean})."
    if "rank" in table_name or "position" in col_names:
        return f"App store ranking history and position metrics ({name_clean})."
    if "audit" in table_name or "score" in col_names:
        return f"Application audit history, quality scores, and review metrics ({name_clean})."
    if "app" in table_name and ("url" in col_names or "name" in col_names):
        return f"Applications, tracked apps, and store metadata ({name_clean})."
    if "keyword" in table_name:
        return f"Search terms, keywords, and app keyword associations ({name_clean})."
    if "categor" in table_name:
        return f"Store category performance, snapshot metrics, and taxonomy ({name_clean})."
    if "slack" in table_name or "notif" in table_name:
        return f"Integration configurations and notification alert settings ({name_clean})."
    if "activit" in table_name or "log" in table_name:
        return f"User session activities, event logs, and timestamps ({name_clean})."

    return f"Database table storing {name_clean} records."


def _generate_domain_notes(table_name: str, columns: list[ColumnSchema], sensitive_cols: list[str]) -> list[str]:
    """Generate intelligent domain rules based on dynamic column properties."""
    notes: list[str] = []
    col_names = {c.name.lower() for c in columns}

    if sensitive_cols:
        cols_str = ", ".join(sensitive_cols)
        notes.append(f"Sensitive column(s) [{cols_str}] must NEVER be queried, projected, or returned.")

    if "rank" in col_names:
        notes.append("A lower numerical rank indicates superior performance (rank = 1 is the best/top position).")

    if "is_deleted" in col_names:
        notes.append("Filter 'is_deleted = false' for active records unless specifically asked about deleted records.")

    if "login_at" in col_names and "logout_at" in col_names:
        notes.append("Session duration can be calculated as EXTRACT(EPOCH FROM (logout_at - login_at)).")

    if "status" in col_names and "payment" in table_name:
        notes.append("Filter for successful transactions using status IN ('captured', 'success').")

    if "opportunity_score" in col_names:
        notes.append("Higher opportunity_score indicates greater potential.")

    return notes


def introspect_database_schema(engine: Engine | None = None, force_refresh: bool = False) -> dict[str, TableSchema]:
    """Dynamically introspect database tables, columns, constraints, and relationships.

    Reflects live schema directly from PostgreSQL. Sensitive columns are automatically
    detected and marked is_sensitive=True, and blocked tables are excluded.
    """
    global _CACHED_SAFE_TABLES, _LAST_INSPECTED_AT

    with _SCHEMA_CACHE_LOCK:
        now = time.time()
        if (
            not force_refresh
            and _CACHED_SAFE_TABLES is not None
            and (now - _LAST_INSPECTED_AT) < _CACHE_TTL_SECONDS
        ):
            return _CACHED_SAFE_TABLES

        if engine is None:
            engine = get_engine()

        try:
            inspector = inspect(engine)
            table_names = inspector.get_table_names(schema="public")
            if not table_names:
                table_names = inspector.get_table_names()

            discovered_tables: dict[str, TableSchema] = {}

            ignored_prefixes = ("pg_", "sql_", "alembic_")
            allowed_names = [
                t for t in table_names
                if not t.startswith(ignored_prefixes)
                and t.lower().strip() not in BLOCKED_TABLES
            ]

            for table_name in allowed_names:
                try:
                    raw_columns = inspector.get_columns(table_name, schema="public")
                except Exception:
                    try:
                        raw_columns = inspector.get_columns(table_name)
                    except Exception as e:
                        logger.warning(f"Failed to inspect columns for table '{table_name}': {e}")
                        continue

                try:
                    pk_constraint = inspector.get_pk_constraint(table_name, schema="public")
                    pk_columns = set(pk_constraint.get("constrained_columns") or [])
                except Exception:
                    pk_columns = set()

                try:
                    fks = inspector.get_foreign_keys(table_name, schema="public") or []
                except Exception:
                    fks = []

                fk_map: dict[str, tuple[str, str]] = {}
                relationships: list[RelationshipSchema] = []
                for fk in fks:
                    referred_table = fk.get("referred_table")
                    constrained_cols = fk.get("constrained_columns") or []
                    referred_cols = fk.get("referred_columns") or []
                    for c_col, r_col in zip(constrained_cols, referred_cols):
                        fk_map[c_col] = (referred_table, r_col)
                        relationships.append(
                            RelationshipSchema(
                                from_table=table_name,
                                from_column=c_col,
                                to_table=referred_table,
                                to_column=r_col,
                                relationship_type="many_to_one",
                            )
                        )

                try:
                    comment_info = inspector.get_table_comment(table_name, schema="public")
                    table_comment = comment_info.get("text")
                except Exception:
                    table_comment = None

                columns: list[ColumnSchema] = []
                sensitive_col_names: list[str] = []

                for col in raw_columns:
                    col_name = col["name"]
                    col_type_str = str(col["type"]).lower()
                    is_pk = col_name in pk_columns
                    is_fk = col_name in fk_map
                    target_tbl, target_col = fk_map.get(col_name, (None, None))
                    is_sens = is_column_sensitive(table_name, col_name)

                    if is_sens:
                        sensitive_col_names.append(col_name)

                    columns.append(
                        ColumnSchema(
                            name=col_name,
                            type=col_type_str,
                            nullable=col.get("nullable", True),
                            primary_key=is_pk,
                            is_foreign_key=is_fk,
                            foreign_table=target_tbl,
                            foreign_column=target_col,
                            description=col.get("comment"),
                            is_sensitive=is_sens,
                        )
                    )

                safe_columns = [c for c in columns if not c.is_sensitive]
                domain_notes = _generate_domain_notes(table_name, columns, sensitive_col_names)
                description = _generate_table_description(table_name, table_comment, raw_columns)

                discovered_tables[table_name.lower().strip()] = TableSchema(
                    name=table_name,
                    description=description,
                    columns=safe_columns,
                    primary_key=list(pk_columns),
                    relationships=relationships,
                    domain_notes=domain_notes,
                )

            if discovered_tables:
                logger.info(f"Dynamically introspected {len(discovered_tables)} tables from database.")
                _CACHED_SAFE_TABLES = discovered_tables
                _LAST_INSPECTED_AT = now
                return discovered_tables

        except Exception as exc:
            logger.warning(f"Dynamic database schema introspection error: {exc}")

        if _CACHED_SAFE_TABLES:
            return _CACHED_SAFE_TABLES

        return _get_offline_fallback_schemas()


def _get_offline_fallback_schemas() -> dict[str, TableSchema]:
    """Lightweight fallback schema definitions used only when database is offline during cold test runs."""
    fallback_tables: dict[str, TableSchema] = {
        "users": TableSchema(
            name="users",
            description="User accounts, authentication providers, and subscription plan tiers.",
            columns=[
                ColumnSchema(name="id", type="integer", nullable=False, primary_key=True, description="Unique user ID"),
                ColumnSchema(name="email", type="varchar(255)", nullable=False, description="User email address"),
                ColumnSchema(name="auth_provider", type="varchar(50)", nullable=True, description="Authentication provider"),
                ColumnSchema(name="role", type="varchar(20)", nullable=True, description="User role"),
                ColumnSchema(name="plan", type="varchar(50)", nullable=True, description="Current subscription plan"),
                ColumnSchema(name="plan_purchased_at", type="timestamp", nullable=True, description="Plan purchase date"),
                ColumnSchema(name="plan_expires_at", type="timestamp", nullable=True, description="Plan expiration timestamp"),
                ColumnSchema(name="created_at", type="timestamp", nullable=True, description="Registration timestamp"),
            ],
            primary_key=["id"],
            domain_notes=["Sensitive column hashed_password must NEVER be returned in any query."],
        ),
        "apps": TableSchema(
            name="apps",
            description="Tracked applications, competitor apps, and audit metadata.",
            columns=[
                ColumnSchema(name="id", type="integer", nullable=False, primary_key=True, description="App ID"),
                ColumnSchema(name="user_id", type="integer", nullable=False, is_foreign_key=True, foreign_table="users", foreign_column="id"),
                ColumnSchema(name="name", type="varchar", nullable=False, description="Application display name"),
                ColumnSchema(name="url", type="varchar", nullable=False, description="Store URL"),
                ColumnSchema(name="is_competitor", type="boolean", nullable=False, description="Whether marked competitor"),
                ColumnSchema(name="is_deleted", type="boolean", nullable=False, description="Soft deletion status"),
                ColumnSchema(name="created_at", type="timestamp", nullable=True),
                ColumnSchema(name="audit_run_count", type="integer", nullable=True),
            ],
            primary_key=["id"],
            relationships=[
                RelationshipSchema(from_table="apps", from_column="user_id", to_table="users", to_column="id")
            ],
            domain_notes=["Filter is_deleted = false for active apps unless specifically requested."],
        ),
        "user_activities": TableSchema(
            name="user_activities",
            description="User session activity records, login timestamps, and logout timestamps.",
            columns=[
                ColumnSchema(name="id", type="integer", nullable=False, primary_key=True),
                ColumnSchema(name="user_id", type="integer", nullable=False, is_foreign_key=True, foreign_table="users", foreign_column="id"),
                ColumnSchema(name="login_at", type="timestamp", nullable=True),
                ColumnSchema(name="logout_at", type="timestamp", nullable=True),
            ],
            primary_key=["id"],
            relationships=[
                RelationshipSchema(from_table="user_activities", from_column="user_id", to_table="users", to_column="id")
            ],
        ),
        "payment_transactions": TableSchema(
            name="payment_transactions",
            description="Payment transactions, billing cycles, currency, and revenue.",
            columns=[
                ColumnSchema(name="id", type="integer", nullable=False, primary_key=True),
                ColumnSchema(name="user_id", type="integer", nullable=False, is_foreign_key=True, foreign_table="users", foreign_column="id"),
                ColumnSchema(name="plan_id", type="varchar(50)", nullable=False),
                ColumnSchema(name="amount", type="numeric(10,2)", nullable=False),
                ColumnSchema(name="currency", type="varchar(10)", nullable=False),
                ColumnSchema(name="status", type="varchar(50)", nullable=False),
                ColumnSchema(name="created_at", type="timestamp", nullable=True),
            ],
            primary_key=["id"],
            relationships=[
                RelationshipSchema(from_table="payment_transactions", from_column="user_id", to_table="users", to_column="id")
            ],
            domain_notes=["razorpay_signature is sensitive and excluded."],
        ),
        "ranking_history": TableSchema(
            name="ranking_history",
            description="Historical keyword rankings for applications.",
            columns=[
                ColumnSchema(name="id", type="integer", nullable=False, primary_key=True),
                ColumnSchema(name="app_id", type="integer", nullable=False, is_foreign_key=True, foreign_table="apps", foreign_column="id"),
                ColumnSchema(name="keyword_id", type="integer", nullable=False, is_foreign_key=True, foreign_table="keywords", foreign_column="id"),
                ColumnSchema(name="rank", type="integer", nullable=False),
                ColumnSchema(name="checked_at", type="timestamp", nullable=True),
            ],
            primary_key=["id"],
            domain_notes=["A lower numerical rank indicates superior position (rank = 1 is top)."],
        ),
        "shopify_categories": TableSchema(
            name="shopify_categories",
            description="App store categories and opportunity scores.",
            columns=[
                ColumnSchema(name="id", type="integer", nullable=False, primary_key=True),
                ColumnSchema(name="title", type="varchar", nullable=False),
                ColumnSchema(name="opportunity_score", type="numeric(5,2)", nullable=True),
                ColumnSchema(name="app_count", type="integer", nullable=True),
                ColumnSchema(name="avg_rating", type="numeric(3,2)", nullable=True),
                ColumnSchema(name="review_velocity_30d", type="numeric(8,2)", nullable=True),
            ],
            primary_key=["id"],
        ),
    }
    return fallback_tables


def refresh_schema_cache() -> dict[str, TableSchema]:
    """Force an immediate re-inspection of the database schema."""
    return introspect_database_schema(force_refresh=True)


def get_safe_table_schemas() -> list[TableSchema]:
    """Return all safe table schemas dynamically introspected from the database."""
    tables_dict = introspect_database_schema()
    return list(tables_dict.values())


def get_safe_table_dict() -> dict[str, TableSchema]:
    """Return mapping of table_name -> TableSchema dynamically introspected from the database."""
    return introspect_database_schema()

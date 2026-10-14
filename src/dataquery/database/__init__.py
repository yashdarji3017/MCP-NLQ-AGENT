"""Database connection, schema definitions, and safe execution package."""

from dataquery.database.connection import get_db_connection, get_engine, test_db_connection
from dataquery.database.executor import (
    execute_safe_query,
    explain_safe_query,
    get_table_sample,
)
from dataquery.database.metadata import SchemaManager, get_schema_manager
from dataquery.database.schema_definitions import (
    get_safe_table_dict,
    get_safe_table_schemas,
)

__all__ = [
    "get_engine",
    "get_db_connection",
    "test_db_connection",
    "execute_safe_query",
    "explain_safe_query",
    "get_table_sample",
    "SchemaManager",
    "get_schema_manager",
    "get_safe_table_dict",
    "get_safe_table_schemas",
]

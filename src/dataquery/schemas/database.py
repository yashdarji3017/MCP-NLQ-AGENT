"""Database schema representation models."""

from typing import Any
from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    """Schema definition for a database table column."""

    name: str = Field(..., description="Column name")
    type: str = Field(..., description="PostgreSQL data type")
    nullable: bool = Field(default=True, description="Whether the column allows NULL values")
    primary_key: bool = Field(default=False, description="Whether this column is part of the primary key")
    is_foreign_key: bool = Field(default=False, description="Whether this column is a foreign key")
    foreign_table: str | None = Field(default=None, description="Target table for foreign key")
    foreign_column: str | None = Field(default=None, description="Target column for foreign key")
    description: str | None = Field(default=None, description="Domain meaning of this column")
    is_sensitive: bool = Field(default=False, description="Whether column is classified as sensitive")


class RelationshipSchema(BaseModel):
    """Foreign key or logical relationship between tables."""

    from_table: str = Field(..., description="Source table")
    from_column: str = Field(..., description="Source column")
    to_table: str = Field(..., description="Target table")
    to_column: str = Field(..., description="Target column")
    relationship_type: str = Field(default="many_to_one", description="Relationship cardinality")


class TableSchema(BaseModel):
    """Schema definition for a database table."""

    name: str = Field(..., description="Table name")
    description: str = Field(..., description="Business domain description of the table")
    columns: list[ColumnSchema] = Field(default_factory=list, description="List of safe columns in the table")
    primary_key: list[str] = Field(default_factory=list, description="Primary key column names")
    relationships: list[RelationshipSchema] = Field(
        default_factory=list, description="Foreign key relationships"
    )
    domain_notes: list[str] = Field(
        default_factory=list, description="Special domain guidance (e.g. rank 1 is best)"
    )


class DatabaseSchema(BaseModel):
    """Collection of tables available for query generation."""

    tables: list[TableSchema] = Field(default_factory=list, description="List of accessible tables")


class SchemaSearchResult(BaseModel):
    """Targeted schema subset matched for a specific natural language query."""

    tables: list[str] = Field(default_factory=list, description="Names of relevant tables")
    relevant_columns: dict[str, list[str]] = Field(
        default_factory=dict, description="Mapping of table name to relevant column names"
    )
    relevance_reasons: dict[str, str] = Field(
        default_factory=dict, description="Explanation of why each table was selected"
    )
    domain_guidance: list[str] = Field(
        default_factory=list, description="Crucial domain rules for the matched tables"
    )

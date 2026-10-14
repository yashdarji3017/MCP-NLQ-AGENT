"""Database metadata discovery, reflection, and schema search."""

import re
from dataquery.config import get_settings
from dataquery.database.connection import get_engine, test_db_connection
from dataquery.database.schema_definitions import get_safe_table_dict, get_safe_table_schemas
from dataquery.schemas.database import DatabaseSchema, SchemaSearchResult, TableSchema


class SchemaManager:
    """Manages schema discovery, live reflection, and question-guided schema search."""

    def __init__(self):
        pass

    @property
    def safe_tables(self) -> dict[str, TableSchema]:
        """Dynamic mapping of table_name -> TableSchema."""
        return get_safe_table_dict()

    def refresh(self) -> dict[str, TableSchema]:
        """Force refresh of database schema from live database."""
        from dataquery.database.schema_definitions import refresh_schema_cache
        return refresh_schema_cache()

    def get_all_tables(self) -> list[str]:
        """Return list of allowed table names."""
        return list(self.safe_tables.keys())

    def get_database_schema(self, table_names: list[str] | None = None) -> DatabaseSchema:
        """Return safe schema definitions for requested or all allowed tables."""
        settings = get_settings()
        current_tables = self.safe_tables

        if table_names:
            selected_tables = [
                current_tables[name.lower().strip()]
                for name in table_names
                if name.lower().strip() in current_tables
            ][: settings.MAX_SCHEMA_TABLES]
        else:
            selected_tables = list(current_tables.values())[: settings.MAX_SCHEMA_TABLES]

        return DatabaseSchema(tables=selected_tables)

    def search_schema(self, question: str, top_k: int = 4) -> SchemaSearchResult:
        """Find relevant tables and columns based on a natural-language question.

        Ranks tables by term frequency and semantic concept overlap across table names,
        column names, descriptions, and domain notes.
        """
        question_tokens = set(re.findall(r"\w+", question.lower()))

        concept_aliases: dict[str, list[str]] = {
            "rank": ["ranking", "ranks", "ranking_history", "position", "best", "worst", "top", "improved"],
            "apps": ["app", "application", "applications", "competitor", "sync", "audit"],
            "users": ["user", "signup", "signups", "account", "accounts", "plan", "member", "customer"],
            "activity": ["login", "logout", "session", "active", "online", "logged"],
            "payments": ["payment", "revenue", "money", "transaction", "transactions", "sales", "paid", "dollar", "cycle"],
            "shopify": ["category", "categories", "opportunity", "growth", "reviews", "velocity", "shopify_categories"],
            "audit": ["audit", "reviews", "score", "rating", "stars"],
            "keywords": ["keyword", "keywords", "search", "term", "terms"],
            "invitations": ["invite", "invitation", "invitations", "invited", "team", "collaborator"],
            "slack": ["slack", "channel", "webhook", "notification", "alert"],
        }

        table_scores: list[tuple[str, float, list[str], str]] = []

        current_tables = self.safe_tables
        for name, table in current_tables.items():
            score = 0.0
            matched_columns: list[str] = []
            reasons: list[str] = []

            if name in question_tokens or any(name in t for t in question_tokens):
                score += 15.0
                reasons.append(f"Table name '{name}' mentioned in question.")

            for concept, synonyms in concept_aliases.items():
                if any(syn in question_tokens for syn in synonyms):
                    if concept in name or any(concept in col.name for col in table.columns):
                        score += 8.0
                        reasons.append(f"Related to business concept '{concept}'.")

            for col in table.columns:
                col_name_tokens = set(col.name.split("_"))
                if col.name in question_tokens or (col_name_tokens & question_tokens):
                    score += 5.0
                    matched_columns.append(col.name)
                elif col.description and any(t in col.description.lower() for t in question_tokens):
                    score += 2.0
                    matched_columns.append(col.name)

            desc_tokens = set(re.findall(r"\w+", table.description.lower()))
            common_desc = desc_tokens & question_tokens
            if common_desc:
                score += len(common_desc) * 1.5

            if score > 0:
                table_scores.append((name, score, matched_columns, " ".join(reasons)))

        table_scores.sort(key=lambda x: x[1], reverse=True)

        selected_tables: list[str] = []
        relevant_columns: dict[str, list[str]] = {}
        relevance_reasons: dict[str, str] = {}
        domain_guidance: list[str] = []

        for name, score, cols, reason in table_scores[:top_k]:
            selected_tables.append(name)
            table_obj = current_tables[name]
            if not cols:
                cols = [c.name for c in table_obj.columns[:5]]
            relevant_columns[name] = list(dict.fromkeys(cols))
            relevance_reasons[name] = reason or f"Matches question context for {name}."
            if table_obj.domain_notes:
                domain_guidance.extend(table_obj.domain_notes)

        if not selected_tables:
            selected_tables = [t for t in ["apps", "users", "shopify_categories"] if t in current_tables]
            if not selected_tables and current_tables:
                selected_tables = list(current_tables.keys())[:3]
            for name in selected_tables:
                table_obj = current_tables[name]
                relevant_columns[name] = [c.name for c in table_obj.columns[:4]]
                relevance_reasons[name] = "Default core table for business analytics."

        return SchemaSearchResult(
            tables=selected_tables,
            relevant_columns=relevant_columns,
            relevance_reasons=relevance_reasons,
            domain_guidance=list(dict.fromkeys(domain_guidance)),
        )


_schema_manager: SchemaManager | None = None


def get_schema_manager() -> SchemaManager:
    """Return singleton SchemaManager instance."""
    global _schema_manager
    if _schema_manager is None:
        _schema_manager = SchemaManager()
    return _schema_manager

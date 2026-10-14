"""DataQuery AI — Streamlit Frontend.

Production-grade Natural Language to SQL Assistant UI with rich data visualization,
safety breakdown, schema inspector, query history, and execution trace observability.
Communicates strictly via the FastAPI backend REST endpoints.
"""

import datetime
import os
import sys
import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
src_dir = os.path.join(parent_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from dataquery.schemas.results import NLQResponse

API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


def api_health_check() -> dict:
    """Fetch system health and settings from FastAPI /health endpoint."""
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{API_BASE_URL}/health")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"status": "offline", "database_connected": False, "settings": {}}


def api_fetch_schema() -> list[dict]:
    """Retrieve full database schema from FastAPI /schema endpoint."""
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{API_BASE_URL}/schema")
            if resp.status_code == 200:
                return resp.json().get("tables", [])
    except Exception:
        pass
    return []


def api_execute_query(question: str) -> NLQResponse:
    """Send natural language query to FastAPI /query endpoint."""
    with httpx.Client(timeout=90.0) as client:
        resp = client.post(
            f"{API_BASE_URL}/query",
            json={"question": question},
        )
        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_data = resp.json()
                err_msg = err_data.get("detail", str(err_data))
            except Exception:
                pass
            raise RuntimeError(f"API Error ({resp.status_code}): {err_msg}")
        return NLQResponse.model_validate(resp.json())


st.set_page_config(
    page_title="DataQuery AI — Natural Language to SQL Assistant",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%);
        padding: 2.2rem 2.5rem;
        border-radius: 18px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px -10px rgba(79, 70, 229, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .main-header h1 {
        font-size: 2.3rem;
        font-weight: 700;
        margin-bottom: 0.4rem;
        background: linear-gradient(120deg, #ffffff 0%, #cbd5e1 50%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .main-header p {
        color: #94a3b8;
        font-size: 1.05rem;
        margin: 0;
    }

    .safety-badge {
        display: inline-flex;
        align-items: center;
        background: rgba(16, 185, 129, 0.12);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 0.35rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
    }

    .safety-badge.warning {
        background: rgba(245, 158, 11, 0.12);
        color: #f59e0b;
        border-color: rgba(245, 158, 11, 0.3);
    }

    .metric-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
    }

    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
    }
</style>
""",
    unsafe_allow_html=True,
)

if "query_history" not in st.session_state:
    st.session_state.query_history = [
        "Which apps have the highest average ranking over the last 30 days?",
        "What was payment revenue by plan last month?",
        "Which Shopify categories have the highest opportunity score?",
        "Which users have logged in most frequently?",
    ]

if "current_response" not in st.session_state:
    st.session_state.current_response = None

if "input_question" not in st.session_state:
    st.session_state.input_question = ""


with st.sidebar:
    st.image("https://api.iconify.design/lucide:database-zap.svg?color=%236366f1", width=42)
    st.title("DataQuery Control")
    st.caption("PydanticAI + Gemini + MCP Database Assistant")

    st.divider()

    st.subheader("System Health")
    health = api_health_check()
    api_online = health.get("status") == "healthy"
    db_connected = health.get("database_connected", False)

    if api_online and db_connected:
        st.success("🟢 API & PostgreSQL: Connected")
    elif api_online:
        st.warning("🟡 API: Online | DB: Reconnecting/Offline")
    else:
        st.error(f"🔴 API Offline ({API_BASE_URL})")

    settings_dict = health.get("settings", {})
    gemini_model = settings_dict.get("gemini_model", os.getenv("GEMINI_MODEL", "gemini"))
    max_rows = settings_dict.get("max_query_rows", 500)
    timeout_sec = settings_dict.get("query_timeout_seconds", 10)

    st.caption(f"**API URL:** `{API_BASE_URL}`")
    st.caption(f"**Model:** `{gemini_model}`")
    st.caption(f"**Row Limit:** `{max_rows}` rows")
    st.caption(f"**Timeout:** `{timeout_sec}` seconds")

    st.divider()

    st.subheader("Recent Questions")
    for idx, hist_q in enumerate(st.session_state.query_history[:6]):
        if st.button(f"💬 {hist_q[:38]}...", key=f"hist_{idx}", use_container_width=True):
            st.session_state.input_question = hist_q
            st.rerun()

    st.divider()

    with st.expander("📚 Explore PostgreSQL Schema", expanded=False):
        schema_tables = api_fetch_schema()
        table_names = [t.get("name") for t in schema_tables if "name" in t]

        if table_names:
            selected_tbl = st.selectbox("Select Table", options=table_names)
            if selected_tbl:
                tbl_info = next((t for t in schema_tables if t.get("name") == selected_tbl), None)
                if tbl_info:
                    st.markdown(f"**{tbl_info.get('description', '')}**")
                    cols_df = pd.DataFrame(
                        [
                            {
                                "Column": c.get("name"),
                                "Type": c.get("type"),
                                "Nullable": c.get("nullable", True),
                                "Key": "PK" if c.get("primary_key") else ("FK" if c.get("is_foreign_key") else "-"),
                            }
                            for c in tbl_info.get("columns", [])
                        ]
                    )
                    st.dataframe(cols_df, width="stretch", hide_index=True)
        else:
            st.caption("Schema unavailable. Ensure FastAPI is running on " + API_BASE_URL)


st.markdown(
    """
<div class="main-header">
    <h1>DataQuery AI</h1>
    <p>Enterprise Natural Language to PostgreSQL Assistant • Schema Grounding • SQL Validation • Safe Execution</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div style="margin-bottom: 1.5rem;">
    <span class="safety-badge">🛡️ Read-Only Transaction</span>
    <span class="safety-badge">✓ AST SQL Validated</span>
    <span class="safety-badge">🔒 Sensitive Columns Excluded</span>
    <span class="safety-badge">⏱️ 10s Execution Timeout</span>
    <span class="safety-badge">📊 Capped at 500 Rows</span>
</div>
""",
    unsafe_allow_html=True,
)

st.subheader("Ask a Question")

st.markdown("<small style='color: #94a3b8;'>Example queries to try:</small>", unsafe_allow_html=True)
col_p1, col_p2, col_p3 = st.columns(3)
with col_p1:
    if st.button("📈 Highest average ranking apps", use_container_width=True):
        st.session_state.input_question = "Which apps have the highest average ranking over the last 30 days?"
        st.rerun()
    if st.button("👥 Most active users by logins", use_container_width=True):
        st.session_state.input_question = "Which users have logged in most frequently?"
        st.rerun()

with col_p2:
    if st.button("💳 Payment revenue by plan", use_container_width=True):
        st.session_state.input_question = "What was payment revenue by plan last month?"
        st.rerun()
    if st.button("⭐ Highest app audit scores", use_container_width=True):
        st.session_state.input_question = "Which apps have the highest audit score?"
        st.rerun()

with col_p3:
    if st.button("🚀 Top Shopify opportunity categories", use_container_width=True):
        st.session_state.input_question = "Which Shopify categories have the highest opportunity score?"
        st.rerun()
    if st.button("❓ Test Ambiguity Detection", use_container_width=True):
        st.session_state.input_question = "Show me the best apps."
        st.rerun()

user_query = st.text_area(
    "Enter business question in natural language:",
    value=st.session_state.input_question,
    placeholder="e.g. Which Shopify categories have the highest opportunity score?",
    height=100,
    label_visibility="collapsed",
)

col_run, col_clear = st.columns([1, 6])
with col_run:
    run_clicked = st.button("🚀 Run Query", type="primary", use_container_width=True)

if run_clicked and user_query.strip():
    with st.spinner("Connecting to API Gateway, generating safe SQL, and querying PostgreSQL..."):
        try:
            response: NLQResponse = api_execute_query(user_query.strip())
            st.session_state.current_response = response

            if user_query.strip() not in st.session_state.query_history:
                st.session_state.query_history.insert(0, user_query.strip())
        except Exception as e:
            st.error(f"Error executing NLQ pipeline: {e}")

resp: NLQResponse | None = st.session_state.current_response

if resp:
    st.divider()

    if resp.is_ambiguous:
        st.warning("⚠️ **Ambiguous Question Detected**")
        st.markdown(resp.answer)
        for opt in resp.clarification_options:
            if st.button(f"👉 {opt}", key=f"clarify_{opt}"):
                st.session_state.input_question = opt
                st.rerun()

    elif resp.is_unsupported:
        st.info("ℹ️ **Unsupported Database Request**")
        st.markdown(resp.answer)
        if resp.unsupported_reason:
            st.caption(f"Details: {resp.unsupported_reason}")

    else:
        st.markdown(
            f"""
<div style="background: rgba(99, 102, 241, 0.08); border-left: 4px solid #6366f1; padding: 1.2rem 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
    <h4 style="margin: 0 0 0.5rem 0; color: #818cf8;">💡 AI Business Answer</h4>
    <p style="margin: 0; font-size: 1.05rem; line-height: 1.6;">{resp.answer}</p>
</div>
""",
            unsafe_allow_html=True,
        )

        tab_data, tab_charts, tab_sql, tab_schema, tab_trace = st.tabs(
            ["📊 Query Results", "📈 Visualization", "🔍 Generated SQL", "📚 Schema Grounding", "⏱️ Observability Trace"]
        )

        with tab_data:
            if resp.columns and resp.rows:
                df = pd.DataFrame(resp.rows, columns=resp.columns)
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Rows Returned", f"{resp.row_count:,}")
                col_m2.metric("Truncated Cap", "Yes (Capped)" if resp.truncated else "No (Complete)")
                col_m3.metric("Execution Time", f"{resp.execution_trace.total_duration_ms:.1f} ms")

                st.dataframe(df, width="stretch")

                csv_data = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv_data,
                    file_name=f"dataquery_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )
            else:
                st.info("No records were returned by this query.")

        with tab_charts:
            if resp.columns and resp.rows:
                df = pd.DataFrame(resp.rows, columns=resp.columns)
                numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                text_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

                if len(numeric_cols) > 0 and len(text_cols) > 0:
                    chart_col = text_cols[0]
                    val_col = numeric_cols[0]

                    fig = px.bar(
                        df.head(15),
                        x=chart_col,
                        y=val_col,
                        title=f"{val_col.replace('_', ' ').title()} by {chart_col.replace('_', ' ').title()}",
                        color=val_col,
                        color_continuous_scale="Purples",
                    )
                    fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=50, b=20))
                    st.plotly_chart(fig, width="stretch")
                elif len(numeric_cols) >= 2:
                    fig = px.scatter(
                        df,
                        x=numeric_cols[0],
                        y=numeric_cols[1],
                        title=f"{numeric_cols[1]} vs {numeric_cols[0]}",
                    )
                    fig.update_layout(template="plotly_dark")
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.caption("Data does not contain sufficient numeric/categorical dimensions for auto-charting.")
            else:
                st.caption("No tabular data available for charting.")

        with tab_sql:
            st.markdown("### Validated PostgreSQL Query")
            st.code(resp.sql, language="sql")

            st.markdown("#### Safety Assertions")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown("- **Statement Type:** `SELECT` (Read-only)")
                st.markdown(f"- **Row Limit:** Capped at `{max_rows}`")
            with col_s2:
                st.markdown("- **AST Security Engine:** `sqlglot` + Security Policy")
                st.markdown("- **Sensitive Columns Filtered:** `hashed_password`, `tokens`, `signatures`")

        with tab_schema:
            st.markdown("### Schema Grounding Context")
            col_sc1, col_sc2 = st.columns(2)
            with col_sc1:
                st.markdown("**Referenced Tables:**")
                for tbl in resp.tables_used:
                    st.markdown(f"- `{tbl}`")
            with col_sc2:
                st.markdown("**Referenced Columns:**")
                for col in resp.columns_used:
                    st.markdown(f"- `{col}`")

        with tab_trace:
            st.markdown(f"### Pipeline Execution Trace (Total: {resp.execution_trace.total_duration_ms:.2f} ms)")
            trace_records = [
                {
                    "Step": step.step_name,
                    "Status": step.status,
                    "Duration (ms)": f"{step.duration_ms:.2f}",
                    "Details": str(step.details),
                }
                for step in resp.execution_trace.steps
            ]
            st.dataframe(pd.DataFrame(trace_records), width="stretch", hide_index=True)

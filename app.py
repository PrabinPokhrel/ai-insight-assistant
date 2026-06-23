import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from groq import Groq
import sqlite3
import os
import re
import tempfile

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("No API key found. Please set GROQ_API_KEY in your environment.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

st.set_page_config(
    page_title="AI Business Insight Assistant",
    page_icon="📊",
    layout="wide"
)

# ── Database helpers ──────────────────────────────────────────────────────────

DEFAULT_CSV   = "data/Sample - Superstore.csv"
DEFAULT_DB    = "data/superstore.db"
DEFAULT_TABLE = "superstore"

def csv_to_sqlite(df, table_name, db_path):
    df.columns = [
        c.strip().replace(" ", "_").replace("-", "_")
         .replace("/", "_").replace("(", "").replace(")", "").lower()
        for c in df.columns
    ]
    conn = sqlite3.connect(db_path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    return df.columns.tolist()

def get_schema(db_path):
    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    schema = ""
    for (table,) in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        cols    = cursor.fetchall()
        col_str = ", ".join([f"{c[1]} ({c[2]})" for c in cols])
        schema += f"Table: {table}\nColumns: {col_str}\n\n"
    conn.close()
    return schema

def run_query(sql, db_path):
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df, None
    except Exception as e:
        conn.close()
        return None, str(e)

def extract_sql(text):
    patterns = [
        r"```sql\s*(.*?)\s*```",
        r"```\s*(SELECT.*?)\s*```",
        r"(SELECT\s+.*?;)",
        r"(SELECT\s+.*?)(?:\n\n|$)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    lines = [
        l for l in text.split('\n')
        if any(kw in l.upper() for kw in
               ['SELECT', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'LIMIT'])
    ]
    return ' '.join(lines).strip() if lines else None

def ask_groq(question, schema):
    prompt = f"""You are a SQL expert assistant for a business analytics dashboard.

Database schema:
{schema}

User question: {question}

Instructions:
1. Write a SQL query to answer the question
2. The query must be valid SQLite syntax
3. Always use lowercase column names with underscores as shown in the schema
4. Return ONLY the SQL query inside ```sql ``` code blocks
5. After the SQL write a brief 1-2 sentence explanation
6. Limit results to 20 rows maximum unless asked for all data

SQL Query:"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

def generate_chart(df, question):
    if df is None or df.empty or len(df.columns) < 2:
        return None
    q            = question.lower()
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    text_cols    = df.select_dtypes(include='object').columns.tolist()
    x_col = text_cols[0]    if text_cols    else df.columns[0]
    y_col = numeric_cols[0] if numeric_cols else df.columns[1]
    try:
        if any(w in q for w in ['trend', 'over time', 'monthly', 'yearly', 'daily', 'week']):
            fig = px.line(df, x=x_col, y=y_col, title=question.title(),
                          color_discrete_sequence=['#378ADD'])
        elif any(w in q for w in ['share', 'proportion', 'percent', 'breakdown']):
            fig = px.pie(df, names=x_col, values=y_col, title=question.title())
        elif any(w in q for w in ['compare', 'vs', 'versus', 'difference', 'between']):
            fig = px.bar(df, x=x_col, y=y_col, title=question.title(),
                         color_discrete_sequence=['#1D9E75'])
        elif len(df) <= 20:
            fig = px.bar(df, x=x_col, y=y_col, title=question.title(),
                         color=y_col, color_continuous_scale='Blues')
        else:
            fig = px.line(df, x=x_col, y=y_col, title=question.title(),
                          color_discrete_sequence=['#378ADD'])
        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            font=dict(family='Arial', size=12),
            title_font_size=14, height=400
        )
        return fig
    except Exception:
        return None

# ── Session state ─────────────────────────────────────────────────────────────

if "db_path"    not in st.session_state:
    st.session_state["db_path"]    = DEFAULT_DB
if "table_name" not in st.session_state:
    st.session_state["table_name"] = DEFAULT_TABLE
if "dataset_name" not in st.session_state:
    st.session_state["dataset_name"] = "Superstore Sales (default)"
if "schema"     not in st.session_state:
    if not os.path.exists(DEFAULT_DB):
        if os.path.exists(DEFAULT_CSV):
            df_default = pd.read_csv(DEFAULT_CSV, encoding='latin-1')
            csv_to_sqlite(df_default, DEFAULT_TABLE, DEFAULT_DB)
    st.session_state["schema"] = get_schema(DEFAULT_DB)

# ── UI ────────────────────────────────────────────────────────────────────────

st.title("📊 AI Business Insight Assistant")
st.markdown("Ask any business question in plain English — works with any CSV dataset.")
st.divider()

# Sidebar
with st.sidebar:
    st.header("Dataset")

    st.markdown("**Current dataset:**")
    st.info(st.session_state["dataset_name"])

    st.markdown("**Upload your own CSV:**")
    uploaded_file = st.file_uploader(
        "Drop any CSV file here",
        type=["csv"],
        help="The app will automatically load your data and let you ask questions about it"
    )

    if uploaded_file is not None:
        try:
            df_upload = pd.read_csv(uploaded_file, encoding='latin-1')
            table_name = re.sub(r'[^a-z0-9_]', '_',
                                uploaded_file.name.replace('.csv', '').lower())

            tmp_db = os.path.join(tempfile.gettempdir(), f"{table_name}.db")
            csv_to_sqlite(df_upload, table_name, tmp_db)

            st.session_state["db_path"]      = tmp_db
            st.session_state["table_name"]   = table_name
            st.session_state["dataset_name"] = uploaded_file.name
            st.session_state["schema"]       = get_schema(tmp_db)

            st.success(f"Loaded: {uploaded_file.name}")
            st.markdown(f"**Rows:** {len(df_upload):,}   **Columns:** {len(df_upload.columns)}")

        except Exception as e:
            st.error(f"Error loading file: {e}")

    if st.button("Reset to default Superstore data", use_container_width=True):
        st.session_state["db_path"]      = DEFAULT_DB
        st.session_state["table_name"]   = DEFAULT_TABLE
        st.session_state["dataset_name"] = "Superstore Sales (default)"
        st.session_state["schema"]       = get_schema(DEFAULT_DB)
        st.rerun()

    st.divider()

    st.markdown("**Example questions:**")
    example_questions = [
        "Which region has the highest total sales?",
        "Show me the top 5 products by profit",
        "What is the monthly sales trend?",
        "Which customer segment is most profitable?",
        "Show sales by category and sub-category",
        "Which state has the lowest profit margin?",
        "What are the top 10 customers by revenue?",
        "Compare sales across shipping modes",
    ]
    for q in example_questions:
        if st.button(q, use_container_width=True):
            st.session_state['question'] = q

    st.divider()
    st.caption("Powered by Groq LLaMA 3.3 70B")
    st.caption("Built by Prabin Pokhrel")
    st.caption("github.com/PrabinPokhrel")

# Main area
col1, col2 = st.columns([3, 1])

with col1:
    question = st.text_input(
        "Ask a business question:",
        value=st.session_state.get('question', ''),
        placeholder="e.g. Which region has the highest sales?",
        key="question_input"
    )

with col2:
    st.write("")
    st.write("")
    ask_button = st.button("Get Answer", type="primary", use_container_width=True)

if ask_button and question:
    with st.spinner("Thinking..."):
        groq_response = ask_groq(question, st.session_state["schema"])
        sql           = extract_sql(groq_response)

        if sql:
            df_result, error = run_query(sql, st.session_state["db_path"])

            with st.expander("Generated SQL Query", expanded=False):
                st.code(sql, language='sql')

            if error:
                st.error(f"SQL Error: {error}")
                st.info("Try rephrasing your question.")

            elif df_result is not None and not df_result.empty:
                fig = generate_chart(df_result, question)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

                with st.expander("View Data Table", expanded=True):
                    st.dataframe(df_result, use_container_width=True)

                insight_prompt = f"""
Question: {question}
Query result (first 5 rows): {df_result.head().to_string()}
Total rows returned: {len(df_result)}

Write a 2-3 sentence business insight summary of these results.
Be specific with numbers. Focus on actionable findings.
"""
                insight_response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": insight_prompt}],
                    temperature=0.3
                )
                st.success("💡 Business Insight")
                st.write(insight_response.choices[0].message.content)

            else:
                st.warning("Query returned no results. Try rephrasing.")
        else:
            st.error("Could not extract SQL from response.")
            with st.expander("Raw Groq Response"):
                st.write(groq_response)

elif ask_button and not question:
    st.warning("Please enter a question first.")

with st.expander("Database Schema", expanded=False):
    st.code(st.session_state["schema"])
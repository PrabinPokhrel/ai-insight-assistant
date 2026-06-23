import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from groq import Groq
import os
import re
from dotenv import load_dotenv

# ── Load API key ─────────────────────────────────────────────────────────────
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("No API key found. Please set GROQ_API_KEY in your environment.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Business Insight Assistant",
    page_icon="📊",
    layout="wide"
)

# ── Database setup ────────────────────────────────────────────────────────────
DB_PATH = "data/superstore.db"

CSV_FILES = {
    "Sample - Superstore.csv": "superstore",
    "Sample_-_Superstore.csv": "superstore",
    "superstore.csv":          "superstore",
}

def load_database():
    conn   = sqlite3.connect(DB_PATH)
    loaded = False
    for filename, table_name in CSV_FILES.items():
        filepath = os.path.join("data", filename)
        if os.path.exists(filepath):
            try:
                df = pd.read_csv(filepath, encoding='latin-1')
                df.columns = [
                    c.strip().replace(" ", "_").replace("-", "_")
                     .replace("/", "_").lower()
                    for c in df.columns
                ]
                df.to_sql(table_name, conn, if_exists="replace", index=False)
                loaded = True
                break
            except Exception as e:
                st.error(f"Error loading {filename}: {e}")
    conn.close()
    return loaded

def get_schema():
    conn   = sqlite3.connect(DB_PATH)
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

def run_query(sql):
    conn = sqlite3.connect(DB_PATH)
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
5. After the SQL write a brief 1-2 sentence explanation of what the query does
6. Limit results to 20 rows maximum unless the question asks for all data

SQL Query:"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

def generate_chart(df, question):
    if df is None or df.empty:
        return None
    q            = question.lower()
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    text_cols    = df.select_dtypes(include='object').columns.tolist()

    if len(df.columns) < 2:
        return None

    x_col = text_cols[0]    if text_cols    else df.columns[0]
    y_col = numeric_cols[0] if numeric_cols else df.columns[1]

    try:
        if any(w in q for w in ['trend', 'over time', 'monthly', 'yearly', 'daily']):
            fig = px.line(df, x=x_col, y=y_col,
                          title=question.title(),
                          color_discrete_sequence=['#378ADD'])
        elif any(w in q for w in ['compare', 'vs', 'versus', 'difference']):
            fig = px.bar(df, x=x_col, y=y_col,
                         title=question.title(),
                         color_discrete_sequence=['#1D9E75'])
        elif any(w in q for w in ['share', 'proportion', 'percent', 'distribution']):
            fig = px.pie(df, names=x_col, values=y_col,
                         title=question.title())
        elif len(df) <= 20:
            fig = px.bar(df, x=x_col, y=y_col,
                         title=question.title(),
                         color=y_col,
                         color_continuous_scale='Blues')
        else:
            fig = px.line(df, x=x_col, y=y_col,
                          title=question.title(),
                          color_discrete_sequence=['#378ADD'])

        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family='Arial', size=12),
            title_font_size=14,
            height=400
        )
        return fig
    except Exception:
        return None

# ── Initialize database ───────────────────────────────────────────────────────
if not os.path.exists(DB_PATH):
    load_database()

schema = get_schema()

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("📊 AI Business Insight Assistant")
st.markdown(
    "Ask any business question in plain English and get instant "
    "SQL queries, charts, and answers."
)

st.divider()

# Sidebar
with st.sidebar:
    st.header("About")
    st.markdown("""
**Dataset:** Superstore Sales
**Powered by:** Groq LLaMA 3.3 70B
**Backend:** SQLite + Python

**Example questions:**
""")

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
    ask_button = st.button(
        "Get Answer",
        type="primary",
        use_container_width=True
    )

if ask_button and question:
    with st.spinner("Thinking..."):

        groq_response = ask_groq(question, schema)
        sql           = extract_sql(groq_response)

        if sql:
            df_result, error = run_query(sql)

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

# Database info
with st.expander("Database Schema", expanded=False):
    st.code(schema)
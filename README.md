# AI Business Insight Assistant

An AI-powered business analytics app that lets you ask plain English 
questions about sales data and get instant SQL queries, charts, and 
actionable insights - powered by Groq LLaMA 3.3 70B and Streamlit.

## Live Demo

https://prabin-insight-assistant.streamlit.app

## What it does

Type any business question in plain English. The app:
1. Sends your question to LLaMA 3.3 70B via Groq API
2. The LLM generates a valid SQLite SQL query
3. The query runs against the Superstore sales database
4. Results are visualised as an interactive chart
5. A plain English business insight is generated from the results

## Example questions

- Which region has the highest total sales?
- Show me the top 5 products by profit
- What is the monthly sales trend?
- Which customer segment is most profitable?
- Show sales by category and sub-category
- Which state has the lowest profit margin?
- What are the top 10 customers by revenue?
- Compare sales across shipping modes

## Tech Stack

- Frontend: Streamlit
- LLM: Groq LLaMA 3.3 70B (free tier)
- Database: SQLite (loaded from CSV at runtime)
- Charts: Plotly Express
- Language: Python

## Project Structure
ai-insight-assistant/

├── app.py               # Main Streamlit application

├── data/

│   └── Sample - Superstore.csv   # Sales dataset

├── requirements.txt     # Python dependencies

└── .gitignore

## Dataset

Superstore Sales Dataset - publicly available on Kaggle:
https://www.kaggle.com/datasets/vivek468/superstore-dataset-final

9,994 orders across 4 regions, 3 customer segments, 
17 product sub-categories (2014 - 2017).

## Architecture
User question

↓

Streamlit UI

↓

Groq API (LLaMA 3.3 70B)

↓

SQL query generated

↓

SQLite database query

↓

Plotly chart + data table + business insight

## How to run locally

1. Clone the repo
2. Install dependencies: pip install -r requirements.txt
3. Create a .env file with your Groq API key:
   GROQ_API_KEY=your_key_here
4. Run: streamlit run app.py
5. Get a free Groq API key at: https://console.groq.com

## Built by

Prabin Pokhrel
github.com/PrabinPokhrel
linkedin.com/in/prabin-pokhrel-23bab9279

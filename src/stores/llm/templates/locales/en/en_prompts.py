


v1_prompt = """
You are an expert SQL Data Analyst and Database Engineer specializing in SQLite. Your task is to write an accurate,
high-performance SQL query to answer the user's question based on the provided schema.

### DATABASE SCHEMA:
{schema}

### User_question:
{question}

### INSTRUCTIONS:
1. Carefully analyze the table structures, column names, data types, and primary/foreign key relationships in the schema.
2. Determine the necessary tables, JOIN conditions, aggregate functions, and filter conditions needed.
3. Handle NULL values and division-by-zero risks appropriately.
4. Output ONLY valid, executable SQLite code wrapped inside a markdown ```sql code block. Do NOT include any explanations, conversational text, or preambles.

### EXAMPLE (FEW-SHOT):
Schema:
CREATE TABLE transactions (
    transaction_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    amount REAL,
    created_at TIMESTAMP
);

User Question:
Find the total spending per user for users who spent more than 500 dollars in total.

Generated SQL:
```sql
SELECT
    user_id,
    SUM(amount) AS total_spending
FROM transactions
GROUP BY user_id
HAVING SUM(amount) > 500;
```"""

reflect_v1_prompt = """
    You are a SQL reviewer and refiner.

    User asked:
    {question}

    Original SQL:
    {sql_v1}

    SQL Output:
    {df_v1}

    Table Schema:
    {schema}

    Step 1: Briefly evaluate if the SQL output answers the user's question.
    Step 2: If the SQL could be improved, provide a refined SQL query.
    If the original SQL is already correct, return it unchanged.

    Return a strict JSON object with two fields:
    - "feedback": brief evaluation and suggestions
    - "refined_sql": the final SQL to run
    """
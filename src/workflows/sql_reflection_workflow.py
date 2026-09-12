import sqlite3
import pandas as pd
import re
import json
from typing import TypedDict, Annotated


class SQLReflectionWorkflow:
    """Handles SQL generation, execution, and reflection workflow."""
    
    def __init__(self, client, system_prompt: str):
        """
        Args:
            client: AISuiteProvider instance for LLM calls
            system_prompt: System prompt for SQL generation
        """
        self.client = client
        self.system_prompt = system_prompt

    def _clean_sql(self, query: str) -> str:
        """
        Extract the SQL query from an LLM response.
        Handles:
        - JSON responses with a 'refined_sql' field
        - Markdown ```sql code blocks (possibly wrapped in prose)
        - Generic code fences
        """
        # Try to parse as JSON (or extract JSON from markdown code block)
        try:
            json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", query, re.DOTALL)
            json_str = json_match.group(1) if json_match else query
            data = json.loads(json_str)
            if isinstance(data, dict) and "refined_sql" in data:
                sql = data["refined_sql"]
                inner = re.search(r"```sql\s*(.*?)\s*```", sql, re.DOTALL | re.IGNORECASE)
                return inner.group(1).strip() if inner else sql.strip()
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract SQL from a fenced code block
        match = re.search(r"```sql\s*(.*?)\s*```", query, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
        # Fallback: strip any generic code fences
        match = re.search(r"```\s*(.*?)\s*```", query, re.DOTALL)
        if match:
            return match.group(1).strip()
            
        # No code block found — return stripped text as-is
        return query.strip()

    def execute_sql(self, query: str, db_path: str) -> pd.DataFrame:
        """Execute any SELECT statement over the SQLite database."""
        q = self._clean_sql(query)
        conn = sqlite3.connect(db_path)
        try:
            return pd.read_sql_query(q, conn)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})
        finally:
            conn.close()

    def generate_sql_v1(self, state: dict) -> dict:
        """Generate the initial SQL query based on user question and DB schema."""
        from src.stores.llm.templates.locales.en.en_prompts import v1_prompt
        
        question = state["question"]
        schema = state["schema"]

        prompt = v1_prompt.format(schema=schema, question=question)
        raw_v1 = self.client.generate(prompt=prompt, system_instruction=self.system_prompt).strip()
        sql_v1 = self._clean_sql(raw_v1)
        
        return {"sql_v1": sql_v1}

    def execute_sql_v1(self, state: dict) -> dict:
        """Execute the initial V1 SQL query and serialize DataFrame to records dict."""
        sql_v1 = state["sql_v1"]
        db_path = state.get("db_path", "./db.sqlite")
        df_v1 = self.execute_sql(sql_v1, db_path)
        
        # Convert DataFrame to dictionary records for state compatibility
        df_dict = df_v1.to_dict(orient="records") if isinstance(df_v1, pd.DataFrame) else [{"error": str(df_v1)}]
        
        return {"df_v1": df_dict}

    def reflect_sql_v1(self, state: dict) -> dict:
        """Reflect on the V1 execution results (or errors) and generate a corrected V2 SQL query."""
        from src.stores.llm.templates.locales.en.en_prompts import reflect_v1_prompt
        
        question = state["question"]
        schema = state["schema"]
        sql_v1 = state["sql_v1"]
        df_v1 = state["df_v1"]

        # Convert the dictionary state back or format to string for the LLM to analyze
        result_str = str(df_v1)

        prompt = reflect_v1_prompt.format(question=question, schema=schema, sql_v1=sql_v1, df_v1=result_str)
        raw_v2 = self.client.generate(prompt=prompt, system_instruction=self.system_prompt).strip()
        sql_v2 = self._clean_sql(raw_v2)
        
        return {"sql_v2": sql_v2}

    def execute_sql_v2(self, state: dict) -> dict:
        """Execute the final corrected V2 SQL query and format the final result."""
        sql_v2 = state["sql_v2"]
        db_path = state.get("db_path", "./db.sqlite")
        
        df_v2 = self.execute_sql(sql_v2, db_path)
        
        # Convert DataFrame to dictionary records for state compatibility
        df_dict = df_v2.to_dict(orient="records") if isinstance(df_v2, pd.DataFrame) else [{"error": str(df_v2)}]
        result_str = str(df_dict)
        
        return {"df_v2": df_dict, "result": result_str}
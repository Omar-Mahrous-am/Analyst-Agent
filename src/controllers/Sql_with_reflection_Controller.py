import os
import sqlite3
import pandas as pd
import aisuite as ai
from .BaseController import BaseController
import pandas as pd
from sqlalchemy import create_engine
from src.stores.llm.templates.locales.en import en_prompts



client = ai.Client()


class Sql_with_reflection_Controller(BaseController):

    def __init__(self):
        super().__init__()
        self.db_path = self.get_database_path("products.db")
        self.model = os.getenv("MODEL")

    


    def execute_sql(self, query: str, db_path: str) -> pd.DataFrame:
        """Execute any SELECT over the event-sourced 'transactions' table."""
        q = query.strip().removeprefix("```sql").removesuffix("```").strip()
        conn = sqlite3.connect(db_path)
        try:
            return pd.read_sql_query(q, conn)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})
        finally:
            conn.close() 

    
    def generate_sql(self, question: str, schema: str, model: str) -> str:
        prompt = en_prompts.v1_prompt.format(schema=schema,user_question=question)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content.strip()

    
    def excute_v1(self, user_question: str, sql_v1: str):
        df_sql_V1 = self.execute_sql(sql_v1, db_path=self.db_path)
        return df_sql_V1, sql_v1

   
   
    def reflect_sql_v1(
        self,
        user_question: str,
        sql_v1: str,
        df_sql_V1: pd.DataFrame,
        schema: str,
        model: str,
    ):
        result_str = df_sql_V1.to_string(index=False)

        prompt = en_prompts.reflect_v1_prompt.format(schema=schema, user_question=user_question,
                                                    v1_sql=sql_v1, execution_result=result_str)

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content.strip()

    
    
    def sql_with_reflection(self, user_question: str, schema: str, model: str):
        sql_v1 = self.generate_sql(user_question, schema, model)
        df_sql_V1, _ = self.excute_v1(user_question, sql_v1)
        sql_v2 = self.reflect_sql_v1(
            user_question, sql_v1, df_sql_V1, schema, model
        )
        df_sql_V2, _ = self.excute_v1(user_question, sql_v2)
        return df_sql_V2, sql_v2
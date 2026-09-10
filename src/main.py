from fastapi import FastAPI
from src.routes.Sql_with_reflection import sql_router








app = FastAPI()



@app.get("/")
def welcome():
    return {"Hello": "Welcome to Analyst Agent API"}


app.include_router(sql_router)



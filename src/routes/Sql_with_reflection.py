from fastapi import APIRouter, HTTPException, status, Body, Request
from src.controllers.Sql_with_reflection_Controller import Sql_with_reflection_Controller
from src.helpers.config import get_settings




sql_router=APIRouter(prefix="/sql-with-reflection")

app_settings = get_settings()




@sql_router.post("/sql_gen")
async def sql_with_reflection(request:Request,user_question: str):
    sql_controller=Sql_with_reflection_Controller()


    result=sql_controller.sql_with_reflection(user_question,schema=app_settings.DB_SCHEMA ,model=app_settings.MODEL)


    return result

    




    
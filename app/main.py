import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # 🚀 Importação do CORS
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limiter import limiter

from app.schemas.user_schema import db
import app.schemas.sprint_schema  # noqa: F401 — registers Sprint/PSResponse/PSDeduplication with Base
from app.databases.postgres_database import Base, engine, get_db
from app.routers.user_router import router as user_router
from app.routers.emotion_router import router as emotion_router
from app.routers.emotion_record_router import router as emotion_record_router
from app.routers.team_router import router as team_router
from app.routers.reports_router import router as reports_router
from app.routers.feedback_router import router as feedback_router
from app.routers.auth_router import router as auth_router
from app.routers.trello_router import router as trello_router
from app.routers.jira_router import router as jira_router
from app.routers.teams_router import router as teams_router
from app.routers.planner_router import router as planner_router
from app.routers.questionnaire_router import router as questionnaire_router
from app.services.report_scheduler import create_scheduler
from dotenv import load_dotenv

load_dotenv()  # Carrega as variáveis do arquivo .env

db.Base.metadata.create_all(bind=engine)



@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_vercel_origins = os.getenv("ALLOWED_VERCEL_ORIGIN", "")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Permite acesso do frontend local
    allow_origin_regex=rf"https://{_vercel_origins}\.vercel\.app$" if _vercel_origins else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 🚀 Incluindo as rotas
app.include_router(user_router)
app.include_router(emotion_router)
app.include_router(emotion_record_router)
app.include_router(team_router)
app.include_router(reports_router)
app.include_router(feedback_router)
app.include_router(auth_router)
app.include_router(trello_router)
app.include_router(jira_router)
app.include_router(teams_router)
app.include_router(planner_router)
app.include_router(questionnaire_router)

app.mount("/powerup", StaticFiles(directory="app/static/powerup", html=True), name="powerup")


@app.get("/ping", tags=["admin"])
async def root():
    return {"message": "pong"}

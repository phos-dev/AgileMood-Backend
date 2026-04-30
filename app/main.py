from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # 🚀 Importação do CORS

from app.schemas.user_schema import db
from app.databases.postgres_database import Base, engine, get_db
from app.routers.user_router import router as user_router
from app.routers.emotion_router import router as emotion_router
from app.routers.emotion_record_router import router as emotion_record_router
from app.routers.team_router import router as team_router
from app.routers.reports_router import router as reports_router
from app.routers.feedback_router import router as feedback_router
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Permite acesso do frontend local
    allow_origin_regex="https://.*\\.vercel\\.app$",
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


@app.get("/ping", tags=["admin"])
async def root():
    return {"message": "pong"}

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 - importa modelos para registrar tabelas.
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.demo_data import seed_demo_tutors
from app.routers import tutors


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Atalho do MVP: cria o schema no startup ate introduzirmos migrations.
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_tutors(db)
    yield


app = FastAPI(title="DOT Interview Backend", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tutors.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

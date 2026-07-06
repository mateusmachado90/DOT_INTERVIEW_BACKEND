from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    # Registro de metadata compartilhado por todos os modelos SQLAlchemy.
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    # Dependencia FastAPI: abre uma sessao por request e sempre fecha ao final.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

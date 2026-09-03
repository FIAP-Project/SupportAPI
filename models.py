"""
Modelos SQLAlchemy (tabelas do banco de dados).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class UsuarioDB(Base):
    __tablename__ = "usuarios"

    username: Mapped[str] = mapped_column(String, primary_key=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "USER" ou "ADMIN"


class ChamadoDB(Base):
    __tablename__ = "chamados"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ABERTO")
    usuario: Mapped[str] = mapped_column(String, nullable=False)  # username do dono
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=_agora, onupdate=_agora)

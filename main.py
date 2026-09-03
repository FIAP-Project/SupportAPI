"""
API REST - Gerenciamento de Chamados de Suporte
CP4 - Arquitetura Orientada a Serviço - FIAP

API simples em FastAPI com autenticação via JWT e autorização baseada em
perfil de usuário (USER e ADMIN). Dados persistidos em banco SQLite.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import ChamadoDB, UsuarioDB

# ---------------------------------------------------------------------------
# Configurações gerais
# ---------------------------------------------------------------------------

SECRET_KEY = "cp4-soa-fiap-secret-key"  # apenas para fins acadêmicos
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

security = HTTPBearer(auto_error=False)

app = FastAPI(
    title="API de Chamados de Suporte",
    description="CP4 - Arquitetura Orientada a Serviço",
    version="1.0.0",
)


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# Modelos (enums e schemas Pydantic)
# ---------------------------------------------------------------------------

class Role(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class StatusChamado(str, Enum):
    ABERTO = "ABERTO"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    RESOLVIDO = "RESOLVIDO"
    FECHADO = "FECHADO"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChamadoCreate(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=120)
    descricao: str = Field(..., min_length=3, max_length=2000)


class ChamadoStatusUpdate(BaseModel):
    status: StatusChamado


class ChamadoResponse(BaseModel):
    id: str
    titulo: str
    descricao: str
    status: StatusChamado
    usuario: str
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Inicialização do banco de dados (SQLite)
# ---------------------------------------------------------------------------

@app.on_event("startup")
def iniciar_banco():
    """Cria as tabelas (se não existirem) e popula os usuários de teste."""
    Base.metadata.create_all(bind=engine)

    db = next(get_db())
    try:
        usuarios_padrao = [
            {"username": "user", "password": "user123", "role": Role.USER.value},
            {"username": "admin", "password": "admin123", "role": Role.ADMIN.value},
        ]
        for dados in usuarios_padrao:
            existente = db.get(UsuarioDB, dados["username"])
            if existente is None:
                db.add(
                    UsuarioDB(
                        username=dados["username"],
                        password_hash=hash_senha(dados["password"]),
                        role=dados["role"],
                    )
                )
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Utilitários de autenticação (JWT)
# ---------------------------------------------------------------------------

def criar_access_token(username: str, role: str) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": agora,
        "exp": agora + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


class UsuarioAutenticado(BaseModel):
    username: str
    role: Role


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> UsuarioAutenticado:
    """Valida o JWT enviado no header Authorization e retorna o usuário atual.

    Retorna 401 caso o token não tenha sido enviado, seja inválido ou tenha
    expirado.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado. Informe um token JWT válido no header Authorization.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    role = payload.get("role")
    usuario = db.get(UsuarioDB, username) if username else None
    if usuario is None or role not in (Role.USER.value, Role.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UsuarioAutenticado(username=username, role=Role(role))


def exigir_role(role_exigida: Role):
    """Retorna uma dependência que garante que o usuário autenticado possui
    a role exigida. Caso contrário, retorna 403 (o usuário está autenticado,
    mas não tem permissão para executar a operação).
    """

    def verificador(usuario: UsuarioAutenticado = Depends(get_current_user)) -> UsuarioAutenticado:
        if usuario.role != role_exigida:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Esta operação requer o perfil {role_exigida.value}.",
            )
        return usuario

    return verificador


# ---------------------------------------------------------------------------
# Tratamento de exceções
# ---------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code,
        content={"erro": exc.detail, "status_code": exc.status_code},
        headers=exc.headers,
    )


# ---------------------------------------------------------------------------
# Endpoint de autenticação
# ---------------------------------------------------------------------------

@app.post("/auth/login", response_model=LoginResponse, tags=["Autenticação"])
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    """Autentica um usuário e retorna um token JWT."""
    usuario = db.get(UsuarioDB, dados.username)
    if usuario is None or not verificar_senha(dados.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
        )

    token = criar_access_token(usuario.username, usuario.role)
    return LoginResponse(access_token=token)


# ---------------------------------------------------------------------------
# Endpoints de chamados
# ---------------------------------------------------------------------------

@app.post(
    "/chamados",
    response_model=ChamadoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Chamados"],
)
def criar_chamado(
    dados: ChamadoCreate,
    usuario: UsuarioAutenticado = Depends(exigir_role(Role.USER)),
    db: Session = Depends(get_db),
):
    """Cria um novo chamado. Somente usuários com perfil USER podem criar chamados."""
    chamado = ChamadoDB(
        titulo=dados.titulo,
        descricao=dados.descricao,
        status=StatusChamado.ABERTO.value,
        usuario=usuario.username,
    )
    db.add(chamado)
    db.commit()
    db.refresh(chamado)
    return chamado


@app.get("/chamados", response_model=list[ChamadoResponse], tags=["Chamados"])
def listar_chamados(
    usuario: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista os chamados.

    - USER: visualiza somente os próprios chamados.
    - ADMIN: visualiza todos os chamados.
    """
    query = db.query(ChamadoDB)
    if usuario.role == Role.USER:
        query = query.filter(ChamadoDB.usuario == usuario.username)
    return query.order_by(ChamadoDB.criado_em.desc()).all()


@app.get("/chamados/{chamado_id}", response_model=ChamadoResponse, tags=["Chamados"])
def consultar_chamado(
    chamado_id: str,
    usuario: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consulta um chamado específico.

    - USER: só pode consultar chamados que ele mesmo criou.
    - ADMIN: pode consultar qualquer chamado.
    """
    chamado = db.get(ChamadoDB, chamado_id)
    if chamado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chamado não encontrado.",
        )

    if usuario.role == Role.USER and chamado.usuario != usuario.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para acessar este chamado.",
        )

    return chamado


@app.patch("/chamados/{chamado_id}/status", response_model=ChamadoResponse, tags=["Chamados"])
def alterar_status_chamado(
    chamado_id: str,
    dados: ChamadoStatusUpdate,
    usuario: UsuarioAutenticado = Depends(exigir_role(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Altera o status de um chamado. Somente usuários com perfil ADMIN podem
    executar esta operação."""
    chamado = db.get(ChamadoDB, chamado_id)
    if chamado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chamado não encontrado.",
        )

    chamado.status = dados.status.value
    db.commit()
    db.refresh(chamado)
    return chamado


@app.get("/", tags=["Health"])
def root():
    return {"mensagem": "API de Chamados de Suporte no ar.", "docs": "/docs"}

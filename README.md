# API de Chamados de Suporte

CP4 - Arquitetura Orientada a Serviço - FIAP - 3ESPY - 2º semestre 2026

API REST simples em **FastAPI** para gerenciamento de chamados de suporte, com
autenticação via **JWT** e autorização baseada em perfil de usuário
(`USER` e `ADMIN`).

## Integrantes

- Felipe Cerboncini Cordeiro — RM554909
- Pedro Henrique Martins Alves dos Santos — RM558107
- Milena Codinhoto da Silva - RM554682

## Linguagem e framework

- **Linguagem:** Python 3.10+
- **Framework:** FastAPI
- **Autenticação:** JWT (PyJWT)
- **Banco de dados:** SQLite, acessado via SQLAlchemy (ORM). O arquivo do
  banco (`chamados.db`) é criado automaticamente na primeira execução, na
  raiz do projeto, e os dados persistem entre reinicializações da aplicação.

## Estrutura do projeto

```
chamados-api/
├── main.py             # aplicação FastAPI: rotas, autenticação e autorização
├── database.py         # configuração da conexão SQLite/SQLAlchemy
├── models.py            # tabelas do banco (Usuario e Chamado)
├── pyproject.toml       # dependências (uv)
└── README.md
```

## Instalação e execução

### Opção 1 — usando `uv`

```bash
uv sync
uv run uvicorn main:app --reload
```

A API sobe em `http://127.0.0.1:8000`.

### Documentação interativa

Com o servidor rodando, acesse:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

Para testar as rotas protegidas pelo Swagger:

1. Chame `POST /auth/login` com `username` e `password` e copie o
   `access_token` da resposta.
2. Clique em **Authorize** (cadeado) e cole o token (o Swagger já adiciona o
   prefixo `Bearer` automaticamente).
3. Os endpoints protegidos passam a ser chamados autenticados.

## Usuários/credenciais disponíveis para teste

| Usuário | Senha      | Perfil (role) |
| ------- | ---------- | ------------- |
| `user`  | `user123`  | `USER`        |
| `admin` | `admin123` | `ADMIN`       |

## Endpoints disponíveis

| Método | Rota                       | Acesso                          | Descrição                              |
| ------ | -------------------------- | -------------------------------- | --------------------------------------- |
| POST   | `/auth/login`               | Público                          | Autentica o usuário e retorna o JWT.    |
| POST   | `/chamados`                 | `USER`                           | Cria um novo chamado.                   |
| GET    | `/chamados`                 | `USER` e `ADMIN` (autenticado)   | Lista chamados (USER vê só os seus; ADMIN vê todos). |
| GET    | `/chamados/{id}`            | `USER` (dono) e `ADMIN`          | Consulta um chamado específico.         |
| PATCH  | `/chamados/{id}/status`     | `ADMIN`                          | Altera o status de um chamado.          |

### Status possíveis de um chamado

`ABERTO`, `EM_ANDAMENTO`, `RESOLVIDO`, `FECHADO`

### Exemplos de uso (curl)

```bash
# 1. Login
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "user123"}'

# 2. Criar chamado (USER)
curl -X POST http://127.0.0.1:8000/chamados \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_USER>" \
  -d '{"titulo": "Impressora não funciona", "descricao": "A impressora do 3º andar não liga."}'

# 3. Listar chamados
curl http://127.0.0.1:8000/chamados \
  -H "Authorization: Bearer <TOKEN>"

# 4. Consultar um chamado específico
curl http://127.0.0.1:8000/chamados/<ID_CHAMADO> \
  -H "Authorization: Bearer <TOKEN>"

# 5. Alterar status de um chamado (ADMIN)
curl -X PATCH http://127.0.0.1:8000/chamados/<ID_CHAMADO>/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -d '{"status": "RESOLVIDO"}'
```

### Regras de resposta / tratamento de erros

- Requisição com dados inválidos (ex.: título vazio) → **400/422**.
- Chamado não encontrado → **404 Not Found**.
- Requisição sem token ou com token inválido/expirado → **401 Unauthorized**.
- Usuário autenticado sem permissão para a operação (ex.: `USER` tentando
  alterar status, ou `ADMIN` tentando criar chamado, ou `USER` tentando ver
  chamado de outro usuário) → **403 Forbidden**.

Todas as respostas de erro seguem o formato:

```json
{
  "erro": "mensagem descrevendo o problema",
  "status_code": 401
}
```

## Regras de autorização (USER e ADMIN)

- **USER**
  - Pode criar chamados (`POST /chamados`).
  - Pode consultar apenas os próprios chamados (`GET /chamados`,
    `GET /chamados/{id}`).
  - **Não pode** alterar o status de chamados.
- **ADMIN**
  - Pode consultar todos os chamados de todos os usuários.
  - Pode alterar o status de qualquer chamado (`PATCH /chamados/{id}/status`).
  - **Não pode** criar chamados (essa ação é exclusiva do perfil `USER`,
    conforme o cenário proposto).

A verificação de identidade (quem é o usuário) é feita a partir do JWT
enviado no header `Authorization: Bearer <token>`. A verificação de
permissão (o que o usuário pode fazer) é feita a partir da claim `role`
contida nesse token, comparada com a role exigida por cada endpoint.

---

## Questões discursivas

### Questão 1 — JWT

Possuir um JWT válido comprova apenas que o usuário está **autenticado**, ou
seja, que ele passou pelo processo de login e o servidor consegue confirmar
que o token foi emitido por ele e não foi adulterado (a assinatura é válida)
e ainda não expirou. Isso garante *quem* é o usuário, mas não diz nada sobre
*o que* esse usuário tem permissão para fazer.

Autenticação e autorização são etapas diferentes: um token válido apenas
identifica o usuário (por meio da claim `sub`) e informa seu perfil (claim
`role`), mas cabe à API, em cada endpoint, decidir se aquele perfil tem
autorização para executar a operação solicitada. Por isso, na API implementada,
um usuário `USER` autenticado com um token perfeitamente válido recebe
`403 Forbidden` ao tentar alterar o status de um chamado — o token é válido,
mas a role associada a ele não tem permissão para aquela ação específica.

### Questão 2 — Autenticação e autorização

- **Autenticação** é o processo de verificar **quem** é o usuário — ou seja,
  confirmar sua identidade. Na API, isso acontece no endpoint `POST
  /auth/login`, quando o usuário informa `username` e `password` e o servidor
  confere essas credenciais. Se forem válidas, um token JWT é emitido,
  provando, nas próximas requisições, que aquele usuário já se autenticou.

- **Autorização** é o processo de verificar **o que** o usuário autenticado
  tem permissão para fazer. Na API, isso é feito com base na claim `role`
  contida no token: usuários com perfil `USER` estão autorizados a criar
  chamados e consultar apenas os seus próprios chamados, enquanto usuários
  com perfil `ADMIN` estão autorizados a consultar todos os chamados e
  alterar o status de qualquer um deles.

Ou seja, a autenticação responde "quem está fazendo a requisição?" e a
autorização responde "essa pessoa pode fazer isso?". É perfeitamente possível
estar autenticado (ter um JWT válido) e, ainda assim, não estar autorizado a
executar uma operação específica, como ocorre quando um `USER` tenta alterar
o status de um chamado.

### Questão 3 — Segurança em APIs

- **401 Unauthorized**: indica que a requisição **não foi autenticada** —
  o servidor não sabe (ou não confia em) quem está fazendo a chamada. Isso
  acontece quando o token não foi enviado, é inválido, malformado ou expirou.
  Exemplo na API: chamar `GET /chamados` sem enviar o header `Authorization`,
  ou enviando um token expirado/adulterado — a API retorna `401 Unauthorized`
  antes mesmo de avaliar qualquer regra de permissão.

- **403 Forbidden**: indica que a requisição **foi autenticada com sucesso**
  (o servidor sabe quem é o usuário), mas esse usuário **não tem permissão**
  para executar a operação solicitada. Exemplo na API: um usuário com perfil
  `USER`, autenticado com um token válido, tenta chamar `PATCH
  /chamados/{id}/status` para alterar o status de um chamado — a API
  identifica corretamente o usuário, mas nega a operação com `403 Forbidden`
  porque a role `USER` não tem autorização para essa ação. O mesmo ocorre se
  um `USER` tentar consultar um chamado que pertence a outro usuário.

Em resumo: `401` = "eu não sei quem você é (ou você não provou quem é)";
`403` = "eu sei quem você é, mas você não pode fazer isso".

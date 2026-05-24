# Integração com o Trello — AgileMood

## Visão Geral

O Power-Up AgileMood incorpora funcionalidades de monitoramento de humor diretamente nos boards do Trello. Os membros do time podem registrar sentimentos de forma anônima sem sair do Trello, e o gestor pode visualizar o dashboard do time e configurar lembretes automáticos ao fim de cada sprint.

**Privacidade:** todos os registros enviados pelo Power-Up têm `is_anonymous=True` forçado — o gestor não consegue identificar quem submeteu o quê.

**Funcionalidades disponíveis:**

| Widget | Funcionalidade | Quem usa |
|--------|---------------|----------|
| Registar Sentimento | RF06 — registrar emoção de forma anônima | Membros |
| Mensagens Recebidas | RF07 — visualizar feedbacks recebidos (só leitura) | Membros |
| Dashboard AgileMood | RF03 — gráficos de humor e nível de alerta | Gestor |
| Gatilho de fim de sprint | RF01 — lembretes Slack enviados automaticamente | Automático |

---

## Guia do Gestor

> O Power-Up já foi criado pelo time de desenvolvimento e está disponível para instalação. O gestor não precisa criar nada no Portal de Administração do Trello.

### Pré-requisitos

- Conta AgileMood com perfil de **Gestor**
- Acesso de administrador ao board Trello
- Integração com Slack já configurada na equipa (necessária para os lembretes RF01)

---

### Passo 1 — Instalar o Power-Up no board

1. Abra o board Trello → clique em **Power-Ups** (barra superior)
2. Pesquise "AgileMood" ou use o link direto fornecido pelo time de desenvolvimento
3. Clique em **Adicionar**

---

### Passo 2 — Gerar o seu token pessoal Trello

O token é pessoal e autoriza o AgileMood a agir em seu nome no Trello.

1. Acesse o link de autorização (substitua `SUA_API_KEY` pela chave fornecida pelo dev):
   ```
   https://trello.com/1/authorize?expiration=never&name=AgileMood&scope=read,write&response_type=token&key=SUA_API_KEY
   ```
2. Clique em **Permitir**
3. Copie o token gerado (string longa) — guarde-o com segurança

---

### Passo 3 — Obter o JWT do AgileMood

O JWT é o token de autenticação do AgileMood, válido por 4 horas.

```bash
curl -X POST https://SEU_BACKEND/user/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=SEU_EMAIL&password=SUA_SENHA"
```

Copie o campo `access_token` da resposta.

---

### Passo 4 — Obter o ID da sua equipa

```bash
curl https://SEU_BACKEND/teams/ \
  -H "Authorization: Bearer SEU_JWT"
```

Anote o campo `id` da equipa correspondente.

---

### Passo 5 — Configurar o Power-Up no board

1. No board Trello, clique em **Power-Ups** → selecione AgileMood → clique em **Configurações**
2. Preencha os campos:
   - **URL da API AgileMood:** `https://SEU_BACKEND` (sem barra no final)
   - **Token JWT:** cole o token do Passo 3
   - **ID da Equipa:** cole o ID do Passo 4
3. Clique em **Guardar**

O Power-Up valida o token contra a API antes de salvar. Se aparecer erro, verifique se o JWT não expirou.

---

### Passo 6 — Usar os widgets

**RF06 — Registar Sentimento**
1. Abra qualquer card no board
2. Na barra lateral direita do card → clique em **Registar Sentimento**
3. Selecione a emoção, ajuste a intensidade (1–5) e adicione notas opcionais
4. Clique em **Registar** — enviado de forma 100% anônima

**RF07 — Mensagens Recebidas**
1. Abra qualquer card → clique em **Mensagens Recebidas**
2. Lista somente leitura dos feedbacks recebidos pela equipa

**RF03 — Dashboard de Humor**
1. No cabeçalho do board → clique em **Dashboard AgileMood**
2. Selecione o período e clique em **Carregar**
3. Visualize distribuição de emoções, intensidade média e nível de alerta

> Se os botões não aparecerem nos cards, desative e reative o Power-Up para forçar o recarregamento das funcionalidades.

---

### Passo 7 — Configurar gatilho de fim de sprint (RF01)

Ao mover um card para a coluna final do sprint, o AgileMood envia automaticamente lembretes Slack (RF01) para todos os membros do time.

#### 7.1 Salvar o token Trello no AgileMood

```bash
curl -X POST "https://SEU_BACKEND/integrations/trello/connect?team_id=SEU_TEAM_ID" \
  -H "Authorization: Bearer SEU_JWT" \
  -H "Content-Type: application/json" \
  -d '{"trello_token": "TOKEN_DO_PASSO_2"}'
```

#### 7.2 Obter o ID do board Trello

Acesse `https://trello.com/b/SEU_BOARD_SHORTLINK.json` e copie o campo `id`.

#### 7.3 Registar o webhook no Trello

```bash
curl -X POST "https://api.trello.com/1/webhooks" \
  -d "callbackURL=https://SEU_BACKEND/webhooks/trello/sprint-end?team_id=SEU_TEAM_ID" \
  -d "idModel=ID_DO_BOARD" \
  -d "key=SUA_API_KEY" \
  -d "token=TOKEN_DO_PASSO_2"
```

Após isso, cada vez que um card for movido no board, o Trello notificará o AgileMood e os lembretes RF01 serão disparados via Slack.

---

### Desconectar a integração

```bash
curl -X DELETE "https://SEU_BACKEND/integrations/trello/disconnect?team_id=SEU_TEAM_ID" \
  -H "Authorization: Bearer SEU_JWT"
```

---

### Solução de Problemas

| Problema | Causa | Solução |
|---------|-------|---------|
| "Power-Up não configurado" | Configurações não salvas | Abrir Settings e preencher todos os campos |
| 403 em connect/disconnect | Usuário não é gestor da equipa | Apenas o gestor que criou a equipa pode configurar |
| Webhook retorna 404 | Token Trello não salvo | Executar o Passo 7.1 primeiro |
| Sem lembretes Slack | Equipa sem Slack bot token | Configurar `PUT /teams/{id}/slack-bot-token` |
| JWT expirado | Token válido por 4h | Fazer login novamente e atualizar nas Settings |
| Botões não aparecem nos cards | Power-Up não recarregado | Desativar e reativar o Power-Up no board |

---

---

## Developer Documentation

### What Was Implemented

| File | Change |
|------|--------|
| `migrations/versions/006_add_trello_token_to_team.py` | Alembic migration: `trello_token` column on `team` table |
| `app/schemas/team_schema.py` | Added `trello_token = Column(String, nullable=True)` |
| `app/models/team_model.py` | Added `trello_token: Optional[str]` to `TeamData`; added `TrelloConnectRequest` model |
| `app/crud/team_crud.py` | Added `update_trello_token(db, team_id, token)` |
| `app/routers/trello_router.py` | New router: connect, disconnect, sprint-end webhook, config endpoint |
| `app/services/slack_service.py` | Added `send_sprint_end_reminder(team_id)` |
| `app/main.py` | Registered trello router; mounted `StaticFiles` at `/powerup/` |
| `app/static/powerup/` | Power-Up HTML/JS files (index, settings, rf06, rf03, rf07, powerup.js) |
| `tests/trello_tests.py` | 9 tests covering all endpoints |
| `docs/trello-integration.md` | This document |

---

### Architecture

```
Manager board in Trello
        │
        │  card moved to final column
        ▼
POST /webhooks/trello/sprint-end?team_id=X   (no auth — Trello calls this)
        │
        │  BackgroundTasks.add_task(...)
        ▼
send_sprint_end_reminder(team_id)
        │
        │  for each team member
        ▼
Slack DM via send_dm()  →  RF01 reminder to register mood
```

Power-Up widget flow:
```
Trello board (iframe)
        │  loads
        ▼
/powerup/index.html  →  powerup.js
        │  fetches
        ▼
GET /powerup/trello-config  →  { api_key: "..." }
        │  TrelloPowerUp.initialize(...)
        ▼
Capabilities registered: board-buttons, card-buttons, show-settings
        │
        │  user opens rf06/rf03/rf07 popup
        ▼
t.get('board','private','settings')  →  { apiUrl, token, teamId }
        │
        │  fetch to backend API
        ▼
POST /emotion_record/  |  GET /reports/*  |  GET /feedback/
```

---

### API Endpoints

| Method | Endpoint | Auth | Description |
|--------|---------|------|-------------|
| `GET` | `/powerup-config.js` | None | Serves `powerup.js` with `TRELLO_API_KEY` injected |
| `POST` | `/integrations/trello/connect?team_id=X` | Manager JWT | Save Trello token for team |
| `DELETE` | `/integrations/trello/disconnect?team_id=X` | Manager JWT | Remove Trello token |
| `POST` / `HEAD` | `/webhooks/trello/sprint-end?team_id=X` | None (Trello calls this) | Trigger RF01 Slack reminders |
| `GET` | `/powerup/index.html` | None | Power-Up connector iframe |
| `GET` | `/powerup/settings.html` | None | Settings panel |
| `GET` | `/powerup/rf06-register.html` | None | Register Feeling panel |
| `GET` | `/powerup/rf03-dashboard.html` | None | Dashboard panel |
| `GET` | `/powerup/rf07-messages.html` | None | Received Messages panel |

---

### Environment Variables

| Variable | Required | Description |
|----------|---------|-------------|
| `TRELLO_API_KEY` | Yes | Public API key from the Power-Up Admin Portal. Served to the client via `GET /powerup/trello-config`. |
| `TRELLO_API_SECRET` | Optional | OAuth secret from the Admin Portal. Reserved for future server-side Trello API calls. |

---

### Power-Up Auth Model

- Manager pastes their AgileMood JWT into the Power-Up settings panel once.
- Stored encrypted per-board via `t.set('board', 'private', 'settings', {...})` — never shared across boards or exposed to other members.
- All widget API calls use this token. No per-user auth needed since all emotion records are forced `is_anonymous=True`.

---

### Creating the Power-Up (One-Time Dev Setup)

The Power-Up is created once for the entire AgileMood project. Any company (workspace) can then install it.

1. Go to [Power-Up Admin Portal](https://trello.com/power-ups/admin) → **New App**
2. Fill in:
   - **App name:** AgileMood
   - **Workspace:** your dev workspace (for management only)
   - **Email:** developer contact email
   - **Support contact:** support email or link
   - **Author:** org or personal name
   - **iframe Connector URL:** `https://<backend-domain>/powerup/index.html`
3. After creation, copy the **API Key** → add to `.env` as `TRELLO_API_KEY`
4. Share the Power-Up installation link with companies, or submit to Trello's public directory

Each company installs the same Power-Up and configures their own backend URL in the Settings panel — no new Power-Up needed per company.

---

### Local Testing with ngrok

To test the Trello webhook on localhost:

```bash
# 1. Start the backend
uvicorn app.main:app --reload

# 2. Expose via ngrok
ngrok http 8000

# 3. Update the iframe Connector URL in the Power-Up Admin Portal:
#    https://xxxx.ngrok-free.app/powerup/index.html

# 4. In Trello, disable and re-enable the Power-Up to reload capabilities

# 5. Register the webhook pointing to the ngrok URL:
curl -X POST "https://api.trello.com/1/webhooks" \
  -d "callbackURL=https://xxxx.ngrok-free.app/webhooks/trello/sprint-end?team_id=1" \
  -d "idModel=BOARD_ID" \
  -d "key=TRELLO_API_KEY" \
  -d "token=MANAGER_TRELLO_TOKEN"

# 6. Move a card on the board → check logs for "Reminder queued"
```

> **ngrok free tier note:** if the Power-Up capabilities don't load, add the ngrok URL to the Power-Up's **Allowed Origins** in the Admin Portal, then disable/re-enable the Power-Up on the board.

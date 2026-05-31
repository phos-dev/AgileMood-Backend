# Integração com Microsoft Planner

O AgileMood oferece uma aba interativa no canal do Teams onde o Planner está em uso, permitindo que membros registrem sentimentos anonimamente, gestores visualizem o dashboard de humor do time, e o AgileMood dispare lembretes automáticos (RF01) quando uma tarefa do Planner é concluída.

> **Pré-requisito:** A [integração com Microsoft Teams](./teams-integration.md) deve estar configurada antes de ativar o Planner.

---

## Guia do Gestor

### Como Funciona

- **Aba AgileMood no canal Teams** — qualquer membro do canal pode registrar seu sentimento anonimamente, ver mensagens do gestor e, no caso do gestor, visualizar o dashboard do time
- **RF01 automático** — quando uma tarefa de um plano do Planner é marcada como concluída (100%), o AgileMood envia um lembrete de check-in via DM para todos os membros do time
- **Privacidade garantida** — todos os registros feitos pela aba são forçadamente anônimos; nenhum dado individual é enviado ao backend

### Pré-requisitos

- Papel de **Gestor** no time dentro do AgileMood
- Integração com Microsoft Teams já configurada (tenant ID salvo)
- Acesso de admin para adicionar abas ao canal do Teams onde o Planner está em uso

### Passo 1: Instalar a Aba no Canal

1. No canal do Teams onde o Planner está em uso, clique em **+** na barra de abas
2. Procure por **AgileMood** na lista de aplicativos

   > **Nota:** O aplicativo AgileMood deve estar publicado no catálogo da organização (ver seção Developer Guide).

3. Clique em **Adicionar**
4. Na tela de configuração, insira o **ID do time AgileMood** (número visível na URL do dashboard ou fornecido pelo administrador)
5. Clique em **Salvar**

A aba AgileMood aparecerá no canal com as opções **Registrar**, **Mensagens** e (para gestores) **Dashboard**.

### Passo 2: Ativar Notificações Automáticas do Planner (RF01)

Para que o AgileMood dispare lembretes ao concluir tarefas do Planner, é necessário registrar uma subscrição no Microsoft Graph.

**Obtenha o ID do plano do Planner:**

1. Abra o Planner no Teams
2. Selecione o plano desejado
3. Copie a URL — o ID do plano é o valor após `/plan/` (ex: `aBcDeFgH1234...`)

**Registre a subscrição via API:**

```bash
curl -X POST "https://<seu-backend>/integrations/planner/subscribe?team_id=<id_do_time>" \
  -H "Authorization: Bearer <seu_token>" \
  -H "Content-Type: application/json" \
  -d '{"plan_id": "<id_do_plano>"}'
```

Resposta esperada:
```json
{"subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}
```

A subscrição é renovada automaticamente a cada 48 horas pelo AgileMood. Não é necessário renovar manualmente.

### Passo 3: Usar a Aba AgileMood

#### Para membros do time

1. Clique na aba **AgileMood** no canal
2. Acesse **Registrar** para registrar seu sentimento (sempre anônimo)
3. Acesse **Mensagens** para ver mensagens do gestor (requer login nas Configurações)

#### Para o gestor

1. Acesse **Configurações** e faça login com seu e-mail e senha do AgileMood
2. Após o login, a aba **Dashboard** aparece com os gráficos dos últimos 7 dias
3. As tarefas do Planner concluídas disparam automaticamente lembretes de check-in para todos os membros

### Cancelar Subscrição

Para parar os lembretes automáticos do Planner:

```bash
curl -X DELETE "https://<seu-backend>/integrations/planner/unsubscribe?team_id=<id_do_time>" \
  -H "Authorization: Bearer <seu_token>"
```

### Renovar Manualmente (opcional)

As subscrições do Graph expiram a cada ~3 dias. O AgileMood renova automaticamente a cada 48h. Para forçar uma renovação manual:

```bash
curl -X POST "https://<seu-backend>/integrations/planner/renew?team_id=<id_do_time>" \
  -H "Authorization: Bearer <seu_token>"
```

### Solução de Problemas

| Problema | Causa | Solução |
|----------|-------|---------|
| Aba não aparece no canal | App não publicado no catálogo da organização | Publicar o pacote `.zip` no Teams Admin Center (ver Developer Guide) |
| Erro 400 ao registrar subscrição | Integração com Teams não configurada para o time | Configurar a [integração Teams](./teams-integration.md) antes |
| Lembretes não enviados ao concluir tarefa | Subscrição expirada ou não registrada | Verificar `planner_subscription_id` via API; recriar subscrição |
| Dashboard não carrega | Token JWT expirado na aba | Acessar Configurações e fazer login novamente |
| Erro 403 ao registrar subscrição | Usuário não é gestor do time | Usar conta com papel de gestor |
| Emoções não listadas no formulário | Team ID incorreto configurado na aba | Reconfigurar aba com o ID correto |
| Membros não recebem lembrete | `teams_tenant_id` não configurado para o time | Verificar integração Teams; garantir tenant salvo |
| Erro 502 ao renovar subscrição | Microsoft Graph indisponível temporariamente | Aguardar e tentar novamente; renovação automática tentará a cada 48h |

---

## Developer / Self-Hosting Guide

### What Was Implemented

| File | Status | Purpose |
|------|--------|---------|
| `app/routers/planner_router.py` | New | Webhook handler + subscription management endpoints |
| `app/services/planner_service.py` | New | Graph subscription create/renew/delete via `httpx` |
| `app/services/report_scheduler.py` | Modified | Added `send_sprint_end_reminder_teams()` + `renew_all_planner_subscriptions()` |
| `app/models/team_model.py` | Modified | Added `PlannerSubscribeRequest`, `planner_subscription_id` in `TeamData` |
| `app/schemas/team_schema.py` | Modified | Added `planner_subscription_id = Column(String, nullable=True)` |
| `app/crud/team_crud.py` | Modified | Added `update_planner_subscription_id()`, `get_all_teams()` |
| `app/main.py` | Modified | Registers `planner_router` |
| `migrations/versions/008_add_planner_subscription_id_to_team.py` | New | Adds `planner_subscription_id` column |
| `teams-tab/` | New | React+Vite+TypeScript Teams Channel Tab app |
| `agile-mood.manifest.json` | Modified | Added `configurableTabs` entry, version bumped to 1.1.0 |
| `tests/conftest.py` | New | Real Postgres fixtures for integration tests |
| `tests/planner_tests.py` | New | 17 integration tests (backend) |
| `docs/planner-integration.md` | New | This file |

### Architecture Overview

```
Teams Channel Tab (teams-tab/ React app)
    ├── RF06: POST /emotion_record/public (is_anonymous=True always)
    ├── RF07: GET /feedback/ (requires JWT login)
    └── RF03: GET /reports/emoji-distribution + /reports/average-intensity (manager JWT)

Planner task completed (percentComplete = 100)
    ↓
Microsoft Graph change notification
    ↓
POST /webhooks/planner/plan-completed?team_id={id}
    ↓  (validates clientState == PLANNER_WEBHOOK_SECRET)
    ↓  (validates team exists in DB)
BackgroundTasks → send_sprint_end_reminder_teams(team_id)
    ↓
Teams DM (Adaptive Card) → all team members via Bot Framework
```

**Graph Subscription validation flow (first call):**

```
POST /integrations/planner/subscribe  →  Graph API creates subscription
                                      ↓
Graph sends POST to notificationUrl with ?validationToken=xxx
                                      ↓
Backend returns validationToken as text/plain (200)
                                      ↓
Graph confirms subscription active
```

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/webhooks/planner/plan-completed?team_id={id}` | None (clientState secret) | Receives Graph change notifications; echoes `validationToken` as text/plain for subscription validation |
| `POST` | `/integrations/planner/subscribe?team_id={id}` | Bearer (manager) | Creates Graph subscription for a Planner plan; stores `subscription_id` in DB |
| `POST` | `/integrations/planner/renew?team_id={id}` | Bearer (manager) | Manually renews the Graph subscription |
| `DELETE` | `/integrations/planner/unsubscribe?team_id={id}` | Bearer (manager) | Deletes subscription from Graph and clears DB field |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PLANNER_WEBHOOK_SECRET` | Shared secret sent as `clientState` in Graph subscriptions; validated on every incoming notification | `planner-secret-changeme` |
| `BACKEND_URL` | Public base URL used as the Graph subscription `notificationUrl` | `https://api.agilemood.app` |

Both variables are read in `app/services/planner_service.py`. Change the defaults before deploying to production.

### Teams Tab Structure

```
teams-tab/
├── src/
│   ├── main.tsx              # Teams SDK init + React render
│   ├── App.tsx               # Tab container + nav (Registrar / Mensagens / Dashboard / Configurações)
│   ├── ConfigPage.tsx        # Teams tab configuration page (teamId input)
│   ├── auth.ts               # localStorage JWT persistence helpers
│   ├── api.ts                # Typed fetch wrapper for all backend endpoints
│   ├── types.ts              # AuthState, Emotion, EmojiReport, FeedbackMessage, etc.
│   └── components/
│       ├── Settings.tsx               # Login/logout (email + password → JWT)
│       ├── RF06RegisterFeeling.tsx    # Anonymous mood submission (always public endpoint)
│       ├── RF07Messages.tsx           # Read-only manager messages
│       └── RF03Dashboard.tsx          # Recharts bar charts (emoji freq + avg intensity)
├── vite.config.ts            # port 3001, base: './'
├── .env.example              # VITE_API_URL=https://api.agilemood.app
└── package.json
```

**Building and serving:**

```bash
cd teams-tab
npm install
npm run dev       # dev server at http://localhost:3001
npm run build     # production build → dist/
```

**Serving the built tab from FastAPI (optional):**  
Mount `teams-tab/dist/` as a static directory in `app/main.py` under `/teams-tab` so the tab is served from the same domain as the backend:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/teams-tab", StaticFiles(directory="teams-tab/dist", html=True), name="teams-tab")
```

Update the `configurationUrl` in `agile-mood.manifest.json` to match the production URL before publishing.

### Graph Subscription Lifecycle

- **Create:** `POST https://graph.microsoft.com/v1.0/subscriptions` with `resource=/planner/plans/{planId}/tasks`, `changeType=updated`, `includeResourceData=false`, expiry = now + 4230 minutes (~70h)
- **Renew:** `PATCH .../subscriptions/{id}` updating `expirationDateTime` — done automatically every 48h by `renew_all_planner_subscriptions()`
- **Delete:** `DELETE .../subscriptions/{id}` — called by the unsubscribe endpoint
- **Validation:** Graph sends a POST with `?validationToken=xxx` on subscription creation; backend must echo it as `text/plain` within 10 seconds
- **Auth:** All Graph calls use `get_graph_token(tenant_id)` from `app/services/teams_service.py` (client credentials flow — reuses Teams integration app credentials)

### Scheduler Details

- **Renewal job:** every 48 hours — iterates all teams, renews Graph subscription if `planner_subscription_id` and `teams_tenant_id` are set  
  `IntervalTrigger(hours=48)`  
  **Job ID:** `"renew_planner_subscriptions"`
- **Misfire grace time:** 3600 seconds
- **RF01 trigger:** `send_sprint_end_reminder_teams(team_id)` is called as a `BackgroundTask` when a completed task notification arrives; it is not a scheduled job

### Running the Tests

```bash
# Start the Postgres container
docker compose up -d db

# Get container IP (port is not exposed to host by default)
PGIP=$(docker inspect agilemood-backend-db-1 --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

# Run migrations
DATABASE_URL=postgresql://agilemood:agilemood@${PGIP}:5432/agilemood alembic upgrade head

# Run planner tests (17 integration tests)
DATABASE_URL=postgresql://agilemood:agilemood@${PGIP}:5432/agilemood python -m pytest tests/planner_tests.py -v

# Run full test suite
DATABASE_URL=postgresql://agilemood:agilemood@${PGIP}:5432/agilemood python -m pytest tests/ -v

# Build Teams Tab
cd teams-tab && npm run build
```

> **Note:** The docker-compose `db` service does not expose a host port by default. Either add `ports: ["5433:5432"]` under the `db` service for local development, or connect via the container's internal IP as shown above.

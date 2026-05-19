# Integração com Microsoft Teams

O AgileMood envia relatórios semanais de humor e lembretes via DM no Microsoft Teams usando um bot Azure AD. O bot envia o relatório semanal ao gestor e um lembrete de check-in a cada membro do time.

---

## Guia do Gestor

### Como Funciona

- **Segunda-feira às 09:00 UTC** — o gestor recebe uma DM privada com o relatório semanal de humor do time
- **Sexta-feira às 16:00 UTC** — cada membro do time recebe uma DM de lembrete para registrar seu check-in
- Os relatórios incluem: nível de alerta, distribuição de emoções, intensidade média e resumo anônimo
- Nenhum dado individual é incluído — apenas agregados do time
- A integração é feita por organização: um único consentimento cobre todos os times da mesma instância AgileMood

### Pré-requisitos

- Papel de **Gestor** no time dentro do AgileMood
- Conta Microsoft com acesso ao Azure AD da organização (admin ou permissão para dar consent)

### Passo 1: Dar Consentimento à Aplicação

Acesse o endpoint de conexão como gestor do time:

```
GET /teams/{team_id}/teams-connect
Authorization: Bearer <seu_token>
```

O AgileMood redirecionará para a página de consentimento da Microsoft. O admin da organização precisa aprovar as permissões solicitadas. Isso só precisa ser feito uma vez por organização. Após o consent, o AgileMood salvará o tenant ID e começará a enviar DMs na próxima execução agendada.

### Passo 2: Verificar a Conexão

Após o consent, nenhuma configuração adicional é necessária. O bot identifica os membros pelo e-mail cadastrado no AgileMood e instala o bot automaticamente para cada membro na primeira execução.

### Passo 3: Fallback — ID Manual

Se um membro não for encontrado automaticamente (e-mail diferente no Azure AD, conta de convidado, etc.), o gestor pode definir o AAD Object ID manualmente:

```
PUT /users/{user_id}/teams-user-id
Authorization: Bearer <seu_token>
Content-Type: application/json

{
  "teams_user_id": "<AAD Object ID do membro>"
}
```

Para encontrar o AAD Object ID: Azure Portal → Users → selecione o usuário → campo **Object ID**.

Para remover o ID manual:

```
DELETE /users/{user_id}/teams-user-id
Authorization: Bearer <seu_token>
```

Ao fim de cada execução de lembretes, o gestor recebe uma DM listando os membros que não puderam ser alcançados, para que saiba quem precisa de configuração manual.

### Desconectar

```
DELETE /teams/{team_id}/teams-credentials
Authorization: Bearer <seu_token>
```

Remove o tenant ID salvo. O AgileMood deixará de enviar mensagens para esse time.

### Perguntas Frequentes

**Preciso instalar o bot manualmente para cada membro?**
Não. O AgileMood instala o bot automaticamente para cada membro na primeira execução, desde que o admin consent tenha sido concedido.

**Outros times podem usar organizações Microsoft diferentes?**
Não. A integração é por organização (tenant Azure AD). Todos os times da mesma instância AgileMood compartilham o mesmo Azure AD.

**E se meu time não tiver registros de humor na semana?**
O AgileMood envia uma mensagem de "nenhum registro encontrado" em vez de pular o relatório.

**O que acontece se o consent expirar?**
O token de aplicação é renovado automaticamente via client credentials flow. Não há expiração de consent — a permissão é permanente até ser revogada pelo admin no Azure Portal.

**Posso disparar um relatório manualmente?**
Apenas em ambientes de desenvolvimento. Use `POST /user/test/trigger-teams-reports`.

---

## Developer / Self-Hosting Guide

### Architecture Overview

- Teams integration uses Azure Active Directory OAuth2 (client credentials flow — no user-level tokens stored)
- The app authenticates as itself using `TEAMS_APP_ID` + `TEAMS_APP_SECRET`
- `teams_tenant_id` is stored per team in the DB (set after admin consent via the OAuth callback)
- Bot Framework Connector API sends Adaptive Cards as DMs
- Microsoft Graph API resolves user AAD Object IDs and installs the bot for each user before messaging

### Azure Setup (Required Once)

#### 1 — App Registration

1. Azure Portal → **App Registrations** → **New registration**
2. Name: `AgileMood`, Supported account types: **Single Tenant** (dev) or **Accounts in any organizational directory** (prod multi-tenant)
3. Redirect URI (Web): `https://<your-backend>/auth/teams/callback`
4. **API Permissions** → Add → Microsoft Graph → Application permissions:
   - `User.Read.All`
   - `TeamsAppInstallation.ReadWriteSelfForUser.All`
   - `AppCatalog.Read.All`
   - Click **Grant admin consent for [tenant]** ✅
5. **Certificates & Secrets** → New client secret → copy the **Value** immediately (shown only once)

#### 2 — Azure Bot Resource

1. Azure Portal → Create a resource → **Azure Bot**
2. Microsoft App ID: use the App Registration Client ID from step 1
3. Bot Type: **Single Tenant** (dev) or **Multi Tenant** (prod)
4. Messaging endpoint: `https://<your-backend>/api/messages` (can be a placeholder — only needed if you want to receive messages from users)
5. Channels → enable **Microsoft Teams** channel ✅

#### 3 — Teams App (Org Catalog)

The `teams-app/` directory contains the app manifest and icons. Build the zip once:

```bash
cd teams-app && zip teams-app.zip manifest.json color.png outline.png
```

Then upload to the org catalog:

1. **Teams Admin Center** (`admin.teams.microsoft.com`) → **Teams apps → Manage apps** → **Upload**
2. Select `teams-app.zip`
3. Confirm the app appears in the catalog

This step is required for Graph API proactive messaging (`TeamsAppInstallation.ReadWriteSelfForUser.All` installs from the catalog). Without it, `_get_catalog_app_id()` returns `None` and DMs cannot be sent.

To update the app after manifest changes: **Manage your apps** → AgileMood → three dots → **Update** (do not re-upload as a new app).

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TEAMS_APP_ID` | Azure App Registration Client ID | `21e362ce-...` |
| `TEAMS_APP_SECRET` | Azure App Registration Client Secret | `Iaf8Q~...` |
| `TEAMS_REDIRECT_URI` | OAuth callback URL registered in Azure | `https://yourdomain.com/auth/teams/callback` |
| `TEAMS_BOT_TENANT` | Bot token tenant. Single Tenant: AAD tenant ID. Multi-Tenant (default): `botframework.com` | `88be7986-...` |
| `TEAMS_SERVICE_URL` | Bot Framework regional URL. Default: global. See regions below. | `https://smba.trafficmanager.net/amer` |

**Regional `TEAMS_SERVICE_URL` values:**

| Region | URL |
|--------|-----|
| Default (global, multi-tenant prod) | `https://smba.trafficmanager.net/apis` |
| Americas / Brazil | `https://smba.trafficmanager.net/amer` |
| EMEA | `https://smba.trafficmanager.net/emea` |
| APAC | `https://smba.trafficmanager.net/apac` |

> **Why this matters:** The global URL uses round-robin routing across datacenters. If the bot install and the DM post land on different datacenters, you get `403 Failed to decrypt conversation id`. Use a regional URL to pin all requests to the same DC.

### Relevant Files

| File | Purpose |
|------|---------|
| `app/services/teams_service.py` | Adaptive Card builders, `send_dm()`, Graph API helpers |
| `app/services/report_scheduler.py` | APScheduler job definitions (`send_weekly_teams_reports`, `send_weekly_teams_reminders`) |
| `app/routers/team_router.py` | `GET /teams/{id}/teams-connect`, `DELETE /teams/{id}/teams-credentials` |
| `app/routers/user_router.py` | `PUT`/`DELETE` `/users/{id}/teams-user-id` |
| `app/routers/authentication.py` | `GET /auth/teams/callback` — stores `tenant_id` after consent |
| `app/crud/team_crud.py` | `update_teams_tenant_id()`, `clear_teams_tenant_id()` |
| `app/crud/user_crud.py` | `update_teams_user_id()`, `clear_teams_user_id()` |
| `migrations/versions/` | DB migrations adding `teams_tenant_id` (team) and `teams_user_id` (user) |
| `teams-app/` | Teams app manifest, icons, and zip |

### DM Delivery Flow

1. `get_graph_token(tenant_id)` — obtains Graph API token via client credentials for the team's tenant
2. `_get_catalog_app_id(graph_token)` — resolves the internal Teams catalog ID from the manifest's `externalId` (= Azure App Registration ID)
3. `_ensure_bot_installed(graph_token, teams_user_id)` — checks if bot is installed for user; installs if not; returns `catalog_id`
4. `_get_installation_chat_id(graph_token, teams_user_id, catalog_id)` — two-step: get installation ID, then get personal chat ID (`19:xxx@unq.gbl.spaces`)
5. `POST {TEAMS_SERVICE_URL}/v3/conversations/{chat_id}/activities` — sends Adaptive Card via Bot Framework Connector

> **Why skip `POST /v3/conversations`?** That endpoint requires a Teams pairwise MRI (not a raw AAD Object ID). Using the chat ID from the bot installation sidesteps this entirely.

### Scheduler Details

- **Library:** APScheduler (`AsyncIOScheduler`)
- **Weekly report:** every Monday at 09:00 UTC — DM to manager  
  `CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="UTC")`  
  **Job ID:** `"weekly_teams_report"`
- **Weekly reminder:** every Friday at 16:00 UTC — DM to each team member  
  `CronTrigger(day_of_week="fri", hour=16, minute=0, timezone="UTC")`  
  **Job ID:** `"weekly_teams_reminder"`
- **Misfire grace time:** 3600 seconds
- **Lifecycle:** started and stopped in `app/main.py` via the FastAPI `lifespan` context manager

### Common Errors & Solutions

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` on `POST /v3/conversations` | Single Tenant bot but token obtained from `botframework.com` tenant — JWT `iss` mismatch | Set `TEAMS_BOT_TENANT=<your-aad-tenant-id>` |
| `403 Failed to decrypt conversation id` | Global Bot Framework URL routes request to different datacenter than where conversation was created | Set `TEAMS_SERVICE_URL=https://smba.trafficmanager.net/amer` (or regional equivalent) |
| `403 Failed to decrypt pairwise id` | Attempted to use `29:{AAD_Object_ID}` as a Teams user ID — not a valid pairwise MRI | Don't use `POST /v3/conversations` with AAD IDs; instead get `chat_id` from Graph API installedApps after bot installation |
| `403 Forbidden` on `GET /appCatalogs/teamsApps` | Missing `AppCatalog.Read.All` application permission | Add `AppCatalog.Read.All` in App Registration → API Permissions and grant admin consent |
| `404 Not Found` on `GET /users/{id}/teamwork/installedApps` | Missing `TeamsAppInstallation.ReadWriteSelfForUser.All` OR app not in org catalog | (a) Grant admin consent for `TeamsAppInstallation.ReadWriteSelfForUser.All`; (b) Upload app via Teams Admin Center → Manage apps |
| `400 Bad Request` on `installedApps?$filter=...&$expand=chat` | Graph API does not support combining `$filter` and `$expand=chat` in one call | Two separate calls: `$filter` to get `installation_id`, then `GET installedApps/{installation_id}/chat` |
| `404 POST /api/messages` in logs | Azure Bot sends activity notification to bot's messaging endpoint; no handler registered | Harmless for notification-only bots. Only implement `/api/messages` if you need to receive messages from users. |
| `psycopg2.OperationalError: SSL connection has been closed unexpectedly` | Neon PostgreSQL closes idle connections; SQLAlchemy engine missing `pool_pre_ping` | Add `pool_pre_ping=True` to `create_engine()` in `app/databases/postgres_database.py` |
| App not found in org catalog (`_get_catalog_app_id` returns `None`) | Teams app zip not uploaded to org catalog yet | Upload `teams-app.zip` via Teams Admin Center → Manage apps |

### Running the Tests

```bash
PYTHONPATH=. pytest tests/teams_tests.py -v
```

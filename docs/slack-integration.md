# Integração com Slack

O AgileMood envia relatórios semanais de humor e lembretes via DM no Slack usando um **bot token**. O bot envia o relatório semanal ao gestor e um lembrete de check-in a cada membro do time.

---

## Guia do Gestor

### Como Funciona

- **Segunda-feira às 09:00 UTC** — o gestor recebe uma DM privada com o relatório semanal de humor do time
- **Sexta-feira às 16:00 UTC** — cada membro do time recebe uma DM de lembrete para registrar seu check-in
- Os relatórios incluem: nível de alerta, distribuição de emoções, intensidade média e um resumo anônimo
- Nenhum dado individual é incluído — os relatórios contêm apenas agregados do time
- Cada time tem seu próprio bot token; times diferentes podem usar workspaces do Slack diferentes

### Pré-requisitos

- Você precisa ter o papel de **Gestor** no time dentro do AgileMood
- Um app Slack instalado no seu workspace com os seguintes escopos de bot token:
  - `chat:write` — enviar DMs
  - `users:read.email` — buscar membros por e-mail

### Passo 1: Criar o App no Slack

O caminho mais rápido é usar o manifest:

1. Acesse [https://api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From an app manifest**
2. Cole o conteúdo do arquivo `slack-app-manifest.yml` deste repositório
3. Selecione seu workspace → **Create**
4. No menu lateral, clique em **Install App** → **Install to Workspace** → **Allow**
5. Copie o **Bot User OAuth Token** (começa com `xoxb-`)

Ou crie manualmente:

1. **Create New App** → **From scratch**, dê o nome `AgileMood` e selecione seu workspace
2. Vá em **OAuth & Permissions** → **Scopes** → adicione `chat:write` e `users:read.email`
3. Vá em **Install App** → **Install to Workspace** → **Allow**
4. Copie o **Bot User OAuth Token**

### Passo 2: Registrar o Bot Token no AgileMood

Envie uma requisição `PUT` como gestor do time:

```
PUT /teams/{team_id}/slack-bot-token
Authorization: Bearer <seu_token>
Content-Type: application/json

{
  "slack_bot_token": "xoxb-..."
}
```

O AgileMood começará a enviar DMs na próxima execução agendada.

### Remover o Bot Token

Para parar de receber mensagens, envie uma requisição `DELETE`:

```
DELETE /teams/{team_id}/slack-bot-token
Authorization: Bearer <seu_token>
```

### Fallback: Slack User ID Manual

Se o e-mail de um membro no AgileMood não corresponder ao e-mail no Slack, o bot não conseguirá localizá-lo automaticamente. O gestor pode definir um ID manualmente:

```
PUT /users/{user_id}/slack-user-id
Authorization: Bearer <seu_token>
Content-Type: application/json

{
  "slack_user_id": "U12345678"
}
```

Para encontrar o Slack User ID: abra o perfil do membro no Slack → **Mais** → **Copiar ID do membro**.

Para remover o ID manual:

```
DELETE /users/{user_id}/slack-user-id
Authorization: Bearer <seu_token>
```

Ao fim de cada execução de lembretes, o gestor recebe uma DM listando os membros que não puderam ser alcançados, para que saiba quem precisa de configuração manual.

### Perguntas Frequentes

**Preciso instalar um bot no Slack?**  
Sim. O AgileMood usa um bot token para enviar DMs. Webhooks de entrada não são utilizados.

**Times diferentes podem usar workspaces do Slack diferentes?**  
Sim. Cada time armazena seu próprio bot token. Não há configuração compartilhada de Slack.

**E se meu time não tiver registros de humor na semana?**  
O AgileMood envia uma mensagem de "nenhum registro encontrado" em vez de pular o relatório.

**Posso disparar um relatório manualmente?**  
Não atualmente. Os relatórios são enviados automaticamente conforme a agenda.

**E se o e-mail de um membro não bater com o Slack?**  
O bot usa o `slack_user_id` manual, se configurado. Caso contrário, o gestor recebe uma notificação listando os membros não alcançados.

---

## Developer / Self-Hosting Guide

### Architecture Overview

- Each team has a `slack_bot_token` column in the database (nullable `String`)
- No global Slack configuration; no Slack-related entries in `.env`
- The scheduler runs inside the FastAPI process — no separate worker needed
- Teams without a bot token are silently skipped each scheduled run

### Relevant Files

| File | Purpose |
|------|---------|
| `app/services/slack_service.py` | Block Kit message builders, `send_dm()`, `resolve_slack_user()` |
| `app/services/report_scheduler.py` | APScheduler job definitions (`send_weekly_reports`, `send_weekly_reminders`) |
| `app/routers/team_router.py` | `PUT`/`DELETE` `/teams/{id}/slack-bot-token` endpoints (manager-only) |
| `app/routers/user_router.py` | `PUT`/`DELETE` `/users/{id}/slack-user-id` endpoints (manager-only) |
| `app/crud/team_crud.py` | `update_slack_bot_token()` |
| `app/crud/user_crud.py` | `update_slack_user_id()` |
| `migrations/versions/002_replace_slack_webhook_with_bot_token.py` | DB migration adding `slack_bot_token` |
| `migrations/versions/003_add_slack_user_id_to_users.py` | DB migration adding `slack_user_id` to users |
| `slack-app-manifest.yml` | One-click Slack app setup manifest |

### Scheduler Details

- **Library:** APScheduler (`AsyncIOScheduler`)
- **Weekly report:** every Monday at 09:00 UTC — DM to manager  
  `CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="UTC")`  
  **Job ID:** `"weekly_slack_report"`
- **Weekly reminder:** every Friday at 16:00 UTC — DM to each team member  
  `CronTrigger(day_of_week="fri", hour=16, minute=0, timezone="UTC")`  
  **Job ID:** `"weekly_slack_reminder"`
- **Misfire grace time:** 3600 seconds — fires within 1 hour if the app was down at trigger time
- **Lifecycle:** started and stopped in `app/main.py` via the FastAPI `lifespan` context manager

### Report Flow

1. `send_weekly_reports()` opens a DB session and fetches all teams
2. Teams with no `slack_bot_token` are skipped
3. For each team, resolves the manager's Slack user ID via `users.lookupByEmail`; falls back to `manager.slack_user_id` if set
4. Fetches 7-day reports: emoji distribution, average intensity, anonymous emotion analysis
5. If no data exists, builds a fallback message via `build_no_data_blocks()`
6. Otherwise builds the full report via `build_weekly_report_blocks()`
7. Sends via `send_dm()` using `chat.postMessage`; logs the result; never raises

### Reminder Flow

1. `send_weekly_reminders()` opens a DB session and fetches all teams
2. Teams with no `slack_bot_token` are skipped
3. For each team member, resolves their Slack user ID and sends a reminder DM
4. Members that cannot be resolved are collected; a notification DM is sent to the manager listing unreachable emails

### Error Handling

- A failure for one team is caught and logged — it does not stop processing of other teams
- `send_dm()` returns `True` on success, `False` on any error; never raises
- `resolve_slack_user()` never raises; returns `None` if unresolvable
- If the bot token is missing the `users:read.email` scope, a `critical` log is emitted with remediation instructions

### Running the Tests

```bash
pytest tests/slack_tests.py
```

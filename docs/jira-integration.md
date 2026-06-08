# Integração com o Jira — AgileMood

## Visão Geral

O App AgileMood para Jira incorpora funcionalidades de monitoramento de humor diretamente nos boards e issues do Jira. Os membros da equipe podem registrar sentimentos de forma anônima sem sair do Jira, e o gestor pode visualizar o dashboard e relatórios de segurança psicológica.

**Privacidade:** todos os registros enviados pelo app têm `is_anonymous=True` forçado — o gestor não consegue identificar quem submeteu o quê.

**Funcionalidades disponíveis:**

| Painel | Funcionalidade | Quem usa |
|--------|---------------|----------|
| Registrar Sentimento | RF06 — registrar emoção de forma anônima | Membros |
| Mensagens Recebidas | RF07 — visualizar feedbacks recebidos (só leitura) | Membros |
| Dashboard AgileMood | RF03 — gráficos de humor e nível de alerta | Gestor |
| Segurança Psicológica | RF01 — questionário anônimo de 7 itens (Edmondson), disponível 48h após o sprint; relatório histórico | Membros / Gestor |

---

## Guia do Gestor

> O App AgileMood para Jira já foi criado pelo time de desenvolvimento. O gestor instala o app no site Jira da empresa e configura suas credenciais.

### Pré-requisitos

- Conta AgileMood com perfil de **Gestor**
- Acesso de administrador ao site Jira
- Integração com Slack e/ou Microsoft Teams já configurada na equipe (necessária para os lembretes RF01)

---

### Passo 1 — Instalar o App no Jira

1. Acesse **Configurações do Jira → Apps → Explorar mais apps**
2. Pesquise "AgileMood" ou use o link de instalação fornecido pelo time de desenvolvimento
3. Clique em **Instalar**

---

### Passo 2 — Configurar o App

1. No Jira, acesse o board do seu projeto
2. No cabeçalho → clique em **AgileMood** → aba **Configurações**
3. Introduza o seu **e-mail** e **password** do AgileMood
4. Clique em **Entrar**

O app autentica automaticamente e associa a equipe à sua conta. **O projeto Jira é conectado automaticamente ao board** — não é necessário copiar tokens ou IDs manualmente. Um indicador verde ("Integração Jira ativa") confirma a conexão.

> **Sessão:** O token expira após 4 horas. Se aparecer erro de "Sessão expirada", clique em **Desconectar** e faça login novamente.

---

### Passo 3 — Usar os painéis

**RF06 — Registrar Sentimento**
1. Abra qualquer issue no Jira
2. Na barra lateral direita → clique em **Registrar Sentimento**
3. Selecione a emoção, ajuste a intensidade (1–5) e adicione notas opcionais
4. Clique em **Registrar** — enviado de forma 100% anônima

**RF07 — Mensagens Recebidas**
1. Abra qualquer issue → clique em **Mensagens Recebidas**
2. Lista somente leitura dos feedbacks recebidos pela equipe

**RF03 — Dashboard de Humor**
1. No board do Jira → clique em **Dashboard AgileMood** (botão no cabeçalho do board)
2. Selecione o período e clique em **Carregar**
3. Visualize distribuição de emoções, intensidade média e nível de alerta

**RF01 — Segurança Psicológica**
1. No board do Jira → clique em **Dashboard AgileMood** → aba **Segurança Psicológica**
2. **Gestor:** vê o relatório histórico por sprint (média, desvio padrão, status semáforo). O gestor não responde o questionário.
3. **Membros:** veem o formulário de 7 perguntas com escala Likert 1–5. Disponível por 48h após o encerramento de cada sprint. Respostas são anônimas.

---

### Passo 4 — Fluxo automático de fim de sprint (RF01)

Ao **fechar uma sprint** no Jira (botão "Concluir sprint"), o AgileMood detecta o evento automaticamente e executa o seguinte fluxo:

1. Cria um registro de sprint na base de dados com a data real de início (capturada no momento do "Iniciar sprint")
2. Gera um token de questionário válido por **48 horas**
3. Envia DMs via **Slack** e **Microsoft Teams** a cada membro da equipe com o link para responder
4. O formulário também fica acessível diretamente no painel RF01 do Jira durante as 48h

> **Sem configuração adicional** — basta o gestor ter feito login no Passo 2 para que a conexão automática ao board esteja ativa.

---

### Desconectar a integração

Na aba **Configurações** do painel AgileMood, clique em **Desconectar integração Jira**.

> **Atenção:** após a desconexão, sprints futuros não serão mais detectados automaticamente e o questionário de Segurança Psicológica não será acionado. Os dados históricos já registados são preservados. Para reativar, faça login novamente como gestor na aba Configurações.

---

### Solução de Problemas

| Problema | Causa | Solução |
|---------|-------|---------|
| "AgileMood não configurado" | Configurações não salvas | Abrir Settings e preencher todos os campos |
| "Integração Jira ativa" não aparece | Gestor não fez login ainda | Fazer login na aba Configurações |
| 403 em connect/disconnect | Usuário não é gestor da equipe | Apenas o gestor que criou a equipe pode configurar |
| Sem lembretes Slack | Equipe sem Slack bot token | Configurar `PUT /teams/{id}/slack-bot-token` |
| Sem lembretes Teams | Equipe sem webhook Teams | Configurar integração Teams na plataforma |
| JWT expirado | Token válido por 4h | Fazer login novamente e atualizar nas Settings |
| Painéis não aparecem | App não instalado/recarregado | Desinstalar e reinstalar o app no Jira |
| Questionário não aparece após sprint | Sprint não gerou token | Verificar logs Forge — gestor precisa ter feito login antes do primeiro sprint |

---

---

## Developer Documentation

### What Was Implemented

| File | Change |
|------|--------|
| `migrations/versions/007_add_jira_fields_to_team.py` | Alembic migration: `jira_token` + `jira_cloud_id` columns on `team` table |
| `migrations/versions/009_add_sprint_and_ps_tables.py` | Tables: `sprint`, `ps_response`, `ps_deduplication` |
| `migrations/versions/010_add_sprint_name.py` | `sprint_name TEXT` column on `sprint` |
| `migrations/versions/011_add_questionnaire_expires_at.py` | `questionnaire_expires_at` column; separates questionnaire window from `end_date` |
| `app/schemas/team_schema.py` | Added `jira_token`, `jira_cloud_id` columns |
| `app/schemas/sprint_schema.py` | ORM models: `Sprint`, `PSResponse`, `PSDeduplication` |
| `app/models/team_model.py` | Added fields to `TeamData`; `jira_cloud_id` to `TeamDataSafe`; `JiraConnectRequest` model |
| `app/models/sprint_model.py` | Pydantic: `PSSubmitRequest`, `QuestionnaireState`, `CurrentSprintTokenResponse`, `PSScoreEntry`, `PSReportResponse` |
| `app/crud/team_crud.py` | Added `update_jira_credentials(db, team_id, token, cloud_id)` |
| `app/crud/questionnaire_crud.py` | `create_sprint`, `get_active_sprint`, `has_answered`, `save_ps_response`, `mark_answered`, `get_ps_scores` (Edmondson reverse-scoring) |
| `app/routers/jira_router.py` | Connect, disconnect, sprint-end webhook (POST + HEAD); jira_token check removed — auth via HMAC only |
| `app/routers/questionnaire_router.py` | `GET /questionnaire/{token}`, `POST /questionnaire/submit`, `GET /teams/{id}/current-sprint-token` |
| `app/routers/reports_router.py` | `GET /reports/psychological-safety` |
| `app/routers/authentication.py` | `create_sprint_token()`, `decode_sprint_token()` — 48h JWT |
| `app/main.py` | Registered jira + questionnaire routers |
| `app/services/slack_service.py` | `send_sprint_end_reminder` updated with questionnaire link |
| `app/services/teams_service.py` | `send_sprint_end_reminder` — sends Adaptive Card with questionnaire link |
| `forge-app/manifest.yml` | Two triggers: `avi:jira-software:started:sprint` + `avi:jira-software:closed:sprint` |
| `forge-app/src/triggerStart.js` | Stores actual sprint `start_date` in Forge storage |
| `forge-app/src/trigger.js` | Reads stored `start_date`; calls backend webhook with sprint name + dates |
| `forge-app/src/resolver.js` | `connectProject`, `getProjectStatus`, `getSprintToken`, `submitPsQuestionnaire`, `getPsReport` |
| `forge-app/src/components/RF01PsQuestionnaire.tsx` | Full questionnaire UI (member) + historical report (manager) |
| `tests/jira_tests.py` | 15 tests covering connect/disconnect, signature, deduplication |
| `tests/test_questionnaire.py` | Integration tests: sprint creation, submit, dedup, score calculation |
| `docs/jira-integration.md` | This document |

---

### Architecture

```
Sprint started in Jira board
        │
        │  avi:jira-software:started:sprint
        ▼
Forge trigger: forge-app/src/triggerStart.js
        │
        │  stores { startDate } keyed by sprint.id in Forge storage
        ▼
(waits for sprint close)

Sprint closed in Jira board
        │
        │  avi:jira-software:closed:sprint
        ▼
Forge trigger: forge-app/src/trigger.js
        │
        │  reads agilemood-board-${originBoardId} → teamId
        │  reads agilemood-sprint-${sprintId}-start → startDate
        │  computes HMAC-SHA256(JIRA_WEBHOOK_SECRET, body)
        ▼
POST /webhooks/jira/sprint-end?team_id=X   (X-Jira-Signature header)
        │
        │  verifies signature, deduplicates by sprint.id (60s TTL)
        │  creates sprint row (sprint_number, name, start_date, questionnaire_expires_at = now+48h)
        │  creates sprint_token JWT (exp: 48h)
        │  BackgroundTasks.add_task(...)
        ▼
send_sprint_end_reminder(team_id, questionnaire_url)
        │
        │  for each team member
        ▼
Slack DM + Teams DM  →  link to questionnaire (valid 48h)

Member opens link or Jira RF01 panel:
        │
        │  GET /teams/{id}/current-sprint-token  (Bearer JWT)
        │  GET /questionnaire/{sprint_token}
        ▼
7-item Likert form (Edmondson scale, 1–5)
        │
        │  POST /questionnaire/submit
        ▼
ps_response (answers JSON, no user_id) + ps_deduplication (user_id, sprint_id)

Manager views report:
        │
        │  GET /reports/psychological-safety?team_id=X
        ▼
Per-sprint: response_count, mean_score (reverse-scored items 1,3,5), std_dev
```

Forge App panel flow:
```
Jira board (Forge iframe)
        │  loads
        ▼
RF06 / RF07 / RF03 / RF01 component
        │  reads settings from Forge KVS (jwtToken, teamId, role)
        │
        │  RF06: POST /emotion_record/public?team_id=X  (is_anonymous=True forced)
        │  RF07: GET  /feedback/  (Bearer JWT)
        │  RF03: GET  /reports/emoji-distribution/{teamId}
        │          +  /reports/average-intensity/{teamId}
        │  RF01 (member): GET /teams/{id}/current-sprint-token → GET /questionnaire/{token}
        │                  POST /questionnaire/submit
        │  RF01 (manager): GET /reports/psychological-safety?team_id=X
        ▼
AgileMood Backend API
```

---

### API Endpoints

| Method | Endpoint | Auth | Description |
|--------|---------|------|-------------|
| `POST` | `/integrations/jira/connect?team_id=X` | Manager JWT | Save Jira token + cloud ID for team |
| `DELETE` | `/integrations/jira/disconnect?team_id=X` | Manager JWT | Remove Jira credentials |
| `POST` / `HEAD` | `/webhooks/jira/sprint-end?team_id=X` | HMAC-SHA256 (optional) | Create sprint + token, queue questionnaire reminders |
| `GET` | `/teams/{team_id}/current-sprint-token` | Member/Manager JWT | Returns sprint_token + sprint_name if questionnaire window is open |
| `GET` | `/questionnaire/{sprint_token}` | Member JWT | Returns questionnaire state: pending / answered / expired |
| `POST` | `/questionnaire/submit` | Member JWT | Submit 7-item answers (stored anonymously, dedup by user+sprint) |
| `GET` | `/reports/psychological-safety?team_id=X` | Manager JWT | Per-sprint mean + std_dev (Edmondson reverse-scored) |

---

### Forge Storage Keys

| Key | Set by | Content |
|-----|--------|---------|
| `agilemood-board-${boardId}` | `resolver.js → connectProject` (on manager login) | `{ teamId }` |
| `agilemood-sprint-${sprintId}-start` | `triggerStart.js` (on sprint start) | `{ startDate: ISO string }` |

---

### Environment Variables

| Variable | Required | Description |
|----------|---------|-------------|
| `JIRA_WEBHOOK_SECRET` | Recommended | Shared secret for HMAC-SHA256 webhook signature verification. Set the same value in Forge App settings. Omit for dev/test (verification is skipped). |

---

### Score Calculation (Edmondson Scale)

Items 1, 3, and 5 are reverse-scored: `adjusted = 6 - raw`. All other items use the raw value. The team mean is the average of all adjusted scores across all respondents for a given sprint.

```python
REVERSE_ITEMS = {1, 3, 5}  # 1-indexed question numbers

def _adjusted(answers: dict) -> list[float]:
    return [6 - answers[f"q{i}"] if i in REVERSE_ITEMS else answers[f"q{i}"]
            for i in range(1, 8)]
```

Interpretation thresholds (displayed in the manager Lozenge column):
- **≥ 4.0** → `success` (green) — high psychological safety
- **3.0–3.9** → `moved` (yellow) — moderate
- **< 3.0** → `removed` (red) — alert

---

### Key Differences from Trello Integration

| Aspect | Trello | Jira |
|--------|--------|------|
| Sprint trigger | Sentinel card moved to done-list | Native `avi:jira-software:closed:sprint` event — no card needed |
| Start date capture | N/A | `avi:jira-software:started:sprint` stores real start date before close event fires |
| Webhook signature | HMAC-SHA1 (base64) via `TRELLO_API_SECRET` | HMAC-SHA256 (hex) via `JIRA_WEBHOOK_SECRET` |
| UI delivery | Power-Up HTML served from `app/static/powerup/` | Forge App deployed to Atlassian cloud via CLI |
| Manager setup | Trello token + board/webhook registration | Forge settings panel only — auto-connects on login |
| Deduplication key | Trello action ID | Jira sprint ID |
| Questionnaire | Not implemented | RF01 panel in Forge app + DM link (48h window) |

---

### Creating the Forge App (One-Time Dev Setup)

```bash
cd forge-app
npm install -g @forge/cli
forge login
forge register       # creates app in Atlassian developer console → copy app ID to manifest.yml app.id
forge deploy -e development
forge install --site your-site.atlassian.net -e development
```

Set `JIRA_WEBHOOK_SECRET` in backend `.env` and enter the same value in the Forge App Settings panel.

---

### Local Testing

Backend webhook (simulate sprint-end event):
```bash
SECRET="your-secret"
BODY='{"webhookEvent":"jira:sprint_closed","sprint":{"id":1,"name":"Sprint 1","state":"closed","startDate":"2026-06-01T09:00:00.000-0300"}}'
SIG="sha256=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')"

curl -X POST "http://localhost:8000/webhooks/jira/sprint-end?team_id=1" \
  -H "Content-Type: application/json" \
  -H "X-Jira-Signature: $SIG" \
  -d "$BODY"
```

Forge App:
```bash
cd forge-app
forge tunnel    # requires Atlassian Forge CLI login
```

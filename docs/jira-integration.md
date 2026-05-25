# Integração com o Jira — AgileMood

## Visão Geral

O App AgileMood para Jira incorpora funcionalidades de monitoramento de humor diretamente nos boards e issues do Jira. Os membros da equipe podem registrar sentimentos de forma anônima sem sair do Jira, e o gestor pode visualizar o dashboard e receber lembretes automáticos ao fim de cada sprint.

**Privacidade:** todos os registros enviados pelo app têm `is_anonymous=True` forçado — o gestor não consegue identificar quem submeteu o quê.

**Funcionalidades disponíveis:**

| Painel | Funcionalidade | Quem usa |
|--------|---------------|----------|
| Registrar Sentimento | RF06 — registrar emoção de forma anônima | Membros |
| Mensagens Recebidas | RF07 — visualizar feedbacks recebidos (só leitura) | Membros |
| Dashboard AgileMood | RF03 — gráficos de humor e nível de alerta | Gestor |
| Gatilho de fim de sprint | RF01 — lembretes Slack automáticos ao fechar sprint | Automático |

---

## Guia do Gestor

> O App AgileMood para Jira já foi criado pelo time de desenvolvimento. O gestor instala o app no site Jira da empresa e configura suas credenciais.

### Pré-requisitos

- Conta AgileMood com perfil de **Gestor**
- Acesso de administrador ao site Jira
- Integração com Slack já configurada na equipe (necessária para os lembretes RF01)

---

### Passo 1 — Instalar o App no Jira

1. Acesse **Configurações do Jira → Apps → Explorar mais apps**
2. Pesquise "AgileMood" ou use o link de instalação fornecido pelo time de desenvolvimento
3. Clique em **Instalar**

---

### Passo 2 — Obter o JWT do AgileMood

O JWT é o token de autenticação do AgileMood, válido por 4 horas.

```bash
curl -X POST https://SEU_BACKEND/user/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=SEU_EMAIL&password=SUA_SENHA"
```

Copie o campo `access_token` da resposta.

---

### Passo 3 — Obter o ID da sua equipe

```bash
curl https://SEU_BACKEND/teams/ \
  -H "Authorization: Bearer SEU_JWT"
```

Anote o campo `id` da equipe correspondente.

---

### Passo 4 — Obter o Webhook Secret

Solicite ao time de desenvolvimento o valor de `JIRA_WEBHOOK_SECRET` configurado no servidor. Este segredo é compartilhado entre o backend e o app Jira para verificar autenticidade das requisições.

> Se o campo for deixado em branco nas configurações do app, a verificação de assinatura é desativada (adequado apenas para testes locais).

---

### Passo 5 — Configurar o App

1. No Jira, acesse **Configurações → Apps → AgileMood Settings**
2. Preencha os campos:
   - **URL da API AgileMood:** `https://SEU_BACKEND` (sem barra no final)
   - **Token JWT:** cole o token do Passo 2
   - **ID da Equipe:** cole o ID do Passo 3
   - **Webhook Secret:** cole o segredo do Passo 4
3. Clique em **Salvar**

O app valida o token contra a API antes de salvar. Se aparecer erro, verifique se o JWT não expirou.

---

### Passo 6 — Usar os painéis

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

---

### Passo 7 — Gatilho automático de fim de sprint (RF01)

Ao **fechar uma sprint** no Jira (botão "Concluir sprint"), o AgileMood detecta automaticamente o evento e envia lembretes Slack (RF01) para todos os membros da equipe solicitando o preenchimento do Questionário Anônimo Periódico.

> **Por que automático?** Ao contrário do Trello (que exige um card sentinela), o Jira possui um evento nativo de encerramento de sprint. Nenhuma configuração adicional é necessária — basta ter o Webhook Secret configurado (Passo 4).

---

### Desconectar a integração

```bash
curl -X DELETE "https://SEU_BACKEND/integrations/jira/disconnect?team_id=SEU_TEAM_ID" \
  -H "Authorization: Bearer SEU_JWT"
```

---

### Solução de Problemas

| Problema | Causa | Solução |
|---------|-------|---------|
| "AgileMood não configurado" | Configurações não salvas | Abrir Settings e preencher todos os campos |
| Erro "A URL da API deve usar HTTPS" | URL sem HTTPS | Usar `https://` na URL (localhost é permitido para testes) |
| 403 em connect/disconnect | Usuário não é gestor da equipe | Apenas o gestor que criou a equipe pode configurar |
| Webhook retorna 404 | Equipe sem jira_token salvo | Executar POST /integrations/jira/connect primeiro |
| Sem lembretes Slack | Equipe sem Slack bot token | Configurar `PUT /teams/{id}/slack-bot-token` |
| JWT expirado | Token válido por 4h | Fazer login novamente e atualizar nas Settings |
| Painéis não aparecem | App não instalado/recarregado | Desinstalar e reinstalar o app no Jira |

---

---

## Developer Documentation

### What Was Implemented

| File | Change |
|------|--------|
| `migrations/versions/007_add_jira_fields_to_team.py` | Alembic migration: `jira_token` + `jira_cloud_id` columns on `team` table |
| `app/schemas/team_schema.py` | Added `jira_token`, `jira_cloud_id` columns |
| `app/models/team_model.py` | Added fields to `TeamData`; `jira_cloud_id` to `TeamDataSafe`; `JiraConnectRequest` model |
| `app/crud/team_crud.py` | Added `update_jira_credentials(db, team_id, token, cloud_id)` |
| `app/routers/jira_router.py` | New router: connect, disconnect, sprint-end webhook (POST + HEAD) |
| `app/main.py` | Registered jira router |
| `tests/jira_tests.py` | 15 tests covering all endpoints, signature verification, and deduplication |
| `forge-app/` | Atlassian Forge App (see `forge-app/README.md` for deploy instructions) |
| `docs/jira-integration.md` | This document |

---

### Architecture

```
Sprint closed in Jira board
        │
        │  avi:jira:updated:sprint (state=closed)
        ▼
Forge trigger: forge-app/src/trigger.js
        │
        │  reads settings from Forge storage
        │  computes HMAC-SHA256(JIRA_WEBHOOK_SECRET, body)
        ▼
POST /webhooks/jira/sprint-end?team_id=X   (X-Jira-Signature header)
        │
        │  verifies signature, deduplicates by sprint.id (60s TTL)
        │  BackgroundTasks.add_task(...)
        ▼
send_sprint_end_reminder(team_id)
        │
        │  for each team member
        ▼
Slack DM via send_dm()  →  RF01 reminder to register mood
```

Forge App panel flow:
```
Jira board/issue (Forge iframe)
        │  loads
        ▼
RF06 / RF07 / RF03 component
        │  reads settings from Forge storage (apiUrl, jwtToken, teamId)
        │
        │  RF06: POST /emotion_record/ (is_anonymous=True forced)
        │  RF07: GET  /feedback/?team_id=X
        │  RF03: GET  /reports/mood-summary?team_id=X
        ▼
AgileMood Backend API
```

---

### API Endpoints

| Method | Endpoint | Auth | Description |
|--------|---------|------|-------------|
| `POST` | `/integrations/jira/connect?team_id=X` | Manager JWT | Save Jira token + cloud ID for team |
| `DELETE` | `/integrations/jira/disconnect?team_id=X` | Manager JWT | Remove Jira credentials |
| `POST` / `HEAD` | `/webhooks/jira/sprint-end?team_id=X` | HMAC-SHA256 (optional) | Trigger RF01 Slack reminders on sprint close |

---

### Environment Variables

| Variable | Required | Description |
|----------|---------|-------------|
| `JIRA_WEBHOOK_SECRET` | Recommended | Shared secret for HMAC-SHA256 webhook signature verification. Set the same value in Forge App settings. Omit for dev/test (verification is skipped). |

---

### Key Differences from Trello Integration

| Aspect | Trello | Jira |
|--------|--------|------|
| Sprint trigger | Sentinel card moved to done-list | Native `avi:jira:updated:sprint` event — no card needed |
| Webhook signature | HMAC-SHA1 (base64) via `TRELLO_API_SECRET` | HMAC-SHA256 (hex) via `JIRA_WEBHOOK_SECRET` |
| UI delivery | Power-Up HTML served from `app/static/powerup/` | Forge App deployed to Atlassian cloud via CLI |
| Manager setup | Trello token + board/webhook registration | Forge settings panel only |
| Deduplication key | Trello action ID | Jira sprint ID |

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
BODY='{"webhookEvent":"jira:sprint_closed","sprint":{"id":1,"name":"Sprint 1","state":"closed"}}'
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

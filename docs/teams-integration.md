# Teams Integration

---

## Conectando o AgileMood ao Microsoft Teams

### Pré-requisito

Você precisa ter uma conta Microsoft com permissões de **administrador** da organização para autorizar a conexão.

### Passo a passo

1. Acesse as configurações do seu time no AgileMood
2. Clique em **"Conectar com Teams"**
3. Faça login com sua conta Microsoft de **administrador** da organização
4. Revise as permissões solicitadas e clique em **Aceitar**
5. Você será redirecionado de volta ao AgileMood com a confirmação da conexão
6. (Opcional) Se algum membro não receber mensagens automáticas, configure o ID manual em **Configurações > Membros**

### O que acontece após a conexão

- **Toda segunda-feira às 09h UTC:** relatório semanal de humor enviado ao gestor do time
- **Toda sexta-feira às 16h UTC:** lembrete de check-in enviado a todos os membros do time

### Como desconectar

Acesse **Configurações > Teams** e clique em **"Desconectar Teams"**.

---

## Teams Integration — Developer Reference

### One-time Azure setup

Pedro performs these steps once to register the multi-tenant Azure App. Managers never need to touch Azure.

1. **Azure Portal → App registrations → New registration**
   - Name: `AgileMood`
   - Supported account types: **Accounts in any organizational directory (Multi-tenant)**
   - Leave Redirect URI blank for now

2. **API permissions → Add a permission → Microsoft Graph → Application permissions**
   - Add `User.Read.All`
   - Click **Grant admin consent** for the directory

3. **Certificates & secrets → New client secret**
   - Copy the secret value immediately — it is only shown once

4. **Register an Azure Bot resource**
   - Use the same App ID (client ID) from step 1
   - Enable the **Microsoft Teams** channel on the bot

5. **Set the redirect URI**
   - Back in App registrations → Authentication → Add a platform → Web
   - Redirect URI: value of `TEAMS_REDIRECT_URI` (e.g. `https://your-domain/auth/teams/callback`)

6. **Set server environment variables** (see table below)

### Environment variables

| Variable | Description |
|---|---|
| `TEAMS_APP_ID` | Azure App (client) ID |
| `TEAMS_APP_SECRET` | Azure App client secret |
| `TEAMS_REDIRECT_URI` | e.g. `https://your-domain/auth/teams/callback` |
| `FRONTEND_URL` | Frontend base URL for post-consent redirect |

### API endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/teams/{id}/teams-connect` | Initiates OAuth admin-consent flow |
| GET | `/auth/teams/callback` | OAuth callback — stores `tenant_id` in DB, redirects to frontend |
| DELETE | `/teams/{id}/teams-credentials` | Disconnects Teams (removes stored tenant) |
| PUT | `/users/{id}/teams-user-id` | Sets manual AAD Object ID override for a member |
| DELETE | `/users/{id}/teams-user-id` | Clears the manual AAD Object ID override |
| POST | `/users/test/trigger-teams-reports` | Dev: manually trigger the weekly report job |
| POST | `/users/test/trigger-teams-reminders` | Dev: manually trigger the check-in reminder job |

### Running tests

```bash
PYTHONPATH=. pytest tests/teams_tests.py -v
```

### User ID resolution

When sending a Teams message to a member, the service resolves the recipient as follows:

1. **Graph API email lookup** — queries Microsoft Graph for the user's AAD account by email address.
2. **Manual override fallback** — if the Graph lookup fails (user not in AAD, email mismatch, guest account, etc.), the service falls back to the `teams_user_id` field stored on the user record.

To set a manual override for a member:

```
PUT /users/{id}/teams-user-id
Content-Type: application/json

{ "teams_user_id": "<AAD Object ID>" }
```

To find a user's AAD Object ID: Azure Portal → Users → select the user → copy the **Object ID**.

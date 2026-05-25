# AgileMood — Jira Forge App

Embeds AgileMood mood-tracking panels in Jira boards and issues, with automatic sprint-end Slack reminders.

## Prerequisites

- Node.js 18+
- Forge CLI: `npm install -g @forge/cli`
- Atlassian developer account: https://developer.atlassian.com

## Setup

```bash
cd forge-app
npm install
forge login          # authenticate with Atlassian
forge register       # register app and get app ID → update manifest.yml app.id
```

## Development

```bash
forge tunnel         # local tunnel for live reload
forge deploy         # deploy to development environment
forge install        # install on a Jira site
```

## Configuration

After installing the app on a Jira site:
1. Go to **Jira Settings → Apps → AgileMood Settings**
2. Enter: AgileMood API URL, Manager JWT, Team ID, Webhook Secret
3. The Webhook Secret must match `JIRA_WEBHOOK_SECRET` in the backend `.env`

## Sprint-End Trigger

The trigger fires on `avi:jira:updated:sprint` events. It checks `sprint.state === 'closed'`
and POSTs to `<apiUrl>/webhooks/jira/sprint-end?team_id=<teamId>` with an HMAC-SHA256 signature.

## Panels

| Module | Key | RF |
|--------|-----|----|
| Board Page | `agilemood-dashboard` | RF03 |
| Issue Panel | `agilemood-register-feeling` | RF06 |
| Issue Panel | `agilemood-messages` | RF07 |

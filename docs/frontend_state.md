# Frontend Integration Notes

> See `docs/backend_architecture.md` for full endpoint list.

## Scope

This is a **backend-only** repository. The frontend lives in a separate repo. This document covers the API contract that the frontend consumes.

## Base URL

- Local dev: `http://localhost:8000`
- Production: deployed on Railway (URL set via environment)
- Frontend is deployed on Vercel — CORS is pre-configured to allow `*.vercel.app`

## Authentication

All protected endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

Obtain the token:
```http
POST /user/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=secret
```

Response:
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

Token expires in **240 minutes (4 hours)**. Frontend must re-authenticate after expiry (401 response).

## Key Response Shapes

### Current User
```
GET /user/logged
→ { id, name, email, role, avatar, team_id }
```

### Emotion Record submission
```
POST /emotion_record/
Body: { emotion_id, intensity (1-5), notes?, is_anonymous? }
```

### Team details
```
GET /teams/{team_id}
→ { team_data: { id, name, manager_id, slack_webhook_url }, members: [...], emotions: [...] }
```

### Feedback response field
`manager_knows_identity: bool` — `true` if the employee submitted the record non-anonymously (manager can see who it was). Frontend should use this to display appropriate privacy indicators.

## Error Format

All errors follow FastAPI's default:
```json
{ "detail": "error message here" }
```

Common status codes:
- `400` — bad request (duplicate email, etc.)
- `401` — invalid/expired token
- `403` — role not allowed for this action
- `404` — resource not found or wrong credentials
- `422` — invalid request body

## CORS

Allowed origins (configured in `app/main.py`):
- `http://localhost:3000`
- Any `https://*.vercel.app` domain

Credentials (`Authorization` header) are allowed.

## Interactive API Docs

When running locally, the full API is browsable at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

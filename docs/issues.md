# Issues & Troubleshooting

> Runtime errors show a red error card in the Web UI with the error code, cause, and suggested action.  
> This document covers deployment and configuration issues not shown in the UI.

---

## Q1: 503 — "Too Many Requests"

```
503 Service Unavailable: Notion account rate limited
```

Notion AI enforces rate limits per workspace. Rapid consecutive requests trigger a 429 from Notion, which surfaces as a 503 here.

Solutions:
1. Wait 10–30 seconds and retry — Notion's rate limit recovers quickly
2. Add more accounts to `accounts.json` — the pool automatically switches to a healthy account
3. Reduce request frequency (Lite: 30/min, Standard: 25/min, Heavy: 20/min)

---

## Q2: 401 — Token Expired

```
401 Unauthorized: Notion upstream returned HTTP 401
```

Your `token_v2` has expired or been invalidated (Notion logs out sessions periodically).

Solutions:

Option A — Browser-Assisted (easiest):
```bash
python login.py
```

Option B — Manual F12:
1. Open https://www.notion.so/ai and log in
2. `F12` → **Application** → **Cookies** → find `token_v2` → copy Value
3. Run `scripts/extract_notion_info.js` in Console to get other fields
4. Update `accounts.json`, then restart the service

---

## Q3: 405 — Method Not Allowed

```
405 Method Not Allowed
```

The endpoint does not support the HTTP method used.

Supported endpoints:

| Endpoint | Method |
|---|---|
| `/v1/chat/completions` | POST |
| `/v1/models` | GET |
| `/v1/conversations/{id}` | DELETE |
| `/health` | GET |

Common cause: using `/chat/completions` without the `/v1` prefix, or using GET on the chat endpoint.

Note: **Claude Code is not supported** — it uses Anthropic's native API format, which is incompatible with this service.

---

## Q4: Notion AI Suspended

Notion may suspend AI access on workspaces with unusual request patterns (many thread creations from a server IP, high frequency, etc.). Business Trial workspaces are especially prone to this.

Mitigation:
- Add multiple accounts to distribute load
- Avoid extremely high request frequency
- If suspended, switch to a different workspace account

---

## Q5: Thinking Panel Not Showing

Use `APP_MODE=standard` or `heavy`. Lite mode does not support the Thinking or Search panels.

---

## Q6: Docker — Service Won't Start

```bash
# Check container status
docker-compose ps

# View logs for errors
docker-compose logs --tail=50

# Verify accounts loaded correctly
docker-compose logs | grep "startup"
# Should show: "accounts": N  (N = number of accounts)
```

Common causes: malformed `accounts.json`, missing required env vars in `.env`, port already in use.

---

*Last updated: 2026-06*

# Notion2API — Project Progress

> This document records the complete status, architecture details, development history, and current progress of the project.  
> Goal: after reading this document, you should have a comprehensive understanding of the latest state of the project.  
> Last updated: 2026-08-13 (model names normalized, added Kimi K3 / K2.6 / Gemini 3.6 Flash, retired 4 old models, total 21)

---

## 1. Project Overview

### 1.1 Project Purpose

Notion2API is an open-source project that reverse-engineers **Notion AI** and wraps it as an **OpenAI-compatible API**. By reverse-engineering Notion's Web API (`/api/v3/runInferenceTranscript`), it exposes Notion AI's capabilities through the standard `/v1/chat/completions` interface, allowing third-party clients such as Cherry Studio and Zotero to call it directly.

### 1.2 Core Features

- **OpenAI-Compatible API**: Standard `/v1/chat/completions` endpoint, supports streaming (SSE) and non-streaming responses
- **Three Operation Modes**: Lite / Standard / Heavy to fit different use cases
- **21 AI Models**: Claude (incl. Opus 5), GPT-5.x, Gemini, Kimi (incl. K3), Grok, DeepSeek, GLM
- **Three-Layer Memory System** (Heavy mode): sliding window + compressed summaries + full archive
- **Multi-Account Load Balancing**: Round-Robin polling + cooldown mechanism
- **Built-in Web UI**: Claude-style interface, supports Thinking panel, Search panel, conversation management
- **Docker One-Command Deployment**: docker-compose ready out of the box

### 1.3 Repository Information

- **Repository**: `git@github.com:maverickxone/notion2api.git`
- **Main branch**: `main`
- **License**: MIT
- **Current version**: v2.1.1

---

## 2. Tech Stack

### 2.1 Backend

| Technology | Purpose |
|------------|---------|
| Python 3.11 | Runtime |
| FastAPI | Web framework |
| cloudscraper | Bypass Cloudflare anti-scraping (Notion API requests) |
| requests | HTTP client |
| httpx | Async HTTP client (SiliconFlow summary service) |
| SQLite | Data persistence (Heavy mode) |
| Pydantic | Data model validation |
| slowapi | Rate limiting |
| python-dotenv | Environment variable management |
| uvicorn | ASGI server |

### 2.2 Frontend

| Technology | Purpose |
|------------|---------|
| Vanilla HTML/CSS/JS | No framework, modular organization |
| marked.js (CDN) | Markdown rendering |
| DOMPurify (CDN) | XSS protection |
| highlight.js (CDN) | Code highlighting |

### 2.3 Deployment

| Technology | Purpose |
|------------|---------|
| Docker + docker-compose | Containerized deployment |
| Python 3.11-slim image | Base image |
| Non-root user | Security hardening |

---

## 3. Project Architecture

### 3.1 Directory Structure

```
notion2api/
├── app/                          # Backend core code
│   ├── server.py                 # FastAPI entry, middleware, route mounting
│   ├── api/
│   │   ├── chat.py               # Core: /v1/chat/completions endpoint + structured error system (1700+ lines)
│   │   └── models.py             # /v1/models endpoint
│   ├── conversation.py           # Three-layer memory system (1789 lines, largest file)
│   ├── notion_client.py          # Notion API reverse-engineering client (370+ lines)
│   ├── stream_parser.py          # NDJSON stream parser + segment registry (849 lines)
│   ├── account_pool.py           # Multi-account load balancing + cooldown wait (110+ lines)
│   ├── model_registry.py         # Model name mapping (108 lines)
│   ├── summarizer.py             # SiliconFlow LLM summary service (72 lines)
│   ├── schemas.py                # Pydantic data models (64 lines)
│   ├── config.py                 # Environment variable loading (55 lines)
│   ├── limiter.py                # Rate limiter (22 lines)
│   └── logger.py                 # JSON structured logging (38 lines)
├── frontend/                     # Built-in Web UI
│   ├── index.html                # Main page (1705 lines)
│   ├── css/
│   │   ├── main.css              # Main styles (700 lines)
│   │   ├── components.css        # Component styles (351 lines)
│   │   ├── markdown.css          # Markdown render styles (150 lines)
│   │   └── animations.css        # Animation effects (72 lines)
│   └── js/
│       ├── core/
│       │   ├── app.js            # App entry + event binding (412 lines)
│       │   ├── constants.js      # Constant definitions (131 lines)
│       │   └── state.js          # Global state management (69 lines)
│       ├── api/
│       │   ├── client.js         # API communication client (86 lines)
│       │   ├── models.js         # Model management (63 lines)
│       │   └── settings.js       # Settings panel (27 lines)
│       ├── chat/
│       │   ├── manager.js        # Conversation management (207 lines)
│       │   ├── renderer.js       # Message DOM rendering (276 lines)
│       │   ├── streaming.js      # SSE stream processing (235 lines)
│       │   └── storage.js        # LocalStorage persistence (91 lines)
│       ├── ui/
│       │   ├── input.js          # Input box control (43 lines)
│       │   ├── modal.js          # Modal component (33 lines)
│       │   ├── sidebar.js        # Sidebar (24 lines)
│       │   └── theme.js          # Theme switching (36 lines)
│       └── utils/
│           ├── dom.js            # DOM utility functions (54 lines)
│           ├── markdown.js       # Markdown safe rendering (29 lines)
│           └── validation.js     # Data validation (88 lines)
├── scripts/                      # Deployment and management scripts
│   ├── deploy.sh                 # Linux deployment script
│   ├── deploy.bat                # Windows deployment script
│   ├── manage.sh                 # Service management script (start/stop/backup etc.)
│   └── extract_notion_info.js    # Browser console script: extract Notion credentials (multi-workspace support)
├── docs/                         # Documentation
│   ├── issues.md                 # Troubleshooting guide
│   └── PROJECT_PROGRESS.md       # This document (architecture + progress + AI context, replaces ARCHITECTURE.md)
├── data/                         # SQLite database directory
│   └── conversations.db          # Conversation database (Heavy mode)
├── response/                     # Debug: raw response samples per model
├── main.py                       # Terminal interaction entry (debug)
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker build file
├── docker-compose.yml            # Docker Compose configuration
├── .env.example                  # Environment variable template
├── .gitignore                    # Git ignore rules
├── .dockerignore                 # Docker build ignore rules
├── login.py                      # Browser-assisted login script (CDP, auto-extracts Notion credentials)
├── README.md                     # Project documentation (English)
└── README_EG.md                  # Project documentation (English)
```

### 3.2 Codebase Size

| Part | Files | Total Lines |
|------|-------|-------------|
| Backend Python | 12 | ~4,992 |
| Frontend JS | 13 | ~1,645 |
| Frontend CSS | 4 | ~1,273 |
| Frontend HTML | 1 | ~1,504 |
| **Total** | **30** | **~9,414** |


---

## 4. Core Module Details

### 4.1 Three Operation Modes

#### Lite Mode
- **Characteristics**: Single-turn Q&A, no memory, no database
- **Rate limit**: 30/min
- **Flow**: Extract last user message → build transcript → call Notion API → return result
- **Use case**: Simple Q&A, translation, and other context-free tasks
- **Entry function**: `_handle_lite_request()` in `api/chat.py`

#### Standard Mode (Recommended)
- **Characteristics**: Client manages full context, supports Thinking and Search panels, no database
- **Rate limit**: 25/min
- **Flow**: Receive complete messages history from client → build transcript → call Notion API → return result (incl. thinking/search events)
- **Use case**: Short to medium conversations, third-party client use
- **Entry function**: `_handle_standard_request()` in `api/chat.py`

#### Heavy Mode
- **Characteristics**: Server-managed sessions, SQLite persistence, three-layer memory system
- **Rate limit**: 20/min
- **Flow**:
  1. Get or create conversation_id
  2. Fetch the last 8 rounds from the sliding window
  3. Inject compressed summary (if any)
  4. Build transcript and send to Notion
  5. Persist this round to sliding window + archive
  6. Asynchronously trigger compression (for rounds outside the window)
- **Use case**: Long-term conversations, scenarios requiring server-side memory
- **Entry function**: `create_chat_completion()` main function in `api/chat.py`

### 4.2 Three-Layer Memory System (Heavy Mode)

```
┌─────────────────────────────────────────────────┐
│                  Notion API                      │
│  (receives transcript: config + context + history)│
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│  get_transcript_payload()                        │
│  Assembles transcript:                           │
│  1. config block (model configuration)           │
│  2. context block (user/space info)              │
│  3. compressed summary (if any, injected as system message) │
│  4. last 8 rounds from sliding window            │
│  5. new user prompt                              │
└─────────────────────┬───────────────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    ▼                 ▼                 ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐
│ sliding   │  │ compressed   │  │ full_archive │
│ _window   │  │ _summaries   │  │              │
│ (8 rounds)│  │ (mid summaries)│ │ (permanent) │
│ Core layer│  │ Compress layer│ │ Archive layer│
│ UPSERT   │  │ SiliconFlow  │  │ INSERT OR    │
│ write     │  │ LLM compress │  │ IGNORE       │
└──────────┘  └──────────────┘  └──────────────┘
```

**SQLite Table Structure**:
- `conversations`: conversation metadata (id, title, thread_id, next_round_index)
- `messages`: compatibility message table (role, content, thinking)
- `sliding_window`: sliding window table (round_number, user_content, assistant_content, assistant_thinking, compress_status)
- `compressed_summaries`: compressed summaries table (round_index, user_content, assistant_content, summary, compress_status)
- `full_archive`: full archive table (round_index, role, content)

**Critical behavioral constraints** (must not be modified):
1. **Thread ID persistence**: the entire conversation reuses the same thread_id
2. **is_partial_transcript=True**: must be set when reusing a thread, otherwise the AI loses memory
3. **Do not delete Thread**: Notion's home page will accumulate conversations (acceptable side effect)
4. **Forced sliding window**: `get_transcript_payload()` does not fall back to the messages table

### 4.3 Notion API Reverse-Engineering Client

**Core endpoint**: `https://www.notion.so/api/v3/runInferenceTranscript`

**Request flow**:
1. Build transcript (config + context + conversation history)
2. Map external model name to Notion internal codename (e.g. `claude-sonnet-4-6` → `almond-croissant-low`)
3. Determine thread type per model (`workflow` or `markdown-chat`)
4. Use cloudscraper to bypass Cloudflare and send request
5. Parse NDJSON streaming response

**Thread types**:
- `workflow`: used by most models, supports thinking/search
- `markdown-chat`: used only by Gemini 2.5 Flash

**Anti-scraping measures**:
- Use cloudscraper to simulate a browser (one instance reused per account, retaining Cloudflare challenge cookie)
- Automatically rebuild scraper on 403 to refresh Cloudflare challenge
- Cookies passed as a header string (bypasses non-ASCII encoding issues in the cookie jar)
- Carry full headers (User-Agent, notion-client-version, etc.)
- `notion-client-version` can be overridden via the `NOTION_CLIENT_VERSION` environment variable

### 4.4 NDJSON Stream Parser (stream_parser.py)

**Core mechanism — Segment Registry**:

Notion's streaming response is NDJSON format, one JSON object per line. The parser classifies content via a "segment registry" mechanism:

1. Patches with `o:"a"` + `path="/s/-"` create a new segment; at this point `v.type` marks the type
2. Classify by type: `agent-inference` → thinking, `agent-tool-result` → tool, `text` → content
3. Subsequent `o:"x"` patches append text to existing segments; a table lookup identifies the category

**Three output event types**:
- `{"type": "content", "text": "..."}` — main content
- `{"type": "thinking", "text": "..."}` — reasoning process
- `{"type": "search", "data": {...}}` — search metadata
- `{"type": "final_content", "text": "...", "source_type": "..."}` — final confirmed content (from record-map)

**Special handling**:
- Clean up Notion internal `<lang>` tags and `primary="zh-CN"` attribute fragments
- Extract final authoritative content from record-map (used to correct streamed content)
- Search data extraction and deduplication

### 4.5 Multi-Account Load Balancing

**AccountPool** implements Round-Robin polling:
- Each account corresponds to one `NotionOpusAPI` instance (with its own cloudscraper session)
- On request failure, mark the account as cooling down (default 3 seconds)
- Skip cooling accounts and poll to the next
- When all accounts are cooling, **wait for the soonest cooldown to expire** (up to 15 seconds) rather than failing immediately
- Retry count: `max(3, number of accounts)` — at least 3 retries even with a single account
- 429 (Notion rate limit) is also retryable (retried with a different account)

### 4.6 Supported Models

> **To add / sync a model**: follow the checklist → [`docs/ADD_MODEL.md`](./ADD_MODEL.md) (6 required files + self-check table, no need to search the whole repo).

| External Name | Notion Internal Codename | Thread Type | Description |
|---------------|--------------------------|-------------|-------------|
| claude-sonnet-4-6 | almond-croissant-low | workflow | **Recommended**, best balance of speed and quality |
| claude-sonnet-5 | angel-cake-high | workflow | Sonnet 5 |
| claude-opus-4-7 | apricot-sorbet-high | workflow | Stronger reasoning |
| claude-opus-4-8 | ambrosia-tart-high | workflow | Strong reasoning Claude |
| claude-opus-5 | agave-flan | workflow | Newest Claude Opus, strongest reasoning |
| gpt-5.6-sol | orange-mousse | workflow | GPT-5.6 Sol |
| gpt-5.6-terra | orchid-muffin | workflow | GPT-5.6 Terra |
| gpt-5.6-luna | olive-jellyroll | workflow | GPT-5.6 Luna |
| gpt-5.5 | opal-quince-medium | workflow | GPT-5.5 |
| gpt-5.4 | oval-kumquat-medium | workflow | OpenAI model |
| gemini-3.6-flash | vertex-gemini-3.6-flash | markdown-chat | Gemini 3.6 Flash |
| gemini-3.5-flash | vertex-gemini-3.5-flash | markdown-chat | Gemini 3.5 Flash |
| gemini-3.1-pro | galette-medium-thinking | workflow | Google's strongest reasoning model |
| kimi-k3 | fireworks-kimi-k3 | workflow | Kimi K3 |
| kimi-k2.7 | fireworks-kimi-k2.7 | workflow | Kimi K2.7 |
| kimi-k2.6 | fireworks-kimi-k2.6 | workflow | Kimi K2.6 |
| grok-4.3 | xigua-mochi-medium | workflow | xAI Grok 4.3 |
| spacexai-4.5 | strawberry-whoopiepie | workflow | SpaceXAI 4.5 |
| grok-build-0.1 | xinomavro-cake | workflow | xAI Grok Build 0.1 |
| deepseek-v4-pro | baseten-deepseek-v4-pro | workflow | DeepSeek V4 Pro |
| glm-5.2 | baseten-glm-5.2 | workflow | GLM 5.2 |

### 4.7 Frontend Web UI

**Name**: Notion AI Studio

**Architecture**: Vanilla JS modular, organized via the `window.NotionAI` namespace

**Core features**:
- Conversation management: create, rename, delete, star
- Model selector: grouped dropdown (Anthropic / OpenAI / Google / Moonshot / xAI / DeepSeek)
- Streaming render: SSE real-time output, supports Markdown + code highlighting
- Thinking panel: collapsible, shows AI reasoning process with timer
- Search panel: collapsible, shows search queries and source links
- Theme switching: light/dark mode
- Ambient particle animations (AmbientEngine): supports default/snow/rain/sunny/night weather effects
- Time-based greeting: shows different greetings based on CST time
- Data persistence: LocalStorage stores conversation history
- Responsive design: mobile-friendly sidebar

**SSE Protocol** (frontend–backend contract):
- `choices[0].delta.content` — main content (standard OpenAI format)
- `choices[0].delta.reasoning_content` — thinking content (Heavy mode)
- `{"type": "thinking_chunk", "text": "..."}` — thinking chunk (Standard mode)
- `{"type": "search_metadata", "searches": {...}}` — search results
- `{"type": "content_replace", "content": "..."}` — content replacement (Web client only)
- `{"type": "thinking_replace", "thinking": "..."}` — thinking replacement (Web client only)


---

## 5. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions (core endpoint) |
| `/v1/models` | GET | List available models |
| `/v1/conversations/{id}` | DELETE | Delete conversation (Heavy mode) |
| `/health` | GET | Health check (account pool status, uptime) |
| `/` | GET | Web UI static page |

**Authentication**: Optional Bearer Token (configured via `API_KEY` environment variable)

**Rate limiting**: Per-IP rate limiting, can be disabled via `DISABLE_RATE_LIMIT=True`

---

## 6. Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NOTION_ACCOUNTS` | Notion account JSON array (required) | — |
| `APP_MODE` | Mode: lite / standard / heavy | `heavy` |
| `API_KEY` | Client authentication key | empty (no auth) |
| `DB_PATH` | SQLite database path | `./data/conversations.db` |
| `HOST` | Service bind IP | `0.0.0.0` |
| `PORT` | Service port | `8000` |
| `HOST_PORT` | Docker host port | `8000` |
| `ALLOWED_ORIGINS` | CORS allowed origins | `*` |
| `SILICONFLOW_API_KEY` | Heavy mode summary compression service key | empty |
| `DISABLE_RATE_LIMIT` | Disable rate limiting | `false` |
| `NOTION_CLIENT_VERSION` | Override Notion client version header | `23.13.20260228.0625` |
| `LOG_LEVEL` | Log level | `INFO` |
| `TZ` | Timezone | `Asia/Shanghai` |

**How to get account credentials**:
1. Log in to https://www.notion.so/ai
2. F12 → Application → Cookies → copy `token_v2`
3. F12 → Console → run `scripts/extract_notion_info.js` to get the remaining fields

---

## 7. Development History (Git Commit Timeline)

### Phase 1: Foundation (2026-03-07 ~ 03-08)

| Date | Commit | Content |
|------|--------|---------|
| 03-07 | `8ccc102` | Standardize OpenAI protocol, improve rate limit error messages |
| 03-07 | `0836e28` | Structural adjustments, add GEMINI.md |
| 03-08 | `a8b868c` | Fix long-response amnesia and double rendering, upgrade hierarchical memory and multi-account pool |
| 03-08 | `e98b92a` | Opus/GPT model thinking block optimization, fix missing AI replies in sliding window |
| 03-08 | `2c6dd2e` | Fix Opus/GPT model thinking block / main content confusion |
| 03-08 | `155ab7f` | Add GPT-5.4 (oval-kumquat-medium) |
| 03-08 | `3fc672f` | **Critical fix**: fix severe bug where AI replies were missing from sliding window |
| 03-08 | `520fb2c` | **Critical fix**: fix context memory loss bug, build sliding window + compression pool system |

### Phase 2: Mode Expansion and Frontend Refactor (2026-03-09 ~ 03-11)

| Date | Commit | Content |
|------|--------|---------|
| 03-09 | `cd0538d` | Add CLAUDE.md project progress document |
| 03-09 | `9f156a1` | Rewrite CLAUDE.md as a concise version |
| 03-09 | `50e5827` | **Refactor**: separate frontend static assets + JS modularization |
| 03-09 | `330d5ab` | Optimize frontend design, add frontend features |
| 03-09 | `067d571` | Initialize frontend app: core chat, UI, model selector |
| 03-09 | `d51e43c` | Update v0.9 README |
| 03-09 | `8e9f884` | **v1.0**: add Lite mode |
| 03-11 | `6ab9d00` | Add Standard mode support (with known issues) |
| 03-11 | `40c0b9c` | Partial optimizations, update README |

### Phase 3: Documentation Internationalization (2026-03-11 ~ 03-12)

| Date | Commit | Content |
|------|--------|---------|
| 03-11 | `e89d6e1` | Add English README |
| 03-11 | `0dbd301` | Clean up debug files and notes |
| 03-12 | `78bf3c1` | Create Chinese README |
| 03-12 | `42e42b1` | Translate README and update formatting |
| 03-12 | `21c24d1` | Englishify |

### Phase 4: Bug Fixes and Security Hardening (2026-03-12 ~ 03-13)

| Date | Commit | Content |
|------|--------|---------|
| 03-12 | `17845b1` | Maintenance of thinking block leak bug (still imperfect) |
| 03-13 | `e98a6cf` | **PR #1 merged**: fix thinking block leak in streaming responses |
| 03-13 | `31fd6b0` | **PR #4 merged**: restrict overly permissive CORS policy |
| 03-13 | `5f0d7e1` | Optimize rate limiting logic and add troubleshooting docs |

### Phase 5: New Models and Frontend Optimization (2026-04-28 ~ 04-29)

| Date | Commit | Content |
|------|--------|---------|
| 04-28 | `423e255` | Sync official new models, add no-rate-limit mode |
| 04-29 | `fe558d4` | Fix thinking block overflow bug, add patches for new models |
| 04-29 | `0686550` | Deep frontend optimization, replace with clean frontend UI |

### Phase 6: Error System Refactor and Stability Optimization (2026-04-30)

| Date | Commit | Content |
|------|--------|---------|
| 04-30 | `819d7bb` | Commit missing CSS/JS module files from yesterday's frontend optimization |
| 04-30 | `4bb823f` | **Major overhaul**: structured error messages, retry optimization, Cloudflare fix, footnote cleanup, account extraction script refactor |
| 04-30 | `8aa02e9` | Account extraction script supports multi-account selection (getSpaces API) |
| 04-30 | *(pending push)* | Frontend: move Copy button to message bottom, user message Copy, draggable sidebar width, dark mode code highlighting |

**`4bb823f` detailed changes**:
- **Backend error system**: unify all 503/500 as structured JSON responses with 11 error codes (NOTION_401/403/429/5XX, NETWORK_TIMEOUT, POOL_COOLING, etc.)
- **Retry optimization**: `max_retries` changed from `min(3, accounts)` to `max(3, accounts)`; 429 is now retryable
- **Account pool optimization**: cooldown 10s→3s; wait during cooldown instead of failing immediately
- **Cloudflare fix**: cloudscraper instance reuse; auto-rebuild on 403; cookies passed as header string (fixes encoding crash caused by non-ASCII workspace names)
- **Frontend error cards**: red-themed cards showing error code + specific cause + suggested action + expandable technical details
- **Footnote cleanup**: remove `[^1]` references and end-of-document footnote definitions before Markdown rendering
- **Account extraction script refactor**: supports multi-workspace selection, deep field extraction, 3-second delay before prompt
- **Bug fix**: `_persist_history_messages` 3-tuple unpacking error
- **New files**: `docs/PROJECT_PROGRESS.md`, `accounts.README.md`
- **New config**: `NOTION_CLIENT_VERSION` environment variable

### Phase 7: New Model Sync (2026-05 ~ 06)

| Date | Commit | Content |
|------|--------|---------|
| 05-04 | `6a302ea` | Restructure docs, rewrite README in both languages |
| 05-04 | `2991421` | **PR #12 merged**: browser-assisted login `login.py` |
| 05-29 | `0611adb` | Sync official new model Claude Opus 4.8 (`ambrosia-tart-high`) |
| 05-29 | `7b4439e` | Fix bug with default fallback Sonnet model |
| 06-06 | `880357e` | Sync official new models Grok 4.3, Grok Build 0.1, DeepSeek V4 Pro |
| 07-25 | — | Sync official new model Claude Opus 5 (`claude-opus-5` / `agave-flan`), total models 22 |
| 08-13 | — | Normalize model names (hyphen-separated), add Kimi K3 / K2.6 / Gemini 3.6 Flash, retire Opus 4.6 / Haiku 4.5 / Gemini 3 Flash / Fable 5, total models 21 |

---

## 8. Git Status (as of 2026-06)

### 8.1 Branch Status

| Branch | Status | Description |
|--------|--------|-------------|
| `main` | ✅ Current branch | Main development branch |
| `security-fix-permissive-cors-policy` | ✅ Merged (PR #4) | CORS security fix |
| `jules-1625553040058672141` | ✅ Merged (PR #1) | Thinking leak fix |
| `Sanity-Cloud:feat/login-cdp` | ✅ Merged (PR #12) | Browser-assisted login login.py |

### 8.2 Recent Commits

| Commit | Content |
|--------|---------|
| `880357e` | Sync official new models Grok 4.3, Grok Build 0.1, DeepSeek V4 Pro |
| `0611adb` | Sync official new model Claude Opus 4.8 |
| `7b4439e` | Fix bug with default fallback Sonnet model |
| `6a302ea` | Restructure docs: merge bilingual issues, delete redundant md files, update README |
| PR #12 | feat: browser-assisted login login.py (CDP), add websocket-client dependency |

### 8.3 Closed Branches Worth Referencing

The following PRs were voluntarily closed by the author (not merged); branches still exist and content can be cherry-picked as needed:

1. **`perf-optimize-migration-n1`** — Optimize conversation migration N+1 queries (2026-03-13)
2. **`fix-remove-unused-import-logger`** — Clean up unused `time` import in `app/logger.py` (2026-03-13)
3. **`testing-improvement-truncate-json`** — Add unit tests for `_truncate_json` (2026-03-13)

---

## 9. Known Issues and Improvements

### 9.1 Known Issues

1. **Thinking block leak**: Despite multiple fixes (PR #1, `fe558d4`), some models may still leak thinking content into the main body in certain scenarios. Currently handled by post-processing via `_trim_redundant_thinking()` and `_build_thinking_replacement()`.

2. **Notion home page thread accumulation**: To preserve conversation context, threads are no longer deleted automatically, causing Notion's home page to accumulate many conversation records.

3. **No automated tests**: The project has no test framework or CI/CD. There is one unmerged branch containing unit tests for `_truncate_json`.

4. **CORS configuration**: Default `ALLOWED_ORIGINS=*`; production environments need manual configuration.

5. **Unpinned dependencies**: All dependencies in `requirements.txt` have no pinned versions.

6. **Notion anti-scraping risk**: Notion may restrict workspaces for unusual request patterns (many thread creations, server IP requests, etc.), suspending AI access. Business Trial workspaces are especially prone to this.

### 9.2 Improvement Backlog

1. **Configurable sliding window size**: Currently hardcoded to 8 rounds; README mentions a future environment variable
2. **Test coverage**: need to establish a test framework
3. **CI/CD**: need to configure automated build and testing
4. **Dependency version pinning**: should use `pip freeze` or `poetry` to lock versions
5. **Frontend framework**: current vanilla JS modular approach may become hard to maintain as complexity grows

---

## 10. Compatibility

| Client | Status | Notes |
|--------|--------|-------|
| Cherry Studio | ✅ Full support | Recommended |
| Zotero Translation | ✅ Full support | Slightly slow, but Sonnet model translation is accurate |
| Immersive Translate | ❌ Not recommended | Latency too high |
| Claude Code | ❌ Not supported | Uses Anthropic native API format, incompatible |

**Note**: Due to Notion AI's own call latency, expect ~3 seconds from request to first response.

---

## 11. Deployment Guide

### Docker Deployment (Recommended)

```bash
# 1. Configure environment variables
cp .env.example .env
# Edit .env and fill in Notion credentials

# 2. Start service
docker-compose up -d

# 3. View logs
docker-compose logs -f

# 4. Health check
curl http://localhost:8000/health
```

### Local Development

```bash
pip install -r requirements.txt
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

### Management Scripts

```bash
./scripts/manage.sh start    # Start
./scripts/manage.sh stop     # Stop
./scripts/manage.sh status   # Status
./scripts/manage.sh logs     # Logs
./scripts/manage.sh backup   # Backup database
./scripts/manage.sh test     # Test API
```

---

## 12. Current Work Focus

**As of 2026-07**:

**Completed**:
- ✅ Model list synced to 21, covering latest Claude Opus 5 (`agave-flan`), GPT-5.6, Gemini, Kimi (incl. K3), GLM, Grok, DeepSeek
- ✅ Merged PR #12: browser-assisted login `login.py` (CDP, supports Chrome/Edge, auto-writes accounts.json + .env)
- ✅ Documentation restructure: README bilingual rewrite, issues.md bilingual merge, removed redundant md files (ARCHITECTURE.md, DEPLOYMENT.md, accounts.README.md, CLAUDE.md, issues_CN.md)
- ✅ Structured error message system (11 error codes, frontend red error cards)
- ✅ Retry mechanism optimization (3 retries for single account, 429 retryable, wait during cooldown)
- ✅ Cloudflare bypass optimization (scraper reuse, auto-rebuild on 403, cookie encoding fix)
- ✅ Frontend optimization: minimalist custom UI (Notion AI Studio), ambient particle animations, Copy button, draggable sidebar, dark mode code highlighting

**Under observation**:
- ⏳ Notion anti-scraping control situation
- ⏳ login.py compatibility across platforms (Windows/Mac/Linux)

**Next steps**:
- Image/PDF upload support (packet capture analysis complete, flow confirmed)
- Research methods to reduce Notion anti-scraping trigger probability

---

*This document is updated in sync with each git commit.*

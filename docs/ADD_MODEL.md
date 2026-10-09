# Add Model Checklist

> To add a model, only update the places listed below. **No need to search the whole repo.**  
> Example: `claude-opus-5` → Notion codename `agave-flan`, display name `Opus 5`

You need to confirm first: **external API name**, **Notion internal codename**, **display name**, **provider group** (Anthropic / OpenAI / …).

---

## Required Changes (6 files)

### 1. `app/model_registry.py` (source of truth)

Add one line to each of three dicts, with the external name as the key:

| Dict | Value |
|------|-------|
| `MODEL_MAP` | Notion internal codename |
| `DISPLAY_NAMES` | Display name |
| `MODEL_ICONS` | Icon (copy from an existing model in the same provider) |

`NOTION_MODEL_REVERSE_MAP` does not need to be written manually.  
`/v1/models` and request validation read from here automatically — **do not** duplicate the list in `chat.py` / `models.py`.

Only change `MARKDOWN_CHAT_MODELS` if the new model must use `markdown-chat` (the vast majority use the default `workflow`).

### 2. `frontend/index.html` (the live UI uses this)

| Location | Content |
|----------|---------|
| `MODEL_GROUPS` | Corresponding group; optionally add `badge:"New"` |
| `MODELS` | `{id, label}` |
| `MODEL_DISPLAY_NAMES` | id → display name |
| `MODEL_PROVIDERS` | id → provider name |

### 3. `frontend/js/core/constants.js` (mirrored with html — id sets must be consistent)

| Location | Content |
|----------|---------|
| `MODEL_GROUPS` | Includes `icon`, optional `badge` |
| `MODELS` | `{id, label}` |
| `MODEL_DISPLAY_NAMES` | id → display name |
| `MODEL_ICONS` | id → icon |

### 4–6. Documentation

| File | What to change |
|------|----------------|
| `README.md` | Model count N→N+1; add a row to the "Supported Models" table; update the intro note (keep the link to this file) |
| `README_EG.md` | Same (English) |
| `docs/PROJECT_PROGRESS.md` | Count; §4.6 table (external name / codename / thread / description); date |

---

## Do Not Change

Default values / old model names in examples can stay:

- `app/schemas.py`, `main.py`, `scripts/manage.sh` (default or test model)
- `app/api/chat.py`, `app/api/models.py` (read dynamically from registry)
- `conversation.py` / `notion_client.py` (no hardcoded name list)

Unless the task explicitly requires changing the default model.

---

## Checklist

```
[ ] model_registry.py     MODEL_MAP / DISPLAY_NAMES / MODEL_ICONS
[ ] frontend/index.html   GROUPS / MODELS / DISPLAY / PROVIDERS
[ ] frontend/js/core/constants.js  GROUPS / MODELS / DISPLAY / ICONS
[ ] README.md + README_EG.md + docs/PROJECT_PROGRESS.md
[ ] python -c "from app.model_registry import *; assert is_supported_model('…'); assert get_notion_model('…')=='…'"
```

New provider: add a group to both `MODEL_GROUPS`; add the provider name in `index.html`'s `MODEL_PROVIDERS`.  
Removing a model: delete symmetrically from the lists above; update count N→N-1.

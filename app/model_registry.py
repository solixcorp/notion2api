MODEL_MAP: dict[str, str] = {
    # Anthropic Claude
    "claude-sonnet-4-6": "almond-croissant-low",
    "claude-sonnet-5": "angel-cake-high",
    "claude-opus-4-7": "apricot-sorbet-high",
    "claude-opus-4-8": "ambrosia-tart-high",
    "claude-opus-5": "agave-flan",
    # OpenAI GPT
    "gpt-5.6-sol": "orange-mousse",
    "gpt-5.6-terra": "orchid-muffin",
    "gpt-5.6-luna": "olive-jellyroll",
    "gpt-5.5": "opal-quince-medium",
    "gpt-5.4": "oval-kumquat-medium",
    # Google Gemini
    "gemini-3.5-flash": "vertex-gemini-3.5-flash",
    "gemini-3.6-flash": "vertex-gemini-3.6-flash",
    "gemini-3.1-pro": "galette-medium-thinking",
    # Moonshot Kimi
    "kimi-k2.6": "fireworks-kimi-k2.6",
    "kimi-k2.7": "fireworks-kimi-k2.7",
    "kimi-k3": "fireworks-kimi-k3",
    # xAI Grok
    "grok-4.3": "xigua-mochi-medium",
    "spacexai-4.5": "strawberry-whoopiepie",
    "grok-build-0.1": "xinomavro-cake",
    # DeepSeek
    "deepseek-v4-pro": "baseten-deepseek-v4-pro",
    # Zhipu GLM
    "glm-5.2": "baseten-glm-5.2",
}

NOTION_MODEL_REVERSE_MAP: dict[str, str] = {value: key for key, value in MODEL_MAP.items()}

DISPLAY_NAMES: dict[str, str] = {
    # Anthropic Claude
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-sonnet-5": "Sonnet 5",
    "claude-opus-4-7": "Opus 4.7",
    "claude-opus-4-8": "Opus 4.8",
    "claude-opus-5": "Opus 5",
    # OpenAI GPT
    "gpt-5.6-sol": "GPT-5.6 Sol",
    "gpt-5.6-terra": "GPT-5.6 Terra",
    "gpt-5.6-luna": "GPT-5.6 Luna",
    "gpt-5.5": "GPT-5.5",
    "gpt-5.4": "GPT-5.4",
    # Google Gemini
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gemini-3.6-flash": "Gemini 3.6 Flash",
    "gemini-3.1-pro": "Gemini 3.1 Pro",
    # Moonshot Kimi
    "kimi-k2.6": "Kimi K2.6",
    "kimi-k2.7": "Kimi K2.7",
    "kimi-k3": "Kimi K3",
    # xAI Grok
    "grok-4.3": "Grok 4.3",
    "spacexai-4.5": "SpaceXAI 4.5",
    "grok-build-0.1": "Grok Build 0.1",
    # DeepSeek
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    # Zhipu GLM
    "glm-5.2": "GLM 5.2",
}

MODEL_ICONS: dict[str, str] = {
    # Anthropic Claude
    "claude-sonnet-4-6": "✳️",
    "claude-sonnet-5": "✳️",
    "claude-opus-4-7": "✳️",
    "claude-opus-4-8": "✳️",
    "claude-opus-5": "✳️",
    # OpenAI GPT
    "gpt-5.6-sol": "⚙",
    "gpt-5.6-terra": "⚙",
    "gpt-5.6-luna": "⚙",
    "gpt-5.5": "⚙",
    "gpt-5.4": "⚙",
    # Google Gemini
    "gemini-3.5-flash": "✦",
    "gemini-3.6-flash": "✦",
    "gemini-3.1-pro": "✦",
    # Moonshot Kimi
    "kimi-k2.6": "🌙",
    "kimi-k2.7": "🌙",
    "kimi-k3": "🌙",
    # xAI Grok
    "grok-4.3": "⚡",
    "spacexai-4.5": "⚡",
    "grok-build-0.1": "⚡",
    # DeepSeek
    "deepseek-v4-pro": "🐋",
    # Zhipu GLM
    "glm-5.2": "◆",
}

# 默认使用 Sonnet 4.6（速度和质量的最佳平衡）
DEFAULT_MODEL = "claude-sonnet-4-6"


def get_notion_model(model_name: str) -> str:
    return MODEL_MAP.get(model_name, MODEL_MAP[DEFAULT_MODEL])


# 需要走 markdown-chat 的 Notion 内部代号（vertex- 前缀的模型）
# Gemini 3.1 Pro (galette-medium-thinking) 已改为 workflow，不再走 markdown-chat
MARKDOWN_CHAT_MODELS: set[str] = {
    "vertex-gemini-3.5-flash",
    "vertex-gemini-3.6-flash",
}


def is_gemini_model(model_name: str) -> bool:
    """判断是否为 Gemini 系列模型（用于 config block 构建等）"""
    standard_name = get_standard_model(model_name)
    if standard_name.startswith("gemini-"):
        return True
    notion_model = get_notion_model(standard_name)
    return notion_model.startswith("vertex-") or notion_model.startswith("galette-")


def get_thread_type(model_name: str) -> str:
    """
    根据模型确定 Notion thread type。
    只有 vertex- 前缀的模型走 markdown-chat，其余全部走 workflow。
    """
    standard_name = get_standard_model(model_name)
    notion_model = get_notion_model(standard_name)
    if notion_model in MARKDOWN_CHAT_MODELS:
        return "markdown-chat"
    return "workflow"


def get_standard_model(model_name: str) -> str:
    if model_name in MODEL_MAP:
        return model_name
    return NOTION_MODEL_REVERSE_MAP.get(model_name, DEFAULT_MODEL)


def list_available_models() -> list[str]:
    return list(MODEL_MAP.keys())


def is_supported_model(model_name: str) -> bool:
    return model_name in MODEL_MAP


def get_display_name(model_name: str) -> str:
    standard_name = get_standard_model(model_name)
    return DISPLAY_NAMES.get(standard_name, standard_name)


def get_model_icon(model_name: str) -> str:
    standard_name = get_standard_model(model_name)
    return MODEL_ICONS.get(standard_name, "")
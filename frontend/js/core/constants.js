/**
 * Constants Module — Notion AI Studio
 */

window.NotionAI = window.NotionAI || {};
window.NotionAI.Core = window.NotionAI.Core || {};

window.NotionAI.Core.Constants = {
    STORAGE_KEYS: {
        API_KEY: 'claude_api_key',
        BASE_URL: 'claude_base_url',
        CHATS: 'claude_chats',
        THEME: 'theme'
    },

    API: {
        CHAT_COMPLETIONS: '/v1/chat/completions',
        DELETE_CONVERSATION: (id) => `/v1/conversations/${encodeURIComponent(id)}`
    },

    // Model definitions with grouping
    MODEL_GROUPS: [
        {
            label: 'Anthropic',
            models: [
                { id: "claude-sonnet-4-6", label: "Sonnet 4.6", icon: "✳️", desc: "Fast & efficient" },
                { id: "claude-sonnet-5", label: "Sonnet 5", icon: "✳️", badge: "New" },
                { id: "claude-opus-4-7", label: "Opus 4.7", icon: "✳️" },
                { id: "claude-opus-4-8", label: "Opus 4.8", icon: "✳️" },
                { id: "claude-opus-5", label: "Opus 5", icon: "✳️", badge: "New" },
            ]
        },
        {
            label: 'OpenAI',
            models: [
                { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", icon: "⚙", badge: "New" },
                { id: "gpt-5.6-terra", label: "GPT-5.6 Terra", icon: "⚙", badge: "New" },
                { id: "gpt-5.6-luna", label: "GPT-5.6 Luna", icon: "⚙", badge: "New" },
                { id: "gpt-5.5", label: "GPT-5.5", icon: "⚙", badge: "Beta" },
                { id: "gpt-5.4", label: "GPT-5.4", icon: "⚙" },
            ]
        },
        {
            label: 'Google',
            models: [
                { id: "gemini-3.6-flash", label: "Gemini 3.6 Flash", icon: "✦", badge: "New" },
                { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash", icon: "✦" },
                { id: "gemini-3.1-pro", label: "Gemini 3.1 Pro", icon: "✦" },
            ]
        },
        {
            label: 'Moonshot',
            models: [
                { id: "kimi-k3", label: "Kimi K3", icon: "🌙", badge: "New" },
                { id: "kimi-k2.7", label: "Kimi K2.7", icon: "🌙" },
                { id: "kimi-k2.6", label: "Kimi K2.6", icon: "🌙" },
            ]
        },
        {
            label: 'xAI',
            models: [
                { id: "grok-4.3", label: "Grok 4.3", icon: "⚡", badge: "New" },
                { id: "spacexai-4.5", label: "SpaceXAI 4.5", icon: "⚡", badge: "New" },
                { id: "grok-build-0.1", label: "Grok Build 0.1", icon: "⚡", badge: "New" },
            ]
        },
        {
            label: 'DeepSeek',
            models: [
                { id: "deepseek-v4-pro", label: "DeepSeek V4 Pro", icon: "🐋", badge: "New" },
            ]
        },
        {
            label: 'Zhipu',
            models: [
                { id: "glm-5.2", label: "GLM 5.2", icon: "◆", badge: "New" },
            ]
        }
    ],

    // Flat model list (for backward compat)
    MODELS: [
        { id: "claude-sonnet-4-6", label: "Sonnet 4.6" },
        { id: "claude-sonnet-5", label: "Sonnet 5" },
        { id: "claude-opus-4-7", label: "Opus 4.7" },
        { id: "claude-opus-4-8", label: "Opus 4.8" },
        { id: "claude-opus-5", label: "Opus 5" },
        { id: "gpt-5.6-sol", label: "GPT-5.6 Sol" },
        { id: "gpt-5.6-terra", label: "GPT-5.6 Terra" },
        { id: "gpt-5.6-luna", label: "GPT-5.6 Luna" },
        { id: "gpt-5.5", label: "GPT-5.5" },
        { id: "gpt-5.4", label: "GPT-5.4" },
        { id: "gemini-3.6-flash", label: "Gemini 3.6 Flash" },
        { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash" },
        { id: "gemini-3.1-pro", label: "Gemini 3.1 Pro" },
        { id: "kimi-k3", label: "Kimi K3" },
        { id: "kimi-k2.7", label: "Kimi K2.7" },
        { id: "kimi-k2.6", label: "Kimi K2.6" },
        { id: "grok-4.3", label: "Grok 4.3" },
        { id: "spacexai-4.5", label: "SpaceXAI 4.5" },
        { id: "grok-build-0.1", label: "Grok Build 0.1" },
        { id: "deepseek-v4-pro", label: "DeepSeek V4 Pro" },
        { id: "glm-5.2", label: "GLM 5.2" },
    ],

    DEFAULT_MODEL: "claude-sonnet-4-6",

    MODEL_DISPLAY_NAMES: {
        "claude-sonnet-4-6": "Sonnet 4.6",
        "claude-sonnet-5": "Sonnet 5",
        "claude-opus-4-7": "Opus 4.7",
        "claude-opus-4-8": "Opus 4.8",
        "claude-opus-5": "Opus 5",
        "gpt-5.6-sol": "GPT-5.6 Sol",
        "gpt-5.6-terra": "GPT-5.6 Terra",
        "gpt-5.6-luna": "GPT-5.6 Luna",
        "gpt-5.5": "GPT-5.5",
        "gpt-5.4": "GPT-5.4",
        "gemini-3.6-flash": "Gemini 3.6 Flash",
        "gemini-3.5-flash": "Gemini 3.5 Flash",
        "gemini-3.1-pro": "Gemini 3.1 Pro",
        "kimi-k3": "Kimi K3",
        "kimi-k2.7": "Kimi K2.7",
        "kimi-k2.6": "Kimi K2.6",
        "grok-4.3": "Grok 4.3",
        "spacexai-4.5": "SpaceXAI 4.5",
        "grok-build-0.1": "Grok Build 0.1",
        "deepseek-v4-pro": "DeepSeek V4 Pro",
        "glm-5.2": "GLM 5.2",
    },

    MODEL_ICONS: {
        "claude-sonnet-4-6": "✳️",
        "claude-sonnet-5": "✳️",
        "claude-opus-4-7": "✳️",
        "claude-opus-4-8": "✳️",
        "claude-opus-5": "✳️",
        "gpt-5.6-sol": "⚙",
        "gpt-5.6-terra": "⚙",
        "gpt-5.6-luna": "⚙",
        "gpt-5.5": "⚙",
        "gpt-5.4": "⚙",
        "gemini-3.6-flash": "✦",
        "gemini-3.5-flash": "✦",
        "gemini-3.1-pro": "✦",
        "kimi-k3": "🌙",
        "kimi-k2.7": "🌙",
        "kimi-k2.6": "🌙",
        "grok-4.3": "⚡",
        "spacexai-4.5": "⚡",
        "grok-build-0.1": "⚡",
        "deepseek-v4-pro": "🐋",
        "glm-5.2": "◆",
    },

    GREETINGS: {
        EARLY_MORNING: "Early bird thinking",
        MORNING: "Morning clarity",
        MIDDAY: "Midday focus",
        AFTERNOON: "Afternoon momentum",
        GOLDEN_HOUR: "Golden hour thinking",
        EVENING: "Evening deep work",
        NIGHT_OWL: "Night owl mode",
        LATE_NIGHT: "Late night thinking"
    },

    CLIENT_TYPE: 'Web'
};
import time
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

# ================================
# Request Schemas (Chat Completion)
# ================================

class ChatMessage(BaseModel):
    """A single chat message."""
    role: Literal["user", "assistant", "system"]
    content: str
    thinking: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    """
    OpenAI-compatible chat completion request payload.
    `conversation_id` is a custom extension field; omitting it treats the request as stateless.
    """
    model: str = Field(default="claude-sonnet-4-6", description="Requested model.")
    messages: List[ChatMessage]
    stream: bool = Field(default=False, description="Whether to stream the response as SSE.")
    temperature: Optional[float] = Field(default=None, description="Sampling temperature.")
    conversation_id: Optional[str] = Field(default=None, description="Extension for stateful conversation tracking.")

# ================================
# Non-streaming Response Schemas
# ================================

class ChatMessageResponseChoice(BaseModel):
    """A single choice in a non-streaming response."""
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"

class ChatCompletionResponse(BaseModel):
    """
    OpenAI-compatible full chat completion response payload.
    """
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatMessageResponseChoice]
    usage: Dict[str, int] = Field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    # Standard mode extension field
    search_metadata: Optional[Dict[str, Any]] = Field(default=None)

# ================================
# Streaming Response Schemas (internal)
# ================================

class ChatCompletionChunkDelta(BaseModel):
    """SSE delta block."""
    content: Optional[str] = None
    role: Optional[str] = None

class ChatCompletionChunkChoice(BaseModel):
    """SSE choice block."""
    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None

class ChatCompletionChunk(BaseModel):
    """
    OpenAI-compatible streaming chunk.
    """
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChunkChoice]

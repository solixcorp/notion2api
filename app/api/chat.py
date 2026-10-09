import asyncio
import json
import re
import time
import uuid
from difflib import SequenceMatcher
from typing import Any, Dict, Generator, Iterable, List, Tuple

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import is_lite_mode
from app.conversation import (
    build_lite_transcript,
    compress_round_if_needed,
    compress_sliding_window_round,
)
from app.logger import logger
from app.model_registry import is_supported_model, list_available_models
from app.notion_client import NotionUpstreamError
from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatMessageResponseChoice,
)

router = APIRouter()


# ─── Structured error responses ────────────────────────────────
def _classify_upstream_error(exc: NotionUpstreamError) -> dict[str, Any]:
    sc = exc.status_code

    if sc == 401:
        return {
            "code": "NOTION_401",
            "type": "upstream_auth_error",
            "message": "Notion authentication failed (HTTP 401). Your token may have expired.",
            "suggestion": "Re-generate your token_v2 and update the configuration.",
        }
    if sc == 403:
        return {
            "code": "NOTION_403",
            "type": "upstream_forbidden",
            "message": "Notion access denied (HTTP 403). May be a Cloudflare block or account restriction.",
            "suggestion": "Check your server's network environment or retry in a moment.",
        }
    if sc == 429:
        return {
            "code": "NOTION_429",
            "type": "upstream_rate_limit",
            "message": "Too many requests to Notion (HTTP 429).",
            "suggestion": "Wait a few seconds and retry, or configure multiple accounts to distribute load.",
        }
    if sc and sc >= 500:
        return {
            "code": f"NOTION_{sc}",
            "type": "upstream_server_error",
            "message": f"Notion service temporarily unavailable (HTTP {sc}).",
            "suggestion": "Server-side Notion failure. Please retry in a moment.",
        }
    if "timed out" in str(exc).lower():
        return {
            "code": "NETWORK_TIMEOUT",
            "type": "network_timeout",
            "message": "Connection to Notion timed out.",
            "suggestion": "Check network connectivity from your server to notion.so.",
        }
    if "failed" in str(exc).lower() and not sc:
        return {
            "code": "NETWORK_ERROR",
            "type": "network_error",
            "message": "Cannot connect to Notion service.",
            "suggestion": "Check your server's network and DNS configuration.",
        }
    if "empty" in str(exc).lower():
        return {
            "code": "NOTION_EMPTY",
            "type": "upstream_empty_response",
            "message": "Notion returned an empty response.",
            "suggestion": "Please resend your message.",
        }
    return {
        "code": "UPSTREAM_UNKNOWN",
        "type": "upstream_error",
        "message": str(exc),
        "suggestion": "Please try again in a moment.",
    }


def _build_error_response(
    status_code: int,
    *,
    code: str,
    message: str,
    error_type: str = "server_error",
    suggestion: str = "",
    detail: str = "",
) -> JSONResponse:
    """Build a unified error JSON response that the frontend can parse and display."""
    content: dict[str, Any] = {
        "error": {
            "message": message,
            "type": error_type,
            "code": code,
        }
    }
    if suggestion:
        content["error"]["suggestion"] = suggestion
    if detail:
        content["error"]["detail"] = detail
    return JSONResponse(status_code=status_code, content=content)


def _upstream_error_response(exc: NotionUpstreamError) -> JSONResponse:
    """Convert a NotionUpstreamError into a unified 503 JSON response."""
    info = _classify_upstream_error(exc)
    return _build_error_response(
        503,
        code=info["code"],
        message=info["message"],
        error_type=info["type"],
        suggestion=info.get("suggestion", ""),
        detail=exc.response_excerpt or "",
    )


RECALL_INTENT_KEYWORDS = [
    "earlier",
    "before",
    "recall",
    "remember",
    "last time",
    "previously",
    "do you remember",
    "we talked about",
    "history",
    "look it up",
    "search memory",
]


def _build_stream_chunk(
    response_id: str,
    model: str,
    *,
    content: str = "",
    thinking: str = "",
    role: str = "",
    finish_reason=None,
) -> str:
    delta: Dict[str, Any] = {}
    if role:
        delta["role"] = role
    if content:
        delta["content"] = content
    if thinking:
        delta["reasoning_content"] = thinking

    payload = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_local_ui_chunk(
    response_id: str,
    model: str,
    event_type: str,
    **payload_fields: Any,
) -> str:
    payload: Dict[str, Any] = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
        "type": event_type,
    }
    payload.update(payload_fields)
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _format_search_results_md(search_data: dict[str, Any]) -> str:
    """Format search data as a Markdown blockquote for standard clients."""
    lines = []
    queries = search_data.get("queries", [])
    if queries:
        lines.append(f"> 🔍 **Searched:** {', '.join(queries)}")

    sources = search_data.get("sources", [])
    if sources:
        lines.append("> 🌐 **Sources:**")
        for i, src in enumerate(sources[:5], 1):  # show at most 5 sources
            title = src.get("title") or src.get("url") or "Unknown source"
            url = src.get("url")
            if url:
                lines.append(f"> {i}. [{title}]({url})")
            else:
                lines.append(f"> {i}. {title}")

    if lines:
        return "\n".join(lines) + "\n\n"
    return ""


def _normalize_stream_item(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        return {"type": "content", "text": item}

    if isinstance(item, dict):
        item_type = str(item.get("type", "") or "").lower()
        if item_type == "content":
            return {"type": "content", "text": str(item.get("text", "") or "")}
        if item_type == "search":
            payload = item.get("data")
            return {
                "type": "search",
                "data": payload if isinstance(payload, dict) else {},
            }
        if item_type == "thinking":
            return {"type": "thinking", "text": str(item.get("text", "") or "")}
        if item_type == "final_content":
            return {
                "type": "final_content",
                "text": str(item.get("text", "") or ""),
                "source_type": str(item.get("source_type", "") or ""),
                "source_length": item.get("source_length"),
            }

    return {"type": "unknown"}


def _iter_stream_items(
    first_item: Any, stream_gen: Iterable[Any]
) -> Generator[Any, None, None]:
    if first_item is not None:
        yield first_item
    for item in stream_gen:
        yield item


def _compute_missing_suffix(current_text: str, final_text: str) -> str:
    if not final_text:
        return ""
    if not current_text:
        return final_text
    if final_text.startswith(current_text):
        return final_text[len(current_text) :]
    return ""


def _select_best_final_reply(
    streamed_text: str,
    final_text: str,
    final_source_type: str,
) -> tuple[str, str]:
    streamed = streamed_text or ""
    final = final_text or ""
    streamed_stripped = streamed.strip()
    final_stripped = final.strip()
    source = (final_source_type or "").strip().lower()

    if not final_stripped:
        return streamed, "streamed_only"
    if not streamed_stripped:
        return final, "final_only"
    if final.startswith(streamed):
        return final, "final_extends_streamed"
    if streamed.startswith(final):
        if source == "title" or len(final_stripped) <= max(
            32, int(len(streamed_stripped) * 0.35)
        ):
            return streamed, "streamed_beats_short_final"
        return final, "final_prefix_of_streamed"

    # Diverged content: usually prefer richer non-title final content.
    if source == "title" and len(final_stripped) < max(
        48, int(len(streamed_stripped) * 0.6)
    ):
        return streamed, "streamed_beats_title"
    if len(final_stripped) >= max(48, int(len(streamed_stripped) * 0.6)):
        return final, "final_diverged_preferred"
    return streamed, "streamed_diverged_preferred"


def _normalize_overlap_text(text: str) -> str:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return ""
    normalized = re.sub(r"```.*?```", " ", normalized, flags=re.DOTALL)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _trim_redundant_thinking(
    thinking_text: str, final_reply: str
) -> tuple[str, str, float]:
    thinking = str(thinking_text or "").strip()
    final = str(final_reply or "").strip()
    if not thinking or not final:
        return thinking, "missing_text", 0.0

    normalized_thinking = _normalize_overlap_text(thinking)
    normalized_final = _normalize_overlap_text(final)
    if not normalized_thinking or not normalized_final:
        return thinking, "missing_normalized_text", 0.0

    overlap_ratio = SequenceMatcher(None, normalized_thinking, normalized_final).ratio()
    if normalized_thinking == normalized_final:
        return "", "identical", overlap_ratio

    if thinking.endswith(final):
        prefix = thinking[: -len(final)].rstrip()
        if len(_normalize_overlap_text(prefix)) >= 10:
            return prefix, "suffix_trimmed", overlap_ratio
        return "", "suffix_cleared", overlap_ratio

    if overlap_ratio >= 0.92 and (
        normalized_thinking in normalized_final
        or normalized_final in normalized_thinking
    ):
        return "", "high_overlap_cleared", overlap_ratio

    return thinking, "kept", overlap_ratio


def _build_thinking_replacement(
    streamed_content_text: str,
    thinking_text: str,
    final_reply: str,
    final_source_type: str,
) -> dict[str, Any] | None:
    source = str(final_source_type or "").strip().lower()

    # Relax constraint: Allow replacement for more source types to fix Sonnet thinking leakage
    # But still require minimal validation for non-inference sources
    if source not in ("agent-inference", "text", "markdown-chat", ""):
        # Only skip for clearly non-thinking source types
        return None

    normalized_final = _normalize_overlap_text(final_reply)
    normalized_streamed = _normalize_overlap_text(streamed_content_text)

    # Require at least some thinking content to process
    if not _normalize_overlap_text(thinking_text):
        return None

    # For non-agent-inference sources, be more conservative but still check for obvious duplication
    if source != "agent-inference":
        # Only process if there's clear overlap or thinking is redundant
        if not normalized_final:
            return None

        # Check for obvious duplication (thinking appears in final reply)
        if thinking_text.strip() in final_reply or final_reply in thinking_text:
            # Clear case of duplication - trim it
            replacement, decision, overlap_ratio = _trim_redundant_thinking(
                thinking_text, final_reply
            )
            if replacement != str(thinking_text or "").strip():
                logger.debug(
                    "Non-agent-inference thinking replacement applied",
                    extra={
                        "request_info": {
                            "event": "thinking_replacement_non_agent",
                            "source_type": source,
                            "overlap_ratio": round(overlap_ratio, 4),
                            "decision": f"{decision}_non_agent_inference",
                        }
                    },
                )
                return {
                    "thinking": replacement,
                    "decision": f"{decision}_non_agent_inference",
                    "overlap_ratio": round(overlap_ratio, 4),
                    "source_type": source,
                }
        return None

    # Original agent-inference logic continues
    if not normalized_final:
        return None

    # Only apply when there is very little real content delta, to avoid incorrectly trimming complex reasoning.
    if normalized_streamed and len(normalized_streamed) >= max(
        10, int(len(normalized_final) * 0.35)
    ):
        return None

    replacement, decision, overlap_ratio = _trim_redundant_thinking(
        thinking_text, final_reply
    )
    if replacement == str(thinking_text or "").strip():
        return None

    return {
        "thinking": replacement,
        "decision": decision,
        "overlap_ratio": round(overlap_ratio, 4),
        "source_type": source,
    }


def _contains_recall_intent(text: str) -> bool:
    lowered = text.lower()
    for keyword in RECALL_INTENT_KEYWORDS:
        if keyword.isascii():
            if keyword.lower() in lowered:
                return True
            continue
        if keyword in text:
            return True
    return False


def _extract_recall_query(text: str) -> str:
    cleaned = text
    for keyword in RECALL_INTENT_KEYWORDS:
        if keyword.isascii():
            cleaned = re.sub(
                rf"\b{re.escape(keyword)}\b", " ", cleaned, flags=re.IGNORECASE
            )
        else:
            cleaned = cleaned.replace(keyword, " ")
    cleaned = re.sub(r"[\s，。！？、,.!?;:：]+", " ", cleaned).strip()
    return cleaned or text.strip()


def _prepare_messages(
    req_body: ChatCompletionRequest,
) -> Tuple[str, List[Tuple[str, str, str]], str]:
    system_messages = []
    dialogue_messages = []

    for msg in req_body.messages:
        if msg.role == "system":
            if msg.content.strip():
                system_messages.append(msg.content.strip())
            continue
        dialogue_messages.append((msg.role, msg.content, msg.thinking or ""))

    if not dialogue_messages:
        raise HTTPException(
            status_code=400,
            detail="The messages list must contain at least one user message.",
        )

    last_role, user_prompt, _ = dialogue_messages[-1]
    raw_user_prompt = user_prompt
    history_messages = dialogue_messages[:-1]

    if last_role != "user":
        raise HTTPException(
            status_code=400, detail="The last message must be from role 'user'."
        )
    if not user_prompt.strip():
        raise HTTPException(
            status_code=400, detail="The last user message cannot be empty."
        )

    if system_messages:
        from app.conversation import reframe_system_prompt_for_notion

        merged_system_prompt = "\n".join(system_messages)
        reframed = reframe_system_prompt_for_notion(merged_system_prompt)
        if reframed:
            user_prompt = f"{reframed}\n\n{user_prompt}"

    return user_prompt, history_messages, raw_user_prompt


def _prepare_messages_lite(req_body: ChatCompletionRequest) -> str:
    """Lite mode: extract the last user message only, merging any system instructions."""
    system_messages = []
    user_prompt = ""

    for msg in req_body.messages:
        if msg.role == "system" and msg.content.strip():
            system_messages.append(msg.content.strip())
        elif msg.role == "user":
            user_prompt = msg.content

    if not user_prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="The messages list must contain at least one user message.",
        )

    if system_messages:
        from app.conversation import reframe_system_prompt_for_notion

        reframed = reframe_system_prompt_for_notion(" ".join(system_messages))
        if reframed:
            user_prompt = f"{reframed}\n\n{user_prompt}"

    return user_prompt


def _create_lite_stream_generator(
    response_id: str,
    model_name: str,
    first_item: Any,
    stream_gen: Iterable[Any],
) -> Generator[str, None, None]:
    """Lite mode stream generator: outputs content only, ignores thinking and search."""
    streamed_content_accumulator = ""
    authoritative_final_content = ""
    authoritative_final_source_type = ""
    assistant_started = False

    try:
        for raw_item in _iter_stream_items(first_item, stream_gen):
            item = _normalize_stream_item(raw_item)
            item_type = item.get("type")

            if item_type == "final_content":
                final_text = str(item.get("text", "") or "").strip()
                if final_text:
                    authoritative_final_content = final_text
                    authoritative_final_source_type = str(
                        item.get("source_type", "") or ""
                    )
                continue

            # Lite mode: skip thinking and search events
            if item_type in ("thinking", "search"):
                continue

            if item_type != "content":
                continue

            chunk_text = item.get("text", "")
            if not chunk_text:
                continue

            streamed_content_accumulator += chunk_text
            if not assistant_started:
                assistant_started = True
                yield _build_stream_chunk(
                    response_id,
                    model_name,
                    role="assistant",
                    content=chunk_text,
                )
            else:
                yield _build_stream_chunk(response_id, model_name, content=chunk_text)
    except asyncio.CancelledError:
        logger.info(
            "Lite streaming cancelled by client",
            extra={"request_info": {"event": "lite_stream_cancelled"}},
        )
        raise
    except BaseException as exc:
        if _is_client_disconnect_error(exc):
            logger.info(
                "Lite streaming connection closed by client",
                extra={"request_info": {"event": "lite_stream_client_disconnected"}},
            )
            return
        logger.error(
            "Lite streaming interrupted",
            exc_info=True,
            extra={"request_info": {"event": "lite_stream_interrupted"}},
        )
        error_hint = "\n\n[Notion connection interrupted. Please try again in a moment.]"
        streamed_content_accumulator += error_hint
        if not assistant_started:
            assistant_started = True
            yield _build_stream_chunk(
                response_id,
                model_name,
                role="assistant",
                content=error_hint,
            )
        else:
            yield _build_stream_chunk(response_id, model_name, content=error_hint)
    finally:
        # Pick the best final reply
        final_reply, _ = _select_best_final_reply(
            streamed_content_accumulator,
            authoritative_final_content,
            authoritative_final_source_type,
        )

        # Emit any missing suffix
        missing_suffix = _compute_missing_suffix(
            streamed_content_accumulator, final_reply
        )
        if missing_suffix:
            if not assistant_started:
                assistant_started = True
                yield _build_stream_chunk(
                    response_id,
                    model_name,
                    role="assistant",
                    content=missing_suffix,
                )
            else:
                yield _build_stream_chunk(
                    response_id, model_name, content=missing_suffix
                )
            streamed_content_accumulator += missing_suffix
        elif final_reply != streamed_content_accumulator:
            # Diverged — use the authoritative final reply
            if not streamed_content_accumulator and final_reply:
                if not assistant_started:
                    assistant_started = True
                    yield _build_stream_chunk(
                        response_id,
                        model_name,
                        role="assistant",
                        content=final_reply,
                    )
                else:
                    yield _build_stream_chunk(
                        response_id, model_name, content=final_reply
                    )
                streamed_content_accumulator = final_reply

        yield _build_stream_chunk(response_id, model_name, finish_reason="stop")
        yield "data: [DONE]\n\n"


def _create_standard_stream_generator(
    response_id: str,
    model_name: str,
    first_item: Any,
    stream_gen: Iterable[Any],
    client_type: str = "",
) -> Generator[str, None, None]:
    """
    Standard mode stream generator using frontend-defined SSE event types.

    Frontend protocol:
    - thinking_chunk: incremental thinking fragment
    - thinking_replace: full thinking replacement
    - search_metadata: search results
    - choices[0].delta.content: body content

    For strict OpenAI clients (e.g. opencode), thinking uses delta.reasoning_content
    and search is injected as markdown into content (matching Heavy mode behavior),
    avoiding custom SSE fields that trigger strict validation while preserving results.
    """
    streamed_content_accumulator = ""
    streamed_thinking_accumulator = ""
    collected_search_sources = []
    collected_search_queries = []
    authoritative_final_content = ""
    authoritative_final_source_type = ""
    assistant_started = False
    is_web_client = client_type == "web"

    try:
        for raw_item in _iter_stream_items(first_item, stream_gen):
            item = _normalize_stream_item(raw_item)
            item_type = item.get("type")

            if item_type == "final_content":
                final_text = str(item.get("text", "") or "").strip()
                if final_text:
                    authoritative_final_content = final_text
                    authoritative_final_source_type = str(
                        item.get("source_type", "") or ""
                    )
                continue

            # Standard mode: handle thinking
            if item_type == "thinking":
                thinking_text = item.get("text", "")
                if thinking_text:
                    streamed_thinking_accumulator += thinking_text
                    if is_web_client:
                        # Web UI: use thinking_chunk frontend protocol
                        yield f"data: {json.dumps({'type': 'thinking_chunk', 'text': thinking_text}, ensure_ascii=False)}\n\n"
                    else:
                        # Strict OpenAI client: use reasoning_content; include role in first chunk
                        if not assistant_started:
                            assistant_started = True
                            yield _build_stream_chunk(
                                response_id,
                                model_name,
                                role="assistant",
                                thinking=thinking_text,
                            )
                        else:
                            yield _build_stream_chunk(
                                response_id, model_name, thinking=thinking_text
                            )
                continue

            # Standard mode: collect search events and emit at the end
            if item_type == "search":
                search_data = item.get("data", {})
                if isinstance(search_data, dict):
                    queries = search_data.get("queries", [])
                    sources = search_data.get("sources", [])

                    if queries:
                        collected_search_queries.extend(queries)
                    if sources:
                        collected_search_sources.extend(sources)
                continue

            if item_type != "content":
                continue

            chunk_text = item.get("text", "")
            if not chunk_text:
                continue

            streamed_content_accumulator += chunk_text

            # Emit standard OpenAI delta
            if not assistant_started:
                assistant_started = True
                yield _build_stream_chunk(
                    response_id,
                    model_name,
                    role="assistant",
                    content=chunk_text,
                )
            else:
                yield _build_stream_chunk(response_id, model_name, content=chunk_text)
    except asyncio.CancelledError:
        logger.info(
            "Standard streaming cancelled by client",
            extra={"request_info": {"event": "standard_stream_cancelled"}},
        )
        raise
    except BaseException as exc:
        if _is_client_disconnect_error(exc):
            logger.info(
                "Standard streaming connection closed by client",
                extra={
                    "request_info": {"event": "standard_stream_client_disconnected"}
                },
            )
            return
        logger.error(
            "Standard streaming interrupted",
            exc_info=True,
            extra={"request_info": {"event": "standard_stream_interrupted"}},
        )
        error_hint = "\n\n[Notion connection interrupted. Please try again in a moment.]"
        streamed_content_accumulator += error_hint
        if not assistant_started:
            assistant_started = True
            yield _build_stream_chunk(
                response_id,
                model_name,
                role="assistant",
                content=error_hint,
            )
        else:
            yield _build_stream_chunk(response_id, model_name, content=error_hint)
    finally:
        # Pick the best final reply
        final_reply, _ = _select_best_final_reply(
            streamed_content_accumulator,
            authoritative_final_content,
            authoritative_final_source_type,
        )

        # Emit any missing suffix
        missing_suffix = _compute_missing_suffix(
            streamed_content_accumulator, final_reply
        )
        if missing_suffix:
            if not assistant_started:
                assistant_started = True
                yield _build_stream_chunk(
                    response_id,
                    model_name,
                    role="assistant",
                    content=missing_suffix,
                )
            else:
                yield _build_stream_chunk(
                    response_id, model_name, content=missing_suffix
                )
            streamed_content_accumulator += missing_suffix
        elif final_reply != streamed_content_accumulator:
            # Diverged — use the authoritative final reply
            if not streamed_content_accumulator and final_reply:
                if not assistant_started:
                    assistant_started = True
                    yield _build_stream_chunk(
                        response_id,
                        model_name,
                        role="assistant",
                        content=final_reply,
                    )
                else:
                    yield _build_stream_chunk(
                        response_id, model_name, content=final_reply
                    )
                streamed_content_accumulator = final_reply

        # Emit collected search results
        if collected_search_sources or collected_search_queries:
            search_payload = {
                "queries": collected_search_queries,
                "sources": collected_search_sources,
            }
            if is_web_client:
                # Web UI: extended search_metadata with OpenAI chunk envelope
                yield _build_local_ui_chunk(
                    response_id,
                    model_name,
                    "search_metadata",
                    searches=search_payload,
                )
            else:
                # Strict clients: inject as markdown content to avoid losing results
                search_md = _format_search_results_md(search_payload)
                if search_md:
                    if not assistant_started:
                        assistant_started = True
                        yield _build_stream_chunk(
                            response_id,
                            model_name,
                            role="assistant",
                            content=search_md,
                        )
                    else:
                        yield _build_stream_chunk(
                            response_id, model_name, content=search_md
                        )

        yield _build_stream_chunk(response_id, model_name, finish_reason="stop")
        yield "data: [DONE]\n\n"


def _persist_round(
    manager,
    background_tasks: BackgroundTasks,
    conversation_id: str,
    user_prompt: str,
    assistant_reply: str,
    assistant_thinking: str = "",
) -> None:
    """
    Persist one conversation round and trigger async pre-compression.

    Pre-compression logic:
    - When round >= WINDOW_ROUNDS//2, compress rounds sliding out of the window
    - Uses BackgroundTasks to avoid blocking the current response
    """
    round_index = manager.persist_round(
        conversation_id,
        user_prompt,
        assistant_reply,
        assistant_thinking=assistant_thinking,
    )

    # Async pre-compression: compress rounds sliding out of the window early
    WINDOW_ROUNDS = 8  # must match conversation.py
    PRECOMPRESS_THRESHOLD = WINDOW_ROUNDS // 2  # start pre-compressing at round 4

    if round_index >= PRECOMPRESS_THRESHOLD:
        # Round that is sliding out of the active window
        round_to_compress = round_index - WINDOW_ROUNDS + 1
        if round_to_compress >= 0:
            background_tasks.add_task(
                compress_sliding_window_round,
                manager=manager,
                conversation_id=conversation_id,
                round_number=round_to_compress,
            )
            logger.info(
                "Triggered async pre-compression",
                extra={
                    "request_info": {
                        "event": "async_precompress_triggered",
                        "conversation_id": conversation_id,
                        "current_round": round_index,
                        "compress_round": round_to_compress,
                    }
                },
            )

    # Keep the original compression task as a safety fallback
    background_tasks.add_task(
        compress_round_if_needed,
        manager=manager,
        conversation_id=conversation_id,
    )


def _persist_history_messages(
    manager, conversation_id: str, history_messages: List[Tuple[str, str, str]]
) -> None:
    for role, content, thinking in history_messages:
        manager.add_message(conversation_id, role, content, thinking)


def _is_client_disconnect_error(exc: BaseException) -> bool:
    if isinstance(exc, asyncio.CancelledError):
        return True
    if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
        return True
    if isinstance(exc, OSError):
        return exc.errno in {32, 54, 104, 10053, 10054}
    return False


async def _handle_lite_request(
    request: Request,
    req_body: ChatCompletionRequest,
    response: Response,
) -> JSONResponse | StreamingResponse | ChatCompletionResponse:
    """Handle a Lite mode request (stateless, single-turn)."""
    pool = request.app.state.account_pool

    # Extract user prompt
    user_prompt = _prepare_messages_lite(req_body)

    # Validate model
    if not is_supported_model(req_body.model):
        available_models = list_available_models()
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model: '{req_body.model}'. Available models: {', '.join(available_models)}",
        )

    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    max_retries = max(3, len(pool.clients))

    for attempt in range(1, max_retries + 1):
        client = None
        try:
            client = pool.get_client()

            # Build Lite transcript (no conversation history)
            transcript = build_lite_transcript(user_prompt, req_body.model)

            # Call Notion API (no thread_id for Lite mode)
            stream_gen = client.stream_response(transcript, thread_id=None)
            first_item = next(stream_gen, None)

            if first_item is None:
                raise NotionUpstreamError(
                    "Notion upstream returned empty content.", retriable=True
                )

            # Streaming response
            if req_body.stream:
                stream_headers = {
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
                return StreamingResponse(
                    _create_lite_stream_generator(
                        response_id,
                        req_body.model,
                        first_item,
                        stream_gen,
                    ),
                    media_type="text/event-stream",
                    headers=stream_headers,
                )

            # Non-streaming response
            content_parts: list[str] = []
            authoritative_final_content = ""
            authoritative_final_source_type = ""

            for raw_item in _iter_stream_items(first_item, stream_gen):
                item = _normalize_stream_item(raw_item)
                item_type = item.get("type")

                if item_type == "final_content":
                    final_text = str(item.get("text", "") or "").strip()
                    if final_text:
                        authoritative_final_content = final_text
                        authoritative_final_source_type = str(
                            item.get("source_type", "") or ""
                        )
                    continue

                # Lite mode: skip thinking and search events
                if item_type in ("thinking", "search"):
                    continue

                if item_type != "content":
                    continue

                chunk_text = item.get("text", "")
                if chunk_text:
                    content_parts.append(chunk_text)

            full_text, _ = _select_best_final_reply(
                "".join(content_parts),
                authoritative_final_content,
                authoritative_final_source_type,
            )

            if not full_text.strip():
                raise NotionUpstreamError(
                    "Notion upstream returned empty content.", retriable=True
                )

            response_text = (
                full_text if full_text.strip() else "[assistant_no_visible_content]"
            )
            return ChatCompletionResponse(
                id=response_id,
                model=req_body.model,
                choices=[
                    ChatMessageResponseChoice(
                        message=ChatMessage(role="assistant", content=response_text)
                    )
                ],
            )

        except NotionUpstreamError as exc:
            if client is not None and exc.retriable:
                pool.mark_failed(client)
            logger.warning(
                "Lite mode: Notion upstream failed",
                extra={
                    "request_info": {
                        "event": "lite_notion_upstream_failed",
                        "attempt": attempt,
                        "max_retries": max_retries,
                        "status_code": exc.status_code,
                        "retriable": exc.retriable,
                        "response_excerpt": exc.response_excerpt,
                    }
                },
            )
            if attempt == max_retries or not exc.retriable:
                return _upstream_error_response(exc)
        except RuntimeError as exc:
            logger.error(
                "Lite mode: No available client in account pool",
                extra={
                    "request_info": {
                        "event": "lite_account_pool_unavailable",
                        "detail": str(exc),
                    }
                },
            )
            return _build_error_response(
                503,
                code="POOL_COOLING",
                message=str(exc),
                error_type="account_pool_cooling",
                suggestion="All accounts are temporarily cooling down. Please retry in a few seconds.",
            )
        except HTTPException:
            raise
        except Exception:
            if client is not None:
                pool.mark_failed(client)
            logger.error(
                "Lite mode: Unhandled error",
                exc_info=True,
                extra={
                    "request_info": {
                        "event": "lite_unhandled_exception",
                        "attempt": attempt,
                    }
                },
            )
            if attempt == max_retries:
                return _build_error_response(
                    500,
                    code="INTERNAL_ERROR",
                    message="Internal server error.",
                    error_type="internal_error",
                    suggestion="Please try again in a moment. If this persists, contact the administrator.",
                )

    return _build_error_response(
        503,
        code="RETRIES_EXHAUSTED",
        message="All retries exhausted.",
        error_type="upstream_error",
        suggestion="Notion service is temporarily unavailable. Please try again in a moment.",
    )


async def _handle_standard_request(
    request: Request,
    req_body: ChatCompletionRequest,
    response: Response,
) -> JSONResponse | StreamingResponse | ChatCompletionResponse:
    """
    Handle a Standard mode request (full context, thinking and search supported).

    Similar to Lite mode, but:
    1. Sends the full message history
    2. Preserves thinking output
    3. Preserves search result output
    """
    from app.conversation import build_standard_transcript

    pool = request.app.state.account_pool

    # Validate model
    if not is_supported_model(req_body.model):
        available_models = list_available_models()
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model: '{req_body.model}'. Available models: {', '.join(available_models)}",
        )

    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    max_retries = max(3, len(pool.clients))

    for attempt in range(1, max_retries + 1):
        client = None
        try:
            client = pool.get_client()

            # Build Standard transcript (full context)
            # Extract account info from client
            account = {
                "user_id": client.user_id,
                "space_id": client.space_id,
            }
            messages = [msg.dict() for msg in req_body.messages]
            transcript = build_standard_transcript(messages, req_body.model, account)

            # Call Notion API (no thread_id, let Notion manage threads)
            stream_gen = client.stream_response(transcript, thread_id=None)
            first_item = next(stream_gen, None)

            if first_item is None:
                raise NotionUpstreamError(
                    "Notion upstream returned empty content.", retriable=True
                )

            # Streaming response
            if req_body.stream:
                stream_headers = {
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
                client_type = request.headers.get("X-Client-Type", "").lower()
                return StreamingResponse(
                    _create_standard_stream_generator(
                        response_id,
                        req_body.model,
                        first_item,
                        stream_gen,
                        client_type=client_type,
                    ),
                    media_type="text/event-stream",
                    headers=stream_headers,
                )

            # Non-streaming response
            content_parts: list[str] = []
            thinking_parts: list[str] = []
            search_results: list[dict] = []
            authoritative_final_content = ""
            authoritative_final_source_type = ""

            for raw_item in _iter_stream_items(first_item, stream_gen):
                item = _normalize_stream_item(raw_item)
                item_type = item.get("type")

                if item_type == "final_content":
                    final_text = str(item.get("text", "") or "").strip()
                    if final_text:
                        authoritative_final_content = final_text
                        authoritative_final_source_type = str(
                            item.get("source_type", "") or ""
                        )
                    continue

                # Standard mode: handle thinking
                if item_type == "thinking":
                    thinking_text = item.get("text", "")
                    if thinking_text:
                        thinking_parts.append(thinking_text)
                    continue

                # Standard mode: handle search
                if item_type == "search":
                    search_data = item.get("data", {})
                    if search_data:
                        search_results.append(search_data)
                    continue

                if item_type != "content":
                    continue

                chunk_text = item.get("text", "")
                if chunk_text:
                    content_parts.append(chunk_text)

            full_text, _ = _select_best_final_reply(
                "".join(content_parts),
                authoritative_final_content,
                authoritative_final_source_type,
            )

            if not full_text.strip():
                raise NotionUpstreamError(
                    "Notion upstream returned empty content.", retriable=True
                )

            response_text = (
                full_text if full_text.strip() else "[assistant_no_visible_content]"
            )

            # Build response
            response_message = ChatMessage(role="assistant", content=response_text)

            # Attach thinking to extension field if present (frontend reads it)
            if thinking_parts:
                response_message.thinking = "".join(thinking_parts)

            # Build response object
            response_obj = ChatCompletionResponse(
                id=response_id,
                model=req_body.model,
                choices=[ChatMessageResponseChoice(message=response_message)],
            )

            # Attach search results to extension field if present (frontend reads it)
            if search_results:
                # Extract queries and sources
                all_queries = []
                all_sources = []
                for result in search_results:
                    if isinstance(result, dict):
                        all_queries.extend(result.get("queries", []))
                        all_sources.extend(result.get("sources", []))

                if all_queries or all_sources:
                    # Add to custom field
                    response_obj.search_metadata = {
                        "queries": all_queries,
                        "sources": all_sources,
                    }

            return response_obj

        except NotionUpstreamError as exc:
            if client is not None and exc.retriable:
                pool.mark_failed(client)
            logger.warning(
                "Standard mode: Notion upstream failed",
                extra={
                    "request_info": {
                        "event": "standard_notion_upstream_failed",
                        "attempt": attempt,
                        "max_retries": max_retries,
                        "status_code": exc.status_code,
                        "retriable": exc.retriable,
                        "response_excerpt": exc.response_excerpt,
                    }
                },
            )
            if attempt == max_retries or not exc.retriable:
                return _upstream_error_response(exc)
        except RuntimeError as exc:
            logger.error(
                "Standard mode: No available client in account pool",
                extra={
                    "request_info": {
                        "event": "standard_account_pool_unavailable",
                        "detail": str(exc),
                    }
                },
            )
            return _build_error_response(
                503,
                code="POOL_COOLING",
                message=str(exc),
                error_type="account_pool_cooling",
                suggestion="All accounts are temporarily cooling down. Please retry in a few seconds.",
            )
        except HTTPException:
            raise
        except Exception:
            if client is not None:
                pool.mark_failed(client)
            logger.error(
                "Standard mode: Unhandled error",
                exc_info=True,
                extra={
                    "request_info": {
                        "event": "standard_unhandled_exception",
                        "attempt": attempt,
                    }
                },
            )
            if attempt == max_retries:
                return _build_error_response(
                    500,
                    code="INTERNAL_ERROR",
                    message="Internal server error.",
                    error_type="internal_error",
                    suggestion="Please try again in a moment. If this persists, contact the administrator.",
                )

    return _build_error_response(
        503,
        code="RETRIES_EXHAUSTED",
        message="All retries exhausted.",
        error_type="upstream_error",
        suggestion="Notion service is temporarily unavailable. Please try again in a moment.",
    )


@router.post("/chat/completions", tags=["chat"])
async def create_chat_completion(
    request: Request,
    req_body: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    response: Response,
):
    """
    Create a chat completion request, strictly compatible with the OpenAI API.

    Rate limits:
    - Lite mode:     30/min (suited for single-turn Q&A)
    - Standard mode: 25/min (full context with thinking and search)
    - Heavy mode:    20/min (includes session management)
    """
    from app.config import is_standard_mode

    # Lite mode: single-turn, stateless
    if is_lite_mode():
        return await _handle_lite_request(request, req_body, response)

    # Standard mode: full context with thinking and search
    if is_standard_mode():
        return await _handle_standard_request(request, req_body, response)

    # Heavy mode: full session management
    pool = request.app.state.account_pool
    manager = request.app.state.conversation_manager

    user_prompt, history_messages, raw_user_prompt = _prepare_messages(req_body)
    recall_query = (
        _extract_recall_query(raw_user_prompt)
        if _contains_recall_intent(raw_user_prompt)
        else None
    )

    if not is_supported_model(req_body.model):
        available_models = list_available_models()
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model: '{req_body.model}'. Available models: {', '.join(available_models)}",
        )

    conversation_id = (
        req_body.conversation_id.strip() if req_body.conversation_id else ""
    )
    restore_history = False
    if not conversation_id:
        conversation_id = manager.new_conversation()
        restore_history = True
    elif not manager.conversation_exists(conversation_id):
        logger.warning(
            "Conversation id not found, creating a fresh conversation",
            extra={
                "request_info": {
                    "event": "conversation_id_not_found",
                    "provided_conversation_id": conversation_id,
                }
            },
        )
        conversation_id = manager.new_conversation()
        restore_history = True

    # Always persist history sent by the client to prevent context loss
    # even when conversation_id already exists.
    if history_messages:
        # Check if persistence is needed (avoid duplicates)
        with manager._get_conn() as conn:
            existing_count = manager._count_messages(conn, conversation_id)
            history_count = len(history_messages)

            # Only persist if the client sent more history than the DB already has.
            # This avoids duplicate persistence, ensures full history is saved,
            # and fixes the "sliding window missing AI replies" bug.
            if history_count > existing_count:
                _persist_history_messages(manager, conversation_id, history_messages)
                restored_user_count = sum(
                    1 for role, *_ in history_messages if role == "user"
                )
                restored_assistant_count = sum(
                    1 for role, *_ in history_messages if role == "assistant"
                )

                logger.info(
                    "Restored history into conversation",
                    extra={
                        "request_info": {
                            "event": "conversation_history_restored",
                            "conversation_id": conversation_id,
                            "restore_history_flag": restore_history,
                            "existing_count": existing_count,
                            "history_count": history_count,
                            "restored_total": len(history_messages),
                            "restored_user_count": restored_user_count,
                            "restored_assistant_count": restored_assistant_count,
                        }
                    },
                )

    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    max_retries = max(3, len(pool.clients))

    for attempt in range(1, max_retries + 1):
        client = None
        try:
            client = pool.get_client()
            transcript_payload = manager.get_transcript_payload(
                notion_client=client,
                conversation_id=conversation_id,
                new_prompt=user_prompt,
                model_name=req_body.model,
                recall_query=recall_query,
            )
            transcript = transcript_payload["transcript"]
            memory_degraded = bool(transcript_payload.get("memory_degraded"))
            memory_headers = {"X-Memory-Status": "degraded"} if memory_degraded else {}

            # Fetch or create thread_id for conversation context
            thread_id = manager.get_conversation_thread_id(conversation_id)

            # Detect mid-conversation model switches. Notion pins the model from config
            # to the server-side thread object. Reusing the same thread with a new model
            # causes Notion to silently use the original model. We must discard the old
            # thread so Notion creates a fresh one; our sliding window + summaries rebuild context.
            if thread_id:
                bound_model = manager.get_conversation_thread_model(conversation_id)
                # bound_model is None for legacy conversations (pre-binding tracking).
                # We cannot know what model the thread was bound to, so treat it as
                # a potential mismatch and discard it to avoid the old bug.
                if not bound_model or bound_model != req_body.model:
                    logger.info(
                        "Recreating Notion thread: model changed or legacy binding",
                        extra={
                            "request_info": {
                                "event": "thread_model_switched",
                                "conversation_id": conversation_id,
                                "old_model": bound_model,
                                "new_model": req_body.model,
                                "reason": "model_mismatch" if bound_model else "legacy_no_binding",
                            }
                        },
                    )
                    manager.clear_conversation_thread(conversation_id)
                    thread_id = None

            stream_gen = client.stream_response(transcript, thread_id=thread_id)
            first_item = next(stream_gen, None)

            # Save thread_id (new conversation or model just switched)
            if not thread_id and hasattr(client, "current_thread_id"):
                manager.set_conversation_thread_id(
                    conversation_id,
                    client.current_thread_id,
                    model_name=req_body.model,
                )

            if first_item is None:
                raise NotionUpstreamError(
                    "Notion upstream returned empty content.", retriable=True
                )

            def openai_stream_generator() -> Generator[str, None, None]:
                streamed_content_accumulator = ""
                thinking_accumulator = ""
                authoritative_final_content = ""
                authoritative_final_source_type = ""
                assistant_started = False
                pending_search_md = ""
                client_type = request.headers.get("X-Client-Type", "").lower()
                recent_thinking_buffer: list[str] = []

                try:
                    for raw_item in _iter_stream_items(first_item, stream_gen):
                        item = _normalize_stream_item(raw_item)
                        item_type = item.get("type")

                        if item_type == "search":
                            search_data = item.get("data")
                            if isinstance(search_data, dict) and search_data:
                                pending_search_md += _format_search_results_md(
                                    search_data
                                )
                                if client_type == "web":
                                    yield _build_local_ui_chunk(
                                        response_id,
                                        req_body.model,
                                        "search_metadata",
                                        searches=search_data,
                                    )
                            continue

                        if item_type == "final_content":
                            final_text = str(item.get("text", "") or "").strip()
                            if final_text:
                                authoritative_final_content = final_text
                                authoritative_final_source_type = str(
                                    item.get("source_type", "") or ""
                                )
                            continue

                        if item_type == "thinking":
                            thinking_text = item.get("text", "")
                            if thinking_text:
                                thinking_accumulator += thinking_text
                                # Track recent thinking for overlap detection
                                recent_thinking_buffer.append(thinking_text)
                                # Keep buffer manageable (max 40 recent chunks)
                                if len(recent_thinking_buffer) > 40:
                                    recent_thinking_buffer.pop(0)

                                if not assistant_started:
                                    assistant_started = True
                                    yield _build_stream_chunk(
                                        response_id,
                                        req_body.model,
                                        role="assistant",
                                        thinking=thinking_text,
                                    )
                                else:
                                    yield _build_stream_chunk(
                                        response_id,
                                        req_body.model,
                                        thinking=thinking_text,
                                    )
                            continue

                        if item_type != "content":
                            continue

                        chunk_text = item.get("text", "")
                        if not chunk_text and not pending_search_md:
                            continue

                        # Check if content overlaps with recent thinking (prevents thinking leakage)
                        if recent_thinking_buffer and chunk_text.strip():
                            combined_recent_thinking = "".join(recent_thinking_buffer)
                            chunk_normalized = chunk_text.strip()

                            # Use normalized text without spaces for robust comparison
                            combined_norm = re.sub(r"\s+", "", combined_recent_thinking)
                            chunk_norm = re.sub(r"\s+", "", chunk_normalized)

                            # Check for significant overlap - skip duplicate content
                            # We only skip if a sufficiently long chunk matches to avoid swallowing short common characters.
                            if (
                                chunk_norm
                                and len(chunk_norm) > 3
                                and (
                                    chunk_norm in combined_norm
                                    or (
                                        len(chunk_norm) > 10
                                        and chunk_norm[:10] in combined_norm
                                    )
                                )
                            ):
                                # Skip this chunk as it's likely duplicated thinking content
                                logger.debug(
                                    "Skipping duplicate content chunk that overlaps with thinking",
                                    extra={
                                        "request_info": {
                                            "event": "content_overlap_with_thinking",
                                            "chunk_length": len(chunk_text),
                                            "overlap_detected": True,
                                        }
                                    },
                                )
                                continue

                        # Prepend accumulated search markdown before first content chunk
                        if pending_search_md and client_type != "web":
                            chunk_text = pending_search_md + chunk_text

                        if pending_search_md:
                            pending_search_md = ""

                        streamed_content_accumulator += chunk_text
                        if not assistant_started:
                            assistant_started = True
                            yield _build_stream_chunk(
                                response_id,
                                req_body.model,
                                role="assistant",
                                content=chunk_text,
                            )
                        else:
                            yield _build_stream_chunk(
                                response_id, req_body.model, content=chunk_text
                            )
                except asyncio.CancelledError:
                    logger.info(
                        "Streaming response cancelled by downstream client",
                        extra={
                            "request_info": {
                                "event": "stream_cancelled_by_client",
                                "conversation_id": conversation_id,
                                "attempt": attempt,
                            }
                        },
                    )
                    raise
                except BaseException as exc:
                    if _is_client_disconnect_error(exc):
                        logger.info(
                            "Streaming connection closed by downstream client",
                            extra={
                                "request_info": {
                                    "event": "stream_client_disconnected",
                                    "conversation_id": conversation_id,
                                    "attempt": attempt,
                                }
                            },
                        )
                        return
                    if (
                        isinstance(exc, NotionUpstreamError)
                        and client is not None
                        and exc.retriable
                    ):
                        pool.mark_failed(client)
                    log_method = (
                        logger.warning
                        if isinstance(exc, NotionUpstreamError)
                        else logger.error
                    )
                    log_method(
                        "Streaming response interrupted",
                        exc_info=True,
                        extra={
                            "request_info": {
                                "event": "stream_interrupted",
                                "conversation_id": conversation_id,
                                "attempt": attempt,
                                "is_upstream_error": isinstance(
                                    exc, NotionUpstreamError
                                ),
                            }
                        },
                    )
                    error_hint = "\n\n[Notion connection interrupted. Please try again in a moment.]"
                    streamed_content_accumulator += error_hint
                    if not assistant_started:
                        assistant_started = True
                        yield _build_stream_chunk(
                            response_id,
                            req_body.model,
                            role="assistant",
                            content=error_hint,
                        )
                    else:
                        yield _build_stream_chunk(
                            response_id, req_body.model, content=error_hint
                        )
                finally:
                    final_reply, reply_decision = _select_best_final_reply(
                        streamed_content_accumulator,
                        authoritative_final_content,
                        authoritative_final_source_type,
                    )

                    missing_suffix = _compute_missing_suffix(
                        streamed_content_accumulator, final_reply
                    )
                    if missing_suffix:
                        suffix_to_emit = missing_suffix
                        if (
                            pending_search_md
                            and client_type != "web"
                            and not streamed_content_accumulator
                        ):
                            suffix_to_emit = pending_search_md + suffix_to_emit
                            pending_search_md = ""
                        if not assistant_started:
                            assistant_started = True
                            yield _build_stream_chunk(
                                response_id,
                                req_body.model,
                                role="assistant",
                                content=suffix_to_emit,
                            )
                        else:
                            yield _build_stream_chunk(
                                response_id, req_body.model, content=suffix_to_emit
                            )
                        streamed_content_accumulator += suffix_to_emit
                    elif final_reply != streamed_content_accumulator:
                        # Diverged bodies cannot be safely "patched" in plain OpenAI deltas.
                        # Web client supports replace event to keep rendered body aligned with persisted final reply.
                        if client_type == "web":
                            yield _build_local_ui_chunk(
                                response_id,
                                req_body.model,
                                "content_replace",
                                content=final_reply,
                                source_type=authoritative_final_source_type,
                                decision=reply_decision,
                            )
                            streamed_content_accumulator = final_reply
                        elif not streamed_content_accumulator and final_reply:
                            # Non-web fallback when nothing has been shown yet.
                            emit_text = final_reply
                            if pending_search_md and client_type != "web":
                                emit_text = pending_search_md + emit_text
                                pending_search_md = ""
                            if not assistant_started:
                                assistant_started = True
                                yield _build_stream_chunk(
                                    response_id,
                                    req_body.model,
                                    role="assistant",
                                    content=emit_text,
                                )
                            else:
                                yield _build_stream_chunk(
                                    response_id, req_body.model, content=emit_text
                                )
                            streamed_content_accumulator = final_reply

                    thinking_replacement = _build_thinking_replacement(
                        streamed_content_accumulator,
                        thinking_accumulator,
                        final_reply,
                        authoritative_final_source_type,
                    )
                    if client_type == "web" and thinking_replacement is not None:
                        yield _build_local_ui_chunk(
                            response_id,
                            req_body.model,
                            "thinking_replace",
                            thinking=thinking_replacement["thinking"],
                            decision=thinking_replacement["decision"],
                            overlap_ratio=thinking_replacement["overlap_ratio"],
                            source_type=thinking_replacement["source_type"],
                            reply_decision=reply_decision,
                        )

                    persisted_thinking = (
                        str(thinking_replacement["thinking"])
                        if thinking_replacement is not None
                        else thinking_accumulator
                    )
                    if final_reply.strip() or persisted_thinking.strip():
                        try:
                            _persist_round(
                                manager,
                                background_tasks,
                                conversation_id,
                                user_prompt,
                                final_reply,
                                persisted_thinking,
                            )
                        except Exception:
                            logger.error(
                                "Failed to persist conversation round",
                                exc_info=True,
                                extra={
                                    "request_info": {
                                        "event": "conversation_persist_failed",
                                        "conversation_id": conversation_id,
                                    }
                                },
                            )
                    yield _build_stream_chunk(
                        response_id, req_body.model, finish_reason="stop"
                    )
                    yield "data: [DONE]\n\n"

            if req_body.stream:
                stream_headers = {
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "X-Conversation-Id": conversation_id,
                    **memory_headers,
                }
                return StreamingResponse(
                    openai_stream_generator(),
                    media_type="text/event-stream",
                    headers=stream_headers,
                )

            content_parts: list[str] = []
            thinking_parts: list[str] = []
            authoritative_final_content = ""
            authoritative_final_source_type = ""
            for raw_item in _iter_stream_items(first_item, stream_gen):
                item = _normalize_stream_item(raw_item)
                item_type = item.get("type")
                if item_type == "final_content":
                    final_text = str(item.get("text", "") or "").strip()
                    if final_text:
                        authoritative_final_content = final_text
                        authoritative_final_source_type = str(
                            item.get("source_type", "") or ""
                        )
                    continue
                if item_type == "thinking":
                    thinking_text = str(item.get("text", "") or "")
                    if thinking_text:
                        thinking_parts.append(thinking_text)
                    continue
                if item_type != "content":
                    continue
                chunk_text = item.get("text", "")
                if chunk_text:
                    content_parts.append(chunk_text)

            full_text, _ = _select_best_final_reply(
                "".join(content_parts),
                authoritative_final_content,
                authoritative_final_source_type,
            )
            merged_thinking = "".join(thinking_parts).strip()
            if not full_text.strip() and not merged_thinking:
                raise NotionUpstreamError(
                    "Notion upstream returned empty content.", retriable=True
                )

            _persist_round(
                manager,
                background_tasks,
                conversation_id,
                user_prompt,
                full_text,
                merged_thinking,
            )
            response.headers["X-Conversation-Id"] = conversation_id
            if memory_degraded:
                response.headers["X-Memory-Status"] = "degraded"

            response_text = (
                full_text if full_text.strip() else "[assistant_no_visible_content]"
            )
            return ChatCompletionResponse(
                id=response_id,
                model=req_body.model,
                choices=[
                    ChatMessageResponseChoice(
                        message=ChatMessage(role="assistant", content=response_text)
                    )
                ],
            )
        except NotionUpstreamError as exc:
            if client is not None and exc.retriable:
                pool.mark_failed(client)
            logger.warning(
                "Notion upstream failed",
                extra={
                    "request_info": {
                        "event": "notion_upstream_failed",
                        "attempt": attempt,
                        "max_retries": max_retries,
                        "conversation_id": conversation_id,
                        "status_code": exc.status_code,
                        "retriable": exc.retriable,
                        "response_excerpt": exc.response_excerpt,
                    }
                },
            )
            if attempt == max_retries or not exc.retriable:
                return _upstream_error_response(exc)
        except RuntimeError as exc:
            logger.error(
                "No available client in account pool",
                extra={
                    "request_info": {
                        "event": "account_pool_unavailable",
                        "detail": str(exc),
                    }
                },
            )
            return _build_error_response(
                503,
                code="POOL_COOLING",
                message=str(exc),
                error_type="account_pool_cooling",
                suggestion="All accounts are temporarily cooling down. Please retry in a few seconds.",
            )
        except HTTPException:
            raise
        except Exception:
            if client is not None:
                pool.mark_failed(client)
            logger.error(
                "Unhandled chat completion error",
                exc_info=True,
                extra={
                    "request_info": {
                        "event": "chat_completion_unhandled_exception",
                        "attempt": attempt,
                        "conversation_id": conversation_id,
                    }
                },
            )
            if attempt == max_retries:
                return _build_error_response(
                    500,
                    code="INTERNAL_ERROR",
                    message="Internal server error.",
                    error_type="internal_error",
                    suggestion="Please try again in a moment. If this persists, contact the administrator.",
                )

    return _build_error_response(
        503,
        code="RETRIES_EXHAUSTED",
        message="All retries exhausted.",
        error_type="upstream_error",
        suggestion="Notion service is temporarily unavailable. Please try again in a moment.",
    )


@router.delete("/conversations/{conversation_id}", tags=["chat"])
async def delete_conversation(conversation_id: str, request: Request):
    manager = request.app.state.conversation_manager
    deleted = manager.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"id": conversation_id, "deleted": True}

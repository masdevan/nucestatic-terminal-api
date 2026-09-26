import json
import queue
import threading
import urllib.error
import urllib.request
import uuid
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from typing import Any
from app.api.controllers.auth import require_user
from app.api.utils.dry_run import is_dry_run
from app.api.utils.security import decrypt_api_key

router = APIRouter()


class ChatRequest(BaseModel):
    messages: list
    session_id: str | None = None
    tools: list | None = None
    tool_choice: Any | None = None


def resolve_root(base_url: str) -> str:
    root = base_url.strip().rstrip("/")
    for suffix in ("/v1/chat/completions", "/v1/responses", "/chat/completions", "/responses", "/v1"):
        if root.endswith(suffix):
            return root[: -len(suffix)]
    return root


class ProviderFailure(Exception):
    pass


def open_chat(root: str, model: str, messages: list, headers: dict, tools: list | None, tool_choice: Any | None):
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True, "stream_options": {"include_usage": True}}
    if tools is not None:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice or "auto"
    return urllib.request.urlopen(
        urllib.request.Request(f"{root}/v1/chat/completions", data=json.dumps(payload).encode(), headers=headers),
        timeout=120
    )


def to_responses_input(messages: list) -> list:
    items = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "system":
            items.append({"role": "system", "content": m.get("content", "")})
        elif role == "user":
            items.append({"role": "user", "content": m.get("content", "")})
        elif role == "assistant":
            if m.get("content"):
                items.append({"role": "assistant", "content": m.get("content")})
            for tc in m.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                items.append({
                    "type": "function_call",
                    "call_id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", "{}")
                })
        elif role == "tool":
            items.append({
                "type": "function_call_output",
                "call_id": m.get("tool_call_id", ""),
                "output": m.get("content", "")
            })
    return items


def to_responses_tools(tools: list | None) -> list:
    out = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        fn = t.get("function") or {}
        if fn.get("name"):
            out.append({
                "type": "function",
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {"type": "object", "properties": {}})
            })
    return out


def open_responses(root: str, model: str, messages: list, headers: dict, tools: list | None, tool_choice: Any | None):
    body: dict[str, Any] = {"model": model, "input": to_responses_input(messages), "stream": True}
    if tools is not None:
        body["tools"] = to_responses_tools(tools)
        body["tool_choice"] = tool_choice or "auto"
    return urllib.request.urlopen(
        urllib.request.Request(f"{root}/v1/responses", data=json.dumps(body).encode(), headers=headers),
        timeout=120
    )


def emit(obj: dict) -> bytes:
    return ("data: " + json.dumps(obj) + "\n\n").encode()


def emit_call(index: int, call_id: str, name: str, args: str) -> bytes:
    return emit({"choices": [{"index": 0, "delta": {"tool_calls": [{
        "index": index,
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": args}
    }]}}]})


def synth_complete(obj: dict):
    index = 0
    for item in obj.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for part in item.get("content") or []:
                text = part if isinstance(part, str) else part.get("text", "") if isinstance(part, dict) else ""
                if text:
                    yield emit({"choices": [{"index": 0, "delta": {"content": text}}]})
        elif item.get("type") == "function_call":
            yield emit_call(index, item.get("call_id", ""), item.get("name", ""), item.get("arguments", "{}"))
            index += 1


def translate_responses_stream(upstream):
    pending: dict[int, dict] = {}
    saw_data = False
    try:
        buf = b""
        while True:
            chunk = upstream.read(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                raw = raw.strip()
                if not raw.startswith(b"data:"):
                    continue
                saw_data = True
                data = raw[5:].strip()
                if data == b"[DONE]":
                    continue
                try:
                    event = json.loads(data.decode())
                except ValueError:
                    continue
                etype = event.get("type", "")
                if etype == "response.output_text.delta":
                    delta = event.get("delta", "")
                    if delta:
                        yield emit({"choices": [{"index": 0, "delta": {"content": delta}}]})
                elif etype == "response.reasoning_summary_text.delta":
                    delta = event.get("delta", "")
                    if delta:
                        yield emit({"choices": [{"index": 0, "delta": {"reasoning_content": delta}}]})
                elif etype == "response.output_item.added":
                    item = event.get("item") or {}
                    if item.get("type") == "function_call":
                        index = event.get("output_index", 0)
                        pending[index] = {"call_id": item.get("call_id", ""), "name": item.get("name", ""), "args": ""}
                elif etype == "response.function_call_arguments.delta":
                    index = event.get("output_index", 0)
                    slot = pending.setdefault(index, {"call_id": "", "name": "", "args": ""})
                    slot["args"] += event.get("delta", "")
                elif etype == "response.output_item.done":
                    item = event.get("item") or {}
                    if item.get("type") == "function_call":
                        index = event.get("output_index", 0)
                        slot = pending.pop(index, {"call_id": "", "name": "", "args": ""})
                        yield emit_call(
                            index,
                            item.get("call_id", "") or slot["call_id"],
                            item.get("name", "") or slot["name"],
                            item.get("arguments", "") or slot["args"]
                        )
                elif etype == "response.completed":
                    usage = (event.get("response") or {}).get("usage") or {}
                    if isinstance(usage, dict) and usage:
                        yield emit({"usage": {
                            "prompt_tokens": usage.get("input_tokens", 0),
                            "completion_tokens": usage.get("output_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                            "cached_tokens": ((usage.get("input_tokens_details") or {}).get("cached_tokens", 0))
                        }})
                    for index, slot in pending.items():
                        if slot["name"]:
                            yield emit_call(index, slot["call_id"], slot["name"], slot["args"])
                    pending.clear()
        for index, slot in pending.items():
            if slot["name"]:
                yield emit_call(index, slot["call_id"], slot["name"], slot["args"])
        if not saw_data and buf.strip():
            try:
                obj = json.loads(buf.decode())
            except ValueError:
                obj = None
            if isinstance(obj, dict) and obj.get("object") == "response":
                yield from synth_complete(obj)
        yield b"data: [DONE]\n\n"
    finally:
        upstream.close()


def passthrough(upstream):
    try:
        while True:
            chunk = upstream.read(4096)
            if not chunk:
                break
            yield chunk
    finally:
        upstream.close()


KEEPALIVE_SECONDS = 10
STREAM_QUEUE_SIZE = 256


class StreamFailure:
    def __init__(self, message: str):
        self.message = message


def open_upstream_generator(root: str, model: str, messages: list, headers: dict, tools: list | None, tool_choice: Any | None):
    chat_failure = ""
    try:
        upstream = open_chat(root, model, messages, headers, tools, tool_choice)
    except urllib.error.HTTPError as chat_err:
        if chat_err.code in (401, 402, 403):
            body = chat_err.read().decode(errors="ignore")[:500]
            raise ProviderFailure(f"Provider {chat_err.code}: {body or chat_err.reason}")
        chat_failure = f"chat={chat_err.code}: {chat_err.read().decode(errors='ignore')[:300] or chat_err.reason}"
    except urllib.error.URLError as chat_url_err:
        chat_failure = f"chat=unreachable: {chat_url_err.reason}"
    else:
        yield from passthrough(upstream)
        return
    try:
        upstream = open_responses(root, model, messages, headers, tools, tool_choice)
    except urllib.error.HTTPError as resp_err:
        body = resp_err.read().decode(errors="ignore")[:300]
        detail = f"Provider responses={resp_err.code}: {body or resp_err.reason}"
        if chat_failure:
            detail = f"Provider {chat_failure} / responses={resp_err.code}: {body or resp_err.reason}"
        raise ProviderFailure(detail)
    except urllib.error.URLError as url_err:
        detail = f"Cannot reach provider: {url_err.reason}"
        if chat_failure:
            detail = f"Provider {chat_failure} / responses=unreachable: {url_err.reason}"
        raise ProviderFailure(detail)
    yield from translate_responses_stream(upstream)


def pump_stream(stream, out: queue.Queue, stop: threading.Event) -> None:
    try:
        for chunk in stream:
            while not stop.is_set():
                try:
                    out.put(chunk, timeout=0.5)
                    break
                except queue.Full:
                    continue
            if stop.is_set():
                break
    except Exception as error:
        try:
            out.put(StreamFailure(str(error) or error.__class__.__name__), timeout=1)
        except queue.Full:
            pass
    finally:
        try:
            out.put(None, timeout=1)
        except queue.Full:
            pass


def stream_with_keepalive(stream):
    out: queue.Queue = queue.Queue(maxsize=STREAM_QUEUE_SIZE)
    stop = threading.Event()
    worker = threading.Thread(target=pump_stream, args=(stream, out, stop), daemon=True)
    worker.start()
    try:
        while True:
            try:
                item = out.get(timeout=KEEPALIVE_SECONDS)
            except queue.Empty:
                yield b": keepalive\n\n"
                continue
            if item is None:
                break
            if isinstance(item, StreamFailure):
                yield emit({"error": item.message})
                break
            yield item
        yield b"data: [DONE]\n\n"
    finally:
        stop.set()
        try:
            stream.close()
        except Exception:
            pass


@router.post("")
def chat(req: ChatRequest, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        if not req.messages:
            raise HTTPException(status_code=422, detail="Messages required")
        setting = db.execute(
            text("SELECT api_key, model, base_url FROM opencode_settings WHERE user_id = :user_id AND active = 1"),
            {"user_id": row[0]}
        ).fetchone()
        if not setting:
            raise HTTPException(status_code=404, detail="No active API key")
        if is_dry_run():
            return StreamingResponse(
                iter([emit({"choices": [{"index": 0, "delta": {"content": "dry run"}}]}), b"data: [DONE]\n\n"]),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            )
        session_id = req.session_id.strip() if req.session_id else ""
        if not session_id:
            session_id = uuid.uuid4().hex
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {decrypt_api_key(setting[0])}",
            "User-Agent": "nucestatic-terminal/1.0",
            "x-opencode-session": session_id
        }
        root = resolve_root(setting[2])
        stream = open_upstream_generator(
            root, setting[1], req.messages, headers, req.tools, req.tool_choice
        )
        return StreamingResponse(
            stream_with_keepalive(stream),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )
    finally:
        db.close()

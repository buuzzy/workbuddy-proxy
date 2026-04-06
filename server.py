"""
WorkBuddy → OpenAI-compatible reverse proxy.

Accepts standard OpenAI API requests and forwards them to WorkBuddy's
/v2/chat/completions endpoint with the required authentication headers.

All user-specific values (user_id, enterprise_id, domain) are automatically
extracted from the JWT token — no manual configuration required.

Usage:
    python server.py                                        # auto-extract via CDP
    WB_TOKEN=<jwt> WB_REFRESH_TOKEN=<jwt> python server.py  # manual token
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import httpx
import jwt
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("wb-proxy")

BASE_DIR = Path(__file__).parent
TOKEN_FILE = BASE_DIR / "data" / "token.json"

PROXY_PORT = int(os.getenv("PROXY_PORT", "19090"))
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "wb-proxy-key")
WB_API_BASE = os.getenv("WB_API_BASE", "https://copilot.tencent.com")
CDP_URL = os.getenv("CDP_URL", "http://127.0.0.1:9222")


def _detect_wb_version() -> str:
    """Auto-detect genieVersion from local WorkBuddy installation."""
    candidates = [
        Path("/Applications/WorkBuddy.app/Contents/Resources/app/product.json"),
        Path(os.path.expandvars(
            r"%LOCALAPPDATA%\Programs\WorkBuddy\resources\app\product.json"
        )),
    ]
    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            v = data.get("genieVersion", "")
            if v:
                return v
        except Exception:
            continue
    return ""


WB_VERSION = os.getenv("WB_VERSION", "") or _detect_wb_version() or "4.8.1"

HEADERS_TEMPLATE = {
    "X-IDE-Type": "CodeBuddyIDE",
    "X-IDE-Name": "CodeBuddyIDE",
    "X-IDE-Version": WB_VERSION,
    "X-Product-Version": WB_VERSION,
    "X-Env-ID": "production",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": f"CodeBuddyIDE/{WB_VERSION} coding-copilot/{WB_VERSION}",
}


def _parse_jwt_claims(token: str) -> dict:
    """Extract user_id, enterprise_id and domain from JWT without verification."""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("sub", "")

        iss = payload.get("iss", "")
        # iss format: https://<domain>/auth/realms/sso-<enterprise_id>
        enterprise_id = ""
        m = re.search(r"/sso-([^/]+)$", iss)
        if m:
            enterprise_id = m.group(1)

        domain = ""
        m2 = re.match(r"https?://([^/]+)", iss)
        if m2:
            domain = m2.group(1)

        return {"user_id": user_id, "enterprise_id": enterprise_id, "domain": domain}
    except Exception:
        return {"user_id": "", "enterprise_id": "", "domain": ""}


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------
class TokenManager:
    def __init__(self):
        self.access_token: str = ""
        self.refresh_token: str = ""
        self.user_id: str = ""
        self.enterprise_id: str = ""
        self.domain: str = ""
        self.department_info: str = ""
        self._lock = asyncio.Lock()

    async def init(self):
        self.access_token = os.getenv("WB_TOKEN", "")
        self.refresh_token = os.getenv("WB_REFRESH_TOKEN", "")

        if not self.access_token:
            self._load_from_file()

        if not self.access_token:
            await self._extract_from_cdp()

        if self.access_token:
            self._apply_claims()
            self._log_token_info()
            self._save_to_file()

    def _apply_claims(self):
        claims = _parse_jwt_claims(self.access_token)
        self.user_id = os.getenv("WB_USER_ID", "") or claims["user_id"]
        self.enterprise_id = os.getenv("WB_ENTERPRISE_ID", "") or claims["enterprise_id"]
        self.domain = os.getenv("WB_DOMAIN", "") or claims["domain"]
        log.info(f"User: {self.user_id[:8]}..., Enterprise: {self.enterprise_id}, Domain: {self.domain}")

    def _load_from_file(self):
        if TOKEN_FILE.exists():
            try:
                data = json.loads(TOKEN_FILE.read_text())
                self.access_token = data.get("access_token", "")
                self.refresh_token = data.get("refresh_token", "")
                if self.access_token:
                    log.info("Token loaded from file")
            except Exception:
                pass

    def _save_to_file(self):
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(json.dumps({
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2))

    async def get_token(self) -> str:
        if self._is_expired():
            await self.refresh()
        return self.access_token

    def _is_expired(self) -> bool:
        if not self.access_token:
            return True
        try:
            payload = jwt.decode(self.access_token, options={"verify_signature": False})
            return time.time() > (payload.get("exp", 0) - 300)
        except Exception:
            return False

    def _log_token_info(self):
        try:
            payload = jwt.decode(self.access_token, options={"verify_signature": False})
            hours = (payload.get("exp", 0) - time.time()) / 3600
            log.info(f"Token valid, expires in {hours:.1f}h")
        except Exception:
            log.warning("Could not decode token")

    async def refresh(self):
        async with self._lock:
            if not self._is_expired():
                return
            if self.refresh_token:
                await self._refresh_via_api()
            else:
                await self._extract_from_cdp()

    async def _refresh_via_api(self):
        log.info("Refreshing token via API...")
        headers = {
            **HEADERS_TEMPLATE,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "X-Refresh-Token": self.refresh_token,
            "X-Auth-Refresh-Source": "plugin",
            "X-Domain": self.domain,
            "X-User-Id": self.user_id,
            "X-Enterprise-Id": self.enterprise_id,
            "X-Tenant-Id": self.enterprise_id,
            "X-Request-ID": uuid.uuid4().hex,
            "X-Request-Trace-Id": str(uuid.uuid4()),
        }
        if self.department_info:
            headers["X-Department-Info"] = self.department_info
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(
                f"{WB_API_BASE}/v2/plugin/auth/token/refresh",
                headers=headers,
                json={},
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 0 and data.get("data", {}).get("accessToken"):
                self.access_token = data["data"]["accessToken"]
                if data["data"].get("refreshToken"):
                    self.refresh_token = data["data"]["refreshToken"]
                self._apply_claims()
                log.info("Token refreshed successfully via API")
                self._log_token_info()
                self._save_to_file()
            else:
                log.error(f"Token refresh failed: {data}")
                await self._extract_from_cdp()

    async def _extract_from_cdp(self):
        log.info(f"Extracting token from WorkBuddy via CDP ({CDP_URL})...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{CDP_URL}/json", timeout=5)
                targets = resp.json()

            ws_url = None
            for t in targets:
                if t.get("type") == "page" and "workbench" in t.get("url", ""):
                    ws_url = t.get("webSocketDebuggerUrl")
                    break
            if not ws_url:
                for t in targets:
                    if t.get("type") == "page":
                        ws_url = t.get("webSocketDebuggerUrl")
                        break
            if not ws_url:
                log.error("No CDP target found")
                return

            import websockets

            async with websockets.connect(ws_url) as ws:
                cmd = {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """
                            (async () => {
                                try {
                                    const s = await window.vscode.ipcRenderer.invoke(
                                        'vscode:genie:auth:getSession'
                                    );
                                    return JSON.stringify(s);
                                } catch(e) {
                                    return JSON.stringify({error: e.message});
                                }
                            })()
                        """,
                        "awaitPromise": True,
                        "returnByValue": True,
                    },
                }
                await ws.send(json.dumps(cmd))
                result = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))

                value = result.get("result", {}).get("result", {}).get("value", "")
                if value:
                    session = json.loads(value)
                    auth = session.get("auth", session)
                    if auth.get("accessToken"):
                        self.access_token = auth["accessToken"]
                        self.refresh_token = auth.get("refreshToken", "")
                        account = session.get("account", {})
                        if isinstance(account, dict):
                            self.department_info = account.get("departmentFullName", "")
                        self._apply_claims()
                        log.info("Token extracted from CDP successfully")
                        self._log_token_info()
                        self._save_to_file()
                    elif session.get("error"):
                        log.error(f"CDP extraction error: {session['error']}")

        except ImportError:
            log.warning("websockets not installed — run: pip install websockets")
        except Exception as e:
            log.error(f"CDP extraction failed: {e}")


token_mgr = TokenManager()


# ---------------------------------------------------------------------------
# Available models
# ---------------------------------------------------------------------------
MODELS = [
    # DeepSeek
    {"id": "deepseek-r1", "name": "DeepSeek-R1"},
    {"id": "deepseek-v3", "name": "DeepSeek-V3"},
    {"id": "deepseek-v3.2", "name": "DeepSeek-V3.2"},
    {"id": "deepseek-v3-1", "name": "DeepSeek-V3.1"},
    {"id": "deepseek-v3-0324", "name": "DeepSeek-V3-0324"},
    {"id": "deepseek-v3-1-volc", "name": "DeepSeek-V3-1-Terminus"},
    {"id": "deepseek-v3-0324-lkeap", "name": "DeepSeek-V3-0324-LKEAP"},
    {"id": "deepseek-r1-0528-lkeap", "name": "DeepSeek-R1-0528-LKEAP"},
    {"id": "deepseek-v3-2-volc-ioa", "name": "DeepSeek-V3-2-Volc"},
    # GPT (5.1–5.4 removed: HTTP 400 on WorkBuddy backend)
    # Claude
    {"id": "claude-4.5", "name": "Claude-Sonnet-4.5"},
    {"id": "claude-opus-4.5", "name": "Claude-Opus-4.5"},
    {"id": "claude-opus-4.6", "name": "Claude-Opus-4.6"},
    {"id": "claude-opus-4.6-1m", "name": "Claude-Opus-4.6 (1M context)"},
    {"id": "claude-sonnet-4.6", "name": "Claude-Sonnet-4.6"},
    {"id": "claude-sonnet-4.6-1m", "name": "Claude-Sonnet-4.6 (1M context)"},
    {"id": "claude-haiku-4.5", "name": "Claude-Haiku-4.5"},
    # Gemini (3.0-flash removed: returns empty responses)
    {"id": "gemini-3.0-pro", "name": "Gemini-3.0-Pro"},
    {"id": "gemini-3.1-flash-lite", "name": "Gemini-3.1-Flash-Lite"},
    # GLM
    {"id": "glm-4.6", "name": "GLM-4.6"},
    {"id": "glm-4.7", "name": "GLM-4.7"},
    {"id": "glm-4.7-ioa", "name": "GLM-4.7-IOA"},
    {"id": "glm-5.0-ioa", "name": "GLM-5.0"},
    {"id": "glm-5.0-turbo-ioa", "name": "GLM-5.0-Turbo"},
    {"id": "glm-5v-turbo", "name": "GLM-5v-Turbo"},
    {"id": "glm-5v-turbo-ioa", "name": "GLM-5v-Turbo-IOA"},
    # Hunyuan
    {"id": "hunyuan-2.0-instruct", "name": "Hunyuan-2.0-Instruct"},
    {"id": "hunyuan-2.0-instruct-ioa", "name": "Hunyuan-2.0-Instruct-IOA"},
    {"id": "hunyuan-2.0-thinking-ioa", "name": "Hunyuan-2.0-Thinking"},
    # Kimi
    {"id": "kimi-k2.5-ioa", "name": "Kimi-K2.5"},
    # Default
    {"id": "codewise-default-model-v2", "name": "Default (Codewise)"},
]


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    await token_mgr.init()
    yield


app = FastAPI(title="WorkBuddy Proxy", lifespan=lifespan)


def _verify_api_key(request: Request):
    auth = request.headers.get("Authorization", "")
    key = auth.replace("Bearer ", "").strip()
    if key != PROXY_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _build_headers(access_token: str) -> dict:
    headers = {
        **HEADERS_TEMPLATE,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {access_token}",
        "X-User-Id": token_mgr.user_id,
        "X-Enterprise-Id": token_mgr.enterprise_id,
        "X-Tenant-Id": token_mgr.enterprise_id,
        "X-Domain": token_mgr.domain,
        "X-Request-ID": uuid.uuid4().hex,
        "X-Request-Trace-Id": str(uuid.uuid4()),
    }
    if token_mgr.department_info:
        headers["X-Department-Info"] = token_mgr.department_info
    return headers


@app.get("/v1/models")
async def list_models(request: Request):
    _verify_api_key(request)
    return {
        "object": "list",
        "data": [
            {
                "id": m["id"],
                "object": "model",
                "created": 1700000000,
                "owned_by": "workbuddy",
                "name": m["name"],
            }
            for m in MODELS
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    _verify_api_key(request)

    body = await request.json()
    model = body.get("model", "deepseek-v3")
    stream = body.get("stream", False)

    wb_body = {
        "model": model,
        "messages": body.get("messages", []),
        "stream": True,
    }
    for key in ("temperature", "max_tokens", "top_p", "stop",
                "presence_penalty", "frequency_penalty"):
        if key in body:
            wb_body[key] = body[key]

    access_token = await token_mgr.get_token()
    if not access_token:
        raise HTTPException(status_code=503, detail="No valid WorkBuddy token")

    headers = _build_headers(access_token)
    url = f"{WB_API_BASE}/v2/chat/completions"

    if stream:
        return StreamingResponse(
            _stream_response(url, headers, wb_body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return await _non_stream_response(url, headers, wb_body)


async def _stream_response(
    url: str, headers: dict, body: dict
) -> AsyncGenerator[str, None]:
    async with httpx.AsyncClient(verify=False, timeout=120) as client:
        try:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code == 401:
                    log.warning("Got 401, refreshing token...")
                    await token_mgr.refresh()
                    yield 'data: {"error":"Token expired, please retry"}\n\n'
                    return

                if resp.status_code != 200:
                    error_body = await resp.aread()
                    log.error(f"Upstream error {resp.status_code}: {error_body.decode()}")
                    yield f"data: {json.dumps({'error': error_body.decode()})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield line + "\n\n"
                    elif line.strip():
                        yield f"data: {line}\n\n"

        except httpx.ReadTimeout:
            log.error("Upstream read timeout")
            yield 'data: {"error":"upstream timeout"}\n\n'
            yield "data: [DONE]\n\n"


async def _non_stream_response(url: str, headers: dict, body: dict) -> JSONResponse:
    collected_content = ""
    model = body.get("model", "unknown")
    usage = {}

    async with httpx.AsyncClient(verify=False, timeout=120) as client:
        async with client.stream("POST", url, headers=headers, json=body) as resp:
            if resp.status_code != 200:
                error_body = await resp.aread()
                raise HTTPException(status_code=resp.status_code,
                                    detail=error_body.decode())

            async for line in resp.aiter_lines():
                text = line.removeprefix("data: ").strip()
                if not text or text == "[DONE]":
                    continue
                try:
                    chunk = json.loads(text)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    collected_content += delta.get("content", "")
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    model = chunk.get("model", model)
                except (json.JSONDecodeError, IndexError):
                    pass

    return JSONResponse({
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": collected_content},
            "finish_reason": "stop",
        }],
        "usage": usage,
    })


@app.get("/health")
async def health():
    has_token = bool(token_mgr.access_token)
    expired = token_mgr._is_expired()
    return {"status": "ok" if has_token and not expired else "degraded",
            "has_token": has_token, "expired": expired}


if __name__ == "__main__":
    log.info(f"Starting WorkBuddy proxy on port {PROXY_PORT}")
    log.info(f"WB version: {WB_VERSION}")
    log.info(f"API key: {PROXY_API_KEY}")
    log.info(f"Upstream: {WB_API_BASE}")
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT, log_level="info")

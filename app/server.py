import time
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
from app.config import ACCOUNTS, API_KEY, ALLOWED_ORIGINS, is_lite_mode, is_standard_mode
from app.account_pool import AccountPool
from app.conversation import ConversationManager
from app.api.chat import router as chat_router
from app.api.models import router as models_router
from app.logger import logger
from app.limiter import limiter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize state on startup
    app.state.account_pool = AccountPool(ACCOUNTS)

    # Determine run mode
    if is_lite_mode():
        mode = "lite"
        logger.info("Service starting up in LITE mode", extra={"request_info": {"event": "startup", "accounts": len(ACCOUNTS), "mode": "lite"}})
    elif is_standard_mode():
        mode = "standard"
        logger.info("Service starting up in STANDARD mode", extra={"request_info": {"event": "startup", "accounts": len(ACCOUNTS), "mode": "standard"}})
    else:
        mode = "heavy"
        app.state.conversation_manager = ConversationManager()
        logger.info("Service starting up in HEAVY mode", extra={"request_info": {"event": "startup", "accounts": len(ACCOUNTS), "mode": "heavy"}})

    app.state.start_time = time.time()
    yield
    # Cleanup on shutdown
    logger.info("Service shutting down", extra={"request_info": {"event": "shutdown"}})

app = FastAPI(
    title="Notion Opus API",
    description="A FastAPI wrapper providing an OpenAI-compatible interface for Notion's Claude Opus backend.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS (for local frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach rate limiter
app.state.limiter = limiter

# Custom 429 rate-limit response
def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests, please try again later"}
    )
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled application exception",
        exc_info=True,
        extra={
            "request_info": {
                "event": "unhandled_exception",
                "method": request.method,
                "path": request.url.path,
            }
        },
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "server_error",
            }
        },
    )

# Structured request logging middleware
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Skip noisy low-value paths to avoid log spam
    skip_logging = request.url.path in ["/health", "/favicon.ico"]
    
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        raise
    finally:
        process_time = time.time() - start_time
        client_ip = request.client.host if request.client else "unknown"
        
        if not skip_logging:
            log_level = logger.error if status_code >= 400 else logger.info
            log_level(
                "Request processed",
                extra={
                    "request_info": {
                        "method": request.method,
                        "path": request.url.path,
                        "ip": client_ip,
                        "status_code": status_code,
                        "duration_ms": round(process_time * 1000, 2)
                    }
                }
            )
            
    return response

# Simple API key auth middleware
@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    # Skip auth entirely if API_KEY is not configured
    if API_KEY:
        # Skip OPTIONS requests and unprotected static routes
        if request.url.path.startswith("/v1") and request.method != "OPTIONS":
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header.split(" ")[1] != API_KEY:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "message": "Error: API KEY doesn't match.",
                            "type": "invalid_request_error",
                            "code": "invalid_api_key"
                        }
                    }
                )
    return await call_next(request)

# Mount routers under /v1 prefix
app.include_router(chat_router, prefix="/v1")
app.include_router(models_router, prefix="/v1")

# Health check and static assets
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon", status_code=204)

@app.get("/health", tags=["system"])
def health_check(request: Request):
    uptime = time.time() - request.app.state.start_time
    pool = request.app.state.account_pool
    status = pool.get_status_summary()
    return {
        "status": "ok",
        "accounts": status["active"],
        "accounts_total": status["total"],
        "accounts_cooling": status["cooling"],
        "uptime": int(uptime)
    }

# Mount frontend static files at root
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.logging import setup_logging, get_logger, RequestLogger

logger = setup_logging()

app = FastAPI(
    title="AI Commerce OS",
    description="AI-native conversational commerce system",
    version="1.0.0"
)

request_logger = RequestLogger()

@app.middleware("http")
async def log_requests(request, call_next):
    # await request_logger.log_request(request, call_next)

    # logger_api = get_logger("api")
    # logger_api.info(f"→ {request.method} {request.url.path}")
    # response = await call_next(request)
    # logger_api.info(f"← {response.status_code} {request.method} {request.url.path}")
    # return response
    return await request_logger.log_request(request, call_next)
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(RequestTimingMiddleware)

app.include_router(auth_router, prefix="/api")
app.include_router(api_router, prefix="/api")

app.mount(
    "/static",
    StaticFiles(directory="frontend"),
    name="static"
)

@app.get("/")
async def root():
    logger.info("Serving index.html")
    return FileResponse("frontend/index.html")

@app.get("/health")
async def health():
    return {"status": "healthy"}
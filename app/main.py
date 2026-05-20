from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router as api_router
from app.api.auth import router as auth_router
# from app.core.logger import setup_logging
# from app.core.metrics import RequestTimingMiddleware

# setup_logging()

app = FastAPI(
    title="AI Commerce OS",
    description="AI-native conversational commerce system",
    version="1.0.0"
)

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
    return FileResponse("frontend/index.html")

@app.get("/health")
async def health():
    return {"status": "healthy"}
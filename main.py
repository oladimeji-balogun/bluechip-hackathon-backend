
from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.task_a import router as task_a_router
from src.api.task_b import router as task_b_router
from src.core.profile_store import ProfileStore
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ProfileStore.load(settings.PROFILE_STORE_PATH)
    yield


app = FastAPI(
    title="BCT Hack — LLM Agent Challenge",
    description="Task A: Simulate user reviews and ratings. Task B: Personalised recommendations.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(task_a_router, prefix="/api/v1/task-a", tags=["Task A · User Modeling"])
app.include_router(task_b_router, prefix="/api/v1/task-b", tags=["Task B · Recommendation"])


@app.get("/", tags=["Root"])
async def root():
    return {
        "status": "ok",
        "profiles_loaded": ProfileStore.count(),
        "endpoints": {
            "task_a": "/api/v1/task-a/generate",
            "task_b": "/api/v1/task-b/recommend",
            "docs": "/docs",
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    status = {
        "data_file": "present" if os.path.exists(settings.PROFILE_STORE_PATH) else "missing",
        "profile_store": f"ok ({ProfileStore.count()} profiles)" if ProfileStore.count() > 0 else "empty",
    }
    overall = "ok" if all("missing" not in v and "empty" not in v for v in status.values()) else "degraded"
    return {"status": overall, "details": status}
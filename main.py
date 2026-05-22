<<<<<<< HEAD
from fastapi import FastAPI
from src.api import task_a, task_b
from src.core.profile_store import ProfileStore
import os

PROFILES_JSON_PATH = "" #A placeholder for ProfilrStore.load use

app = FastAPI()

app.include_router(task_a.router, prefix="/task_a")
app.include_router(task_b.router, prefix="/task_b")

# Load profiles once on startup
@app.on_event("startup")
async def startup():
    if os.path.exists(PROFILES_JSON_PATH):
        await ProfileStore.load(PROFILES_JSON_PATH)
        print(f"✅ Loaded {ProfileStore.count()} user profiles")
    else:
        print(f"⚠️ Warning: {PROFILES_JSON_PATH} not found. ProfileStore empty.")

# Healthcheck that actually checks most features
@app.get("/health")
async def health_check():
    status = {"profile_store": "unknown", "data_file": "unknown", "agents": "unknown"}
    overall = "ok"

    # Check if JSON file exists
    if os.path.exists(PROFILES_JSON_PATH):
        status["data_file"] = "present"
    else:
        status["data_file"] = "missing"
        overall = "degraded"

    # Check ProfileStore has data
    try:
        count = ProfileStore.count()
        if count > 0:
            status["profile_store"] = f"ok ({count} profiles)"
        else:
            status["profile_store"] = "empty (0 profiles)"
            overall = "degraded"
    except Exception as e:
        status["profile_store"] = f"error: {str(e)}"
        overall = "failed"

    # Check that agent endpoints are attached (quick route check)
    route_paths = [route.path for route in app.routes]
    if "/task_a/generate" in route_paths and "/task_b/recommend" in route_paths:
        status["agents"] = "attached"
    else:
        status["agents"] = "missing expected endpoints"
        overall = "failed"

    return {"status": overall, "details": status}
=======
from contextlib import asynccontextmanager
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
>>>>>>> ba6a339 (feat: task A pipeline running end-to-end, review generation with nigerian context)

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.routes.health import router as health_router
from app.api.routes.problems import router as problems_router
from app.api.routes.artifacts import router as artifacts_router
from app.api.routes.generation import router as generation_router

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend REST API for PolyPilot competitive programming problem-setting platform.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware restricted to local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health router at root
app.include_router(health_router)

# API v1 Router
api_v1_router = APIRouter(prefix=settings.API_V1_PREFIX)
api_v1_router.include_router(problems_router)
api_v1_router.include_router(artifacts_router)
api_v1_router.include_router(generation_router)

app.include_router(api_v1_router)

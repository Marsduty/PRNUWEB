from fastapi import APIRouter

from app.api.routes import comparisons, devices, fingerprints, health, jobs, metrics

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(devices.router)
api_router.include_router(jobs.router)
api_router.include_router(fingerprints.router)
api_router.include_router(comparisons.router)

from fastapi import APIRouter

from service.api.v1.endpoints import (
    auth,
    gallery,
    export,
    favorites,
    index_maintenance,
    photos,
    scan,
    search,
    standard,
    status,
)

api_router = APIRouter()
api_router.include_router(gallery.router, tags=["gallery"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(scan.router, tags=["scan"])
api_router.include_router(status.router, tags=["status"])
api_router.include_router(photos.router, tags=["photos"])
api_router.include_router(favorites.router, tags=["favorites"])
api_router.include_router(standard.router, tags=["standard"])
api_router.include_router(export.router, tags=["export"])
api_router.include_router(index_maintenance.router, tags=["index_maintenance"])

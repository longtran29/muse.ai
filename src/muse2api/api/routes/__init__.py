from fastapi import APIRouter

from . import (
    admin,
    chat,
    dashboard,
    health,
    images,
    media,
    models,
    playground,
    responses,
    videos,
)


def build_router() -> APIRouter:
    router = APIRouter()
    for module in (health, models, chat, responses, images, videos, media, admin,
                   playground, dashboard):
        router.include_router(module.router)
    return router

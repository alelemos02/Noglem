from fastapi import APIRouter

from app.api.v1.endpoints import collections, documents, chats

api_router = APIRouter()

api_router.include_router(collections.router, tags=["Collections"])
api_router.include_router(documents.router, tags=["Documents"])
api_router.include_router(chats.router, tags=["Chats"])

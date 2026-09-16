from fastapi import FastAPI

from app.db import Base, engine
from app.routers import import_router, messages_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="chat-archive-api", version="0.1.0")

app.include_router(import_router.router)
app.include_router(messages_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}

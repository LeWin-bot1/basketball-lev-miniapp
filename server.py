"""
Единая точка входа для Render: Mini App (FastAPI + статика) и Telegram-бот.

Запуск:
    uvicorn server:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.responses import FileResponse

from miniapp.api.main import app
from miniapp.api.websocket import periodic_tournament_update
from main import build_app, init_db

FRONTEND_DIR = Path(__file__).parent / "miniapp" / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    init_db()

    bot = build_app()
    await bot.initialize()
    await bot.start()
    if bot.updater is None:
        raise RuntimeError("Telegram updater is not available")
    await bot.updater.start_polling()
    logging.info("Telegram bot polling started")

    update_task = asyncio.create_task(periodic_tournament_update())
    try:
        yield
    finally:
        update_task.cancel()
        try:
            await update_task
        except asyncio.CancelledError:
            pass
        await bot.updater.stop()
        await bot.stop()
        await bot.shutdown()
        logging.info("Telegram bot stopped")


app.router.lifespan_context = lifespan


@app.get("/")
async def spa_index():
    index = FRONTEND_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"status": "ok", "message": "Mini App frontend is not built"}


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "ws/", "api", "ws")):
        return {"detail": "Not found"}

    candidate = FRONTEND_DIR / full_path
    if candidate.is_file():
        return FileResponse(candidate)

    index = FRONTEND_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"detail": "Not found"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("server:app", host="0.0.0.0", port=port)

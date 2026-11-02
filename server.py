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

from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse

from miniapp.api.main import app
from miniapp.api.websocket import periodic_tournament_update
from main import build_app, init_db, post_init

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
    # то, что run_polling делает сам: кнопка Mini App + проверка неоплаченных крипто-счетов
    try:
        await post_init(bot)
    except Exception as e:
        logging.warning("post_init failed: %s", e)
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
# сжатие ответов: Mini App грузится ~в 3 раза меньше
app.add_middleware(GZipMiddleware, minimum_size=1000)


# index.html никогда не кешируем — иначе Telegram показывает старую версию Mini App
# (особенно через нижнюю кнопку «Mini App»). Файлы в assets/ с хешем в имени — навсегда.
NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


def _index_response():
    index = FRONTEND_DIR / "index.html"
    if index.is_file():
        return FileResponse(index, headers=NO_CACHE)
    return {"status": "ok", "message": "Mini App frontend is not built"}


@app.get("/")
async def spa_index():
    return _index_response()


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "ws/", "api", "ws")):
        return {"detail": "Not found"}

    candidate = FRONTEND_DIR / full_path
    if candidate.is_file() and candidate.name != "index.html":
        headers = IMMUTABLE if full_path.startswith("assets/") else None
        return FileResponse(candidate, headers=headers)

    return _index_response()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("server:app", host="0.0.0.0", port=port)

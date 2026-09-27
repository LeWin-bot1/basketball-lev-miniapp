"""
Аутентификация и валидация данных Telegram Mini App.
Проверяет подпись initData от Telegram.
"""

import hashlib
import hmac
import os
import time
from typing import Optional
from urllib.parse import parse_qsl, unquote

from dotenv import load_dotenv
from fastapi import HTTPException, Header
from pydantic import BaseModel

# Загружаем токен бота
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")


class TelegramUser(BaseModel):
    """Данные пользователя из Telegram"""
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: Optional[bool] = None
    photo_url: Optional[str] = None


class TelegramInitData(BaseModel):
    """Распарсенные initData от Telegram"""
    user: Optional[TelegramUser] = None
    chat_instance: Optional[str] = None
    chat_type: Optional[str] = None
    auth_date: int
    hash: str
    query_id: Optional[str] = None
    start_param: Optional[str] = None


def validate_init_data(init_data: str, bot_token: str = None) -> TelegramInitData:
    """
    Валидирует initData от Telegram Mini App.
    
    Telegram отправляет данные в виде query string:
    user=...&auth_date=...&hash=...
    
    Для валидации нужно:
    1. Распарсить query string
    2. Создать data_check_string (все поля кроме hash, отсортированные)
    3. Вычислить HMAC-SHA256 с ключом = HMAC-SHA256(BOT_TOKEN, "WebAppData")
    4. Сравнить с hash
    
    Docs: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not bot_token:
        bot_token = BOT_TOKEN
    
    if not bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")
    
    try:
        # Парсим query string
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        
        if "hash" not in parsed:
            raise HTTPException(status_code=401, detail="Missing hash in init data")
        
        received_hash = parsed.pop("hash")
        
        # Создаём data_check_string
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )
        
        # Вычисляем секретный ключ: HMAC-SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            "WebAppData".encode(),
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        # Вычисляем хеш данных
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Сравниваем хеши
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(status_code=401, detail="Invalid init data signature")
        
        # Проверяем auth_date (данные не должны быть старше 1 часа)
        auth_date = int(parsed.get("auth_date", 0))
        if time.time() - auth_date > 3600:  # 1 час
            raise HTTPException(status_code=401, detail="Init data expired")
        
        # Парсим user JSON
        import json
        user_data = None
        if "user" in parsed:
            try:
                user_json = json.loads(unquote(parsed["user"]))
                user_data = TelegramUser(**user_json)
            except (json.JSONDecodeError, ValueError):
                pass
        
        return TelegramInitData(
            user=user_data,
            chat_instance=parsed.get("chat_instance"),
            chat_type=parsed.get("chat_type"),
            auth_date=auth_date,
            hash=received_hash,
            query_id=parsed.get("query_id"),
            start_param=parsed.get("start_param"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid init data: {str(e)}")


async def get_current_user(
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"),
    authorization: str = Header(None),
) -> TelegramInitData:
    """
    FastAPI dependency для получения текущего пользователя.
    
    Ожидает initData в заголовке X-Telegram-Init-Data или Authorization.
    
    Использование:
        @app.get("/api/profile")
        async def get_profile(user: TelegramInitData = Depends(get_current_user)):
            user_id = user.user.id
            ...
    """
    init_data = x_telegram_init_data or authorization
    
    if not init_data:
        raise HTTPException(
            status_code=401, 
            detail="Missing Telegram init data. Send in X-Telegram-Init-Data header."
        )
    
    # Убираем "Bearer " префикс если есть
    if init_data.startswith("Bearer "):
        init_data = init_data[7:]
    
    return validate_init_data(init_data)


def get_user_id_from_init_data(init_data: TelegramInitData) -> int:
    """Извлекает user_id из валидированных данных"""
    if not init_data.user:
        raise HTTPException(status_code=401, detail="No user data in init data")
    return init_data.user.id

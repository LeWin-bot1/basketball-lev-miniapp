"""
API модуль для Telegram Mini App
"""

from .main import app
from .auth import get_current_user, validate_init_data
from .database import get_db

__all__ = ["app", "get_current_user", "validate_init_data", "get_db"]

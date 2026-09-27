#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    MenuButtonWebApp,
    Message,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

# -------------------- ENV --------------------
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
if not BOT_TOKEN:
    raise SystemExit("Не задан BOT_TOKEN в .env")

WELCOME_IMG = BASE_DIR / "assets" / "basketball_money.png"
LION_WELCOME_IMG = BASE_DIR / "assets" / "lion_welcome.png"
THANKS_IMG = BASE_DIR / "assets" / "thanks.png"

# URL мини-приложения. На Render можно не задавать: возьмём RENDER_EXTERNAL_URL.
MINIAPP_URL = (
    os.getenv("MINIAPP_URL") or os.getenv("RENDER_EXTERNAL_URL") or ""
).rstrip("/")


async def send_photo_best_effort(
    bot,
    chat_id,
    source,
    *,
    caption=None,
    parse_mode=None,
    reply_markup=None,
):
    """
    Универсальная отправка картинки:
    1) пробуем URL
    2) пробуем локальный файл
    3) если не вышло — отправляем только текст
    """
    # 1) URL
    try:
        s = str(source)
        if s.startswith(("http://", "https://")):
            await bot.send_photo(
                chat_id=chat_id,
                photo=s,
                caption=caption,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return
    except Exception:
        pass

    # 2) Локальный файл
    try:
        p = Path(source)
        if p.exists():
            with p.open("rb") as f:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=f,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
            return
    except Exception:
        pass

    # 3) Только текст, если картинку отправить не удалось
    if caption:
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )


async def delete_and_send_new(
    query,
    text: str,
    reply_markup=None,
    parse_mode=None,
):
    """
    Удаляет старое сообщение и отправляет новое.
    Используется для красивой навигации по меню.
    """
    try:
        # Удаляем старое сообщение
        await query.message.delete()
    except Exception:
        pass
    
    # Отправляем новое сообщение
    return await query.message.reply_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


# -------------------- DB --------------------
DB_PATH = BASE_DIR / "lev_game.db"


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS players (
          user_id INTEGER PRIMARY KEY,
          username TEXT,
          first_name TEXT,
          game_nick TEXT,
          saved_requisites TEXT,
          lev INTEGER DEFAULT 0,
          rating INTEGER DEFAULT 1000,
          wins INTEGER DEFAULT 0,
          losses INTEGER DEFAULT 0,
          draws INTEGER DEFAULT 0,
          last_match_json TEXT,
          matches_played INTEGER DEFAULT 0,
          team_id INTEGER,
          has_seen_welcome INTEGER DEFAULT 0,
          created_at INTEGER DEFAULT (strftime('%s','now')),
          stars_pending INTEGER DEFAULT 0  -- баланс выигранных звёзд (долг бота)
        );

        CREATE TABLE IF NOT EXISTS purchases (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          pack TEXT NOT NULL,
          lev INTEGER NOT NULL,
          amount INTEGER NOT NULL,
          currency TEXT NOT NULL,
          payload TEXT,
          telegram_charge_id TEXT,
          status TEXT NOT NULL,
          created_at INTEGER DEFAULT (strftime('%s','now')),
          paid_at INTEGER
        );

        -- заявки на вывод Lev
        CREATE TABLE IF NOT EXISTS withdraw_requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          lev INTEGER NOT NULL,
          external_address TEXT,
          status TEXT NOT NULL,
          created_at INTEGER DEFAULT (strftime('%s','now')),
          processed_at INTEGER,
          tx_id TEXT
        );

        -- заявки на вывод Telegram Stars
        CREATE TABLE IF NOT EXISTS star_withdraw_requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          stars INTEGER NOT NULL,
          requisites TEXT,
          status TEXT NOT NULL,          -- pending / paid / rejected
          created_at INTEGER DEFAULT (strftime('%s','now')),
          processed_at INTEGER,
          comment TEXT
        );

        CREATE TABLE IF NOT EXISTS teams (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE NOT NULL,
          creator_id INTEGER NOT NULL,
          wins INTEGER DEFAULT 0,
          losses INTEGER DEFAULT 0,
          tournament_points INTEGER DEFAULT 0,
          created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS team_members (
          team_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,
          tournament_points INTEGER DEFAULT 0,
          joined_at INTEGER DEFAULT (strftime('%s','now')),
          PRIMARY KEY (team_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS tournament_solo (
          user_id INTEGER PRIMARY KEY,
          wins INTEGER DEFAULT 0,
          losses INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS tournament_team (
          team_id INTEGER PRIMARY KEY,
          wins INTEGER DEFAULT 0,
          losses INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS config (
          key TEXT PRIMARY KEY,
          value TEXT
        );

        CREATE TABLE IF NOT EXISTS ledger (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          currency TEXT NOT NULL,
          amount INTEGER NOT NULL,
          balance_after INTEGER,
          tx_type TEXT NOT NULL,
          ref_type TEXT,
          ref_id TEXT,
          note TEXT,
          created_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS active_matches (
          match_id TEXT PRIMARY KEY,
          data_json TEXT NOT NULL,
          updated_at INTEGER DEFAULT (strftime('%s','now'))
        );
        """
    )
    # миграции для старой схемы (если ранее таблица уже была создана)
    for sql in [
        "ALTER TABLE players ADD COLUMN wins INTEGER DEFAULT 0",
        "ALTER TABLE players ADD COLUMN losses INTEGER DEFAULT 0",
        "ALTER TABLE players ADD COLUMN draws INTEGER DEFAULT 0",
        "ALTER TABLE players ADD COLUMN last_match_json TEXT",
        "ALTER TABLE players ADD COLUMN matches_played INTEGER DEFAULT 0",
        "ALTER TABLE players ADD COLUMN team_id INTEGER",
        "ALTER TABLE players ADD COLUMN has_seen_welcome INTEGER DEFAULT 0",
        "ALTER TABLE teams ADD COLUMN creator_id INTEGER DEFAULT 0",
        "ALTER TABLE teams ADD COLUMN tournament_points INTEGER DEFAULT 0",
        "ALTER TABLE team_members ADD COLUMN tournament_points INTEGER DEFAULT 0",
        "ALTER TABLE players ADD COLUMN stars_pending INTEGER DEFAULT 0",
        "ALTER TABLE players ADD COLUMN stars_credit INTEGER DEFAULT 0",
    ]:
        try:
            cur.execute(sql)
        except sqlite3.OperationalError:
            pass
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_ledger_user ON ledger(user_id, created_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_purchases_charge_id "
        "ON purchases(telegram_charge_id) "
        "WHERE telegram_charge_id IS NOT NULL AND telegram_charge_id != ''",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_payment_ref "
        "ON ledger(ref_type, ref_id) "
        "WHERE ref_type = 'payment' AND ref_id IS NOT NULL AND ref_id != ''",
    ]:
        try:
            cur.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = db()
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_config(key: str, value: str) -> None:
    conn = db()
    conn.execute(
        "INSERT INTO config(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def ensure_player(u) -> None:
    conn = db()
    conn.execute(
        "INSERT OR IGNORE INTO players(user_id, username, first_name) VALUES(?,?,?)",
        (u.id, u.username or "", u.first_name or ""),
    )
    conn.execute(
        "UPDATE players SET username=?, first_name=? WHERE user_id=?",
        (u.username or "", u.first_name or "", u.id),
    )
    conn.commit()
    conn.close()


def get_player(uid: int):
    return db().execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone()


def display_name(uid: int) -> str:
    row = get_player(uid)
    if not row:
        return f"user_{uid}"
    if row["username"]:
        return f"@{row['username']}"
    return row["first_name"] or f"user_{uid}"


# --------- Lev helpers ----------
def get_lev(uid: int) -> int:
    row = get_player(uid)
    return (row["lev"] if row else 0) or 0


def add_lev(uid: int, amt: int) -> None:
    conn = db()
    conn.execute("UPDATE players SET lev=COALESCE(lev,0)+? WHERE user_id=?", (amt, uid))
    conn.commit()
    conn.close()


def sub_lev_safe(uid: int, amt: int) -> bool:
    conn = db()
    row = conn.execute("SELECT lev FROM players WHERE user_id=?", (uid,)).fetchone()
    bal = (row["lev"] if row else 0) or 0
    if bal < amt:
        conn.close()
        return False
    conn.execute("UPDATE players SET lev=lev-? WHERE user_id=?", (amt, uid))
    conn.commit()
    conn.close()
    return True


# --------- Stars helpers ----------
def get_stars_pending(uid: int) -> int:
    """Баланс выигранных звёзд (долг бота перед игроком)."""
    row = get_player(uid)
    if not row:
        return 0
    try:
        return (row["stars_pending"] or 0) if "stars_pending" in row.keys() else 0
    except Exception:
        return 0


def add_stars_pending(uid: int, amt: int) -> None:
    """Увеличить баланс выигранных звёзд (долг бота перед игроком)."""
    if amt <= 0:
        return
    conn = db()
    conn.execute(
        "UPDATE players SET stars_pending=COALESCE(stars_pending,0)+? WHERE user_id=?",
        (amt, uid),
    )
    conn.commit()
    conn.close()


def sub_stars_pending_safe(uid: int, amt: int) -> bool:
    """Безопасно уменьшить баланс выигранных звёзд (для заявок на вывод)."""
    conn = db()
    row = conn.execute(
        "SELECT stars_pending FROM players WHERE user_id=?",
        (uid,),
    ).fetchone()
    bal = (row["stars_pending"] if row else 0) or 0
    if bal < amt:
        conn.close()
        return False
    conn.execute(
        "UPDATE players SET stars_pending=COALESCE(stars_pending,0)-? WHERE user_id=?",
        (amt, uid),
    )
    conn.commit()
    conn.close()
    return True


def reset_stars_pending(uid: int) -> None:
    """Полностью обнулить баланс выигранных звёзд (жёсткое действие админа)."""
    conn = db()
    conn.execute("UPDATE players SET stars_pending=0 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()


# -------------------- GAME CONSTANTS --------------------
GOAL_POINTS = [6, 9, 18]          # обычные матчи на Lev
STARS_GOAL_POINTS = [6, 8, 12]    # матчи на звёзды

STAR_STAKES = [1, 25, 50]         # ставки в звёздах
MATCHMAKING_TIMEOUT = 120
DEFAULT_STAKE_LEV = 25
BOT_ID = 0
TURN_TIMEOUT = 90.0  # 1.5 минуты

LEV_SCORING = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}

# турнир
TOURNAMENT_DEADLINE_TS = int(time.mktime(time.strptime("2025-12-01", "%Y-%m-%d")))
TOURNAMENT_PRIZE_SOLO = "майка Prada"
TOURNAMENT_PRIZE_TEAM = "10000 тг Sta"


@dataclass
class Match:
    match_id: str
    mode: str            # "mm" | "friend" | "train" | "stars"
    target: int
    stake: int           # для Lev-матчей = Lev, для звёздных матчей = ставке в звёздах
    p1: int
    p2: Optional[int] = None
    score: Dict[int, int] = field(default_factory=dict)
    throws: Dict[int, int] = field(default_factory=dict)
    turn: Optional[int] = None
    started: bool = False
    created_at: float = field(default_factory=time.time)
    first_throw_done: Dict[int, bool] = field(default_factory=dict)
    last_turn_change_ts: float = field(default_factory=time.time)


matches: Dict[str, Match] = {}

# обычный матчмейкинг на Lev
mm_queue: Dict[int, List[str]] = {6: [], 9: [], 18: []}

# матчмейкинг на звёзды: ключ (stake:target) -> список матчей
stars_queue: Dict[str, List[str]] = {}
# оплаты матчей на звёзды: mid -> set(user_id, которые уже оплатили)
stars_match_payments: Dict[str, set[int]] = {}
# кредит звёзд (когда матч не состоялся, но оплата прошла): user_id -> stars
stars_credit: Dict[int, int] = defaultdict(int)

# token -> {"creator_id": int, "target": int, "stake": int, "match_id": str}
invites: Dict[str, Dict[str, int]] = {}
rematch_offers: Dict[str, Dict] = {}               # token -> {from,to,target,stake,mode}
team_invites: Dict[str, int] = {}                  # token -> team_id

# -------------------- NAV: BACK STACK --------------------
MENU_STACK_KEY = "menu_stack"

def push_menu(context: ContextTypes.DEFAULT_TYPE, cb: str) -> None:
    """
    Запоминаем текущий экран (callback_data) в стек.
    Добавляй это ТОЛЬКО в меню-экранах (play_menu, money_menu, stars_money_menu и т.д.)
    """
    stack = context.user_data.setdefault(MENU_STACK_KEY, [])
    if not stack or stack[-1] != cb:
        stack.append(cb)


def pop_menu(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    """
    Убираем текущий экран и возвращаем предыдущий.
    Если предыдущего нет — вернём None.
    """
    stack = context.user_data.get(MENU_STACK_KEY, [])
    if len(stack) <= 1:
        return None
    stack.pop()
    return stack[-1]


def back_kb() -> InlineKeyboardMarkup:
    """
    Универсальная кнопка "назад на шаг".
    """
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Вернуться назад", callback_data="back")]]
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    """
    Кнопка возврата в главное меню.
    """
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]
    )


async def dispatch_menu_like_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Диспетчер меню-экранов.
    ВАЖНО: здесь должны быть только МЕНЮ (НЕ игра: throw/goal/invite и т.д.)
    """
    q = update.callback_query
    data = q.data

    if data == "play_menu":
        return await play_menu(update, context)
    if data == "tournaments_menu":
        return await tournaments_menu(update, context)
    if data == "money_menu":
        return await money_menu(update, context)
    if data == "stars_money_menu":
        return await stars_money_menu(update, context)
    if data == "profile":
        return await profile_btn(update, context)
    if data == "team_menu":
        return await team_menu(update, context)

    # fallback — если не нашли экран
    try:
        await q.edit_message_text("Главное меню:", reply_markup=main_menu(q.from_user.id))
    except Exception:
        await q.message.reply_text("Главное меню:", reply_markup=main_menu(q.from_user.id))


async def back_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик callback_data="back" — шаг назад по стеку меню.
    """
    q = update.callback_query
    await q.answer()

    prev = pop_menu(context)

    if not prev:
        # если возвращаться некуда — покажем главное меню
        try:
            await q.edit_message_text("Главное меню:", reply_markup=main_menu(q.from_user.id))
        except Exception:
            await q.message.reply_text("Главное меню:", reply_markup=main_menu(q.from_user.id))
        return

    # подменяем data на "предыдущий экран" и вызываем диспетчер
    q.data = prev
    await dispatch_menu_like_callback(update, context)
# -------------------- UI / HELPERS --------------------
def has_pending_withdraw(uid: int) -> Optional[int]:
    row = db().execute(
        "SELECT id FROM withdraw_requests WHERE user_id=? AND status='pending' "
        "ORDER BY id DESC LIMIT 1",
        (uid,),
    ).fetchone()
    return row["id"] if row else None


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Вернуться назад", callback_data="back")]]
    )
MENU_STACK_KEY = "menu_stack"          # стек экранов (callback_data)
MENU_MSGS_KEY = "menu_message_ids"     # какие сообщения можно удалять как "меню"

def push_menu(context: ContextTypes.DEFAULT_TYPE, cb: str) -> None:
    stack = context.user_data.setdefault(MENU_STACK_KEY, [])
    if not stack or stack[-1] != cb:
        stack.append(cb)

def pop_menu(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    stack = context.user_data.get(MENU_STACK_KEY, [])
    if len(stack) <= 1:
        return None
    stack.pop()              # убрать текущий
    return stack[-1]         # вернуться к предыдущему


def has_requisites(uid: int) -> bool:
    """Проверить, сохранил ли игрок реквизиты для вывода."""
    conn = db()
    row = conn.execute(
        "SELECT saved_requisites FROM players WHERE user_id=?",
        (uid,),
    ).fetchone()
    conn.close()
    return bool(row and row["saved_requisites"])


def is_admin(uid: int) -> bool:
    return bool(ADMIN_ID and uid == ADMIN_ID)


def valid_requisites(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith("сбп ") or t.startswith("карта ")


def withdraw_status_ru(code: str) -> str:
    return {
        "pending": "в процессе",
        "paid": "выплачена",
        "rejected": "отклонена",
    }.get(code, code)


# -------------------- TEAMS HELPERS --------------------
def get_user_team(uid: int):
    row = db().execute(
        "SELECT t.* FROM teams t "
        "JOIN players p ON p.team_id=t.id WHERE p.user_id=?",
        (uid,),
    ).fetchone()
    return row


def get_team_members(team_id: int):
    return db().execute(
        "SELECT p.user_id, p.username, p.first_name, p.wins, p.losses "
        "FROM team_members tm "
        "JOIN players p ON p.user_id=tm.user_id "
        "WHERE tm.team_id=? ORDER BY tm.joined_at",
        (team_id,),
    ).fetchall()


# -------------------- TOURNAMENT HELPERS --------------------
async def check_tournaments_maybe_finish(context: ContextTypes.DEFAULT_TYPE):
    now = int(time.time())
    if now < TOURNAMENT_DEADLINE_TS:
        return
    if get_config("tournament_finished", "0") == "1":
        return

    conn = db()
    solo_row = conn.execute(
        "SELECT user_id, wins FROM tournament_solo ORDER BY wins DESC, losses ASC LIMIT 1"
    ).fetchone()
    team_row = conn.execute(
        "SELECT team_id, wins FROM tournament_team ORDER BY wins DESC, losses ASC LIMIT 1"
    ).fetchone()
    conn.close()

    if ADMIN_ID:
        if solo_row:
            uid = solo_row["user_id"]
            await context.bot.send_message(
                ADMIN_ID,
                f"🏆 Победитель одиночного турнира: {display_name(uid)} "
                f"(user_id={uid}), приз: {TOURNAMENT_PRIZE_SOLO}",
            )
        if team_row:
            team_id = team_row["team_id"]
            team = db().execute("SELECT name FROM teams WHERE id=?", (team_id,)).fetchone()
            members = get_team_members(team_id)
            members_str = ", ".join(
                display_name(m["user_id"]) for m in members
            ) or "нет игроков"
            await context.bot.send_message(
                ADMIN_ID,
                f"🏆 Победитель командного турнира: команда «{team['name']}» (id={team_id})\n"
                f"Игроки: {members_str}\nПриз: {TOURNAMENT_PRIZE_TEAM}",
            )

    # очистить таблицы турнира
    conn = db()
    conn.execute("DELETE FROM tournament_solo")
    conn.execute("DELETE FROM tournament_team")
    conn.commit()
    conn.close()
    set_config("tournament_finished", "1")


def inc_player_matches(uid: int):
    conn = db()
    conn.execute(
        "UPDATE players SET matches_played=COALESCE(matches_played,0)+1 WHERE user_id=?",
        (uid,),
    )
    conn.commit()
    conn.close()


def maybe_send_timeout_reminder(uid: int, context: ContextTypes.DEFAULT_TYPE):
    row = get_player(uid)
    if not row:
        return
    mp = row["matches_played"] or 0
    if mp > 0 and mp % 2 == 0:
        asyncio.create_task(
            context.bot.send_message(
                uid,
                "⏱ Напоминание: на каждый ход даётся 1.5 минуты. "
                "Если не успеешь сделать бросок — техническое поражение по времени.",
                reply_markup=back_to_main_kb(),
            )
        )


# -------------------- MAIN MENU / UI --------------------
def main_menu(uid: int) -> InlineKeyboardMarkup:
    # Проверяем, есть ли у игрока команда
    team = get_user_team(uid)
    
    kb = [
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("▶️ Играть", callback_data="play_menu")],
        [InlineKeyboardButton("🏆 Турниры", callback_data="tournaments_menu")],
    ]
    
    # Добавляем кнопку команды в зависимости от того, есть ли у игрока команда
    if team:
        kb.append([InlineKeyboardButton("👥 Моя команда", callback_data="my_team_menu")])
    else:
        kb.append([InlineKeyboardButton("👥 Создать команду", callback_data="create_team_start")])
    
    kb.extend([
        [InlineKeyboardButton("💰 Покупка Lev / Вывод Lev", callback_data="money_menu")],
        [InlineKeyboardButton("⭐ Вывод Stars", callback_data="stars_money_menu")],
        [InlineKeyboardButton("📜 Правила", callback_data="rules_btn")],
        [InlineKeyboardButton("🛟 Поддержка", callback_data="support_btn")],
    ])
    
    # Добавляем кнопки Mini App, если URL настроен
    if MINIAPP_URL:
        kb.append([
            InlineKeyboardButton(
                "📊 Статистика",
                web_app=WebAppInfo(url=f"{MINIAPP_URL}/profile")
            ),
            InlineKeyboardButton(
                "🏅 Рейтинг",
                web_app=WebAppInfo(url=f"{MINIAPP_URL}/leaderboard")
            ),
        ])
    
    return InlineKeyboardMarkup(kb)

async def stars_money_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Меню для звёзд: вывод + история.
    """
    q = update.callback_query
    await q.answer()
    
    push_menu(context, "stars_money_menu")
    
    uid = q.from_user.id
    stars_pending = get_stars_pending(uid)

    text = (
        f"⭐ Выигранные звёзды (долг бота): {stars_pending}\n\n"
        "Чтобы вывести звёзды, можно использовать кнопку ниже.\n"
        "⚠️ Перед выводом обязательно укажи корректные реквизиты (СБП/КАРТА)."
    )

    kb = [
        [InlineKeyboardButton("⭐ Вывести Stars", callback_data="stars_withdraw_btn")],
        [InlineKeyboardButton("📜 История вывода Stars", callback_data="stars_withdraw_history")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
    ]

    markup = InlineKeyboardMarkup(kb)
    
    await delete_and_send_new(q, text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def lev_purchases_history_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Кнопка '🧾 История покупок Lev'
    """
    q = update.callback_query
    await q.answer()

    rows = db().execute(
        "SELECT id, lev, amount, currency, status "
        "FROM purchases "
        "WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (q.from_user.id,),
    ).fetchall()

    if not rows:
        return await delete_and_send_new(
            q,
            "История покупок Lev пуста.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
        )

    lines = ["🧾 История покупок Lev:"]
    for r in rows:
        if r["currency"] == "RUB":
            price = r["amount"] / 100.0
            price_str = f"{price:.2f} ₽"
        else:
            price_str = f"{r['amount']} {r['currency']}"

        status_ru = {
            "paid": "оплачено",
            "pending": "в обработке",
            "failed": "ошибка",
        }.get(r["status"], r["status"])

        lines.append(
            f"#{r['id']}: {r['lev']} Lev — {price_str} — {status_ru}"
        )

    await delete_and_send_new(
        q,
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
    )



def goals_menu(mode: str) -> InlineKeyboardMarkup:
    """Меню выбора цели матча (до скольких очков). Для звёзд свои значения."""
    if mode == "stars":
        goals = STARS_GOAL_POINTS
    else:
        goals = GOAL_POINTS

    rows = [[InlineKeyboardButton(f"До {g}", callback_data=f"goal:{mode}:{g}") for g in goals]]
    rows.append([InlineKeyboardButton("🏠 В главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def play_controls(mid: str, *, first: bool) -> InlineKeyboardMarkup:
    label = "Сделать бросок" if first else "Ещё бросок"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"🏀 {label}", callback_data=f"throw:{mid}")]]
    )


def end_controls(mid: str, *, draw: bool) -> InlineKeyboardMarkup:
    if draw:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔁 Взять реванш", callback_data=f"rematch_offer:{mid}")],
                [InlineKeyboardButton("🏠 В главное меню", callback_data="menu")],
            ]
        )
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔁 Сыграть ещё раз", callback_data=f"rematch_offer:{mid}")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="menu")]
        ]
    )


def pretty_mode(m: str) -> str:
    return {
        "mm": "Матчмейкинг",
        "friend": "Дуэль с другом",
        "train": "Тренировка",
        "stars": "Дуэль на звёзды",
    }.get(m, m)


# -------------------- SHOP --------------------
PACKS = {
    "small": ("Малый пак (100 Lev)", 100, 99),
    "medium": ("Средний пак (300 Lev)", 300, 249),
    "large": ("Большой пак (700 Lev)", 700, 499),
}


# -------------------- WITHDRAW CONSTANTS --------------------
WITHDRAW_MIN = 100          # Lev
STARS_WITHDRAW_MIN = 1      # минимальное количество Stars для заявки

WITHDRAW_NOTE = (
    "Реквизиты для вывода указываются строго в одном из двух форматов:\n"
    "1) СБП номер_телефона банк ФИО\n"
    "2) КАРТА номер_карты банк ФИО\n\n"
    "Пример написания реквизитов:\n"
    "1) СБП +7-000-000-00-00 Сбербанк ИвановИванИванович\n"
    "2) КАРТА 4276-8383-1286-7320 Сбербанк ИвановИванИванович"
)


# -------------------- PROFILE & CHAMPIONS --------------------
async def profile_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    push_menu(context, "profile")

    row = get_player(q.from_user.id)
    if not row:
        ensure_player(q.from_user)
        row = get_player(q.from_user.id)

    wins = row["wins"] or 0
    losses = row["losses"] or 0
    try:
        draws = row["draws"] if row["draws"] is not None else 0
    except (KeyError, TypeError):
        draws = 0
    stars = get_stars_pending(q.from_user.id)

    last = "—"
    if row["last_match_json"]:
        try:
            lm = json.loads(row["last_match_json"])
            delta = lm.get("delta_lev", 0)
            delta_str = f"+{delta}" if delta > 0 else (f"{delta}" if delta < 0 else "0")
            last = (
                f"{lm.get('mode_human','Матч')} до {lm.get('target')} | "
                f"Счёт: {lm.get('you_score')}-{lm.get('opp_score')} | "
                f"Соперник: {lm.get('opponent_nick','—')} | "
                f"Итог по Lev: {delta_str}"
            )
        except Exception:
            pass

    text = (
        f"👤 Профиль: {display_name(q.from_user.id)}\n"
        f"Победы: {wins}\n"
        f"Поражения: {losses}\n"
        f"Ничьи: {draws}\n"
        f"Матчей сыграно: {row['matches_played'] or 0}\n"
        f"Последний матч: {last}\n\n"
        f"⭐ Выигранные звёзды (долг бота): {stars}\n"
    )

    kb = []
    
    # Добавляем кнопку Mini App для детальной статистики
    if MINIAPP_URL:
        kb.append([
            InlineKeyboardButton(
                "📊 Подробная статистика",
                web_app=WebAppInfo(url=f"{MINIAPP_URL}/profile")
            )
        ])
    
    team = get_user_team(q.from_user.id)
    if team:
        kb.append([InlineKeyboardButton("👥 Профиль команды", callback_data="team_profile_self")])
    
    kb.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu")])

    markup = InlineKeyboardMarkup(kb)

    await delete_and_send_new(q, text, reply_markup=markup)



async def champions_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = db().execute(
        "SELECT username, first_name, wins "
        "FROM players ORDER BY wins DESC, rating DESC LIMIT 50"
    ).fetchall()
    if not rows:
        text = "Список пуст."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]])
        return await delete_and_send_new(q, text, reply_markup=kb)

    lines = ["🏆 Чемпионы (по победам):"]
    for i, r in enumerate(rows, start=1):
        if r["username"]:
            name = f"@{r['username']}"
        else:
            name = r["first_name"] or "—"
        lines.append(f"{i}. {name} — {r['wins']} побед")

    text = "\n".join(lines)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]])

    await delete_and_send_new(q, text, reply_markup=kb)


# -------------------- RULES / SUPPORT --------------------
async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📜 <b>Правила Basketball Lev</b>\n\n"
        "‼️ <b>Очень важно</b>\n"
        "Чтобы вывести выигранные звёзды и Lev, ОБЯЗАТЕЛЬНО укажи корректные реквизиты "
        "(СБП/КАРТА) в разделе «✏️ Реквизиты» при первом входе в бот.\n"
        "Без сохранённых реквизитов бот не сможет вывести тебе ни звёзды, ни деньги, "
        "а также не допустит до игр с другими игроками и покупки Lev.\n\n"
        "🎯 <b>Цель матча</b>\n"
        "• Игра идёт до 6, 9 или 18 очков (режим Lev).\n"
        "• В режиме звёзд — до 6, 8 или 12 очков.\n"
        "• У обоих игроков всегда <b>равное количество бросков</b>.\n"
        "• Раунд заканчивается только после того, как оба сделали одинаковое число бросков.\n\n"
        "🏀 <b>Очки за бросок</b>\n"
        "Телеграм-кубик (🏀) даёт значение 1–5, бот переводит это в очки:\n"
        "1 → 0 очков\n2 → 1 очко\n3 → 2 очка\n4 → 3 очка\n5 → 4 очка\n\n"
        "⏱ <b>Ограничение по времени</b>\n"
        "• На каждый ход даётся <b>1.5 минуты</b>.\n"
        "• Если игрок не успевает сделать бросок — он получает <b>техническое поражение по времени</b>.\n"
        "• После каждых двух сыгранных матчей бот напоминает об этом правиле перед началом новой игры.\n\n"
        "🤝 <b>Режимы</b>\n"
        "• Матчмейкинг: случайный соперник за фиксированную ставку Lev.\n"
        "• Дуэль с другом: создаёшь ссылку и выбираешь ставку Lev.\n"
        "• Тренировка: игра против бота, без изменения Lev и рейтинга.\n"
        "• Дуэль на звёзды: бот создаёт банк звёзд; победитель забирает весь банк.\n\n"
        "⭐ <b>Дуэли на звёзды</b>\n"
        "• Доступные ставки: 1, 25 и 50 звёзд с игрока.\n"
        "• Игра идёт до 6, 8 или 12 очков.\n"
        "• После победы звёзды начисляются на баланс «долг бота» (в профиле), "
        "а затем ты можешь подать заявку на их вывод.\n\n"
        "👥 <b>Команды</b>\n"
        "• Команда — до 3 игроков.\n"
        "• Название команды: только латиница, цифры и подчёркивание, 3–40 символов.\n\n"
        "🏆 <b>Турниры до 01.12.2025</b>\n"
        "• Одиночный турнир: главный приз — майка Prada.\n"
        "• Командный турнир (команды до 3 игроков): приз — 10000 тг Sta на команду.\n"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=back_to_main_kb(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ Кратко:\n"
        "• Выбирай режим: матчмейкинг, дуэль с другом, тренировка или дуэль на звёзды.\n"
        "• Бросай баскетбольный мяч в корзинку с помощью стикера 🏀.\n"
        "• Цель — набрать 6/9/18 (Lev) или 6/8/12 (звёзды) очков, при равном числе бросков.\n"
        "• На ход 1.5 минуты, иначе — поражение по времени.\n\n"
        "Подробные правила: /rules\n"
        "Поддержка: /support"
    )
    await update.message.reply_text(text, reply_markup=back_to_main_kb())


async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🛟 Поддержка\n\n"
        "Наш ассистент @Nikita_Kovalevsk поможет по любым вопросам.\n"
        "Он отвечает ежедневно с 10:00 до 22:00 (по Москве)."
    )
    await update.message.reply_text(text, reply_markup=back_to_main_kb())


async def cmd_reset_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда для сброса флага приветствия (для тестирования).
    """
    u = update.effective_user
    conn = db()
    conn.execute(
        "UPDATE players SET has_seen_welcome=0 WHERE user_id=?",
        (u.id,),
    )
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        "✅ Флаг приветствия сброшен!\n"
        "Теперь отправь /start чтобы увидеть приветственное сообщение снова.",
    )


async def rules_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    text = (
        "📜 <b>Правила Basketball Lev</b>\n\n"
        "‼️ <b>Очень важно</b>\n"
        "Чтобы вывести выигранные звёзды и Lev, ОБЯЗАТЕЛЬНО укажи корректные реквизиты "
        "(СБП/КАРТА) в разделе «✏️ Реквизиты» при первом входе в бот.\n"
        "Без сохранённых реквизитов бот не сможет вывести тебе ни звёзды, ни деньги, "
        "а также не допустит до игр с другими игроками и покупки Lev.\n\n"
        "🎯 <b>Цель матча</b>\n"
        "• Режим Lev: до 6, 9 или 18 очков.\n"
        "• Режим звёзд: до 6, 8 или 12 очков.\n"
        "• У обоих игроков всегда <b>равное количество бросков</b>.\n"
        "• Раунд заканчивается только после того, как оба сделали одинаковое число бросков.\n\n"
        "🏀 <b>Очки за бросок</b>\n"
        "Телеграм-кубик (🏀) даёт значение 1–5, бот переводит это в очки.\n\n"
        "⏱ <b>Ограничение по времени</b>\n"
        "• На каждый ход даётся <b>1.5 минуты</b>.\n"
        "• Если игрок не успевает сделать бросок — он получает <b>техническое поражение по времени</b>.\n\n"
        "🤝 <b>Режимы</b>\n"
        "• Матчмейкинг, дуэль с другом, тренировка и дуэль на звёзды."
    )

    await delete_and_send_new(
        q,
        text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]
        ),
        parse_mode=ParseMode.HTML,
    )


async def support_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    text = (
        "🛟 Поддержка\n\n"
        "Наш ассистент @Nikita_Kovalevsk поможет по любым вопросам.\n"
        "Он отвечает ежедневно с 10:00 до 22:00 (по Москве)."
    )

    await delete_and_send_new(
        q,
        text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]
        ),
    )


# -------------------- /start + TEXT HANDLER --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — Приветствие для новых пользователей или главное меню для существующих.
    """
    u = update.effective_user
    ensure_player(u)

    context.user_data["menu_stack"] = ["menu"]

    # Проверяем, видел ли пользователь приветствие
    conn = db()
    row = conn.execute(
        "SELECT has_seen_welcome FROM players WHERE user_id=?",
        (u.id,),
    ).fetchone()
    
    has_seen_welcome = 0
    if row:
        try:
            has_seen_welcome = row["has_seen_welcome"] if row["has_seen_welcome"] is not None else 0
        except (KeyError, TypeError):
            has_seen_welcome = 0
    
    conn.close()
    
    # Если пользователь новый - показываем приветствие
    if not has_seen_welcome:
        # Короткое приветственное сообщение в стиле Virus Game Bot
        welcome_text = (
            "<b>🦁 Что умеет Basketball Lev Bot?</b>\n\n"
            "💰 Это бот для <b>дуэлей</b>, в которых ты можешь <b>выигрывать реальные деньги!</b>\n\n"
            "🏀 Бросай баскетбольный мяч в корзинку\n"
            "🎯 Побеждай соперников в дуэлях\n"
            "💸 Зарабатывай Lev и Telegram Stars\n"
            "🏆 Участвуй в турнирах и командных соревнованиях\n"
            "💎 Выводи выигрыш на карту или СБП\n\n"
            "👇 <b>Нажми кнопку «Старт» чтобы начать!</b>"
        )

        # Пытаемся отправить фото со львом
        try:
            # Проверяем, существует ли файл
            if LION_WELCOME_IMG.exists():
                with open(LION_WELCOME_IMG, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo,
                        caption=welcome_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("🚀 Старт", callback_data="start_game")]]
                        ),
                    )
            else:
                # Если файла нет - отправляем просто текст с кнопкой
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=welcome_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🚀 Старт", callback_data="start_game")]]
                    ),
                )
        except Exception as e:
            # В случае ошибки отправляем текст
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=welcome_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🚀 Старт", callback_data="start_game")]]
                ),
            )
    else:
        # Пользователь уже видел приветствие - показываем главное меню
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Главное меню:",
            reply_markup=main_menu(u.id),
        )


async def text_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = update.message.text.strip()
    # --- пользователь вводит количество Stars для вывода (кнопка "Вывести Stars") ---
    if context.user_data.get("await_stars_withdraw"):
        # сбросим флаг в любом случае, чтобы не зациклиться
        context.user_data["await_stars_withdraw"] = False

        # парсим число
        try:
            stars_amt = int(text)
        except ValueError:
            return await update.message.reply_text(
                "Количество звёзд должно быть целым числом.",
                reply_markup=back_to_main_kb(),
            )

        if stars_amt < STARS_WITHDRAW_MIN:
            return await update.message.reply_text(
                f"Минимальная сумма для вывода Stars: {STARS_WITHDRAW_MIN} ⭐.",
                reply_markup=back_to_main_kb(),
            )

        u = update.effective_user

        # проверяем реквизиты
        row = db().execute(
            "SELECT saved_requisites FROM players WHERE user_id=?",
            (u.id,),
        ).fetchone()
        saved_req = row["saved_requisites"] if row else None
        if not saved_req:
            return await update.message.reply_text(
                "‼️ Перед выводом звёзд нужно указать реквизиты в разделе «✏️ Реквизиты».\n\n"
                "Зайди в меню: «Покупка Lev / Вывод Lev» → «✏️ Реквизиты».",
                reply_markup=back_to_main_kb(),
            )

        # проверяем баланс звёзд
        current_stars = get_stars_pending(u.id)
        if current_stars < stars_amt:
            return await update.message.reply_text(
                f"Недостаточно звёзд для вывода.\n"
                f"Баланс выигранных звёзд: {current_stars} ⭐.",
                reply_markup=back_to_main_kb(),
            )

        # уменьшаем долг (stars_pending)
        if not sub_stars_pending_safe(u.id, stars_amt):
            return await update.message.reply_text(
                "Не удалось забронировать звёзды для вывода. Попробуй позже.",
                reply_markup=back_to_main_kb(),
            )

        # создаём заявку в правильной таблице star_withdraw_requests
        conn = db()
        cur = conn.execute(
            "INSERT INTO star_withdraw_requests(user_id,stars,requisites,status) "
            "VALUES(?,?,?, 'pending')",
            (u.id, stars_amt, saved_req),
        )
        swid = cur.lastrowid
        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"⭐ Спасибо! Заявка на вывод звёзд #{swid} создана.\n"
            f"Сумма: {stars_amt} ⭐.\n"
            "После обработки админом звёзды будут отправлены на твой Telegram-аккаунт или по указанным реквизитам.",
            reply_markup=back_to_main_kb(),
        )

        # уведомление админу (как в cmd_swithdraw)
        if ADMIN_ID:
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"⭐ Новая заявка на вывод Stars #{swid}\n"
                    f"Игрок: {display_name(u.id)} (id={u.id})\n"
                    f"Сумма: {stars_amt} ⭐\n"
                    f"Реквизиты: {saved_req}",
                )
            except Exception:
                pass

        return
    # ввод суммы ставки для дуэли с другом (на Lev)
    if context.user_data.get("await_friend_stake"):
        context.user_data.pop("await_friend_stake", None)
        try:
            stake = int(text)
        except ValueError:
            return await update.message.reply_text(
                "Сумма Lev должна быть целым числом.",
                reply_markup=back_to_main_kb(),
            )
        if stake <= 0:
            return await update.message.reply_text(
                "Сумма Lev должна быть больше нуля.",
                reply_markup=back_to_main_kb(),
            )
        if get_lev(u.id) < stake:
            return await update.message.reply_text(
                f"Недостаточно Lev. Текущий баланс: {get_lev(u.id)} Lev.",
                reply_markup=back_to_main_kb(),
            )

        context.user_data["friend_stake"] = stake
        return await update.message.reply_text(
            f"Сумма для дуэли: {stake} Lev.\nТеперь выбери цель матча:",
            reply_markup=goals_menu("friend"),
        )

    # ввод реквизитов
    if context.user_data.get("await_requisites"):
        if not valid_requisites(text):
            return await update.message.reply_text(
                "Реквизиты должны начинаться с 'СБП' или 'КАРТА'.\n" + WITHDRAW_NOTE,
                parse_mode=ParseMode.HTML,
                reply_markup=back_to_main_kb(),
            )
        conn = db()
        conn.execute(
            "UPDATE players SET saved_requisites=? WHERE user_id=?", (text, u.id)
        )
        conn.commit()
        conn.close()
        context.user_data.pop("await_requisites", None)
        return await update.message.reply_text(
            "✅ Реквизиты сохранены.",
            reply_markup=main_menu(u.id),
        )

    # ввод названия команды
    if context.user_data.get("await_team_name"):
        context.user_data.pop("await_team_name", None)
        name = text[:40].strip()
        if len(name) < 3:
            return await update.message.reply_text(
                "Название команды должно быть от 3 символов.",
                reply_markup=back_to_main_kb(),
            )

        # только латиница, цифры и подчёркивание
        if not all(ch.isascii() and (ch.isalnum() or ch == "_") for ch in name):
            return await update.message.reply_text(
                "Название команды может содержать только латинские буквы, цифры и подчёркивание.",
                reply_markup=back_to_main_kb(),
            )

        if get_user_team(u.id):
            return await update.message.reply_text(
                "У тебя уже есть команда.",
                reply_markup=back_to_main_kb(),
            )
        conn = db()
        cur = conn.execute("SELECT id FROM teams WHERE name=?", (name,))
        if cur.fetchone():
            conn.close()
            return await update.message.reply_text(
                "Команда с таким названием уже существует. Выбери другое.",
                reply_markup=back_to_main_kb(),
            )
        cur = conn.execute(
            "INSERT INTO teams(name, creator_id, tournament_points) VALUES(?, ?, 0)",
            (name, u.id),
        )
        team_id = cur.lastrowid
        conn.execute(
            "INSERT INTO team_members(team_id, user_id, tournament_points) VALUES(?, ?, 0)",
            (team_id, u.id),
        )
        conn.execute("UPDATE players SET team_id=? WHERE user_id=?", (team_id, u.id))
        conn.commit()
        conn.close()
        
        # Предлагаем пригласить друзей
        return await update.message.reply_text(
            f"✅ <b>Команда «{name}» создана!</b>\n\n"
            f"👤 Ты — создатель и первый участник команды.\n"
            f"👥 Можно пригласить ещё 2 игроков.\n\n"
            f"<b>Как пригласить друзей?</b>\n"
            f"Зайди в меню команды и нажми «Пригласить игрока».\n"
            f"Ты сможешь пригласить друзей позже в любое время.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Моя команда", callback_data="my_team_menu")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
            ]),
        )

    # дефолтный ответ на любой текст
    await update.message.reply_text(
        "Я тебя не совсем понял 🤔\n"
        "Используй кнопки меню или команду /help.",
        reply_markup=back_to_main_kb(),
    )


# -------------------- MENU: BACK --------------------
async def back_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    prev = pop_menu(context)

    if not prev:
        # если стека нет — просто в главное меню
        try:
            await q.edit_message_text("Главное меню:", reply_markup=main_menu(q.from_user.id))
        except Exception:
            await q.message.reply_text("Главное меню:", reply_markup=main_menu(q.from_user.id))
        return

    # имитируем "нажатие" предыдущей кнопки:
    q.data = prev
    await dispatch_menu_like_callback(update, context)

async def dispatch_menu_like_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data

    # сопоставь только меню/экраны (НЕ игру)
    if data == "play_menu":
        return await play_menu(update, context)
    if data == "tournaments_menu":
        return await tournaments_menu(update, context)
    if data == "money_menu":
        return await money_menu(update, context)
    if data == "stars_money_menu":
        return await stars_money_menu(update, context)
    if data == "profile":
        return await profile_btn(update, context)

    # fallback
    try:
        await q.edit_message_text("Главное меню:", reply_markup=main_menu(q.from_user.id))
    except Exception:
        await q.message.reply_text("Главное меню:", reply_markup=main_menu(q.from_user.id))

# -------------------- MENUS: PLAY / TOURNAMENTS / MONEY --------------------
async def play_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    push_menu(context, "play_menu")

    kb = [
        [InlineKeyboardButton("🎯 Матчмейкинг на Lev", callback_data="mode:mm")],
        [InlineKeyboardButton("⭐ Матчмейкинг на звёзды", callback_data="stars_menu")],
        [InlineKeyboardButton("🤝 Игра с другом на Lev", callback_data="mode:friend")],
        [InlineKeyboardButton("🤝⭐ Игра с другом на звёзды", callback_data="friend_stars_soon")],
        [InlineKeyboardButton("🎓 Тренировка", callback_data="mode:train")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
    ]

    text = "Выберите режим игры:"

    await delete_and_send_new(q, text, reply_markup=InlineKeyboardMarkup(kb))

async def tournaments_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    push_menu(context, "tournaments_menu")

    kb = [
        [InlineKeyboardButton("👥 Командный турнир", callback_data="tournament_team")],
        [InlineKeyboardButton("🏀 Одиночный турнир", callback_data="tournament_solo")],
        [InlineKeyboardButton("🏆 Чемпионы", callback_data="champions")],
    ]
    
    # Добавляем кнопку Mini App для детальной таблицы турнира
    if MINIAPP_URL:
        kb.append([
            InlineKeyboardButton(
                "📊 Полная таблица турнира",
                web_app=WebAppInfo(url=f"{MINIAPP_URL}/tournaments")
            )
        ])
    
    kb.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu")])

    text = "Турниры:"

    await delete_and_send_new(q, text, reply_markup=InlineKeyboardMarkup(kb))



async def money_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    lev = get_lev(uid)

    text = (
        f"💰 Баланс: {lev} Lev\n\n"
        "Здесь можно пополнить Lev, создать заявку на вывод и посмотреть историю своих операций."
    )

    kb_rows = [
        [InlineKeyboardButton("💸 Купить Lev", callback_data="shop")],
        [InlineKeyboardButton("🏦 Вывод Lev", callback_data="withdraw_menu")],
        [InlineKeyboardButton("🧾 История покупок Lev", callback_data="lev_purchases_history")],
        [InlineKeyboardButton("📜 История вывода Lev", callback_data="lev_withdraw_history")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
    ]
    markup = InlineKeyboardMarkup(kb_rows)

    await delete_and_send_new(q, text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def friend_stars_soon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Временная заглушка для "Игры с другом на звёзды".
    Потом можно заменить на реальную логику.
    """
    q = update.callback_query
    await q.answer()
    await delete_and_send_new(
        q,
        "Игра с другом на звёзды пока в разработке 🛠\n"
        "Скоро добавим возможность отправлять приглашение со ставкой в звёздах.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
    )


# -------------------- SHOP: ПОКУПКА LEV --------------------
async def shop_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not has_requisites(q.from_user.id):
        return await delete_and_send_new(
            q,
            "‼️ Чтобы покупать Lev и потом выводить деньги, сначала укажи реквизиты для вывода "
            "(СБП/КАРТА).\n\n"
            "Без корректных реквизитов вывести средства будет невозможно.\n\n"
            "Укажи реквизиты по формату:\n"
            "1) СБП номер_телефона банк ФИО\n"
            "2) КАРТА номер_карты банк ФИО",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✏️ Ввести реквизиты", callback_data="requisites_menu")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
                ]
            ),
        )

    kb = [
        [
            InlineKeyboardButton(f"{lbl} — {price}₽", callback_data=f"buy:{pid}")
        ]
        for pid, (lbl, lev_amt, price) in PACKS.items()
    ]
    kb.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu")])
    await delete_and_send_new(
        q, "🛍 Выберите пакет Lev:", reply_markup=InlineKeyboardMarkup(kb)
    )


async def buy_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    pid = q.data.split(":")[1]
    if pid not in PACKS:
        return await q.answer("Пакет не найден", show_alert=True)
    label, lev_amt, price_rub = PACKS[pid]
    payload = f"rub_{pid}_{q.from_user.id}_{int(time.time())}_{secrets.token_hex(3)}"
    prices = [LabeledPrice(label=label, amount=price_rub * 100)]
    await context.bot.send_invoice(
        chat_id=q.message.chat.id,
        title=label,
        description=f"Покупка {lev_amt} Lev за {price_rub}₽",
        payload=payload,
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter="lev_shop",
    )


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка успешной оплаты:
    - XTR (Telegram Stars) для дуэлей на звёзды (payload stars_match_start:...)
    - RUB для покупки Lev
    """
    u = update.message.from_user
    ensure_player(u)
    sp = update.message.successful_payment
    payload = sp.invoice_payload

    # ---------- 1) Оплата участия в матче на реальные Telegram Stars ----------
    if sp.currency == "XTR" and payload.startswith("stars_match_start:"):
        # payload: stars_match_start:mid:uid:stake:target:token
        try:
            _, mid, uid_s, stake_s, target_s, token = payload.split(":")
            paid_uid = int(uid_s)
        except Exception:
            logging.error("Bad stars_match_start payload: %s", payload)
            await update.message.reply_text(
                "Оплата принята, но не удалось привязать её к матчу. Напишите /support.",
                reply_markup=back_to_main_kb(),
            )
            return

        if paid_uid != u.id:
            logging.warning(
                "Stars payment user mismatch: payload uid=%s, actual=%s",
                paid_uid,
                u.id,
            )

        m = matches.get(mid)
        if not m or m.mode != "stars":
            # матч уже неактуален -> начисляем кредит
            stars_credit[u.id] = stars_credit.get(u.id, 0) + sp.total_amount
            await update.message.reply_text(
                "Матч уже неактуален, но оплата принята.\n"
                f"Вам начислен кредит {sp.total_amount} ⭐ для следующих игр.",
                reply_markup=back_to_main_kb(),
            )
            return

        paid_set = stars_match_payments.setdefault(mid, set())
        paid_set.add(u.id)

        await update.message.reply_text(
            "Оплата участия в дуэли на звёзды получена.\n"
            "Ожидаем оплату соперника.",
            reply_markup=back_to_main_kb(),
        )

        # если оба игрока оплатили — стартуем матч
        if m.p1 in paid_set and m.p2 in paid_set:
            stars_match_payments.pop(mid, None)
            await announce_start(context, m)

        return

    # ---------- 2) Покупка Lev за RUB ----------
    try:
        _, pid, *_ = payload.split("_")
    except Exception:
        pid = None

    if pid not in PACKS:
        return await update.message.reply_text(
            "Оплата получена, но пакет не распознан.",
            reply_markup=back_to_main_kb(),
        )

    label, lev_amt, price_rub = PACKS[pid]

    conn = db()
    conn.execute(
        "INSERT INTO purchases(user_id,pack,lev,amount,currency,payload,telegram_charge_id,status,paid_at) "
        "VALUES(?,?,?,?,?,?,?,?,strftime('%s','now'))",
        (
            u.id,
            pid,
            lev_amt,
            price_rub * 100,
            "RUB",
            payload,
            sp.telegram_payment_charge_id,
            "paid",
        ),
    )
    conn.execute(
        "UPDATE players SET lev=COALESCE(lev,0)+? WHERE user_id=?", (lev_amt, u.id)
    )
    conn.commit()
    conn.close()

    instruction = (
        "Спасибо за покупку! 🎉\n\n"
        "Как вывести Lev обратно в деньги:\n"
        "1) Сохраните корректные реквизиты (СБП/КАРТА) в «✏️ Реквизиты».\n"
        "2) Создайте заявку командой: "
        "<code>/withdraw &lt;Lev&gt; &lt;СБП/КАРТА и данные&gt;</code>.\n"
        "3) При корректных реквизитах деньги придут в течение 5 часов.\n"
        "4) Статус заявки — в разделе «Покупка Lev / Вывод Lev» → «История вывода Lev»."
    )

    await send_photo_best_effort(
        context.bot,
        update.effective_chat.id,
        THANKS_IMG,
        caption=instruction,
        parse_mode=ParseMode.HTML,
        reply_markup=back_to_main_kb(),
    )


async def balance_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        f"💰 Баланс: {get_lev(q.from_user.id)} Lev\n"
        f"⭐ Выигранные звёзды (долг бота): {get_stars_pending(q.from_user.id)}",
        reply_markup=back_to_main_kb(),
    )


# -------------------- WITHDRAW / REQUISITES (LEV) --------------------
async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    push_menu(context, "withdraw_menu")

    row = db().execute(
        "SELECT saved_requisites FROM players WHERE user_id=?",
        (q.from_user.id,),
    ).fetchone()
    saved = row["saved_requisites"] if row else None

    text = "🏦 Вывод Lev.\n" + WITHDRAW_NOTE
    if saved:
        text += f"\n\nСохранённые реквизиты: {saved}"

    kb = [
        [InlineKeyboardButton("Создать заявку (команда)", callback_data="withdraw_how")],
        [InlineKeyboardButton("✏️ Изменить реквизиты", callback_data="requisites_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
    ]
    
    await delete_and_send_new(q, text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def stars_withdraw_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Кнопка '⭐ Вывести Stars' в меню Stars.
    Просит ввести сумму, затем text_any создаёт заявку (аналог /swithdraw).
    """
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    # проверяем реквизиты (как в cmd_swithdraw)
    row = db().execute(
        "SELECT saved_requisites FROM players WHERE user_id=?",
        (uid,),
    ).fetchone()
    saved_req = row["saved_requisites"] if row else None

    if not saved_req:
        text = (
            "‼️ Перед выводом звёзд нужно указать реквизиты в разделе «✏️ Реквизиты».\n\n"
            "Зайди в меню: «💰 Покупка Lev / Вывод Lev» → «✏️ Реквизиты»."
        )
        try:
            await q.edit_message_text(
                text,
                reply_markup=back_to_main_kb(),
            )
        except Exception:
            await q.message.reply_text(
                text,
                reply_markup=back_to_main_kb(),
            )
        return

    stars_pending = get_stars_pending(uid)

    if stars_pending < STARS_WITHDRAW_MIN:
        text = (
            f"Недостаточно звёзд для вывода.\n"
            f"Минимальная сумма: {STARS_WITHDRAW_MIN} ⭐.\n"
            f"Текущий баланс выигранных звёзд: {stars_pending} ⭐."
        )
        try:
            await q.edit_message_text(
                text,
                reply_markup=back_to_main_kb(),
            )
        except Exception:
            await q.message.reply_text(
                text,
                reply_markup=back_to_main_kb(),
            )
        return

    # помечаем, что ждём от пользователя число звёзд в следующем текстовом сообщении
    context.user_data["await_stars_withdraw"] = True

    text = (
        f"Введите количество ⭐ для вывода (доступно: {stars_pending}).\n"
        f"Минимум: {STARS_WITHDRAW_MIN}.\n\n"
        "Пример: <code>50</code>"
    )

    try:
        await q.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("↩️ Отмена", callback_data="stars_money_menu")]]
            ),
        )
    except Exception:
        await q.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("↩️ Отмена", callback_data="stars_money_menu")]]
            ),
        )


async def withdraw_how(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await delete_and_send_new(
        q,
        "Создайте заявку командой:\n"
        "<code>/withdraw &lt;Lev&gt; &lt;СБП/КАРТА и данные&gt;</code>\n"
        "Примеры:\n"
        "• <code>/withdraw 500 СБП +79990000000, Тинькофф, Иванов Иван</code>\n"
        "• <code>/withdraw 1000 КАРТА 2200********0000, Сбербанк, Иванов Иван</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("↩️ Назад", callback_data="withdraw_menu")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
            ]
        ),
    )


async def withdraw_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    wid = int(q.data.split(":")[1])

    row = db().execute(
        "SELECT status, external_address, lev "
        "FROM withdraw_requests WHERE id=? AND user_id=?",
        (wid, q.from_user.id),
    ).fetchone()

    if not row:
        return await q.edit_message_text(
            "Заявка не найдена.",
            reply_markup=back_to_main_kb(),
        )

    status_text = withdraw_status_ru(row["status"])
    text = (
        f"📦 Заявка #{wid}: {row['lev']} Lev → {row['external_address']}\n"
        f"Статус: {status_text}"
    )

    await q.edit_message_text(
        text,
        reply_markup=back_to_main_kb(),
    )


async def requisites_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    push_menu(context, "requisites_menu")

    row = db().execute(
        "SELECT saved_requisites FROM players WHERE user_id=?",
        (q.from_user.id,),
    ).fetchone()
    saved = row["saved_requisites"] if row else None

    text = "✏️ Сохранённые реквизиты: " + (saved or "не заданы") + "\n\n" + WITHDRAW_NOTE

    kb = [
        [InlineKeyboardButton("Изменить", callback_data="requisites_edit")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
    ]

    markup = InlineKeyboardMarkup(kb)

    await delete_and_send_new(q, text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def requisites_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["await_requisites"] = True
    await delete_and_send_new(
        q,
        "Отправьте новые реквизиты одним сообщением.\n\n" + WITHDRAW_NOTE,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("↩️ Отмена", callback_data="requisites_menu")]]
        ),
    )


async def cmd_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /withdraw <Lev> <реквизиты>
    Создание заявки на вывод Lev.
    """
    u = update.effective_user
    ensure_player(u)
    if len(context.args) < 2:
        return await update.message.reply_text(
            "Использование: /withdraw &lt;Lev&gt; &lt;СБП/КАРТА и данные&gt;\n\n" + WITHDRAW_NOTE,
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_main_kb(),
        )
    try:
        lev_amt = int(context.args[0])
    except ValueError:
        return await update.message.reply_text(
            "Сумма Lev должна быть числом.",
            reply_markup=back_to_main_kb(),
        )
    if lev_amt < WITHDRAW_MIN:
        return await update.message.reply_text(
            f"Минимальная сумма для вывода: {WITHDRAW_MIN} Lev.",
            reply_markup=back_to_main_kb(),
        )
    details = " ".join(context.args[1:])[:200]
    if not valid_requisites(details):
        return await update.message.reply_text(
            "Реквизиты должны начинаться с 'СБП' или 'КАРТА'.\n\n" + WITHDRAW_NOTE,
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_main_kb(),
        )
    if not sub_lev_safe(u.id, lev_amt):
        return await update.message.reply_text(
            f"Недостаточно средств. Баланс: {get_lev(u.id)} Lev.",
            reply_markup=back_to_main_kb(),
        )
    conn = db()
    cur = conn.execute(
        "INSERT INTO withdraw_requests(user_id,lev,external_address,status) "
        "VALUES(?,?,?, 'pending')",
        (u.id, lev_amt, details),
    )
    wid = cur.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"Спасибо! Заявка #{wid} создана.\n"
        "При корректных реквизитах деньги поступят в течение 5 часов.",
        reply_markup=back_to_main_kb(),
    )

    # уведомление админу
    if ADMIN_ID:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"💸 Новая заявка на вывод Lev #{wid}\n"
                f"Игрок: {display_name(u.id)} (id={u.id})\n"
                f"Сумма: {lev_amt} Lev\n"
                f"Реквизиты: {details}",
            )
        except Exception:
            pass


# -------------------- ЗАЯВКИ НА ВЫВОД STARs --------------------
async def cmd_swithdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /swithdraw <stars>
    Создание заявки на вывод Telegram Stars (на основе stars_pending и сохранённых реквизитов).
    """
    u = update.effective_user
    ensure_player(u)

    # проверяем аргументы
    if len(context.args) < 1:
        return await update.message.reply_text(
            "Использование: /swithdraw &lt;количество_звёзд&gt;\n\n"
            "Заявка создаётся из твоего баланса выигранных звёзд (долг бота).\n"
            "Реквизиты берутся из раздела «✏️ Реквизиты».",
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_main_kb(),
        )
    try:
        stars_amt = int(context.args[0])
    except ValueError:
        return await update.message.reply_text(
            "Количество звёзд должно быть целым числом.",
            reply_markup=back_to_main_kb(),
        )

    if stars_amt < STARS_WITHDRAW_MIN:
        return await update.message.reply_text(
            f"Минимальная сумма для вывода Stars: {STARS_WITHDRAW_MIN} ⭐.",
            reply_markup=back_to_main_kb(),
        )

    # проверяем реквизиты
    row = db().execute(
        "SELECT saved_requisites FROM players WHERE user_id=?",
        (u.id,),
    ).fetchone()
    saved_req = row["saved_requisites"] if row else None
    if not saved_req:
        return await update.message.reply_text(
            "‼️ Перед выводом звёзд нужно указать реквизиты в разделе «✏️ Реквизиты».\n\n"
            "Зайди в меню: «Покупка Lev / Вывод Lev» → «✏️ Реквизиты».",
            reply_markup=back_to_main_kb(),
        )

    # проверяем баланс звёзд
    current_stars = get_stars_pending(u.id)
    if current_stars < stars_amt:
        return await update.message.reply_text(
            f"Недостаточно звёзд для вывода.\n"
            f"Баланс выигранных звёзд: {current_stars} ⭐.",
            reply_markup=back_to_main_kb(),
        )

    # уменьшаем долг (stars_pending)
    if not sub_stars_pending_safe(u.id, stars_amt):
        return await update.message.reply_text(
            "Не удалось забронировать звёзды для вывода. Попробуй позже.",
            reply_markup=back_to_main_kb(),
        )

    conn = db()
    cur = conn.execute(
        "INSERT INTO star_withdraw_requests(user_id,stars,requisites,status) "
        "VALUES(?,?,?, 'pending')",
        (u.id, stars_amt, saved_req),
    )
    swid = cur.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"⭐ Спасибо! Заявка на вывод звёзд #{swid} создана.\n"
        f"Сумма: {stars_amt} ⭐.\n"
        "После обработки админом звёзды будут отправлены на твой Telegram-аккаунт или по указанным реквизитам.",
        reply_markup=back_to_main_kb(),
    )

    # уведомление админу
    if ADMIN_ID:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"⭐ Новая заявка на вывод Stars #{swid}\n"
                f"Игрок: {display_name(u.id)} (id={u.id})\n"
                f"Сумма: {stars_amt} ⭐\n"
                f"Реквизиты: {saved_req}",
            )
        except Exception:
            pass


# -------------------- ИСТОРИЯ ВЫВОДОВ ДЛЯ ИГРОКА --------------------
async def stars_withdraw_history_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Кнопка '📜 История вывода Stars'
    """
    q = update.callback_query
    await q.answer()

    rows = db().execute(
        "SELECT id, stars, status, created_at, processed_at "
        "FROM star_withdraw_requests "
        "WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (q.from_user.id,),
    ).fetchall()

    if not rows:
        return await delete_and_send_new(
            q,
            "История вывода Stars пуста.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
        )

    lines = ["📜 История вывода Stars:"]
    for r in rows:
        st = r["status"]
        st_ru = {
            "pending": "в процессе",
            "paid": "выплачена",
            "rejected": "отклонена",
        }.get(st, st)
        lines.append(f"#{r['id']}: {r['stars']} ⭐ — {st_ru}")

    await delete_and_send_new(
        q,
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
    )


async def lev_withdraw_history_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Кнопка '📜 История вывода Lev'
    """
    q = update.callback_query
    await q.answer()

    rows = db().execute(
        "SELECT id, lev, status, external_address "
        "FROM withdraw_requests "
        "WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (q.from_user.id,),
    ).fetchall()

    if not rows:
        return await delete_and_send_new(
            q,
            "История вывода Lev пуста.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
        )

    lines = ["📜 История вывода Lev:"]
    for r in rows:
        st_ru = withdraw_status_ru(r["status"])
        lines.append(
            f"#{r['id']}: {r['lev']} Lev → {r['external_address']} — {st_ru}"
        )

    await delete_and_send_new(
        q,
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
    )


# -------------------- ADMIN: ВЫВОД LEV --------------------
async def wlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    rows = db().execute(
        "SELECT * FROM withdraw_requests ORDER BY id DESC LIMIT 20"
    ).fetchall()
    if not rows:
        return await update.message.reply_text("Заявок по Lev нет.", reply_markup=back_to_main_kb())
    lines = ["Последние заявки на вывод Lev:"]
    for r in rows:
        st = withdraw_status_ru(r["status"])
        lines.append(
            f"#{r['id']} | u{r['user_id']} | {r['lev']} Lev | "
            f"{r['external_address']} | {st}"
        )
    await update.message.reply_text("\n".join(lines), reply_markup=back_to_main_kb())


async def wapprove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        return await update.message.reply_text(
            "Использование: /wapprove <id>",
            reply_markup=back_to_main_kb(),
        )
    wid = int(context.args[0])
    tx_id = f"tx_{wid}_{int(time.time())}"
    conn = db()
    cur = conn.execute(
        "UPDATE withdraw_requests "
        "SET status='paid', processed_at=strftime('%s','now'), tx_id=? "
        "WHERE id=? AND status='pending'",
        (tx_id, wid),
    )
    updated = cur.rowcount
    conn.commit()
    conn.close()
    if not updated:
        return await update.message.reply_text(
            "Заявка не найдена или уже обработана.",
            reply_markup=back_to_main_kb(),
        )
    await update.message.reply_text(
        f"✅ Заявка #{wid} по Lev отмечена как выплаченная. TX: {tx_id}",
        reply_markup=back_to_main_kb(),
    )


async def wreject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        return await update.message.reply_text(
            "Использование: /wreject <id> <причина>",
            reply_markup=back_to_main_kb(),
        )
    wid = int(context.args[0])
    reason = " ".join(context.args[1:])[:200]
    conn = db()
    row = conn.execute(
        "SELECT user_id,lev,status FROM withdraw_requests WHERE id=?", (wid,)
    ).fetchone()
    if not row:
        conn.close()
        return await update.message.reply_text(
            "Заявка не найдена.",
            reply_markup=back_to_main_kb(),
        )
    if row["status"] != "pending":
        conn.close()
        return await update.message.reply_text(
            "Заявка уже обработана.",
            reply_markup=back_to_main_kb(),
        )
    conn.execute(
        "UPDATE withdraw_requests "
        "SET status='rejected', processed_at=strftime('%s','now') "
        "WHERE id=?",
        (wid,),
    )
    # возвращаем Lev
    conn.execute(
        "UPDATE players SET lev=lev+? WHERE user_id=?",
        (row["lev"], row["user_id"]),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"❌ Заявка #{wid} по Lev отклонена: {reason}",
        reply_markup=back_to_main_kb(),
    )

# -------------------- АДМИН ПО ЗВЁЗДАМ --------------------
async def stars_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /starslist — показать игроков с ненулевым балансом выигранных звёзд
    вместе с их реквизитами и кнопками для обнуления.
    """
    if not is_admin(update.effective_user.id):
        return

    rows = db().execute(
        """
        SELECT user_id, stars_pending, saved_requisites
        FROM players
        WHERE COALESCE(stars_pending,0) > 0
        ORDER BY stars_pending DESC
        LIMIT 50
        """
    ).fetchall()

    if not rows:
        return await update.message.reply_text(
            "Сейчас нет игроков с выигранными звёздами.",
            reply_markup=back_to_main_kb(),
        )

    total = 0
    lines: list[str] = ["⭐ Выигранные звёзды (долг бота):\n"]
    kb_rows: list[list[InlineKeyboardButton]] = []

    for r in rows:
        uid = r["user_id"]
        stars = r["stars_pending"]
        total += stars
        name = display_name(uid)
        req = r["saved_requisites"] or "—"

        lines.append(f"• {name} — {stars} ⭐")
        lines.append(f"  Реквизиты: {req}\n")

        kb_rows.append(
            [InlineKeyboardButton(
                f"Обнулить {name} ({stars}⭐)",
                callback_data=f"stars_clear:{uid}",
            )]
        )

    lines.append(f"Итого к выплате: {total} ⭐")

    kb_rows.append(
        [InlineKeyboardButton("🏠 В главное меню", callback_data="menu")]
    )

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )


async def stars_clear_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Кнопка 'stars_clear:<uid>' — админ обнуляет баланс выигранных звёзд.
    После обнуления игрок сразу пропадает из списка.
    """
    q = update.callback_query
    await q.answer()

    if not is_admin(q.from_user.id):
        return await q.answer("Нет доступа.", show_alert=True)

    _, uid_str = q.data.split(":")
    uid = int(uid_str)

    # Обнуляем баланс звёзд
    conn = db()
    conn.execute(
        "UPDATE players SET stars_pending = 0 WHERE user_id=?",
        (uid,),
    )
    conn.commit()
    conn.close()

    # Пересобираем список после обнуления
    rows = db().execute(
        """
        SELECT user_id, stars_pending, saved_requisites
        FROM players
        WHERE COALESCE(stars_pending,0) > 0
        ORDER BY stars_pending DESC
        LIMIT 50
        """
    ).fetchall()

    if not rows:
        # Если больше никого нет — показываем, что списки пусты
        return await q.edit_message_text(
            "Все долги по звёздам обнулены.\n"
            "Сейчас нет игроков с выигранными звёздами.",
            reply_markup=back_to_main_kb(),
        )

    total = 0
    lines: list[str] = ["⭐ Выигранные звёзды (долг бота):\n"]
    kb_rows: list[list[InlineKeyboardButton]] = []

    for r in rows:
        r_uid = r["user_id"]
        stars = r["stars_pending"]
        total += stars
        name = display_name(r_uid)
        req = r["saved_requisites"] or "—"

        lines.append(f"• {name} — {stars} ⭐")
        lines.append(f"  Реквизиты: {req}\n")

        kb_rows.append(
            [InlineKeyboardButton(
                f"Обнулить {name} ({stars}⭐)",
                callback_data=f"stars_clear:{r_uid}",
            )]
        )

    lines.append(f"Итого к выплате: {total} ⭐")

    kb_rows.append(
        [InlineKeyboardButton("🏠 В главное меню", callback_data="menu")]
    )

    # Обновляем то же сообщение, чтобы игрок сразу исчез из списка
    await q.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )

    # (опционально) уведомим игрока
    try:
        await context.bot.send_message(
            uid,
            "⭐ Ваш баланс выигранных звёзд был обнулён администратором "
            "(предполагается, что звёзды уже начислены на Telegram-аккаунт).",
            reply_markup=back_to_main_kb(),
        )
    except Exception:
        pass
# -------------------- ADMIN: ВЫВОД STARS --------------------
async def swlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /swlist — список заявок на вывод Stars (по умолчанию только pending).
    """
    if not is_admin(update.effective_user.id):
        return
    status_filter = "pending"
    if context.args:
        # /swlist all  -> показать все
        if context.args[0] == "all":
            status_filter = None

    if status_filter:
        rows = db().execute(
            "SELECT * FROM star_withdraw_requests "
            "WHERE status=? ORDER BY id DESC LIMIT 50",
            (status_filter,),
        ).fetchall()
    else:
        rows = db().execute(
            "SELECT * FROM star_withdraw_requests "
            "ORDER BY id DESC LIMIT 50",
        ).fetchall()

    if not rows:
        return await update.message.reply_text(
            "Заявок на вывод Stars нет.",
            reply_markup=back_to_main_kb(),
        )

    lines = ["Заявки на вывод Stars:"]
    for r in rows:
        st = r["status"]
        st_ru = {
            "pending": "в процессе",
            "paid": "выплачена",
            "rejected": "отклонена",
        }.get(st, st)
        lines.append(
            f"#{r['id']} | u{r['user_id']} | {r['stars']} ⭐ | {st_ru} | {r['requisites']}"
        )

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=back_to_main_kb(),
    )


async def swapprove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /swapprove <id> [комментарий]
    Админ помечает заявку Stars как выплаченную.
    """
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        return await update.message.reply_text(
            "Использование: /swapprove <id> [комментарий]",
            reply_markup=back_to_main_kb(),
        )
    swid = int(context.args[0])
    comment = " ".join(context.args[1:])[:200] if len(context.args) > 1 else ""

    conn = db()
    row = conn.execute(
        "SELECT user_id,stars,status FROM star_withdraw_requests WHERE id=?",
        (swid,),
    ).fetchone()
    if not row:
        conn.close()
        return await update.message.reply_text(
            "Заявка не найдена.",
            reply_markup=back_to_main_kb(),
        )
    if row["status"] != "pending":
        conn.close()
        return await update.message.reply_text(
            "Заявка уже обработана.",
            reply_markup=back_to_main_kb(),
        )

    conn.execute(
        "UPDATE star_withdraw_requests "
        "SET status='paid', processed_at=strftime('%s','now'), comment=? "
        "WHERE id=?",
        (comment, swid),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Заявка Stars #{swid} отмечена как выплаченная.",
        reply_markup=back_to_main_kb(),
    )

    # уведомляем игрока
    try:
        await context.bot.send_message(
            row["user_id"],
            f"⭐ Ваша заявка на вывод звёзд #{swid} выплачена. Спасибо, что играете!",
            reply_markup=back_to_main_kb(),
        )
    except Exception:
        pass


async def swreject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /swreject <id> <причина>
    Отклонить заявку Stars, вернуть звёзды в долг бота.
    """
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        return await update.message.reply_text(
            "Использование: /swreject <id> <причина>",
            reply_markup=back_to_main_kb(),
        )
    swid = int(context.args[0])
    reason = " ".join(context.args[1:])[:200]

    conn = db()
    row = conn.execute(
        "SELECT user_id,stars,status FROM star_withdraw_requests WHERE id=?",
        (swid,),
    ).fetchone()
    if not row:
        conn.close()
        return await update.message.reply_text(
            "Заявка не найдена.",
            reply_markup=back_to_main_kb(),
        )
    if row["status"] != "pending":
        conn.close()
        return await update.message.reply_text(
            "Заявка уже обработана.",
            reply_markup=back_to_main_kb(),
        )

    # помечаем как отклонённую
    conn.execute(
        "UPDATE star_withdraw_requests "
        "SET status='rejected', processed_at=strftime('%s','now'), comment=? "
        "WHERE id=?",
        (reason, swid),
    )
    # возвращаем звёзды в долг (stars_pending)
    conn.commit()
    conn.close()

    add_stars_pending(row["user_id"], row["stars"])

    await update.message.reply_text(
        f"❌ Заявка Stars #{swid} отклонена: {reason}",
        reply_markup=back_to_main_kb(),
    )

    # уведомляем игрока
    try:
        await context.bot.send_message(
            row["user_id"],
            f"❌ Ваша заявка на вывод звёзд #{swid} отклонена.\nПричина: {reason}\n"
            "Звёзды возвращены на ваш баланс выигранных звёзд.",
            reply_markup=back_to_main_kb(),
        )
    except Exception:
        pass
# -------------------- GAME FLOW --------------------
# Отдельная очередь для матчмейкинга в звёздном режиме:
# ключ — "stake:target", значение — список match_id
stars_queue: Dict[str, List[str]] = {}
# Оплаты матчей на звёзды: mid -> set(user_id, которые уже оплатили)
stars_match_payments: Dict[str, set[int]] = {}
# Кредит звёзд: user_id -> сколько Stars пользователь уже заплатил,
# но матч не начался (можно использовать в следующих играх)
stars_credit: Dict[int, int] = defaultdict(int)


def opponent_of(m: Match, uid: int) -> Optional[int]:
    if uid == m.p1:
        return m.p2
    if uid == m.p2:
        return m.p1
    return None


def equal_throws(m: Match) -> bool:
    return m.p2 is not None and m.throws.get(m.p1, 0) == m.throws.get(m.p2, 0)


async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    mode = q.data.split(":")[1]

    # 🔥 Проверка реквизитов — без них нельзя в матчмейкинг и дуэль на Lev
    if mode in ("mm", "friend") and not has_requisites(q.from_user.id):
        return await delete_and_send_new(
            q,
            "‼️ Перед игрой с другими игроками нужно указать реквизиты для вывода (СБП/КАРТА).\n\n"
            "Это нужно, чтобы бот мог отправить тебе выигрыш за звёзды или Lev.\n\n"
            "Укажи реквизиты по формату:\n"
            "1) СБП номер_телефона банк ФИО\n"
            "2) КАРТА номер_карты банк ФИО",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✏️ Ввести реквизиты", callback_data="requisites_menu")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
                ]
            ),
        )

    # Новый поток для дуэли с другом (Lev):
    if mode == "friend":
        context.user_data["await_friend_stake"] = True
        return await delete_and_send_new(
            q,
            "Введи сумму Lev, на которую хочешь сыграть с другом.\n"
            "Пример: <code>50</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]
            ),
        )

    # Остальные режимы сразу переходят к выбору цели
    await delete_and_send_new(
        q,
        f"Режим: <b>{pretty_mode(mode)}</b>\nВыберите до скольких очков:",
        parse_mode=ParseMode.HTML,
        reply_markup=goals_menu(mode),
    )


async def stars_menu_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Подменю '⭐ Матчмейкинг на звёзды' из раздела ИГРАТЬ.
    """
    q = update.callback_query
    await q.answer()

    push_menu(context, "stars_menu")  # важно для кнопки "назад"

    # --- нет реквизитов ---
    if not has_requisites(q.from_user.id):
        text = (
            "‼️ Чтобы играть на реальные Telegram Stars, сначала укажи реквизиты для вывода "
            "(СБП/КАРТА).\n\n"
            "Иначе я не смогу отправить тебе выигрыш.\n\n"
            "Зайди в раздел «✏️ Реквизиты» и укажи данные по формату:\n"
            "1) СБП номер_телефона банк ФИО\n"
            "2) КАРТА номер_карты банк ФИО"
        )

        kb = [
            [InlineKeyboardButton("✏️ Ввести реквизиты", callback_data="requisites_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
        ]
        markup = InlineKeyboardMarkup(kb)

        return await delete_and_send_new(q, text, reply_markup=markup)

    # --- реквизиты есть ---
    text = (
        "⭐ Выберите формат дуэли на звёзды:\n"
        "• Ставка — количество Telegram Stars с каждого игрока.\n"
        "• Победитель забирает весь банк (2× ставка).\n"
        "• Звёзды отображаются как «долг бота» в профиле и выводятся по заявке."
    )

    kb = [
        [InlineKeyboardButton("1 ⭐ · до 6 очков", callback_data="stars_join:1:6")],
        [InlineKeyboardButton("25 ⭐ · до 8 очков", callback_data="stars_join:25:8")],
        [InlineKeyboardButton("50 ⭐ · до 12 очков", callback_data="stars_join:50:12")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
    ]
    markup = InlineKeyboardMarkup(kb)

    await delete_and_send_new(q, text, reply_markup=markup)



async def schedule_turn_timeout(
    mid: str,
    player_id: int,
    turn_started_ts: float,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Таймер на ход: если игрок не успел за TURN_TIMEOUT секунд — тех.поражение.
    """
    await asyncio.sleep(TURN_TIMEOUT)
    m = matches.get(mid)
    if not m or not m.started:
        return
    # ход уже перешёл к другому или был сделан новый бросок
    if m.turn != player_id:
        return
    if m.last_turn_change_ts > turn_started_ts:
        return

    # игрок не сделал ход вовремя → тех.поражение
    loser_id = player_id
    # в тренировке, если вдруг бот — игнорируем
    if m.mode == "train" and loser_id == BOT_ID:
        return

    await finish_timeout_loss(m, loser_id, context)


async def choose_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, mode, t = q.data.split(":")
    target = int(t)

    # ---------- ТРЕНИРОВКА ----------
    if mode == "train":
        mid = secrets.token_hex(6)
        m = Match(
            match_id=mid,
            mode=mode,
            target=target,
            stake=0,
            p1=q.from_user.id,
            p2=BOT_ID,
            score={q.from_user.id: 0, BOT_ID: 0},
            throws={q.from_user.id: 0, BOT_ID: 0},
            started=True,
            turn=q.from_user.id,
            first_throw_done={q.from_user.id: False},
            last_turn_change_ts=time.time(),
        )
        matches[mid] = m
        await q.edit_message_text(
            f"🎓 Тренировка до {target}. Ваш ход — бросайте!",
            reply_markup=None,
        )
        await context.bot.send_message(
            q.from_user.id,
            "Ваш ход! Это ваш 1-й бросок.\n\n"
            "⏱ На ход даётся 1.5 минуты. Не успеешь — поражение по времени.",
            reply_markup=play_controls(mid, first=True),
        )
        # таймер на ход
        asyncio.create_task(
            schedule_turn_timeout(mid, q.from_user.id, m.last_turn_change_ts, context)
        )
        return

    # ---------- PvP-режимы на Lev (mm / friend) ----------
    if mode == "mm":
        stake = DEFAULT_STAKE_LEV
    else:
        # friend — берём пользовательскую ставку
        stake = context.user_data.pop("friend_stake", None)
        if stake is None or stake <= 0:
            stake = DEFAULT_STAKE_LEV

    bal = get_lev(q.from_user.id)
    if bal < stake:
        return await q.edit_message_text(
            f"❗ Не хватает Lev для ставки ({stake}). Ваш баланс: {bal} Lev.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💸 Купить Lev", callback_data="shop")],
                    [InlineKeyboardButton("🏠 В главное меню", callback_data="menu")],
                ]
            ),
        )
    if not sub_lev_safe(q.from_user.id, stake):
        return await q.answer("Не удалось списать ставку", show_alert=True)

    mid = secrets.token_hex(6)
    m = Match(
        match_id=mid,
        mode=mode,
        target=target,
        stake=stake,
        p1=q.from_user.id,
        score={q.from_user.id: 0},
        throws={q.from_user.id: 0},
        started=False,
        first_throw_done={q.from_user.id: False},
        last_turn_change_ts=time.time(),
    )
    matches[mid] = m

    # матчмейкинг Lev
    if mode == "mm":
        mm_queue[target].append(mid)
        await q.edit_message_text(
            f"🎯 Вы в очереди (до {target}). Ставка списана: {stake} Lev. Ждём соперника…",
            reply_markup=back_to_main_kb(),
        )
        asyncio.create_task(
            mm_timeout(mid, target, q.from_user.id, stake)
        )
        await try_matchmaking(target, context)
        return

    # дуэль по ссылке с произвольной ставкой (Lev, friend)
    token = secrets.token_urlsafe(6)
    invites[token] = {
        "creator_id": q.from_user.id,
        "target": target,
        "stake": stake,
        "match_id": mid,
    }
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start=invite_{token}"
    await q.edit_message_text(
        f"🤝 Дуэль до {target}.\n"
        f"Ставка списана: {stake} Lev.\n\n"
        f"Отправь другу эту ссылку:\n{link}\n\n"
        "Как друг подтвердит — матч начнётся.",
        reply_markup=back_to_main_kb(),
    )


async def stars_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Пользователь выбрал формат звёздной дуэли (callback stars_join:stake:target).

    На этом шаге: только ставим игрока в очередь БЕЗ оплаты.
    Оплата произойдёт ПОСЛЕ нахождения соперника.
    """
    q = update.callback_query
    await q.answer()
    _, stake_s, target_s = q.data.split(":")
    stake = int(stake_s)
    target = int(target_s)

    mid = secrets.token_hex(6)
    m = Match(
        match_id=mid,
        mode="stars",
        target=target,
        stake=stake,  # ставка в Telegram Stars с игрока
        p1=q.from_user.id,
        score={q.from_user.id: 0},
        throws={q.from_user.id: 0},
        started=False,
        first_throw_done={q.from_user.id: False},
        last_turn_change_ts=time.time(),
    )
    matches[mid] = m

    key = f"{stake}:{target}"
    stars_queue.setdefault(key, []).append(mid)

    await q.edit_message_text(
        f"⭐ Вы в очереди на дуэль на звёзды.\n"
        f"Ставка: {stake} ⭐ с игрока (банк: {stake * 2} ⭐).\n"
        f"Игра до {target} очков.\n\n"
        "Ждём соперника…",
        reply_markup=back_to_main_kb(),
    )

    # тайм-аут ожидания соперника
    asyncio.create_task(stars_mm_timeout(mid, key, q.from_user.id))
    await try_stars_matchmaking(key, context)


async def mm_timeout(mid: str, target: int, uid: int, stake: int):
    await asyncio.sleep(MATCHMAKING_TIMEOUT)
    m = matches.get(mid)
    if not m or m.p2:
        return
    try:
        mm_queue[target].remove(mid)
    except ValueError:
        pass
    matches.pop(mid, None)
    # возвращаем Lev
    add_lev(uid, stake)


async def stars_mm_timeout(mid: str, key: str, uid: int):
    await asyncio.sleep(MATCHMAKING_TIMEOUT)
    m = matches.get(mid)
    if not m or m.p2:
        return
    lst = stars_queue.get(key, [])
    try:
        lst.remove(mid)
    except ValueError:
        pass
    if not lst:
        stars_queue.pop(key, None)
    matches.pop(mid, None)
    # тут специально без сообщений — тихое снятие с очереди


async def announce_start(context: ContextTypes.DEFAULT_TYPE, m: Match):
    m.started = True
    m.turn = m.p1
    m.last_turn_change_ts = time.time()
    first_name = display_name(m.p1)

    if m.mode == "stars":
        stake_text = f"{m.stake} ⭐"
    else:
        stake_text = f"{m.stake} Lev"

    await context.bot.send_message(
        m.p1,
        f"🔥 Матч начат! До {m.target}. Ставка: {stake_text}.\nПервый ход: {first_name}\n"
        f"Это ваш 1-й бросок.\n\n"
        "⏱ На каждый ход даётся 1.5 минуты. Не успеешь — тех.поражение по времени.",
        reply_markup=play_controls(m.match_id, first=True),
    )
    if m.p2:
        m.score.setdefault(m.p2, 0)
        m.throws.setdefault(m.p2, 0)
        m.first_throw_done.setdefault(m.p2, False)
        await context.bot.send_message(
            m.p2,
            f"🔥 Матч начат! До {m.target}. Ставка: {stake_text}.\nПервый ход: {first_name}\n"
            "⏱ На каждый ход даётся 1.5 минуты.",
            reply_markup=back_to_main_kb(),
        )

    # таймер хода для первого игрока
    asyncio.create_task(
        schedule_turn_timeout(m.match_id, m.p1, m.last_turn_change_ts, context)
    )


async def try_matchmaking(target: int, context: ContextTypes.DEFAULT_TYPE):
    q = mm_queue[target]
    while len(q) >= 2:
        mid1, mid2 = q.pop(0), q.pop(0)
        m1, m2 = matches.get(mid1), matches.get(mid2)
        if not m1 or not m2:
            continue
        m1.p2 = m2.p1
        m1.score[m1.p2] = 0
        m1.throws[m1.p2] = 0
        m1.first_throw_done[m1.p2] = False
        matches.pop(mid2, None)
        await announce_start(context, m1)


async def try_stars_matchmaking(key: str, context: ContextTypes.DEFAULT_TYPE):
    lst = stars_queue.get(key, [])
    while len(lst) >= 2:
        mid1, mid2 = lst.pop(0), lst.pop(0)
        m1, m2 = matches.get(mid1), matches.get(mid2)
        if not m1 or not m2:
            continue

        # формируем пару
        m1.p2 = m2.p1
        m1.score[m1.p2] = 0
        m1.throws[m1.p2] = 0
        m1.first_throw_done[m1.p2] = False
        matches.pop(mid2, None)

        # для этого матча будем отслеживать, кто оплатил
        stars_match_payments[m1.match_id] = set()

        # отправляем обоим запрос на оплату Stars
        await send_stars_payment_request(context, m1)

        # запускаем таймер на оплату (например, 5 минут)
        asyncio.create_task(stars_payment_timeout(m1.match_id, context, timeout=300))

    if not lst:
        stars_queue.pop(key, None)


async def send_stars_payment_request(context: ContextTypes.DEFAULT_TYPE, m: Match):
    """
    Отправляет обоим игрокам:
    - либо счёт на оплату Stars,
    - либо, если есть кредит, использует его вместо счёта.
    """
    stake = m.stake
    target = m.target
    mid = m.match_id

    paid = stars_match_payments.setdefault(mid, set())

    for uid in (m.p1, m.p2):
        if uid is None or uid == BOT_ID:
            continue

        # если у игрока есть кредит и его хватает — используем кредит
        if stars_credit.get(uid, 0) >= stake:
            stars_credit[uid] -= stake
            paid.add(uid)
            try:
                await context.bot.send_message(
                    uid,
                    f"Матч найден! Использован ваш кредит на {stake} ⭐.\n"
                    f"Ожидаем оплату/подтверждение от соперника.",
                    reply_markup=back_to_main_kb(),
                )
            except Exception:
                pass
            continue

        # иначе отправляем invoice на реальные Stars
        token = secrets.token_hex(4)
        payload = f"stars_match_start:{mid}:{uid}:{stake}:{target}:{token}"

        prices = [LabeledPrice(label=f"Дуэль на звёзды до {target}", amount=stake)]

        await context.bot.send_invoice(
            chat_id=uid,
            title=f"Дуэль на звёзды (ставка {stake} ⭐)",
            description=(
                f"Матч найден! Оплата участия: {stake} Telegram Stars.\n"
                f"Игра до {target} очков. Матч начнётся, когда оба игрока оплатят."
            ),
            payload=payload,
            provider_token="",   # для Stars можно оставить пустым
            currency="XTR",
            prices=prices,
            start_parameter="stars_game",
        )

        try:
            await context.bot.send_message(
                uid,
                "Матч найден! Оплатите участие звёздами, чтобы начать игру.\n"
                "Если второй игрок не оплатит вовремя, ваш платёж превратится в кредит.",
                reply_markup=back_to_main_kb(),
            )
        except Exception:
            pass

    # если оба игрока покрылись кредитом и уже считаются оплаченными
    if m.p1 in paid and m.p2 in paid:
        stars_match_payments.pop(mid, None)
        await announce_start(context, m)


async def stars_payment_timeout(mid: str, context: ContextTypes.DEFAULT_TYPE, timeout: int = 300):
    """
    Если оба игрока не оплатили участие в матче на звёзды за timeout секунд,
    матч отменяется. Тем, кто успел оплатить, начисляется кредит.
    """
    await asyncio.sleep(timeout)

    m = matches.get(mid)
    paid = stars_match_payments.get(mid)

    # матч уже удалён или не звёздный — ничего не делаем
    if not m or m.mode != "stars":
        return

    # если матч уже начался — выходим
    if m.started:
        return

    if not paid:
        # никто не оплатил -> просто убираем матч
        matches.pop(mid, None)
        stars_match_payments.pop(mid, None)
        return

    # кто-то оплатил, но не оба -> начисляем кредит оплатившим
    for uid in paid:
        stars_credit[uid] = stars_credit.get(uid, 0) + m.stake
        try:
            await context.bot.send_message(
                uid,
                "Оппонент не оплатил участие в дуэли на звёзды вовремя.\n"
                f"Вам начислен кредит {m.stake} ⭐, его можно использовать в следующей игре.",
                reply_markup=back_to_main_kb(),
            )
        except Exception:
            pass

    # уведомим неоплатившего, если найдём
    for uid in (m.p1, m.p2):
        if uid not in paid:
            try:
                await context.bot.send_message(
                    uid,
                    "Матч на звёзды отменён, так как вы не оплатили участие вовремя.",
                    reply_markup=back_to_main_kb(),
                )
            except Exception:
                pass

    # чистим
    stars_match_payments.pop(mid, None)
    matches.pop(mid, None)


def menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В главное меню", callback_data="menu")]])


async def start_deeplink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start с параметрами (инвайт в дуэль, инвайт в команду) или обычный старт.
    """
    u = update.effective_user
    ensure_player(u)

    # ✅ инициализируем стек навигации
    context.user_data["menu_stack"] = ["menu"]

    if context.args:
        arg = context.args[0]

        # Дуэльное приглашение
        if arg.startswith("invite_"):
            token = arg.split("invite_", 1)[1]
            offer = invites.get(token)
            if not offer:
                return await update.message.reply_text(
                    "Инвайт не найден или устарел.",
                    reply_markup=menu_kb(),
                )

            creator_id = offer["creator_id"]
            target = offer["target"]
            stake = offer["stake"]

            if u.id == creator_id:
                return await update.message.reply_text(
                    "Нельзя принять собственный инвайт.",
                    reply_markup=menu_kb(),
                )

            creator_name = display_name(creator_id)
            text = (
                f"🤝 Приглашение в дуэль до {target} очков.\n"
                f"Ставка: {stake} Lev.\n"
                f"Соперник: {creator_name}\n\n"
                "Вы действительно хотите сыграть?"
            )
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✅ Согласиться", callback_data=f"invite_accept:{token}")],
                    [InlineKeyboardButton("❌ Отказаться", callback_data=f"invite_decline:{token}")],
                    [InlineKeyboardButton("🏠 В главное меню", callback_data="menu")],
                ]
            )
            return await update.message.reply_text(text, reply_markup=kb)

        # приглашение в команду
        if arg.startswith("team_"):
            token = arg.split("team_", 1)[1]
            team_id = team_invites.get(token)
            if not team_id:
                return await update.message.reply_text(
                    "Инвайт в команду не найден или устарел.",
                    reply_markup=menu_kb(),
                )

            if get_user_team(u.id):
                return await update.message.reply_text(
                    "Ты уже состоишь в какой-то команде.",
                    reply_markup=menu_kb(),
                )

            conn = db()
            size_row = conn.execute(
                "SELECT COUNT(*) AS c FROM team_members WHERE team_id=?",
                (team_id,),
            ).fetchone()

            if not size_row or size_row["c"] >= 3:
                conn.close()
                return await update.message.reply_text(
                    "В команде уже 3 игрока. Места нет.",
                    reply_markup=menu_kb(),
                )

            conn.execute(
                "INSERT OR IGNORE INTO team_members(team_id,user_id) VALUES(?,?)",
                (team_id, u.id),
            )
            conn.execute(
                "UPDATE players SET team_id=? WHERE user_id=?",
                (team_id, u.id),
            )
            conn.commit()
            conn.close()

            team = db().execute("SELECT name FROM teams WHERE id=?", (team_id,)).fetchone()
            return await update.message.reply_text(
                f"🎉 Ты вступил в команду «{team['name']}»!",
                reply_markup=main_menu(u.id),
            )

    # обычный старт
    return await start(update, context)


# ---------- THROW LOGIC WITH TIMEOUT + ВИДИМЫЕ БРОСКИ СОПЕРНИКА ----------
async def throw_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, mid = q.data.split(":")
    m = matches.get(mid)
    if not m:
        return await q.answer("Матч уже завершён.", show_alert=True)
    if not m.started:
        return await q.answer("Матч ещё не начался или уже завершён.", show_alert=True)

    uid = q.from_user.id
    if uid not in m.score:
        return await q.answer("Вы не участник этого матча.", show_alert=True)
    if m.mode != "train" and m.turn != uid:
        return await q.answer("Сейчас не ваш ход.", show_alert=True)

    # Бросок текущим игроком
    sent: Message = await context.bot.send_dice(
        chat_id=q.message.chat_id, emoji="🏀"
    )
    val = sent.dice.value
    gained = LEV_SCORING.get(val, 0)
    m.score[uid] = m.score.get(uid, 0) + gained
    m.throws[uid] = m.throws.get(uid, 0) + 1
    m.first_throw_done[uid] = True
    # обновляем время последнего действия для текущего хода
    m.last_turn_change_ts = time.time()
    await asyncio.sleep(2.0)

    # информация для бросившего
    your_score = m.score[uid]
    remaining = max(0, m.target - your_score)
    throw_num = m.throws[uid]

    if remaining > 0:
        if remaining <= 3:
            motivation = f"Осталось всего {remaining} очк. до победы — жми! 💪"
        else:
            motivation = f"До победы осталось {remaining} очк."
    else:
        motivation = "Вы достигли или превысили цель по очкам!"

    score_text = (
        f"+{gained} очк. | Счёт {m.score.get(m.p1, 0)}–{m.score.get(m.p2, 0)} (до {m.target}).\n"
        f"Это ваш {throw_num}-й бросок.\n"
        f"{motivation}"
    )
    await context.bot.send_message(q.message.chat_id, score_text)

    # 🔔 Показываем бросок соперника — уведомление второму игроку
    if m.mode not in ("train",):
        opp_id = opponent_of(m, uid)
        if opp_id:
            await context.bot.send_message(
                opp_id,
                f"{display_name(uid)} сделал бросок.\n"
                f"Выпало: {val} (это +{gained} очк.).\n"
                f"Текущий счёт: {m.score.get(m.p1, 0)}–{m.score.get(m.p2, 0)} (до {m.target}).",
            )

    # ---------- ТРЕНИРОВКА: ход бота ----------
    if m.mode == "train":
        if not equal_throws(m):
            await asyncio.sleep(1.2)
            bot_msg: Message = await context.bot.send_dice(
                chat_id=q.message.chat_id, emoji="🏀"
            )
            bval = bot_msg.dice.value
            bgain = LEV_SCORING.get(bval, 0)
            m.score[BOT_ID] += bgain
            m.throws[BOT_ID] += 1
            await asyncio.sleep(2.0)
            await context.bot.send_message(
                q.message.chat_id,
                f"+{bgain} очк. (бот) | Счёт {m.score.get(m.p1, 0)}–{m.score.get(m.p2, 0)} (до {m.target}).",
            )

        if equal_throws(m) and (
            m.score[m.p1] >= m.target or m.score[m.p2] >= m.target
        ):
            try:
                await q.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            if m.score[m.p1] >= m.target and m.score[m.p2] >= m.target:
                await finish_draw(m, context)
            else:
                winner = m.p1 if m.score[m.p1] >= m.target else m.p2
                await finish_match(m, winner, context)
            return

        # иначе снова ход игрока
        next_num = m.throws.get(m.p1, 0) + 1
        await context.bot.send_message(
            q.message.chat_id,
            f"Ваш ход! Это ваш {next_num}-й бросок.\n"
            "⏱ На ход 1.5 минуты.",
            reply_markup=play_controls(
                m.match_id, first=not m.first_throw_done.get(m.p1, False)
            ),
        )
        # таймер на следующий ход (только человек)
        m.last_turn_change_ts = time.time()
        asyncio.create_task(
            schedule_turn_timeout(m.match_id, m.p1, m.last_turn_change_ts, context)
        )
        return

    # ---------- PvP: смена хода ----------
    m.turn = m.p2 if uid == m.p1 else m.p1
    m.last_turn_change_ts = time.time()

    # Проверка конца матча при равных бросках
    if equal_throws(m) and (
        m.score[m.p1] >= m.target or m.score[m.p2] >= m.target
    ):
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        if m.score[m.p1] >= m.target and m.score[m.p2] >= m.target:
            await finish_draw(m, context)
        else:
            winner = m.p1 if m.score[m.p1] >= m.target else m.p2
            await finish_match(m, winner, context)
        return

    # иначе ход соперника
    next_player = m.turn
    next_num = m.throws.get(next_player, 0) + 1
    await context.bot.send_message(
        next_player,
        f"Сейчас твой ход, {display_name(next_player)}! "
        f"Это твой {next_num}-й бросок.\n"
        "⏱ На ход 1.5 минуты.",
        reply_markup=play_controls(
            m.match_id, first=not m.first_throw_done.get(next_player, False)
        ),
    )
    # таймер хода для соперника
    asyncio.create_task(
        schedule_turn_timeout(
            m.match_id, next_player, m.last_turn_change_ts, context
        )
    )
# ---------- FINISH MATCH ----------
# ---------- SAVE LAST MATCH + TOURNAMENT STATS ----------

def _save_last_match(
    uid: int,
    m: Match,
    *,
    you_score: int,
    opp_score: int,
    result: str,
    delta_lev: int,
    opp_id: int,
):
    """
    Сохранить информацию о последнем матче игрока (для профиля и реванша).
    """
    data = {
        "ts": int(time.time()),
        "mode": m.mode,
        "mode_human": pretty_mode(m.mode),
        "target": m.target,
        "stake": m.stake,
        "you_score": you_score,
        "opp_score": opp_score,
        "result": result,        # "win" / "loss" / "draw" / "timeout_win" / "timeout_loss"
        "delta_lev": delta_lev,  # +Lev / -Lev / 0
        "opponent_id": opp_id,
        "opponent_nick": display_name(opp_id),
    }
    conn = db()
    conn.execute(
        "UPDATE players SET last_match_json=? WHERE user_id=?",
        (json.dumps(data, ensure_ascii=False), uid),
    )
    conn.commit()
    conn.close()


def _update_tournament_stats(m: Match, winner_id: int, loser_id: int):
    """
    Обновление таблиц турнира (только для матчей на Lev: mm / friend).
    Звёздные матчи в турнир не засчитываются.
    """
    now = int(time.time())
    if now > TOURNAMENT_DEADLINE_TS:
        return

    if m.mode not in ("mm", "friend"):
        return

    conn = db()

    # Одиночный турнир
    for uid, is_win in ((winner_id, True), (loser_id, False)):
        row = conn.execute(
            "SELECT wins, losses FROM tournament_solo WHERE user_id=?",
            (uid,),
        ).fetchone()
        if not row:
            wins = 1 if is_win else 0
            losses = 0 if is_win else 1
            conn.execute(
                "INSERT INTO tournament_solo(user_id, wins, losses) VALUES(?,?,?)",
                (uid, wins, losses),
            )
        else:
            wins = row["wins"]
            losses = row["losses"]
            if is_win:
                wins += 1
            else:
                losses += 1
            conn.execute(
                "UPDATE tournament_solo SET wins=?, losses=? WHERE user_id=?",
                (wins, losses, uid),
            )

    conn.commit()
    conn.close()
async def finish_match(m: Match, winner_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    Обычная победа (не по времени).
    Обрабатывает 3 режима: train / stars / lev (mm & friend)
    """

    # ---- helpers ----
    def s(uid: int) -> int:
        return int(m.score.get(uid, 0) or 0)

    def loser_of(wid: int) -> Optional[int]:
        if m.p1 is None or m.p2 is None:
            return None
        return m.p2 if wid == m.p1 else m.p1

    async def safe_send(uid: int, text: str, reply_markup=None):
        try:
            await context.bot.send_message(uid, text, reply_markup=reply_markup)
        except Exception:
            pass

    # --- ТРЕНИРОВКА ---
    if m.mode == "train":
        human_id = m.p1
        bot_id = m.p2 if m.p2 is not None else BOT_ID

        human_score = s(human_id)
        bot_score = s(bot_id)

        _save_last_match(
            human_id,
            m,
            you_score=human_score,
            opp_score=bot_score,
            result="win" if winner_id == human_id else "loss",
            delta_lev=0,
            opp_id=bot_id,
        )

        text = (
            f"🎉 Тренировка завершена!\n"
            f"Счёт {human_score}–{bot_score} (до {m.target}).\n"
            "Отличная игра!"
        )

        await safe_send(human_id, text, reply_markup=end_controls(m.match_id, draw=False))
        matches.pop(m.match_id, None)
        return

    # если это PvP, но по какой-то причине второго игрока нет — просто завершаем
    if m.p2 is None:
        matches.pop(m.match_id, None)
        return

    loser_id = loser_of(winner_id)
    if loser_id is None:
        matches.pop(m.match_id, None)
        return

    # --- STARS MODE ---
    if m.mode == "stars":
        pot_stars = int(m.stake) * 2

        # начисляем "долг" победителю
        add_stars_pending(winner_id, pot_stars)

        # сохраняем last_match
        _save_last_match(
            winner_id,
            m,
            you_score=s(winner_id),
            opp_score=s(loser_id),
            result="win",
            delta_lev=0,
            opp_id=loser_id,
        )
        _save_last_match(
            loser_id,
            m,
            you_score=s(loser_id),
            opp_score=s(winner_id),
            result="loss",
            delta_lev=0,
            opp_id=winner_id,
        )

        # +1 матч сыгранный для обоих
        conn = db()
        conn.execute(
            "UPDATE players SET matches_played=COALESCE(matches_played,0)+1 "
            "WHERE user_id IN (?,?)",
            (winner_id, loser_id),
        )
        conn.commit()
        conn.close()

        maybe_send_timeout_reminder(winner_id, context)
        maybe_send_timeout_reminder(loser_id, context)

        winner_msg = (
            "🎉 Победа в дуэли на звёзды!\n"
            f"Счёт: {s(m.p1)}–{s(m.p2)} (до {m.target}).\n"
            f"Вы выиграли {pot_stars} ⭐.\n\n"
            "Звёзды начислены в баланс «долг бота» (см. профиль)."
        )
        loser_msg = (
            "💪 Хорошая игра!\n"
            f"Счёт: {s(m.p1)}–{s(m.p2)} (до {m.target}).\n"
            "В этот раз победа за соперником."
        )

        kb = end_controls(m.match_id, draw=False)
        await safe_send(winner_id, winner_msg, reply_markup=kb)
        await safe_send(loser_id, loser_msg, reply_markup=kb)

        matches.pop(m.match_id, None)
        return

    # --- режим Lev PvP (mm / friend) ---
    pot = int(m.stake) * 2
    add_lev(winner_id, pot)

    delta_win = int(m.stake)
    delta_lose = -int(m.stake)

    # обновляем статистику
    conn = db()
    conn.execute(
        "UPDATE players SET rating=rating+10, wins=wins+1, "
        "matches_played=COALESCE(matches_played,0)+1 "
        "WHERE user_id=?",
        (winner_id,),
    )
    conn.execute(
        "UPDATE players SET rating=MAX(800, rating-8), losses=losses+1, "
        "matches_played=COALESCE(matches_played,0)+1 "
        "WHERE user_id=?",
        (loser_id,),
    )
    conn.commit()
    conn.close()

    _save_last_match(
        winner_id,
        m,
        you_score=s(winner_id),
        opp_score=s(loser_id),
        result="win",
        delta_lev=delta_win,
        opp_id=loser_id,
    )
    _save_last_match(
        loser_id,
        m,
        you_score=s(loser_id),
        opp_score=s(winner_id),
        result="loss",
        delta_lev=delta_lose,
        opp_id=winner_id,
    )

    _update_tournament_stats(m, winner_id, loser_id)

    maybe_send_timeout_reminder(winner_id, context)
    maybe_send_timeout_reminder(loser_id, context)

    winner_balance = get_lev(winner_id)

    winner_msg = (
        "🎉 Великолепно! Вы победили!\n"
        f"Итог: {s(m.p1)}–{s(m.p2)} (до {m.target}).\n"
        f"+{delta_win} Lev! Баланс: {winner_balance} Lev."
    )
    loser_msg = (
        "💪 Хорошая игра!\n"
        f"Итог: {s(m.p1)}–{s(m.p2)} (до {m.target})."
    )

    kb = end_controls(m.match_id, draw=False)
    await safe_send(winner_id, winner_msg, reply_markup=kb)
    await safe_send(loser_id, loser_msg, reply_markup=kb)

    matches.pop(m.match_id, None)
    await check_tournaments_maybe_finish(context)


# ---------- DRAW ----------
async def finish_draw(m: Match, context: ContextTypes.DEFAULT_TYPE):
    """
    Ничья — одинаковая логика для всех режимов.
    """

    def s(uid: int) -> int:
        return int(m.score.get(uid, 0) or 0)

    async def safe_send(uid: int, text: str, reply_markup=None):
        try:
            await context.bot.send_message(uid, text, reply_markup=reply_markup)
        except Exception:
            pass

    # ---- тренировка ----
    if m.mode == "train":
        human_id = m.p1
        bot_id = m.p2 if m.p2 is not None else BOT_ID

        _save_last_match(
            human_id,
            m,
            you_score=s(human_id),
            opp_score=s(bot_id),
            result="draw",
            delta_lev=0,
            opp_id=bot_id,
        )

        text = (
            f"🤝 Ничья в тренировке! Счёт {s(human_id)}–{s(bot_id)}.\n"
            "Отличная борьба!"
        )
        await safe_send(human_id, text, reply_markup=end_controls(m.match_id, draw=True))
        matches.pop(m.match_id, None)
        return

    # ---- PvP: если второго игрока нет — просто чистим матч ----
    if m.p2 is None:
        matches.pop(m.match_id, None)
        return

    p1, p2 = m.p1, m.p2

    # last_match для обоих
    _save_last_match(
        p1, m,
        you_score=s(p1),
        opp_score=s(p2),
        result="draw",
        delta_lev=0,
        opp_id=p2,
    )
    _save_last_match(
        p2, m,
        you_score=s(p2),
        opp_score=s(p1),
        result="draw",
        delta_lev=0,
        opp_id=p1,
    )

    # матчи сыграны +1
    conn = db()
    conn.execute(
        "UPDATE players SET matches_played=COALESCE(matches_played,0)+1 "
        "WHERE user_id IN (?,?)",
        (p1, p2),
    )
    conn.commit()
    conn.close()

    maybe_send_timeout_reminder(p1, context)
    maybe_send_timeout_reminder(p2, context)

    if m.mode == "stars":
        text = (
            f"🤝 Ничья! Счёт {s(p1)}–{s(p2)} (до {m.target}).\n"
            "Ни у кого нет выигрышных ⭐ — можно взять реванш!"
        )
    else:
        text = f"🤝 Ничья! Счёт {s(p1)}–{s(p2)} (до {m.target})."

    kb = end_controls(m.match_id, draw=True)
    await safe_send(p1, text, reply_markup=kb)
    await safe_send(p2, text, reply_markup=kb)

    matches.pop(m.match_id, None)
    await check_tournaments_maybe_finish(context)



# ---------- TIMEOUT LOSS ----------
async def finish_timeout_loss(m: Match, loser_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    Техническое поражение по времени.
    """

    def s(uid: int) -> int:
        return int(m.score.get(uid, 0) or 0)

    async def safe_send(uid: int, text: str, reply_markup=None):
        try:
            await context.bot.send_message(uid, text, reply_markup=reply_markup)
        except Exception:
            pass

    # ---- тренировка ----
    if m.mode == "train":
        human_id = m.p1
        if loser_id != human_id:
            return  # бот не проигрывает по времени

        bot_id = m.p2 if m.p2 is not None else BOT_ID

        _save_last_match(
            human_id, m,
            you_score=s(human_id),
            opp_score=s(bot_id),
            result="timeout_loss",
            delta_lev=0,
            opp_id=bot_id,
        )

        await safe_send(
            human_id,
            "⏱ Время истекло — техническое поражение в тренировке.",
            reply_markup=end_controls(m.match_id, draw=False),
        )
        matches.pop(m.match_id, None)
        return

    # ---- PvP: если второго игрока нет — чистим матч ----
    if m.p2 is None:
        matches.pop(m.match_id, None)
        return

    # определяем победителя
    winner_id = m.p2 if loser_id == m.p1 else m.p1

    # ---- stars ----
    if m.mode == "stars":
        pot_stars = int(m.stake) * 2
        add_stars_pending(winner_id, pot_stars)

        _save_last_match(
            winner_id, m,
            you_score=s(winner_id),
            opp_score=s(loser_id),
            result="timeout_win",
            delta_lev=0,
            opp_id=loser_id,
        )
        _save_last_match(
            loser_id, m,
            you_score=s(loser_id),
            opp_score=s(winner_id),
            result="timeout_loss",
            delta_lev=0,
            opp_id=winner_id,
        )

        conn = db()
        conn.execute(
            "UPDATE players SET matches_played=COALESCE(matches_played,0)+1 "
            "WHERE user_id IN (?,?)",
            (winner_id, loser_id),
        )
        conn.commit()
        conn.close()

        maybe_send_timeout_reminder(winner_id, context)
        maybe_send_timeout_reminder(loser_id, context)

        kb = end_controls(m.match_id, draw=False)

        await safe_send(
            winner_id,
            "🎉 Победа по времени в дуэли на звёзды!\n"
            f"Вы выиграли {pot_stars} ⭐.",
            reply_markup=kb,
        )
        await safe_send(
            loser_id,
            "⏱ Вы не успели сделать ход. Техническое поражение.",
            reply_markup=kb,
        )

        matches.pop(m.match_id, None)
        return

    # ---- Lev матч (mm/friend) ----
    pot = int(m.stake) * 2
    add_lev(winner_id, pot)

    delta_win = int(m.stake)
    delta_lose = -int(m.stake)

    conn = db()
    conn.execute(
        "UPDATE players SET rating=rating+10, wins=wins+1, "
        "matches_played=COALESCE(matches_played,0)+1 "
        "WHERE user_id=?",
        (winner_id,),
    )
    conn.execute(
        "UPDATE players SET rating=MAX(800, rating-8), losses=losses+1, "
        "matches_played=COALESCE(matches_played,0)+1 "
        "WHERE user_id=?",
        (loser_id,),
    )
    conn.commit()
    conn.close()

    _save_last_match(
        winner_id, m,
        you_score=s(winner_id),
        opp_score=s(loser_id),
        result="timeout_win",
        delta_lev=delta_win,
        opp_id=loser_id,
    )
    _save_last_match(
        loser_id, m,
        you_score=s(loser_id),
        opp_score=s(winner_id),
        result="timeout_loss",
        delta_lev=delta_lose,
        opp_id=winner_id,
    )

    _update_tournament_stats(m, winner_id, loser_id)

    maybe_send_timeout_reminder(winner_id, context)
    maybe_send_timeout_reminder(loser_id, context)

    kb = end_controls(m.match_id, draw=False)

    await safe_send(
        winner_id,
        f"🎉 Победа по времени!\n+{delta_win} Lev!",
        reply_markup=kb,
    )
    await safe_send(
        loser_id,
        "⏱ Время на ход истекло — техническое поражение.",
        reply_markup=kb,
    )

    matches.pop(m.match_id, None)
    await check_tournaments_maybe_finish(context)



# ---------- REMATCH OFFER ----------
async def rematch_offer_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Нажатие кнопки «Взять реванш»
    """
    q = update.callback_query
    await q.answer()
    # mid нам не нужен, оставляем для совместимости с callback_data
    try:
        _, _mid = q.data.split(":")
    except Exception:
        _mid = ""

    row = get_player(q.from_user.id)
    if not row or not row["last_match_json"]:
        return await q.answer("Нет данных последнего матча.", show_alert=True)

    try:
        lm = json.loads(row["last_match_json"])
        mode = str(lm.get("mode", ""))
        target = int(lm.get("target", 0) or 0)
        stake = int(lm.get("stake", 0) or 0)
        opponent_id = int(lm.get("opponent_id", 0) or 0)
    except Exception:
        return await q.answer("Ошибка данных последнего матча.", show_alert=True)

    # базовая валидация
    if target <= 0:
        return await q.answer("Некорректная цель матча.", show_alert=True)

    # если соперник некорректный — не пытаемся отправлять
    if opponent_id in (0, None) or opponent_id == q.from_user.id:
        # тренировка/бот тоже сюда попадёт — ниже обработаем
        pass

    # --- ТРЕНИРОВКА / БОТ ---
    if mode == "train" or opponent_id == BOT_ID:
        mid = secrets.token_hex(6)
        m = Match(
            match_id=mid,
            mode="train",
            target=target,
            stake=0,
            p1=q.from_user.id,
            p2=BOT_ID,
            score={q.from_user.id: 0, BOT_ID: 0},
            throws={q.from_user.id: 0, BOT_ID: 0},
            started=True,
            turn=q.from_user.id,
            first_throw_done={q.from_user.id: False},
            last_turn_change_ts=time.time(),
        )
        matches[mid] = m

        # edit может упасть если исходное сообщение было фото/подпись
        try:
            await q.edit_message_text(f"🎓 Тренировка до {target}. Ваш ход!", reply_markup=None)
        except Exception:
            try:
                await q.message.reply_text(f"🎓 Тренировка до {target}. Ваш ход!")
            except Exception:
                pass

        await context.bot.send_message(
            q.from_user.id,
            "Это ваш 1-й бросок.\n⏱ 1.5 мин на ход.",
            reply_markup=play_controls(mid, first=True),
        )
        asyncio.create_task(
            schedule_turn_timeout(mid, q.from_user.id, m.last_turn_change_ts, context)
        )
        return

    # если соперник отсутствует/битый — сообщаем
    if opponent_id in (0, None):
        return await q.answer("Не удалось найти соперника для реванша.", show_alert=True)

    # --- STARS REMATCH ---
    if mode == "stars":
        token = secrets.token_urlsafe(6)
        rematch_offers[token] = {
            "from": q.from_user.id,
            "to": opponent_id,
            "target": target,
            "stake": stake,   # ставка в ⭐ из last_match
            "mode": "stars",
        }

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Принять", callback_data=f"rematch_accept:{token}")],
                [InlineKeyboardButton("❌ Отказаться", callback_data=f"rematch_decline:{token}")],
            ]
        )

        # важный момент: send_message сопернику может упасть
        try:
            await context.bot.send_message(
                opponent_id,
                f"🔁 Реванш в звёздной дуэли!\nДо {target}, ставка {stake} ⭐.\n"
                f"Инициатор: {display_name(q.from_user.id)}",
                reply_markup=kb,
            )
        except Exception:
            rematch_offers.pop(token, None)
            return await q.answer(
                "Не удалось отправить сопернику запрос (возможно он заблокировал бота).",
                show_alert=True,
            )

        # подтверждение инициатору (edit или reply)
        try:
            await q.edit_message_text(
                "✅ Запрос на реванш отправлен сопернику.",
                reply_markup=back_to_main_kb(),
            )
        except Exception:
            try:
                await q.message.reply_text(
                    "✅ Запрос на реванш отправлен сопернику.",
                    reply_markup=back_to_main_kb(),
                )
            except Exception:
                pass
        return

    # --- LEV REMATCH (friend) ---
    token = secrets.token_urlsafe(6)
    rematch_offers[token] = {
        "from": q.from_user.id,
        "to": opponent_id,
        "target": target,
        "stake": stake,
        "mode": "friend",
    }

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Принять", callback_data=f"rematch_accept:{token}")],
            [InlineKeyboardButton("❌ Отказаться", callback_data=f"rematch_decline:{token}")],
        ]
    )

    try:
        await context.bot.send_message(
            opponent_id,
            f"🔁 Реванш!\nДо {target}, ставка {stake} Lev.\n"
            f"Инициатор: {display_name(q.from_user.id)}",
            reply_markup=kb,
        )
    except Exception:
        rematch_offers.pop(token, None)
        return await q.answer(
            "Не удалось отправить сопернику запрос (возможно он заблокировал бота).",
            show_alert=True,
        )

    try:
        await q.edit_message_text(
            "✅ Запрос на реванш отправлен сопернику.",
            reply_markup=back_to_main_kb(),
        )
    except Exception:
        try:
            await q.message.reply_text(
                "✅ Запрос на реванш отправлен сопернику.",
                reply_markup=back_to_main_kb(),
            )
        except Exception:
            pass

# ---------- ACCEPT REMATCH ----------
async def rematch_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, token = q.data.split(":")
    offer = rematch_offers.pop(token, None)

    if not offer or offer["to"] != q.from_user.id:
        return await q.answer("Запрос неактуален.", show_alert=True)

    p_from = offer["from"]
    p_to = offer["to"]
    target = offer["target"]
    stake = offer["stake"]
    mode = offer["mode"]

    # STARS REMATCH — без списания Lev
    if mode == "stars":
        mid = secrets.token_hex(6)
        m = Match(
            match_id=mid,
            mode="stars",
            target=target,
            stake=stake,
            p1=p_from,
            p2=p_to,
            score={p_from: 0, p_to: 0},
            throws={p_from: 0, p_to: 0},
            started=True,
            turn=p_from,
            first_throw_done={p_from: False, p_to: False},
            last_turn_change_ts=time.time(),
        )
        matches[mid] = m

        first_name = display_name(p_from)

        await context.bot.send_message(
            p_from,
            f"🔥 Реванш (⭐) начат! До {target}. Ставка {stake} ⭐.\n"
            f"Первый ход: {first_name}",
            reply_markup=play_controls(mid, first=True),
        )
        await context.bot.send_message(
            p_to,
            f"🔥 Реванш (⭐) начат! До {target}. Ставка {stake} ⭐.\n"
            f"Первый ход: {first_name}",
            reply_markup=back_to_main_kb(),
        )

        asyncio.create_task(
            schedule_turn_timeout(mid, p_from, m.last_turn_change_ts, context)
        )

        return await q.edit_message_text("Реванш принят.", reply_markup=back_to_main_kb())

    # ――― Lev реванш ―――
    # списываем ставки с обоих
    if stake > 0:
        if not sub_lev_safe(p_from, stake):
            await context.bot.send_message(
                p_from, "Недостаточно Lev для реванша.", reply_markup=back_to_main_kb()
            )
            return await q.edit_message_text(
                "У соперника недостаточно Lev.", reply_markup=back_to_main_kb()
            )
        if not sub_lev_safe(p_to, stake):
            add_lev(p_from, stake)
            await context.bot.send_message(
                p_to, "Недостаточно Lev для реванша.", reply_markup=back_to_main_kb()
            )
            return await q.edit_message_text("Недостаточно Lev.", reply_markup=back_to_main_kb())

    mid = secrets.token_hex(6)
    m = Match(
        match_id=mid,
        mode="friend",
        target=target,
        stake=stake,
        p1=p_from,
        p2=p_to,
        score={p_from: 0, p_to: 0},
        throws={p_from: 0, p_to: 0},
        started=True,
        turn=p_from,
        first_throw_done={p_from: False, p_to: False},
        last_turn_change_ts=time.time(),
    )
    matches[mid] = m

    first_name = display_name(p_from)

    await context.bot.send_message(
        p_from,
        f"🔥 Реванш начат! До {target}. Ставка {stake} Lev.\n"
        f"Первый ход: {first_name}",
        reply_markup=play_controls(mid, first=True),
    )
    await context.bot.send_message(
        p_to,
        f"🔥 Реванш начат! До {target}. Ставка {stake} Lev.\n"
        f"Первый ход: {first_name}",
        reply_markup=back_to_main_kb(),
    )

    asyncio.create_task(
        schedule_turn_timeout(mid, p_from, m.last_turn_change_ts, context)
    )

    await q.edit_message_text("Реванш принят.", reply_markup=back_to_main_kb())


# ---------- DECLINE REMATCH ----------
async def rematch_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, token = q.data.split(":")
    offer = rematch_offers.pop(token, None)

    if not offer:
        return await q.answer("Запрос устарел.", show_alert=True)

    from_id = offer["from"]

    try:
        await context.bot.send_message(
            from_id,
            "Оппонент отказался от реванша.",
            reply_markup=back_to_main_kb(),
        )
    except Exception:
        pass

    await q.edit_message_text("Вы отказались от реванша.", reply_markup=back_to_main_kb())


# ---------- INVITE ACCEPT ----------
async def invite_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, token = q.data.split(":")
    offer = invites.get(token)

    if not offer:
        return await q.edit_message_text("Инвайт неактуален.", reply_markup=back_to_main_kb())

    creator_id = offer["creator_id"]
    target = offer["target"]
    stake = offer["stake"]
    mid = offer["match_id"]
    opponent_id = q.from_user.id

    if opponent_id == creator_id:
        return await q.answer("Нельзя принять свой инвайт.", show_alert=True)

    # списываем Lev у принимающего
    if not sub_lev_safe(opponent_id, stake):
        return await q.edit_message_text(
            f"Недостаточно Lev для участия. Нужно {stake}.",
            reply_markup=back_to_main_kb(),
        )

    m = matches.get(mid)
    if not m or m.p2 is not None:
        add_lev(opponent_id, stake)  # вернуть списанное
        invites.pop(token, None)
        return await q.edit_message_text("Матч неактуален.", reply_markup=back_to_main_kb())

    m.p2 = opponent_id
    m.score[opponent_id] = 0
    m.throws[opponent_id] = 0
    m.first_throw_done[opponent_id] = False

    invites.pop(token, None)

    await q.edit_message_text("Вы приняли приглашение. Матч начинается!", reply_markup=back_to_main_kb())
    await announce_start(context, m)


# ---------- INVITE DECLINE ----------
async def invite_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, token = q.data.split(":")
    offer = invites.pop(token, None)

    if offer:
        add_lev(offer["creator_id"], offer["stake"])
        mid = offer["match_id"]
        matches.pop(mid, None)
        try:
            await context.bot.send_message(
                offer["creator_id"],
                "Оппонент отказался от дуэли. Ставка возвращена.",
                reply_markup=back_to_main_kb(),
            )
        except Exception:
            pass

    await q.edit_message_text("Вы отказались от дуэли.", reply_markup=back_to_main_kb())
# -------------------- TEAMS & TOURNAMENTS --------------------

async def cmd_teams_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👥 Команды:\n\n"
        "• Создай свою команду.\n"
        "• Приглашай друзей по ссылки.\n"
        "• До 3 игроков в команде.\n"
        "• Смотри профиль своей команды и выходи из неё при желании.",
        reply_markup=back_to_main_kb(),
    )


async def cmd_tournaments_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 Турниры:\n\n"
        "• Одиночный турнир — учитываются победы.\n"
        "• Командный турнир — учитываются победы игроков команды.\n"
        "• Призы и сроки смотри в /rules.",
        reply_markup=back_to_main_kb(),
    )


async def team_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    team = get_user_team(q.from_user.id)

    if team:
        kb = [
            [InlineKeyboardButton("📘 Профиль команды", callback_data="team_profile_self")],
            [InlineKeyboardButton("➕ Пригласить в команду", callback_data="team_invite")],
            [InlineKeyboardButton("🚪 Выйти из команды", callback_data="team_leave_confirm")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
        ]
        text = f"👥 Ваша команда: «{team['name']}»"
    else:
        kb = [
            [InlineKeyboardButton("🎉 Создать команду", callback_data="team_create_start")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
        ]
        text = "У тебя пока нет команды."

    markup = InlineKeyboardMarkup(kb)

    await delete_and_send_new(q, text, reply_markup=markup)


async def create_team_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало создания команды из главного меню.
    """
    q = update.callback_query
    await q.answer()
    
    # Проверяем, есть ли уже команда
    team = get_user_team(q.from_user.id)
    if team:
        return await delete_and_send_new(
            q,
            f"Ты уже состоишь в команде «{team['name']}».\n"
            "Сначала выйди из неё, чтобы создать новую.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
        )
    
    context.user_data["await_team_name"] = True
    await delete_and_send_new(
        q,
        "<b>🏆 Создание команды для Командного турнира</b>\n\n"
        "Команда может состоять из <b>3 игроков максимум</b>.\n"
        "В командном турнире учитываются очки всех участников команды.\n\n"
        "Введи название команды:\n"
        "• От 3 до 40 символов\n"
        "• Только латинские буквы, цифры и подчёркивание\n\n"
        "<i>Пример: MyDreamTeam</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("↩️ Отмена", callback_data="menu")]]
        ),
    )


async def team_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старая функция для совместимости"""
    return await create_team_start(update, context)


async def my_team_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Меню моей команды с информацией о турнире.
    """
    q = update.callback_query
    await q.answer()
    
    team = get_user_team(q.from_user.id)
    if not team:
        return await delete_and_send_new(
            q,
            "Ты не состоишь ни в одной команде.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
        )
    
    # Получаем участников команды с их турнирными очками
    members_rows = db().execute(
        "SELECT p.user_id, p.username, p.first_name, tm.tournament_points "
        "FROM team_members tm "
        "JOIN players p ON p.user_id=tm.user_id "
        "WHERE tm.team_id=? ORDER BY tm.tournament_points DESC",
        (team["id"],),
    ).fetchall()
    
    # Получаем место команды в турнире
    all_teams = db().execute(
        "SELECT id, name, tournament_points FROM teams "
        "ORDER BY tournament_points DESC"
    ).fetchall()
    
    team_position = 0
    for i, t in enumerate(all_teams, start=1):
        if t["id"] == team["id"]:
            team_position = i
            break
    
    # Формируем текст
    try:
        total_points = team["tournament_points"] if team["tournament_points"] is not None else 0
    except (KeyError, TypeError):
        total_points = 0
    member_count = len(members_rows)
    
    text = (
        f"<b>👥 Команда «{team['name']}»</b>\n\n"
        f"🏆 <b>Командный турнир</b>\n"
        f"📍 Место в таблице: #{team_position}\n"
        f"⭐️ Очки команды: {total_points}\n"
        f"👤 Участников: {member_count}/3\n"
        f"📅 Дата окончания: <i>31 декабря 2026</i>\n\n"
        f"<b>Участники команды:</b>\n"
    )
    
    for mem in members_rows:
        name = f"@{mem['username']}" if mem['username'] else mem['first_name'] or f"user_{mem['user_id']}"
        try:
            points = mem['tournament_points'] if mem['tournament_points'] is not None else 0
        except (KeyError, TypeError):
            points = 0
        text += f"• {name}: {points} очков\n"
    
    if member_count < 3:
        text += f"\n<i>Можно пригласить ещё {3 - member_count} игрок(а)</i>"
    
    kb = [
        [InlineKeyboardButton("📊 Таблица турнира", callback_data="team_tournament_table")],
    ]
    
    # Добавляем кнопку Mini App для детального просмотра команды
    if MINIAPP_URL:
        kb.append([
            InlineKeyboardButton(
                "📱 Подробнее в приложении",
                web_app=WebAppInfo(url=f"{MINIAPP_URL}/team")
            )
        ])
    
    if member_count < 3:
        kb.append([InlineKeyboardButton("➕ Пригласить игрока", callback_data="team_invite")])
    
    kb.extend([
        [InlineKeyboardButton("🚪 Выйти из команды", callback_data="team_leave_confirm")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
    ])
    
    await delete_and_send_new(q, text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)


async def team_profile_self(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старая функция для совместимости"""
    return await my_team_menu(update, context)


async def team_profile_self_old(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    team = get_user_team(q.from_user.id)
    if not team:
        # ВАЖНО: edit может упасть -> делаем try/except
        text = "Ты не состоишь ни в одной команде."
        try:
            return await q.edit_message_text(text, reply_markup=back_to_main_kb())
        except Exception:
            await q.message.reply_text(text, reply_markup=back_to_main_kb())
            return

    members = get_team_members(team["id"])
    lines = [f"👥 Команда «{team['name']}»\n"]

    for mem in members:
        name = display_name(mem["user_id"])
        wins = mem["wins"] or 0
        losses = mem["losses"] or 0
        lines.append(f"• {name}: {wins}W / {losses}L")

    kb = [
        [InlineKeyboardButton("➕ Пригласить", callback_data="team_invite")],
        [InlineKeyboardButton("🚪 Выйти из команды", callback_data="team_leave_confirm")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="menu")],  # или back:menu
    ]
    markup = InlineKeyboardMarkup(kb)
    text = "\n".join(lines)

    try:
        await q.edit_message_text(text, reply_markup=markup)
    except Exception:
        await q.message.reply_text(text, reply_markup=markup)

async def team_invite_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    team = get_user_team(q.from_user.id)
    if not team:
        return await q.edit_message_text("У тебя нет команды.", reply_markup=back_to_main_kb())

    token = secrets.token_urlsafe(6)
    team_invites[token] = team["id"]
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start=team_{token}"

    await q.edit_message_text(
        f"Отправь другу эту ссылку для вступления в команду:\n{link}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("↩️ Назад", callback_data="team_menu")]]
        ),
    )


async def team_profile_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "Просмотр других команд пока не реализован.",
        reply_markup=back_to_main_kb(),
    )


async def team_leave_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    team = get_user_team(q.from_user.id)
    if not team:
        return await delete_and_send_new(
            q,
            "Ты уже не в команде.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
        )
    
    # Получаем турнирные очки игрока
    member_row = db().execute(
        "SELECT tournament_points FROM team_members WHERE user_id=? AND team_id=?",
        (q.from_user.id, team["id"]),
    ).fetchone()
    
    member_points = 0
    if member_row:
        try:
            member_points = member_row["tournament_points"] if member_row["tournament_points"] is not None else 0
        except (KeyError, TypeError):
            member_points = 0

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Да, выйти", callback_data="team_leave_do")],
            [InlineKeyboardButton("↩️ Отмена", callback_data="my_team_menu")],
        ]
    )

    text = (
        f"<b>⚠️ Выход из команды «{team['name']}»</b>\n\n"
        f"Ты точно хочешь выйти из команды?\n\n"
        f"<b>Важно:</b>\n"
        f"• Твои турнирные очки ({member_points}) останутся в команде\n"
        f"• При вступлении в новую команду счет начнется с нуля\n"
        f"• Ты сможешь создать или вступить в другую команду"
    )

    await delete_and_send_new(q, text, reply_markup=kb, parse_mode=ParseMode.HTML)



async def team_leave_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    team = get_user_team(q.from_user.id)
    if not team:
        return await delete_and_send_new(
            q,
            "Ты уже не в команде.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
        )

    team_name = team["name"]
    
    # Получаем турнирные очки игрока
    member_row = db().execute(
        "SELECT tournament_points FROM team_members WHERE user_id=? AND team_id=?",
        (q.from_user.id, team["id"]),
    ).fetchone()
    
    member_points = 0
    if member_row:
        try:
            member_points = member_row["tournament_points"] if member_row["tournament_points"] is not None else 0
        except (KeyError, TypeError):
            member_points = 0

    conn = db()
    # Очки остаются в team_members, но игрок удаляется из активных участников
    # Для этого просто обнуляем связь в players
    conn.execute("UPDATE players SET team_id=NULL WHERE user_id=?", (q.from_user.id,))
    # НЕ удаляем из team_members, чтобы очки остались
    # Но можем пометить игрока как неактивного
    conn.commit()
    conn.close()

    await delete_and_send_new(
        q,
        f"✅ <b>Ты вышел из команды «{team_name}»</b>\n\n"
        f"Твои турнирные очки ({member_points}) остались в команде.\n"
        f"Теперь ты можешь создать новую команду или вступить в другую.",
        reply_markup=main_menu(q.from_user.id),
        parse_mode=ParseMode.HTML,
    )


async def tournament_solo_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await delete_and_send_new(
        q,
        "🏀 Одиночный турнир:\n\n"
        "• Учитываются победы и поражения.\n"
        "• Лучшие игроки получают призы.\n"
        "• Детали и сроки — в /rules.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
    )


async def tournament_team_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await delete_and_send_new(
        q,
        "👥 Командный турнир:\n\n"
        "• В зачёт идут победы игроков команды.\n"
        "• Команда до 3 игроков.\n"
        "• Детали — в /rules.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
    )


async def team_tournament_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает таблицу командного турнира.
    """
    q = update.callback_query
    await q.answer()
    
    # Получаем все команды отсортированные по очкам
    teams = db().execute(
        "SELECT t.id, t.name, t.tournament_points, "
        "(SELECT COUNT(*) FROM team_members WHERE team_id=t.id) as member_count "
        "FROM teams t "
        "ORDER BY t.tournament_points DESC "
        "LIMIT 50"
    ).fetchall()
    
    if not teams:
        return await delete_and_send_new(
            q,
            "📊 <b>Таблица командного турнира</b>\n\n"
            "Пока нет зарегистрированных команд.\n"
            "Создай свою команду и стань первым!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]),
            parse_mode=ParseMode.HTML,
        )
    
    text = "<b>📊 Таблица командного турнира</b>\n\n"
    text += "🏆 <b>Топ команд:</b>\n\n"
    
    for i, team in enumerate(teams, start=1):
        medal = ""
        if i == 1:
            medal = "🥇 "
        elif i == 2:
            medal = "🥈 "
        elif i == 3:
            medal = "🥉 "
        
        try:
            points = team["tournament_points"] if team["tournament_points"] is not None else 0
        except (KeyError, TypeError):
            points = 0
        member_count = team["member_count"]
        
        text += f"{medal}<b>#{i}</b> {team['name']}\n"
        text += f"   ⭐️ {points} очков | 👤 {member_count}/3 игроков\n\n"
    
    text += "\n<i>📅 Турнир завершится 31 декабря 2026</i>"
    
    kb = [
        [InlineKeyboardButton("↩️ Назад", callback_data="my_team_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
    ]
    
    await delete_and_send_new(q, text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def clear_menu_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int, keep_last: int = 1):
    ids = context.user_data.get(MENU_MSGS_KEY, [])
    if not ids:
        return
    # оставим последние keep_last, остальные удалим
    to_delete = ids[:-keep_last] if keep_last > 0 else ids[:]
    new_ids = ids[-keep_last:] if keep_last > 0 else []
    for mid in to_delete:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass
    context.user_data[MENU_MSGS_KEY] = new_ids

def back_to_main_kb() -> InlineKeyboardMarkup:
    # совместимость со старым кодом: раньше возвращало "в меню",
    # теперь будет возвращать "назад"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Вернуться назад", callback_data="back")]]
    )


# -------------------- MENU MESSAGE CLEANER --------------------
MENU_MSGS_KEY = "menu_message_ids"

async def clear_menu_messages(context, chat_id: int, keep_last: int = 1):
    ids = context.user_data.get(MENU_MSGS_KEY, [])
    if len(ids) <= keep_last:
        return

    to_delete = ids[:-keep_last]
    context.user_data[MENU_MSGS_KEY] = ids[-keep_last:]

    for mid in to_delete:
        try:
            await context.bot.delete_message(chat_id, mid)
        except Exception:
            pass

async def show_screen(
    q,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    *,
    parse_mode: Optional[str] = None,
):
    """
    Безопасно "показывает экран":
    - пытается отредактировать сообщение
    - если нельзя (часто фото/подпись) — отправляет новое
    """
    try:
        await q.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except Exception:
        await q.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

async def start_game_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Старт" из приветственного сообщения.
    """
    q = update.callback_query
    await q.answer()
    
    u = q.from_user
    
    # Помечаем, что пользователь увидел приветствие
    conn = db()
    conn.execute(
        "UPDATE players SET has_seen_welcome=1 WHERE user_id=?",
        (u.id,),
    )
    
    # Проверяем реквизиты
    row = conn.execute(
        "SELECT saved_requisites FROM players WHERE user_id=?",
        (u.id,),
    ).fetchone()
    saved_req = row["saved_requisites"] if row else None
    conn.commit()
    conn.close()
    
    # Сбрасываем историю и фиксируем, что мы в главном меню
    context.user_data["menu_stack"] = ["menu"]
    
    # Если реквизитов нет — запрашиваем их
    if not saved_req:
        context.user_data["await_requisites"] = True
        await delete_and_send_new(
            q,
            "‼️ <b>Перед началом игры укажи свои реквизиты</b>\n\n"
            "Это нужно для вывода выигранных звёзд и Lev.\n\n"
            "Отправь реквизиты ОДНИМ сообщением:\n\n"
            "<b>Формат 1 (СБП):</b>\n"
            "<code>СБП +7-000-000-00-00 Сбербанк ИвановИванИванович</code>\n\n"
            "<b>Формат 2 (КАРТА):</b>\n"
            "<code>КАРТА 4276-8383-1286-7320 Сбербанк ИвановИванИванович</code>\n\n"
            "⚠️ Без реквизитов нельзя будет вывести средства и играть с другими игроками.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⏭ Пропустить (укажу позже)", callback_data="menu")]]
            ),
        )
    else:
        # Реквизиты есть — показываем главное меню
        await delete_and_send_new(q, "Главное меню:", reply_markup=main_menu(u.id))


async def menu_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # Сбрасываем историю и фиксируем, что мы в главном меню
    context.user_data["menu_stack"] = ["menu"]

    await delete_and_send_new(q, "Главное меню:", reply_markup=main_menu(q.from_user.id))
def nav_kb(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Если пользователь сделал 1 шаг от главного меню -> показываем "В главное меню".
    Если 2+ шагов -> показываем "Вернуться назад".
    """
    stack = context.user_data.get("menu_stack", ["menu"])
    depth = len(stack) - 1  # сколько шагов от главного

    if depth <= 1:
        # после одного действия
        return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В главное меню", callback_data="menu")]])
    else:
        # после нескольких действий
        return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Вернуться назад", callback_data="back")]])

# -------------------- BUILD APP --------------------
async def post_init(application) -> None:
    """
    Вызывается после инициализации бота.
    Устанавливает Menu Button для Mini App.
    """
    if MINIAPP_URL:
        try:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="📱 Mini App",
                    web_app=WebAppInfo(url=MINIAPP_URL)
                )
            )
            logging.info(f"Menu button set to Mini App: {MINIAPP_URL}")
        except Exception as e:
            logging.warning(f"Failed to set menu button: {e}")


def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # --- Команды ---
    app.add_handler(CommandHandler("start", start_deeplink))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("support", cmd_support))
    app.add_handler(CommandHandler("reset_welcome", cmd_reset_welcome))
    app.add_handler(CallbackQueryHandler(start_game_btn, pattern=r"^start_game$"))
    app.add_handler(CallbackQueryHandler(menu_btn, pattern=r"^menu$"))

    # История операций Lev и Stars
    app.add_handler(CallbackQueryHandler(lev_withdraw_history_btn, pattern=r"^lev_withdraw_history$"))
    app.add_handler(CallbackQueryHandler(stars_withdraw_history_btn, pattern=r"^stars_withdraw_history$"))
    app.add_handler(CallbackQueryHandler(lev_purchases_history_btn, pattern=r"^lev_purchases_history$"))

    app.add_handler(CallbackQueryHandler(money_menu, pattern=r"^money_menu$"))
    app.add_handler(CallbackQueryHandler(stars_money_menu, pattern=r"^stars_money_menu$"))

    # Вывод Lev / реквизиты
    app.add_handler(CallbackQueryHandler(withdraw_menu, pattern=r"^withdraw_menu$"))
    app.add_handler(CallbackQueryHandler(withdraw_how, pattern=r"^withdraw_how$"))
    app.add_handler(CallbackQueryHandler(withdraw_track, pattern=r"^withdraw_track:\d+$"))
    app.add_handler(CallbackQueryHandler(requisites_menu, pattern=r"^requisites_menu$"))
    app.add_handler(CallbackQueryHandler(requisites_edit, pattern=r"^requisites_edit$"))

    # Админские команды по выводу Lev
    app.add_handler(CommandHandler("wlist", wlist))
    app.add_handler(CommandHandler("wapprove", wapprove))
    app.add_handler(CommandHandler("wreject", wreject))

    # Админ по звёздам (просмотр долгов по звёздам, обнуление)
    app.add_handler(CommandHandler("starslist", stars_admin_list))

    app.add_handler(CallbackQueryHandler(stars_withdraw_btn, pattern=r"^stars_withdraw_btn$"))

    # Подсказки по командам и турнирам
    app.add_handler(CommandHandler("teams", cmd_teams_help))
    app.add_handler(CommandHandler("tournaments", cmd_tournaments_help))

    # --- Профиль / чемпионы ---
    app.add_handler(CallbackQueryHandler(profile_btn, pattern=r"^profile$"))
    app.add_handler(CallbackQueryHandler(champions_btn, pattern=r"^champions$"))

    # --- Главное меню и подменю ---тэ
    app.add_handler(CallbackQueryHandler(back_btn, pattern=r"^back$"))
    app.add_handler(CallbackQueryHandler(play_menu, pattern=r"^play_menu$"))
    app.add_handler(CallbackQueryHandler(tournaments_menu, pattern=r"^tournaments_menu$"))
    app.add_handler(CallbackQueryHandler(money_menu, pattern=r"^money_menu$"))

    # Играть
    app.add_handler(CallbackQueryHandler(friend_stars_soon, pattern=r"^friend_stars_soon$"))

    # Магазин Lev
    app.add_handler(CallbackQueryHandler(shop_btn, pattern=r"^shop$"))
    app.add_handler(CallbackQueryHandler(buy_btn, pattern=r"^buy:.+"))
    app.add_handler(CallbackQueryHandler(balance_btn, pattern=r"^balance$"))

    # Звёздный матчмейкинг
    app.add_handler(CallbackQueryHandler(stars_menu_btn, pattern=r"^stars_menu$"))
    app.add_handler(CallbackQueryHandler(stars_join, pattern=r"^stars_join:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(stars_clear_btn, pattern=r"^stars_clear:\d+$"))

    # Вывод Lev / реквизиты
    app.add_handler(CallbackQueryHandler(withdraw_menu, pattern=r"^withdraw_menu$"))
    app.add_handler(CallbackQueryHandler(withdraw_how, pattern=r"^withdraw_how$"))
    app.add_handler(CallbackQueryHandler(withdraw_track, pattern=r"^withdraw_track:\d+$"))
    app.add_handler(CallbackQueryHandler(requisites_menu, pattern=r"^requisites_menu$"))
    app.add_handler(CallbackQueryHandler(requisites_edit, pattern=r"^requisites_edit$"))

    # Режимы и цель матча
    app.add_handler(CallbackQueryHandler(choose_mode, pattern=r"^mode:(mm|friend|train)$"))
    app.add_handler(CallbackQueryHandler(choose_goal, pattern=r"^goal:(mm|friend|train):\d+$"))

    # Броски
    app.add_handler(CallbackQueryHandler(throw_btn, pattern=r"^throw:[0-9a-f]+$"))

    # Реванш
    app.add_handler(CallbackQueryHandler(rematch_offer_btn, pattern=r"^rematch_offer:[0-9a-f]+$"))
    app.add_handler(CallbackQueryHandler(rematch_accept, pattern=r"^rematch_accept:.+$"))
    app.add_handler(CallbackQueryHandler(rematch_decline, pattern=r"^rematch_decline:.+$"))

    # Приглашения в дуэль
    app.add_handler(CallbackQueryHandler(invite_accept, pattern=r"^invite_accept:.+$"))
    app.add_handler(CallbackQueryHandler(invite_decline, pattern=r"^invite_decline:.+$"))

    # Команды (UI)
    app.add_handler(CallbackQueryHandler(team_menu, pattern=r"^team_menu$"))
    app.add_handler(CallbackQueryHandler(create_team_start, pattern=r"^create_team_start$"))
    app.add_handler(CallbackQueryHandler(team_create_start, pattern=r"^team_create_start$"))
    app.add_handler(CallbackQueryHandler(my_team_menu, pattern=r"^my_team_menu$"))
    app.add_handler(CallbackQueryHandler(team_profile_self, pattern=r"^team_profile_self$"))
    app.add_handler(CallbackQueryHandler(team_tournament_table, pattern=r"^team_tournament_table$"))
    app.add_handler(CallbackQueryHandler(team_invite_btn, pattern=r"^team_invite$"))
    app.add_handler(CallbackQueryHandler(team_profile_from_list, pattern=r"^team_profile:\d+$"))
    app.add_handler(CallbackQueryHandler(team_leave_confirm, pattern=r"^team_leave_confirm$"))
    app.add_handler(CallbackQueryHandler(team_leave_do, pattern=r"^team_leave_do$"))

    # Турниры
    app.add_handler(CallbackQueryHandler(tournament_solo_btn, pattern=r"^tournament_solo$"))
    app.add_handler(CallbackQueryHandler(tournament_team_btn, pattern=r"^tournament_team$"))

    # Правила / поддержка по кнопкам
    app.add_handler(CallbackQueryHandler(rules_btn, pattern=r"^rules_btn$"))
    app.add_handler(CallbackQueryHandler(support_btn, pattern=r"^support_btn$"))

    # Платежи
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    # Любой текст (ставка друга / реквизиты / название команды / прочее)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_any))


    # ❌ Раньше тут был job_queue для авто-отчёта по звёздам каждые 2 часа.
    # Ты просил убрать автоматические действия — поэтому НИЧЕГО не планируем в job_queue.
    # Админ сам вызывает /starslist, когда ему нужно.

    return app


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    logging.info("Starting Basketball Lev bot...")
    init_db()
    app = build_app()
    app.run_polling()
    logging.info("Bot stopped.")


if __name__ == "__main__":
    main()

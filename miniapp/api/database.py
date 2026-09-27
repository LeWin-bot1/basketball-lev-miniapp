"""
Слой доступа к базе данных для API мини-приложения.
Использует ту же SQLite базу, что и основной бот.
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple
from contextlib import contextmanager

# Путь к базе данных бота
BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / "lev_game.db"


@contextmanager
def get_db():
    """Контекстный менеджер для подключения к БД"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    """Конвертирует sqlite3.Row в dict"""
    if row is None:
        return None
    return dict(row)


# -------------------- Player Functions --------------------

def get_player(user_id: int) -> Optional[dict]:
    """Получить профиль игрока по user_id"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, username, first_name, game_nick, lev, rating,
                   wins, losses, draws, matches_played, team_id, created_at,
                   stars_pending, last_match_json
            FROM players
            WHERE user_id = ?
            """,
            (user_id,)
        )
        row = cur.fetchone()
        return row_to_dict(row)


def get_player_rank(user_id: int) -> Tuple[int, int]:
    """Получить ранг игрока и общее количество игроков"""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Общее количество игроков
        cur.execute("SELECT COUNT(*) FROM players")
        total = cur.fetchone()[0]
        
        # Ранг игрока (по победам, затем по рейтингу)
        cur.execute(
            """
            SELECT COUNT(*) + 1
            FROM players
            WHERE wins > (SELECT wins FROM players WHERE user_id = ?)
               OR (wins = (SELECT wins FROM players WHERE user_id = ?)
                   AND rating > (SELECT rating FROM players WHERE user_id = ?))
            """,
            (user_id, user_id, user_id)
        )
        rank = cur.fetchone()[0]
        
        return rank, total


def get_leaderboard(page: int = 1, per_page: int = 50) -> Tuple[List[dict], int]:
    """Получить таблицу лидеров с пагинацией"""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Общее количество игроков
        cur.execute("SELECT COUNT(*) FROM players WHERE wins > 0 OR losses > 0")
        total = cur.fetchone()[0]
        
        # Получить страницу лидеров
        offset = (page - 1) * per_page
        cur.execute(
            """
            SELECT user_id, username, first_name, game_nick, wins, losses, rating
            FROM players
            WHERE wins > 0 OR losses > 0
            ORDER BY wins DESC, rating DESC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset)
        )
        rows = cur.fetchall()
        
        return [row_to_dict(r) for r in rows], total


# -------------------- Tournament Functions --------------------

def get_solo_tournament_leaderboard(limit: int = 100) -> Tuple[List[dict], int]:
    """Получить таблицу одиночного турнира"""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Общее количество участников
        cur.execute("SELECT COUNT(*) FROM tournament_solo WHERE wins > 0 OR losses > 0")
        total = cur.fetchone()[0]
        
        # Топ игроков турнира
        cur.execute(
            """
            SELECT ts.user_id, p.username, p.first_name, p.game_nick, ts.wins, ts.losses,
                   (ts.wins * 3) as points
            FROM tournament_solo ts
            JOIN players p ON p.user_id = ts.user_id
            WHERE ts.wins > 0 OR ts.losses > 0
            ORDER BY ts.wins DESC, ts.losses ASC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cur.fetchall()
        
        return [row_to_dict(r) for r in rows], total


def get_solo_tournament_rank(user_id: int) -> Optional[int]:
    """Получить ранг игрока в одиночном турнире"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) + 1
            FROM tournament_solo
            WHERE wins > (SELECT COALESCE(wins, 0) FROM tournament_solo WHERE user_id = ?)
               OR (wins = (SELECT COALESCE(wins, 0) FROM tournament_solo WHERE user_id = ?)
                   AND losses < (SELECT COALESCE(losses, 0) FROM tournament_solo WHERE user_id = ?))
            """,
            (user_id, user_id, user_id)
        )
        result = cur.fetchone()
        return result[0] if result else None


def get_team_tournament_leaderboard(limit: int = 50) -> Tuple[List[dict], int]:
    """Получить таблицу командного турнира"""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Общее количество команд
        cur.execute("SELECT COUNT(*) FROM teams WHERE wins > 0 OR losses > 0")
        total = cur.fetchone()[0]
        
        # Топ команд
        cur.execute(
            """
            SELECT t.id as team_id, t.name, t.wins, t.losses, t.tournament_points
            FROM teams t
            WHERE t.wins > 0 OR t.losses > 0
            ORDER BY t.tournament_points DESC, t.wins DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cur.fetchall()
        
        return [row_to_dict(r) for r in rows], total


# -------------------- Team Functions --------------------

def get_team(team_id: int) -> Optional[dict]:
    """Получить информацию о команде"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id as team_id, name, creator_id, wins, losses, 
                   tournament_points, created_at
            FROM teams
            WHERE id = ?
            """,
            (team_id,)
        )
        row = cur.fetchone()
        return row_to_dict(row)


def get_team_members(team_id: int) -> List[dict]:
    """Получить участников команды"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tm.user_id, p.username, p.first_name, tm.tournament_points, 
                   tm.joined_at, p.wins, p.losses
            FROM team_members tm
            JOIN players p ON p.user_id = tm.user_id
            WHERE tm.team_id = ?
            ORDER BY tm.tournament_points DESC
            """,
            (team_id,)
        )
        rows = cur.fetchall()
        return [row_to_dict(r) for r in rows]


def get_user_team(user_id: int) -> Optional[dict]:
    """Получить команду пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.id as team_id, t.name, t.creator_id, t.wins, t.losses,
                   t.tournament_points, t.created_at
            FROM teams t
            JOIN players p ON p.team_id = t.id
            WHERE p.user_id = ?
            """,
            (user_id,)
        )
        row = cur.fetchone()
        return row_to_dict(row)


def get_team_rank(team_id: int) -> Optional[int]:
    """Получить ранг команды в турнире"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) + 1
            FROM teams
            WHERE tournament_points > (SELECT COALESCE(tournament_points, 0) FROM teams WHERE id = ?)
               OR (tournament_points = (SELECT COALESCE(tournament_points, 0) FROM teams WHERE id = ?)
                   AND wins > (SELECT COALESCE(wins, 0) FROM teams WHERE id = ?))
            """,
            (team_id, team_id, team_id)
        )
        result = cur.fetchone()
        return result[0] if result else None


# -------------------- Ledger Functions --------------------

def get_ledger_history(user_id: int, currency: str = None, limit: int = 50, offset: int = 0) -> Tuple[List[dict], int]:
    """Получить историю транзакций пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Базовый запрос
        where_clause = "WHERE user_id = ?"
        params = [user_id]
        
        if currency:
            where_clause += " AND currency = ?"
            params.append(currency)
        
        # Общее количество записей
        cur.execute(f"SELECT COUNT(*) FROM ledger {where_clause}", params)
        total = cur.fetchone()[0]
        
        # Получить записи
        cur.execute(
            f"""
            SELECT id, currency, amount, balance_after, tx_type, 
                   ref_type, ref_id, note, created_at
            FROM ledger
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset]
        )
        rows = cur.fetchall()
        
        return [row_to_dict(r) for r in rows], total


def get_balance_summary(user_id: int) -> dict:
    """Получить сводку по балансу пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Текущий баланс
        cur.execute(
            "SELECT lev, stars_pending FROM players WHERE user_id = ?",
            (user_id,)
        )
        row = cur.fetchone()
        lev = row["lev"] if row else 0
        stars_pending = row["stars_pending"] if row else 0
        
        # Общая сумма выигрышей
        cur.execute(
            """
            SELECT COALESCE(SUM(amount), 0) as total
            FROM ledger
            WHERE user_id = ? AND amount > 0 AND tx_type IN ('game_win', 'tournament_prize')
            """,
            (user_id,)
        )
        total_earned = cur.fetchone()[0]
        
        # Общая сумма расходов
        cur.execute(
            """
            SELECT COALESCE(ABS(SUM(amount)), 0) as total
            FROM ledger
            WHERE user_id = ? AND amount < 0
            """,
            (user_id,)
        )
        total_spent = cur.fetchone()[0]
        
        return {
            "lev": lev,
            "stars_pending": stars_pending,
            "total_earned": total_earned,
            "total_spent": total_spent
        }


NICK_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9 _.-]{2,20}$")


def ensure_player(user_id: int, username: str = "", first_name: str = "") -> dict:
    """Создаёт игрока, если его ещё нет, и возвращает профиль."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO players(user_id, username, first_name) VALUES(?,?,?)",
            (user_id, username or "", first_name or ""),
        )
        cur.execute(
            "UPDATE players SET username=?, first_name=? WHERE user_id=?",
            (username or "", first_name or "", user_id),
        )
        conn.commit()
    player = get_player(user_id)
    if not player:
        raise RuntimeError("Failed to create player")
    return player


def update_game_nick(user_id: int, game_nick: str) -> str:
    """Сохраняет игровой ник. Возвращает нормализованное имя."""
    nick = (game_nick or "").strip()
    if not NICK_RE.match(nick):
        raise ValueError(
            "Ник: 2–20 символов, буквы, цифры, пробел, _ . -"
        )
    with get_db() as conn:
        conn.execute(
            "UPDATE players SET game_nick=? WHERE user_id=?",
            (nick, user_id),
        )
        conn.commit()
    return nick


def _row_to_match(row: dict, user_id: int) -> dict:
    result = (row.get("result") or "").replace("timeout_", "")
    if result not in ("win", "loss", "draw"):
        if result.endswith("win"):
            result = "win"
        elif result.endswith("loss"):
            result = "loss"
        else:
            result = "draw"
    return {
        "match_id": str(row.get("id") or ""),
        "opponent_name": row.get("opponent_nick"),
        "opponent_id": row.get("opponent_id"),
        "player_score": row.get("you_score") or 0,
        "opponent_score": row.get("opp_score") or 0,
        "result": result,
        "bet_amount": row.get("stake"),
        "currency": "stars" if row.get("mode") == "stars" else "lev",
        "played_at": row.get("played_at"),
        "mode": row.get("mode_human") or row.get("mode"),
        "delta_lev": row.get("delta_lev") or 0,
    }


def _last_match_from_json(player: dict) -> Optional[dict]:
    raw = player.get("last_match_json")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return _row_to_match(
        {
            "id": "last",
            "opponent_nick": data.get("opponent_nick"),
            "opponent_id": data.get("opponent_id"),
            "you_score": data.get("you_score"),
            "opp_score": data.get("opp_score"),
            "result": data.get("result"),
            "stake": data.get("stake"),
            "mode": data.get("mode"),
            "mode_human": data.get("mode_human"),
            "played_at": data.get("ts"),
            "delta_lev": data.get("delta_lev"),
        },
        player.get("user_id", 0),
    )


def get_match_history(user_id: int, limit: int = 50, offset: int = 0) -> Tuple[List[dict], int]:
    """История матчей игрока. Если таблицы ещё нет — берём last_match_json."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM match_history WHERE user_id = ?",
                (user_id,),
            )
            total = cur.fetchone()[0]
            cur.execute(
                """
                SELECT id, user_id, opponent_id, opponent_nick, mode, mode_human,
                       target, stake, you_score, opp_score, result, delta_lev, played_at
                FROM match_history
                WHERE user_id = ?
                ORDER BY played_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            )
            rows = [row_to_dict(r) for r in cur.fetchall()]
        if rows:
            return [_row_to_match(r, user_id) for r in rows], total
    except sqlite3.OperationalError:
        pass

    player = get_player(user_id)
    last = _last_match_from_json(player or {})
    if last:
        return [last], 1
    return [], 0


def compute_win_streaks(user_id: int) -> Tuple[int, int]:
    """Текущая и лучшая серия побед."""
    matches, _ = get_match_history(user_id, limit=200, offset=0)
    if not matches:
        return 0, 0

    current = 0
    for match in matches:
        if match["result"] == "win":
            current += 1
        else:
            break

    best = 0
    run = 0
    for match in reversed(matches):
        if match["result"] == "win":
            run += 1
            best = max(best, run)
        else:
            run = 0
    return current, max(best, current)

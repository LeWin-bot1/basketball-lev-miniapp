"""
FastAPI backend для Telegram Mini App баскетбольного бота.

Запуск:
    uvicorn miniapp.api.main:app --reload --port 8080

Или в production:
    uvicorn miniapp.api.main:app --host 0.0.0.0 --port 8080
"""

import asyncio
import math
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_current_user, get_user_id_from_init_data, TelegramInitData
from .database import (
    get_player,
    get_player_rank,
    get_leaderboard,
    get_solo_tournament_leaderboard,
    get_solo_tournament_rank,
    get_team_tournament_leaderboard,
    get_team,
    get_team_members,
    get_user_team,
    get_team_rank,
    get_ledger_history,
    get_balance_summary,
    ensure_player,
    update_game_nick,
    get_match_history,
    compute_win_streaks,
)
from .models import (
    PlayerProfile,
    PlayerStats,
    TournamentLeaderboard,
    TournamentPlayer,
    TournamentTeam,
    TeamInfo,
    TeamMember,
    TeamLeaderboard,
    LedgerEntry,
    FinanceHistory,
    BalanceSummary,
    GlobalLeaderboard,
    LeaderboardEntry,
    UpdateNickRequest,
    MatchHistory,
    MatchResult,
)

TOURNAMENT_END_DATE = "2027-06-01"
TOURNAMENT_PRIZE_SOLO = "майка Prada"
TOURNAMENT_PRIZE_TEAM = "10000 тг Sta"


def _player_or_create(init_data: TelegramInitData) -> dict:
    user_id = get_user_id_from_init_data(init_data)
    player = get_player(user_id)
    if player:
        return player
    tg = init_data.user
    return ensure_player(
        user_id,
        username=(tg.username if tg else "") or "",
        first_name=(tg.first_name if tg else "") or "",
    )


def _to_profile(player_data: dict) -> PlayerProfile:
    data = dict(player_data)
    data.pop("last_match_json", None)
    return PlayerProfile(**data)


def _to_match(item: dict) -> MatchResult:
    return MatchResult(**item)
from .websocket import (
    manager as ws_manager,
    handle_tournament_websocket,
    periodic_tournament_update,
)


# -------------------- App Lifespan --------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Запускаем фоновую задачу обновления турниров
    update_task = asyncio.create_task(periodic_tournament_update())
    yield
    # Останавливаем задачу при выключении
    update_task.cancel()
    try:
        await update_task
    except asyncio.CancelledError:
        pass


# -------------------- App Setup --------------------

app = FastAPI(
    title="Basketball Lev Bot Mini App API",
    description="API для мини-приложения баскетбольного бота",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS для разработки, Render и Telegram WebView
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://web.telegram.org",
        "https://telegram.org",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------- Health Check --------------------

@app.get("/api/health")
async def health():
    """Health check"""
    return {"status": "healthy"}


# -------------------- Profile Endpoints --------------------

@app.get("/api/profile", response_model=PlayerStats)
async def get_my_profile(
    user: TelegramInitData = Depends(get_current_user)
):
    """
    Получить профиль текущего пользователя.
    
    Требует авторизацию через Telegram initData.
    """
    player_data = _player_or_create(user)
    user_id = player_data["user_id"]
    
    rank, total_players = get_player_rank(user_id)
    matches, _ = get_match_history(user_id, limit=20)
    win_streak, best_win_streak = compute_win_streaks(user_id)
    
    return PlayerStats(
        player=_to_profile(player_data),
        rank=rank,
        total_players=total_players,
        recent_matches=[_to_match(m) for m in matches],
        win_streak=win_streak,
        best_win_streak=best_win_streak,
    )


@app.patch("/api/profile/nick", response_model=PlayerProfile)
async def set_my_nick(
    body: UpdateNickRequest,
    user: TelegramInitData = Depends(get_current_user),
):
    """Сохранить игровой ник, который видят другие игроки."""
    player_data = _player_or_create(user)
    try:
        update_game_nick(player_data["user_id"], body.game_nick)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    updated = get_player(player_data["user_id"])
    return _to_profile(updated)


@app.get("/api/matches", response_model=MatchHistory)
async def get_my_matches(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: TelegramInitData = Depends(get_current_user),
):
    """Полная история матчей текущего игрока."""
    player_data = _player_or_create(user)
    matches, total = get_match_history(player_data["user_id"], limit, offset)
    return MatchHistory(matches=[_to_match(m) for m in matches], total=total)


@app.get("/api/profile/{user_id}", response_model=PlayerStats)
async def get_player_profile(
    user_id: int,
    _: TelegramInitData = Depends(get_current_user)
):
    """Публичный профиль другого игрока: статистика и матчи."""
    player_data = get_player(user_id)
    if not player_data:
        raise HTTPException(status_code=404, detail="Player not found")
    
    rank, total_players = get_player_rank(user_id)
    matches, _ = get_match_history(user_id, limit=20)
    win_streak, best_win_streak = compute_win_streaks(user_id)
    
    return PlayerStats(
        player=_to_profile(player_data),
        rank=rank,
        total_players=total_players,
        recent_matches=[_to_match(m) for m in matches],
        win_streak=win_streak,
        best_win_streak=best_win_streak,
    )


# -------------------- Leaderboard Endpoints --------------------

@app.get("/api/leaderboard", response_model=GlobalLeaderboard)
async def get_global_leaderboard(
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(50, ge=10, le=100, description="Записей на странице"),
    user: TelegramInitData = Depends(get_current_user)
):
    """
    Глобальная таблица лидеров по победам.
    
    Поддерживает пагинацию.
    """
    user_id = get_user_id_from_init_data(user)
    
    players, total = get_leaderboard(page, per_page)
    
    # Получаем ранг текущего пользователя
    current_user_rank, _ = get_player_rank(user_id)
    
    # Формируем записи с рангами
    entries = []
    start_rank = (page - 1) * per_page + 1
    for i, p in enumerate(players):
        entries.append(LeaderboardEntry(
            rank=start_rank + i,
            user_id=p["user_id"],
            username=p.get("username"),
            first_name=p.get("first_name"),
            game_nick=p.get("game_nick"),
            wins=p.get("wins", 0),
            losses=p.get("losses", 0),
            rating=p.get("rating", 1000),
            is_current_user=(p["user_id"] == user_id),
        ))
    
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    
    return GlobalLeaderboard(
        entries=entries,
        total_players=total,
        current_user_rank=current_user_rank,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


# -------------------- Tournament Endpoints --------------------

@app.get("/api/tournaments/solo", response_model=TournamentLeaderboard)
async def get_solo_tournament(
    limit: int = Query(100, ge=10, le=500),
    user: TelegramInitData = Depends(get_current_user)
):
    """
    Таблица одиночного турнира.
    """
    user_id = get_user_id_from_init_data(user)
    
    players_data, total = get_solo_tournament_leaderboard(limit)
    current_rank = get_solo_tournament_rank(user_id)
    
    players = [
        TournamentPlayer(
            user_id=p["user_id"],
            username=p.get("username"),
            first_name=p.get("first_name"),
            game_nick=p.get("game_nick"),
            wins=p.get("wins", 0),
            losses=p.get("losses", 0),
            points=p.get("points", 0),
        )
        for p in players_data
    ]
    
    return TournamentLeaderboard(
        type="solo",
        players=players,
        total_participants=total,
        current_user_rank=current_rank,
        tournament_end_date=TOURNAMENT_END_DATE,
        prize=TOURNAMENT_PRIZE_SOLO,
    )


@app.get("/api/tournaments/team", response_model=TeamLeaderboard)
async def get_team_tournament(
    limit: int = Query(50, ge=10, le=200),
    user: TelegramInitData = Depends(get_current_user)
):
    """
    Таблица командного турнира.
    """
    user_id = get_user_id_from_init_data(user)
    
    teams_data, total = get_team_tournament_leaderboard(limit)
    
    # Получаем команду пользователя для определения текущего ранга
    user_team = get_user_team(user_id)
    current_team_rank = None
    if user_team:
        current_team_rank = get_team_rank(user_team["team_id"])
    
    teams = []
    for t in teams_data:
        members = get_team_members(t["team_id"])
        teams.append(TournamentTeam(
            team_id=t["team_id"],
            name=t["name"],
            wins=t.get("wins", 0),
            losses=t.get("losses", 0),
            tournament_points=t.get("tournament_points", 0),
            members=[TeamMember(**m) for m in members],
        ))
    
    return TeamLeaderboard(
        teams=teams,
        total_teams=total,
        current_team_rank=current_team_rank,
        tournament_end_date=TOURNAMENT_END_DATE,
        prize=TOURNAMENT_PRIZE_TEAM,
    )


# -------------------- Team Endpoints --------------------

@app.get("/api/team/my", response_model=Optional[TeamInfo])
async def get_my_team(
    user: TelegramInitData = Depends(get_current_user)
):
    """
    Получить команду текущего пользователя.
    
    Возвращает null если пользователь не в команде.
    """
    user_id = get_user_id_from_init_data(user)
    
    team_data = get_user_team(user_id)
    if not team_data:
        return None
    
    members = get_team_members(team_data["team_id"])
    rank = get_team_rank(team_data["team_id"])
    
    return TeamInfo(
        **team_data,
        members=[TeamMember(**m) for m in members],
        rank=rank,
    )


@app.get("/api/team/{team_id}", response_model=TeamInfo)
async def get_team_info(
    team_id: int,
    _: TelegramInitData = Depends(get_current_user)
):
    """
    Получить информацию о команде по ID.
    """
    team_data = get_team(team_id)
    if not team_data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    members = get_team_members(team_id)
    rank = get_team_rank(team_id)
    
    return TeamInfo(
        **team_data,
        members=[TeamMember(**m) for m in members],
        rank=rank,
    )


# -------------------- Finance Endpoints --------------------

@app.get("/api/balance", response_model=BalanceSummary)
async def get_my_balance(
    user: TelegramInitData = Depends(get_current_user)
):
    """
    Получить сводку по балансу текущего пользователя.
    """
    user_id = get_user_id_from_init_data(user)
    
    summary = get_balance_summary(user_id)
    return BalanceSummary(**summary)


@app.get("/api/ledger", response_model=FinanceHistory)
async def get_my_ledger(
    currency: Optional[str] = Query(None, description="Фильтр по валюте: lev, stars"),
    limit: int = Query(50, ge=10, le=200),
    offset: int = Query(0, ge=0),
    user: TelegramInitData = Depends(get_current_user)
):
    """
    История транзакций текущего пользователя.
    
    Поддерживает фильтрацию по валюте и пагинацию.
    """
    user_id = get_user_id_from_init_data(user)
    
    entries_data, total = get_ledger_history(user_id, currency, limit, offset)
    
    # Получаем текущий баланс
    player = get_player(user_id)
    current_balance = 0
    if player:
        if currency == "lev" or currency is None:
            current_balance = player.get("lev", 0)
        elif currency == "stars":
            current_balance = player.get("stars_pending", 0)
    
    entries = [LedgerEntry(**e) for e in entries_data]
    
    return FinanceHistory(
        entries=entries,
        total_entries=total,
        current_balance=current_balance,
        currency=currency or "all",
    )


# -------------------- WebSocket Endpoints --------------------

@app.websocket("/ws/tournaments/{tournament_type}")
async def websocket_tournament(websocket: WebSocket, tournament_type: str):
    """
    WebSocket endpoint для real-time обновлений турнира.
    
    tournament_type: "solo" или "team"
    
    Клиент получает:
    - initial_data при подключении
    - tournament_update каждые 30 секунд
    - match_result при завершении матча
    """
    if tournament_type not in ("solo", "team"):
        await websocket.close(code=4000, reason="Invalid tournament type")
        return
    
    await handle_tournament_websocket(websocket, tournament_type)


@app.get("/ws/status")
async def websocket_status():
    """Статус WebSocket соединений"""
    return {
        "solo_tournament_connections": ws_manager.get_connection_count("solo_tournament"),
        "team_tournament_connections": ws_manager.get_connection_count("team_tournament"),
        "leaderboard_connections": ws_manager.get_connection_count("leaderboard"),
    }


# -------------------- Run with uvicorn --------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

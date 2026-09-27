"""
Pydantic модели для API мини-приложения
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# -------------------- Profile Models --------------------

class PlayerProfile(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    game_nick: Optional[str] = None
    lev: int = 0
    rating: int = 1000
    wins: int = 0
    losses: int = 0
    draws: int = 0
    matches_played: int = 0
    team_id: Optional[int] = None
    created_at: Optional[int] = None
    stars_pending: int = 0
    
    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        if total == 0:
            return 0.0
        return round(self.wins / total * 100, 1)


class PlayerStats(BaseModel):
    player: PlayerProfile
    rank: int  # Позиция в общем рейтинге
    total_players: int
    recent_matches: List["MatchResult"] = []
    win_streak: int = 0
    best_win_streak: int = 0


# -------------------- Match Models --------------------

class MatchResult(BaseModel):
    match_id: Optional[str] = None
    opponent_name: Optional[str] = None
    opponent_id: Optional[int] = None
    player_score: int = 0
    opponent_score: int = 0
    result: str  # "win", "loss", "draw"
    bet_amount: Optional[int] = None
    currency: Optional[str] = None
    played_at: Optional[int] = None
    mode: Optional[str] = None
    delta_lev: int = 0


# -------------------- Tournament Models --------------------

class TournamentPlayer(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    game_nick: Optional[str] = None
    wins: int = 0
    losses: int = 0
    points: int = 0  # wins * 3 (можно настроить)
    
    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        if total == 0:
            return 0.0
        return round(self.wins / total * 100, 1)


class TournamentLeaderboard(BaseModel):
    type: str  # "solo" or "team"
    players: List[TournamentPlayer]
    total_participants: int
    current_user_rank: Optional[int] = None
    tournament_end_date: Optional[str] = None
    prize: Optional[str] = None


class TournamentTeam(BaseModel):
    team_id: int
    name: str
    wins: int = 0
    losses: int = 0
    tournament_points: int = 0
    members: List["TeamMember"] = []


# -------------------- Team Models --------------------

class TeamMember(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    tournament_points: int = 0
    joined_at: Optional[int] = None
    wins: int = 0
    losses: int = 0


class TeamInfo(BaseModel):
    team_id: int
    name: str
    creator_id: int
    wins: int = 0
    losses: int = 0
    tournament_points: int = 0
    created_at: Optional[int] = None
    members: List[TeamMember] = []
    rank: Optional[int] = None  # Позиция в командном турнире


class TeamLeaderboard(BaseModel):
    teams: List[TournamentTeam]
    total_teams: int
    current_team_rank: Optional[int] = None
    tournament_end_date: Optional[str] = None
    prize: Optional[str] = None


# -------------------- Ledger / Finance Models --------------------

class LedgerEntry(BaseModel):
    id: int
    currency: str  # "lev", "stars"
    amount: int
    balance_after: Optional[int] = None
    tx_type: str  # "game_win", "game_loss", "purchase", "withdraw", etc.
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    note: Optional[str] = None
    created_at: int


class FinanceHistory(BaseModel):
    entries: List[LedgerEntry]
    total_entries: int
    current_balance: int
    currency: str


class BalanceSummary(BaseModel):
    lev: int = 0
    stars_pending: int = 0
    total_earned: int = 0
    total_spent: int = 0


# -------------------- API Response Models --------------------

class ApiResponse(BaseModel):
    success: bool = True
    data: Optional[dict] = None
    error: Optional[str] = None


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    game_nick: Optional[str] = None
    wins: int = 0
    losses: int = 0
    rating: int = 1000
    is_current_user: bool = False


class GlobalLeaderboard(BaseModel):
    entries: List[LeaderboardEntry]
    total_players: int
    current_user_rank: Optional[int] = None
    page: int = 1
    per_page: int = 50
    total_pages: int = 1


class UpdateNickRequest(BaseModel):
    game_nick: str


class MatchHistory(BaseModel):
    matches: List[MatchResult]
    total: int


# Для forward references
PlayerStats.model_rebuild()
TournamentTeam.model_rebuild()
TeamInfo.model_rebuild()

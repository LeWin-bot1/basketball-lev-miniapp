// Типы для API мини-приложения

export interface PlayerProfile {
  user_id: number;
  username?: string;
  first_name?: string;
  game_nick?: string;
  lev: number;
  rating: number;
  wins: number;
  losses: number;
  draws: number;
  matches_played: number;
  team_id?: number;
  created_at?: number;
}

export interface PlayerStats {
  player: PlayerProfile;
  rank: number;
  total_players: number;
  recent_matches: MatchResult[];
  win_streak: number;
  best_win_streak: number;
}

export interface MatchResult {
  match_id?: string;
  opponent_name?: string;
  opponent_id?: number;
  player_score: number;
  opponent_score: number;
  result: 'win' | 'loss' | 'draw';
  bet_amount?: number;
  currency?: string;
  played_at?: number;
}

export interface TournamentPlayer {
  user_id: number;
  username?: string;
  first_name?: string;
  wins: number;
  losses: number;
  points: number;
}

export interface TournamentLeaderboard {
  type: 'solo' | 'team';
  players: TournamentPlayer[];
  total_participants: number;
  current_user_rank?: number;
  tournament_end_date?: string;
}

export interface TeamMember {
  user_id: number;
  username?: string;
  first_name?: string;
  tournament_points: number;
  joined_at?: number;
  wins: number;
  losses: number;
}

export interface TournamentTeam {
  team_id: number;
  name: string;
  wins: number;
  losses: number;
  tournament_points: number;
  members: TeamMember[];
}

export interface TeamInfo {
  team_id: number;
  name: string;
  creator_id: number;
  wins: number;
  losses: number;
  tournament_points: number;
  created_at?: number;
  members: TeamMember[];
  rank?: number;
}

export interface TeamLeaderboard {
  teams: TournamentTeam[];
  total_teams: number;
  current_team_rank?: number;
}

export interface LedgerEntry {
  id: number;
  currency: string;
  amount: number;
  balance_after?: number;
  tx_type: string;
  ref_type?: string;
  ref_id?: string;
  note?: string;
  created_at: number;
}

export interface FinanceHistory {
  entries: LedgerEntry[];
  total_entries: number;
  current_balance: number;
  currency: string;
}

export interface BalanceSummary {
  lev: number;
  stars_pending: number;
  total_earned: number;
  total_spent: number;
}

export interface LeaderboardEntry {
  rank: number;
  user_id: number;
  username?: string;
  first_name?: string;
  wins: number;
  losses: number;
  rating: number;
  is_current_user: boolean;
}

export interface GlobalLeaderboard {
  entries: LeaderboardEntry[];
  total_players: number;
  current_user_rank?: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// Типы для Telegram
export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
  photo_url?: string;
}

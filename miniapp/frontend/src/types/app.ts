// Типы новых экранов Mini App (/api/me, /api/wallet, /api/profile/:id)
import type { MatchResult } from './index';

export interface Requisites {
  type: 'cryptobot' | 'trc20' | 'ton';
  label: string;
  value: string;
}

export interface MeStats {
  matches: number;
  wins: number;
  losses: number;
  win_rate: number;
  lev_won: number;
  lev_lost: number;
  lev_net: number;
  best_win: number;
  win_streak: number;
  best_win_streak: number;
}

export interface MeTournament {
  rank: number | null;
  wins: number;
  losses: number;
  points: number;
  total: number;
}

export interface Me {
  user_id: number;
  nick: string;
  username?: string | null;
  balance: number;
  stats: MeStats;
  tournament: MeTournament | null;
  requisites: Requisites | null;
  recent_matches: MatchResult[];
  total_matches: number;
}

export interface Deposit {
  id: string;
  method: 'stars' | 'usdt' | 'ton' | 'rub' | string;
  amount: string;
  lev: number;
  status: 'paid' | 'active' | 'expired' | string;
  details: string;
  created_at: number | null;
}

export interface Withdrawal {
  id: number;
  lev: number;
  method: 'cryptobot' | 'trc20' | 'ton' | string;
  asset: string | null;
  amount: string | null;
  destination: string | null;
  status: 'pending' | 'processing' | 'paid' | 'rejected' | string;
  queue_position: number | null;
  reject_reason: string | null;
  created_at: number | null;
  processed_at: number | null;
}

export interface Wallet {
  balance: number;
  pending_withdraw_lev: number;
  requisites: Requisites | null;
  deposits: Deposit[];
  withdrawals: Withdrawal[];
}

export interface PublicProfile {
  user_id: number;
  nick: string;
  matches: number;
}

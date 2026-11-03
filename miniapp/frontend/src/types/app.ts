// Типы новых экранов Mini App (/api/me, /api/wallet, /api/profile/:id)
import type { MatchResult } from './index';

/** Реквизиты игрока: для пополнения (с каких кошельков платит) и для вывода. */
export interface Requisites {
  deposit: { ton: string | null; trc20: string | null };
  withdraw: { ton: string | null; trc20: string | null; cryptobot: string | null };
}

export type RequisitePurpose = 'deposit' | 'withdraw';
export type RequisiteMethod = 'ton' | 'trc20' | 'cryptobot';

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
  requisites: Requisites;
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
  requisites: Requisites;
  deposits: Deposit[];
  withdrawals: Withdrawal[];
}

export interface PublicProfile {
  user_id: number;
  nick: string;
  matches: number;
}

// -------- Вкладка «Крипта» --------
export type CryptoAsset = 'USDT' | 'TON';
export type WithdrawMethod = 'cryptobot' | 'trc20' | 'ton';

export interface CryptoConfig {
  enabled: boolean;
  network: string;
  balance: number;
  rates: Record<CryptoAsset, number>;
  deposit: {
    assets: CryptoAsset[];
    presets: Record<CryptoAsset, string[]>;
    min: Record<CryptoAsset, number>;
    max: number;
  };
  withdraw: {
    min_lev: number;
    fee_pct: number;
    decimals: Record<CryptoAsset, number>;
    saved: { ton: string | null; trc20: string | null; cryptobot: string | null };
  };
}

export interface CryptoInvoice {
  invoice_id: number;
  asset: CryptoAsset;
  amount: string;
  lev: number;
  status: 'active' | 'paid' | 'expired' | string;
  pay_url: string | null;
  balance?: number;
}

export interface WithdrawResult {
  id: number;
  lev: number;
  asset: CryptoAsset;
  amount: string;
  method: WithdrawMethod;
  destination: string;
  queue_position: number;
  balance: number;
}

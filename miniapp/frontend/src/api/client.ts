import WebApp from '@twa-dev/sdk';
import type {
  PlayerStats,
  PlayerProfile,
  GlobalLeaderboard,
  TournamentLeaderboard,
  TeamLeaderboard,
  TeamInfo,
  BalanceSummary,
  FinanceHistory,
  MatchHistory,
} from '../types';

// Базовый URL API (в production заменить на реальный)
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Получаем initData для авторизации
function getAuthHeader(): Record<string, string> {
  const initData = WebApp.initData;
  if (initData) {
    return {
      'X-Telegram-Init-Data': initData,
    };
  }
  return {};
}

// Базовая функция для запросов
async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ==================== Profile API ====================

export async function getMyProfile(): Promise<PlayerStats> {
  return fetchApi<PlayerStats>('/profile');
}

export async function getPlayerProfile(userId: number): Promise<PlayerStats> {
  return fetchApi<PlayerStats>(`/profile/${userId}`);
}

export async function updateMyNick(gameNick: string): Promise<PlayerProfile> {
  return fetchApi<PlayerProfile>('/profile/nick', {
    method: 'PATCH',
    body: JSON.stringify({ game_nick: gameNick }),
  });
}

export async function getMyMatches(
  limit: number = 50,
  offset: number = 0
): Promise<MatchHistory> {
  return fetchApi<MatchHistory>(`/matches?limit=${limit}&offset=${offset}`);
}

// ==================== Leaderboard API ====================

export async function getLeaderboard(
  page: number = 1,
  perPage: number = 50
): Promise<GlobalLeaderboard> {
  return fetchApi<GlobalLeaderboard>(
    `/leaderboard?page=${page}&per_page=${perPage}`
  );
}

// ==================== Tournament API ====================

export async function getSoloTournament(
  limit: number = 100
): Promise<TournamentLeaderboard> {
  return fetchApi<TournamentLeaderboard>(`/tournaments/solo?limit=${limit}`);
}

export async function getTeamTournament(
  limit: number = 50
): Promise<TeamLeaderboard> {
  return fetchApi<TeamLeaderboard>(`/tournaments/team?limit=${limit}`);
}

// ==================== Team API ====================

export async function getMyTeam(): Promise<TeamInfo | null> {
  return fetchApi<TeamInfo | null>('/team/my');
}

export async function getTeamInfo(teamId: number): Promise<TeamInfo> {
  return fetchApi<TeamInfo>(`/team/${teamId}`);
}

// ==================== Finance API ====================

export async function getBalance(): Promise<BalanceSummary> {
  return fetchApi<BalanceSummary>('/balance');
}

export async function getLedgerHistory(
  currency?: string,
  limit: number = 50,
  offset: number = 0
): Promise<FinanceHistory> {
  const params = new URLSearchParams();
  if (currency) params.set('currency', currency);
  params.set('limit', limit.toString());
  params.set('offset', offset.toString());
  
  return fetchApi<FinanceHistory>(`/ledger?${params.toString()}`);
}

// ==================== Export ====================

export const api = {
  profile: {
    getMy: getMyProfile,
    getById: getPlayerProfile,
    updateNick: updateMyNick,
  },
  matches: {
    getMy: getMyMatches,
  },
  leaderboard: {
    get: getLeaderboard,
  },
  tournaments: {
    getSolo: getSoloTournament,
    getTeam: getTeamTournament,
  },
  team: {
    getMy: getMyTeam,
    getById: getTeamInfo,
  },
  finance: {
    getBalance: getBalance,
    getHistory: getLedgerHistory,
  },
};

export default api;

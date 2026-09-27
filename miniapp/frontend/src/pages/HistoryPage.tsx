import { useEffect, useState } from 'react';
import { ArrowUpRight, ArrowDownRight, Filter, Wallet, Trophy } from 'lucide-react';
import { api } from '../api/client';
import type { FinanceHistory, LedgerEntry, BalanceSummary, MatchResult } from '../types';
import { PageLoader } from '../components/LoadingSpinner';
import MatchCard from '../components/MatchCard';

type FilterType = 'all' | 'lev' | 'stars';
type HistoryTab = 'matches' | 'finance';

// Моковые данные
const mockBalance: BalanceSummary = {
  lev: 15000,
  stars_pending: 250,
  total_earned: 45000,
  total_spent: 30000,
};

const mockHistory: FinanceHistory = {
  entries: [
    {
      id: 1,
      currency: 'lev',
      amount: 100,
      balance_after: 15000,
      tx_type: 'game_win',
      note: 'Победа в дуэли',
      created_at: Date.now() / 1000 - 3600,
    },
    {
      id: 2,
      currency: 'lev',
      amount: -50,
      balance_after: 14900,
      tx_type: 'game_loss',
      note: 'Поражение в дуэли',
      created_at: Date.now() / 1000 - 7200,
    },
    {
      id: 3,
      currency: 'lev',
      amount: 500,
      balance_after: 14950,
      tx_type: 'purchase',
      note: 'Покупка за Stars',
      created_at: Date.now() / 1000 - 86400,
    },
    {
      id: 4,
      currency: 'stars',
      amount: -100,
      balance_after: 150,
      tx_type: 'withdraw',
      note: 'Вывод Stars',
      created_at: Date.now() / 1000 - 172800,
    },
    {
      id: 5,
      currency: 'lev',
      amount: 200,
      balance_after: 14450,
      tx_type: 'game_win',
      note: 'Победа в турнире',
      created_at: Date.now() / 1000 - 259200,
    },
  ],
  total_entries: 5,
  current_balance: 15000,
  currency: 'all',
};

function formatDate(timestamp: number): string {
  const date = new Date(timestamp * 1000);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffHours < 1) {
    return 'Только что';
  } else if (diffHours < 24) {
    return `${diffHours} ч. назад`;
  } else if (diffDays < 7) {
    return `${diffDays} дн. назад`;
  } else {
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
    });
  }
}

function getTxTypeLabel(txType: string): string {
  const labels: Record<string, string> = {
    game_win: 'Победа',
    game_loss: 'Поражение',
    purchase: 'Покупка',
    withdraw: 'Вывод',
    tournament_prize: 'Приз турнира',
    refund: 'Возврат',
  };
  return labels[txType] || txType;
}

export default function HistoryPage() {
  const [tab, setTab] = useState<HistoryTab>('matches');
  const [balance, setBalance] = useState<BalanceSummary | null>(null);
  const [history, setHistory] = useState<FinanceHistory | null>(null);
  const [matches, setMatches] = useState<MatchResult[]>([]);
  const [filter, setFilter] = useState<FilterType>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const isDev = import.meta.env.DEV;
        
        if (isDev) {
          await new Promise((r) => setTimeout(r, 300));
          setBalance(mockBalance);
          setHistory(mockHistory);
          setMatches([
            {
              opponent_name: 'Лев',
              player_score: 6,
              opponent_score: 3,
              result: 'win',
              delta_lev: 25,
              currency: 'lev',
              mode: 'Матчмейкинг',
              played_at: Date.now() / 1000 - 1800,
            },
          ]);
        } else {
          const [balanceData, historyData, matchData] = await Promise.all([
            api.finance.getBalance(),
            api.finance.getHistory(filter === 'all' ? undefined : filter),
            api.matches.getMy(100),
          ]);
          setBalance(balanceData);
          setHistory(historyData);
          setMatches(matchData.matches);
        }
      } catch (err) {
        console.error('Error loading history:', err);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [filter]);

  if (loading && !history) {
    return <PageLoader />;
  }

  return (
    <div className="p-4 page-transition">
      {/* Заголовок */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Wallet className="text-primary-500" />
          История
        </h1>
      </div>

      <div className="flex bg-gray-100 rounded-xl p-1 mb-6">
        <button
          onClick={() => setTab('matches')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium ${
            tab === 'matches' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'
          }`}
        >
          <Trophy size={14} className="inline mr-1" />
          Матчи
        </button>
        <button
          onClick={() => setTab('finance')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium ${
            tab === 'finance' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'
          }`}
        >
          <Wallet size={14} className="inline mr-1" />
          Финансы
        </button>
      </div>

      {tab === 'matches' && (
        <div className="space-y-2">
          {matches.map((match, index) => (
            <MatchCard key={match.match_id || index} match={match} />
          ))}
          {matches.length === 0 && (
            <div className="text-center py-8 text-gray-400">История матчей пуста</div>
          )}
        </div>
      )}

      {tab === 'finance' && balance && (
        <div className="grid grid-cols-2 gap-3 mb-6">
          <div className="bg-gradient-to-r from-primary-500 to-primary-600 rounded-xl p-4 text-white">
            <div className="text-sm opacity-80">Баланс Lev</div>
            <div className="text-2xl font-bold">{balance.lev.toLocaleString()}</div>
          </div>
          <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 rounded-xl p-4 text-white">
            <div className="text-sm opacity-80">Stars</div>
            <div className="text-2xl font-bold">{balance.stars_pending}</div>
          </div>
        </div>
      )}

      {tab === 'finance' && balance && (
        <div className="bg-white rounded-xl p-4 border border-gray-100 mb-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-gray-500">Всего заработано</div>
              <div className="text-lg font-semibold text-green-600">
                +{balance.total_earned.toLocaleString()}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Всего потрачено</div>
              <div className="text-lg font-semibold text-red-600">
                -{balance.total_spent.toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'finance' && (
        <>
          <div className="flex items-center gap-2 mb-4">
            <Filter size={16} className="text-gray-400" />
            <div className="flex bg-gray-100 rounded-lg p-1">
              {(['all', 'lev', 'stars'] as FilterType[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    filter === f
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-500'
                  }`}
                >
                  {f === 'all' ? 'Все' : f === 'lev' ? 'Lev' : 'Stars'}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            {history?.entries.map((entry: LedgerEntry) => (
              <div
                key={entry.id}
                className="bg-white rounded-xl p-4 border border-gray-100 flex items-center gap-3"
              >
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    entry.amount > 0 ? 'bg-green-100' : 'bg-red-100'
                  }`}
                >
                  {entry.amount > 0 ? (
                    <ArrowDownRight className="text-green-600" size={20} />
                  ) : (
                    <ArrowUpRight className="text-red-600" size={20} />
                  )}
                </div>
                <div className="flex-1">
                  <div className="font-medium text-gray-900">
                    {getTxTypeLabel(entry.tx_type)}
                  </div>
                  {entry.note && (
                    <div className="text-xs text-gray-400">{entry.note}</div>
                  )}
                </div>
                <div className="text-right">
                  <div
                    className={`font-semibold ${
                      entry.amount > 0 ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {entry.amount > 0 ? '+' : ''}
                    {entry.amount} {entry.currency.toUpperCase()}
                  </div>
                  <div className="text-xs text-gray-400">
                    {formatDate(entry.created_at)}
                  </div>
                </div>
              </div>
            ))}

            {history?.entries.length === 0 && (
              <div className="text-center py-8 text-gray-400">
                История транзакций пуста
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

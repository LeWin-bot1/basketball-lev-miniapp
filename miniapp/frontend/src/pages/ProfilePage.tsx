import { useEffect, useState } from 'react';
import { Trophy, TrendingUp, Target, Zap, Award, Pencil, Check, X } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';
import type { PlayerStats } from '../types';
import StatCard from '../components/StatCard';
import PlayerAvatar from '../components/PlayerAvatar';
import MatchCard from '../components/MatchCard';
import { PageLoader } from '../components/LoadingSpinner';
import { useTelegram } from '../hooks/useTelegram';

interface ProfilePageProps {
  isDev?: boolean;
}

const mockStats: PlayerStats = {
  player: {
    user_id: 123456,
    username: 'test_user',
    first_name: 'Тестовый',
    game_nick: 'TestPlayer',
    lev: 1500,
    rating: 1250,
    wins: 42,
    losses: 18,
    draws: 3,
    matches_played: 63,
    stars_pending: 12,
  },
  rank: 15,
  total_players: 250,
  recent_matches: [
    {
      opponent_name: 'Лев',
      player_score: 6,
      opponent_score: 4,
      result: 'win',
      delta_lev: 25,
      currency: 'lev',
      mode: 'Матчмейкинг',
      played_at: Date.now() / 1000 - 3600,
    },
  ],
  win_streak: 5,
  best_win_streak: 12,
};

export default function ProfilePage({ isDev = false }: ProfilePageProps) {
  const { hapticFeedback, showAlert } = useTelegram();
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [nick, setNick] = useState('');
  const [saving, setSaving] = useState(false);

  async function loadProfile() {
    try {
      setLoading(true);
      if (isDev) {
        await new Promise((r) => setTimeout(r, 300));
        setStats(mockStats);
        setNick(mockStats.player.game_nick || '');
      } else {
        const data = await api.profile.getMy();
        setStats(data);
        setNick(data.player.game_nick || '');
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки профиля');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProfile();
  }, [isDev]);

  async function saveNick() {
    if (isDev) {
      setStats((prev) =>
        prev ? { ...prev, player: { ...prev.player, game_nick: nick.trim() } } : prev
      );
      setEditing(false);
      return;
    }
    try {
      setSaving(true);
      const updated = await api.profile.updateNick(nick);
      setStats((prev) => (prev ? { ...prev, player: updated } : prev));
      setNick(updated.game_nick || nick);
      setEditing(false);
      hapticFeedback('light');
    } catch (err) {
      showAlert(err instanceof Error ? err.message : 'Не удалось сохранить ник');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <PageLoader />;

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-50 text-red-600 p-4 rounded-xl text-center">{error}</div>
      </div>
    );
  }

  if (!stats) return null;

  const { player, rank, total_players, win_streak, best_win_streak, recent_matches } = stats;
  const decided = player.wins + player.losses;
  const winRate = decided > 0 ? Math.round((player.wins / decided) * 100) : 0;
  const displayName = player.game_nick || player.first_name || 'Игрок';

  const pieData = [
    { name: 'Победы', value: player.wins, color: '#22c55e' },
    { name: 'Поражения', value: player.losses, color: '#ef4444' },
    { name: 'Ничьи', value: player.draws, color: '#9ca3af' },
  ].filter((d) => d.value > 0);

  return (
    <div className="p-4 page-transition">
      <div className="bg-gradient-to-r from-primary-500 to-primary-600 rounded-2xl p-6 text-white mb-6">
        <div className="flex items-center gap-4">
          <PlayerAvatar name={displayName} size="lg" />
          <div className="flex-1 min-w-0">
            {editing ? (
              <div className="flex items-center gap-2">
                <input
                  value={nick}
                  onChange={(e) => setNick(e.target.value)}
                  maxLength={20}
                  className="w-full rounded-lg px-3 py-2 text-gray-900 text-sm"
                  placeholder="Как тебя называть?"
                  autoFocus
                />
                <button
                  onClick={saveNick}
                  disabled={saving}
                  className="p-2 rounded-lg bg-white/20"
                >
                  <Check size={16} />
                </button>
                <button
                  onClick={() => {
                    setEditing(false);
                    setNick(player.game_nick || '');
                  }}
                  className="p-2 rounded-lg bg-white/20"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold truncate">{displayName}</h1>
                <button
                  onClick={() => setEditing(true)}
                  className="p-1 rounded-md bg-white/20"
                  aria-label="Изменить ник"
                >
                  <Pencil size={14} />
                </button>
              </div>
            )}
            {player.username && <p className="text-primary-100">@{player.username}</p>}
            <div className="flex items-center gap-2 mt-2">
              <Award size={16} />
              <span className="text-sm">
                #{rank} из {total_players} игроков
              </span>
            </div>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-primary-400 grid grid-cols-2 gap-3">
          <div>
            <div className="text-primary-100 text-sm">Баланс Lev</div>
            <div className="text-2xl font-bold">{player.lev.toLocaleString()}</div>
          </div>
          <div>
            <div className="text-primary-100 text-sm">Stars</div>
            <div className="text-2xl font-bold">{player.stars_pending ?? 0}</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-6">
        <StatCard label="Рейтинг" value={player.rating} icon={<TrendingUp size={18} />} />
        <StatCard
          label="Винрейт"
          value={`${winRate}%`}
          subValue={winRate >= 50 ? '↑' : '↓'}
          trend={winRate >= 50 ? 'up' : 'down'}
          icon={<Target size={18} />}
        />
        <StatCard label="Матчей" value={player.matches_played} icon={<Trophy size={18} />} />
        <StatCard
          label="Серия побед"
          value={win_streak}
          subValue={best_win_streak ? `рекорд ${best_win_streak}` : undefined}
          icon={<Zap size={18} />}
        />
      </div>

      <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 mb-6">
        <h3 className="font-semibold text-gray-900 mb-4">Статистика матчей</h3>
        <div className="flex items-center gap-8">
          <div className="w-32 h-32">
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={30}
                    outerRadius={50}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={entry.name + index} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="w-full h-full flex items-center justify-center text-xs text-gray-400">
                Нет игр
              </div>
            )}
          </div>
          <div className="flex-1 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Победы</span>
              <span className="font-semibold text-green-600">{player.wins}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Поражения</span>
              <span className="font-semibold text-red-600">{player.losses}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Ничьи</span>
              <span className="font-semibold text-gray-500">{player.draws}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">История матчей</h3>
        <span className="text-xs text-gray-400">{recent_matches.length}</span>
      </div>
      <div className="space-y-2">
        {recent_matches.map((match, index) => (
          <MatchCard key={match.match_id || index} match={match} />
        ))}
        {recent_matches.length === 0 && (
          <div className="text-center py-8 text-gray-400 text-sm">
            Пока нет сыгранных матчей. Они появятся здесь после игры в боте.
          </div>
        )}
      </div>
    </div>
  );
}

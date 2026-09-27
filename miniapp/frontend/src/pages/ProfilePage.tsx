import { useEffect, useState } from 'react';
import { Trophy, TrendingUp, Target, Zap, Award } from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';
import { api } from '../api/client';
import type { PlayerStats } from '../types';
import StatCard from '../components/StatCard';
import PlayerAvatar from '../components/PlayerAvatar';
import { PageLoader } from '../components/LoadingSpinner';

interface ProfilePageProps {
  isDev?: boolean;
}

// Моковые данные для разработки
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
  },
  rank: 15,
  total_players: 250,
  recent_matches: [],
  win_streak: 5,
  best_win_streak: 12,
};

export default function ProfilePage({ isDev = false }: ProfilePageProps) {
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadProfile() {
      try {
        setLoading(true);
        if (isDev) {
          // В режиме разработки используем моковые данные
          await new Promise((r) => setTimeout(r, 500));
          setStats(mockStats);
        } else {
          const data = await api.profile.getMy();
          setStats(data);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Ошибка загрузки профиля');
      } finally {
        setLoading(false);
      }
    }

    loadProfile();
  }, [isDev]);

  if (loading) {
    return <PageLoader />;
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-50 text-red-600 p-4 rounded-xl text-center">
          {error}
        </div>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  const { player, rank, total_players, win_streak } = stats;
  const winRate =
    player.wins + player.losses > 0
      ? Math.round((player.wins / (player.wins + player.losses)) * 100)
      : 0;

  // Данные для круговой диаграммы
  const pieData = [
    { name: 'Победы', value: player.wins, color: '#22c55e' },
    { name: 'Поражения', value: player.losses, color: '#ef4444' },
    { name: 'Ничьи', value: player.draws, color: '#9ca3af' },
  ].filter((d) => d.value > 0);

  // Данные для графика прогресса (моковые)
  const progressData = [
    { name: 'Пн', wins: 3, losses: 1 },
    { name: 'Вт', wins: 5, losses: 2 },
    { name: 'Ср', wins: 4, losses: 3 },
    { name: 'Чт', wins: 6, losses: 1 },
    { name: 'Пт', wins: 8, losses: 2 },
    { name: 'Сб', wins: 5, losses: 4 },
    { name: 'Вс', wins: 7, losses: 3 },
  ];

  return (
    <div className="p-4 page-transition">
      {/* Заголовок профиля */}
      <div className="bg-gradient-to-r from-primary-500 to-primary-600 rounded-2xl p-6 text-white mb-6">
        <div className="flex items-center gap-4">
          <PlayerAvatar
            name={player.first_name || player.username || 'Player'}
            size="lg"
          />
          <div className="flex-1">
            <h1 className="text-xl font-bold">
              {player.game_nick || player.first_name || 'Игрок'}
            </h1>
            {player.username && (
              <p className="text-primary-100">@{player.username}</p>
            )}
            <div className="flex items-center gap-2 mt-2">
              <Award size={16} />
              <span className="text-sm">
                #{rank} из {total_players} игроков
              </span>
            </div>
          </div>
        </div>
        
        {/* Баланс */}
        <div className="mt-4 pt-4 border-t border-primary-400">
          <div className="flex justify-between items-center">
            <span className="text-primary-100">Баланс Lev</span>
            <span className="text-2xl font-bold">{player.lev.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Статистика */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <StatCard
          label="Рейтинг"
          value={player.rating}
          icon={<TrendingUp size={18} />}
        />
        <StatCard
          label="Винрейт"
          value={`${winRate}%`}
          subValue={winRate >= 50 ? '↑' : '↓'}
          trend={winRate >= 50 ? 'up' : 'down'}
          icon={<Target size={18} />}
        />
        <StatCard
          label="Всего матчей"
          value={player.matches_played}
          icon={<Trophy size={18} />}
        />
        <StatCard
          label="Серия побед"
          value={win_streak}
          icon={<Zap size={18} />}
        />
      </div>

      {/* График побед/поражений */}
      <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 mb-6">
        <h3 className="font-semibold text-gray-900 mb-4">Статистика матчей</h3>
        <div className="flex items-center gap-8">
          {/* Круговая диаграмма */}
          <div className="w-32 h-32">
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
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          
          {/* Легенда */}
          <div className="flex-1 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className="text-sm text-gray-600">Победы</span>
              </div>
              <span className="font-semibold">{player.wins}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <span className="text-sm text-gray-600">Поражения</span>
              </div>
              <span className="font-semibold">{player.losses}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-gray-400" />
                <span className="text-sm text-gray-600">Ничьи</span>
              </div>
              <span className="font-semibold">{player.draws}</span>
            </div>
          </div>
        </div>
      </div>

      {/* График активности за неделю */}
      <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
        <h3 className="font-semibold text-gray-900 mb-4">Активность за неделю</h3>
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={progressData}>
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 12, fill: '#9ca3af' }}
              />
              <YAxis hide />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                }}
              />
              <Bar
                dataKey="wins"
                fill="#22c55e"
                radius={[4, 4, 0, 0]}
                name="Победы"
              />
              <Bar
                dataKey="losses"
                fill="#ef4444"
                radius={[4, 4, 0, 0]}
                name="Поражения"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

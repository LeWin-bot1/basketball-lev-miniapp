import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '../api/client';
import type { GlobalLeaderboard, LeaderboardEntry } from '../types';
import LeaderboardRow from '../components/LeaderboardRow';
import { PageLoader } from '../components/LoadingSpinner';

// Моковые данные
const mockLeaderboard: GlobalLeaderboard = {
  entries: Array.from({ length: 20 }, (_, i) => ({
    rank: i + 1,
    user_id: 1000 + i,
    username: `player_${i + 1}`,
    first_name: `Игрок ${i + 1}`,
    wins: 100 - i * 4,
    losses: 20 + i * 2,
    rating: 1500 - i * 20,
    is_current_user: i === 14,
  })),
  total_players: 250,
  current_user_rank: 15,
  page: 1,
  per_page: 50,
  total_pages: 5,
};

export default function LeaderboardPage() {
  const navigate = useNavigate();
  const [leaderboard, setLeaderboard] = useState<GlobalLeaderboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    async function loadLeaderboard() {
      try {
        setLoading(true);
        // В режиме разработки используем моковые данные
        const isDev = import.meta.env.DEV;
        if (isDev) {
          await new Promise((r) => setTimeout(r, 300));
          setLeaderboard(mockLeaderboard);
        } else {
          const data = await api.leaderboard.get(page);
          setLeaderboard(data);
        }
      } catch (err) {
        console.error('Error loading leaderboard:', err);
      } finally {
        setLoading(false);
      }
    }

    loadLeaderboard();
  }, [page]);

  if (loading && !leaderboard) {
    return <PageLoader />;
  }

  if (!leaderboard) {
    return (
      <div className="p-4 text-center text-gray-500">
        Не удалось загрузить таблицу лидеров
      </div>
    );
  }

  return (
    <div className="p-4 page-transition">
      {/* Заголовок */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Таблица лидеров</h1>
        <p className="text-gray-500 mt-1">
          Всего игроков: {leaderboard.total_players.toLocaleString()}
        </p>
      </div>

      {/* Твоя позиция */}
      {leaderboard.current_user_rank && (
        <div className="bg-primary-50 rounded-xl p-4 mb-6 border border-primary-200">
          <div className="text-sm text-primary-600 font-medium">Твоя позиция</div>
          <div className="text-3xl font-bold text-primary-700">
            #{leaderboard.current_user_rank}
          </div>
        </div>
      )}

      {/* Список */}
      <div className="space-y-2 mb-6">
        {leaderboard.entries.map((entry: LeaderboardEntry) => (
          <LeaderboardRow
            key={entry.user_id}
            rank={entry.rank}
            name={entry.game_nick || entry.first_name || entry.username || `ID: ${entry.user_id}`}
            username={entry.username}
            wins={entry.wins}
            losses={entry.losses}
            rating={entry.rating}
            isCurrentUser={entry.is_current_user}
            onClick={() => navigate(`/player/${entry.user_id}`)}
          />
        ))}
      </div>

      {/* Пагинация */}
      {leaderboard.total_pages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-2 rounded-lg bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={20} />
          </button>
          <span className="text-sm text-gray-600">
            Страница {page} из {leaderboard.total_pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(leaderboard.total_pages, p + 1))}
            disabled={page === leaderboard.total_pages}
            className="p-2 rounded-lg bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronRight size={20} />
          </button>
        </div>
      )}
    </div>
  );
}

import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Award, Trophy, Target } from 'lucide-react';
import { api } from '../api/client';
import type { PlayerStats } from '../types';
import PlayerAvatar from '../components/PlayerAvatar';
import StatCard from '../components/StatCard';
import MatchCard from '../components/MatchCard';
import { PageLoader } from '../components/LoadingSpinner';

export default function PlayerViewPage() {
  const { userId } = useParams();
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      if (!userId) return;
      try {
        setLoading(true);
        const data = await api.profile.getById(Number(userId));
        setStats(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Игрок не найден');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [userId]);

  if (loading) return <PageLoader />;
  if (error || !stats) {
    return (
      <div className="p-4">
        <div className="bg-red-50 text-red-600 p-4 rounded-xl text-center">
          {error || 'Игрок не найден'}
        </div>
      </div>
    );
  }

  const { player, rank, total_players, recent_matches } = stats;
  const name = player.game_nick || player.first_name || `ID ${player.user_id}`;
  const decided = player.wins + player.losses;
  const winRate = decided > 0 ? Math.round((player.wins / decided) * 100) : 0;

  return (
    <div className="p-4 page-transition">
      <div className="bg-white rounded-2xl p-5 border border-gray-100 mb-6">
        <div className="flex items-center gap-4">
          <PlayerAvatar name={name} size="lg" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">{name}</h1>
            {player.username && <p className="text-gray-400">@{player.username}</p>}
            <div className="flex items-center gap-1 mt-1 text-sm text-gray-500">
              <Award size={14} />
              #{rank} из {total_players}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-6">
        <StatCard label="Рейтинг" value={player.rating} icon={<Trophy size={18} />} />
        <StatCard label="Винрейт" value={`${winRate}%`} icon={<Target size={18} />} />
        <StatCard label="Победы" value={player.wins} />
        <StatCard label="Поражения" value={player.losses} />
      </div>

      <h3 className="font-semibold text-gray-900 mb-3">Последние матчи</h3>
      <div className="space-y-2">
        {recent_matches.map((match, index) => (
          <MatchCard key={match.match_id || index} match={match} />
        ))}
        {recent_matches.length === 0 && (
          <div className="text-center py-8 text-gray-400 text-sm">Нет матчей</div>
        )}
      </div>
    </div>
  );
}

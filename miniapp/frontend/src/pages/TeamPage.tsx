import { useEffect, useState } from 'react';
import { Users, Crown, Trophy, UserPlus } from 'lucide-react';
import { api } from '../api/client';
import type { TeamInfo, TeamMember } from '../types';
import PlayerAvatar from '../components/PlayerAvatar';
import { PageLoader } from '../components/LoadingSpinner';

// Моковые данные
const mockTeam: TeamInfo = {
  team_id: 123,
  name: 'Alpha Squad',
  creator_id: 1001,
  wins: 45,
  losses: 12,
  tournament_points: 135,
  created_at: Date.now() / 1000 - 86400 * 30,
  members: [
    {
      user_id: 1001,
      username: 'captain_pro',
      first_name: 'Капитан',
      tournament_points: 60,
      joined_at: Date.now() / 1000 - 86400 * 30,
      wins: 20,
      losses: 5,
    },
    {
      user_id: 1002,
      username: 'sniper',
      first_name: 'Снайпер',
      tournament_points: 45,
      joined_at: Date.now() / 1000 - 86400 * 20,
      wins: 15,
      losses: 4,
    },
    {
      user_id: 1003,
      username: 'rookie',
      first_name: 'Новичок',
      tournament_points: 30,
      joined_at: Date.now() / 1000 - 86400 * 5,
      wins: 10,
      losses: 3,
    },
  ],
  rank: 5,
};

export default function TeamPage() {
  const [team, setTeam] = useState<TeamInfo | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadTeam() {
      try {
        setLoading(true);
        const isDev = import.meta.env.DEV;
        
        if (isDev) {
          await new Promise((r) => setTimeout(r, 300));
          setTeam(mockTeam);
        } else {
          const data = await api.team.getMy();
          setTeam(data);
        }
      } catch (err) {
        console.error('Error loading team:', err);
        setTeam(null);
      } finally {
        setLoading(false);
      }
    }

    loadTeam();
  }, []);

  if (loading) {
    return <PageLoader />;
  }

  // Нет команды
  if (team === null) {
    return (
      <div className="p-4 page-transition">
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mb-4">
            <Users size={40} className="text-gray-400" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            У вас нет команды
          </h2>
          <p className="text-gray-500 mb-6 max-w-xs">
            Создайте команду или примите приглашение от друзей через бота
          </p>
          <button className="btn btn-primary">
            <UserPlus size={18} className="inline mr-2" />
            Создать команду в боте
          </button>
        </div>
      </div>
    );
  }

  if (!team) {
    return null;
  }

  const winRate = team.wins + team.losses > 0
    ? Math.round((team.wins / (team.wins + team.losses)) * 100)
    : 0;

  return (
    <div className="p-4 page-transition">
      {/* Заголовок команды */}
      <div className="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-2xl p-6 text-white mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-14 h-14 bg-white/20 rounded-xl flex items-center justify-center">
            <Users size={28} />
          </div>
          <div>
            <h1 className="text-xl font-bold">{team.name}</h1>
            {team.rank && (
              <div className="flex items-center gap-1 text-blue-100">
                <Trophy size={14} />
                <span className="text-sm">#{team.rank} в турнире</span>
              </div>
            )}
          </div>
        </div>

        {/* Статистика команды */}
        <div className="grid grid-cols-3 gap-4 pt-4 border-t border-white/20">
          <div className="text-center">
            <div className="text-2xl font-bold">{team.wins}</div>
            <div className="text-xs text-blue-100">Победы</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">{team.losses}</div>
            <div className="text-xs text-blue-100">Поражения</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">{winRate}%</div>
            <div className="text-xs text-blue-100">Винрейт</div>
          </div>
        </div>
      </div>

      {/* Очки команды */}
      <div className="bg-yellow-50 rounded-xl p-4 mb-6 border border-yellow-200">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-yellow-700">Турнирные очки</div>
            <div className="text-2xl font-bold text-yellow-800">
              {team.tournament_points}
            </div>
          </div>
          <Trophy className="text-yellow-500" size={32} />
        </div>
      </div>

      {/* Участники команды */}
      <div className="mb-4">
        <h2 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Users size={18} />
          Участники ({team.members.length}/3)
        </h2>
        
        <div className="space-y-3">
          {team.members.map((member: TeamMember) => (
            <div
              key={member.user_id}
              className="bg-white rounded-xl p-4 border border-gray-100"
            >
              <div className="flex items-center gap-3">
                <PlayerAvatar
                  name={member.first_name || member.username}
                  size="md"
                />
                <div className="flex-1">
                  <div className="font-medium text-gray-900 flex items-center gap-2">
                    {member.first_name || member.username}
                    {member.user_id === team.creator_id && (
                      <Crown size={14} className="text-yellow-500" />
                    )}
                  </div>
                  {member.username && (
                    <div className="text-xs text-gray-400">@{member.username}</div>
                  )}
                </div>
                <div className="text-right">
                  <div className="font-semibold text-primary-600">
                    {member.tournament_points} оч.
                  </div>
                  <div className="text-xs text-gray-400">
                    {member.wins}W / {member.losses}L
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Кнопка приглашения */}
      {team.members.length < 3 && (
        <button className="w-full btn btn-secondary mt-4">
          <UserPlus size={18} className="inline mr-2" />
          Пригласить игрока (в боте)
        </button>
      )}
    </div>
  );
}

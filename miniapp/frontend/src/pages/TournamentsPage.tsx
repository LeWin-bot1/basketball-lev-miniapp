import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trophy, Users, Clock, Medal, Wifi, WifiOff } from 'lucide-react';
import { api } from '../api/client';
import { useTournamentWebSocket } from '../hooks/useWebSocket';
import type { TournamentLeaderboard, TeamLeaderboard, TournamentPlayer, TournamentTeam } from '../types';
import LeaderboardRow from '../components/LeaderboardRow';
import { PageLoader } from '../components/LoadingSpinner';

type TabType = 'solo' | 'team';

// Моковые данные
const mockSoloTournament: TournamentLeaderboard = {
  type: 'solo',
  players: Array.from({ length: 15 }, (_, i) => ({
    user_id: 1000 + i,
    username: `champ_${i + 1}`,
    first_name: `Чемпион ${i + 1}`,
    wins: 50 - i * 3,
    losses: 5 + i,
    points: (50 - i * 3) * 3,
  })),
  total_participants: 120,
  current_user_rank: 8,
};

const mockTeamTournament: TeamLeaderboard = {
  teams: Array.from({ length: 10 }, (_, i) => ({
    team_id: 100 + i,
    name: `Team Alpha ${i + 1}`,
    wins: 30 - i * 2,
    losses: 5 + i,
    tournament_points: (30 - i * 2) * 3,
    members: [],
  })),
  total_teams: 45,
  current_team_rank: 5,
};

function formatDeadline(isoDate?: string): string {
  if (!isoDate) return 'Дата уточняется';
  const end = new Date(`${isoDate}T23:59:59`);
  const diff = end.getTime() - Date.now();
  if (diff <= 0) return 'Турнир завершён';
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  if (days > 0) return `${days} дн. ${hours} ч.`;
  return `${hours} ч.`;
}

export default function TournamentsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('solo');
  const [soloData, setSoloData] = useState<TournamentLeaderboard | null>(null);
  const [teamData, setTeamData] = useState<TeamLeaderboard | null>(null);
  const [loading, setLoading] = useState(true);

  // WebSocket для real-time обновлений (только в production)
  const isDev = import.meta.env.DEV;
  
  const handleSoloUpdate = useCallback((data: unknown) => {
    const message = data as { type: string; data?: { players?: TournamentPlayer[]; total_participants?: number } };
    if (message.type === 'tournament_update' || message.type === 'initial_data') {
      if (message.data?.players) {
        setSoloData((prev) => prev ? {
          ...prev,
          players: message.data!.players!,
          total_participants: message.data!.total_participants ?? prev.total_participants,
        } : null);
      }
    }
  }, []);

  const handleTeamUpdate = useCallback((data: unknown) => {
    const message = data as { type: string; data?: { teams?: TournamentTeam[]; total_teams?: number } };
    if (message.type === 'tournament_update' || message.type === 'initial_data') {
      if (message.data?.teams) {
        setTeamData((prev) => prev ? {
          ...prev,
          teams: message.data!.teams!,
          total_teams: message.data!.total_teams ?? prev.total_teams,
        } : null);
      }
    }
  }, []);

  // Подключаем WebSocket только если не в режиме разработки
  const { isConnected: soloConnected } = useTournamentWebSocket(
    'solo',
    !isDev ? handleSoloUpdate : undefined
  );
  const { isConnected: teamConnected } = useTournamentWebSocket(
    'team', 
    !isDev ? handleTeamUpdate : undefined
  );

  const isWsConnected = activeTab === 'solo' ? soloConnected : teamConnected;

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        
        if (isDev) {
          await new Promise((r) => setTimeout(r, 300));
          setSoloData(mockSoloTournament);
          setTeamData(mockTeamTournament);
        } else {
          const [solo, team] = await Promise.all([
            api.tournaments.getSolo(),
            api.tournaments.getTeam(),
          ]);
          setSoloData(solo);
          setTeamData(team);
        }
      } catch (err) {
        console.error('Error loading tournaments:', err);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [isDev]);

  if (loading) {
    return <PageLoader />;
  }

  return (
    <div className="p-4 page-transition">
      {/* Заголовок */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Trophy className="text-primary-500" />
            Турниры
          </h1>
          {/* Индикатор WebSocket соединения */}
          {!isDev && (
            <div className={`flex items-center gap-1 text-xs ${isWsConnected ? 'text-green-500' : 'text-gray-400'}`}>
              {isWsConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
              {isWsConnected ? 'Live' : 'Offline'}
            </div>
          )}
        </div>
        <p className="text-gray-500 mt-1">Текущие турнирные таблицы</p>
      </div>

      {/* Информация о турнире */}
      <div className="bg-gradient-to-r from-purple-500 to-indigo-600 rounded-2xl p-4 mb-6 text-white">
        <div className="flex items-center gap-2 mb-2">
          <Clock size={18} />
          <span className="text-sm opacity-90">До конца турнира</span>
        </div>
        <div className="text-2xl font-bold">
          {formatDeadline(
            activeTab === 'solo'
              ? soloData?.tournament_end_date
              : teamData?.tournament_end_date
          )}
        </div>
        <div className="mt-3 text-sm opacity-75">
          Приз:{' '}
          {activeTab === 'solo'
            ? soloData?.prize || 'майка Prada'
            : teamData?.prize || '10000 тг Sta'}
        </div>
      </div>

      {/* Табы */}
      <div className="flex bg-gray-100 rounded-xl p-1 mb-6">
        <button
          onClick={() => setActiveTab('solo')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'solo'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500'
          }`}
        >
          <Trophy size={16} className="inline mr-1" />
          Одиночный
        </button>
        <button
          onClick={() => setActiveTab('team')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'team'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500'
          }`}
        >
          <Users size={16} className="inline mr-1" />
          Командный
        </button>
      </div>

      {/* Твоя позиция */}
      {activeTab === 'solo' && soloData?.current_user_rank && (
        <div className="bg-yellow-50 rounded-xl p-4 mb-4 border border-yellow-200">
          <div className="flex items-center gap-2">
            <Medal className="text-yellow-600" size={20} />
            <span className="text-sm text-yellow-700">Твоя позиция в турнире:</span>
            <span className="font-bold text-yellow-800">#{soloData.current_user_rank}</span>
          </div>
        </div>
      )}
      
      {activeTab === 'team' && teamData?.current_team_rank && (
        <div className="bg-blue-50 rounded-xl p-4 mb-4 border border-blue-200">
          <div className="flex items-center gap-2">
            <Users className="text-blue-600" size={20} />
            <span className="text-sm text-blue-700">Позиция твоей команды:</span>
            <span className="font-bold text-blue-800">#{teamData.current_team_rank}</span>
          </div>
        </div>
      )}

      {/* Список */}
      <div className="space-y-2">
        {activeTab === 'solo' &&
          (soloData?.players.length ? (
            soloData.players.map((player: TournamentPlayer, index: number) => (
              <LeaderboardRow
                key={player.user_id}
                rank={index + 1}
                name={player.game_nick || player.first_name || player.username || `ID: ${player.user_id}`}
                username={player.username}
                wins={player.wins}
                losses={player.losses}
                points={player.points}
                onClick={() => navigate(`/player/${player.user_id}`)}
              />
            ))
          ) : (
            <div className="text-center py-10 text-gray-400 text-sm">
              Таблица одиночного турнира пуста. Очки идут за матчи на Lev.
            </div>
          ))}

        {activeTab === 'team' && !teamData?.teams.length && (
          <div className="text-center py-10 text-gray-400 text-sm">
            Командная таблица пуста. Создай команду в боте и сыграй матч.
          </div>
        )}

        {activeTab === 'team' &&
          teamData?.teams.map((team: TournamentTeam, index: number) => (
            <div
              key={team.team_id}
              className="bg-white rounded-xl p-4 border border-gray-100"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 text-center">
                  {index < 3 ? (
                    <span className="text-xl">
                      {index === 0 && '🥇'}
                      {index === 1 && '🥈'}
                      {index === 2 && '🥉'}
                    </span>
                  ) : (
                    <span className="text-sm font-medium text-gray-400">
                      #{index + 1}
                    </span>
                  )}
                </div>
                <div className="flex-1">
                  <div className="font-semibold text-gray-900">{team.name}</div>
                  <div className="text-xs text-gray-400">
                    {team.wins}W / {team.losses}L
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-primary-600">
                    {team.tournament_points} очков
                  </div>
                </div>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}

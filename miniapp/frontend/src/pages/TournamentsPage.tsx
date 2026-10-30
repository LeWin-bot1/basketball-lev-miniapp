import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trophy, Clock, Medal, Users, Gift, Wifi, WifiOff, Crown } from 'lucide-react';
import { api } from '../api/client';
import { useTournamentWebSocket } from '../hooks/useWebSocket';
import type { TournamentLeaderboard, TournamentPlayer } from '../types';
import LeaderboardRow from '../components/LeaderboardRow';
import { PageLoader } from '../components/LoadingSpinner';

// Моковые данные для разработки
const mockTournament: TournamentLeaderboard = {
  type: 'solo',
  players: Array.from({ length: 12 }, (_, i) => ({
    user_id: 1000 + i,
    username: `champ_${i + 1}`,
    first_name: `Игрок ${i + 1}`,
    wins: 40 - i * 3,
    losses: 4 + i,
    points: (40 - i * 3) * 3,
  })),
  total_participants: 87,
  current_user_rank: 6,
  prize: 'майка Prada',
  status: 'active',
  end_ts: Math.floor(Date.now() / 1000) + 3 * 86400 + 5 * 3600,
  winners: [],
};

function playerName(p: TournamentPlayer): string {
  return p.game_nick || p.first_name || (p.username ? `@${p.username}` : `ID ${p.user_id}`);
}

function endTs(data: TournamentLeaderboard | null): number | null {
  if (!data) return null;
  if (data.end_ts) return data.end_ts;
  if (data.tournament_end_date) return Math.floor(new Date(`${data.tournament_end_date}T00:00:00`).getTime() / 1000);
  return null;
}

/** Живой обратный отсчёт: дни / часы / минуты / секунды */
function useCountdown(target: number | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!target) return null;
  const left = Math.max(0, target * 1000 - now);
  return {
    done: left === 0,
    days: Math.floor(left / 86_400_000),
    hours: Math.floor((left / 3_600_000) % 24),
    minutes: Math.floor((left / 60_000) % 60),
    seconds: Math.floor((left / 1000) % 60),
  };
}

function TimeBox({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex-1 bg-white/15 backdrop-blur rounded-xl py-2 text-center">
      <div className="text-2xl font-extrabold tabular-nums leading-tight">
        {String(value).padStart(2, '0')}
      </div>
      <div className="text-[11px] uppercase tracking-wide opacity-80">{label}</div>
    </div>
  );
}

const PODIUM = [
  { place: 2, medal: '🥈', height: 'h-20', ring: 'ring-gray-300', bg: 'from-gray-100 to-gray-200' },
  { place: 1, medal: '🥇', height: 'h-28', ring: 'ring-yellow-400', bg: 'from-yellow-100 to-amber-200' },
  { place: 3, medal: '🥉', height: 'h-16', ring: 'ring-orange-300', bg: 'from-orange-100 to-orange-200' },
];

function Podium({
  top,
  onOpen,
}: {
  top: TournamentPlayer[];
  onOpen: (id: number) => void;
}) {
  return (
    <div className="flex items-end justify-center gap-2">
      {PODIUM.map(({ place, medal, height, ring, bg }) => {
        const p = top[place - 1];
        return (
          <div key={place} className="flex-1 flex flex-col items-center min-w-0">
            {p ? (
              <button
                onClick={() => onOpen(p.user_id)}
                className="flex flex-col items-center w-full min-w-0 mb-2"
              >
                {place === 1 && <Crown size={20} className="text-yellow-500 mb-1" />}
                <div
                  className={`w-12 h-12 rounded-full bg-white ring-4 ${ring} flex items-center justify-center text-2xl shadow`}
                >
                  {medal}
                </div>
                <div className="mt-1 text-sm font-semibold text-gray-900 truncate w-full text-center">
                  {playerName(p)}
                </div>
                <div className="text-xs text-gray-500">{p.wins} побед</div>
              </button>
            ) : (
              <div className="mb-2 text-xs text-gray-300">—</div>
            )}
            <div
              className={`w-full ${height} rounded-t-xl bg-gradient-to-b ${bg} flex items-start justify-center pt-2 text-lg font-extrabold text-gray-700`}
            >
              {place}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function TournamentsPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<TournamentLeaderboard | null>(null);
  const [loading, setLoading] = useState(true);
  const isDev = import.meta.env.DEV;

  const handleUpdate = useCallback((msg: unknown) => {
    const m = msg as { type: string; data?: { players?: TournamentPlayer[]; total_participants?: number } };
    if ((m.type === 'tournament_update' || m.type === 'initial_data') && m.data?.players) {
      setData((prev) =>
        prev
          ? {
              ...prev,
              players: m.data!.players!,
              total_participants: m.data!.total_participants ?? prev.total_participants,
            }
          : prev
      );
    }
  }, []);

  const { isConnected } = useTournamentWebSocket('solo', !isDev ? handleUpdate : undefined);

  useEffect(() => {
    (async () => {
      try {
        if (isDev) {
          await new Promise((r) => setTimeout(r, 300));
          setData(mockTournament);
        } else {
          setData(await api.tournaments.getSolo());
        }
      } catch (err) {
        console.error('Error loading tournament:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [isDev]);

  const countdown = useCountdown(endTs(data));

  if (loading) return <PageLoader />;

  const finished = data?.status === 'finished' || countdown?.done === true;
  const players = data?.players ?? [];
  const top = finished && data?.winners?.length ? data.winners : players.slice(0, 3);
  const endDate = endTs(data)
    ? new Date(endTs(data)! * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
    : null;
  const openPlayer = (id: number) => navigate(`/player/${id}`);

  return (
    <div className="p-4 page-transition">
      {/* Заголовок */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Trophy className="text-primary-500" />
          Турнир
        </h1>
        {!isDev && !finished && (
          <div className={`flex items-center gap-1 text-xs ${isConnected ? 'text-green-500' : 'text-gray-400'}`}>
            {isConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
            {isConnected ? 'Live' : 'Offline'}
          </div>
        )}
      </div>

      {/* Главная карточка: обратный отсчёт или итог */}
      <div
        className={`rounded-2xl p-4 mb-5 text-white shadow-lg ${
          finished
            ? 'bg-gradient-to-br from-gray-700 to-gray-900'
            : 'bg-gradient-to-br from-primary-500 via-primary-600 to-accent-500'
        }`}
      >
        {finished ? (
          <>
            <div className="flex items-center gap-2 text-sm opacity-90">
              <Trophy size={16} /> Турнир завершён{endDate ? ` · ${endDate}` : ''}
            </div>
            <div className="mt-2 text-xl font-extrabold">
              {top[0] ? `Победитель — ${playerName(top[0])} 🎉` : 'Победитель не определён'}
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2 text-sm opacity-90 mb-3">
              <Clock size={16} /> До конца турнира
            </div>
            {countdown && (
              <div className="flex gap-2">
                <TimeBox value={countdown.days} label="дней" />
                <TimeBox value={countdown.hours} label="часов" />
                <TimeBox value={countdown.minutes} label="минут" />
                <TimeBox value={countdown.seconds} label="секунд" />
              </div>
            )}
            {endDate && <div className="mt-3 text-xs opacity-80">Финиш: {endDate}</div>}
          </>
        )}

        <div className="mt-4 flex gap-2 text-sm">
          <div className="flex-1 flex items-center gap-2 bg-white/15 rounded-xl px-3 py-2">
            <Gift size={16} />
            <span className="truncate">{data?.prize || 'майка Prada'}</span>
          </div>
          <div className="flex items-center gap-2 bg-white/15 rounded-xl px-3 py-2">
            <Users size={16} />
            {data?.total_participants ?? 0}
          </div>
        </div>
      </div>

      {/* Пьедестал */}
      {top.length > 0 && (
        <div className="bg-white rounded-2xl p-4 mb-5 border border-gray-100">
          <div className="text-sm font-semibold text-gray-500 mb-3">
            {finished ? '🏆 Победители' : '🔥 Лидеры сейчас'}
          </div>
          <Podium top={top} onOpen={openPlayer} />
        </div>
      )}

      {/* Твоя позиция */}
      {data?.current_user_rank && (
        <div className="bg-yellow-50 rounded-xl p-4 mb-4 border border-yellow-200 flex items-center gap-2">
          <Medal className="text-yellow-600" size={20} />
          <span className="text-sm text-yellow-700">
            {finished ? 'Твоё итоговое место:' : 'Твоя позиция:'}
          </span>
          <span className="font-bold text-yellow-800">#{data.current_user_rank}</span>
        </div>
      )}

      {/* Таблица */}
      <div className="text-sm font-semibold text-gray-500 mb-2">Таблица</div>
      <div className="space-y-2">
        {players.length ? (
          players.map((p, i) => (
            <LeaderboardRow
              key={p.user_id}
              rank={i + 1}
              name={playerName(p)}
              username={p.username}
              wins={p.wins}
              losses={p.losses}
              points={p.points}
              onClick={() => openPlayer(p.user_id)}
            />
          ))
        ) : (
          <div className="text-center py-10 text-gray-400 text-sm">
            {finished
              ? 'Таблица турнира очищена — смотри победителей выше.'
              : 'Пока никто не сыграл. Побеждай в матчах на Lev, чтобы попасть в таблицу!'}
          </div>
        )}
      </div>

      <p className="mt-4 text-center text-xs text-gray-400">
        Победа в матче на Lev = 3 очка. Места — по числу побед.
      </p>
    </div>
  );
}

import PlayerAvatar from './PlayerAvatar';

interface LeaderboardRowProps {
  rank: number;
  name: string;
  username?: string;
  wins: number;
  losses: number;
  rating?: number;
  points?: number;
  isCurrentUser?: boolean;
  onClick?: () => void;
}

export default function LeaderboardRow({
  rank,
  name,
  username,
  wins,
  losses,
  rating,
  points,
  isCurrentUser = false,
  onClick,
}: LeaderboardRowProps) {
  const winRate = wins + losses > 0 ? Math.round((wins / (wins + losses)) * 100) : 0;

  return (
    <div
      onClick={onClick}
      className={`flex items-center gap-3 p-3 rounded-xl transition-colors ${
        isCurrentUser
          ? 'bg-primary-50 border border-primary-200'
          : 'bg-white hover:bg-gray-50'
      } ${onClick ? 'cursor-pointer' : ''}`}
    >
      {/* Rank */}
      <div className="w-8 text-center">
        {rank <= 3 ? (
          <span className="text-xl">
            {rank === 1 && '🥇'}
            {rank === 2 && '🥈'}
            {rank === 3 && '🥉'}
          </span>
        ) : (
          <span className="text-sm font-medium text-gray-400">#{rank}</span>
        )}
      </div>

      {/* Avatar */}
      <PlayerAvatar name={name} size="sm" />

      {/* Name */}
      <div className="flex-1 min-w-0">
        <div className="font-medium text-gray-900 truncate">
          {name}
          {isCurrentUser && (
            <span className="ml-2 text-xs text-primary-500">(вы)</span>
          )}
        </div>
        {username && (
          <div className="text-xs text-gray-400 truncate">@{username}</div>
        )}
      </div>

      {/* Stats */}
      <div className="text-right">
        {points !== undefined ? (
          <div className="font-bold text-primary-600">{points} очков</div>
        ) : (
          <div className="font-semibold text-gray-900">
            {wins}W / {losses}L
          </div>
        )}
        <div className="text-xs text-gray-400">
          {rating !== undefined ? (
            <span>Рейтинг: {rating}</span>
          ) : (
            <span>{winRate}% побед</span>
          )}
        </div>
      </div>
    </div>
  );
}
